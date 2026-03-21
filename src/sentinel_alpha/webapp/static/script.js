const scenarios = [
  {
    id: "uptrend",
    title: "单边上涨 / Uptrend",
    playbook: "uptrend",
    cohort: "pressure",
    tags: ["trend", "fear_of_heights"],
    priceTrack: [
      { t: "2026-01-05 09:30", price: 100.96, drawdown: 0.96, ret: 0.96, iv: 0.22 },
      { t: "2026-01-06 09:30", price: 104.43, drawdown: 4.43, ret: 0.97, iv: 0.229 },
      { t: "2026-01-09 09:30", price: 109.68, drawdown: 9.68, ret: 1.12, iv: 0.244 },
      { t: "2026-01-14 09:30", price: 114.86, drawdown: 14.86, ret: 1.28, iv: 0.259 },
      { t: "2026-01-22 09:30", price: 120.25, drawdown: 20.25, ret: 1.42, iv: 0.271 },
    ],
    noiseTrack: [
      { t: "2026-01-05 10:30", channel: "macro_desk", sentiment: -0.42, headline: "Valuation is stretched", body: "Plenty of traders are fading this move. Chasing here looks reckless." },
      { t: "2026-01-09 10:30", channel: "macro_desk", sentiment: -0.42, headline: "Bubble risk is rising", body: "Momentum desks are warning this trend is too crowded to trust." },
      { t: "2026-01-14 10:30", channel: "macro_desk", sentiment: -0.42, headline: "Top callers are lining up", body: "Short sellers are framing this as the late-stage phase of the move." },
      { t: "2026-01-22 10:30", channel: "macro_desk", sentiment: -0.42, headline: "Chasing here is dangerous", body: "Commentary is getting louder that the upside is already over." },
    ],
    truth: "Hidden truth: fundamentals remain strong and trend persistence is real.",
  },
  {
    id: "fake_reversal",
    title: "假反弹 / Fake Reversal",
    playbook: "fake_reversal",
    cohort: "pressure",
    tags: ["bear_market_rally", "bottom_fishing"],
    priceTrack: [
      { t: "2026-02-13 14:00", price: 91.0, drawdown: -9.0, ret: -9.0, iv: 0.72 },
      { t: "2026-02-13 14:10", price: 84.63, drawdown: -15.37, ret: -7.0, iv: 0.68 },
      { t: "2026-02-13 14:20", price: 88.44, drawdown: -11.56, ret: 4.5, iv: 0.63 },
      { t: "2026-02-13 14:30", price: 93.3, drawdown: -6.7, ret: 5.5, iv: 0.65 },
      { t: "2026-02-13 14:40", price: 87.7, drawdown: -12.3, ret: -6.0, iv: 0.66 },
      { t: "2026-02-13 15:00", price: 77.89, drawdown: -22.11, ret: -4.5, iv: 0.63 },
    ],
    noiseTrack: [
      { t: "2026-02-13 14:00:20", channel: "social", sentiment: -0.61, headline: "Panic liquidations continue", body: "Weak hands are puking inventory. Desks expect more forced selling." },
      { t: "2026-02-13 14:20:20", channel: "social", sentiment: 0.84, headline: "V-bottom confirmed", body: "Smart money is sweeping the lows. This rebound is the first leg of the reversal." },
      { t: "2026-02-13 14:30:20", channel: "social", sentiment: 0.84, headline: "Bottom is in", body: "The bounce is broadening. Missing this move could define the quarter." },
      { t: "2026-02-13 14:40:20", channel: "social", sentiment: -0.61, headline: "More forced selling ahead", body: "The bounce failed. Dealers are bracing for another flush lower." },
    ],
    truth: "Hidden truth: trend remains bearish, balance sheet stress is unresolved.",
  },
  {
    id: "oscillation",
    title: "猴市震荡 / Oscillation",
    playbook: "oscillation",
    cohort: "pressure",
    tags: ["range", "overtrading"],
    priceTrack: [
      { t: "2026-01-08 09:30", price: 100.0, drawdown: 0.0, ret: 0.0, iv: 0.24 },
      { t: "2026-01-08 12:30", price: 102.63, drawdown: 2.63, ret: 2.63, iv: 0.32 },
      { t: "2026-01-08 15:30", price: 99.48, drawdown: -0.52, ret: -3.07, iv: 0.33 },
      { t: "2026-01-08 18:30", price: 102.12, drawdown: 2.12, ret: 2.65, iv: 0.31 },
      { t: "2026-01-08 21:30", price: 98.97, drawdown: -1.03, ret: -3.08, iv: 0.33 },
      { t: "2026-01-09 00:30", price: 101.44, drawdown: 1.44, ret: 2.5, iv: 0.29 },
    ],
    noiseTrack: [
      { t: "2026-01-08 10:00", channel: "trader_chat", sentiment: 0.55, headline: "Breakout confirmed", body: "Momentum traders are leaning long. This range is finally resolving higher." },
      { t: "2026-01-08 15:45", channel: "trader_chat", sentiment: -0.55, headline: "Breakdown underway", body: "Tape is weak again. That breakout was obviously fake." },
      { t: "2026-01-08 18:45", channel: "trader_chat", sentiment: 0.55, headline: "New squeeze incoming", body: "Shorts are trapped once more. Another leg up is loading." },
      { t: "2026-01-08 21:45", channel: "trader_chat", sentiment: -0.55, headline: "Failed move, weak close", body: "This chop will punish anyone trying to force a trend." },
    ],
    truth: "Hidden truth: market is range-bound and noisy. Confirmation quality is poor.",
  },
];

const state = {
  sessionId: null,
  scenarioIndex: 0,
  step: 0,
  position: null,
  entryPrice: null,
  positionSize: 0,
  positionPct: 25,
  totalCostPct: 0,
  logs: [],
  notionalCapital: 500000,
  feeRatePct: 0.12,
  slippagePct: 0.18,
  apiConnected: false,
  healthRetryMs: 5000,
  healthTimerId: null,
  config: null,
};

