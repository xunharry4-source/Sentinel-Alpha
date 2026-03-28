# Sentinel-Alpha 页面与接口映射

以下文档从开发与联调视角整理当前 NiceGUI 页面和 FastAPI 接口的对应关系，方便按页面排查接口、做联调验收或补测试。

相关文案基线另见：
- `docs/ui-copy-baseline.md`
- `docs/ui-remaining-work-checklist.md`

基准实现：
- 前端：`src/sentinel_alpha/nicegui/app.py`
- 后端：`src/sentinel_alpha/api/app.py`

当前本地热更新开发链路：
- NiceGUI: `http://127.0.0.1:8010`
- API: `http://127.0.0.1:8001`
- API 健康检查: `http://127.0.0.1:8001/api/health`

## 页面：会话

### 页面说明

负责在页面打开后自动创建并加载默认会话，并支持手动切换已有会话，是其它页面的上下文入口。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 自动创建并加载默认会话 | 页面启动后自动创建新的工作会话并载入快照 | 是 | `POST /api/sessions` | 是 | 正常 |
| 手动新建默认会话 | 用户主动新建一个新的默认会话 | 是 | `POST /api/sessions` | 是 | 正常 |
| 切换到已有会话 | 加载已有会话快照 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看会话摘要 | 读取当前 session 的关键信息 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看会话 JSON | 读取完整快照结构 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：配置

### 页面说明

负责系统配置的读取、编辑、保存、备份与测试，并提供默认大模型配置和按 Agent 单独配置入口。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 加载配置 | 读取当前系统配置 payload 与 validation | 是 | `GET /api/config` | 是 | 正常 |
| 默认大模型配置 | 设置默认 provider、模型列表、temperature、max tokens，供未单独配置的 Agent 继承 | 是 | `GET /api/config` / `POST /api/config` | 是 | 正常 |
| Agent 专用模型配置 | 为选定 Agent 单独设置 provider、模型列表、temperature、max tokens | 是 | `GET /api/config` / `POST /api/config` | 是 | 正常 |
| 保存配置 | 保存编辑后的系统配置 | 是 | `POST /api/config` | 是 | 正常 |
| 配置自动备份 | 保存或测试配置前先备份当前 `settings.toml` | 是 | `POST /api/config` / `POST /api/config/test` / `POST /api/config/test-item` | 是 | 正常 |
| 全量配置测试 | 对配置做整体测试 | 是 | `POST /api/config/test` | 是 | 正常 |
| 单项配置测试 | 针对配置 family/provider 测试 | 是 | `POST /api/config/test-item` | 是 | 正常 |

## 页面：策略参数与目标

### 页面说明

负责训练前输入，包括股票池、目标函数、目标值和训练窗口。策略公共配置只在 `策略参数与目标` 子页面中显示，默认训练区间为 `2021-01-01` 到 `2025-12-31`。策略五个子页面各自拥有独立页头与说明卡。

当前前端呈现采用更面向用户的标题命名，主要包括 `当前策略概览`、`提交前检查`、`训练输入来源`、`训练特征摘要`、`交易策略启用`。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 提交交易标的 | 设置交易标的池 | 是 | `POST /api/sessions/{session_id}/trade-universe` | 是 | 正常 |
| 策略公共配置按子页显示 | 策略公共配置仅在 `策略参数与目标` 子页面内渲染 | 否 | 无 | 是 | 正常 |
| 默认训练时间 | 页面默认训练开始为 `2021-01-01`，训练结束为 `2025-12-31` | 否 | 无 | 是 | 正常 |
| 训练参数校验 | 前端校验训练窗口和目标值是否合法 | 否 | 无 | 是 | 正常 |
| 发起策略迭代 | 提交训练参数并触发一轮或多轮训练 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 输入用户策略方式 | 提交用户自己的策略方式，用于驱动训练分析 | 否 | 无 | 是 | 正常 |
| 输入用户策略说明 | 提交用户自己的策略说明、约束和核心规则 | 否 | 无 | 是 | 正常 |
| 输入交易金额限制 | 提交单笔交易资金占比上限和单笔交易金额上限 | 否 | 无 | 是 | 正常 |
| 策略数据需求阻断 | 根据策略方式判断必需数据，不足时由后端直接阻断训练并返回补数说明 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 选择当前交易策略 | 在当前版本和历史版本之间切换当前用于交易的策略 | 是 | `POST /api/sessions/{session_id}/strategy/active` | 是 | 正常 |
| 查看策略健康状态 | 读取当前交易策略的健康状态与原因 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看策略当前状态 | 读取当前交易策略的生命周期状态与原因 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看交易限制状态 | 读取当前策略的交易限制状态、限制模式和限制说明 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看当前策略状态 | 查看策略包、特征快照、输入数据包等 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：训练页面

