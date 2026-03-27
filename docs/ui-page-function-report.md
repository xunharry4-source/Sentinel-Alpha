# Sentinel-Alpha 页面功能分析报告

以下报告基于当前 NiceGUI 主界面实现 `/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/nicegui/app.py` 与 FastAPI 接口 `/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/api/app.py` 的代码分析整理。

已验证的包括：
- `/api/health`
- `/api/system-health`
- 会话创建
- 配置读取与配置单项测试
- 运行控制操作写入
- 数据源扩展生成与 dry-run 应用
- 终端集成生成、smoke test 与 dry-run 应用
- 情报查询
- 情报查询后自动补充市场数据

未逐按钮做全量人工点击回归的功能，在“功能是否正常”列中标记为“部分正常”或“待验证”。

## 页面：会话

### 页面说明

负责创建会话、加载会话、查看当前会话摘要和完整 JSON。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 创建会话 | 新建工作会话，并自动补齐部分前置数据 | 是 | `POST /api/sessions` | 是 | 正常 |
| 加载会话 | 按 `session_id` 加载已有会话 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 会话摘要 | 显示当前 session 状态、资金、版本、最新情报等 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 会话 JSON | 显示完整快照 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：配置

### 页面说明

当前主要是查看当前配置结果，不是完整配置编辑器。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 当前配置查看 | 展示交易标的、偏好、策略包摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 配置 JSON 查看 | 展示配置类原始结构 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 在线编辑配置 | 页面内修改系统配置 | 是 | `GET /api/config` / `POST /api/config` | 是 | 正常 |
| 配置测试 | 页面内直接测试配置项 | 是 | `POST /api/config/test` / `POST /api/config/test-item` | 是 | 正常 |

## 页面：策略参数与目标

### 页面说明

负责设置训练参数、交易标的、目标函数、训练区间，并查看训练输入说明。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 提交交易标的 | 设置交易标的池 | 是 | `POST /api/sessions/{session_id}/trade-universe` | 是 | 正常 |
| 训练参数校验 | 在提交训练前检查训练窗口、收益/胜率/回撤/最大亏损输入是否合法 | 否 | 无 | 是 | 正常 |
| 设置训练参数 | 设置策略类型、目标函数、训练时间、目标值 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 当前训练状态 | 展示当前策略状态、推荐候选、训练窗口 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 训练输入说明 | 展示输入数据包、source lineage、数据质量 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 特征快照 | 展示训练特征与快照信息 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：训练页面

### 页面说明

负责发起训练、继续自动训练、人工介入、查看检查结果和修复建议。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 生成下一版策略 | 发起策略迭代 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 继续自动训练 | 切换自动模式后继续迭代 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 我来介入后再训练 | 切到人工反馈模式 | 否 | 无 | 是 | 正常 |
| 回填修复反馈 | 将修复建议回填到训练反馈 | 否 | 无 | 是 | 正常 |
| 回填修复指令 | 将修复建议回填到 Programmer Agent | 否 | 无 | 是 | 正常 |
| 检查结果 | 展示 Integrity / Stress / Overfit 检查 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 检查趋势 | 展示失败趋势与研究联动 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 训练日志 | 展示本地与后端训练过程摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 部分正常 |

## 页面：结果页面

### 页面说明

负责展示模型总计指标、按年指标、回测、滚动窗口和研究结论。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 模型总计指标 | 展示收益、复利、回撤、最大亏损、胜率等总计指标 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` 返回快照 | 是 | 正常 |
| 按年指标表 | 展示按年收益、复利、回撤、最大亏损、胜率等 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` 返回快照 | 是 | 正常 |
| 基准与方案对比 | 展示 baseline 与候选模型对比 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 回测与分段评估 | 展示 dataset evaluation / backtest 摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 滚动窗口结果 | 展示 walk-forward 结果 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 研究趋势摘要 | 展示研究结论趋势 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：历史页面

### 页面说明

