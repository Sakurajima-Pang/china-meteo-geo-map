# -*- coding: utf-8 -*-
"""抓取 Natural Earth 河道中心线 → data/ne_rivers.geojson，并裁剪出中国子集

数据集为 `ne_10m_rivers_lake_centerlines`（1:1000 万比例尺），约 1455 个要素、
7.0 MB。本项目只用到其中中国境内的一小部分 —— geo.py 的 RIVER_SPEC 通过
「英文河名 + 包围盒」挑出 29 条河流。

因此下载后立即裁剪，产出 `data/ne_rivers_cn.geojson`（约 1.19 MB / 238 要素），
geo.py 优先读该文件、回退读未裁剪的原始文件。裁剪采用「要素包围盒与中国包围盒
相交」判据，**只删整条无关要素，不裁剪顶点**，故几何与原始文件逐点一致。

两个下载源：GitHub raw 与 jsDelivr CDN，前者失败则回退到后者。
坐标系：**WGS-84**（与行政区划的 GCJ-02 不同，详见 README「坐标系约定」）。

下载后打印中国境内（含边境）河流的英文名频次表，用于人工核对 RIVER_SPEC
中的 match 名单是否与实际数据吻合。
"""
import json, urllib.request, os, ssl, time

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
os.makedirs(OUT, exist_ok=True)
dst = os.path.join(OUT, 'ne_rivers.geojson')
dst_cn = os.path.join(OUT, 'ne_rivers_cn.geojson')

# 中国包围盒（含近海与边境），比 RIVER_SPEC 各 box 的并集
# （78.40–135.40°E / 21.10–54.00°N）略宽，作为裁剪安全余量。
CN_BB = (73.0, 136.5, 17.0, 54.5)

ctx = ssl.create_default_context()

URLS = [
    'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_rivers_lake_centerlines.geojson',
    'https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/ne_10m_rivers_lake_centerlines.geojson',
]

if not os.path.exists(dst):
    for u in URLS:
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
                data = r.read()
            open(dst, 'wb').write(data)
            print('ok', u, len(data))
            break
        except Exception as e:
            print('fail', u, e)
            time.sleep(1)


def _flat(cs):
    """把 LineString / MultiLineString 的坐标展平为点序列。"""
    if not cs:
        return
    if isinstance(cs[0], (int, float)):
        yield cs
    else:
        for x in cs:
            yield from _flat(x)


def clip_to_cn(src, target, bb=CN_BB):
    """裁剪：只保留包围盒与 bb 相交的要素（不裁顶点，几何逐点不变）。"""
    gj = json.load(open(src, encoding='utf-8'))
    keep = []
    for f in gj['features']:
        g = f.get('geometry')
        if not g:
            continue
        pts = list(_flat(g['coordinates']))
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if max(xs) < bb[0] or min(xs) > bb[1] or max(ys) < bb[2] or min(ys) > bb[3]:
            continue
        keep.append(f)
    out = {'type': 'FeatureCollection', 'features': keep}
    with open(target, 'w', encoding='utf-8', newline='') as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
    return len(gj['features']), len(keep), os.path.getsize(target)


if os.path.exists(dst):
    gj = json.load(open(dst, encoding='utf-8'))
    print('features', len(gj['features']))
    # 中国范围内（含边境）的河流，按名称出现频次排序
    from collections import Counter
    c = Counter()
    inside = []
    for f in gj['features']:
        g = f['geometry']
        if not g:
            continue
        pts = list(_flat(g['coordinates']))
        inCN = sum(1 for x, y in pts if 73 <= x <= 136 and 17 <= y <= 54)
        if inCN < len(pts) * 0.5 or inCN == 0:
            continue
        nm = f['properties'].get('name') or f['properties'].get('name_en')
        c[nm] += 1
        inside.append((nm, f['properties'].get('name_en'), inCN, len(pts)))
    print('CN river features:', len(inside))
    for nm, cnt in c.most_common(60):
        print(cnt, nm)

if os.path.exists(dst):
    n0, n1, sz = clip_to_cn(dst, dst_cn)
    print('裁剪 → %s：%d → %d 要素，%.2f MB'
          % (os.path.basename(dst_cn), n0, n1, sz / 1048576))
