# -*- coding: utf-8 -*-
"""统一构建入口。

用法：
    python build.py            完整构建（fetch -> geo -> content -> assemble），并做产物一致性校验
    python build.py --check    只做校验，不重新构建
    python build.py --fetch    连同联网抓取一起执行（默认只在缺少原始数据时抓取）

依赖顺序（务必遵守，改上游必须重跑下游）：
    fetch_national.py / fetch_cities.py / fetch_rivers.py
        -> data/*.json（fetch_rivers.py 另产出裁剪版 ne_rivers_cn.geojson）
    geo.py          -> build/out/geo.json      （几何）
    content.py      -> build/out/data.json     （内容；内置三道构建门禁）
    assemble.py     -> 中国气象地理区划交互地图.html

校验共四道（全部在 verify() / check_js_syntax() 中）：
    ① 内嵌数据与中间产物逐字段全等；② 前端字段完整性；③ 坐标范围与离线自包含；
    ④ 成品 JS 语法可解析（防止语法错误导致整页空白而构建仍报通过）。
"""
import json, os, re, subprocess, sys, io, hashlib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(HERE, 'out')
TARGET = os.path.join(ROOT, '中国气象地理区划交互地图.html')
DATA = os.path.join(ROOT, 'data')
PY = sys.executable


def run(script, title):
    print('\n' + '=' * 66)
    print('▶ %s' % title)
    print('=' * 66)
    r = subprocess.run([PY, os.path.join(HERE, script)], cwd=HERE,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = r.stdout.decode('utf-8', 'replace')
    print(out.rstrip())
    if r.returncode != 0:
        raise SystemExit('✗ %s 失败（退出码 %d）' % (script, r.returncode))


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 16), b''):
            h.update(b)
    return h.hexdigest()[:16]


def verify():
    """校验成品 HTML 内嵌的 DATA 与中间产物完全一致，且数据可被前端逻辑解析。"""
    print('\n' + '=' * 66)
    print('▶ 产物一致性校验')
    print('=' * 66)
    geo = json.load(open(os.path.join(OUT, 'geo.json'), encoding='utf-8'))
    ctx = json.load(open(os.path.join(OUT, 'data.json'), encoding='utf-8'))
    html = open(TARGET, encoding='utf-8').read()
    m = re.search(r'const DATA = (\{.*?\});</script>', html, re.S)
    if not m:
        raise SystemExit('✗ 成品 HTML 中未找到内嵌 DATA')
    emb = json.loads(m.group(1).replace('<\\/', '</'))

    exp = {
        'p': [{'a': p['ad'], 'n': p['name'], 'c': p['c'], 'g': p['g']} for p in geo['provinces']],
        'ci': {ad: [{'a': c['ad'], 'n': c['name'], 'c': c['c'], 'g': c['g']} for c in lst]
               for ad, lst in geo['cities'].items()},
        'jd': [ring for poly in geo['jd'] for ring in poly],
        'rv': ctx['rivers'], 'mt': ctx['mt'], 'lk': ctx['lk'],
        'rg': ctx['regions'], 'pr': ctx['provRegions'], 'feat': ctx['feat'],
        'info': ctx['info'], 'ec': ctx['extraCities'], 'isles': ctx['isles'],
        'dongsha': ctx['dongsha'],
    }
    bad = [k for k in exp if emb.get(k) != exp[k]]
    if bad:
        raise SystemExit('✗ 成品与中间产物不一致的字段: %s' % '、'.join(bad))
    print('  内嵌数据与 out/geo.json + out/data.json 逐字段全等（%d 个字段）✓' % len(exp))

    # 前端渲染依赖的字段完整性
    ads = [p['a'] for p in emb['p']]
    miss_info = [a for a in ads if a not in emb['info']]
    miss_pr = [a for a in ads if a not in emb['pr']]
    if miss_info or miss_pr:
        raise SystemExit('✗ 前端所需字段缺失: info=%s pr=%s' % (miss_info, miss_pr))
    unres = []
    for r in emb['rg']:
        for mm in r['mem']:
            if mm.get('all'):
                if mm['p'] not in ads:
                    unres.append(r['id'] + '->' + mm['p'])
            elif mm['p'] not in emb['ci'] or (mm['ci'] and max(mm['ci']) >= len(emb['ci'][mm['p']])):
                unres.append(r['id'] + '->' + mm['p'])
    if unres:
        raise SystemExit('✗ 前端无法解析的区划成员引用: %s' % unres)
    print('  省级 %d、地级单元 %d、河流 %d、山脉 %d、湖泊 %d、区划 %d、岛礁符号 %d、东沙细分符号 %d ✓'
          % (len(emb['p']), sum(len(v) for v in emb['ci'].values()), len(emb['rv']),
             len(emb['mt']), len(emb['lk']), len(emb['rg']), len(emb['isles']),
             len(emb['dongsha'])))

    # 坐标越界检查
    oob = []
    for k, v in emb['mt'].items():
        if not (73 <= v[1] <= 136 and 17 <= v[2] <= 54):
            oob.append('山 ' + v[0])
    for k, v in emb['lk'].items():
        if not (73 <= v[1] <= 136 and 17 <= v[2] <= 54):
            oob.append('湖 ' + v[0])
    for it in emb['isles']:
        if not (73 <= it[1] <= 136 and 0 <= it[2] <= 54):
            oob.append('岛 ' + it[0])
    if oob:
        raise SystemExit('✗ 注记坐标越出中国范围: %s' % oob)
    print('  注记坐标全部落在中国范围内 ✓')

    ext = re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', html)
    if ext:
        raise SystemExit('✗ 成品存在外部资源引用，不再是离线自包含: %s' % ext)
    print('  离线自包含（零外部资源引用）✓  HTML %.1f KB' % (os.path.getsize(TARGET) / 1024))
    print('\n  产物指纹  geo.json=%s  data.json=%s'
          % (sha(os.path.join(OUT, 'geo.json')), sha(os.path.join(OUT, 'data.json'))))

    check_js_syntax(html)