### 页面说明

负责训练过程控制、反馈回填、人工介入、风险与质量检查，以及下一步修复建议展示，并以独立页头说明当前子页面用途。

当前前端呈现采用更面向用户的标题命名，主要包括 `风险与质量检查`、`问题变化趋势`、`下一步修复建议`、`当前研究结论`、`研究与修复联动`、`训练过程记录`。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 继续自动训练 | 延续自动迭代模式继续训练 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 我来介入后再训练 | 切换到人工反馈模式 | 否 | 无 | 是 | 正常 |
| 确认当前策略 | 将当前策略设为确认状态 | 是 | `POST /api/sessions/{session_id}/strategy/approve` | 是 | 正常 |
| 查看策略检查 | 查看完整性、压测、过拟合检查 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看训练日志 | 查看训练过程和本地联动日志，并显示本轮结论、下一步、策略方式和数据要求摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：结果页面

### 页面说明

负责展示训练输出的总计指标、按年指标、回测摘要和滚动检验结果，并以独立页头说明当前子页面用途。

当前前端呈现采用更面向用户的标题命名，主要包括 `策略模型表现`、`方案对比`、`回测摘要`、`滚动检验结果`、`研究趋势`、`结果健康结论`。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 查看模型总计指标 | 查看 full period 汇总收益、回撤、胜率等 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看按年指标 | 查看 annual performance 明细 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看模型对比 | 对比 baseline 与候选方案 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看回测摘要 | 查看 dataset evaluation 与 backtest 摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看滚动窗口结果 | 查看 walk-forward 窗口结果 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：历史页面

### 页面说明

负责查看历史版本、恢复前预览、差异对比与研究详情，并以独立页头说明当前子页面用途。

当前前端呈现采用更面向用户的标题命名，主要包括 `版本时间线`、`历史归档`、`差异对比`、`恢复前预览`、`研究对比`、`研究详情`、`失败原因变化`。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 查看历史版本 | 查看历史策略迭代与研究归档 | 是 | `GET /api/sessions/{session_id}` / `GET /api/sessions/{session_id}/reports` | 是 | 正常 |
| 恢复预览 | 在恢复前预览版本参数 | 否 | 无 | 是 | 正常 |
| 恢复版本 | 将历史版本回填到当前实验参数 | 否 | 无 | 是 | 正常 |
| 版本对比 | 对比两版策略与研究差异 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看历史代码 | 查看归档版本代码 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：成果页面

### 页面说明

负责展示发布结论、当前推荐代码、模型选择、LLM 资源消耗与 Programmer Agent 结果，并以独立页头说明当前子页面用途。

当前前端呈现采用更面向用户的标题命名，主要包括 `发布结论`、`关键分析`、`当前推荐代码`、`模型选择与路由`、`本轮 LLM 资源消耗`、`Programmer Agent 执行记录`。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 查看发布摘要 | 查看研究发布与 gate 状态 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看推荐代码 | 查看推荐策略代码 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 执行 Programmer Agent | 按目标文件发起受限修改，并展示 dry-run、边界拦截、修复链路和接受/回退建议 | 是 | `POST /api/sessions/{session_id}/programmer/execute` | 是 | 正常 |
| 查看 Programmer 结果 | 查看失败类型、趋势、diff 与摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看 dry-run 说明 | 对扩展和终端 apply 的未提交模式给出说明 | 否 | 无 | 是 | 正常 |

## 页面：模拟

### 页面说明

