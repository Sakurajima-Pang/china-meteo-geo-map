# -*- coding: utf-8 -*-
"""对 audit_issues.py 中【投影】【经纬网】新增/改写的判据逐条注入真实缺陷，
确认每条都能失败（非空检查）。

设计原则（踩过的坑）：
  · 注入必须是**真实且有效**的缺陷，不能只是"改个字符串" ——
    若改动在语义上等价（如仅调整采样步长而仍沿弧线取点），检查本就该通过，
    那不是空检查、是注入无效。
  · 注入后必须断言"补丁确实进入了被检文本"，否则"未检出"可能只是补丁写错了位置。
  · 本脚本只改 template.html 文本并在内存中求值检查，不重建产物，故速度快、无副作用。
    （投影类判据读的是 tmpl 源码，无需产物；故直接用 audit_issues 的判据逻辑复算。）
"""
import io, os, re, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = HERE          # 本脚本与 template.html 同在 build/
TPL = open(os.path.join(BUILD, 'template.html'), encoding='utf-8').read()


def get_dg(t):
    """按大括号配平截取 drawGrid 函数体（与 audit_issues.py 同法）"""
    i0 = t.index('function drawGrid()')
    dp, end = 0, i0
    for k in range(i0, len(t)):
        if t[k] == '{':
            dp += 1
        elif t[k] == '}':
            dp -= 1
            if dp == 0:
                end = k + 1
                break
    return t[i0:end]


def get_cty_rule(t):
    i = t.index('.cty{')
    raw = ' '.join(t[i:t.index('}', i)].split())
    return re.sub(r'/\*.*?\*/', '', raw, flags=re.S)


# 每条： (名称, 对 tmpl 的变换, 检查函数(返回 True=通过))
# 检查函数返回 False 即代表缺陷被检出。

def c_lcc_y(t):
    b = t[t.index('function lcc('):t.index('var MAIN_BB')]
    ret = [l for l in b.splitlines() if 'return [' in l]
    return (len(ret) == 1 and re.search(
        r'return\s*\[\s*rho\s*\*\s*Math\.sin\(th\)\s*,\s*\+?\s*rho\s*\*\s*Math\.cos\(th\)\s*\]',
        ret[0]) is not None and '-rho' not in ret[0].replace(' ', ''))


def c_lcc_x(t):
    b = t[t.index('function lcc('):t.index('var MAIN_BB')]
    return 'Math.sin(th)' in b


def c_n_formula(t):
    return ('Math.log(Math.cos(LCC_LAT1*RAD) / Math.cos(LCC_LAT2*RAD))' in t and
            'Math.tan(Math.PI/4 + LCC_LAT2*RAD/2) / Math.tan(Math.PI/4 + LCC_LAT1*RAD/2)' in t)


def c_lat12(t):
    return 'var LCC_LAT1 = 30, LCC_LAT2 = 60;' in t


def c_lng0(t):
    return 'var LCC_LNG0 = 105;' in t


def c_projbounds(t):
    return ('function projBounds' in t and 'N = 200' in t and
            t.count('acc(bb.lng[0]') >= 2 and t.count('acc(bb.lng[1]') >= 1)


def c_shared(t):
    return t.count('var B = projBounds(bb);') == 2


def c_atan2(t):
    return 'Math.atan2(px, py)' in t


def c_dg_len(t):
    d = get_dg(t)
    return len(d) > 2000 and d.rstrip().endswith('}')


def c_E(t):
    return '°E"' in get_dg(t)


def c_N(t):
    return '°N"' in get_dg(t)


def c_pts(t):
    d = get_dg(t)
    return 'pts.push(PM(' in d and 'pts = [];' in d


def c_segclip(t):
    d = get_dg(t)
    return 'clipLineToRect(pts[j-1][0]' in d and 'gGrid.appendChild(mk("path"' in d


def c_step(t):
    return 'step = GRID_STEP/' in get_dg(t)


def c_ray(t):
    d = get_dg(t)
    return 'PM(i, -60)' in d and 'PM(i, 80)' in d


def c_lineclip(t):
    return 'clipLineToRect(pa[0], pa[1], pb[0], pb[1]' in get_dg(t)


def c_mainbb(t):
    d = get_dg(t)
    return ('var lngMin = MAIN_BB.lng[0], lngMax = MAIN_BB.lng[1];' in d and
            'var latMin = MAIN_BB.lat[0], latMax = MAIN_BB.lat[1];' in d)