def check_js_syntax(html):
    """门禁 4：成品中的每个 <script> 块必须能通过 JS 语法解析。

    为什么需要这一条：上述所有校验（字段全等、引用完整性、坐标范围、外部资源）
    都只看**数据**，对**前端代码的语法错误完全不敏感**。一个多余的 `}` 可以让
    整个脚本块无法解析，页面渲染出 0 个元素，而构建仍然报"全部通过"。
    本项目曾真实发生过：编辑降级代码时多留了一个 `})();`，产物被推送后
    整页空白，直到跑无头浏览器验证才发现。

    实现：把每个 script 块写入临时文件，用 node --check 解析。
    node 不可用时给出警告而不中断（保持「无 node 环境也能构建」的能力），
    但会明确提示该门禁未执行——"未执行"与"通过"必须能被区分。
    """
    blocks = re.findall(r'<script>(.*?)</script>', html, re.S)
    if not blocks:
        raise SystemExit('✗ 成品中未找到任何 script 块')
    node = None
    for cand in ('node', 'node.exe'):
        try:
            r = subprocess.run([cand, '--version'], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=20)
            if r.returncode == 0:
                node = cand
                break
        except Exception:
            continue
    if node is None:
        print('  ⚠ JS 语法门禁未执行：未找到可用的 node，无法校验前端代码语法。')
        print('    （数据类校验已完成；建议在有 node 的环境重跑 build.py --check）')
        return
    import tempfile
    bad = []
    for i, blk in enumerate(blocks):
        fd, tmp = tempfile.mkstemp(suffix='.js')
        os.close(fd)
        try:
            with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
                f.write(blk)
            r = subprocess.run([node, '--check', tmp], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=60)
            if r.returncode != 0:
                msg = r.stdout.decode('utf-8', 'replace').strip().splitlines()
                bad.append('script 块 %d：%s' % (i, ' | '.join(msg[:3])))
        finally:
            os.remove(tmp)
    if bad:
        raise SystemExit('✗ 成品中的 JS 存在语法错误（页面将无法渲染）:\n  ' + '\n  '.join(bad))
    print('  JS 语法校验通过（%d 个 script 块）✓' % len(blocks))


def main():
    argv = sys.argv[1:]
    do_check_only = '--check' in argv
    do_fetch = '--fetch' in argv

    if not do_check_only:
        # 河流数据：裁剪版或原始文件任一存在即可（geo.py 优先读裁剪版）
        river_ok = any(os.path.exists(os.path.join(DATA, f)) for f in
                       ('ne_rivers_cn.geojson', 'ne_rivers.geojson'))
        need_ok = os.path.exists(os.path.join(DATA, '100000_full.json')) and river_ok
        if do_fetch or not need_ok:
            run('fetch_national.py', '抓取全国省级行政区划')
            run('fetch_cities.py', '抓取各省级下辖市级行政区划')
            run('fetch_rivers.py', '抓取 Natural Earth 河道中心线')
        else:
            print('原始数据已存在，跳过联网抓取（如需强制重抓请加 --fetch）')
        run('geo.py', '几何处理（简化 / 量化 / 河段拼接）')
        run('content.py', '内容层（区划归属 / 注记 / 要素清单，含构建门禁）')
        run('assemble.py', '注入模板，产出单文件 HTML')

    verify()
    print('\n✓ 构建与校验全部通过')


if __name__ == '__main__':
    main()
