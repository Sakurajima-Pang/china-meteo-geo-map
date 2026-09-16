# -*- coding: utf-8 -*-
"""南海诸岛注记的**单一真源**（声明表）。

职责：声明「哪些几何不是真实海岸线」以及「哪些岛礁该以面状注记呈现、性质为何」。
`geo.py` 与 `content.py` 都从这里读，避免同一份考证在两处各写一遍而漂移。

--------------------------------------------------------------------------
一、为什么需要这张表
--------------------------------------------------------------------------
DataV.GeoAtlas 的行政区划数据中，**东沙群岛被表示为三块按自身中心生成的圆形
range ring**，而不是海岛海岸线。三条独立证据：

1. **是外生数据**：DataV 使用高德底图。高德不自行测绘，其海域要素转引自
   天地图。本图采用的审图号为 GS(2024)0650号 的版本亦沿用了同一批面状表示。
2. **不是实际行政区域**：三块的质心与官方公布的东沙岛、北卫滩、南卫滩坐标
   分别相差 **16.90 / 4.37 / 4.97 km**（见文末自检报告）。作为对照，
   同市**真实**的东沙岛本体几何与官方坐标只差 3.28 km。
3. **不是自然岸线**（实测值见文末自检报告，`python build/isles_data.py` 可复现）：

   下表为**市级几何**（`440000_full.json` / 汕尾市）实测值。同一批 ring 在**省级几何**
   （`100000_full.json` / 广东省）里另存一份，面积略有出入（166.33 / 102.25 / 40.22 km²）
   —— 两者是不同粒度的两次概括，都需摘除，见 `REMOVE_FROM`。

   | 块 | 面积 | 圆形度 4πA/P² | 顶点 |
   |---|---|---|---|
   | 东沙环礁 ring | 172.93 km² | 0.261 | 35 |
   | 北卫滩 ring | 111.30 km² | **0.930** | 16 |
   | 南卫滩 ring | 43.32 km² | **0.820** | 11 |
   | *（对照）东沙岛本体* | *1.67 km²* | *0.616* | *5* |
   | *（对照）汕尾近岸小岛* | *0.56 / 0.35 km²* | *0.540 / 0.536* | *4* |

   · 北卫滩、南卫滩两块的圆形度 0.82~0.93，**比自然岸线更接近正圆** ——
     自然岸线因有岬湾、礁缘起伏，圆度普遍在 0.5 附近，达不到 0.82 以上。
   · 东沙环礁那块的圆度只有 0.261，是因为它的外缘带高频锯齿（range ring
     常见的画法），周长被拉长；面积仍是 172.93 km²。
   · **面积是最干净的判据**：三条 range ring 43~173 km²，而同一海域的
     真实陆地只有 1.67 km²，相差 **25 倍**；北卫滩、南卫滩更是**完全没入水下**
     （−11 m 与 −58 m，另一来源对北卫滩给 −60 m）。

⚠ **不要只凭「质心接近」就断定是人造轮廓** —— 真实东沙岛本体的质心距声明的
东沙坐标仅 3.28 km，同样落在雷达内。这正是需要 `MIN_SYNTH_AREA_KM2` 的原因，
详见该常量的说明。

结论：这三块面积/直径远大于真实露出陆地，是**面状位置与范围的示意表示**。
数据源属性中没有任何「岛/礁/水深」字段（`properties` 仅 10 个键），
所以性质只能靠本表声明 —— 这与项目既有的 `RIVER_SPEC` / `MANUAL_DEG` 范式一致。

--------------------------------------------------------------------------
二、本表做什么
--------------------------------------------------------------------------
① `split_dongshat()`：把这三块从行政区划几何里**摘出来**（省级与市级各存一份几何，
   见 `REMOVE_FROM`，两份都要摘 —— 只摘一份会让另一份继续渲染）。
   不摘的话，图上会多出三块人工圆形色块（等效直径 7.2~14.8 km，在本图比例下
   主图仅 1.1~2.3 px、附图 0.6~1.2 px）——**尺寸不起眼，但性质是错的**：
   把人工 range ring 描成陆地，等于宣称「这就是东沙的形状」。

② 摘出来之后**怎么呈现** —— 这件事做过一次失败的尝试，结论必须留在这里：

   ▸ 试过的方案：按「面状注记」呈现，用 kind 区分 cay（实心）/ bank（虚线）。
     结果不可读。这三块虽然面积写着 43~173 km²，但那是 range ring 的**圆面积**，
     屏幕尺寸按外接框算：附图比例 8.29 viewBox 单位/°，故
         东沙环礁（ring）19.2×21.9 km → 1.4×1.6 px
         北卫滩  （ring）12.9×11.8 km → 1.0×0.9 px
         南卫滩  （ring） 7.7× 8.9 km → 0.6×0.7 px
     最小的一块 0.5 px，虚线样式在 0.6 px 的轮廓上完全不可见（已用
     deviceScaleFactor:4 放大截图确认：肉眼只见一片底色）。
     更根本的问题是：**把 range ring 的轮廓画出来，等于把一个人造图形当成
     真实岛礁海岸线展示** —— 无论怎么设样式，都在暗示「这就是东沙的形状」。

   ▸ 采用的方案：**点状符号 + 性质区分**。这与本图既有的制图惯例一致 ——
     `ISLES` 里的西沙/中沙/南沙/黄岩岛/曾母暗沙同样是「面积不足 1 像素、
     以符号表示」。区别只在样式：
         · cay （有露出陆地）→ 实心圆点，与既有点状符号同族；
         · bank（完全没入水下）→ **空心圆**，一眼可辨「此处无陆地」。
     两者都是「位置示意」，不冒充海岸线，且尺寸由我们决定、不受比例尺挤压。

   因此 `AREAS` 现在只提供**坐标与性质**，不再提供轮廓；三块 range ring 由
   `geo.py` 摘除后即丢弃。

   ⚠ **但真实陆地必须留下**：东沙岛本体（1.67 km²）是**真实几何**，
   不是人造轮廓，`split_dongshat()` 会保留它。它只有 0.35×0.21 px（主图）/
   0.19 px（附图），肉眼不可见 —— 这不是缺陷，是本图比例尺的固有结果，
   已由页脚「岛礁实际面积不足 1 像素，按制图惯例以符号表示」统一披露。
   注：2026-09-16 起主图已整体不渲染东沙（仅附图呈现），但**几何本身仍须保留**
   —— 它是真实的行政区划几何，不该因为不显示就删掉。

--------------------------------------------------------------------------
三、维护须知
--------------------------------------------------------------------------
- `match()` 用**质心就近**匹配，雷达半径 `MATCH_R_KM = 25`。理由是这三块
  range ring 的质心与官方坐标有 4.4~16.9 km 偏差，用「包围盒包含坐标点」会漏配。
- **但仅凭质心匹配是不够的** —— 真实东沙岛本体的质心距声明的东沙坐标只有
  3.28 km，同样落在雷达内，曾因此被误摘。故必须叠加 `MIN_SYNTH_AREA_KM2`
  面积判据（见该常量说明）。两个判据由 `is_synthetic()` 统一封装。
- `remove` 判据限定在 `REMOVE_FROM` 列出的单元内，防止误伤其它单元的几何。
- 摘除结果由 `geo.py` 的**三道门禁**守住（见其注释）：① 产物中不得残留任何人造轮廓；
  ② 每条声明都必须在数据里兑现；③ 声明坐标附近的真实陆地必须恰有 1 环。
  三者互补，缺一不可 —— 各自能拦住的漂移类型不同。
- 若上游数据更新后这三块消失或改变形状，`split_dongshat()` 会返回
  `dropped == 0`，而 `content.py` 的门禁 4 会因「声明为空」而失败 ——
  这是**有意的**：声明与数据脱钩时必须显式暴露，不能静默留下一张空表。
- `AREAS` 里的坐标**不用于绘图定位**（定位用 `ISLES` 的点），只用于
  ① 甄别该摘掉哪几块、② 在提示文字里核对与官方坐标的偏差。
  两者数值不同是正常的：`ISLES['东沙群岛']` 是一个覆盖全群岛的点位。
"""

