# 策略训练页面数据获取说明

## 页面

策略训练页面

## 页面说明

本页面不是分别向多个后端接口零散取数，而是以一次策略训练请求为核心，训练完成后由后端返回最新的整份 `SessionSnapshot`。前端把这份快照保存到本地状态 `state.snapshot`，训练页面上的各个卡片和面板都从这份快照中读取对应字段。

训练页面的数据来源分为三层：

1. 前端输入层：用户在 `策略参数与目标` 子页面填写训练参数、目标函数、反馈、训练时间、用户策略方式、用户策略说明，以及当前策略下的单笔交易限制；策略公共配置不在其它策略子页面常驻显示，默认训练时间为 `2021-01-01` 到 `2025-12-31`。
2. 后端训练层：`/api/sessions/{session_id}/strategy/iterate` 执行策略迭代、评估、检查、研究总结和日志归档。
3. 策略启用层：`/api/sessions/{session_id}/strategy/active` 允许用户从当前版本和历史版本中选择一个策略，作为当前用于交易的策略版本。
4. 快照展示层：后端返回最新 `SessionSnapshot`，前端统一用 `refresh_all()` 渲染训练页面和结果页面。

## 功能表格

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 训练参数输入 | 用户填写策略类型、反馈、迭代模式、自动轮数、目标函数、目标值和训练时间 | 否 | 无 | 是 | 正常 |
| 用户策略方式输入 | 用户填写自己的策略方式，让训练保留原有策略思路 | 否 | 无 | 是 | 正常 |
| 用户策略说明输入 | 用户填写自己的策略说明、核心规则和约束 | 否 | 无 | 是 | 正常 |
| 单笔交易限制输入 | 用户填写单笔交易资金占比上限与金额上限 | 否 | 无 | 是 | 正常 |
| 默认训练时间初始化 | 页面初始默认训练开始为 `2021-01-01`，训练结束为 `2025-12-31` | 否 | 无 | 是 | 正常 |
| 训练参数前端校验 | 提交前校验时间范围、收益/胜率/回撤/最大亏损输入是否合法 | 否 | 无 | 是 | 正常 |
| 补齐训练前置条件 | 训练前自动确保交易标的、行为画像、偏好等基础上下文存在 | 是 | 内部串联多个 session 接口 | 是 | 正常 |
| 发起策略训练 | 将当前训练参数发送给策略迭代接口 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 选择当前交易策略 | 将用户选择的策略版本切换为当前交易策略 | 是 | `POST /api/sessions/{session_id}/strategy/active` | 是 | 正常 |
| 获取训练结果快照 | 训练完成后返回最新整份 `SessionSnapshot` | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 策略健康状态显示 | 显示当前交易策略的 `健康 / 观察 / 危险 / 失效` 状态 | 是 | `SessionSnapshot.strategy_status_summary.health_status` | 是 | 正常 |
| 策略当前状态显示 | 显示当前交易策略的 `开发中 / 测试中 / 验证中 / 正常` 状态 | 是 | `SessionSnapshot.strategy_status_summary.current_status` | 是 | 正常 |
| 交易限制状态显示 | 显示当前策略的交易限制状态与限制说明 | 是 | `SessionSnapshot.strategy_status_summary.trade_execution_limits` | 是 | 正常 |
| 检查结果显示 | 从快照中读取完整性检查与稳健性检查结果 | 是 | `SessionSnapshot.strategy_checks` | 是 | 正常 |
| 检查趋势显示 | 从训练日志中读取最近多轮失败类型和 gate 趋势 | 是 | `SessionSnapshot.strategy_training_log` | 是 | 正常 |
| 修复建议路由显示 | 基于训练日志、研究摘要、Programmer Agent 结果生成修复建议 | 是 | `SessionSnapshot.strategy_training_log` + `SessionSnapshot.programmer_runs` + `SessionSnapshot.strategy_package.research_summary` | 是 | 正常 |
| 研究结论显示 | 读取当前策略包中的研究摘要、最优版本、发布门和下一轮重点 | 是 | `SessionSnapshot.strategy_package.research_summary` | 是 | 正常 |
| 研究与编程联动显示 | 读取训练失败类型与编程失败类型并做联动摘要 | 是 | `SessionSnapshot.strategy_training_log` + `SessionSnapshot.programmer_runs` | 是 | 正常 |
| 训练日志显示 | 同时显示后端训练日志和前端本地提示日志 | 是 | `SessionSnapshot.strategy_training_log` | 是 | 正常 |
| 结果页模型绩效显示 | 读取推荐模型、基线模型、候选模型的评估结果 | 是 | `SessionSnapshot.strategy_package.recommended_variant` + `baseline_evaluation` + `candidate_variants` | 是 | 正常 |
| 历史恢复回填训练参数 | 从历史策略包读取参数并回填当前训练表单 | 是 | `SessionSnapshot.report_history` / `SessionSnapshot.strategy_training_log` / `SessionSnapshot.strategy_package` | 是 | 正常 |
| LLM 资源消耗显示 | 显示当前 session 的 token 使用和模型消耗摘要 | 是 | `SessionSnapshot.token_usage` | 是 | 正常 |

