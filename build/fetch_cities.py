# -*- coding: utf-8 -*-
"""抓取各省级下辖的市级 / 区级行政区划 → data/{adcode}_full.json

对每个省级 adcode 请求一份 `{adcode}_full.json`，共 33 份（台湾省 710000 除外 ——
DataV 接口对该省返回 404，本项目的做法是改以点位标注其下辖县市，见 content.py
的 EXTRA_CITIES）。

容错策略：两个 URL 模板交替重试，最多 6 次，退避间隔逐步拉长；
已存在且大于 1000 字节的文件直接复用（`cached`），不重复下载。
坐标系：GCJ-02。
"""
import json, urllib.request, os, time, ssl

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
os.makedirs(OUT, exist_ok=True)

ctx = ssl.create_default_context()
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Referer': 'https://datav.aliyun.com/'}

TMPL = [
    'https://geo.datav.aliyun.com/areas_v3/bound/%s_full.json',
    'https://geo.datav.aliyun.com/areas_v3/bound/geojson?code=%s_full',
]

def fetch(ad, tries=6):
    dst = os.path.join(OUT, '%s_full.json' % ad)
    if os.path.exists(dst) and os.path.getsize(dst) > 1000:
        return 'cached', os.path.getsize(dst)
    last = None
    for i in range(tries):
        url = TMPL[i % len(TMPL)] % ad
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
                data = r.read()
            if len(data) < 100:
                raise ValueError('too small %d' % len(data))
            open(dst, 'wb').write(data)
            return 'ok', len(data)
        except Exception as e:
            last = e
            time.sleep(1.2 + i * 0.8)
    return 'FAIL', repr(last)

gj = json.load(open(os.path.join(OUT, '100000_full.json'), encoding='utf-8'))
adcodes = [f['properties']['adcode'] for f in gj['features']
           if f['properties'].get('level') == 'province']

total = 0
for ad in adcodes:
    st, info = fetch(ad)
    print(ad, st, info, flush=True)
    if st != 'FAIL':
        total += os.path.getsize(os.path.join(OUT, '%s_full.json' % ad))
print('total city json bytes:', total)
