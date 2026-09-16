# -*- coding: utf-8 -*-
"""几何处理：简化、量化、压缩编码。输出 build/out/geo.json

阶段二。职责边界：只处理**几何**，不含任何区划归属或注记内容（那属 content.py）。

主要步骤：
1. Douglas-Peucker 简化（dp）——省级 0.003°、市级 0.005°、九段线 0.03°、河流 0.03°；
2. 面积过滤（ring_area）——剔除过小的碎片环，三沙市 460300 例外（保留全部南海岛屿）；
3. 环形状过滤（_ring_ok）——剔除抽稀后被压成一条线的环（见下）；
4. 整数化——坐标 ×SCALE(1000) 取整并去重，把浮点压成整数以减小体积；
5. 河段拼接（stitch）——把 Natural Earth 拆散的碎段按端点就近接成连续河道。

关于精度档（TOL_PROV / TOL_CITY 等常量）：
本图早期用 0.008° / 0.018° 的粗容差，实测导致**群岛被抽稀成一条线**（舟山的 94 个
岛屿只剩 3 个 part），而数据源本身可用顶点共约 37.8 万、当时只用了 15.8%。现改用
高精档，使全国地级单元恢复「多 part 群岛」形态（舟山 94→99 part、尚有 5 个环因原
面积过小被面积阈值剔除，见 MIN_AREA_*）。
调整这四个常量必须同步跑 `python build/build.py`：产物体积与指纹都会变，
README / 核查报告中的数字也要跟着改。

三处容易踩坑的地方：
- `stitch()` 的 max_bridge=0.45° 只连接链的**端点**，不处理「某链端点接在另一链
  中部」的情形。北江、郁江即因此独立成段（视觉上仍在汇合点相接）。
- 河流输出顺序被固定为「RIVER_SPEC 声明序 + 其余键排序」，以保证同一输入产出
  字节一致的 geo.json（便于 build.py 做指纹比对）。
- **`len(out) < 6` 的最小顶点数只能筛掉「本来就退化的环」，不能筛掉「被抽稀压成
  一条线的小岛」**：后者顶点数是 6~9（看起来正常），但 6 个点共线，在屏幕上宽度
  为 0。必须另用 `_ring_ok()` 的面积判据。历史上真发生过：放宽面积阈值后，海岛的
  3 点环经 dp 变成 4 点共线环，写成 path 后在浏览器里**完全不显示**，而构建、
  门禁、verify_tools.js / verify_grid.js 全都报通过。

关于 RIVER_SPEC 的维护：**不要只凭「某区间内有多少个点」判断 NE 是否覆盖某河段**
—— NE 里存在同名碎段，会让计数虚高，从而误判为「整条缺失」而画上手工线。
可靠判据是：删掉手工段后，看 stitch() 输出的 chain 数是否仍为 1。
本文件中多处注释记录了历史上踩过这个坑并已修正的河流（海河、珠江三条支流、
嘉陵江、乌江、岷江、瓯江、钱塘江）。
"""
import json, os, math, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
# 南海诸岛注记的单一真源：东沙三块人造轮廓的甄别逻辑在那里，本文件只负责调用
from isles_data import (AREAS, MIN_SYNTH_AREA_KM2, REMOVE_FROM, is_synthetic,
                       real_parts_near_rings, split_dongshat)

# 已命中并摘除的声明 id（省级 + 市级累计）。用于断言「每条声明都在数据里兑现了」——
# 注意同一批 ring 在省级与市级各存一份，故同一条声明会被命中两次，这里用集合去重。
_synth_seen = set()

SCALE = 1000.0   # 坐标放大倍数（整数编码）

# ---------- 精度档 ----------
# 全部为「度」。数值依据见本文件顶部说明；改动后必须重跑 build.py。
TOL_PROV = 0.003      # 省级 Douglas-Peucker 容差
TOL_CITY = 0.005      # 市级 Douglas-Peucker 容差
TOL_JD   = 0.030      # 九段线容差（直线段为主，可粗）
TOL_RIV  = 0.030      # 河流容差
MIN_AREA_PROV = 0.00002   # 省级最小外环面积（平方度）≈ 0.2 km²
MIN_AREA_CITY = 0.00005   # 市级最小外环面积（平方度）≈ 0.5 km²
# 三沙市（460300）不做面积过滤：南海诸岛本就是星散小环，过滤会整片消失。
NO_AREA_FILTER = ('460300',)