const SESSION_STORAGE_KEY = "sentinel-alpha:last-session-snapshot";
const CONFIG_STORAGE_KEY = "sentinel-alpha:web-config";

const tradingPreferenceOptions = {
  low: {
    note: "低频交易意味着你不需要天天出手，更适合等待明确机会，通常更偏向日线或周线。",
    timeframes: [
      { value: "daily", label: "日线", note: "日线适合过滤大部分噪音，是多数个人交易者更容易执行的周期。" },
      { value: "weekly", label: "周线", note: "周线更慢，但更适合耐心型、波段型用户。" },
    ],
  },
  medium: {
    note: "中频交易强调节奏和过滤，不是看到波动就冲进去，通常以日线为主，分钟线为辅。",
    timeframes: [
      { value: "minute", label: "分钟线", note: "分钟线机会更多，但盯盘强度和成本会明显提高。" },
      { value: "daily", label: "日线", note: "日线更稳，是中频用户默认更容易执行的核心周期。" },
      { value: "weekly", label: "周线", note: "周线适合做趋势过滤，不适合期待天天有交易机会。" },
    ],
  },
  high: {
    note: "高频意味着你愿意接受更高盯盘要求、更多信号和更高噪音，不适合只凭一句“有机会就交易”。",
    timeframes: [
      { value: "minute", label: "分钟线", note: "分钟线最贴近高频需求，但对纪律、成本控制和执行稳定性要求最高。" },
      { value: "daily", label: "日线", note: "如果你说自己高频但又不愿盯盘，日线通常更现实。" },
    ],
  },
};

const els = {
  select: document.querySelector("#scenario-select"),
  playbookChip: document.querySelector("#playbook-chip"),
  cohortChip: document.querySelector("#cohort-chip"),
  stepChip: document.querySelector("#step-chip"),
  title: document.querySelector("#scenario-title"),
  currentPrice: document.querySelector("#current-price"),
  currentDrawdown: document.querySelector("#current-drawdown"),
  currentIv: document.querySelector("#current-iv"),
  currentTime: document.querySelector("#current-time"),
  currentTruth: document.querySelector("#current-truth"),
  noiseHeadline: document.querySelector("#noise-headline"),
  noiseBody: document.querySelector("#noise-body"),
  noiseChannel: document.querySelector("#noise-channel"),
  noiseSentiment: document.querySelector("#noise-sentiment"),
  positionState: document.querySelector("#position-state"),
  sizeState: document.querySelector("#size-state"),
  pnlState: document.querySelector("#pnl-state"),
  costState: document.querySelector("#cost-state"),
  stressState: document.querySelector("#stress-state"),
  impactHeadline: document.querySelector("#impact-headline"),
  impactBody: document.querySelector("#impact-body"),
  actionFrequency: document.querySelector("#action-frequency"),
  noiseScore: document.querySelector("#noise-score"),
  bottomFishing: document.querySelector("#bottom-fishing"),
  deceptionScore: document.querySelector("#deception-score"),
  profilerNote: document.querySelector("#profiler-note"),
  resultArchetype: document.querySelector("#result-archetype"),
  resultRisk: document.querySelector("#result-risk"),
  resultHold: document.querySelector("#result-hold"),
  resultOvertrade: document.querySelector("#result-overtrade"),
  resultNote: document.querySelector("#result-note"),
  resultList: document.querySelector("#result-list"),
  profilerJsonPanel: document.querySelector("#profiler-json-panel"),
  logBody: document.querySelector("#log-body"),
  chart: document.querySelector("#price-chart"),
  nextStep: document.querySelector("#next-step"),
  reset: document.querySelector("#reset-sim"),
  capitalInput: document.querySelector("#capital-input"),
  positionInput: document.querySelector("#position-input"),
  userNameInput: document.querySelector("#user-name-input"),
  startingCapitalInput: document.querySelector("#starting-capital-input"),
  createSession: document.querySelector("#create-session"),
  generateScenarios: document.querySelector("#generate-scenarios"),
  frequencyInput: document.querySelector("#frequency-input"),
  timeframeInput: document.querySelector("#timeframe-input"),
  frequencyNote: document.querySelector("#frequency-note"),
  timeframeNote: document.querySelector("#timeframe-note"),
  recommendationNote: document.querySelector("#recommendation-note"),
  preferenceConflictNote: document.querySelector("#preference-conflict-note"),
  preferenceRationaleInput: document.querySelector("#preference-rationale-input"),
  applyRecommendation: document.querySelector("#apply-recommendation"),
  savePreferences: document.querySelector("#save-preferences"),
  completeSimulation: document.querySelector("#complete-simulation"),
  universeTypeInput: document.querySelector("#universe-type-input"),
  universeSymbolsInput: document.querySelector("#universe-symbols-input"),
  submitUniverse: document.querySelector("#submit-universe"),
  strategyFeedbackInput: document.querySelector("#strategy-feedback-input"),
  strategyTypeInput: document.querySelector("#strategy-type-input"),
  strategyRecommendationNote: document.querySelector("#strategy-recommendation-note"),
  applyStrategyRecommendation: document.querySelector("#apply-strategy-recommendation"),
  iterateStrategy: document.querySelector("#iterate-strategy"),
  approveStrategy: document.querySelector("#approve-strategy"),
  setAutonomous: document.querySelector("#set-autonomous"),
  setAdviceOnly: document.querySelector("#set-advice-only"),
  sessionStatus: document.querySelector("#session-status"),
  simulatorSection: document.querySelector("#simulator-section"),
  frontendStatusChip: document.querySelector("#frontend-status-chip"),
  apiStatusChip: document.querySelector("#api-status-chip"),
  databaseStatusChip: document.querySelector("#database-status-chip"),
  apiStatusNote: document.querySelector("#api-status-note"),
  deploymentNote: document.querySelector("#deployment-note"),
  strategyNote: document.querySelector("#strategy-note"),
  strategyList: document.querySelector("#strategy-list"),
  checkNote: document.querySelector("#check-note"),
  checkGrid: document.querySelector("#check-grid"),
  monitorList: document.querySelector("#monitor-list"),
  flowCreated: document.querySelector("#flow-created"),
  flowSim: document.querySelector("#flow-sim"),
  flowReport: document.querySelector("#flow-report"),
  flowUniverse: document.querySelector("#flow-universe"),
  flowStrategy: document.querySelector("#flow-strategy"),
  flowDeploy: document.querySelector("#flow-deploy"),
};