负责模拟市场回放、自动按当前会话股票池加载行情、简化行为输入、自动行为捕获、行为画像与执行记录。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 初始化模拟市场 | 自动使用当前会话股票池的第一个标的加载日线与 5 分钟线数据，并初始化当前模拟时钟 | 是 | `POST /api/sessions/{session_id}/simulation/market/initialize` | 是 | 正常 |
| 按时间推进模拟 | 以固定 5 分钟 bar 为单位推进模拟时钟，并写入当前市场快照 | 是 | `POST /api/sessions/{session_id}/simulation/market/advance` | 是 | 正常 |
| 查看模拟日线与 5 分钟线 | 通过 session snapshot 查看当前模拟市场状态与图表数据 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 用户动作记录 | 用户只提交买入、卖出、不交易三种动作，后端自动补充当前市场上下文 | 是 | `POST /api/sessions/{session_id}/simulation/events` | 是 | 正常 |
| 行为捕获层 | 前端自动随动作提交盯盘时长、亏损下刷新次数与触发回撤点；后端再结合真实交易记录推导手动干预自动化与信任衰减 | 是 | `POST /api/sessions/{session_id}/simulation/events` / `POST /api/sessions/{session_id}/trade-executions` / `GET /api/sessions/{session_id}` | 是 | 正常 |
| 完成模拟门禁 | 未初始化市场、未推进市场、或无用户动作时，后端拒绝生成画像 | 是 | `POST /api/sessions/{session_id}/simulation/complete` | 是 | 正常 |
| 完成模拟 | 生成 behavioral report | 是 | `POST /api/sessions/{session_id}/simulation/complete` | 是 | 正常 |
| 查看模拟训练状态 | 读取 `simulation_training_state`，显示当前是否建议重训练模拟 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 基于新增行为重新训练模拟 | 基于新增行为样本重新生成模拟画像和行为基线 | 是 | `POST /api/sessions/{session_id}/simulation/retrain` | 是 | 正常 |
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

## 页面：习惯与目标

### 页面说明

负责把行为测试、偏好、训练反馈、真实交易、行为捕获信号和当前策略状态聚合成统一的习惯与目标演化分析，并展示时间线。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 查看当前习惯与目标结论 | 读取 `habit_goal_evolution.current`，显示综合结论、习惯判断、目标判断、当前重点和交易限制，并纳入历史情报搜索行为与模拟训练建议 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看行为捕获摘要 | 读取 `habit_goal_evolution.current.behavior_capture_summary`，显示盯盘时长、焦虑刷新、手动干预和信任衰减 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看风险、冲突与下一步 | 读取 `habit_goal_evolution.current.risk_flags / next_actions / required_user_inputs` | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看最近变化 | 读取 `habit_goal_evolution.current.habit_shift / goal_shift` | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看演化时间线 | 读取 `habit_goal_evolution.history`，按事件源展示演化记录 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| LLM 习惯与目标演化分析 | 后端调用 `habit_goal_evolution_analysis` 任务，并在失败时回退规则分析 | 是 | `GET /api/sessions/{session_id}` 读取结果；由后端状态变更时自动刷新 | 是 | 正常 |
| 查看原始演化数据 | 查看 `habit_goal_evolution` 原始 JSON | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

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
| 查看按 Agent 的 LLM 统计 | 读取 `token_usage.by_agent`，展示每个 Agent 的调用次数、token、fallback 比率和模型列表 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看弱模型切换提示 | 读取 `token_usage.model_switch_recommendations`，提示哪些 Agent 需要换更强或更稳定的模型 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：数据源扩展

### 页面说明