# 抽稀后环的「压塌」判据：外接框任一边长小于此值（度）即认为已被压成一条线。
# 0.004° ≈ 440 m，远小于 SCALE(1000) 下一个坐标单位的可表达范围，
# 故凡通过此判据的环，在屏幕上至少有一维是可分辨的。
MIN_RING_EXTENT = 0.0005


# ---------- Douglas-Peucker ----------
def dp(pts, tol):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    t2 = tol * tol
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            if seg2 == 0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / seg2
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                qx, qy = ax + t * dx, ay + t * dy
                d2 = (px - qx) ** 2 + (py - qy) ** 2
            if d2 > best:
                best, bi = d2, i
        if best > t2:
            keep[bi] = True
            stack.append((a, bi))
            stack.append((bi, b))
    return [p for i, p in enumerate(pts) if keep[i]]


def ring_area(pts):
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _ring_ok(pts):
    """抽稀后的环是否还「撑得开」。

    必须与 `len(pts) < 3` 分开判断，原因见模块 docstring 第三个坑：
    一组共线的 4 个点顶点数合格、面积却为 0，前面的顶点数检查拦不住。
    判据取外接框两边长，而不是面积 —— 面积会把「细长但真实」的岬角、
    沙洲一并误杀，外接框只排除真正退化的情形。
    注：此处比较的是**原始经纬度**（非整数化后的坐标），阈值单位是度。
    """
    if len(pts) < 3:
        return False
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (max(xs) - min(xs)) >= MIN_RING_EXTENT and (max(ys) - min(ys)) >= MIN_RING_EXTENT


def prep_ring(ring, tol, min_area):
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return None
    if ring_area(pts) < min_area:
        return None
    pts = dp(pts, tol)
    if not _ring_ok(pts):
        return None
    # 整数化 + 去重
    out = []
    last = None
    for x, y in pts:
        ix, iy = int(round(x * SCALE)), int(round(y * SCALE))
        if last != (ix, iy):
            out.append(ix); out.append(iy)
            last = (ix, iy)
    if len(out) < 6:
        return None
    return out


def prep_polygon(coords, tol, min_area):
    """GeoJSON Polygon -> [ring, ring...]（首环外环，其余内环）"""
    rings = []
    for i, ring in enumerate(coords):
        r = prep_ring(ring, tol, 0.0 if i else min_area)
        if r:
            rings.append(r)
    return rings if rings else None


def prep_geometry(geom, tol, min_area):
    if not geom:
        return []
    t = geom['type']
    polys = [geom['coordinates']] if t == 'Polygon' else geom['coordinates']
    res = []
    for poly in polys:
        p = prep_polygon(poly, tol, min_area)
        if p:
            res.append(p)
    return res


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


# ---------- 省级 ----------
nat = load(os.path.join(DATA, '100000_full.json'))
provinces = []
jd = None
for f in nat['features']:
    p = f['properties']
    if str(p.get('adcode')) == '100000_JD':
        jd = prep_geometry(f['geometry'], TOL_JD, 0.0)
        continue
    if p.get('level') != 'province':
        continue
    ad = str(p['adcode'])
    g, dids = split_dongshat(ad, prep_geometry(f['geometry'], TOL_PROV, MIN_AREA_PROV))
    _synth_seen.update(dids)
    provinces.append({
        'ad': ad,
        'name': p['name'],
        'abbr': p.get('adchar') or '',
        'c': [round(p['center'][0], 3), round(p['center'][1], 3)],
        'g': g,
    })

print('provinces', len(provinces))
print('JD lines', len(jd))

