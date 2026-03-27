# Sentinel-Alpha 页面与接口映射

以下文档从开发与联调视角整理当前 NiceGUI 页面和 FastAPI 接口的对应关系，方便按页面排查接口、做联调验收或补测试。

基准实现：
- 前端：`/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/nicegui/app.py`
- 后端：`/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/api/app.py`

当前本地热更新开发链路：
- NiceGUI: `http://127.0.0.1:8010`
- API: `http://127.0.0.1:8001`

## 页面：会话

### 页面说明

负责创建、加载和查看当前会话快照，是其它页面的上下文入口。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 创建会话 | 创建新的工作会话 | 是 | `POST /api/sessions` | 是 | 正常 |
| 加载会话 | 加载已有会话快照 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看会话摘要 | 读取当前 session 的关键信息 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看会话 JSON | 读取完整快照结构 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：配置

### 页面说明

负责系统配置的读取、编辑、保存与测试。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 加载配置 | 读取当前系统配置 payload 与 validation | 是 | `GET /api/config` | 是 | 正常 |
| 保存配置 | 保存编辑后的系统配置 | 是 | `POST /api/config` | 是 | 正常 |
| 全量配置测试 | 对配置做整体测试 | 是 | `POST /api/config/test` | 是 | 正常 |
| 单项配置测试 | 针对配置 family/provider 测试 | 是 | `POST /api/config/test-item` | 是 | 正常 |

## 页面：策略参数与目标

### 页面说明

负责训练前输入，包括股票池、目标函数、目标值和训练窗口。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 提交交易标的 | 设置交易标的池 | 是 | `POST /api/sessions/{session_id}/trade-universe` | 是 | 正常 |
| 训练参数校验 | 前端校验训练窗口和目标值是否合法 | 否 | 无 | 是 | 正常 |
| 发起策略迭代 | 提交训练参数并触发一轮或多轮训练 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 查看当前策略状态 | 查看策略包、特征快照、输入数据包等 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：训练页面

### 页面说明

负责训练过程控制、反馈回填、人工介入与训练结果检查。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 继续自动训练 | 延续自动迭代模式继续训练 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 我来介入后再训练 | 切换到人工反馈模式 | 否 | 无 | 是 | 正常 |
| 确认当前策略 | 将当前策略设为确认状态 | 是 | `POST /api/sessions/{session_id}/strategy/approve` | 是 | 正常 |
| 查看策略检查 | 查看完整性、压测、过拟合检查 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看训练日志 | 查看训练过程和本地联动日志 | 是 | `GET /api/sessions/{session_id}` | 是 | 部分正常 |

## 页面：结果页面

### 页面说明

负责展示训练输出的总计指标、按年指标、回测和滚动窗口结果。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 查看模型总计指标 | 查看 full period 汇总收益、回撤、胜率等 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看按年指标 | 查看 annual performance 明细 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看模型对比 | 对比 baseline 与候选方案 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看回测摘要 | 查看 dataset evaluation 与 backtest 摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看滚动窗口结果 | 查看 walk-forward 窗口结果 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：历史页面

### 页面说明

负责查看历史版本、恢复历史版本、比较版本与研究归档。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 查看历史版本 | 查看历史策略迭代与研究归档 | 是 | `GET /api/sessions/{session_id}` / `GET /api/sessions/{session_id}/reports` | 是 | 正常 |
| 恢复预览 | 在恢复前预览版本参数 | 否 | 无 | 是 | 正常 |
| 恢复版本 | 将历史版本回填到当前实验参数 | 否 | 无 | 是 | 正常 |
| 版本对比 | 对比两版策略与研究差异 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看历史代码 | 查看归档版本代码 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：成果页面

### 页面说明

负责展示发布摘要、推荐代码、模型路由与 Programmer Agent 结果。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 查看发布摘要 | 查看研究发布与 gate 状态 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看推荐代码 | 查看推荐策略代码 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 执行 Programmer Agent | 按目标文件发起受限修改 | 是 | `POST /api/sessions/{session_id}/programmer/execute` | 是 | 部分正常 |
| 查看 Programmer 结果 | 查看失败类型、趋势、diff 与摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看 dry-run 说明 | 对扩展和终端 apply 的未提交模式给出说明 | 否 | 无 | 是 | 正常 |

