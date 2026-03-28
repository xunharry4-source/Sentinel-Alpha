# Sentinel-Alpha 页面功能分析报告

以下报告基于当前 NiceGUI 主界面实现 `src/sentinel_alpha/nicegui/app.py` 与 FastAPI 接口 `src/sentinel_alpha/api/app.py` 的代码分析整理。

相关文案基线另见：
- `docs/ui-copy-baseline.md`
- `docs/ui-remaining-work-checklist.md`

已验证的包括：
- `/api/health`
- `/api/system-health`
- 会话创建
- 配置读取与配置单项测试
- 运行控制操作写入
- 数据源扩展生成与 dry-run 应用
- 交易终端接入最小输入生成、能力缺口判断、smoke test 与 dry-run 应用
- 情报查询
- 情报查询后自动补充市场数据

当前主页面和关键高风险区域已完成定向回归、展示层单测和运行中烟测；外部数据源失败场景会在页面中按真实状态展示，不再视为页面链路缺失。

当前默认本地访问地址：
- NiceGUI：`http://127.0.0.1:8010`
- API：`http://127.0.0.1:8001`
- API 健康检查：`http://127.0.0.1:8001/api/health`

## 页面：会话

### 页面说明

负责在页面打开后自动创建并加载默认会话，同时保留切换已有会话、查看当前会话摘要和完整 JSON 的能力。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 自动创建并加载默认会话 | 页面打开后自动新建工作会话，并补齐训练前置数据，避免每次先手动创建或加载会话 | 是 | `POST /api/sessions` | 是 | 正常 |
| 手动新建默认会话 | 手动重新创建一个新的默认会话，并自动补齐前置数据 | 是 | `POST /api/sessions` | 是 | 正常 |
| 切换到已有会话 | 按 `session_id` 加载已有会话 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 会话摘要 | 显示当前 session 状态、资金、版本、最新情报等 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 会话 JSON | 显示完整快照 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：配置

### 页面说明

当前页面已补齐默认大模型配置、按 Agent 单独配置、配置保存备份和配置测试，不再只是原始 JSON 编辑器。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 当前配置查看 | 展示交易标的、偏好、策略包摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 配置 JSON 查看 | 展示配置类原始结构 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 默认大模型配置 | 设置系统默认 provider、模型列表、temperature 和 max tokens；未单独配置的 Agent 默认继承这里 | 是 | `GET /api/config` / `POST /api/config` | 是 | 正常 |
| Agent 专用模型配置 | 为单个 Agent 单独设置 provider、模型列表、temperature 和 max tokens | 是 | `GET /api/config` / `POST /api/config` | 是 | 正常 |
| 在线编辑配置 | 页面内修改系统配置 | 是 | `GET /api/config` / `POST /api/config` | 是 | 正常 |
| 配置自动备份 | 每次保存配置或测试配置前先备份当前 `settings.toml`，避免模型或参数改坏后无法回退 | 是 | `POST /api/config` / `POST /api/config/test` / `POST /api/config/test-item` | 是 | 正常 |
| 配置测试 | 页面内直接测试配置项 | 是 | `POST /api/config/test` / `POST /api/config/test-item` | 是 | 正常 |

## 页面：策略参数与目标

### 页面说明

负责设置训练参数、交易标的、目标函数、训练区间，并查看训练输入说明。策略公共配置只在点击 `策略参数与目标` 子页面时显示，默认训练区间为 `2021-01-01` 到 `2025-12-31`。策略五个子页面各自带独立页头说明，不再共享一个常驻的大页头。