负责在最小输入模式下生成数据源扩展方案。用户只需要提供 `API KEY` 和接口文档，后端会先用 LLM 对文档做结构化语义分析；当 LLM 不可用、调用失败或输出非法结构时，再回退到规则兜底分析。随后系统基于结构化 integration spec 生成 adapter、测试和 config 候选，并支持 dry-run 应用。策略训练缺少真实历史数据时，会自动优先复用当前会话里可用的 `market_data` 扩展 run 或已启用 provider 补抓缺失数据并写回本地 `market_data` 目录。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 最小输入扩展请求 | 接收 API KEY 和接口文档作为唯一必填输入 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 数据源健康检查 | 汇总当前 session 的扩展 run 健康状态和当前配置的数据源健康状态，并返回 `conclusion / notes / next_actions` 供页面优先展示人类化结论 | 是 | `GET /api/sessions/{session_id}/data-source/health` | 是 | 正常 |
| 已配置数据源管理表格 | 不依赖 session 查看当前配置文件中的数据源健康和校验结果，并以表格方式展示 provider、状态、启用情况、API KEY 状态、Base URL 和说明 | 是 | `GET /api/data-source/health` | 是 | 正常 |
| 本地数据路径与格式提示 | 显示按类型拆分后的本地数据目录、文件命名规则、支持 JSON/CSV 格式和样例 | 否 | 无 | 是 | 正常 |
| 扩展结果本地保存 | 把数据源扩展 run 和 apply 结果写入本地 JSON 清单，不保存明文 API KEY | 是 | `POST /api/sessions/{session_id}/data-source/expand` / `POST /api/sessions/{session_id}/data-source/apply` | 是 | 正常 |
| 数据源扩展 smoke test | 对指定 run 执行 adapter 结构验证，并在提供 API KEY 时尝试 live fetch；对无效 API KEY、计费限制、权限不足、网络失败、文档/endpoint 不匹配做分类；结果写入本地 JSON 清单 | 是 | `POST /api/sessions/{session_id}/data-source/test` | 是 | 正常 |
| 训练自动补数 | 训练前检查真实历史数据覆盖；不足时优先复用会话内可用的 `market_data` 扩展 run 或已启用 provider 自动补抓 `1d` 历史数据并写入本地文件 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| LLM 文档分析 | 使用 LLM 解析非结构化接口文档并生成结构化 integration spec | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 规则兜底分析 | 当 LLM 不可用或输出非法结构时执行规则兜底，并记录 fallback 原因 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 生成数据源扩展方案 | 基于结构化 integration spec 生成 adapter/module/test 草案 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 生成结果验证 | 对生成模块和测试做语法/结构验证并返回状态 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 查看扩展记录 | 查看 data source runs | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 更新扩展数据源 | 对指定 run 重新分析接口文档并更新生成结果 | 是 | `POST /api/sessions/{session_id}/data-source/update` | 是 | 正常 |
| 删除扩展数据源 | 删除指定 run | 是 | `POST /api/sessions/{session_id}/data-source/delete` | 是 | 正常 |
| 应用数据源扩展 | 执行 apply；`commit_changes=false` 时为 dry-run | 是 | `POST /api/sessions/{session_id}/data-source/apply` | 是 | 正常 |
| 保存已配置数据源 | 保存或新增配置文件中的 provider 设置 | 是 | `POST /api/config/data-source/provider` | 是 | 正常 |
| 删除已配置数据源 | 从配置文件中删除 provider 设置 | 是 | `POST /api/config/data-source/provider/delete` | 是 | 正常 |

## 页面：交易运行

### 页面说明

负责以更接近交易工作流的方式，把当天交易准备、市场状态、消息记录、交易记录和执行方式写入当前会话，并展示最近运行记录与提醒。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 当前运行状态 | 从 session snapshot 汇总执行方式、当前策略、股票池、最近交易和最近消息 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 准备今日交易场景 | 生成默认场景包 | 是 | `POST /api/sessions/{session_id}/generate-scenarios` | 是 | 正常 |
| 保存当前执行方式 | 更新 execution mode | 是 | `POST /api/sessions/{session_id}/deployment` | 是 | 正常 |
| 保存市场状态 | 写入 market snapshot；前端会自动补 `source=manual_ui` 并根据当前价格推导开收盘价 | 是 | `POST /api/sessions/{session_id}/market-snapshots` | 是 | 正常 |
| 保存消息记录 | 写入 information events；前端自动补默认 source，并把标题和内容整理成结构化消息 | 是 | `POST /api/sessions/{session_id}/information-events` | 是 | 正常 |
| 保存交易记录 | 写入 trade execution record；前端自动计算 notional，并优先带入当前交易策略版本 | 是 | `POST /api/sessions/{session_id}/trade-executions` | 是 | 正常 |
| 最近运行记录与提醒 | 查看运行事件与监控结果 | 是 | `GET /api/sessions/{session_id}/history` / `GET /api/sessions/{session_id}/monitors` | 是 | 正常 |

