# -*- coding: utf-8 -*-
"""交叉核查（二）：① 山脉中心点是否落在其自身示意多边形内 ② 各省列出的要素是否与该省范围相交
   ③ 区划文字描述与实际聚合范围的一致性（用真实坐标）

只读，不修改任何产物。这是 content.py 三道构建门禁的**独立复算**——
门禁在构建时拦截问题，本脚本则可在任何时候对已有产物重新验证同一批性质。
"""
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
geo = json.load(open(os.path.join(OUT, 'geo.json'), encoding='utf-8'))
ctx = json.load(open(os.path.join(OUT, 'data.json'), encoding='utf-8'))

def bbox_of_polys(g):
    xs = [c / 1000 for poly in g for r in poly for c in r[0::2]]
    ys = [c / 1000 for poly in g for r in poly for c in r[1::2]]
    return (min(xs), min(ys), max(xs), max(ys))

def point_in_poly(pt, flat):
    x, y = pt
    pts = [(flat[i * 2] / 1000, flat[i * 2 + 1] / 1000) for i in range(len(flat) // 2)]
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside

print('=' * 74)
print('【G】山脉「中心注记」是否落在其「示意范围多边形」内')
print('=' * 74)
bad = []
for k, v in ctx['mt'].items():
    ok = point_in_poly((v[1], v[2]), v[3])
    if not ok:
        bad.append('%s 中心(%.2f,%.2f) 不在自身范围内' % (v[0], v[1], v[2]))
print('不一致条目 %d / %d:' % (len(bad), len(ctx['mt'])))
for b in bad:
    print('  -', b)

print()
print('=' * 74)
print('【H】各省列出的山脉 / 湖泊 / 河流 是否与该省范围相交')
print('=' * 74)
pb = {p['ad']: bbox_of_polys(p['g']) for p in geo['provinces']}
pm = {p['ad']: p['name'] for p in geo['provinces']}
def inter(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])
prob = []
for ad, f in ctx['feat'].items():
    bb = pb[ad]
    for m in f['m']:
        mb = bbox_of_polys([ctx['mt'][m][3:4]]) if False else None
        fl = ctx['mt'][m][3]
        xs = [fl[i] / 1000 for i in range(0, len(fl), 2)]
        ys = [fl[i] / 1000 for i in range(1, len(fl), 2)]
        if not inter(bb, (min(xs), min(ys), max(xs), max(ys))):
            prob.append('%s %s 列出山脉「%s」但范围完全不相交' % (ad, pm[ad], ctx['mt'][m][0]))
    for w in f['w']:
        kind, i = w.split(':', 1)
        if kind == 'l':
            lk = ctx['lk'][i]
            if not (bb[0] <= lk[1] <= bb[2] and bb[1] <= lk[2] <= bb[3]):
                prob.append('%s %s 列出湖泊「%s」但点位在省界包围盒外' % (ad, pm[ad], lk[0]))
        else:
            xs = [c / 1000 for s in ctx['rivers'][i]['s'] for c in s[0::2]]
            ys = [c / 1000 for s in ctx['rivers'][i]['s'] for c in s[1::2]]
            if not inter(bb, (min(xs), min(ys), max(xs), max(ys))):
                prob.append('%s %s 列出河流「%s」但河道完全不相交' % (ad, pm[ad], ctx['rivers'][i]['n']))
print('可疑归属 %d 项:' % len(prob))
for p in prob:
    print('  -', p)

print()
print('=' * 74)
print('【I】区划文字描述 vs 实际聚合范围（关键地级市真实中心坐标）')
print('=' * 74)
CIDX = {}
for ad, lst in geo['cities'].items():
    for c in lst:
        CIDX[c['name']] = (c['c'][0], c['c'][1], ad)
def show(names, note):
    print('  %s' % note)
    for n in names:
        if n in CIDX:
            x, y, ad = CIDX[n]
            print('      %-8s %6.2fE %5.2fN  (省 %s)' % (n, x, y, ad))
        else:
            print('      %-8s 未在市级数据中找到' % n)

show(['济南市', '青岛市', '淄博市', '潍坊市', '泰安市', '日照市', '临沂市', '菏泽市', '烟台市', '威海市', '东营市', '滨州市', '德州市', '聊城市'],
     '山东：实际归属见【J】（华北 11 市 / 黄淮 5 市，南北分界约 36°N）')
print('     黄河在山东自西南(菏泽东明~35.3N)流向东北(东营入海~37.8N)；'
      '济南城区36.65N 位于黄河(该经度约36.75N)南岸')
show(['南平市', '宁德市', '三明市', '福州市', '龙岩市', '莆田市'],
     '福建：江南=南平/宁德/三明；华南=福州/厦门/莆田/泉州/漳州/龙岩（按纬度自北向南，无重叠矛盾）')
show(['蚌埠市', '淮南市', '淮北市', '阜阳市', '合肥市', '安庆市'],
     '安徽：黄淮=淮北/亳州/宿州/阜阳/蚌埠；江淮=淮南/合肥/六安/滁州/安庆')
show(['信阳市', '南阳市', '郑州市', '三门峡市'],
     '河南：华北=豫北6市；黄淮=郑州/开封/洛阳等10市；江淮=信阳；江汉=南阳')
show(['襄阳市', '随州市', '孝感市', '武汉市', '十堰市'],
     '湖北：江淮=孝感/黄冈/随州；江南=黄石/咸宁/鄂州；江汉=武汉/襄阳等11市')

print()
print('=' * 74)
print('【J】省内地级市归属汇总（用于人工复核口径）')
print('=' * 74)
for r in ctx['regions']:
    for m in r['mem']:
        if not m.get('all'):
            names = [geo['cities'][m['p']][i]['name'] for i in m['ci']]
            print('  %s / %s(%s): %s' % (r['n'], m['p'], pm[m['p']], '、'.join(names)))
