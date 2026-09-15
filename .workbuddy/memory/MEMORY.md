# 项目长期记忆 · 中国气象地理区划交互地图

## 项目定位
单文件离线 SVG 交互地图，教学/演示用途。成品：`中国气象地理区划交互地图.html`（857.6 KB，零外部资源）。
**不追求"权威地图"，但所有声明必须诚实** —— 项目已有较高的披露标准，改动文案时要维持这一标准。

## 三层结构
- `data/`（11.2 MB）：DataV.GeoAtlas 行政区划（GCJ-02，34 省 + 475 地级单元）+ Natural Earth `ne_10m_rivers_lake_centerlines`（WGS-84）。
- `build/`：`fetch_national.py` → `fetch_cities.py` / `fetch_rivers.py` → `geo.py`（几何压缩，产出 `out/geo.json`）→ `content.py`（内容层，产出 `out/data.json`）→ `assemble.py`（注入 `template.html`）。
- **统一入口：`python build/build.py`**（`--check` 只校验、`--fetch` 强制重抓）。它按序调 4 个脚本并跑三道构建门禁 + 产物一致性校验，**改动上游一律走它，不要手工按序跑单个脚本**。
- 三道门禁（在 `content.py` 末尾，失败即终止）：① 山脉注记必须在自身示意范围内；② `FEAT` 要素必须与所属省相交；③ `EXTRA_RIVERS` 的"缺失"主张必须成立（关键词表 `_NE_KEYWORD`）。

## 关键约定与坑
- 坐标系**混用**：行政区划 GCJ-02、河流 WGS-84。本图比例下偏移约 0.11 px（不可见），但不要在此基础上做高精度量测。
- `mt_shapes.py` 的 `SHAPES` 与 `content.py` 的 `MT` 必须**键名一一对应**（已有断言）。**山脉范围与注记坐标的耦合易出错**：注记点必须距多边形边界 ≥0.08°，否则 `int(round(x*1000))` 取整后会内外翻转。改坐标后跑 `build.py` 即可验证。
- 区划成员结构：WHOLE 成员为 `{p, all:1}`，SPLIT 成员为 `{p, ci:[索引]}`，**SPLIT 成员没有 `all` 键**。Python 处理时用 `.get('all')`，JS 里 `!mem.all` 可直接用。
- 主图按"外环最大纬度 < 17.8°N 剔除"排除南海岛礁，只在附图呈现；附图包围盒 104.5–125°E / 2.5–24.5°N。
- 河流拼接 `stitch()` 的 `max_bridge=0.45°`，只连链的端点，**不处理"端点接在另一链中部"**（北江/郁江即因此独立成段，视觉上仍在汇合点相接）。
- **河名标注**：`rv.lp`（数据层锚点）优先，否则按最长段的**累积弧长中点**。`RIVER_LABEL` 里为珠江、长江显式给了锚点。
- **判断"NE 是否覆盖某河段"不要只数区间内点数**——NE 有同名碎段会让计数虚高。可靠判据是删掉手工段后看 `stitch()` 的 chain 数是否仍为 1。
- NE 中的中文河英文名（易踩）：`Jialing`=嘉陵江、`Wu`=乌江（同名的 `Wujia`=乌加河）、`Min`=岷江/闽江（两条，靠 box 区分）、`Ou`=瓯江（另有云南同名）、`Fuchun`=富春江、`Bei`/`Dong`/`Xi`/`Yu`=北江/东江/西江/郁江、`Hai`+`Yongding`=海河干流+永定河。

## 已修复（2026-09-15 两轮）
P0 页脚"整条缺失河流"名单已据实重写（原 6 条中 5 条 NE 中本有真实河道，已改回）；青海误列怒江已删除。
P1 10 座山脉注记越界 → 已校正（现 100/100 通过门禁）；长白山范围延至辽东；喜马拉雅山范围南拉含珠峰；山东日照改归黄淮；台湾/澳门数据缺口与坐标基准已在页脚披露；珠江标注已从贵州移到珠江三角洲。
剩余**未处理**（低优先，非错误）：福建、湖北的城市级划分口径仍属推断，页脚已声明；`data/` 11.2 MB 中 `ne_rivers.geojson` 占 7.1 MB 仅用极小部分，尚未裁剪。
详见 `.workbuddy/memory/2026-09-15.md` 与 `核查报告-中国气象地理区划交互地图.html`。

## 验证方法（复用）
- `NODE_PATH="$APPDATA/npm/node_modules" <node> xxx.js` + `chromium.launch({channel:'chrome',headless:true})`，用全局 `@playwright/test`，无需下载 Chromium。
- 交付前必须确认页面 `pageerror` / `console.error` 均为零。
- 低对比度细线（1.5 px 浅色虚线）必须在 `deviceScaleFactor:2` 下截图，否则会误判"未渲染"。