import math

# ---------- 判据一：质心就近匹配 ----------
# 匹配时使用的雷达半径（km）。取 25 km 是因为：三块 range ring 的质心与官方公布
# 坐标偏差最大约 17 km（东沙环礁那块），而最近的两块之间相隔约 18 km，
# 25 km 既能覆盖偏差又不会互相抢配。
MATCH_R_KM = 25.0

# ---------- 判据二：面积下限（**不可省**） ----------
# 「人造轮廓」的面积下限（km²）。
#
# 为什么必须有这一条：仅凭质心就近匹配会**连带摘除真实陆地**。这是已实际发生的
# 缺陷 —— 东沙岛本体（真实几何，1.73 km²）的质心距本表声明的东沙坐标仅 3.27 km，
# 故它同样落在 25 km 雷达内，曾与三条 range ring 一起被摘除。
#
# 判据依据（实测，见本文件末尾 `if __name__` 的报告）：
#   · 三条 range ring：172.89 / 110.38 / 43.28 km²
#   · 同一海域的真实陆地：东沙岛本体 1.73 km²
#   两者相差 **25 倍**。取 10 km² 落在中间，两侧各留 ≥4 倍余量：
#       最小的人造轮廓 43.28 ÷ 10 = 4.3 倍余量
#       最大的真实陆地 10 ÷ 1.73 = 5.8 倍余量
#
# 换言之，这条判据编码的是「人造轮廓必然远大于该处的真实陆地」——
# 这本来就是我们把它们判为人造的理由。若上游某天真的出现了 ≥10 km² 的真实岛屿，
# 本判据会把它误当成 range ring，故 `split_dongshat` 的摘除数有断言兜底（见 geo.py）。
MIN_SYNTH_AREA_KM2 = 10.0

