# -*- coding: utf-8 -*-
"""把几何数据与内容数据合并，注入 HTML 模板，产出单文件页面。

这是构建链的最后一环，也是「单文件、离线自包含」这一目标的实现点：
把 out/geo.json + out/data.json 压成一份紧凑 JSON，替换 template.html 中的
`/*__DATA__*/` 占位符，写出成品到项目根目录。

两点必须留意：
1. 字段名在此处被**缩写**（p / ci / jd / rv / mt / lk / rg / pr / feat / info /
   ec / isles），前端 JS 依赖这些名字，改名要同步改 template.html。
2. 序列化时把 `</` 转义为 `<\\/`，避免数据中出现 `</script>` 序列而提前闭合脚本块。
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
ROOT = os.path.abspath(os.path.join(HERE, '..'))
TARGET = os.path.join(ROOT, '中国气象地理区划交互地图.html')

geo = json.load(open(os.path.join(OUT, 'geo.json'), encoding='utf-8'))
ctx = json.load(open(os.path.join(OUT, 'data.json'), encoding='utf-8'))

DATA = {
    'p': [{'a': p['ad'], 'n': p['name'], 'c': p['c'], 'g': p['g']} for p in geo['provinces']],
    'ci': {ad: [{'a': c['ad'], 'n': c['name'], 'c': c['c'], 'g': c['g']} for c in lst]
           for ad, lst in geo['cities'].items()},
    'jd': [ring for poly in geo['jd'] for ring in poly],
    'rv': ctx['rivers'],
    'mt': ctx['mt'],
    'lk': ctx['lk'],
    'rg': ctx['regions'],
    'pr': ctx['provRegions'],
    'feat': ctx['feat'],
    'info': ctx['info'],
    'ec': ctx['extraCities'],
    'isles': ctx['isles'],
}

blob = json.dumps(DATA, ensure_ascii=False, separators=(',', ':'))
blob = blob.replace('</', '<\\/')

tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
# 占位符必须**恰好出现一次**：str.replace 会替换全部出现处。若模板的注释里也写了
# 这个标记，数据会被重复注入，HTML 体积翻倍且体积校验不会报错（数据字段仍全等）。
_ph = '/*__DATA__*/'
if tpl.count(_ph) != 1:
    raise SystemExit('模板中数据占位符 %s 出现 %d 次，应恰好为 1 次' % (_ph, tpl.count(_ph)))
html = tpl.replace(_ph, blob)

with open(TARGET, 'w', encoding='utf-8', newline='\n') as f:
    f.write(html)

print('target:', TARGET)
print('html bytes:', os.path.getsize(TARGET))
print('data bytes:', len(blob.encode('utf-8')))