# ---------- 市级 ----------
# 东沙群岛的三块环礁在 DataV 数据中是**按自身中心生成的圆形 range ring**
# （详见 isles_data.py 的考证），与真实海岸线无关，也不是汕尾市的实际行政区域。
# 它们在数据层面被归给汕尾市，故必须从行政区划几何中**剔除**。
# 剔除的理由不是「尺寸显眼」—— 三块的等效直径为 7.2~14.8 km，在本图比例下
# 主图仅 1.1~2.3 px、附图 0.6~1.2 px，肉眼几乎看不出；真正的理由是
# **把人工 range ring 描成陆地色块，等于宣称「这就是东沙的形状」**。
# 注意同一批 ring 在省级（广东省）与市级（汕尾市）各存一份，两份都要摘，
# 只摘一份会让另一份继续渲染（见 REMOVE_FROM 的说明）。
_real_near = 0       # 声明坐标附近被保留的**真实**陆地环数（应为 1：东沙岛本体）
city_index = {}   # province ad -> [ {ad,name,c,g} ]
for pr in provinces:
    path = os.path.join(DATA, '%s_full.json' % pr['ad'])
    if not os.path.exists(path):
        city_index[pr['ad']] = []
        continue
    gj = load(path)
    items = []
    for f in gj['features']:
        p = f['properties']
        if p.get('level') not in ('city', 'district'):
            continue
        ad = str(p['adcode'])
        # 三沙市（南海诸岛）保留全部岛屿，不做面积过滤
        ma = 0.0 if ad in NO_AREA_FILTER else MIN_AREA_CITY
        g = prep_geometry(f['geometry'], TOL_CITY, ma)
        keep, dids = split_dongshat(ad, g)
        _synth_seen.update(dids)
        # 正面判据：该处的**真实陆地**必须在产物里，而不只是「没被本表摘掉」。
        # 面积过滤在 split_dongshat 之前运行，故真实小岛可能被它提前剔除，
        # 而「声明已兑现」的断言对此完全无感（详见 real_parts_near_rings）。
        if ad in REMOVE_FROM:
            _real_near += len(real_parts_near_rings(keep))
        if not keep and g:
            # 该单元的全部几何都是人造环礁轮廓：保留记录（前端会标为无边界数据），
            # 但不得静默留空而不出声 —— 这属于「数据被我们主动改动」，必须可追溯。
            print('  注：%s(%s) 的全部几何均为东沙群岛人造轮廓，已剔除' % (p['name'], ad))
        items.append({
            'ad': ad,
            'name': p['name'],
            'c': [round(p['center'][0], 3), round(p['center'][1], 3)],
            'g': keep,
        })
    city_index[pr['ad']] = items

tot = sum(len(v) for v in city_index.values())
print('cities', tot)
print('东沙群岛人造轮廓命中并摘除的声明:', '、'.join(sorted(_synth_seen)) or '（无）')

# ---------- 门禁 1：后置条件 —— 产物中不得残留任何人造轮廓 ----------
# 这是最强、也最贴近目标的判据：直接检查**结果**，而不是「我们摘了几个」。
# 它拦得住「摘漏了某个层级/某个单元」—— 本项目真实发生过：同一批 ring 在省级
# 与市级各存一份，只摘市级那份时，ring 仍经省级图层渲染（表现为「摘了却还有印子」），
# 而当时基于「摘除数 == 声明数」的判据对此完全无感。
_leftover = []
for _u in provinces:
    for _poly in (_u['g'] or []):
        if any(is_synthetic(_r) for _r in _poly):
            _leftover.append('省级 %s(%s)' % (_u['name'], _u['ad']))
for _lst in city_index.values():
    for _u in _lst:
        for _poly in (_u['g'] or []):
            if any(is_synthetic(_r) for _r in _poly):
                _leftover.append('市级 %s(%s)' % (_u['name'], _u['ad']))
if _leftover:
    raise SystemExit(
        '产物中仍残留人造轮廓（%d 处）：%s\n'
        '  排查：REMOVE_FROM 是否列全了所有含 ring 的单元（省级与市级是两份独立几何，\n'
        '  同一批 ring 各存一份，只列其中一个会让另一个继续渲染）。\n'
        '  核对：python build/isles_data.py（逐 part 打印判定依据）'
        % (len(_leftover), '、'.join(sorted(set(_leftover)))))

# ---------- 门禁 2：每条声明都必须在数据里兑现 ----------
# 与门禁 1 互补：门禁 1 是「不许漏摘」，本条是「不许空声明」。
# 若上游把 ring 删掉了，门禁 1 会**空过**（没有残留自然没有违规），
# 此时只有本条能发现「声明表已经与数据脱钩」。
_missing = set(AREAS) - _synth_seen
if _missing:
    raise SystemExit(
        '声明表未在数据中兑现：%s 这 %d 条声明未命中任何几何。\n'
        '  说明上游数据已变动（ring 被删除或移到别处），声明表须同步更新。\n'
        '  核对：python build/isles_data.py'
        % ('、'.join(sorted(_missing)), len(_missing)))