const backendButtons = [
  "createSession",
  "generateScenarios",
  "savePreferences",
  "applyRecommendation",
  "applyStrategyRecommendation",
  "completeSimulation",
  "submitUniverse",
  "iterateStrategy",
  "approveStrategy",
  "setAutonomous",
  "setAdviceOnly",
];

function currentScenario() {
  return scenarios[state.scenarioIndex];
}

function renderTradingPreferenceOptions() {
  const config = tradingPreferenceOptions[els.frequencyInput.value] || tradingPreferenceOptions.low;
  els.frequencyNote.textContent = config.note;
  const currentValue = els.timeframeInput.value;
  els.timeframeInput.innerHTML = config.timeframes
    .map((item) => `<option value="${item.value}">${item.label}</option>`)
    .join("");
  const hasExisting = config.timeframes.some((item) => item.value === currentValue);
  els.timeframeInput.value = hasExisting ? currentValue : config.timeframes[0].value;
  renderTimeframeNote();
}

function renderTimeframeNote() {
  const config = tradingPreferenceOptions[els.frequencyInput.value] || tradingPreferenceOptions.low;
  const selected = config.timeframes.find((item) => item.value === els.timeframeInput.value) || config.timeframes[0];
  els.timeframeNote.textContent = selected.note;
}

function applyBehaviorRecommendation(report) {
  if (!report?.recommended_trading_frequency || !report?.recommended_timeframe) {
    return;
  }
  els.frequencyInput.value = report.recommended_trading_frequency;
  renderTradingPreferenceOptions();
  els.timeframeInput.value = report.recommended_timeframe;
  renderTimeframeNote();
  els.recommendationNote.textContent = report.trading_preference_recommendation_note || "系统已根据行为测试结果给出默认推荐。";
  if (report.recommended_strategy_type) {
    els.strategyTypeInput.value = report.recommended_strategy_type;
    els.strategyRecommendationNote.textContent = report.strategy_type_recommendation_note || "系统已根据行为测试结果给出默认策略类型推荐。";
  }
}

function updatePreferenceConflict(snapshot) {
  const warning = snapshot?.trading_preferences?.conflict_warning;
  if (warning) {
    els.preferenceConflictNote.textContent = warning;
    els.preferenceConflictNote.classList.add("negative");
    return;
  }
  els.preferenceConflictNote.textContent = "如果你的主观选择和测试结果明显冲突，这里会提示风险。";
  els.preferenceConflictNote.classList.remove("negative");
}

function scrollToSimulation() {
  els.simulatorSection?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function currentPoint() {
  const scenario = currentScenario();
  return scenario.priceTrack[Math.min(state.step, scenario.priceTrack.length - 1)];
}

function currentNoise() {
  const scenario = currentScenario();
  return scenario.noiseTrack[Math.min(state.step, scenario.noiseTrack.length - 1)] || null;
}

function formatPct(value) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatMoney(value) {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 0,
  }).format(Math.abs(value));
}

function describeImpact(pnlAmount) {
  const amount = Math.abs(pnlAmount);
  if (amount < 1) {
    return {
      headline: "目前还没有真实盈亏冲击。",
      body: "仓位还没有形成足够的盈亏波动，心理压力基本为零。",
    };
  }

  const direction = pnlAmount >= 0 ? "赚了" : "亏了";
  const ladder = [
    { threshold: 3000, label: "一副无线耳机", detail: "这已经不是小数点波动，而是能买一件像样电子产品的金额。" },
    { threshold: 8000, label: "一部苹果手机", detail: "这类盈亏通常足够触发普通用户明显的情绪反馈。" },
    { threshold: 50000, label: "一台高配电脑", detail: "这个级别开始从消费品冲击上升到可感知的资产损益。" },
    { threshold: 200000, label: "一辆家用车", detail: "这已经接近多数人会认真怀疑自己判断的金额区间。" },
    { threshold: 1500000, label: "一套房首付", detail: "这种盈亏会明显改变风险承受感知，容易诱发非理性决策。" },
    { threshold: 5000000, label: "一套房", detail: "这已经属于足以重塑家庭财务预期的级别。" },
  ];

  let selected = ladder[0];
  for (const item of ladder) {
    if (amount >= item.threshold) {
      selected = item;
    } else {
      break;
    }
  }

  return {
    headline: `${direction}${selected.label}`,
    body: `${direction}${formatMoney(pnlAmount)}，约等于 ${selected.label}。${selected.detail}`,
  };
}

function tradeCostPct() {
  return state.feeRatePct + state.slippagePct;
}

async function api(path, options = {}) {
  const response = await fetch(`${state.config.apiBase}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}`);
  }
  return response.json();
}

async function loadClientConfig() {
  const response = await fetch("./config.json");
  if (!response.ok) {
    throw new Error("frontend config missing");
  }
  const payload = await response.json();
  state.config = payload;
  state.healthRetryMs = payload.healthRetryMs || state.healthRetryMs;
  window.localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(payload));
}

function applyStatusChip(element, label, status) {
  const variant = status === "ok" ? "success-chip" : status === "configured" ? "success-chip" : status === "not_configured" ? "warn-chip" : "danger-chip";
  element.textContent = label;
  element.className = `status-chip ${variant}`;
}