当前页面文案已做产品化收敛，用户在页面上看到的主要卡片标题包括：
- `当前策略概览`
- `提交前检查`
- `训练输入来源`
- `训练特征摘要`
- `交易策略启用`

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 提交交易标的 | 设置交易标的池 | 是 | `POST /api/sessions/{session_id}/trade-universe` | 是 | 正常 |
| 策略公共配置按子页显示 | 策略公共配置仅在 `策略参数与目标` 子页面内显示，不在整个策略页顶层常驻显示 | 否 | 无 | 是 | 正常 |
| 默认训练时间 | 训练开始默认值为 `2021-01-01`，训练结束默认值为 `2025-12-31` | 否 | 无 | 是 | 正常 |
| 训练参数校验 | 在提交训练前检查训练窗口、收益/胜率/回撤/最大亏损输入是否合法 | 否 | 无 | 是 | 正常 |
| 设置训练参数 | 设置策略类型、目标函数、训练时间、目标值 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 用户策略方式输入 | 用户可以直接填写自己的策略方式，要求训练时保留原有思路而不是只走内置模板 | 否 | 无 | 是 | 正常 |
| 用户策略说明输入 | 用户可以补充自己的策略说明、约束和核心规则，训练时会一并进入分析上下文 | 否 | 无 | 是 | 正常 |
| 交易金额限制输入 | 允许按当前策略设置单笔交易资金占比上限和单笔交易金额上限 | 否 | 无 | 是 | 正常 |
| 交易限制状态显示 | 在策略概览里显示当前策略的交易限制状态和限制说明 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 策略数据需求判断 | 在训练前按策略方式判断需要哪些数据类型；数据不足时不给假训练结果，直接停止并说明需要补哪些数据 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 选择当前交易策略 | 在当前版本和历史版本之间选择一个策略，作为当前用于交易的策略版本 | 是 | `POST /api/sessions/{session_id}/strategy/active` | 是 | 正常 |
| 策略健康状态检测 | 自动给当前交易策略打出 `健康 / 观察 / 危险 / 失效` 四档健康状态 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 策略当前状态检测 | 自动给当前交易策略打出 `开发中 / 测试中 / 验证中 / 正常` 四档当前状态 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 当前训练状态 | 展示当前策略状态、推荐候选、训练窗口 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 训练输入说明 | 展示输入数据包、source lineage、数据质量 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 特征快照 | 展示训练特征与快照信息 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：训练页面

### 页面说明

负责发起训练、继续自动训练、人工介入、查看风险与质量检查、问题变化趋势和下一步修复建议。当前子页面有独立页头和用途说明。

当前页面文案已做产品化收敛，用户在页面上看到的主要卡片标题包括：
- `风险与质量检查`
- `问题变化趋势`
- `下一步修复建议`
- `当前研究结论`
- `研究与修复联动`
- `训练过程记录`

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 生成下一版策略 | 发起策略迭代 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 用户策略说明驱动训练 | 训练时会把用户填写的策略方式、策略说明与交易限制一起带入后端分析和策略包 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 数据不足阻断训练 | 如果当前策略方式需要的必需数据没到位，直接停止训练并明确要求用户补充哪类数据 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 继续自动训练 | 切换自动模式后继续迭代 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| 我来介入后再训练 | 切到人工反馈模式 | 否 | 无 | 是 | 正常 |
| 回填修复反馈 | 将修复建议回填到训练反馈 | 否 | 无 | 是 | 正常 |
| 回填修复指令 | 将修复建议回填到 Programmer Agent | 否 | 无 | 是 | 正常 |
| 检查结果 | 展示 Integrity / Stress / Overfit 检查 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 检查趋势 | 展示失败趋势与研究联动 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 训练日志 | 展示本地与后端训练过程摘要，并给出本轮结论、下一步、策略方式、数据要求和交易限制摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：结果页面

### 页面说明

负责展示模型总计指标、按年指标、回测摘要、滚动检验结果和研究结论。当前子页面有独立页头和用途说明。

当前页面文案已做产品化收敛，用户在页面上看到的主要卡片标题包括：
- `策略模型表现`
- `方案对比`
- `回测摘要`
- `滚动检验结果`
- `研究趋势`
- `结果健康结论`

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

负责查看历史策略版本、恢复前预览、差异对比、研究详情和失败原因变化。当前子页面有独立页头和用途说明。

当前页面文案已做产品化收敛，用户在页面上看到的主要卡片标题包括：
- `版本时间线`
- `历史归档`
- `差异对比`
- `恢复前预览`
- `研究对比`
- `研究详情`
- `失败原因变化`

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

负责展示发布结论、当前推荐代码、模型选择、LLM 资源消耗和 Programmer Agent 结果。当前子页面有独立页头和用途说明。

