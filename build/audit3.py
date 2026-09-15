# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""审计脚本（三）：成品自包含性、构建链完备性与代码规模。只读，不修改任何产物。

与前两个审计不同，本脚本检查的是**工程形态**而非数据正确性：
- 离线自包含：成品 HTML 中是否存在任何外部资源引用（src / href 指向 http(s)）；
- 构建链：build/ 下是否有统一入口（本项目有 build.py）；
- 代码规模：Python / JS / 模板各自的行数分布。
"""
import io, sys, re, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
h = open('中国气象地理区划交互地图.html', encoding='utf-8').read()
print('【离线自包含性】')
ext = re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', h)
print('  外部资源引用:', ext if ext else '无 -> 完全离线自包含')
print('  内联 <script> 块:', len(re.findall(r'<script', h)), ' <style> 块:', len(re.findall(r'<style', h)))
print('  HTML 总大小: %.1f KB' % (len(h.encode()) / 1024))
m = re.search(r'const DATA = (\{.*?\});</script>', h, re.S)
print('  其中内嵌数据: %.1f KB (%.0f%%)' % (len(m.group(1).encode()) / 1024, len(m.group(1).encode()) / len(h.encode()) * 100))
print('  模板(不含数据): %.1f KB' % ((len(h) - len(m.group(1))) / 1024))
print()
print('【构建链】')
print('  build/ 下有无统一入口:',
      [f for f in os.listdir('build') if f.lower() in ('build.py', 'makefile', 'package.json', 'build.sh', 'run.py')] or '无 -> 需人工按序执行 fetch -> geo -> content -> assemble')
print()
print('【代码规模】')
tot = 0
for f in sorted(os.listdir('build')):
    p = os.path.join('build', f)
    if os.path.isfile(p) and f.split('.')[-1] in ('py', 'js', 'html'):
        n = sum(1 for _ in open(p, encoding='utf-8', errors='ignore')); tot += n
        print('  %-24s %5d 行' % (f, n))
print('  合计 %d 行' % tot)
print()
print('【遗留调试文件】', [f for f in os.listdir('build') if f.startswith(('dbg', 'test_', 'final_shot', 'inspect'))])
g = open('build/geo.py', encoding='utf-8').read()
print()
print('【geo.py 死代码】含空分支 if minpts in spec: pass ->', "if 'minpts' in spec:" in g)
print('【fetch_cities.py TLS】verify_mode=CERT_NONE ->', 'CERT_NONE' in open('build/fetch_cities.py', encoding='utf-8').read())
print()
print('【数据体积】')
for p in ['data/100000_full.json', 'data/ne_rivers.geojson', 'build/out/geo.json', 'build/out/data.json']:
    print('  %-32s %8.1f KB' % (p, os.path.getsize(p) / 1024))
tot = sum(os.path.getsize(os.path.join('data', f)) for f in os.listdir('data'))
print('  data/ 合计 %.1f MB' % (tot / 1024 / 1024))
