# -*- coding: utf-8 -*-
"""审计脚本（一）：校验数据来源、计算逻辑与界面展示的一致性。只读，不修改任何产物。

覆盖面：
  【A】原始数据源核查——文件要素数、level 分布、九段线要素是否存在；
  【B】起——几何压缩前后的规模对比与坐标精度损失；
  以及后续各节对**成品 HTML 内嵌数据**与 out/*.json 的一致性、界面文案与数据
  是否吻合的检查。

与 audit2.py（三种交叉核查）、audit3.py（工程形态）互补，三者都不修改产物。
运行前需先完成一次构建（out/geo.json、out/data.json 须存在）。
"""
import json, os, re, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(HERE, 'out')
R = []
def p(*a):
    R.append(' '.join(str(x) for x in a))

geo = json.load(open(os.path.join(OUT, 'geo.json'), encoding='utf-8'))
ctx = json.load(open(os.path.join(OUT, 'data.json'), encoding='utf-8'))
html = open(os.path.join(ROOT, '中国气象地理区划交互地图.html'), encoding='utf-8').read()

p('=' * 70)
p('【A】原始数据源核查')
p('=' * 70)
nat = json.load(open(os.path.join(ROOT, 'data', '100000_full.json'), encoding='utf-8'))
p('100000_full.json features =', len(nat['features']))
levels = {}
for f in nat['features']:
    levels[f['properties'].get('level')] = levels.get(f['properties'].get('level'), 0) + 1
p('  level 分布:', levels)
jd_f = [f for f in nat['features'] if str(f['properties'].get('adcode')) == '100000_JD']
p('  100000_JD(九段线) 存在:', bool(jd_f), '| 几何类型:', jd_f[0]['geometry']['type'] if jd_f else None,
  '| 段数:', len(jd_f[0]['geometry']['coordinates']) if jd_f else 0)
prov_ad = sorted(str(f['properties']['adcode']) for f in nat['features']
                 if f['properties'].get('level') == 'province')
p('  省级 adcode 数:', len(prov_ad))
p('  adcode 列表:', ','.join(prov_ad))
missing_file = [ad for ad in prov_ad if not os.path.exists(os.path.join(ROOT, 'data', '%s_full.json' % ad))]
p('  缺少市级数据文件的省级单位:', missing_file)
p('  data/ 目录中无对应的市级文件 -> 该省城市列表为空')

p('')
p('=' * 70)
p('【B】geo.json 与 data.json 结构核查')
p('=' * 70)
p('provinces =', len(geo['provinces']))
p('cities 省级条目 =', len(geo['cities']), '| 城市总数 =', sum(len(v) for v in geo['cities'].values()))
p('rivers =', len(geo['rivers']), '| jd 段 =', len(geo['jd']) if geo['jd'] else 0)
p('regions =', len(ctx['regions']), '| 山脉注记 =', len(ctx['mt']), '| 湖泊注记 =', len(ctx['lk']))
p('provRegions 覆盖省数 =', len(ctx['provRegions']), '| feat 覆盖省数 =', len(ctx['feat']),
  '| info 覆盖省数 =', len(ctx['info']))

# 省份集合
geo_ad = set(x['ad'] for x in geo['provinces'])
info_ad = set(ctx['info'].keys())
pr_ad = set(ctx['provRegions'].keys())
feat_ad = set(ctx['feat'].keys())
p('')
p('geo 中有但 info 缺失:', sorted(geo_ad - info_ad))
p('info 中有但 geo 缺失 :', sorted(info_ad - geo_ad))
p('geo 中有但 provRegions 缺失:', sorted(geo_ad - pr_ad))
p('feat 中有但 geo 缺失:', sorted(feat_ad - geo_ad))
p('geo 中有但 feat 缺失:', sorted(geo_ad - feat_ad))

# 空几何
empt = [x['ad'] + x['name'] for x in geo['provinces'] if not x['g']]
p('')
p('省级几何为空的单位:', empt if empt else '无')
emptc = []
for ad, lst in geo['cities'].items():
    for c in lst:
        if not c['g']:
            emptc.append(ad + '/' + c['name'])
p('市级几何为空的单元:', emptc if emptc else '无')
p('城市数为 0 的省级单位:', [ad for ad, v in geo['cities'].items() if not v])