print('东沙人造轮廓已摘除，命中的声明共 %d 条（%s）'
      % (len(_synth_seen), '、'.join(sorted(_synth_seen))))

# ---------- 门禁 3：东沙一带的真实陆地必须仍在产物中 ----------
# 只有这条能拦住「被面积过滤提前剔除」——前两条对那种情况无感：
# 面积过滤在 split_dongshat 之前运行，剔掉真实岛后既无残留、声明也已兑现。
if _real_near != 1:
    raise SystemExit(
        '东沙一带的真实陆地缺失：声明坐标附近保留了 %d 个真实陆地环，应为 1 个'
        '（东沙岛本体，约 1.67 km²）。\n'
        '  若为 0，通常是它被 MIN_AREA_CITY(%.5f 平方度 ≈ %.1f km²) 面积过滤'
        '提前剔除了 —— 该过滤在 split_dongshat 之前运行。\n'
        '  核对：python build/isles_data.py'
        % (_real_near, MIN_AREA_CITY, MIN_AREA_CITY * 111.32 * 110.57 * 0.936))

# ---------- 河流（Natural Earth，仅取河道中心线） ----------
RIVER_SPEC = {
    'changjiang': {'name': '长江', 'match': ['Tuotuo', 'Tongtian', 'Jinsha', 'Chang Jiang', 'Yangtze'],
                   'box': (90.0, 122.6, 25.3, 35.8)},
    'huanghe':    {'name': '黄河', 'match': ['Huang'], 'box': (95.4, 119.6, 33.0, 41.3)},
    'heilongjiang': {'name': '黑龙江', 'match': ['Heilong Jiang', 'Amur'], 'box': (119.0, 135.2, 47.0, 54.0)},
    'songhuajiang': {'name': '松花江', 'match': ["Songhua", "Di’er Songhua"], 'box': (123.3, 133.2, 42.2, 48.2), 'minpts': 50},
    'liaohe':     {'name': '辽河', 'match': ['Liao', 'Xiliao'], 'box': (119.3, 124.6, 40.4, 43.9)},
    'huaihe':     {'name': '淮河', 'match': ['Huai'], 'box': (112.6, 120.8, 31.7, 34.0)},
    # 海河：NE 有 Hai（海河干流 47 点）与 Yongding（永定河 93 点）两段真实河道，原先误判为
    # "断开段"而以 5 点手工线替代，现改回真实河道。
    'haihe':      {'name': '海河', 'match': ['Hai', 'Yongding'], 'box': (115.4, 118.0, 38.8, 40.5)},
    'hanjiang':   {'name': '汉江', 'match': ['Han'], 'box': (105.4, 114.9, 30.0, 33.6), 'minpts': 100},
    'xiangjiang': {'name': '湘江', 'match': ['Xiang'], 'box': (110.2, 113.5, 25.1, 29.6)},
    'ganjiang':   {'name': '赣江', 'match': ['Gan'], 'box': (114.0, 116.4, 24.3, 29.7), 'minpts': 100},
    'minjiang':   {'name': '闽江', 'match': ['Min'], 'box': (116.8, 119.5, 25.7, 28.3), 'minpts': 100},
    # 珠江：干流（武宣—虎门段）NE 无对应要素，由下方人工河段补充；西江/北江/东江见下。
    'zhujiang':   {'name': '珠江', 'match': ['Hongshui', 'Nanpan', 'Yu'], 'box': (102.0, 114.3, 21.7, 25.8)},
    # 珠江支流：NE 中本有真实河道（西江 180 点、北江 110 点、东江 178 点），
    # 原先误判为需手工补线（3~4 点折线），现改回真实河道，并按项目既定做法
    # 以 merge_into 并入「珠江」系统、作为独立线段绘制。
    'xijiang':    {'name': '西江', 'match': ['Xi'],   'box': (110.8, 113.8, 22.4, 23.7), 'merge_into': 'zhujiang'},
    'beijiang':   {'name': '北江', 'match': ['Bei'],  'box': (112.0, 114.2, 22.9, 25.6), 'merge_into': 'zhujiang'},
    'dongjiang':  {'name': '东江', 'match': ['Dong'], 'box': (113.4, 116.0, 22.8, 25.2), 'merge_into': 'zhujiang'},
    'lancangjiang': {'name': '澜沧江', 'match': ['Lancang'], 'box': (93.6, 101.5, 21.1, 33.2)},
    'nujiang':    {'name': '怒江', 'match': ['Nu'], 'box': (91.8, 99.4, 23.9, 32.0)},
    'yaluzangbujiang': {'name': '雅鲁藏布江', 'match': ['Yarlung', 'Dihang'], 'box': (80.0, 96.4, 28.6, 31.2)},
    'tarim':      {'name': '塔里木河', 'match': ['Tarim'], 'box': (78.4, 88.6, 38.8, 42.1)},
    'weihe':      {'name': '渭河', 'match': ['Wei'], 'box': (103.4, 110.6, 33.7, 35.5)},
    'fenhe':      {'name': '汾河', 'match': ['Fen'], 'box': (110.2, 113.1, 35.1, 39.3)},
    'yuanjiang':  {'name': '元江（红河）', 'match': ['Hong'], 'box': (99.7, 104.0, 22.2, 25.7)},
    'yalujiang':  {'name': '鸭绿江', 'match': ['Yalu'], 'box': (124.1, 128.6, 39.8, 42.2)},
    'tumenjiang': {'name': '图们江', 'match': ['Tumen'], 'box': (127.9, 131.0, 41.7, 43.3)},
    'wusulijiang': {'name': '乌苏里江', 'match': ['Ussuri'], 'box': (132.9, 135.4, 43.3, 48.7)},
    'sangganhe':  {'name': '桑干河（永定河上游）', 'match': ['Sanggan'], 'box': (112.0, 116.0, 39.0, 40.6), 'minpts': 50},
    # 以下三条 Natural Earth 中本就有真实河道（嘉陵江 434 点、乌江 380 点、岷江下游段 61 点）。
    # 早期误判为"整条缺失"而以手工 5 点折线替代，现改回真实河道。岷江上游段（松潘—乐山）
    # NE 未覆盖，仍由下方 MANUAL_DEG 补充，两者端点重合，stitch() 会自动拼接为单段。
    'jialingjiang': {'name': '嘉陵江', 'match': ['Jialing'], 'box': (105.0, 107.5, 29.0, 34.5)},
    'wujiang':    {'name': '乌江',   'match': ['Wu'],  'box': (104.0, 109.0, 26.0, 30.0)},
    'minjiangsc': {'name': '岷江',   'match': ['Min'], 'box': (103.0, 105.2, 28.5, 33.0)},
    # 瓯江、钱塘江：NE 中分别以 Ou（温州段 65 点）、Fuchun（富春江段 82 点）存在真实河道，
    # 原先误判为"整条缺失"而以手工线替代，现改回真实河道，另以人工短段补齐入海口。
    'oujiang':      {'name': '瓯江',   'match': ['Ou'],     'box': (118.5, 121.2, 27.5, 28.8)},
    'qiantangjiang': {'name': '钱塘江', 'match': ['Fuchun'], 'box': (117.5, 120.9, 29.2, 30.4)},
}

