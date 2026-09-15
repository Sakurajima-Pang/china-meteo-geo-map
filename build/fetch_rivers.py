# -*- coding: utf-8 -*-
"""抓取 Natural Earth 河道中心线 → data/ne_rivers.geojson

数据集为 `ne_10m_rivers_lake_centerlines`（1:1000 万比例尺），约 1455 个要素、
7.0 MB。**注意：本项目只用到其中极小一部分** —— geo.py 的 RIVER_SPEC 通过
「英文河名 + 包围盒」挑出中国境内的 29 条河流。该文件尚未裁剪（低优先级，非错误）。

两个下载源：GitHub raw 与 jsDelivr CDN，前者失败则回退到后者。
坐标系：**WGS-84**（与行政区划的 GCJ-02 不同，详见 README「坐标系约定」）。

下载后打印中国境内（含边境）河流的英文名频次表，用于人工核对 RIVER_SPEC
中的 match 名单是否与实际数据吻合。
"""
import json, urllib.request, os, ssl, time

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
os.makedirs(OUT, exist_ok=True)
dst = os.path.join(OUT, 'ne_rivers.geojson')

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
        coords = g['coordinates']
        def flat(cs):
            if not cs:
                return
            if isinstance(cs[0], (int, float)):
                yield cs
            else:
                for x in cs:
                    yield from flat(x)
        pts = list(flat(coords))
        inCN = sum(1 for x, y in pts if 73 <= x <= 136 and 17 <= y <= 54)
        if inCN < len(pts) * 0.5 or inCN == 0:
            continue
        nm = f['properties'].get('name') or f['properties'].get('name_en')
        c[nm] += 1
        inside.append((nm, f['properties'].get('name_en'), inCN, len(pts)))
    print('CN river features:', len(inside))
    for nm, cnt in c.most_common(60):
        print(cnt, nm)