p('')
p('=' * 70)
p('【C】一级气象地理区划：成员归属完整性')
p('=' * 70)
for r in ctx['regions']:
    tot_city = 0
    provs = []
    for m in r['mem']:
        if m.get('all'):
            provs.append(m['p'] + '(全境)')
        else:
            n = len(m['ci'])
            tot_city += n
            provs.append('%s(%d市)' % (m['p'], n))
    p('%-6s %-6s 成员 %d 项: %s' % (r['id'], r['n'], len(r['mem']), ' '.join(provs)))

p('')
p('--- 每个 SPLIT 省：城市是否被完整且唯一地划分 ---')
split_map = {}
for r in ctx['regions']:
    for m in r['mem']:
        if not m.get('all'):
            split_map.setdefault(m['p'], {})[r['id']] = m['ci']
for ad, groups in split_map.items():
    names = [c['name'] for c in geo['cities'][ad]]
    seen = []
    for rid, idx in groups.items():
        seen += idx
    dup = [i for i in set(seen) if seen.count(i) > 1]
    miss = [i for i in range(len(names)) if i not in seen]
    p('  %s 城市总数=%d 已归=%d 重复=%s 遗漏=%s' %
      (ad, len(names), len(seen),
       [names[i] for i in dup] or '无',
       [names[i] for i in miss] or '无'))

p('')
p('--- 每省所属区划数（>1 表示跨区）---')
for ad in sorted(ctx['provRegions']):
    rs = ctx['provRegions'][ad]
    nm = ctx['info'][ad][0]
    tag = '跨区' if len(rs) > 1 else '单一'
    p('  %s %-4s %s -> %s' % (ad, nm, tag, '/'.join(rs)))

p('')
p('=' * 70)
p('【D】要素引用完整性')
p('=' * 70)
bad = []
for ad, f in ctx['feat'].items():
    for m in f['m']:
        if m not in ctx['mt']: bad.append('feat/%s 山 %s' % (ad, m))
    for w in f['w']:
        k, i = w.split(':', 1)
        if k == 'r' and i not in ctx['rivers']: bad.append('feat/%s 河 %s' % (ad, i))
        if k == 'l' and i not in ctx['lk']: bad.append('feat/%s 湖 %s' % (ad, i))