def c_label_clip(t):
    d = get_dg(t)
    return ('var lx = Math.max(vx0 + 12, Math.min(vx1 - 12, lp[0]));' in d and
            'var ly = Math.max(vy0 + 10, Math.min(vy1 - 6, best[1] - 3));' in d and
            'var lx2 = Math.max(vx0 + 12, Math.min(vx1 - 12, best[0] - 5));' in d)


def c_cty_trans(t):
    return re.search(r'(?<![\w-])fill\s*:\s*transparent', get_cty_rule(t)) is not None


def c_cty_none(t):
    return re.search(r'(?<![\w-])fill\s*:\s*none', get_cty_rule(t)) is None


def c_cty_pe(t):
    return 'pointer-events:visiblePainted' in get_cty_rule(t)


def c_cty_click(t):
    return 'el.addEventListener("click"' in t and 'toggleFeat("c:" + c.a)' in t


def c_cty_drag(t):
    return 'if(!dragMoved && !measOn) toggleFeat("c:" + c.a)' in t


def sub1(old, new):
    def f(t):
        assert old in t, '注入锚点未找到: ' + old[:60]
        return t.replace(old, new, 1)
    return f


def chk_rule(name, mutate, check, must_appear=None):
    """注入 → 断言补丁生效 → 断言检查失败"""
    t2 = mutate(TPL)
    if must_appear is not None:
        assert must_appear in t2, '[' + name + '] 注入未进入文本，本项无效'
    assert t2 != TPL, '[' + name + '] 注入未改变文本，本项无效'
    passed = check(t2)
    return passed