# 东沙群岛。coordinates 取官方公布值（度）。
# depth_m 为负表示水面以下米数；0 表示有露出水面的陆地。
AREAS = {
    'dongsha_atoll': {
        'name': '东沙岛',
        'parent': '东沙群岛',
        'coordinates': [116.7000, 20.7167],
        'kind': 'cay',
        'depth_m': 0,
        'note': '东沙环礁上唯一常年露出水面的沙岛，面积约 1.7 km²；环礁整体（含潟湖）约 400 km²',
    },
    'north_vereker': {
        'name': '北卫滩',
        'parent': '东沙群岛',
        'coordinates': [115.9667, 21.0667],
        'kind': 'bank',
        'depth_m': -11,
        'note': '沉水环礁，最浅处约 11 m 位于水面以下',
    },
    'south_vereker': {
        'name': '南卫滩',
        'parent': '东沙群岛',
        'coordinates': [115.9167, 20.9667],
        'kind': 'bank',
        'depth_m': -58,
        'note': '沉水环礁，最浅处约 58 m 位于水面以下',
    },
}

# 哪些行政区划单元的几何需要做「摘除人造轮廓」处理。**必须列全**。
#
# ⚠ 这里是本项目踩过的第二个坑：同一批人造 range ring 在**两个层级**各存了一份 ——
#   · `440000`（广东省，**省级**，来自 `data/100000_full.json`）
#   · `441500`（汕尾市，**市级**，来自 `data/440000_full.json`）
# 二者是两份独立的几何，各自都带这三块 ring。只摘市级那一份的话，ring 仍会经
# **省级图层**渲染出来 —— 表现为「摘了却还在图上有印子」。故两个 adcode 都要列。
#
# 注：省级那份**不含**真实东沙岛本体（只有三条 ring），市级那份含
# （广东省的省级几何只到近岸小岛为止）。这是两份数据粒度的正常差异。
REMOVE_FROM = ('440000', '441500')