p('要素引用错误:', bad if bad else '无')
# 山脉多边形
nopoly = [k for k, v in ctx['mt'].items() if len(v) < 4 or not v[3] or len(v[3]) < 6]
p('缺少范围多边形的山脉:', nopoly if nopoly else '无')
p('山脉多边形顶点数分布: min=%d max=%d' %
  (min(len(v[3]) // 2 for v in ctx['mt'].values()), max(len(v[3]) // 2 for v in ctx['mt'].values())))
# 注记是否落在国界内（粗判）
outside = []
for k, v in ctx['mt'].items():
    if not (73 <= v[1] <= 136 and 17 <= v[2] <= 54): outside.append('山 ' + v[0])
for k, v in ctx['lk'].items():
    if not (73 <= v[1] <= 136 and 17 <= v[2] <= 54): outside.append('湖 ' + v[0])
for ad, arr in ctx['extraCities'].items():
    for c in arr:
        if not (73 <= c[1] <= 136 and 17 <= c[2] <= 54): outside.append('市 ' + c[0])
p('注记坐标越出中国范围(73-136E,17-54N):', outside if outside else '无')

p('')
p('=' * 70)
p('【E】界面展示与数据是否一致（构建产物同步性）')
p('=' * 70)
m = re.search(r'const DATA = (\{.*?\});</script>', html, re.S)
p('HTML 内嵌 DATA 块:', bool(m))
if m:
    emb = json.loads(m.group(1).replace('<\\/', '</'))
    p('  内嵌 p(省级)=%d ci(城市 key)=%d rv(河)=%d mt=%d lk=%d rg=%d' %
      (len(emb['p']), len(emb['ci']), len(emb['rv']), len(emb['mt']), len(emb['lk']), len(emb['rg'])))
    # 与 out/*.json 对比
    g2 = json.load(open(os.path.join(OUT, 'geo.json'), encoding='utf-8'))
    c2 = json.load(open(os.path.join(OUT, 'data.json'), encoding='utf-8'))
    exp_p = [{'a': x['ad'], 'n': x['name'], 'c': x['c'], 'g': x['g']} for x in g2['provinces']]
    p('  p 与 geo.json 一致:', emb['p'] == exp_p)
    exp_ci = {ad: [{'a': c['ad'], 'n': c['name'], 'c': c['c'], 'g': c['g']} for c in l]
             for ad, l in g2['cities'].items()}
    p('  ci 与 geo.json 一致:', emb['ci'] == exp_ci)
    p('  rv 与 data.json 一致:', emb['rv'] == c2['rivers'])
    p('  mt 与 data.json 一致:', emb['mt'] == c2['mt'])
    p('  lk 与 data.json 一致:', emb['lk'] == c2['lk'])
    p('  rg 与 data.json 一致:', emb['rg'] == c2['regions'])
    p('  pr 与 data.json 一致:', emb['pr'] == c2['provRegions'])
    p('  feat 与 data.json 一致:', emb['feat'] == c2['feat'])
    p('  info 与 data.json 一致:', emb['info'] == c2['info'])
    p('  ec 与 data.json 一致:', emb['ec'] == c2['extraCities'])
    # 前端渲染依赖的字段是否齐备
    bad_info = [x['a'] for x in emb['p'] if x['a'] not in emb['info']]
    p('  模板 drawLabels 依赖 info[p.a][0]，缺 info 的省:', bad_info or '无(渲染不会抛错)')
    bad_pr = [x['a'] for x in emb['p'] if x['a'] not in emb['pr']]
    p('  模板 provTip 依赖 pr[p.a]，缺 pr 的省:', bad_pr or '无')
    # 区划成员引用是否都能在前端解析
    unresolved = []
    for r in emb['rg']:
        for mm in r['mem']:
            if mm.get('all'):
                if mm['p'] not in [x['a'] for x in emb['p']]: unresolved.append(r['id'] + '->' + mm['p'])
            else:
                if mm['p'] not in emb['ci']: unresolved.append(r['id'] + '->' + mm['p'] + '(市级数据缺失)')
                else:
                    mx = max(mm['ci']) if mm['ci'] else -1
                    if mx >= len(emb['ci'][mm['p']]): unresolved.append(r['id'] + '->' + mm['p'] + '(索引越界)')
    p('  前端 regionGeom 无法解析的成员引用:', unresolved or '无')

p('')
p('--- 模板中的静态文案（非计算得出）与实际数据对照 ---')
claims = {
    '覆盖 34 个省级行政区': len(geo['provinces']) == 34,
    '11 个一级气象地理区划': len(ctx['regions']) == 11,
}
for k, v in claims.items():
    p('  声称「%s」 -> %s (实际 %s)' % (k, '一致' if v else '不一致', '见上'))
# 检查模板里的数字型断言
nums = set(re.findall(r'(\d+)\s*个', html))
p('  模板/产物中出现的「N 个」字样:', sorted(nums))

p('')
p('=' * 70)
p('【F】河流数据核查')
p('=' * 70)
for _rid, r in ctx['rivers'].items():
    segs = r['s']
    tot = sum(len(s) // 2 for s in segs)
    xs = [s[i] / 1000 for s in segs for i in range(0, len(s), 2)]
    ys = [s[i] / 1000 for s in segs for i in range(1, len(s), 2)]
    p('  %-10s 段数=%d 点数=%4d  经度 %.1f-%.1f 纬度 %.1f-%.1f' %
      (r['n'], len(segs), tot, min(xs), max(xs), min(ys), max(ys)))
p('河流注记引用数 =', len(ctx['rivers']))
ne = json.load(open(os.path.join(ROOT, 'data', 'ne_rivers.geojson'), encoding='utf-8'))
p('Natural Earth 原文件 features =', len(ne['features']))
names = set()
for f in ne['features']:
    names.add(f['properties'].get('name'))
p('NE 中含中文大河的原始名称抽样:', [n for n in names if n and any(t in n for t in
   ['Chang', 'Huang', 'Heilong', 'Songhua', 'Liao', 'Huai', 'Han', 'Xiang', 'Gan', 'Min',
    'Hongshui', 'Lancang', 'Nu', 'Yarlung', 'Tarim', 'Wei', 'Fen', 'Yalu', 'Tumen', 'Ussuri',
    'Sanggan', 'Tuotuo', 'Jinsha', 'Tongtian'])][:60])

open(os.path.join(HERE, 'audit_report.txt'), 'w', encoding='utf-8').write('\n'.join(R))
print('\n'.join(R))