raw = {}
# 优先读裁剪版（fetch_rivers.py 产出，仅保留中国包围盒内相交的要素，
# 6.97 MB → 1.19 MB，几何与原始文件完全一致）；未裁剪时回退读原始文件。
_RIVER_FILES = ['ne_rivers_cn.geojson', 'ne_rivers.geojson']
_river_path = next((os.path.join(DATA, f) for f in _RIVER_FILES
                    if os.path.exists(os.path.join(DATA, f))), None)
if _river_path:
    ne = load(_river_path)
    print('河流数据源: %s (%d 要素)' % (os.path.basename(_river_path), len(ne['features'])))
    for rid, spec in RIVER_SPEC.items():
        # merge_into：该名称的河道并入目标河流，作为其独立线段（如珠江的西江/北江/东江）
        tgt = spec.get('merge_into', rid)
        segs = []
        for f in ne['features']:
            nm = (f['properties'].get('name') or '')
            if nm not in spec['match']:
                continue
            geom = f['geometry']
            if not geom:
                continue
            lines = [geom['coordinates']] if geom['type'] == 'LineString' else geom['coordinates']
            for ln in lines:
                if len(ln) < (spec.get('minpts') or 0):
                    continue
                x0, x1, y0, y1 = spec['box']
                part = [(x, y) for x, y in ln if x0 <= x <= x1 and y0 <= y <= y1]
                if len(part) < 8:
                    continue
                segs.append(part)
        if not segs:
            # 硬失败：避免某个声明在 NE 中匹配不到要素却静默产出空河道
            raise SystemExit('RIVER_SPEC 未匹配到河道: %s (%s) match=%s'
                             % (rid, spec['name'], spec['match']))
        raw.setdefault(tgt, []).extend(segs)

