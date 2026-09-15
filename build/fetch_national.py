# -*- coding: utf-8 -*-
"""抓取全国省级行政区划（DataV.GeoAtlas）→ data/100000_full.json

产出该文件包含 34 个省级行政区的面状界线，以及一个 adcode 为 100000_JD 的
「九段线」要素（geo.py 会把它单独取出，绘制在南海诸岛附图中）。

坐标系：GCJ-02。已存在则跳过下载（不覆盖），下载后可打印要素清单供人工核对。
"""
import json, urllib.request, os, sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
os.makedirs(OUT, exist_ok=True)

URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json'
dst = os.path.join(OUT, '100000_full.json')

if not os.path.exists(dst):
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open(dst, 'wb') as f:
        f.write(data)
    print('downloaded', len(data), 'bytes')
else:
    print('cached')

gj = json.load(open(dst, encoding='utf-8'))
print('type', gj.get('type'), 'features', len(gj['features']))
for ft in gj['features']:
    p = ft['properties']
    print(p.get('adcode'), '|', p.get('name'), '| level=', p.get('level'),
          '| center=', p.get('center'), '| childrenNum=', p.get('childrenNum'),
          '| geom=', ft['geometry']['type'] if ft.get('geometry') else None)