当前页面文案已做产品化收敛，用户在页面上看到的主要卡片标题包括：
- `发布结论`
- `关键分析`
- `当前推荐代码`
- `模型选择与路由`
- `本轮 LLM 资源消耗`
- `Programmer Agent 执行记录`

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 研究发布摘要 | 展示发布门、winner、稳健性等 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 推荐代码 | 展示当前推荐策略代码 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 模型矩阵 | 展示模型路由与研究选择 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| LLM 消耗 | 展示 token 使用情况 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 按 Agent 统计 LLM 消耗 | 按 Agent 单独展示调用次数、token 消耗、fallback 比例和模型列表 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 弱模型切换提示 | 如果某个 Agent 最近大量 fallback 或模型链路明显不稳定，会给出更换模型的提示 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 执行 Programmer Agent | 发起受限代码修改，并明确显示 dry-run、边界拦截、修复链路、接受判断和回退建议 | 是 | `POST /api/sessions/{session_id}/programmer/execute` | 是 | 正常 |
| dry-run 结果说明 | 在数据源扩展和交易终端接入未提交改动时，明确显示只是预演未写入工作区 | 否 | 无 | 是 | 正常 |
| Programmer Agent 趋势与统计 | 展示失败类型与趋势 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

## 页面：模拟

### 页面说明

负责模拟交易、自动按当前会话股票池加载模拟市场数据、查看日线与 5 分钟线、按固定 5 分钟节奏推进模拟时钟、让用户只做买入/卖出/不交易三种行为、自动捕获盯盘时长/亏损下频繁刷新/手动干预自动化等行为细节，并生成行为画像、查看用户/系统行为报告。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 初始化模拟市场 | 自动使用当前会话股票池的第一个标的加载日线与 5 分钟线数据，并建立当前模拟时钟 | 是 | `POST /api/sessions/{session_id}/simulation/market/initialize` | 是 | 正常 |
| 日线图展示 | 展示模拟窗口内的日线价格轨迹与当前定位 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 5 分钟线图展示 | 展示当前模拟日的 5 分钟级别价格轨迹与当前推进位置 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 按时间推进模拟 | 按固定 5 分钟 bar 推进模拟时钟，并刷新当前价格、回撤、进度和快照；后续新增行为会继续作为模拟重训练输入 | 是 | `POST /api/sessions/{session_id}/simulation/market/advance` | 是 | 正常 |
| 用户行为输入 | 用户在每个市场时点只做买入、卖出、不交易三种动作，其它上下文由系统自动记录 | 是 | `POST /api/sessions/{session_id}/simulation/events` | 是 | 正常 |
| 行为捕获层 | 自动记录当前动作前的盯盘时长、亏损下频繁刷新次数、触发焦虑刷新的回撤点，以及后续真实交易里的手动干预自动化信号 | 是 | `POST /api/sessions/{session_id}/simulation/events` + `POST /api/sessions/{session_id}/trade-executions` + `GET /api/sessions/{session_id}` | 是 | 正常 |
| 完成模拟门禁 | 未加载市场、未推进市场、或没有至少一次用户动作时，不允许直接生成行为画像 | 是 | `POST /api/sessions/{session_id}/simulation/complete` | 是 | 正常 |
| 完成模拟并生成画像 | 生成 behavioral report | 是 | `POST /api/sessions/{session_id}/simulation/complete` | 是 | 正常 |
| 模拟训练状态 | 显示当前模拟是在建立基线、已可训练策略、持续监控，还是已经建议重训练；当同一情报主题被反复确认或短时再次确认时，也会作为失效理由纳入 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 基于新增行为重新训练模拟 | 当模拟失效或用户主动要求时，基于新增行为重新训练模拟画像和行为基线 | 是 | `POST /api/sessions/{session_id}/simulation/retrain` | 是 | 正常 |
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

## 页面：习惯与目标

### 页面说明

负责统一汇总模拟测试结果、手动偏好、训练反馈、真实交易行为和当前策略状态，并通过 `HabitGoalEvolutionAgent` + LLM 生成综合分析，展示当前习惯、目标、风险、行为捕获结论和历史变化时间线。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 当前习惯与目标结论 | 展示当前习惯判断、目标判断、综合结论、当前重点、交易限制和分析方式，并纳入情报搜索行为与主题级确认偏误信号 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 行为捕获摘要 | 展示盯盘时长、焦虑刷新、手动干预自动化和信任衰减等自动捕获结论 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 风险、冲突与下一步 | 展示风险标记、下一步动作、需要用户补充的信息、一致性判断和置信说明 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 最近变化 | 展示最近一次习惯变化和目标变化摘要 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 演化时间线 | 记录模拟测试、偏好更新、训练迭代、策略切换、真实交易等事件带来的综合分析变化 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| LLM 演化分析 | 使用 LLM 对习惯、目标和策略状态做综合判断；失败时回退到规则分析并保留 warning | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 原始演化 JSON | 查看 `habit_goal_evolution` 的原始结构 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |

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

