# 原始数据归档

本目录存放**构建所依赖的原始数据**的压缩归档。`data/` 目录下的原始文件不入库
（合计 13 MB，其中 `ne_rivers.geojson` 单文件即 7.3 MB），改为以归档形式提供，
使仓库克隆后仍可完整复现构建。

## 归档清单

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `rawdata-2026-09-15.zip` | 3.99 MB | `da84ad2bea4922c00c6b3e1369965a905b4545106e4198e3321857a75575fc83` |

归档内含 36 个文件：

- `100000_full.json` — DataV.GeoAtlas 全国省级行政区划（含 `100000_JD` 九段线要素）
- `{adcode}_full.json` × 33 — 各省级行政区的下辖市级 / 区级界线。
  **不含台湾省（`710000`）**：DataV 接口对该省返回 404，台湾省下辖县市改由点位标注
- `ne_rivers.geojson` — Natural Earth `ne_10m_rivers_lake_centerlines`（WGS-84）
- `ne_rivers_cn.geojson` — 上者的**中国子集裁剪版**（7.3 MB → 1.19 MB，238 个要素）。
  非独立数据源，由 `build/fetch_rivers.py` 从 `ne_rivers.geojson` 派生：只保留与中国
  包围盒（73–136.5°E / 17–54.5°N）相交的整条要素，**不裁剪顶点**，故几何与原始文件
  逐点一致（已验证裁剪前后 `geo.json` 指纹相同）。`geo.py` 优先读该文件，
  未裁剪时自动回退读原始文件。归档内一并提供，是为了让克隆者跳过 7 MB 的解析开销。

## 复原方法

PowerShell：

```powershell
Expand-Archive archive/rawdata-2026-09-15.zip -DestinationPath data -Force
```

或 Python（跨平台）：

```bash
python -c "import zipfile; zipfile.ZipFile('archive/rawdata-2026-09-15.zip').extractall('data')"
```

复原后 `data/` 目录的大小与文件清单：

```
data/  13 MB / 36 files
```

## 校验

复原后建议核对完整性：

```bash
sha256sum archive/rawdata-2026-09-15.zip
# 应输出 da84ad2bea4922c00c6b3e1369965a905b4545106e4198e3321857a75575fc83
```

若归档缺失，亦可直接跳过复原步骤 —— `python build/build.py --fetch` 会从上游
重新抓取全部原始数据。需要注意：上游数据是**滚动更新**的，重新抓取可能得到与本
仓库成品不同的几何版本（尤其是 Natural Earth 的 `master` 分支），此时
`build.py` 的产物一致性校验可能报出差异。要复现与本仓库一致的成品，请使用归档。