# ---- 人工补充河段（逐条复核后，确认 Natural Earth 确实未覆盖的区间；单位：度）----
MANUAL_DEG = {
    # 淮河下游：NE 的 Huai 止于 116.52°E（洪泽湖以上），此下无数据
    'huaihe': [[[116.50, 32.60], [117.40, 32.95], [118.15, 33.10], [118.62, 33.30], [119.18, 33.50], [119.76, 33.77]]],
    # 长江河口段：NE 的长江止于约 119.6°E
    'changjiang': [[[119.61, 32.24], [119.96, 32.18], [120.48, 31.94], [121.05, 32.01], [121.85, 31.60]]],
    # 珠江干流武宣—梧州段：NE 的 Hongshui 止于 109.53°E、Xi 起于 111.30°E，中间区间极稀疏
    'zhujiang': [[[109.53, 23.80], [109.70, 23.62], [109.90, 23.50], [110.09, 23.40], [110.45, 23.55],
                  [110.90, 23.42], [111.30, 23.48], [111.52, 23.38], [111.85, 23.15], [112.20, 23.02],
                  [112.47, 23.05], [112.75, 23.10], [112.90, 23.17], [113.10, 23.12], [113.26, 23.11],
                  [113.45, 22.95], [113.60, 22.81]]],
    # 岷江松潘—乐山段：NE 的 Min 仅覆盖乐山以下；本段末端与 NE 段起点重合，stitch() 会自动拼接
    'minjiangsc': [[[103.60, 32.65], [103.52, 31.80], [103.62, 31.00], [103.77, 29.55]]],
    # 瓯江温州—瓯江口：NE 的 Ou 止于约 120.57°E
    'oujiang': [[[120.57, 28.10], [120.75, 27.98], [120.90, 27.95]]],
    # 钱塘江杭州—河口：NE 的 Fuchun 止于约 120.16°E
    'qiantangjiang': [[[120.16, 30.20], [120.42, 30.28], [120.90, 30.40]]],
    # 汉江白河—郧阳—丹江口段：NE 的 Han 主河道在此断开 1.5°（实测删除后汉江会裂为两段）
    'hanshui': [[[109.74, 32.94], [110.30, 32.85], [110.85, 32.70], [111.48, 32.57]]],
    # 鸭绿江丹东—宽甸段：NE 的 Yalu 主体与 124.96°E 以东的独立碎段之间缺口（实测删除后裂为两段）
    'yalujiang_gap': [[[124.37, 40.10], [124.72, 40.30], [124.96, 40.45]]],
}
# 别名：手工段的键名与目标河流 id 不同者在此映射
ALIAS = {'hanshui': 'hanjiang', 'yalujiang_gap': 'yalujiang'}
for _rid, _groups in MANUAL_DEG.items():
    _tgt = ALIAS.get(_rid, _rid)
    if _tgt not in RIVER_SPEC:
        raise SystemExit('MANUAL_DEG 的目标河流未在 RIVER_SPEC 中声明: %s -> %s' % (_rid, _tgt))
    raw.setdefault(_tgt, [])
    for _g in _groups:
        raw[_tgt].append(_g)