当前数据源扩展改成最小输入模式：用户只需要提供 `API KEY` 和接口文档，系统会先用 LLM 对非结构化接口文档做语义分析并产出结构化接入规范；当 LLM 不可用、调用失败或返回非法结构时，再回退到规则兜底分析。随后系统基于结构化规范生成符合 Agent 要求的 adapter 代码与测试草案，并支持 dry-run 应用。策略训练发现真实股票历史数据缺失时，会自动优先复用这里已经生成并可用的 `market_data` 数据源补抓缺失历史数据，并把结果落到本地 `market_data` 目录。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 数据源健康检查 | 检查当前已配置数据源和扩展数据源的健康状态，区分 healthy / warning / generated_not_tested / error，并给出一句话结论、风险说明和下一步动作 | 是 | `GET /api/sessions/{session_id}/data-source/health` | 是 | 正常 |
| 已配置数据源管理表格 | 以表格方式查看 `market_data / fundamentals / dark_pool / options_data` 已配置 provider 的启用状态、API KEY 状态、Base URL 和说明 | 是 | `GET /api/data-source/health` / `GET /api/sessions/{session_id}/data-source/health` | 是 | 正常 |
| 数据源扩展记录查看 | 查看已有扩展记录 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 输入数据包记录查看 | 查看 data bundle 记录 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 最小输入扩展请求 | 用户只提供 API KEY 和接口文档，由系统自动完成分析、生成和测试 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 本地数据路径与格式提示 | 在工作台直接显示按类型拆分后的本地数据目录、文件命名规则、支持格式与示例 | 否 | 无 | 是 | 正常 |
| 扩展结果本地保存 | 生成或补充数据源后，将扩展结果与 apply 结果保存到本地清单文件 | 是 | `POST /api/sessions/{session_id}/data-source/expand` / `POST /api/sessions/{session_id}/data-source/apply` | 是 | 正常 |
| 数据源扩展 smoke test | 对已生成的数据源 run 执行 smoke test，并在提供 API KEY 时尝试 live fetch；会区分无效 API KEY、套餐/计费限制、权限不足、网络失败、文档或 endpoint 不匹配，并给出处理建议；测试结果会保存到本地清单 | 是 | `POST /api/sessions/{session_id}/data-source/test` | 是 | 正常 |
| 训练自动补数 | 当策略训练缺少真实历史数据时，自动优先复用当前会话里可用的 `market_data` 扩展 run 或已启用 provider 补抓 `1d` 历史数据，并保存到本地 | 是 | `POST /api/sessions/{session_id}/strategy/iterate` | 是 | 正常 |
| LLM 接口文档分析 | LLM 对非结构化接口文档做语义理解，提取 provider、分类、鉴权、endpoint、参数和返回结构 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 规则兜底分析 | 当 LLM 不可用、失败或返回非法结构时，回退到规则分析并明确记录 fallback 原因 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 结构化接入规范生成 | 输出结构化 integration spec，供代码生成、测试和 apply 复用 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 自动生成代码与测试 | 基于结构化 integration spec 生成 adapter 模块、测试代码和 config 候选 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 扩展结果测试 | 对生成结果进行语法/结构测试，并输出验证状态 | 是 | `POST /api/sessions/{session_id}/data-source/expand` | 是 | 正常 |
| 更新扩展数据源 | 修改已有扩展 run 的接口文档、provider 名称、类型、Base URL、API KEY ENV 等，并重新生成方案 | 是 | `POST /api/sessions/{session_id}/data-source/update` | 是 | 正常 |
| 删除扩展数据源 | 删除指定扩展 run | 是 | `POST /api/sessions/{session_id}/data-source/delete` | 是 | 正常 |
| 应用数据源扩展 | 在页面内应用扩展结果 | 是 | `POST /api/sessions/{session_id}/data-source/apply` | 是 | 正常 |
| 保存已配置数据源 | 修改或新增已配置 provider 的启用状态、默认状态、Base URL、Base Path、API KEY ENV 等 | 是 | `POST /api/config/data-source/provider` | 是 | 正常 |
| 删除已配置数据源 | 删除已配置 provider，并同步从 enabled 列表和 default_provider 中移除 | 是 | `POST /api/config/data-source/provider/delete` | 是 | 正常 |

## 页面：交易运行

### 页面说明