## 训练页面取数链路

### 1. 前端收集输入

训练页表单位于：

- [app.py](../src/sentinel_alpha/nicegui/app.py)

前端收集的主要字段有：

- `strategy_type`
- `strategy_feedback`
- `auto_iterations`
- `iteration_mode`
- `objective_metric`
- `strategy_method`
- `strategy_description`
- `target_return`
- `target_win_rate`
- `target_drawdown`
- `target_max_loss`
- `max_trade_allocation_pct`
- `max_trade_amount`
- `training_start`
- `training_end`

这些字段在点击“生成下一版策略”时，由 `run_strategy_iteration()` 组装成请求 payload。

### 2. 前端发起训练请求

请求入口：

- [app.py](../src/sentinel_alpha/nicegui/app.py)

调用接口：

- `POST /api/sessions/{session_id}/strategy/iterate`

### 2.1 真实历史数据自动补数

在真正开始策略训练前，后端会先检查当前股票池是否已经具备足够的真实历史数据。

- 如果本地 `market_data` 已经有足够历史数据，直接进入训练
- 如果本地数据不足，后端会自动优先复用当前会话里可用的 `market_data` 数据源扩展 run
- 如果没有可用扩展 run，后端会继续尝试当前已启用的内置真实 provider
- 自动补到的数据会写回本地 `data/local_market_data/market_data/{SYMBOL}_1d.csv`
- 如果自动补数仍然失败，训练会停止，并提示用户进入“数据源扩展”工作台提供 `API KEY + 接口文档`

请求体结构由：

- [schemas.py](../src/sentinel_alpha/api/schemas.py)

中的 `StrategyIterationRequest` 约束，字段包括：

- `feedback`
- `strategy_type`
- `strategy_method`
- `strategy_description`
- `auto_iterations`
- `iteration_mode`
- `objective_metric`
- `target_return_pct`
- `target_win_rate_pct`
- `target_drawdown_pct`
- `target_max_loss_pct`
- `max_trade_allocation_pct`
- `max_trade_amount`
- `training_start_date`
- `training_end_date`

### 3. API 执行策略迭代

API 入口：

- [app.py](../src/sentinel_alpha/api/app.py)

该入口不直接拼页面数据，而是把请求参数传给：

- [workflow_service.py](../src/sentinel_alpha/api/workflow_service.py)

中的 `iterate_strategy(...)`

后端训练过程会生成并写入以下 session 字段：

- `strategy_package`
- `strategy_checks`
- `strategy_training_log`
- `report_history`

### 4. API 返回整份 SessionSnapshot

训练完成后，API 通过 `snapshot(session_id)` 返回整份 `SessionSnapshot`，定义在：

- [schemas.py](../src/sentinel_alpha/api/schemas.py)

训练页真正依赖的核心快照字段是：

- `strategy_package`
- `strategy_checks`
- `strategy_training_log`
- `report_history`
- `programmer_runs`
- `token_usage`
- `active_trading_strategy`
- `strategy_status_summary`

### 5. 前端统一刷新页面

前端收到最新 `snapshot` 后，写入：

- `state.snapshot`

然后调用：

- `refresh_all()`

该函数负责把训练页、结果页、历史页等区域全部重新渲染。

## 训练页面各面板字段映射