def _dist(a, b):
    dx = (a[0] - b[0]) * 0.87
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def stitch(segs, max_bridge=0.45):
    """把同一河流的碎段按端点就近首尾相接，跨距不超过 max_bridge 的直接以直线补齐。

    两遍算法：
      第一遍——按段长降序，每段尝试挂到已有的链上（比对链首/链尾与段的两个端点，
              取最近的一对，方向按需反转），挂不上就新开一条链；
      第二遍——反复合并端点足够近的两条链，直到没有可合并的对为止。

    注意 max_bridge 只管**端点对端点**。若某链的端点恰好落在另一条链的中间部位，
    这里不会把它们接起来（北江、郁江即属此情形，在图上仍表现为独立线段）。
    """
    chains = []
    for s in sorted(segs, key=len, reverse=True):
        best = None
        for ci, ch in enumerate(chains):
            for endname, p in (('tail', ch[-1]), ('head', ch[0])):
                for rev in (False, True):
                    q = s[-1] if rev else s[0]
                    d = _dist(p, q)
                    if d <= max_bridge and (best is None or d < best[0]):
                        best = (d, ci, endname, rev)
        if best is None:
            chains.append(list(s))
            continue
        _d0, ci, endname, rev = best
        if endname == 'tail':
            # 接在链尾：段的起点必须是被匹配的那个端点
            seg = list(reversed(s)) if rev else list(s)
            chains[ci].extend(seg)
        else:
            # 接在链首：段的**末点**必须是被匹配的那个端点，故取向与链尾情形相反
            seg = list(s) if rev else list(reversed(s))
            chains[ci][0:0] = seg
    # 第二遍：合并端点足够近的两条链
    changed = True
    while changed and len(chains) > 1:
        changed = False
        for i in range(len(chains)):
            for j in range(len(chains)):
                if i == j:
                    continue
                a, b = chains[i], chains[j]
                cands = sorted([(_dist(a[-1], b[0]), 'ab'), (_dist(a[-1], b[-1]), 'abr'),
                                (_dist(a[0], b[-1]), 'ba'), (_dist(a[0], b[0]), 'bar')])
                d, mode = cands[0]
                if d <= max_bridge:
                    if mode == 'ab':
                        na = a + b
                    elif mode == 'abr':
                        na = a + list(reversed(b))
                    elif mode == 'ba':
                        na = b + a
                    else:
                        na = list(reversed(b)) + a
                    chains[i] = na
                    chains.pop(j)
                    changed = True
                    break
            if changed:
                break
    return chains


print('--- 河流拼接诊断（chain=拼接后连续段数, gap=剩余最大跨距°, len=总点数）---')
rivers = []
# 顺序固定为「RIVER_SPEC 声明序（不含并入项）+ 其余键排序」，保证同一输入产出字节一致的 geo.json
_spec_keys = [k for k in RIVER_SPEC if 'merge_into' not in RIVER_SPEC[k]]
order = _spec_keys + sorted(k for k in raw if k not in _spec_keys)
for rid in order:
    segs = raw.get(rid)
    if not segs:
        continue
    chs = stitch(segs)
    chs.sort(key=len, reverse=True)
    gaps = []
    for i in range(1, len(chs)):
        a, b = chs[0], chs[i]
        gaps.append(min(_dist(a[-1], b[0]), _dist(a[-1], b[-1]), _dist(a[0], b[-1]), _dist(a[0], b[0])))
    nm = RIVER_SPEC.get(rid, {}).get('name')
    if nm is None:
        nm = {'haihe': '海河'}.get(rid, rid)
    print('  %-8s chain=%d gap=%.2f len=%d' % (nm, len(chs), max(gaps) if gaps else 0.0, sum(len(c) for c in chs)))
    if len(chs) > 1:
        for k, c in enumerate(chs):
            xs = [p[0] for p in c]; ys = [p[1] for p in c]
            print('       #%d bbox %.2f-%.2f, %.2f-%.2f  head=(%.2f,%.2f) tail=(%.2f,%.2f)'
                  % (k, min(xs), max(xs), min(ys), max(ys), c[0][0], c[0][1], c[-1][0], c[-1][1]))
    enc = []
    for c in chs:
        pts = dp([(float(a), float(b)) for a, b in c], 0.03)
        flat = []
        for x, y in pts:
            flat.append(int(round(x * SCALE))); flat.append(int(round(y * SCALE)))
        if len(flat) >= 4:
            enc.append(flat)
    rivers.append({'id': rid, 'name': nm, 'seg': enc})
print('rivers', len(rivers), 'total segs', sum(len(r['seg']) for r in rivers))

out = {'provinces': provinces, 'cities': city_index, 'rivers': rivers, 'jd': jd}
p = os.path.join(OUT, 'geo.json')
with open(p, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
print('geo.json bytes', os.path.getsize(p))