## 页面：模拟

### 页面说明

负责模拟市场回放、自动按当前会话股票池加载行情、简化行为输入、行为画像与执行记录。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 初始化模拟市场 | 自动使用当前会话股票池的第一个标的加载日线与 5 分钟线数据，并初始化当前模拟时钟 | 是 | `POST /api/sessions/{session_id}/simulation/market/initialize` | 是 | 正常 |
| 按时间推进模拟 | 以固定 5 分钟 bar 为单位推进模拟时钟，并写入当前市场快照 | 是 | `POST /api/sessions/{session_id}/simulation/market/advance` | 是 | 正常 |
| 查看模拟日线与 5 分钟线 | 通过 session snapshot 查看当前模拟市场状态与图表数据 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 用户动作记录 | 用户只提交买入、卖出、不交易三种动作，后端自动补充当前市场上下文 | 是 | `POST /api/sessions/{session_id}/simulation/events` | 是 | 正常 |
| 完成模拟门禁 | 未初始化市场、未推进市场、或无用户动作时，后端拒绝生成画像 | 是 | `POST /api/sessions/{session_id}/simulation/complete` | 是 | 正常 |
| 完成模拟 | 生成 behavioral report | 是 | `POST /api/sessions/{session_id}/simulation/complete` | 是 | 正常 |
| 查看行为报告 | 查看用户与系统行为报告 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看交易记录 | 查看 trade records | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：偏好

### 页面说明

负责承接行为推荐并写入交易偏好。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 应用行为推荐 | 将行为测试推荐回填到 UI | 否 | 无 | 是 | 正常 |
| 保存交易偏好 | 写入交易频率、周期与理由 | 是 | `POST /api/sessions/{session_id}/trading-preferences` | 是 | 正常 |
| 查看交易偏好 | 查看当前偏好与冲突提示 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：报告

### 页面说明

负责汇总当前研究、归档报告、反馈记录与执行质量。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 查看当前研究结论 | 查看当前研究摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看报告归档 | 查看报告历史 | 是 | `GET /api/sessions/{session_id}/reports` | 是 | 正常 |
| 查看反馈记录 | 查看 strategy feedback log | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看执行质量 | 查看执行相关结果 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看 LLM 资源消耗统计 | 查看 token 使用、模型消耗与调用摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：数据源扩展

### 页面说明

负责在最小输入模式下生成数据源扩展方案。用户只需要提供 `API KEY` 和接口文档，后端会先用 LLM 对文档做结构化语义分析；当 LLM 不可用、调用失败或输出非法结构时，再回退到规则兜底分析。随后系统基于结构化 integration spec 生成 adapter、测试和 config 候选，并支持 dry-run 应用。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 最小输入扩展请求 | 接收 API KEY 和接口文档作为唯一必填输入 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 本地数据路径与格式提示 | 显示按类型拆分后的本地数据目录、文件命名规则、支持 JSON/CSV 格式和样例 | 否 | 无 | 是 | 正常 |
| 扩展结果本地保存 | 把数据源扩展 run 和 apply 结果写入本地 JSON 清单，不保存明文 API KEY | 是 | `POST /api/sessions/{session_id}/data-source/expand` / `POST /api/sessions/{session_id}/data-source/apply` | 是 | 正常 |
| 数据源扩展 smoke test | 对指定 run 执行 adapter 结构验证，并在提供 API KEY 时尝试 live fetch；对无效 API KEY、计费限制、权限不足、网络失败、文档/endpoint 不匹配做分类；结果写入本地 JSON 清单 | 是 | `POST /api/sessions/{session_id}/data-source/test` | 是 | 正常 |
| LLM 文档分析 | 使用 LLM 解析非结构化接口文档并生成结构化 integration spec | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 规则兜底分析 | 当 LLM 不可用或输出非法结构时执行规则兜底，并记录 fallback 原因 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 生成数据源扩展方案 | 基于结构化 integration spec 生成 adapter/module/test 草案 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 生成结果验证 | 对生成模块和测试做语法/结构验证并返回状态 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 查看扩展记录 | 查看 data source runs | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 应用数据源扩展 | 执行 apply；`commit_changes=false` 时为 dry-run | 是 | `POST /api/sessions/{session_id}/data-source/apply` | 是 | 正常 |