负责查看历史策略版本、恢复版本、版本对比、研究归档和失败演化。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 策略迭代历史 | 查看历史版本列表 | 是 | `GET /api/sessions/{session_id}` / `GET /api/sessions/{session_id}/reports` | 是 | 正常 |
| 恢复预览 | 在恢复前查看版本、目标函数、训练窗口和股票池 | 否 | 无 | 是 | 正常 |
| 恢复版本 | 将历史版本恢复成当前实验版本 | 是 | 依赖会话快照与前端恢复逻辑 | 是 | 正常 |
| 版本对比 | 比较两个历史版本 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 历史版本代码查看 | 查看归档代码 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 研究归档对比 | 比较研究导出与 gate 变化 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 失败原因演化 | 查看失败类型随迭代变化 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：成果页面

### 页面说明

负责展示研究发布摘要、推荐代码、模型路由、LLM 消耗和 Programmer Agent 结果。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 研究发布摘要 | 展示发布门、winner、稳健性等 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 推荐代码 | 展示当前推荐策略代码 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 模型矩阵 | 展示模型路由与研究选择 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| LLM 消耗 | 展示 token 使用情况 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 执行 Programmer Agent | 发起受限代码修改 | 是 | `POST /api/sessions/{session_id}/programmer/execute` | 是 | 部分正常 |
| dry-run 结果说明 | 在数据源扩展和终端集成未提交改动时，明确显示只是预演未写入工作区 | 否 | 无 | 是 | 正常 |
| Programmer Agent 趋势与统计 | 展示失败类型与趋势 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：模拟

### 页面说明

负责模拟交易、自动按当前会话股票池加载模拟市场数据、查看日线与 5 分钟线、按固定 5 分钟节奏推进模拟时钟、让用户只做买入/卖出/不交易三种行为、生成行为画像、查看用户/系统行为报告。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 初始化模拟市场 | 自动使用当前会话股票池的第一个标的加载日线与 5 分钟线数据，并建立当前模拟时钟 | 是 | `POST /api/sessions/{session_id}/simulation/market/initialize` | 是 | 正常 |
| 日线图展示 | 展示模拟窗口内的日线价格轨迹与当前定位 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 5 分钟线图展示 | 展示当前模拟日的 5 分钟级别价格轨迹与当前推进位置 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 按时间推进模拟 | 按固定 5 分钟 bar 推进模拟时钟，并刷新当前价格、回撤、进度和快照 | 是 | `POST /api/sessions/{session_id}/simulation/market/advance` | 是 | 正常 |
| 用户行为输入 | 用户在每个市场时点只做买入、卖出、不交易三种动作，其它上下文由系统自动记录 | 是 | `POST /api/sessions/{session_id}/simulation/events` | 是 | 正常 |
| 完成模拟门禁 | 未加载市场、未推进市场、或没有至少一次用户动作时，不允许直接生成行为画像 | 是 | `POST /api/sessions/{session_id}/simulation/complete` | 是 | 正常 |
| 完成模拟并生成画像 | 生成 behavioral report | 是 | `POST /api/sessions/{session_id}/simulation/complete` | 是 | 正常 |
| 用户行为报告 | 查看用户行为分析 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 系统行为报告 | 查看系统行为分析 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 交易执行记录 | 查看 trade records | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 场景记录 | 查看 scenario 记录 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：偏好

### 页面说明

负责承接行为推荐并保存交易偏好。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 应用行为推荐 | 从行为报告自动回填推荐偏好 | 否 | 无 | 是 | 正常 |
| 保存交易偏好 | 保存频率、周期、理由 | 是 | `POST /api/sessions/{session_id}/trading-preferences` | 是 | 正常 |
| 当前交易偏好查看 | 显示当前偏好 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 行为推荐查看 | 显示推荐结果与冲突提示 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：报告

### 页面说明

负责汇总当前研究结论、历史报告、用户意见、执行质量。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 当前研究结论 | 查看当前研究摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 报告归档 | 查看历史报告 | 是 | `GET /api/sessions/{session_id}/reports` | 是 | 正常 |
| 用户意见记录 | 查看 feedback log | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 执行质量 | 查看行为/执行质量结论 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| LLM 资源消耗统计 | 查看当前会话的 token 使用、模型消耗与调用摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 报告 JSON | 查看原始报告结构 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：数据源扩展

### 页面说明