当前页面改成面向人的 `交易运行与记录` 工作区，用来准备当天交易环境、记录当前市场状态、补一条重要消息、保存一笔人工交易，并查看最近运行记录与提醒。页面不再把底层调试字段直接暴露给用户。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 当前运行状态 | 用用户能理解的方式显示当前执行方式、当前交易策略、股票池、最近交易记录、最近消息记录和监控提醒数量 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 准备今日交易场景 | 生成默认场景包，并为当天交易准备基础运行上下文 | 是 | `POST /api/sessions/{session_id}/generate-scenarios` | 是 | 正常 |
| 保存当前执行方式 | 在 `仅建议，不自动下单` 与 `自动执行` 之间切换当前执行方式 | 是 | `POST /api/sessions/{session_id}/deployment` | 是 | 正常 |
| 保存市场状态 | 只输入股票、周期、价格、高低点、成交量和市场氛围，即可写入当前市场状态 | 是 | `POST /api/sessions/{session_id}/market-snapshots` | 是 | 正常 |
| 保存消息记录 | 只输入消息类型、标题、影响倾向和内容，即可补一条会影响交易判断的消息 | 是 | `POST /api/sessions/{session_id}/information-events` | 是 | 正常 |
| 保存交易记录 | 只输入股票、买卖方向、数量、价格和备注，即可记录一笔人工交易；成交金额和当前策略会自动带入 | 是 | `POST /api/sessions/{session_id}/trade-executions` | 是 | 正常 |
| 最近页面操作 | 展示用户刚刚在该页做过的保存动作，避免误以为页面没有响应 | 否 | 无 | 是 | 正常 |
| 最近运行记录与提醒 | 合并展示历史事件和监控提醒，减少用户在多个工程面板之间切换 | 是 | `GET /api/sessions/{session_id}/history` / `GET /api/sessions/{session_id}/monitors` | 是 | 正常 |

## 页面：交易终端接入

### 页面说明

当前交易终端接入改成最小输入模式：用户只需要提供 `API KEY` 和技术文档，系统会先用 LLM 分析非结构化技术文档，再自动生成接入代码、测试代码和结构化能力说明。当前只覆盖单交易所/单账户接入，同时明确保留多交易所、多账户和跨交易所路由的后续扩展缺口。系统会明确区分自动交易必需能力和可选能力：

- 必需能力：
  - `生成交易`
  - `查询订单状态`
  - `账户股票信息`
  - `账户资金信息`
- 可选能力：
  - `撤单`
  - `查询交易记录`

如果缺少必需能力，系统会明确提示当前无法执行自动交易，并要求用户重新提供更完整的技术文档；如果缺少可选能力，系统会给出警告，用户可以继续补充文档，或者带警告继续。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 交易终端接入记录查看 | 查看 terminal integration 记录 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 最小输入接入请求 | 用户只提供 API KEY 和技术文档，由系统自动完成分析、生成和能力判断 | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 更新交易终端接入 | 用户提供新的技术文档后，更新已有 run 的能力和生成代码 | 是 | `POST /api/sessions/{session_id}/terminal/update` | 是 | 正常 |
| 删除交易终端接入 | 删除指定交易终端接入 run | 是 | `POST /api/sessions/{session_id}/terminal/delete` | 是 | 正常 |
| LLM 技术文档分析 | LLM 对非结构化技术文档做语义理解，提取终端类型、Base URL、鉴权方式和能力 endpoint | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 必需能力判定 | 自动判断 `生成交易 / 查询订单状态 / 账户股票信息 / 账户资金信息` 是否齐备，并决定是否允许自动交易 | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 可选能力判定 | 自动判断 `撤单 / 查询交易记录` 是否齐备；缺失时给出警告但不一定阻断 | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 单交易所范围说明 | 在接入结果里明确 `single_exchange` 范围和多交易所扩展缺口 | 是 | `POST /api/sessions/{session_id}/terminal/expand` / `GET /api/sessions/{session_id}` | 是 | 正常 |
| 自动生成代码与测试 | 基于结构化技术文档分析结果生成终端 adapter 和测试代码 | 是 | `POST /api/sessions/{session_id}/terminal/expand` | 是 | 正常 |
| 应用交易终端接入 | 页面内应用交易终端接入结果 | 是 | `POST /api/sessions/{session_id}/terminal/apply` | 是 | 正常 |
| 测试交易终端接入 | 页面内发起交易终端接入测试，验证必需/可选能力和返回结构 | 是 | `POST /api/sessions/{session_id}/terminal/test` | 是 | 正常 |

