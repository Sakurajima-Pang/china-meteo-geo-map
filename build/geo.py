# -*- coding: utf-8 -*-
"""几何处理：简化、量化、压缩编码。输出 build/out/geo.json

阶段二。职责边界：只处理**几何**，不含任何区划归属或注记内容（那属 content.py）。

主要步骤：
1. Douglas-Peucker 简化（dp）——省级 0.008°、市级 0.018°、九段线 0.03°、河流 0.03°；
2. 面积过滤（ring_area）——剔除过小的碎片环，三沙市 460300 例外（保留全部南海岛屿）；
3. 整数化——坐标 ×SCALE(1000) 取整并去重，把浮点压成整数以减小体积；
4. 河段拼接（stitch）——把 Natural Earth 拆散的碎段按端点就近接成连续河道。

两处容易踩坑的地方：
- `stitch()` 的 max_bridge=0.45° 只连接链的**端点**，不处理「某链端点接在另一链
  中部」的情形。北江、郁江即因此独立成段（视觉上仍在汇合点相接）。
- 河流输出顺序被固定为「RIVER_SPEC 声明序 + 其余键排序」，以保证同一输入产出
  字节一致的 geo.json（便于 build.py 做指纹比对）。

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

SCALE = 1000.0   # 坐标放大倍数（整数编码）


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


def prep_ring(ring, tol, min_area):
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return None
    if ring_area(pts) < min_area:
        return None
    pts = dp(pts, tol)
    if len(pts) < 3:
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
        jd = prep_geometry(f['geometry'], 0.03, 0.0)
        continue
    if p.get('level') != 'province':
        continue
    provinces.append({
        'ad': str(p['adcode']),
        'name': p['name'],
        'abbr': p.get('adchar') or '',
        'c': [round(p['center'][0], 3), round(p['center'][1], 3)],
        'g': prep_geometry(f['geometry'], 0.008, 0.00015),
    })

print('provinces', len(provinces))
print('JD lines', len(jd))

# ---------- 市级 ----------
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
        ma = 0.0 if ad == '460300' else 0.0003
        items.append({
            'ad': ad,
            'name': p['name'],
            'c': [round(p['center'][0], 3), round(p['center'][1], 3)],
            'g': prep_geometry(f['geometry'], 0.018, ma),
        })
    city_index[pr['ad']] = items

tot = sum(len(v) for v in city_index.values())
print('cities', tot)

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