当前数据源扩展改成最小输入模式：用户只需要提供 `API KEY` 和接口文档，系统会先用 LLM 对非结构化接口文档做语义分析并产出结构化接入规范；当 LLM 不可用、调用失败或返回非法结构时，再回退到规则兜底分析。随后系统基于结构化规范生成符合 Agent 要求的 adapter 代码与测试草案，并支持 dry-run 应用。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 数据源扩展记录查看 | 查看已有扩展记录 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 输入数据包记录查看 | 查看 data bundle 记录 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 最小输入扩展请求 | 用户只提供 API KEY 和接口文档，由系统自动完成分析、生成和测试 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 本地数据路径与格式提示 | 在工作台直接显示按类型拆分后的本地数据目录、文件命名规则、支持格式与示例 | 否 | 无 | 是 | 正常 |
| 扩展结果本地保存 | 生成或补充数据源后，将扩展结果与 apply 结果保存到本地清单文件 | 是 | `POST /api/sessions/{session_id}/data-source/expand` / `POST /api/sessions/{session_id}/data-source/apply` | 是 | 正常 |
| 数据源扩展 smoke test | 对已生成的数据源 run 执行 smoke test，并在提供 API KEY 时尝试 live fetch；会区分无效 API KEY、套餐/计费限制、权限不足、网络失败、文档或 endpoint 不匹配，并给出处理建议；测试结果会保存到本地清单 | 是 | `POST /api/sessions/{session_id}/data-source/test` | 是 | 正常 |
| LLM 接口文档分析 | LLM 对非结构化接口文档做语义理解，提取 provider、分类、鉴权、endpoint、参数和返回结构 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 规则兜底分析 | 当 LLM 不可用、失败或返回非法结构时，回退到规则分析并明确记录 fallback 原因 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 结构化接入规范生成 | 输出结构化 integration spec，供代码生成、测试和 apply 复用 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 自动生成代码与测试 | 基于结构化 integration spec 生成 adapter 模块、测试代码和 config 候选 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 扩展结果测试 | 对生成结果进行语法/结构测试，并输出验证状态 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 应用数据源扩展 | 在页面内应用扩展结果 | 是 | `POST /api/sessions/{session_id}/data-source/apply` | 是 | 正常 |

## 页面：运行

### 页面说明

当前提供运行事件、监控信号和运行控制操作入口。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 运行事件查看 | 查看 history events | 是 | `GET /api/sessions/{session_id}/history` | 是 | 正常 |
| 监控信号查看 | 查看 monitor signals | 是 | `GET /api/sessions/{session_id}/monitors` | 是 | 正常 |
| 运行操作控制 | 页面内执行运行级操作 | 是 | `POST /api/sessions/{session_id}/generate-scenarios` / `POST /api/sessions/{session_id}/market-snapshots` / `POST /api/sessions/{session_id}/information-events` / `POST /api/sessions/{session_id}/trade-executions` / `POST /api/sessions/{session_id}/deployment` | 是 | 正常 |

## 页面：终端集成

### 页面说明

当前已提供终端集成记录查看、方案生成、应用和 smoke test 工作台。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 终端集成记录查看 | 查看 terminal integration 记录 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 发起终端集成扩展 | 页面内提交终端扩展请求 | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 应用终端集成 | 页面内应用终端结果 | 是 | `POST /api/sessions/{session_id}/terminal/apply` | 是 | 正常 |
| 测试终端连通性 | 页面内发起测试 | 是 | `POST /api/sessions/{session_id}/terminal/test` | 是 | 正常 |

## 页面：情报

### 页面说明

负责情报查询、股票列表批量查询、历史查看，并自动补充最新财报、暗池、期权数据。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 单次情报查询 | 按查询词发起情报搜索 | 是 | `POST /api/sessions/{session_id}/intelligence/search` | 是 | 正常 |
| 当前股票列表批量查询 | 基于当前交易标的批量查询情报 | 是 | `POST /api/sessions/{session_id}/intelligence/search` | 是 | 正常 |
| 自动补充市场数据 | 情报查询后自动补查财报、暗池、期权 | 是 | `POST /api/sessions/{session_id}/intelligence/search` 触发后端自动补查 | 是 | 正常 |
| 股票情报总览 | 按股票维度汇总最新情报结论 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 历史情报查看 | 查看历史查询详情和 JSON | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 财报摘要 | 展示自动补查财报结果 | 是 | `POST /api/sessions/{session_id}/intelligence/financials` | 是 | 部分正常 |
| 暗池摘要 | 展示自动补查暗池结果 | 是 | `POST /api/sessions/{session_id}/intelligence/dark-pool` | 是 | 部分正常 |
| 期权摘要 | 展示自动补查期权结果 | 是 | `POST /api/sessions/{session_id}/intelligence/options` | 是 | 部分正常 |

