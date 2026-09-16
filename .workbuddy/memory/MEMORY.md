# 项目长期记忆 · 中国气象地理区划交互地图

## 定位与交付
单文件离线 SVG 交互地图（教学/演示），功能含悬停/单击联动、区划框选、缩放平移、经纬网、经纬度读数、图上测距。
成品 `中国气象地理区划交互地图.html`，**1785.5 KB、零外部资源**。
**不追求「权威地图」，但所有声明必须诚实** —— 披露标准较高，改文案要维持。
仓库 `github.com/Sakurajima-Pang/china-meteo-geo-map`（public，`main`）。
交付标准：全新 clone → 解压 `archive/rawdata-*.zip` 到 `data/` → `python build/build.py` → 成品**逐字节相同**。

## 构建管线与门禁
唯一入口 `python build/build.py`（**勿手工按序跑单脚本**）：
`fetch_*.py` → `geo.py`（简化/量化/摘除 → `out/geo.json`）→ `content.py`（内容 → `out/data.json`）→ `assemble.py`（注入 `template.html`）。
**八道门禁**，任一失败即终止：`geo.py` 3 道（产物无残留人造轮廓 / 声明必命中几何 / 声明点附近**真实陆地恰 1 环**）→ `content.py` 4 道（山脉注记 / 要素相交 / 河流缺失主张 / 东沙细分声明）→ `build.py` 1 道（`node --check` 每个 `<script>`）。详见 README。

## 易错的数据结构
- 区划成员：WHOLE `{p, all:1}` / SPLIT `{p, ci:[…]}`（**SPLIT 无 `all` 键**）。
- `FEAT = {m:[山脉键名(无前缀)], w:[河流/湖泊("r:"/"l:" 前缀)]}` —— **湖泊坐标取 `[1],[2]`**（写复核脚本极易错）。
- `SHAPES`(mtn_shapes.py) 与 `MT`(content.py) 键名须一一对应（已断言）；`stitch()` 只连链端点。

## 两个易被静默破坏的模板约定
- `assemble.py` 要求 `/*__DATA__*/` 在模板中**恰好 1 次**；写在注释里会**双份注入、体积翻倍而校验仍全等通过**。
- **模板注释里不可出现 `script` 标签字面量**（会提前终止脚本块解析）。

## 投影：兰勃特等角圆锥（30°N/60°N 双标准纬线、中央经线 105°E）
**改投影必同步三处**：① 经线是射线、纬线是圆弧（弓高最大 171 px，**不可直线近似**，须按经度采样成点串）；
② `projBounds()` 不能取四角极值（纬线下凹，y 极值落在**南边界中央**），须沿四边密集采样；
③ 经纬网范围取自 `MAIN_BB`（→15 条经线），**不是**视图四角、也**不是**内容 bbox。
已踩坑：`lcc` 曾误取 `y=−ρ·cosθ` 致**整图南北倒置**（正确 `y=+ρ·cosθ`）；度标须夹到**画面边界**而非内容 bbox。

## 前端已固化的约定
- 逆投影 `makeInv` 与 `makeProj` **共用参数**故严格互逆；坐标读数取 **viewBox 坐标**（非屏幕像素）。
- 测距用 **Haversine**（`EARTH_R=6371.0088`），**不可用平面欧氏**。
- `.cty` 必须 `fill:transparent`（`fill:none` 使**面**不参与命中测试）+ `pointer-events:visiblePainted` + **`fill-rule:evenodd`**。
- `gMeas` 与 `gGrid` **不参与 `clipMain`**；`gGrid` 还须 `pointer-events:none`；`drawGrid()` 必须先清空再重绘。
- 交互互斥**不要用 `stopPropagation`**（会掐掉同一 svg 的 pointerup 取点）；双击结束用原生 `dblclick`；`setMeasure` 里**还原必须先于备份**，否则省名再也回不来。
- 可点击符号用 SVG 原生 `<title>` 给提示（不依赖 JS）。

## 东沙群岛（最易踩，完整考证见 `build/isles_data.py` 头部）
- DataV 把东沙表示为**三块圆形 range ring**（173/111/43 km²，圆度 0.26/0.93/0.82）——**不是海岸线**。
- **摘除需两判据同时成立**（`is_synthetic()`）：质心 ≤`MATCH_R_KM`(25) **且** 面积 ≥`MIN_SYNTH_AREA_KM2`(10)。
  ⚠ **只凭质心会连真实东沙岛本体（1.67 km²，质心距声明坐标仅 3.28 km）一并摘掉** —— 已实际发生并修复。