def _centroid(flat):
    """整数化（×1000）的扁平坐标数组 → 面积加权的多边形质心（度）。"""
    n = len(flat) // 2
    s = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n):
        x1 = flat[2 * i] / 1000.0
        y1 = flat[2 * i + 1] / 1000.0
        x2 = flat[2 * ((i + 1) % n)] / 1000.0
        y2 = flat[2 * ((i + 1) % n) + 1] / 1000.0
        cr = x1 * y2 - x2 * y1
        s += cr
        cx += (x1 + x2) * cr
        cy += (y1 + y2) * cr
    if abs(s) < 1e-12:
        return (sum(flat[0::2]) / n / 1000.0, sum(flat[1::2]) / n / 1000.0)
    return (cx / (3 * s), cy / (3 * s))


def _area_km2(flat):
    """整数化（×1000）的扁平坐标数组 → 多边形面积（km²）。

    经度方向按质心纬度做收缩修正（1° 经度 = 111.32·cosφ km），
    否则在南海上空会把面积算大约 5%。
    """
    n = len(flat) // 2
    s = 0.0
    for i in range(n):
        x1 = flat[2 * i] / 1000.0
        y1 = flat[2 * i + 1] / 1000.0
        x2 = flat[2 * ((i + 1) % n)] / 1000.0
        y2 = flat[2 * ((i + 1) % n) + 1] / 1000.0
        s += x1 * y2 - x2 * y1
    lat0 = (sum(flat[1::2]) / n) / 1000.0
    return abs(s) / 2 * 111.32 * 110.57 * math.cos(math.radians(lat0))


def match(centroid_lng, centroid_lat):
    """给定某 part 的质心，返回命中的声明 id；无命中返回 None。"""
    best = None
    for aid, a in AREAS.items():
        ln, la = a['coordinates']
        dy = (la - centroid_lat) * 111.32
        dx = (ln - centroid_lng) * 111.32 * math.cos(math.radians(la))
        d = math.sqrt(dx * dx + dy * dy)
        if d <= MATCH_R_KM and (best is None or d < best[1]):
            best = (aid, d)
    return best[0] if best else None


def is_synthetic(ring):
    """该环是否应判为「人造轮廓」而摘除。

    **两个判据必须同时成立**，缺一不可：
      ① 质心落在某个声明坐标的 MATCH_R_KM 雷达内（`match` 非 None）；
      ② 面积 ≥ MIN_SYNTH_AREA_KM2。
    只判 ① 会摘掉真实陆地（东沙岛本体曾被误摘，见常量处说明）。
    """
    if match(*_centroid(ring)) is None:
        return False
    return _area_km2(ring) >= MIN_SYNTH_AREA_KM2


def split_dongshat(ad, geom):
    """把 (adcode, 预处理后的几何) 拆成 (保留的几何, 命中并摘除的声明 id 列表)。

    只处理 REMOVE_FROM 中列出的单元，其余原样返回 —— 避免本表的作用范围
    在日后被无声扩大。

    判据见 `is_synthetic()`：质心就近 **且** 面积达标。真实的小块陆地
    （东沙岛本体 1.67 km²、汕尾近岸小岛）面积不达标，故会被保留。

    返回**声明 id 列表**（而非计数）是为了让调用方能断言
    「每条声明都在数据里兑现了」—— 计数无法区分「摘到 3 条声明」与
    「摘到 5 块但只命中 2 条声明」。
    """
    if ad not in REMOVE_FROM or not geom:
        return geom, []
    keep = []
    hit_ids = []
    for poly in geom:
        ids = [match(*_centroid(ring)) for ring in poly if is_synthetic(ring)]
        if ids:
            hit_ids.extend(ids)
        else:
            keep.append(poly)
    return keep, hit_ids


def real_parts_near_rings(geom):
    """保留几何中「落在某声明坐标雷达内、却**不是**人造轮廓」的环。

    这就是「该处的真实陆地」。东沙群岛处应恰有 1 块（东沙岛本体）。

    存在的理由：`prep_geometry` 的面积过滤（`MIN_AREA_CITY`）在
    `split_dongshat` **之前**运行，所以真实东沙岛有可能被面积过滤提前剔除，
    而此时「声明已兑现」的断言仍然成立 —— 那条断言拦不住这种漏失。
    故需要这条**正面**判据：真实陆地必须确实存在于产物中，而不只是「没被本表摘掉」。
    """
    out = []
    for poly in geom or []:
        for ring in poly:
            if match(*_centroid(ring)) is not None and not is_synthetic(ring):
                out.append(ring)
    return out