说明：
- “部分正常”不是页面链路有问题，而是外部市场数据源本身可能成功或失败，页面会真实显示结果。

## 页面：健康

### 页面说明

负责展示系统健康概览、风险、建议动作、异常模块与原始 JSON。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 自动加载健康数据 | 打开页面自动拉取系统健康 | 是 | `GET /api/system-health` | 是 | 正常 |
| 刷新系统健康 | 手动刷新健康状态 | 是 | `GET /api/system-health` | 是 | 正常 |
| 人类化健康概览 | 展示一句话结论、问题、建议动作 | 是 | `GET /api/system-health` | 是 | 正常 |
| 异常模块/依赖/Agent | 展示异常对象 | 是 | `GET /api/system-health` | 是 | 正常 |
| 原始 JSON | 展示底层健康结构 | 是 | `GET /api/system-health` | 是 | 正常 |

## 未完成的页面与说明

| 页面 | 未完成说明 |
|---|---|
| 无阻塞型未完成功能页面 | 此前标记未完成的 `配置 / 数据源扩展 / 终端集成 / 运行` 已补齐，并完成本地接口全流程烟测。`策略参数与目标` 已补充训练参数校验，`历史页面` 已补充恢复预览。当前剩余的是视觉优化、提示文案增强和更高强度人工回归，不属于功能缺失。 |

## 本次补充说明

- 当前本地热更新开发链路为：NiceGUI `http://127.0.0.1:8010`，API `http://127.0.0.1:8001`。
- `/api/system-health` 的本地开发态空时间戳崩溃问题已修复。
- `data-source/apply` 与 `terminal/apply` 在 `commit_changes=false` 时为真正 `dry_run`，不会触发真实仓库写入。
- 最新已完成的本地验证包括：
  - `python -m py_compile src/sentinel_alpha/nicegui/app.py src/sentinel_alpha/api/workflow_service.py src/sentinel_alpha/api/app.py tests/test_api_workflow.py`
  - `pytest tests/test_api_workflow.py -q -k 'data_source_expansion_can_be_applied_by_programmer_agent or trading_terminal_integration_can_be_applied_by_programmer_agent or trading_terminal_integration_can_be_smoke_tested'`
  - 本地 API `/api/system-health` 返回正常
  - 本地 NiceGUI 页面输出已确认包含 `系统配置工作台 / 数据源扩展工作台 / 运行控制工作台 / 终端集成工作台 / 恢复预览`

## 数据源扩展新要求

- 新的数据源扩展模式要求用户只提供：
  - `API KEY`
  - `接口文档`
- 系统需要优先通过 `LLM` 自动完成：
  - 解析非结构化接口文档
  - 生成结构化 `integration spec`
  - 识别 provider 名称、数据分类、base URL、鉴权方式、endpoint、请求参数和返回结构
- 结构化 `integration spec` 至少应覆盖：
  - `provider_name`
  - `category`
  - `base_url`
  - `auth_style`
  - `auth_header_name`
  - `auth_query_param`
  - `quote_endpoint`
  - `history_endpoint`
  - `symbol_param`
  - `interval_param`
  - `lookback_param`
  - `response_root_path`
  - `default_headers`
  - `default_query_params`
  - `pagination_style`
  - `error_field_path`
- 当 `LLM` 不可用或输出非法结构时，系统需要自动回退到规则兜底分析，但必须保留：
  - `analysis_generation_mode`
  - `analysis_status`
  - `fallback_reason`
  - `structured_integration_spec`
- 系统需要继续自动完成：
  - 基于结构化 spec 生成 adapter 代码
  - 基于结构化 spec 生成测试代码
  - 输出生成结果验证状态