CASES = [
    # ---- 投影：真实缺陷（会画错图 / 无法反算） ----
    ('y 取 −ρcosθ（南北倒置，真实发生过的 bug）',
     sub1('return [rho * Math.sin(th), rho * Math.cos(th)];',
          'return [rho * Math.sin(th), -rho * Math.cos(th)];'),
     c_lcc_y, '-rho * Math.cos(th)'),
    ('x 误取 cosθ（经向错位 90°）',
     sub1('return [rho * Math.sin(th), rho * Math.cos(th)];',
          'return [rho * Math.cos(th), rho * Math.cos(th)];'),
     c_lcc_x, None),
    ('标准纬线误改为 25/47（n 变了，形状全错）',
     sub1('var LCC_LAT1 = 30, LCC_LAT2 = 60;', 'var LCC_LAT1 = 25, LCC_LAT2 = 47;'),
     c_lat12, 'LCC_LAT1 = 25'),
    ('中央经线误改为 0（扇形整体旋转）',
     sub1('var LCC_LNG0 = 105;', 'var LCC_LNG0 = 0;'),
     c_lng0, 'LCC_LNG0 = 0;'),
    ('n 的分子分母颠倒（圆锥常数取倒数）',
     sub1('Math.log(Math.cos(LCC_LAT1*RAD) / Math.cos(LCC_LAT2*RAD)) /',
          'Math.log(Math.cos(LCC_LAT2*RAD) / Math.cos(LCC_LAT1*RAD)) /'),
     c_n_formula, 'Math.cos(LCC_LAT2*RAD) / Math.cos(LCC_LAT1*RAD)) /'),
    ('反投影 atan2 参量颠倒（反算纬度整体偏 90°）',
     sub1('var th  = Math.atan2(px, py);', 'var th  = Math.atan2(py, px);'),
     c_atan2, 'Math.atan2(py, px)'),
    ('projBounds 退化为四角取极值（纬线下凹 → 外接盒偏小）',
     sub1('  var i, N = 200, t, p, x, y;', '  var i, N = 0, t, p, x, y;'),
     c_projbounds, 'N = 0'),
    ('makeInv 不复用 projBounds（正逆不再严格互逆）',
     sub1("function makeInv(bb, vw, vh, pad){\n  var B = projBounds(bb);",
          "function makeInv(bb, vw, vh, pad){\n  var B = [0,0,1,1];"),
     c_shared, 'function makeInv(bb, vw, vh, pad){\n  var B = [0,0,1,1];'),
    # ---- 经纬网：真实缺陷（会画错线 / 度标消失） ----
    ('drawGrid 截取窗口退化（模拟固定 2000 字符旧写法）',
     lambda t: t[:t.index('function drawGrid()')] + 'function drawGrid(){ }',
     c_dg_len, None),
    ('经度度标漏掉 E 后缀（会出现「-5°E」式矛盾读数）',
     sub1('}, i + "°E"));', '}, i));'),
     c_E, 'i));'),
    ('纬度度标漏掉 N 后缀',
     sub1('}, i + "°N"));', '}, i));'),
     c_N, 'i));'),
    ('纬线退化为直线（不采样，弓高达 171px 会明显画错）',
     sub1('''    pts = [];
    for(j = lng0 - 4*GRID_STEP; j <= lng1 + 4*GRID_STEP; j += step){
      pts.push(PM(j, i));
    }''',
          '''    pts = [PM(lng0, i), PM(lng1, i)];'''),
     c_pts, 'pts = [PM(lng0, i), PM(lng1, i)];'),
    ('纬线采样步长放大到格距的 10 倍（弧线精度不足）',
     sub1('step = GRID_STEP/8;', 'step = GRID_STEP*10;'),
     c_step, 'step = GRID_STEP*10;'),
    ('经线只画到数据边界（放大后断在画中）',
     sub1('var pa = PM(i, -60), pb = PM(i, 80);',
          'var pa = PM(i, MAIN_BB.lat[0]), pb = PM(i, MAIN_BB.lat[1]);'),
     c_ray, 'var pa = PM(i, MAIN_BB.lat[0]), pb = PM(i, MAIN_BB.lat[1]);'),
    ('经线不经裁剪（直接画两端点，超出画面）',
     sub1('''    seg = clipLineToRect(pa[0], pa[1], pb[0], pb[1], cx0, cy0, cx1, cy1);
    if(!seg) continue;''',
          '''    seg = [pa[0], pa[1], pb[0], pb[1]];'''),
     c_lineclip, 'seg = [pa[0], pa[1], pb[0], pb[1]];'),
    ('格线改用视图四角反算（画出 50–155°E 的无用经线）',
     sub1('var lngMin = MAIN_BB.lng[0], lngMax = MAIN_BB.lng[1];',
          'var lngMin = -20, lngMax = 200;'),
     c_mainbb, 'var lngMin = -20, lngMax = 200;'),
    ('度标不再夹取到画面内（缩放后飘到画面外）',
     sub1('var lx = Math.max(vx0 + 12, Math.min(vx1 - 12, lp[0]));',
          'var lx = lp[0];'),
     c_label_clip, 'var lx = lp[0];'),
    # ---- 城市命中：真实缺陷（注册过的 UX bug） ----
    ('.cty 改回 fill:none（面不可点击 —— 海西州"点了没反应"）',
     sub1('  fill:transparent;pointer-events:visiblePainted;fill-rule:evenodd}',
          '  fill:none;pointer-events:visiblePainted;fill-rule:evenodd}'),
     c_cty_trans, 'fill:none;pointer-events:visiblePainted'),
    ('.cty 保留 fill:none 冗余声明（陷阱：误删下一行即静默失效）',
     sub1('.cty{stroke:#7ba6d6;', '.cty{fill:none;stroke:#7ba6d6;'),
     c_cty_none, '.cty{fill:none;stroke:#7ba6d6;'),
    ('.cty 去掉 pointer-events:visiblePainted',
     sub1('fill:transparent;pointer-events:visiblePainted;fill-rule:evenodd}',
          'fill:transparent;fill-rule:evenodd}'),
     c_cty_pe, 'fill:transparent;fill-rule:evenodd}'),
    ('cty 点击处理器被移除（地图上点单元无反应）',
     sub1('el.addEventListener("click", function(ev){ ev.stopPropagation(); if(!dragMoved && !measOn) toggleFeat("c:" + c.a); });',
          'void el;'),
     c_cty_click, 'void el;'),
    ('cty 点击不再排除拖拽（拖图误选中单元）',
     sub1('if(!dragMoved && !measOn) toggleFeat("c:" + c.a)',
          'toggleFeat("c:" + c.a)'),
     c_cty_drag, 'toggleFeat("c:" + c.a); });'),
]

P = print
P('=' * 76)
P('注入回归：确认【投影】【经纬网】【下辖单元命中】判据均非空')
P('=' * 76)
bad = 0
for name, mut, check, must in CASES:
    try:
        ok = chk_rule(name, mut, check, must)
    except AssertionError as e:
        P('  !! %s\n     %s' % (name, e))
        bad += 1
        continue
    # 未注入时必须通过（否则基线本身就错）
    base = check(TPL)
    if not base:
        P('  !! 基线不通过（说明当前模板已违反该判据）：%s' % name)
        bad += 1
        continue
    if ok:
        P('  ✗ 未检出：%s' % name)
        bad += 1
    else:
        P('  ✓ 已检出：%s' % name)
P('')
P('=' * 76)
if bad:
    P('注入回归失败：%d 项（存在空检查或基线错误）' % bad)
else:
    P('注入回归：%d/%d 全部检出 —— 全部判据均为非空检查' % (len(CASES), len(CASES)))
P('=' * 76)