# ---------------------------------------------------------------------------
# 自检报告：把本表判据作用到原始数据上，逐 part 打印判定结果。
# 用途：本文件各处引用的面积/偏移数字都由此产出，改动判据后跑一次核对。
#   python build/isles_data.py
# 只读，不写任何文件。
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import io
    import json
    import os

    _here = os.path.dirname(os.path.abspath(__file__))

    def _km(p, q):
        dx = (q[0] - p[0]) * 111.32 * math.cos(math.radians((p[1] + q[1]) / 2))
        dy = (q[1] - p[1]) * 110.57
        return math.hypot(dx, dy)

    # 同一批 range ring 在省级与市级各存一份，两份都要看 —— 只查市级的漏过省级那种
    # 情况（ring 仍会经省级图层渲染），这正是本项目踩过的坑。
    _sources = [
        ('省级', '100000_full.json', '440000', '广东省'),
        ('市级', '440000_full.json', '441500', '汕尾市'),
    ]
    print('判据：质心 ≤ %.0f km 且 面积 ≥ %.1f km²   —— 两者必须同时成立'
          % (MATCH_R_KM, MIN_SYNTH_AREA_KM2))
    print('注：本报告读**原始** data/*.json（未经 prep_geometry 简化），故面积与构建期'
          '略有出入。')
    _total = 0
    for _lvl, _fn, _ad, _nm in _sources:
        _path = os.path.join(_here, '..', 'data', _fn)
        if not os.path.exists(_path):
            raise SystemExit('缺少原始数据 %s（未解压 archive/rawdata-*.zip？）' % _path)
        _raw = json.load(io.open(_path, encoding='utf-8'))
        _feat = [f for f in _raw['features'] if str(f['properties']['adcode']) == _ad]
        if not _feat:
            raise SystemExit('%s 中未找到 adcode=%s' % (_fn, _ad))
        _polys = _feat[0]['geometry']['coordinates']
        print()
        print('=== %s %s（%s，来自 %s）共 %d 个 part ===' % (_lvl, _nm, _ad, _fn, len(_polys)))
        print('%-7s %7s %10s %8s %10s  %s'
              % ('part', '顶点', '面积km²', '圆度', '质心偏移', '判定'))
        for _i, _poly in enumerate(_polys):
            _ring = [int(round(v * 1000)) for _p in _poly[0] for v in _p]
            _pts = _poly[0]
            _A = _area_km2(_ring)
            _P = sum(_km(_pts[_k], _pts[(_k + 1) % len(_pts)]) for _k in range(len(_pts)))
            _circ = 4 * math.pi * _A / (_P * _P) if _P else 0.0
            _c = _centroid(_ring)
            _hit = match(*_c)
            _off = ''
            if _hit:
                _ln, _la = AREAS[_hit]['coordinates']
                # _centroid 返回 (lng, lat)；勿把下标写反（曾把偏移算成 14000+ km）
                _off = '%.2f km' % math.hypot(
                    (_ln - _c[0]) * 111.32 * math.cos(math.radians(_la)),
                    (_la - _c[1]) * 111.32)
            _synth = is_synthetic(_ring)
            if _synth:
                _total += 1
            if len(_pts) > 60:
                print('%-7s %7d %10s %8s %10s  %s'
                      % ('part%d' % _i, len(_pts), '—', '—', _off or '—',
                         '【陆域主体】'))
                continue
            print('%-7s %7d %10.2f %8.3f %10s  %s' % (
                'part%d' % _i, len(_pts), _A, _circ, _off or '—',
                ('摘除（人造轮廓 ← %s）' % _hit) if _synth
                else ('保留' + ('（命中 %s 但面积不达标 → 真实陆地）' % _hit
                              if _hit else ''))))
    print()
    print('合计摘除 %d 个（省级 + 市级各 %d 个；应为 %d 个声明 × %d 个层级）'
          % (_total, len(AREAS), len(AREAS), len(_sources)))
