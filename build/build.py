# -*- coding: utf-8 -*-
"""统一构建入口。

用法：
    python build.py            完整构建（fetch -> geo -> content -> assemble），并做产物一致性校验
    python build.py --check    只做校验，不重新构建
    python build.py --fetch    连同联网抓取一起执行（默认只在缺少原始数据时抓取）

依赖顺序（务必遵守，改上游必须重跑下游）：
    fetch_national.py / fetch_cities.py / fetch_rivers.py
        -> data/*.json
    geo.py          -> build/out/geo.json      （几何）
    content.py      -> build/out/data.json     （内容；内置构建门禁）
    assemble.py     -> 中国气象地理区划交互地图.html
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
    print('  省级 %d、地级单元 %d、河流 %d、山脉 %d、湖泊 %d、区划 %d、岛礁符号 %d ✓'
          % (len(emb['p']), sum(len(v) for v in emb['ci'].values()), len(emb['rv']),
             len(emb['mt']), len(emb['lk']), len(emb['rg']), len(emb['isles'])))

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


def main():
    argv = sys.argv[1:]
    do_check_only = '--check' in argv
    do_fetch = '--fetch' in argv

    if not do_check_only:
        need = [os.path.join(DATA, '100000_full.json'), os.path.join(DATA, 'ne_rivers.geojson')]
        if do_fetch or not all(os.path.exists(p) for p in need):
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