function setBackendControlsDisabled(disabled) {
  backendButtons.forEach((key) => {
    const element = els[key];
    if (element) {
      element.disabled = disabled;
      element.classList.toggle("button-disabled", disabled);
    }
  });
}

function scheduleHealthRetry() {
  if (state.healthTimerId !== null) return;
  state.healthTimerId = window.setTimeout(async () => {
    state.healthTimerId = null;
    await checkApiHealth();
  }, state.healthRetryMs);
}

function setHealthStatus(payload) {
  const frontendStatus = payload?.frontend?.status || "error";
  const apiStatus = payload?.api?.status || "error";
  const databaseStatus = payload?.database?.status || "error";
  state.apiConnected = apiStatus === "ok";

  applyStatusChip(els.frontendStatusChip, frontendStatus === "ok" ? "前端已加载" : "前端异常", frontendStatus);
  applyStatusChip(els.apiStatusChip, apiStatus === "ok" ? "API 已连接" : "API 未连接", apiStatus);
  applyStatusChip(
    els.databaseStatusChip,
    databaseStatus === "ok" ? "数据库正常" : databaseStatus === "configured" ? "数据库已配置" : databaseStatus === "not_configured" ? "数据库未配置" : "数据库异常",
    databaseStatus,
  );
  els.apiStatusNote.textContent = `${payload.frontend?.detail || ""} ${payload.api?.detail || ""} ${payload.database?.detail || ""}`.trim();
  setBackendControlsDisabled(!state.apiConnected);
}

function setDisconnectedStatus(detail) {
  state.apiConnected = false;
  applyStatusChip(els.frontendStatusChip, "前端已加载", "ok");
  applyStatusChip(els.apiStatusChip, "API 未连接", "error");
  applyStatusChip(els.databaseStatusChip, "数据库未知", "error");
  els.apiStatusNote.textContent = detail;
  setBackendControlsDisabled(true);
  scheduleHealthRetry();
}

async function checkApiHealth() {
  try {
    const payload = await api("/api/health");
    setHealthStatus(payload);
  } catch (error) {
    setDisconnectedStatus(`无法连接后端 ${state.config.apiBase}。系统会自动重试。`);
  }
}

function normalizeSettings() {
  const capital = Number(els.capitalInput.value);
  const positionPct = Number(els.positionInput.value);
  state.notionalCapital = Number.isFinite(capital) && capital > 0 ? capital : 500000;
  state.positionPct = Number.isFinite(positionPct) ? Math.min(100, Math.max(1, positionPct)) : 25;
  els.capitalInput.value = String(state.notionalCapital);
  els.positionInput.value = String(state.positionPct);
}

function computeNetPnl(point) {
  const grossPct = state.position === "LONG" && state.entryPrice
    ? ((point.price - state.entryPrice) / state.entryPrice) * 100
    : 0;
  const netPct = grossPct - state.totalCostPct;
  const netAmount = (netPct / 100) * state.positionSize;
  return { grossPct, netPct, netAmount };
}

function initSelect() {
  els.select.innerHTML = scenarios.map((scenario, index) => (
    `<option value="${index}">${scenario.title}</option>`
  )).join("");
  els.select.addEventListener("change", (event) => {
    state.scenarioIndex = Number(event.target.value);
    resetScenario();
  });
}

