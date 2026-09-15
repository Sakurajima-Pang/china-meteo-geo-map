# 原始数据归档

本目录存放**构建所依赖的原始数据**的压缩归档。`data/` 目录下的原始文件不入库
（合计 11.5 MB，其中 `ne_rivers.geojson` 单文件即 7.0 MB），改为以归档形式提供，
使仓库克隆后仍可完整复现构建。

## 归档清单

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `rawdata-2026-09-15.zip` | 3.56 MB | `d68e50e5188dae7d2dc8c4eb2b5f0e97c6e10f8af18b05d27b0e76ecaa0bfb03` |

归档内含 35 个文件：

- `100000_full.json` — DataV.GeoAtlas 全国省级行政区划（含 `100000_JD` 九段线要素）
- `{adcode}_full.json` × 33 — 各省级行政区的下辖市级 / 区级界线。
  **不含台湾省（`710000`）**：DataV 接口对该省返回 404，台湾省下辖县市改由点位标注
- `ne_rivers.geojson` — Natural Earth `ne_10m_rivers_lake_centerlines`（WGS-84）

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
data/  11.5 MB / 35 files
```

## 校验

复原后建议核对完整性：

```bash
sha256sum archive/rawdata-2026-09-15.zip
# 应输出 d68e50e5188dae7d2dc8c4eb2b5f0e97c6e10f8af18b05d27b0e76ecaa0bfb03
```

若归档缺失，亦可直接跳过复原步骤 —— `python build/build.py --fetch` 会从上游
重新抓取全部原始数据。需要注意：上游数据是**滚动更新**的，重新抓取可能得到与本
仓库成品不同的几何版本（尤其是 Natural Earth 的 `master` 分支），此时
`build.py` 的产物一致性校验可能报出差异。要复现与本仓库一致的成品，请使用归档。
