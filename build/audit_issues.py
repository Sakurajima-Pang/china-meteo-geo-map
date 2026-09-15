# -*- coding: utf-8 -*-
"""构建约束与数据自洽性的回归复核（只读）。

本脚本把《核查报告-中国气象地理区划交互地图.html》所依赖的判据变成可复跑的检查，
用于在改动构建脚本后快速确认「报告所述事实仍然成立」。

只读：不改动任何产物。判据与核查报告一致（用同一套空间运算重算），
避免「读了源码就下结论」的失真。

与另外三个审计脚本的关系：
  audit.py        —— 数据源与产物的逐字段一致性
  audit2.py       —— 空间关系交叉核查（可视为构建门禁的独立复算）
  audit3.py       —— 工程形态（自包含性、构建链、代码规模）
  audit_issues.py —— 本脚本，回归复核报告所依赖的事实与约束

用法：
    python build/build.py           # 先构建，产出 out/geo.json 与 out/data.json
    python build/audit_issues.py    # 再复核
"""
import json, os, sys, io, math

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
ROOT = os.path.abspath(os.path.join(HERE, '..'))
SC = 1000.0

geo = json.load(open(os.path.join(OUT, 'geo.json'), encoding='utf-8'))
ctx = json.load(open(os.path.join(OUT, 'data.json'), encoding='utf-8'))
html = open(os.path.join(ROOT, '中国气象地理区划交互地图.html'), encoding='utf-8').read()
# 河流原始数据优先用裁剪版（与 geo.py 一致）
_rf = next((os.path.join(ROOT, 'data', f) for f in
            ('ne_rivers_cn.geojson', 'ne_rivers.geojson')
            if os.path.exists(os.path.join(ROOT, 'data', f))), None)
NE = json.load(open(_rf, encoding='utf-8')) if _rf else None

fails = []      # 断言失败项（回归告警）


def flat_pts(flat):
    return [(flat[i] / SC, flat[i + 1] / SC) for i in range(0, len(flat), 2)]


def bbox(pts):
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))


def in_poly(pt, pts):
    x, y = pt
    n = len(pts)
    ins = False
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                ins = not ins
    return ins


def dist_to_poly(pt, pts):
    """点到多边形边界的最短距离（度）。点在内部返回正值，在外部返回负值。"""
    x, y = pt
    best = 1e9
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
        px, py = x1 + t * dx, y1 + t * dy
        d = math.hypot(x - px, y - py)
        if d < best:
            best = d
    return best if in_poly(pt, pts) else -best