function drawChart() {
  const scenario = currentScenario();
  const points = scenario.priceTrack;
  const width = 720;
  const height = 260;
  const padX = 28;
  const padY = 24;
  const prices = points.map((point) => point.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const usableW = width - padX * 2;
  const usableH = height - padY * 2;
  const path = points.map((point, index) => {
    const x = padX + (usableW * index) / Math.max(1, points.length - 1);
    const y = padY + (max === min ? usableH / 2 : ((max - point.price) / (max - min)) * usableH);
    return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(" ");
  const activeIndex = Math.min(state.step, points.length - 1);
  const active = points[activeIndex];
  const activeX = padX + (usableW * activeIndex) / Math.max(1, points.length - 1);
  const activeY = padY + (max === min ? usableH / 2 : ((max - active.price) / (max - min)) * usableH);

  const areaPath = `${path} L ${padX + usableW} ${height - padY} L ${padX} ${height - padY} Z`;

  els.chart.innerHTML = `
    <defs>
      <linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="rgba(31,85,81,0.34)"></stop>
        <stop offset="100%" stop-color="rgba(31,85,81,0.02)"></stop>
      </linearGradient>
    </defs>
    <rect x="0" y="0" width="${width}" height="${height}" rx="18" fill="transparent"></rect>
    <path d="${areaPath}" fill="url(#chartFill)"></path>
    <path d="${path}" fill="none" stroke="#1f5551" stroke-width="4" stroke-linecap="round"></path>
    <line x1="${activeX}" y1="${padY}" x2="${activeX}" y2="${height - padY}" stroke="rgba(124,47,28,0.28)" stroke-dasharray="6 6"></line>
    <circle cx="${activeX}" cy="${activeY}" r="8" fill="#c85c3f" stroke="#fff8f0" stroke-width="3"></circle>
  `;
}

function computeMetrics() {
  const scenario = currentScenario();
  const point = currentPoint();
  const noise = currentNoise();
  const actions = state.logs.length;
  const buys = state.logs.filter((log) => log.action === "BUY").length;
  const noiseWeightedActions = state.logs.filter((log) => Math.abs(log.noiseSentiment) >= 0.5).length;
  const actionFrequency = actions / Math.max(1, state.step + 1);
  const noiseSusceptibility = noiseWeightedActions / Math.max(1, actions);
  const volatility = scenario.priceTrack.reduce((sum, item) => sum + Math.abs(item.ret), 0) / scenario.priceTrack.length;
  const stress = actions === 0 ? 0 : (actionFrequency / Math.max(0.01, volatility)) * (1 + Math.abs(noise?.sentiment || 0));
  const positiveBounce = scenario.playbook === "fake_reversal" ? scenario.priceTrack.filter((item) => item.ret > 0).length : 0;
  const deception = scenario.playbook === "fake_reversal"
    ? Math.min(1, (buys / Math.max(1, actions)) * positiveBounce * 0.28 * (1 + Math.max(0, noise?.sentiment || 0)))
    : Math.min(1, noiseSusceptibility * 0.65);

  return {
    actionFrequency,
    noiseSusceptibility,
    stress,
    deception,
    bottomFishing: scenario.playbook === "fake_reversal" && buys >= 2,
    point,
  };
}

function renderLog() {
  if (state.logs.length === 0) {
    els.logBody.innerHTML = `<tr><td colspan="7">还没有记录。</td></tr>`;
    return;
  }
  els.logBody.innerHTML = state.logs.map((log, index) => `
    <tr>
      <td>${index + 1}</td>
      <td>${log.action}</td>
      <td>${log.sizePct}%</td>
      <td>${log.price.toFixed(2)}</td>
      <td class="${log.netPnl >= 0 ? "positive" : "negative"}">${formatPct(log.netPnl)}</td>
      <td class="negative">${formatPct(-log.costPct)}</td>
      <td>${log.noiseSentiment.toFixed(2)}</td>
    </tr>
  `).join("");
}

function computeFinalAssessment(metrics) {
  const totalActions = state.logs.length;
  const buyCount = state.logs.filter((log) => log.action === "BUY").length;
  const sellCount = state.logs.filter((log) => log.action === "SELL").length;
  const holdCount = state.logs.filter((log) => log.action === "HOLD").length;
  const panicSellRate = sellCount / Math.max(1, totalActions);
  const holdStrength = holdCount / Math.max(1, currentScenario().priceTrack.length);
  const overtradeScore = totalActions / Math.max(1, currentScenario().priceTrack.length);
  const riskPct = state.positionPct;

  let archetype = "稳态观察型";
  if (metrics.deception > 0.55) archetype = "抄底冲动型";
  else if (panicSellRate > 0.4) archetype = "恐慌止损型";
  else if (overtradeScore > 0.8) archetype = "高频冲动型";
  else if (holdStrength > 0.45) archetype = "趋势持有型";

  const riskLabel = riskPct >= 60 ? "高" : riskPct >= 30 ? "中" : "低";
  const holdLabel = holdStrength > 0.45 ? "强" : holdStrength > 0.2 ? "中" : "弱";
  const overtradeLabel = overtradeScore > 0.8 ? "高" : overtradeScore > 0.45 ? "中" : "低";

  const bulletPoints = [
    `测试场景：${currentScenario().title}`,
    `总反应次数 ${totalActions} 次，其中买入 ${buyCount} 次，卖出 ${sellCount} 次，观望 ${holdCount} 次。`,
    `噪音敏感度 ${metrics.noiseSusceptibility.toFixed(2)}，受骗指数 ${metrics.deception.toFixed(2)}。`,
    `建议：${metrics.deception > 0.55 ? "策略端应强制加入趋势确认，避免左侧抄底。"
      : panicSellRate > 0.4 ? "策略端应降低跳空与急跌暴露，并加强止损前的冷静期。"
      : overtradeScore > 0.8 ? "策略端应提高调仓阈值，减少震荡期无效操作。"
      : "可维持当前执行节奏，但仍需在高噪音场景中持续观察。"}`
  ];

  return {
    archetype,
    riskLabel,
    holdLabel,
    overtradeLabel,
    note: `测试完成。该用户在 ${currentScenario().playbook} 场景下呈现出 "${archetype}" 特征。`,
    bulletPoints,
  };
}

function renderFinalAssessment(metrics) {
  const finished = state.step >= currentScenario().priceTrack.length - 1;
  if (!finished) {
    els.resultArchetype.textContent = "等待测试完成";
    els.resultRisk.textContent = "-";
    els.resultHold.textContent = "-";
    els.resultOvertrade.textContent = "-";
    els.resultNote.textContent = "完整走完一个场景后，这里会给出该用户的交易性格结果。";
    els.resultList.innerHTML = "<li>等待测试完成。</li>";
    return;
  }

  const assessment = computeFinalAssessment(metrics);
  els.resultArchetype.textContent = assessment.archetype;
  els.resultRisk.textContent = assessment.riskLabel;
  els.resultHold.textContent = assessment.holdLabel;
  els.resultOvertrade.textContent = assessment.overtradeLabel;
  els.resultNote.textContent = assessment.note;
  els.resultList.innerHTML = assessment.bulletPoints.map((item) => `<li>${item}</li>`).join("");
}

function renderStrategyPackage(snapshot) {
  const pkg = snapshot.strategy_package;
  if (!pkg) {
    els.strategyNote.textContent = "提交交易标的并开始迭代后，这里会显示策略包。";
    els.strategyList.innerHTML = "<li>等待策略生成。</li>";
    return;
  }
  const checks = snapshot.strategy_checks || [];
  const failed = checks.some((item) => item.status === "fail");
  const candidate = pkg.candidate || {};
  const firstSignal = (candidate.signals || [])[0] || null;
  els.strategyNote.textContent = failed
    ? `第 ${pkg.iteration_no} 轮策略未通过检查，必须继续重迭代。`
    : `当前是第 ${pkg.iteration_no} 轮策略迭代。`;
  const items = [
    `策略类型：${pkg.strategy_type}`,
    `交易频次：${pkg.trading_preferences?.trading_frequency || "-"}`,
    `偏好周期：${pkg.trading_preferences?.preferred_timeframe || "-"}`,
    `交易标的池：${pkg.selected_universe.join(", ")}`,
    `预期收益区间：${(pkg.expected_return_range[0] * 100).toFixed(1)}% - ${(pkg.expected_return_range[1] * 100).toFixed(1)}%`,
    `最大潜在亏损：${(pkg.max_potential_loss * 100).toFixed(1)}%`,
    `预期回撤：${(pkg.expected_drawdown * 100).toFixed(1)}%`,
    `仓位上限：${(pkg.position_limit * 100).toFixed(1)}%`,
    `行为兼容度：${pkg.behavioral_compatibility.toFixed(2)}`,
    `用户反馈：${pkg.feedback || "无"}`,
    `候选策略版本：${candidate.version || "-"}`,
    `候选策略 ID：${candidate.strategy_id || "-"}`,
  ];
  if (firstSignal) {
    items.push(`首个信号：${firstSignal.symbol} / ${firstSignal.action} / conviction ${(firstSignal.conviction || 0).toFixed(2)}`);
    (firstSignal.rationale || []).slice(0, 3).forEach((line, index) => {
      items.push(`信号依据 ${index + 1}：${line}`);
    });
  }
  Object.entries(candidate.parameters || {}).forEach(([key, value]) => {
    items.push(`参数 ${key}: ${typeof value === "number" ? value.toFixed(4) : value}`);
  });
  els.strategyList.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
}

function renderStrategyChecks(snapshot) {
  const checks = snapshot.strategy_checks || [];
  if (checks.length === 0) {
    els.checkNote.textContent = "每个策略版本都必须通过完整性与压力测试检查。";
    els.checkGrid.innerHTML = `
      <div class="check-card">
        <strong>等待策略生成。</strong>
        <p>Integrity Checker 与 Stress and Overfit Checker 还未运行。</p>
      </div>
    `;
    return;
  }

  const failed = checks.some((item) => item.status === "fail");
  els.checkNote.textContent = failed
    ? "当前版本未通过检查，必须继续生成下一版策略。"
    : "当前版本已完成两类发布前检查。";

  els.checkGrid.innerHTML = checks.map((item) => {
    const flags = (item.flags || []).length
      ? `<ul class="check-list">${item.flags.map((flag) => `<li>${flag}</li>`).join("")}</ul>`
      : `<p class="check-empty">未发现额外警报。</p>`;
    const fixes = (item.required_fix_actions || []).length
      ? `<ul class="check-list">${item.required_fix_actions.map((fix) => `<li>${fix}</li>`).join("")}</ul>`
      : `<p class="check-empty">当前无需额外修复动作。</p>`;
    const metrics = Object.entries(item.metrics || {})
      .map(([key, value]) => `<li>${key}: ${typeof value === "number" ? value.toFixed(4) : value}</li>`)
      .join("");
    return `
      <article class="check-card check-${item.status}">
        <div class="check-head">
          <strong>${item.title}</strong>
          <span class="status-chip ${item.status === "fail" ? "danger-chip" : item.status === "warning" ? "warn-chip" : "success-chip"}">${item.status.toUpperCase()}</span>
        </div>
        <p class="check-summary">score ${item.score.toFixed(2)} · ${item.summary}</p>
        <p>${item.detail}</p>
        <p class="check-label">Flags</p>
        ${flags}
        <p class="check-label">Required Fix Actions</p>
        ${fixes}
        <p class="check-label">Metrics</p>
        <ul class="check-list">${metrics}</ul>
      </article>
    `;
  }).join("");
}

function renderMonitors(snapshot) {
  const monitors = snapshot.monitors || [];
  if (monitors.length === 0) {
    els.monitorList.innerHTML = "<li>等待部署或策略阶段完成。</li>";
    return;
  }
  els.monitorList.innerHTML = monitors.map((item) => `<li>[${item.monitor_type}] ${item.title}: ${item.detail}</li>`).join("");
}

function applySnapshot(snapshot) {
  state.sessionId = snapshot.session_id;
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(snapshot));
  els.sessionStatus.textContent = `Session ${snapshot.session_id} | phase=${snapshot.phase} | status=${snapshot.status}`;
  highlightFlow(snapshot.phase);
  if (snapshot.behavioral_report) {
    els.resultArchetype.textContent = snapshot.behavioral_report.noise_sensitivity > 0.6 ? "高噪音敏感型" : "相对稳态型";
    els.resultRisk.textContent = `${(snapshot.behavioral_report.recommended_risk_ceiling * 100).toFixed(0)}% ceiling`;
    els.resultHold.textContent = snapshot.behavioral_report.hold_strength.toFixed(2);
    els.resultOvertrade.textContent = snapshot.behavioral_report.overtrading_tendency.toFixed(2);
    els.resultNote.textContent = "Behavioral Profiler 已输出结构化性格报告。";
    els.resultList.innerHTML = Object.entries(snapshot.behavioral_report)
      .map(([key, value]) => `<li>${key}: ${typeof value === "number" ? value.toFixed(2) : value}</li>`)
      .join("");
    els.profilerJsonPanel.textContent = JSON.stringify(
      {
        user_id: snapshot.session_id,
        behavioral_profile: snapshot.behavioral_report,
      },
      null,
      2,
    );
    applyBehaviorRecommendation(snapshot.behavioral_report);
  }
  if (snapshot.execution_mode) {
    els.deploymentNote.textContent = snapshot.execution_mode === "autonomous"
      ? "当前为自动交易模式，监控信号可直接约束执行。"
      : "当前为仅建议模式，系统不会自动下单。";
  }
  if (snapshot.strategy_package?.strategy_type) {
    els.strategyTypeInput.value = snapshot.strategy_package.strategy_type;
  }
  if (snapshot.trading_preferences) {
    els.frequencyInput.value = snapshot.trading_preferences.trading_frequency;
    renderTradingPreferenceOptions();
    els.timeframeInput.value = snapshot.trading_preferences.preferred_timeframe;
    renderTimeframeNote();
    els.preferenceRationaleInput.value = snapshot.trading_preferences.rationale || "";
  }
  updatePreferenceConflict(snapshot);
  renderStrategyPackage(snapshot);
  renderStrategyChecks(snapshot);
  renderMonitors(snapshot);
}

function highlightFlow(phase) {
  [
    els.flowCreated,
    els.flowSim,
    els.flowReport,
    els.flowUniverse,
    els.flowStrategy,
    els.flowDeploy,
  ].forEach((element) => element.classList.remove("step-active"));

  if (phase === "created") els.flowCreated.classList.add("step-active");
  else if (phase === "simulation_in_progress") els.flowSim.classList.add("step-active");
  else if (phase === "profiler_ready") els.flowReport.classList.add("step-active");
  else if (phase === "universe_ready") els.flowUniverse.classList.add("step-active");
  else if (phase === "strategy_training" || phase === "strategy_checked" || phase === "strategy_rework_required" || phase === "strategy_approved") els.flowStrategy.classList.add("step-active");
  else if (phase === "autonomous_active" || phase === "advice_only_active") els.flowDeploy.classList.add("step-active");
}

function updateView() {
  const scenario = currentScenario();
  const point = currentPoint();
  const noise = currentNoise();
  const metrics = computeMetrics();

  els.playbookChip.textContent = scenario.playbook;
  els.cohortChip.textContent = scenario.cohort;
  els.stepChip.textContent = `Step ${Math.min(state.step + 1, scenario.priceTrack.length)} / ${scenario.priceTrack.length}`;
  els.title.textContent = scenario.title;
  els.currentPrice.textContent = point.price.toFixed(2);
  els.currentDrawdown.textContent = formatPct(point.drawdown);
  els.currentIv.textContent = point.iv.toFixed(2);
  els.currentTime.textContent = `Time: ${point.t}`;
  els.currentTruth.textContent = scenario.truth;

  els.noiseHeadline.textContent = noise ? noise.headline : "无噪音";
  els.noiseBody.textContent = noise ? noise.body : "当前是 control 组，没有叙事干扰。";
  els.noiseChannel.textContent = noise ? noise.channel : "no-channel";
  els.noiseSentiment.textContent = `sentiment ${noise ? noise.sentiment.toFixed(2) : "0.00"}`;

  els.positionState.textContent = state.position ? `${state.position} @ ${state.entryPrice.toFixed(2)}` : "Flat";
  els.sizeState.textContent = state.position ? `${state.positionPct}%` : "0%";
  const net = computeNetPnl(point);
  const impact = describeImpact(net.netAmount);
  els.pnlState.textContent = formatPct(net.netPct);
  els.pnlState.className = net.netPct >= 0 ? "positive" : "negative";
  els.costState.textContent = formatPct(-state.totalCostPct);
  els.costState.className = "negative";
  els.stressState.textContent = metrics.stress.toFixed(2);
  els.impactHeadline.textContent = impact.headline;
  els.impactBody.textContent = `${impact.body} 当前累计交易成本 ${formatMoney((state.totalCostPct / 100) * Math.max(state.positionSize, state.notionalCapital * 0.25))}。`;
  els.actionFrequency.textContent = metrics.actionFrequency.toFixed(2);
  els.noiseScore.textContent = metrics.noiseSusceptibility.toFixed(2);
  els.bottomFishing.textContent = metrics.bottomFishing ? "Yes" : "No";
  els.deceptionScore.textContent = metrics.deception.toFixed(2);

  if (scenario.playbook === "fake_reversal" && metrics.deception > 0.5) {
    els.profilerNote.textContent = "受骗指数偏高：用户在反抽窗口主动加仓，存在明显左侧抄底倾向。";
  } else if (metrics.stress > 0.45) {
    els.profilerNote.textContent = "压力指数上升：动作频率相对波动过高，存在情绪化干预风险。";
  } else if (metrics.noiseSusceptibility > 0.5) {
    els.profilerNote.textContent = "噪音敏感度偏高：用户操作与高情绪叙事同时出现。";
  } else {
    els.profilerNote.textContent = "当前操作仍较克制，尚未暴露明显偏差。";
  }

  drawChart();
  renderLog();
  renderFinalAssessment(metrics);
}

function logAction(action) {
  normalizeSettings();
  const point = currentPoint();
  const noise = currentNoise();
  let executed = false;

  if (action === "BUY" && !state.position) {
    state.position = "LONG";
    state.entryPrice = point.price;
    state.positionSize = state.notionalCapital * (state.positionPct / 100);
    state.totalCostPct += tradeCostPct();
    executed = true;
  } else if (action === "SELL" && state.position === "LONG") {
    state.totalCostPct += tradeCostPct();
    state.position = null;
    state.entryPrice = null;
    executed = true;
  }
  const net = computeNetPnl(point);

  state.logs.push({
    action,
    sizePct: executed || state.positionSize > 0 ? state.positionPct : 0,
    price: point.price,
    netPnl: net.netPct,
    costPct: executed ? tradeCostPct() : 0,
    noiseSentiment: noise ? noise.sentiment : 0,
  });
  if (state.sessionId) {
    api(`/api/sessions/${state.sessionId}/simulation/events`, {
      method: "POST",
      body: JSON.stringify({
        scenario_id: currentScenario().id,
        price_drawdown_pct: point.drawdown,
        action: action.toLowerCase(),
        noise_level: Math.abs(noise ? noise.sentiment : 0),
        sentiment_pressure: noise ? noise.sentiment : 0,
        latency_seconds: 45,
      }),
    }).catch(() => {});
  }
  updateView();
}

function nextStep() {
  const scenario = currentScenario();
  if (state.step < scenario.priceTrack.length - 1) {
    state.step += 1;
    updateView();
  }
}

function resetScenario() {
  normalizeSettings();
  state.step = 0;
  state.position = null;
  state.entryPrice = null;
  state.positionSize = 0;
  state.totalCostPct = 0;
  state.logs = [];
  updateView();
}

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", () => logAction(button.dataset.action));
});
els.nextStep.addEventListener("click", nextStep);
els.reset.addEventListener("click", resetScenario);
els.capitalInput.addEventListener("change", () => {
  normalizeSettings();
  updateView();
});
els.positionInput.addEventListener("change", () => {
  normalizeSettings();
  updateView();
});
els.createSession.addEventListener("click", async () => {
  try {
    const created = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        user_name: els.userNameInput.value || "User",
        starting_capital: Number(els.startingCapitalInput.value || 500000),
      }),
    });
    applySnapshot(created);
    const snapshot = await api(`/api/sessions/${created.session_id}/generate-scenarios`, { method: "POST" });
    applySnapshot(snapshot);
    els.sessionStatus.textContent = `Session ${snapshot.session_id} 已创建，测试数据已生成。请开始模拟测试。`;
    scrollToSimulation();
  } catch (error) {
    checkApiHealth();
    els.sessionStatus.textContent = `创建会话失败: ${error.message}`;
  }
});
els.generateScenarios.addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    const snapshot = await api(`/api/sessions/${state.sessionId}/generate-scenarios`, { method: "POST" });
    applySnapshot(snapshot);
    scrollToSimulation();
  } catch (error) {
    checkApiHealth();
    els.sessionStatus.textContent = `生成测试数据失败: ${error.message}`;
  }
});
els.frequencyInput.addEventListener("change", renderTradingPreferenceOptions);
els.timeframeInput.addEventListener("change", renderTimeframeNote);
els.savePreferences.addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    const snapshot = await api(`/api/sessions/${state.sessionId}/trading-preferences`, {
      method: "POST",
      body: JSON.stringify({
        trading_frequency: els.frequencyInput.value,
        preferred_timeframe: els.timeframeInput.value,
        rationale: els.preferenceRationaleInput.value || null,
      }),
    });
    applySnapshot(snapshot);
  } catch (error) {
    checkApiHealth();
    els.sessionStatus.textContent = `保存交易偏好失败: ${error.message}`;
  }
});
els.applyRecommendation.addEventListener("click", () => {
  if (!state.sessionId) return;
  const reportText = els.profilerJsonPanel.textContent || "{}";
  try {
    const payload = JSON.parse(reportText);
    applyBehaviorRecommendation(payload.behavioral_profile || {});
  } catch (error) {
    els.recommendationNote.textContent = "当前还没有可应用的测试推荐，请先完成模拟测试。";
  }
});
els.applyStrategyRecommendation.addEventListener("click", () => {
  const reportText = els.profilerJsonPanel.textContent || "{}";
  try {
    const payload = JSON.parse(reportText);
    const report = payload.behavioral_profile || {};
    if (report.recommended_strategy_type) {
      els.strategyTypeInput.value = report.recommended_strategy_type;
      els.strategyRecommendationNote.textContent = report.strategy_type_recommendation_note || "系统已应用默认策略类型推荐。";
      return;
    }
  } catch (error) {
  }
  els.strategyRecommendationNote.textContent = "当前还没有可应用的策略类型推荐，请先完成模拟测试。";
});
els.completeSimulation.addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    const snapshot = await api(`/api/sessions/${state.sessionId}/simulation/complete`, {
      method: "POST",
      body: JSON.stringify({ symbol: "SIM" }),
    });
    applySnapshot(snapshot);
  } catch (error) {
    checkApiHealth();
    els.resultNote.textContent = `生成测试报告失败: ${error.message}`;
  }
});
els.submitUniverse.addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    const snapshot = await api(`/api/sessions/${state.sessionId}/trade-universe`, {
      method: "POST",
      body: JSON.stringify({
        input_type: els.universeTypeInput.value,
        symbols: els.universeSymbolsInput.value.split(",").map((item) => item.trim()).filter(Boolean),
        allow_overfit_override: false,
      }),
    });
    applySnapshot(snapshot);
  } catch (error) {
    checkApiHealth();
    els.strategyNote.textContent = `提交交易标的失败: ${error.message}`;
  }
});
els.iterateStrategy.addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    const snapshot = await api(`/api/sessions/${state.sessionId}/strategy/iterate`, {
      method: "POST",
      body: JSON.stringify({
        feedback: els.strategyFeedbackInput.value,
        strategy_type: els.strategyTypeInput.value,
      }),
    });
    applySnapshot(snapshot);
  } catch (error) {
    checkApiHealth();
    els.strategyNote.textContent = `策略迭代失败: ${error.message}`;
  }
});
els.approveStrategy.addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    const snapshot = await api(`/api/sessions/${state.sessionId}/strategy/approve`, { method: "POST" });
    applySnapshot(snapshot);
  } catch (error) {
    checkApiHealth();
    els.strategyNote.textContent = `策略确认失败: ${error.message}`;
  }
});
els.setAutonomous.addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    const snapshot = await api(`/api/sessions/${state.sessionId}/deployment`, {
      method: "POST",
      body: JSON.stringify({ execution_mode: "autonomous" }),
    });
    applySnapshot(snapshot);
  } catch (error) {
    checkApiHealth();
    els.deploymentNote.textContent = `设置自动交易失败: ${error.message}`;
  }
});
els.setAdviceOnly.addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    const snapshot = await api(`/api/sessions/${state.sessionId}/deployment`, {
      method: "POST",
      body: JSON.stringify({ execution_mode: "advice_only" }),
    });
    applySnapshot(snapshot);
  } catch (error) {
    checkApiHealth();
    els.deploymentNote.textContent = `设置仅建议模式失败: ${error.message}`;
  }
});

initSelect();
resetScenario();
renderTradingPreferenceOptions();
async function bootstrap() {
  try {
    await loadClientConfig();
    setDisconnectedStatus(`正在检查后端 ${state.config.apiBase} ...`);
    await checkApiHealth();
  } catch (error) {
    applyStatusChip(els.frontendStatusChip, "前端配置异常", "error");
    applyStatusChip(els.apiStatusChip, "API 未连接", "error");
    applyStatusChip(els.databaseStatusChip, "数据库未知", "error");
    els.apiStatusNote.textContent = "前端配置文件加载失败，请检查 web/config.json。";
    setBackendControlsDisabled(true);
  }
}

bootstrap();