- ⚠ **同一批 ring 在省级与市级各存一份几何**（`100000_full.json` 的广东省 `440000` 与 `440000_full.json` 的汕尾市 `441500`），**两份都要摘**（`REMOVE_FROM` 两者都列）。只摘市级那份时 ring 仍经**省级图层**渲染，「摘了却还有印子」—— 已实际发生。
- 三块摘除后**丢弃**改以点状符号：实心=有露出陆地、空心=沉水。北卫滩/南卫滩相距 12.2 km、主图仅 1.8 单位 → **合群为一枚符号**；`<title>` 逐块给出水深，信息未丢失。
- `ISLES` 的「东沙群岛」代表点**不再渲染**（`ISLES_SUPERSEDED`）：与东沙岛点仅差 **0.3 单位**，重叠会使实心点白描边露出成月牙白边。⚠ 该 JS 常量与 Python 数据**无法共享**，改动须手工同步两处。
- **主图不渲染东沙**（2026-09-16 用户要求）：主图只表达一级气象地理区划，东沙距汕尾
  陆域约 295 km、孤悬南海，与「香港」省名相邻显得突兀。故 `gIsle` 图层、`drawIsleMarks()`、
  `.islt`/`.isll` 样式全部移除。**附图（`gInset`）仍保留** —— 附图是南海诸岛指定呈现位，
  东沙与西沙/中沙/南沙并列，移除会使四大群岛缺一、领土表述不完整。主图与附图的这一区别
  已在页脚第 7 条如实披露。⚠ 别因「主图没有」就删 `DATA_.dongsha` 或 `isles_data.py` 的声明表。
- 自检：`python build/isles_data.py`。

## 验证：判据必须能失败（否则是空检查）
**恒通过的检查比没有检查更危险。** 已逮到 ≥10 处空检查，全是「看起来对、实际测不出」。做法：
1. 判据**绑定到具体声明语句/语义单元**；不要只判「函数体含某子串」，也不要把多条件拆成互不相关的全局 `in` 测试。
2. 文本检查前**先剥注释**（注释常复述被检查的关键字）。
3. 写完判据立即**注入真实缺陷**验证会失败（`build/dev-scratch/inject_proj.py`）。注入前 `assert old in src` 且 **`old != new`**（曾因锚点少一个空格静默跳过，误判「未检出」）。
4. 凡检查模板内容，**不要从成品读**（成品是 assemble 的产物，不同步）。容差不可设到机器精度（`toFixed(1)` 落格会放大误差，「恒失败」的是判据而非页面）。
5. **上游过滤器可能提前剔掉下游要检查的东西**，此时下游断言仍会通过 —— 必须加**正面**判据，而不只是「没被本表摘掉」。
6. **数枚数式的判据几乎总是空检查**（如「摘除数 == 声明数」）：只要存在**多个可摘之处**（同一数据在省级/市级各一份），漏摘其中一处时枚数不变、判据照过。应改为**后置条件**（扫产物确认「不许存在残留」）+ **正向兑现**（每条声明都要被命中），两者互补。
7. **负向判据（「图上没有 X」）必须配一条对照判据**（「但 Y 处确实还有 X」）—— 否则把数据全删了它照样通过。`verify_isles.js` 【二】组即此模式。

## 验证脚本与运行环境
静态：`audit.py` / `audit2.py` / `audit3.py` / `audit_issues.py` / `inject_proj.py` / `isles_data.py`。
渲染：`audit_render.js` / `verify_fix.js` / `verify_tools.js` / `verify_grid.js` / `verify_isles.js` / `verify_city_hit.js`。
均需 `NODE_PATH="$APPDATA/npm/node_modules"` + 本机 Chrome；**多数需 `<HTML路径> <输出目录>` 两个参数**（缺参数报 `ERR_INVALID_ARG_TYPE`）。
交付前 `pageerror` / `console.error` 必须为零；推送前另做全新 clone 端到端验证。
低对比度细线须 `deviceScaleFactor:2` 截图，否则误判「未渲染」。临时脚本放 `build/dev-scratch/`，**不要放 `/tmp`**（Git Bash 下 node 会解析成 `D:\tmp`）。

## 本机坑
- `data/`、`build/out/`、`build/dev-scratch/` 均不入库。`.gitattributes` 的 `* text=auto eol=lf` **不要删**（本机 `core.autocrlf=true` 会转 CRLF、产生虚假 diff）。
- `git push` 报 `schannel: failed to receive handshake` → `git config http.sslBackend openssl`。GitHub 会剔除仓库名中的非 ASCII 字符（中文名静默变 `-`）。
- ⚠ **未提交的工作绝不能用 `git checkout` 回退** —— 曾因此摧毁整个兰勃特改造。改动前先提交或备份到项目内。
- `changes-detail` / `modify_backup` 目录会**自动轮转**（数十分钟），需要的内容须**立即** `cp` 到项目内。
- 坐标系**混用**（行政区划 GCJ-02 / 河流 WGS-84），偏移约 0.11 px，不可做高精度量测。

## 文档同步（改动后必须跟上）
`README.md`、`核查报告-*.html`、日日志中的**体积与指纹数字**须与实际一致。
核查报告**只记录仍成立的事实**：已修复项在修复时即删除（约束以门禁或回归脚本固化），不保留历史陈述。