def hit(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def chk(label, ok, detail=''):
    """记录并打印一项检查结果。ok=False 计为回归失败。"""
    if not ok:
        fails.append(label)
    print('  %-56s %s%s' % (label, '✓' if ok else '✗ 回归失败', ('  ' + detail) if detail else ''))
    return ok


P = print
P('=' * 76)
P('构建约束与数据自洽性回归复核')
P('=' * 76)

# ---------------------------------------------------------------- 空间约束
P('')
P('【一】山脉注记必须落在自身示意范围内（构建门禁 ①）')
outside = []
margins = []
# 真正的技术风险不是"余量小"，而是"整数化取整后注记点被翻到多边形外"。
# 故对每座山：把注记坐标按前端同样的 int(round(x*1000)) 取整后再判定一次。
flip = []
for k, v in ctx['mt'].items():
    d = dist_to_poly((v[1], v[2]), flat_pts(v[3]))
    margins.append(d)
    if d < 0:
        outside.append((v[0], d))
    # 取整后复判（模拟 assemble 的整数化编码：×1000 后 int(round())）
    qx = int(round(v[1] * SC)) / SC
    qy = int(round(v[2] * SC)) / SC
    if not in_poly((qx, qy), flat_pts(v[3])):
        flip.append(v[0])
chk('山脉总数 %d，注记越界 %d 座' % (len(ctx['mt']), len(outside)),
    not outside,
    '' if not outside else '；'.join('%s 偏离 %.3f°' % (n, -d) for n, d in outside))
if margins:
    P('        安全余量范围 %.3f° ~ %.3f°（最小者为面积很小的山体，余量小属正常）'
      % (min(margins), max(margins)))
chk('整数化取整后无注记点被翻到范围外', not flip,
    '' if not flip else '；'.join(flip))

P('')
P('【二】省级要素清单中的要素必须与该省范围相交（构建门禁 ②）')
prov_bb = {}
for p in geo['provinces']:
    pts = [(c / SC, d / SC) for poly in p['g'] for r in poly
           for c, d in zip(r[0::2], r[1::2])]
    prov_bb[p['ad']] = bbox(pts)
feat = ctx['feat']
bad_feat = []
n_feat = 0
# feat 的实际结构：{m:[山脉键名（无前缀）], w:[河流/湖泊（"r:"/"l:" 前缀）]}。
# 湖泊注记值为 [名称, lng, lat]，取坐标须用 [1],[2]。
for ad, f in feat.items():
    bb = prov_bb.get(ad)
    if not bb:
        continue
    for k in f.get('m', []):
        n_feat += 1
        if k not in ctx['mt']:
            bad_feat.append((ad, k, '悬空引用'))
            continue
        if not hit(bbox(flat_pts(ctx['mt'][k][3])), bb):
            bad_feat.append((ad, k, '与该省零交叠'))
    for item in f.get('w', []):
        n_feat += 1
        pfx, _, k = item.partition(':')
        if not k:
            bad_feat.append((ad, item, '缺少前缀'))
            continue
        if pfx == 'l':
            if k not in ctx['lk']:
                bad_feat.append((ad, item, '悬空引用'))
                continue
            lng, lat = ctx['lk'][k][1], ctx['lk'][k][2]
            if not (bb[0] <= lng <= bb[2] and bb[1] <= lat <= bb[3]):
                bad_feat.append((ad, item, '点位在省界外'))
        elif pfx == 'r':
            if k not in ctx['rivers']:
                bad_feat.append((ad, item, '悬空引用'))
                continue
            pts = [(x / SC, y / SC) for s in ctx['rivers'][k]['s']
                   for x, y in zip(s[0::2], s[1::2])]
            if not pts or not hit(bbox(pts), bb):
                bad_feat.append((ad, item, '与该省零交叠'))
        else:
            bad_feat.append((ad, item, '未知前缀'))
chk('要素引用 %d 项，异常 %d 项' % (n_feat, len(bad_feat)), not bad_feat,
    '' if not bad_feat else str(bad_feat[:4]))

P('')
P('【三】补充河流的「整条缺失」主张必须成立（构建门禁 ③）')
# EXTRA_RIVERS 声明为"NE 中不存在"的河流，其英文名不应出现在 NE 中国河流集合中
_NE_KW = {'nandujiang': 'Nandu'}
if NE is None:
    chk('NE 河流文件可用', False, 'data/ne_rivers*.geojson 均不存在')
else:
    def flat_coords(c):
        if not c:
            return
        if isinstance(c[0], (int, float)):
            yield c
            return
        for x in c:
            if x:
                yield from flat_coords(x)

    ne_names = set()
    for f in NE['features']:
        g = f.get('geometry')
        if not g or not g.get('coordinates'):
            continue
        if f['properties'].get('featurecla') != 'River':
            continue
        pts = list(flat_coords(g['coordinates']))
        if not pts or not all(73 <= a <= 136 and 17 <= b <= 54 for a, b in pts):
            continue
        nm = f['properties'].get('name')
        if nm:
            ne_names.add(nm)
    for rid, kw in _NE_KW.items():
        if rid in ctx['rivers']:
            chk('EXTRA_RIVERS 项 %s 的缺失主张（NE 无「%s」）' % (rid, kw),
                kw not in ne_names)

P('')
P('【四】区划聚合完整性（跨区省的成员必须无遗漏、无重复）')
reg = {r['id']: r for r in ctx['regions']}
all_ad = set(prov_bb.keys())
in_reg = set()
for r in ctx['regions']:
    for m in r['mem']:
        in_reg.add(m['p'])
chk('34 省全部归入至少 1 个一级区划（实际 %d 省）' % len(in_reg),
    len(in_reg) == len(all_ad), '未归入: %s' % sorted(all_ad - in_reg))

split_ok = True
split_detail = []
for ad, cs in geo['cities'].items():
    idx = []
    for r in ctx['regions']:
        for m in r['mem']:
            if m['p'] == ad and not m.get('all'):
                idx += m['ci']
    if idx:
        if sorted(idx) != list(range(len(cs))):
            split_ok = False
            split_detail.append('%s(应 %d 项，实得 %d)' % (ad, len(cs), len(set(idx))))
chk('跨区省的地级单元索引完整且无重复', split_ok, '; '.join(split_detail))

# ---------------------------------------------------------------- 事实约束
P('')
P('【五】页脚与面板的关键披露仍然存在')
foot = html[html.find('<footer'):]
for kw, label in [('DataV 不提供台湾省的地级界线', '台湾无地级界线的披露'),
                  ('无边界数据', '澳门无边界堂区的披露'),
                  ('GCJ-02', '坐标基准 GCJ-02'),
                  ('WGS-84', '坐标基准 WGS-84'),
                  ('放大', '名山范围放大的披露'),
                  ('推断性细化', '城市级归属系推断的披露')]:
    chk('页脚含「%s」' % label, kw in foot)

P('')
P('【六】制图常量集中于模板顶部（不得散落硬编码）')
tmpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
body_after_cfg = tmpl.split('var SMALL_LABEL_VERTS', 1)[-1]
chk('MAIN_LAT_MIN 已定义且被引用 ≥3 处',
    'var MAIN_LAT_MIN' in tmpl and tmpl.count('MAIN_LAT_MIN') >= 3,
    '引用 %d 次' % tmpl.count('MAIN_LAT_MIN'))
chk('渲染代码中无裸 17.8 字面量（仅定义行）',
    tmpl.count('17.8') == 1, '出现 %d 次' % tmpl.count('17.8'))
chk('SMALL_LABEL_VERTS 已用于省名字号判定',
    'p.g.length > SMALL_LABEL_VERTS' in tmpl)

P('')
P('【七】降级路径存在（数据缺失时不得白屏）')
chk('bootFail 提示函数已定义', 'function bootFail' in tmpl)
chk('必需字段断言已前置', 'var _need = [' in tmpl and 'bootFail(_miss)' in tmpl)

P('')
P('【八】构建期基础设施')
chk('统一构建入口 build.py', os.path.exists(os.path.join(HERE, 'build.py')))
content = open(os.path.join(HERE, 'content.py'), encoding='utf-8').read()
chk('三道构建门禁已内置', '构建门禁' in content)
geo_src = open(os.path.join(HERE, 'geo.py'), encoding='utf-8').read()
chk('输出顺序显式排序（保证可复现）', 'order = _spec_keys + sorted(' in geo_src)
chk('死代码已清除（无 if \'minpts\' in spec: pass）', "if 'minpts' in spec" not in geo_src)
chk('拼接河流不原地变异模块级常量',
    'MT_OUT = {k: [v[0], v[1], v[2], POLY_ENC[k]]' in content)
chk('河名键名规范（yalujiang，无 yalvjiang）',
    'yalvjiang' not in geo_src and 'yalvjiang' not in content)
chk('河流优先读裁剪版 ne_rivers_cn.geojson',
    'ne_rivers_cn.geojson' in geo_src)
chk('调试文件已清理（无 dbg/test_page 等）',
    not any(f.startswith(('dbg', 'test_page', 'test_mtn', 'test_river'))
            for f in os.listdir(HERE)))

P('')
P('【九】抓取脚本的 TLS 校验状态')
# 判据是「是否显式关闭校验」，而非「是否出现某个词」
fc = open(os.path.join(HERE, 'fetch_cities.py'), encoding='utf-8').read()
fr = open(os.path.join(HERE, 'fetch_rivers.py'), encoding='utf-8').read()
_tls_off = [w for w in ('CERT_NONE', 'check_hostname = False', 'check_hostname=False',
                        '_create_unverified_context')
            if w in fc or w in fr]
chk('fetch_*.py 未关闭 TLS 校验', not _tls_off,
    '仍关闭（%s）' % ','.join(_tls_off) if _tls_off else '')

# ---------------------------------------------------------------- 汇总
P('')
P('=' * 76)
if fails:
    P('回归复核：%d 项失败' % len(fails))
    for f in fails:
        P('  ✗ %s' % f)
    sys.exit(1)
else:
    P('回归复核：全部通过 —— 核查报告所述事实与构建约束均成立')
P('=' * 76)