## 页面：运行

### 页面说明

负责把运行控制相关事件写入当前会话。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 生成场景 | 生成默认场景包 | 是 | `POST /api/sessions/{session_id}/generate-scenarios` | 是 | 正常 |
| 写入市场快照 | 写入 market snapshot | 是 | `POST /api/sessions/{session_id}/market-snapshots` | 是 | 正常 |
| 写入信息事件 | 写入 information events | 是 | `POST /api/sessions/{session_id}/information-events` | 是 | 正常 |
| 写入交易执行记录 | 写入 trade execution record | 是 | `POST /api/sessions/{session_id}/trade-executions` | 是 | 正常 |
| 更新部署模式 | 更新 execution mode | 是 | `POST /api/sessions/{session_id}/deployment` | 是 | 正常 |
| 查看运行历史 | 查看运行事件与监控结果 | 是 | `GET /api/sessions/{session_id}/history` / `GET /api/sessions/{session_id}/monitors` | 是 | 正常 |

## 页面：终端集成

### 页面说明

负责生成终端接入方案、运行 smoke test，并在安全模式下预演应用。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 生成终端接入方案 | 生成 terminal adapter 草案 | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 查看终端接入记录 | 查看 terminal integration runs | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 终端 smoke test | 执行接入健康检查 | 是 | `POST /api/sessions/{session_id}/terminal/test` | 是 | 正常 |
| 应用终端接入 | 执行 apply；`commit_changes=false` 时为 dry-run | 是 | `POST /api/sessions/{session_id}/terminal/apply` | 是 | 正常 |

## 页面：情报

### 页面说明

负责情报查询、批量股票查询和自动补查市场数据。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 单次情报查询 | 按查询词搜索情报 | 是 | `POST /api/sessions/{session_id}/intelligence/search` | 是 | 正常 |
| 批量股票情报查询 | 使用当前股票池批量查情报 | 是 | `POST /api/sessions/{session_id}/intelligence/search` | 是 | 正常 |
| 自动补查市场数据 | 自动补查财报、暗池、期权 | 是 | `POST /api/sessions/{session_id}/intelligence/financials` / `POST /api/sessions/{session_id}/intelligence/dark-pool` / `POST /api/sessions/{session_id}/intelligence/options` | 是 | 正常 |
| 查看历史情报 | 查看历史查询记录、详情和 JSON | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：健康

### 页面说明

负责展示系统健康、问题摘要和建议动作。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 自动加载健康数据 | 页面进入后自动拉取系统健康 | 是 | `GET /api/system-health` | 是 | 正常 |
| 刷新系统健康 | 手动刷新健康状态 | 是 | `GET /api/system-health` | 是 | 正常 |
| 查看异常模块/依赖/Agent | 查看系统异常列表 | 是 | `GET /api/system-health` | 是 | 正常 |
| 查看健康原始 JSON | 查看完整健康结构 | 是 | `GET /api/system-health` | 是 | 正常 |

## 当前联调结论

| 项目 | 说明 |
|---|---|
| 已补齐的历史缺口 | `配置 / 数据源扩展 / 终端集成 / 运行 / 训练参数校验 / 恢复预览` |
| 本地 API 状态 | `GET /api/system-health` 已恢复正常，本地开发态可用 |
| dry-run 语义 | `data-source/apply` 与 `terminal/apply` 在 `commit_changes=false` 时只做预演，不写仓库 |
| 数据源扩展目标模式 | 用户只提供 `API KEY + 接口文档`，系统先用 LLM 生成结构化 integration spec，再据此生成代码与测试；规则仅作为 fallback |
| 当前剩余事项 | 主要是视觉优化、信息层级优化和更高强度人工回归，不属于接口缺失 |