## 页面：情报

### 页面说明

负责情报查询、股票列表批量查询、历史查看，并自动补充最新财报、暗池、期权数据。

| 功能 | 功能说明 | 是否需要后段 | 后端访问地址 | 是否已经完成 | 功能是否正常 |
|---|---|---|---|---|---|
| 单次情报查询 | 按查询词发起情报搜索 | 是 | `POST /api/sessions/{session_id}/intelligence/search` | 是 | 正常 |
| 新闻自动翻译与总结 | 情报搜索后自动把新闻标题与摘要翻译成中文，并生成整批新闻总结 | 是 | `POST /api/sessions/{session_id}/intelligence/search` | 是 | 正常 |
| 翻译结果写入历史 | 把新闻翻译结果和中文总摘要写入查询历史、事件时间线和报告归档，便于后续回看 | 是 | `POST /api/sessions/{session_id}/intelligence/search` + `GET /api/sessions/{session_id}` | 是 | 正常 |
| 当前股票列表批量查询 | 基于当前交易标的批量查询情报 | 是 | `POST /api/sessions/{session_id}/intelligence/search` | 是 | 正常 |
| 情报查询行为捕获 | 统计查询次数、是否频繁查询、重复搜索比例、短时间高频搜索比例，并把结果纳入行为和模拟重训练判断 | 是 | `POST /api/sessions/{session_id}/intelligence/search` + `GET /api/sessions/{session_id}` | 是 | 正常 |
| 历史情报行为分析 | 基于历史情报查询记录分析是否频繁查询、是否频繁重复搜索、重复主题组数量、短时重复主题组数量，以及是否存在主题级确认偏误或焦虑确认，并给出模拟测试或重训建议 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 自动补充市场数据 | 情报查询后自动补查财报、暗池、期权 | 是 | `POST /api/sessions/{session_id}/intelligence/search` 触发后端自动补查 | 是 | 正常 |
| 股票情报总览 | 按股票维度汇总最新情报结论 | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| 历史情报查看 | 查看历史查询详情、中文总结、首条翻译摘要和 JSON | 是 | `GET /api/sessions/{session_id}` | 是 | 正常 |
| Agent 原子日志 | 显示情报搜索、批量查询、自动补查市场数据以及其他 Agent 操作的原子步骤日志，避免用户误判系统卡死 | 是 | `GET /api/sessions/{session_id}/agent-activity` | 是 | 正常 |
| 财报摘要 | 展示自动补查财报结果，并在人类化错误分类下显示失败原因与建议 | 是 | `POST /api/sessions/{session_id}/intelligence/financials` | 是 | 正常 |
| 暗池摘要 | 展示自动补查暗池结果，并在人类化错误分类下显示失败原因与建议 | 是 | `POST /api/sessions/{session_id}/intelligence/dark-pool` | 是 | 正常 |
| 期权摘要 | 展示自动补查期权结果，并在人类化错误分类下显示失败原因与建议 | 是 | `POST /api/sessions/{session_id}/intelligence/options` | 是 | 正常 |

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

## 当前状态

当前页面体系的功能主链、关键高风险展示、文案基线和相关技术文档已经完成第一轮收尾。剩余工作属于后续增强型优化或更高强度回归，不再归类为页面功能未完成。

## 本次补充说明

- 当前本地热更新开发链路为：NiceGUI `http://127.0.0.1:8010`，API `http://127.0.0.1:8001`。
- `/api/system-health` 的本地开发态空时间戳崩溃问题已修复。
- `data-source/apply` 与 `terminal/apply` 在 `commit_changes=false` 时为真正 `dry_run`，不会触发真实仓库写入。
- 最新已完成的本地验证包括：
  - `python -m py_compile src/sentinel_alpha/nicegui/app.py src/sentinel_alpha/api/workflow_service.py src/sentinel_alpha/api/app.py tests/test_api_workflow.py`
  - `pytest tests/test_api_workflow.py -q -k 'data_source_expansion_can_be_applied_by_programmer_agent or trading_terminal_integration_can_be_applied_by_programmer_agent or trading_terminal_integration_can_be_smoke_tested'`
  - 本地 API `/api/system-health` 返回正常
  - 本地 NiceGUI 页面输出已确认包含 `系统配置工作台 / 数据源扩展工作台 / 交易运行与记录 / 交易终端接入工作台 / 恢复预览`

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
