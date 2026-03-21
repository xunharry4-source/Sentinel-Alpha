# Market Template Library

每个标的一个目录，例如：

- `data/market_templates/AAPL/`
- `data/market_templates/AMD/`
- `data/market_templates/TSLA/`

目录下至少包含：

- `daily.csv`
- `5m.csv`
- `meta.json`

`daily.csv` 字段：

```csv
timestamp,symbol,open,high,low,close,volume
2025-01-02T00:00:00Z,AAPL,250.0,255.0,248.0,254.0,100000000
```

`5m.csv` 字段：

```csv
timestamp,symbol,open,high,low,close,volume
2025-01-02T14:30:00Z,AAPL,250.0,250.8,249.5,250.4,1200000
```

`meta.json` 示例：

```json
{
  "playbook": "fake_reversal",
  "market_regime": "bear",
  "shape_family": "W",
  "pattern_label": "W 底诱多反杀",
  "notes": "用于测试假反、反抽、追涨回落"
}
```

建议至少覆盖这些标签：

- `shape_family`: `W`, `N`, `V`, `A`, `box`, `trend`
- `market_regime`: `bull`, `bear`, `oscillation`, `fake_reversal`, `gap`

导入命令：

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
PYTHONPATH=src python scripts/import_market_template_library.py
```

重组逻辑：

- 系统会先把真实交易日按“周”打乱重组
- 第一段使用测试基准价启动
- 从第二个交易日起，缩放锚点使用“上一交易日的真实收盘对应关系”
- 不再使用“当周第一天开盘价”作为整周统一缩放基准