| 页面区块 | 前端读取字段 | 后端生成来源 | 说明 |
|---|---|---|---|
| 当前训练状态 | `strategy_package` | `WorkflowService.iterate_strategy()` | 显示当前策略版本、目标函数、候选数、推荐版本等 |
| 当前交易限制 | `strategy_package.trade_execution_limits` + `strategy_status_summary` | `WorkflowService._normalize_trade_execution_limits()` + `_build_strategy_status_summary()` | 显示当前策略下的单笔交易限制 |
| 训练参数校验 | 前端输入框当前值 | 前端本地校验逻辑 | 不依赖后端快照，提交前即时生成 |
| 训练输入说明 | `strategy_package.input_manifest` | `WorkflowService._build_input_manifest()` | 展示输入数据协议、数据包、训练就绪度和策略数据需求 |
| 训练特征快照 | `strategy_package.feature_snapshot` | `WorkflowService._get_iteration_context()` | 展示当前训练使用的特征快照 |
| 输入数据包注册表 | `data_bundles` | `WorkflowService._register_data_bundle()` | 展示已注册的数据包与来源 |
| 策略包 | `strategy_package` | `WorkflowService.iterate_strategy()` | 展示完整策略包摘要 |
| 检查结果 | `strategy_checks` | `WorkflowService._run_strategy_checks()` | 展示 integrity / stress_overfit 结果 |
| 检查失败趋势 | `strategy_training_log[*]` | `WorkflowService.iterate_strategy()` | 展示最近多轮训练失败类型和 gate 趋势 |
| 修复建议路由 | `strategy_training_log` + `programmer_runs` + `strategy_package.research_summary` | `WorkflowService._build_unified_repair_route_summary()` + 前端 `_build_repair_routes()` | 汇总研究修复建议与编程修复失败类型 |
| 研究结论 | `strategy_package.research_summary` | `WorkflowService._build_research_summary()` + `_finalize_research_summary()` | 展示研究摘要、最优版本、送检目标、发布门、下一轮重点 |
| 研究与编程联动 | `strategy_training_log` + `programmer_runs` | 前端 `_research_code_loop_lines()` | 训练侧失败与编程侧失败的联动提示 |
| 训练日志 | `strategy_training_log` + `state.local_strategy_logs` | 后端训练日志 + 前端本地提示 | 同时包含后端正式日志与前端过程提示 |
| 模型绩效结果 | `strategy_package.recommended_variant.evaluation` / `baseline_evaluation` / `candidate_variants[*].evaluation` | `MetricsEngine` 评估结果经 `WorkflowService` 挂入策略包 | 结果页使用 |
| 历史恢复 | `report_history` / `strategy_training_log` / `strategy_package` | 历史归档 + 当前快照 | 恢复历史版本时回填输入参数 |
| LLM 资源消耗 | `token_usage` | `llm_runtime.usage_snapshot()` | 展示 session 当前模型资源消耗、按 Agent 统计和弱模型切换提示 |

## 训练页函数级映射

| 前端函数或面板 | 读取字段 | 后端生成位置 | 用途 |
|---|---|---|---|
| `refresh_all()` -> `当前策略概览` | `strategy_status_summary` + `active_trading_strategy` + `strategy_package` | `WorkflowService._build_strategy_status_summary()` + `_build_active_trading_strategy_payload()` + `iterate_strategy()` | 汇总策略健康状态、当前状态、交易限制和当前启用策略 |
| `refresh_all()` -> `提交前检查` | 当前输入框值 | 前端 `_strategy_input_validation_lines()` | 在提交前即时校验训练时间、目标值和交易限制输入 |
| `refresh_all()` -> `训练输入来源` | `strategy_package.input_manifest` | `WorkflowService._build_input_manifest()` | 展示训练数据协议、数据质量、来源链路和策略数据要求 |
| `refresh_all()` -> `训练特征摘要` | `strategy_package.feature_snapshot` | `WorkflowService._get_iteration_context()` | 展示行为、情报、财报、暗池、期权等特征快照 |
| `refresh_all()` -> `风险与质量检查` | `strategy_checks` | `WorkflowService._run_strategy_checks()` | 展示 integrity / stress_overfit 检查结果 |
| `refresh_all()` -> `问题变化趋势` | `strategy_training_log[*].failed_checks` + `research_summary.final_release_gate_summary` | `iterate_strategy()` | 展示最近几轮训练失败类型和 gate 变化 |
| `refresh_all()` -> `下一步修复建议` | `strategy_training_log` + `programmer_runs` + `strategy_package.research_summary` | `WorkflowService._build_unified_repair_route_summary()` + 前端 `_build_repair_routes()` | 汇总研究侧和代码侧修复动作 |
| `refresh_all()` -> `当前研究结论` | `strategy_package.research_summary` | `WorkflowService._build_research_summary()` + `_finalize_research_summary()` | 展示 winner、送检目标、稳健性、发布门、下一轮重点 |
| `refresh_all()` -> `研究与修复联动` | `strategy_training_log` + `programmer_runs` | 前端 `_research_code_loop_lines()` | 把训练侧失败与 Programmer 失败做联动提示 |
| `refresh_all()` -> `训练过程记录` | `strategy_training_log` + `state.local_strategy_logs` | `iterate_strategy()` + 前端本地提示 | 同时展示后端正式训练日志和前端过程提示 |
| `run_strategy_iteration()` | 当前表单输入 | `POST /api/sessions/{session_id}/strategy/iterate` | 发起训练、拿回最新 `SessionSnapshot` |
| `restore_version()` | `report_history[*].body.strategy_package` | 历史归档报告 | 把历史策略参数回填到当前训练表单 |

## 关键结论

策略训练页面现在采用的是“单次训练请求 + 整份快照回填”的取数模式，而不是每个卡片单独调用接口。

这意味着：

- 页面显示是否正确，核心取决于后端 `SessionSnapshot` 是否完整
- 如果训练页某个卡片没数据，优先检查 `snapshot` 对应字段是否存在，而不是先怀疑前端渲染
- 训练页、结果页、历史页之间的数据是一致的，因为它们都依赖同一份最新 session 快照

## 当前状态

训练页面的数据来源、快照结构、面板映射和函数级映射已经补齐，可直接用于后续联调、排障和回归测试。