## 页面：交易终端接入

### 页面说明

负责在最小输入模式下生成交易终端接入方案。用户只需要提供 `API KEY` 和技术文档，后端会先用 LLM 对技术文档做结构化分析，再生成接入代码、测试代码，并判断自动交易必需能力与可选能力的缺口。当前只支持单交易所/单账户接入，并在结果里保留多交易所扩展缺口。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 最小输入接入请求 | 接收 API KEY 和技术文档作为主要输入 | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| LLM 技术文档分析 | 使用 LLM 解析非结构化技术文档并生成结构化终端接入规范 | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 必需能力判定 | 判定 `place_order / order_status / positions / balances` 是否齐备，并输出 `automatic_trading_ready` | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 可选能力判定 | 判定 `cancel_order / trade_records` 是否齐备，并输出 warning 或下一步建议 | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 生成交易终端接入方案 | 基于结构化规范生成 terminal adapter 草案 | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 查看交易终端接入记录 | 查看 terminal integration runs | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 更新交易终端接入 | 用新的技术文档更新指定 run 的接入结果 | 是 | `POST /api/sessions/{session_id}/terminal/update` | 是 | 正常 |
| 删除交易终端接入 | 删除指定交易终端接入 run | 是 | `POST /api/sessions/{session_id}/terminal/delete` | 是 | 正常 |
| 查看单交易所范围说明 | 读取当前 run 的 `exchange_support_summary`，确认当前只支持单交易所并暴露多交易所扩展缺口 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 交易终端接入 smoke test | 执行接入健康检查，并验证必需/可选能力与核心返回结构 | 是 | `POST /api/sessions/{session_id}/terminal/test` | 是 | 正常 |
| 应用交易终端接入 | 执行 apply；`commit_changes=false` 时为 dry-run | 是 | `POST /api/sessions/{session_id}/terminal/apply` | 是 | 正常 |

## 页面：情报

### 页面说明

负责情报查询、批量股票查询和自动补查市场数据。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 单次情报查询 | 按查询词搜索情报 | 是 | `POST /api/sessions/{session_id}/intelligence/search` | 是 | 正常 |
| 批量股票情报查询 | 使用当前股票池批量查情报 | 是 | `POST /api/sessions/{session_id}/intelligence/search` | 是 | 正常 |
| 情报查询行为捕获 | 每次情报搜索后更新查询次数、是否频繁查询、重复搜索比例和短时间高频搜索比例，并回写到 session | 是 | `POST /api/sessions/{session_id}/intelligence/search` | 是 | 正常 |
| 历史情报行为分析 | 读取 `intelligence_history_analysis`，展示是否频繁查询、是否重复搜索、是否存在同一主题反复确认或短时再次确认，以及是否建议先做模拟测试或重训模拟 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 自动补查市场数据 | 自动补查财报、暗池、期权 | 是 | `POST /api/sessions/{session_id}/intelligence/financials` / `POST /api/sessions/{session_id}/intelligence/dark-pool` / `POST /api/sessions/{session_id}/intelligence/options` | 是 | 正常 |
| 查看历史情报 | 查看历史查询记录、详情和 JSON | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 查看 Agent 原子日志 | 查看当前 session 下所有 Agent 操作的原子步骤日志，包括情报批量查询、自动补查市场数据及其他 Agent 运行步骤，避免用户误判系统卡死 | 是 | `GET /api/sessions/{session_id}/agent-activity` | 是 | 正常 |

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
| 已补齐的历史缺口 | `配置 / 数据源扩展 / 交易终端接入 / 运行 / 训练参数校验 / 恢复预览` |
| 本地 API 状态 | `GET /api/system-health` 已恢复正常，本地开发态可用 |
| dry-run 语义 | `data-source/apply` 与 `terminal/apply` 在 `commit_changes=false` 时只做预演，不写仓库 |
| 数据源扩展目标模式 | 用户只提供 `API KEY + 接口文档`，系统先用 LLM 生成结构化 integration spec，再据此生成代码与测试；规则仅作为 fallback |
| 当前剩余事项 | 主要是视觉优化、信息层级优化和更高强度人工回归，不属于接口缺失 |
