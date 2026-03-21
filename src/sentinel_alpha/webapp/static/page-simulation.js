const CAMPAIGN_STORAGE_PREFIX = "sentinel-alpha:campaign:";
const CAMPAIGN_STATE_PREFIX = "sentinel-alpha:campaign-state:";
const DAILY_PAUSE_BAR_INDEXES = [15, 31, 47, 63, 77];

const REGIMES = [
  {
    key: "uptrend",
    label: "单边上涨",
    bias: 0.0018,
    volatility: 0.0035,
    gapBias: 0.002,
    noiseSentiment: -0.25,
    noiseHeadline: "估值过高的讨论再次升温",
    noiseBody: "盘中分歧扩大，追高与踏空情绪都在升温。",
  },
  {
    key: "gap",
    label: "跳空缺口",
    bias: -0.0006,
    volatility: 0.0055,
    gapBias: -0.035,
    noiseSentiment: -0.75,
    noiseHeadline: "突发消息冲击盘前情绪",
    noiseBody: "盘前消息密集发酵，市场对后续走势存在明显分歧。",
  },
  {
    key: "oscillation",
    label: "猴市震荡",
    bias: 0.0,
    volatility: 0.0048,
    gapBias: 0.0,
    noiseSentiment: 0.12,
    noiseHeadline: "市场观点再次分裂",
    noiseBody: "多空观点快速切换，盘中一致性较弱。",
  },
  {
    key: "drawdown",
    label: "深度回撤",
    bias: -0.0022,
    volatility: 0.0042,
    gapBias: -0.01,
    noiseSentiment: 0.52,
    noiseHeadline: "抄底言论开始占据主流",
    noiseBody: "市场上关于“便宜筹码”的讨论明显增多。",
  },
  {
    key: "fake_reversal",
    label: "假反弹",
    bias: -0.0014,
    volatility: 0.0058,
    gapBias: 0.006,
    noiseSentiment: 0.78,
    noiseHeadline: "V 型反转的声音非常响",
    noiseBody: "反弹出现后，关于趋势反转的讨论快速升温。",
  },
  {
    key: "downtrend",
    label: "单边下跌",
    bias: -0.0026,
    volatility: 0.0038,
    gapBias: -0.005,
    noiseSentiment: -0.32,
    noiseHeadline: "下跌逻辑被不断合理化",
    noiseBody: "市场对下跌原因的解释越来越多，空头叙事占优。",
  },
];

const HEADLINE_TEMPLATES = {
  uptrend: [
    { source: "宏观快讯", title: "估值争议升温，但资金继续推高板块龙头", body: "场外资金担心泡沫，盘中买盘仍然偏强。", tone: "neutral" },
    { source: "卖方晨报", title: "又有机构上调目标价，评论区反而开始劝退", body: "主流观点继续上修预期，但分歧也在扩大。", tone: "positive" },
  ],
  gap: [
    { source: "盘前突发", title: "缺口低开引发黑天鹅猜测", body: "盘前传闻密集，市场仍在快速定价。", tone: "negative" },
    { source: "快讯聚合", title: "利空与辟谣同时出现，市场先用价格投票", body: "多条消息交错出现，短线资金反应剧烈。", tone: "neutral" },
  ],
  oscillation: [
    { source: "论坛热帖", title: "突破派和回调派再次打起来了", body: "盘中观点切换很快，市场暂未形成一致方向。", tone: "neutral" },
    { source: "量化观察", title: "区间震荡继续，盘中分歧持续放大", body: "短线信号频繁出现，市场节奏偏碎。", tone: "negative" },
  ],
  drawdown: [
    { source: "抄底情报", title: "评论区开始喊“跌越多越便宜”", body: "抄底观点开始成为热门讨论。", tone: "positive" },
    { source: "风险快评", title: "基本面恶化被弱化，情绪开始替代分析", body: "市场对风险的解读分歧明显。", tone: "negative" },
  ],
  fake_reversal: [
    { source: "热点推送", title: "V 型反转词条冲上榜首", body: "反转预期快速升温，短线情绪明显活跃。", tone: "positive" },
    { source: "盘后复盘", title: "反弹声量越大，分歧也越大", body: "反弹持续性仍有较大争议。", tone: "negative" },
  ],
  downtrend: [
    { source: "策略点评", title: "利空逻辑越来越顺，市场谨慎情绪持续", body: "空头叙事占优，买盘承接偏弱。", tone: "negative" },
    { source: "市场扫描", title: "连续阴跌后，账户波动开始放大", body: "市场成交偏谨慎，情绪仍未明显修复。", tone: "neutral" },
  ],
};

const DISCUSSION_TEMPLATES = {
  uptrend: [
    { author: "群聊-多头", text: "都涨成这样了还不敢拿？一卖就飞。", tone: "positive" },
    { author: "群聊-空头", text: "这种位置追进去就是接盘，别到时候哭。", tone: "negative" },
    { author: "KOL 评论", text: "涨得慢最磨人，因为你总觉得还有更好上车点。", tone: "neutral" },
  ],
  gap: [
    { author: "盘前喊单", text: "这缺口不补就是大问题，赶紧先跑。", tone: "negative" },
    { author: "短线群", text: "恐慌盘出来了，越慌越是机会。", tone: "positive" },
    { author: "老股民", text: "先看半小时，别让消息替你点按钮。", tone: "neutral" },
  ],
  oscillation: [
    { author: "群友 A", text: "这次突破是真的，我已经满仓了。", tone: "positive" },
    { author: "群友 B", text: "又是假突破，你们怎么还没学会。", tone: "negative" },
    { author: "交易室", text: "震荡盘最难的是接受没必要天天交易。", tone: "neutral" },
  ],
  drawdown: [
    { author: "抄底派", text: "跌成这样不买，难道等涨回去再买？", tone: "positive" },
    { author: "风控派", text: "下跌趋势里摊平，很容易把小错做成大错。", tone: "negative" },
    { author: "老手提醒", text: "最危险的不是下跌，是你开始觉得自己必须做点什么。", tone: "neutral" },
  ],
  fake_reversal: [
    { author: "热帖", text: "底部已现，这里不上车后面只能追高。", tone: "positive" },
    { author: "冷眼旁观", text: "这种反弹最喜欢骗抄底的人。", tone: "negative" },
    { author: "市场旁白", text: "下降趋势中的反弹，经常会引发对趋势是否反转的争论。", tone: "neutral" },
  ],
  downtrend: [
    { author: "空头群", text: "越跌越不敢卖，这就是人性。", tone: "negative" },
    { author: "套牢盘", text: "已经亏这么多了，卖了更难受。", tone: "negative" },
    { author: "风控讨论", text: "真正的纪律不是知道止损，而是舍得执行。", tone: "neutral" },
  ],
};

const state = {
  campaign: null,
  campaignState: null,
  feeRatePct: 0.12,
  slippagePct: 0.18,
};

function activeSessionId() {
  return loadStoredSnapshot()?.session_id || "anonymous";
}

function campaignKey() {
  return `${CAMPAIGN_STORAGE_PREFIX}${activeSessionId()}`;
}

function campaignStateKey() {
  return `${CAMPAIGN_STATE_PREFIX}${activeSessionId()}`;
}

function readJson(key) {
  try {
    return JSON.parse(window.localStorage.getItem(key) || "null");
  } catch (error) {
    return null;
  }
}

function writeJson(key, payload) {
  window.localStorage.setItem(key, JSON.stringify(payload));
}

function seededRandom(seed) {
  let t = seed >>> 0;
  return function next() {
    t += 0x6d2b79f5;
    let n = Math.imul(t ^ (t >>> 15), 1 | t);
    n ^= n + Math.imul(n ^ (n >>> 7), 61 | n);
    return ((n ^ (n >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(value) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

function pick(random, values) {
  return values[Math.floor(random() * values.length)];
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function regimeSchedule(random, dayCount) {
  const mandatory = [...REGIMES];
  for (let index = mandatory.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1));
    [mandatory[index], mandatory[swapIndex]] = [mandatory[swapIndex], mandatory[index]];
  }
  const schedule = [...mandatory];
  while (schedule.length < dayCount) {
    schedule.push(pick(random, REGIMES));
  }
  return schedule.slice(0, dayCount);
}

function intradayShapeLibrary(regimeKey) {
  const base = [
    { key: "w_reversal", label: "W", anchors: [0, -0.55, -0.2, -0.62, 0.05, 0.38] },
    { key: "n_breakdown", label: "N", anchors: [0, 0.45, 0.12, 0.58, 0.18, -0.42] },
    { key: "v_reversal", label: "V", anchors: [0, -0.88, -0.35, 0.22, 0.62, 0.92] },
    { key: "a_distribution", label: "A", anchors: [0, 0.72, 0.28, -0.08, -0.42, -0.76] },
    { key: "range_fake_break", label: "假突破", anchors: [0, 0.22, 0.48, -0.12, 0.16, -0.08] },
    { key: "pm_reversal", label: "午后反转", anchors: [0, -0.22, -0.44, -0.18, 0.22, 0.68] },
  ];
  if (regimeKey === "uptrend") {
    return [base[0], base[2], base[4], base[5]];
  }
  if (regimeKey === "fake_reversal") {
    return [base[1], base[3], base[4], { key: "bear_rally", label: "反抽", anchors: [0, -0.42, -0.76, 0.12, 0.38, -0.58] }];
  }
  if (regimeKey === "oscillation") {
    return [base[0], base[1], base[4], { key: "box_chop", label: "箱体", anchors: [0, 0.18, -0.08, 0.14, -0.12, 0.06] }];
  }
  if (regimeKey === "drawdown" || regimeKey === "downtrend") {
    return [base[1], base[3], { key: "stair_fall", label: "台阶下跌", anchors: [0, -0.18, -0.42, -0.36, -0.64, -0.92] }];
  }
  if (regimeKey === "gap") {
    return [base[2], base[3], { key: "gap_and_go", label: "跳空延续", anchors: [0, 0.58, 0.72, 0.88, 0.94, 1.02] }, { key: "gap_fill", label: "回补缺口", anchors: [0, -0.26, -0.48, -0.62, -0.36, -0.08] }];
  }
  return base;
}

function interpolateAnchors(anchors, t) {
  const segments = anchors.length - 1;
  const scaled = Math.min(segments, Math.max(0, t * segments));
  const left = Math.floor(scaled);
  const right = Math.min(segments, left + 1);
  const ratio = scaled - left;
  return anchors[left] + (anchors[right] - anchors[left]) * ratio;
}

function generateDayBars(previousClose, regime, random) {
  const bars = [];
  const intervalMinutes = 5;
  const openGap = regime.gapBias + (random() - 0.5) * regime.volatility * 3;
  let price = previousClose * (1 + openGap);
  let high = price;
  let low = price;
  const open = price;
  const intradayShockBar = Math.floor(random() * 78);
  const shape = pick(random, intradayShapeLibrary(regime.key));

  for (let barIndex = 0; barIndex < 78; barIndex += 1) {
    const t = barIndex / 77;
    const cyclical = Math.sin(barIndex / 9) * regime.volatility * 0.28;
    const shaped = interpolateAnchors(shape.anchors, t) * regime.volatility * 1.2;
    let move = regime.bias + cyclical + shaped + (random() - 0.5) * regime.volatility * 0.55;
    if (regime.key === "fake_reversal" && barIndex > 18 && barIndex < 40) {
      move += 0.0032;
    }
    if (regime.key === "fake_reversal" && barIndex >= 40) {
      move -= 0.004;
    }
    if (regime.key === "oscillation") {
      move += Math.sin(barIndex / 3.2) * 0.0026;
    }
    if (barIndex === intradayShockBar) {
      move += (random() - 0.5) * regime.volatility * 7;
    }
    if (barIndex === Math.floor(78 * 0.5) && (shape.key === "w_reversal" || shape.key === "n_breakdown")) {
      move += (random() - 0.5) * regime.volatility * 5;
    }
    const openPrice = price;
    const closePrice = Math.max(1, openPrice * (1 + move));
    const wickScale = Math.abs(move) + regime.volatility * 0.6;
    const highPrice = Math.max(openPrice, closePrice) * (1 + random() * wickScale);
    const lowPrice = Math.min(openPrice, closePrice) * (1 - random() * wickScale);
    price = closePrice;
    high = Math.max(high, highPrice);
    low = Math.min(low, lowPrice);
    bars.push({
      index: barIndex,
      timeLabel: `${String(9 + Math.floor((30 + barIndex * intervalMinutes) / 60)).padStart(2, "0")}:${String((30 + barIndex * intervalMinutes) % 60).padStart(2, "0")}`,
      open: openPrice,
      high: highPrice,
      low: lowPrice,
      close: closePrice,
      volume: Math.round(900 + random() * 3800 + Math.abs(move) * 220000),
    });
  }

  const close = bars[bars.length - 1].close;
  const closeReturnPct = ((close / previousClose) - 1) * 100;
  const drawdownPct = ((low / previousClose) - 1) * 100;
  const reboundPct = ((high / low) - 1) * 100;
  const iv = 0.18 + Math.abs(closeReturnPct) * 0.08 + Math.abs(drawdownPct) * 0.03;

  return {
    open,
    high,
    low,
    close,
    closeReturnPct,
    drawdownPct,
    reboundPct,
    iv,
    patternKey: shape.key,
    patternLabel: shape.label,
    bars,
  };
}

function generateCampaign(sessionId) {
  const random = seededRandom(hashString(sessionId));
  const dayCount = 30 + Math.floor(random() * 31);
  const schedule = regimeSchedule(random, dayCount);
  const days = [];
  let previousClose = 100;
  const start = new Date("2026-01-05T09:30:00");

  for (let dayIndex = 0; dayIndex < dayCount; dayIndex += 1) {
    const regime = schedule[dayIndex];
    const generated = generateDayBars(previousClose, regime, random);
    const date = new Date(start.getTime() + dayIndex * 24 * 60 * 60 * 1000);
    const noiseShift = (random() - 0.5) * 0.25;
    const noiseSentiment = clamp(regime.noiseSentiment + noiseShift, -1, 1);
    const headlineFeed = HEADLINE_TEMPLATES[regime.key].map((item, index) => ({
      ...item,
      time: generated.bars[Math.min(generated.bars.length - 1, 6 + index * 18)].timeLabel,
    }));
    const discussionFeed = DISCUSSION_TEMPLATES[regime.key].map((item, index) => ({
      ...item,
      time: generated.bars[Math.min(generated.bars.length - 1, 10 + index * 14)].timeLabel,
    }));
    days.push({
      dayIndex,
      dateLabel: date.toISOString().slice(0, 10),
      regimeKey: regime.key,
      regimeLabel: regime.label,
      open: generated.open,
      high: generated.high,
      low: generated.low,
      close: generated.close,
      closeReturnPct: generated.closeReturnPct,
      drawdownPct: generated.drawdownPct,
      reboundPct: generated.reboundPct,
      iv: generated.iv,
      patternKey: generated.patternKey,
      patternLabel: generated.patternLabel,
      noiseHeadline: regime.noiseHeadline,
      noiseBody: regime.noiseBody,
      noiseSentiment,
      headlineFeed,
      discussionFeed,
      bars: generated.bars,
    });
    previousClose = generated.close;
  }

  return {
    sessionId,
    createdAt: new Date().toISOString(),
    dayCount,
    timeframe: "5m",
    cadence: "daily_decision",
    days,
  };
}

function initialCampaignState() {
  const capital = Number(document.querySelector("#capital-input")?.value || 500000);
  const orderAmount = Number(document.querySelector("#order-amount-input")?.value || 50000);
  const orderMode = document.querySelector("#order-mode-input")?.value || "amount";
  const initialLimitPrice = Number(document.querySelector("#limit-price-input")?.value || 100);
  return {
    currentDayIndex: 0,
    currentPauseIndex: 0,
    cash: capital,
    capitalBase: capital,
    capitalLocked: false,
    orderAmount,
    orderMode,
    limitPrice: initialLimitPrice,
    shares: 0,
    avgEntry: 0,
    realizedPnl: 0,
    accumulatedCost: 0,
    actionLog: [],
    completed: false,
  };
}

function loadCampaign() {
  const stored = readJson(campaignKey());
  if (stored?.days?.length) {
    return stored;
  }
  const generated = generateCampaign(activeSessionId());
  writeJson(campaignKey(), generated);
  return generated;
}

function loadCampaignState() {
  const stored = readJson(campaignStateKey());
  if (stored?.capitalBase) {
    return stored;
  }
  const created = initialCampaignState();
  writeJson(campaignStateKey(), created);
  return created;
}

function persistState() {
  writeJson(campaignStateKey(), state.campaignState);
}

function resetCampaignProgress() {
  state.campaign = generateCampaign(activeSessionId());
  state.campaignState = initialCampaignState();
  writeJson(campaignKey(), state.campaign);
  persistState();
}

function currentDay() {
  return state.campaign.days[Math.min(state.campaignState.currentDayIndex, state.campaign.days.length - 1)];
}

function currentPauseBarIndex() {
  return DAILY_PAUSE_BAR_INDEXES[Math.min(state.campaignState.currentPauseIndex || 0, DAILY_PAUSE_BAR_INDEXES.length - 1)];
}

function currentVisibleBars(day = currentDay()) {
  return day.bars.slice(0, currentPauseBarIndex() + 1);
}

function pauseDaySnapshot(day = currentDay()) {
  const visibleBars = currentVisibleBars(day);
  const firstBar = visibleBars[0];
  const lastBar = visibleBars[visibleBars.length - 1];
  const high = Math.max(...visibleBars.map((bar) => bar.high));
  const low = Math.min(...visibleBars.map((bar) => bar.low));
  const totalVolume = visibleBars.reduce((sum, bar) => sum + bar.volume, 0);
  const referenceClose = day.dayIndex > 0 ? state.campaign.days[day.dayIndex - 1].close : firstBar.open;
  return {
    bars: visibleBars,
    open: firstBar.open,
    high,
    low,
    close: lastBar.close,
    volume: totalVolume,
    timeLabel: lastBar.timeLabel,
    returnPct: ((lastBar.close / referenceClose) - 1) * 100,
    drawdownPct: ((low / referenceClose) - 1) * 100,
    reboundPct: ((high / Math.max(low, 0.0001)) - 1) * 100,
  };
}

function transactionCostRate() {
  return (state.feeRatePct + state.slippagePct) / 100;
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
  }).format(value);
}

function formatVolume(value) {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(2)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return `${Math.round(value)}`;
}

function syncOrderInputLabel() {
  const mode = document.querySelector("#order-mode-input")?.value || "amount";
  const label = document.querySelector("#order-value-label");
  const input = document.querySelector("#order-amount-input");
  if (!label || !input) return;
  if (mode === "shares") {
    label.textContent = "本次交易股数";
    input.min = "1";
    input.step = "1";
    if (Number(input.value) <= 0) {
      input.value = "100";
    }
  } else {
    label.textContent = "本次交易金额 (CNY)";
    input.min = "1000";
    input.step = "1000";
    if (Number(input.value) <= 0) {
      input.value = "50000";
    }
  }
}

function toneClass(tone) {
  return tone === "positive" ? "positive" : tone === "negative" ? "negative" : "neutral";
}

function markToMarket(close) {
  const cash = state.campaignState.cash;
  const positionValue = state.campaignState.shares * close;
  return cash + positionValue;
}

function unrealizedPnl(close) {
  if (state.campaignState.shares <= 0) {
    return 0;
  }
  return (close - state.campaignState.avgEntry) * state.campaignState.shares;
}

function drawIntradayChart(day, points) {
  const width = 740;
  const height = 320;
  const padX = 24;
  const padY = 18;
  const volumeHeight = 72;
  const priceHeight = height - padY * 2 - volumeHeight - 10;
  const prices = points.flatMap((point) => [point.high, point.low]);
  const volumes = points.map((point) => point.volume);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const maxVolume = Math.max(...volumes);
  const usableW = width - padX * 2;
  const candleWidth = usableW / Math.max(1, points.length) * 0.62;
  const priceY = (price) => padY + (max === min ? priceHeight / 2 : ((max - price) / (max - min)) * priceHeight);
  const volumeTop = padY + priceHeight + 14;

  const backgroundLines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = padY + priceHeight * ratio;
    return `<line x1="${padX}" y1="${y.toFixed(2)}" x2="${width - padX}" y2="${y.toFixed(2)}" stroke="rgba(31,42,42,0.10)" stroke-dasharray="4 6"></line>`;
  }).join("");

  const candles = points.map((point, index) => {
    const stepX = padX + (usableW * (index + 0.5)) / points.length;
    const openY = priceY(point.open);
    const closeY = priceY(point.close);
    const highY = priceY(point.high);
    const lowY = priceY(point.low);
    const bodyY = Math.min(openY, closeY);
    const bodyHeight = Math.max(2, Math.abs(closeY - openY));
    const candleClass = point.close >= point.open ? "#1f5551" : "#c85c3f";
    const volumeBarHeight = maxVolume === 0 ? 2 : Math.max(2, (point.volume / maxVolume) * volumeHeight);
    const volumeY = volumeTop + volumeHeight - volumeBarHeight;
    return `
      <line x1="${stepX.toFixed(2)}" y1="${highY.toFixed(2)}" x2="${stepX.toFixed(2)}" y2="${lowY.toFixed(2)}" stroke="${candleClass}" stroke-width="1.4"></line>
      <rect x="${(stepX - candleWidth / 2).toFixed(2)}" y="${bodyY.toFixed(2)}" width="${candleWidth.toFixed(2)}" height="${bodyHeight.toFixed(2)}" rx="1.5" fill="${candleClass}"></rect>
      <rect x="${(stepX - candleWidth / 2).toFixed(2)}" y="${volumeY.toFixed(2)}" width="${candleWidth.toFixed(2)}" height="${volumeBarHeight.toFixed(2)}" rx="1.5" fill="rgba(133,115,95,0.55)"></rect>
    `;
  }).join("");
  document.querySelector("#price-chart").innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" rx="20" fill="rgba(255,255,255,0.18)"></rect>
    ${backgroundLines}
    ${candles}
  `;
}

function drawCampaignChart() {
  const days = state.campaign.days;
  const width = 720;
  const height = 250;
  const padX = 24;
  const padY = 18;
  const values = days.flatMap((day) => [day.high, day.low]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const usableW = width - padX * 2;
  const usableH = height - padY * 2;
  const candleWidth = usableW / Math.max(1, days.length) * 0.55;
  const yFor = (price) => padY + (max === min ? usableH / 2 : ((max - price) / (max - min)) * usableH);
  const currentIndex = state.campaignState.currentDayIndex;
  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = padY + usableH * ratio;
    return `<line x1="${padX}" y1="${y.toFixed(2)}" x2="${width - padX}" y2="${y.toFixed(2)}" stroke="rgba(31,42,42,0.08)" stroke-dasharray="4 6"></line>`;
  }).join("");
  const candles = days.map((day, index) => {
    const x = padX + (usableW * (index + 0.5)) / days.length;
    const openY = yFor(day.open);
    const closeY = yFor(day.close);
    const highY = yFor(day.high);
    const lowY = yFor(day.low);
    const bodyY = Math.min(openY, closeY);
    const bodyHeight = Math.max(2, Math.abs(closeY - openY));
    const color = day.close >= day.open ? "#1f5551" : "#c85c3f";
    const highlight = index === currentIndex ? `stroke="rgba(124,47,28,0.75)" stroke-width="2.2"` : `stroke="${color}" stroke-width="1.2"`;
    return `
      <line x1="${x.toFixed(2)}" y1="${highY.toFixed(2)}" x2="${x.toFixed(2)}" y2="${lowY.toFixed(2)}" ${highlight}></line>
      <rect x="${(x - candleWidth / 2).toFixed(2)}" y="${bodyY.toFixed(2)}" width="${candleWidth.toFixed(2)}" height="${bodyHeight.toFixed(2)}" rx="1.5" fill="${color}" opacity="${index === currentIndex ? "1" : "0.78"}"></rect>
    `;
  }).join("");
  document.querySelector("#campaign-chart").innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" rx="20" fill="rgba(255,255,255,0.18)"></rect>
    ${gridLines}
    ${candles}
  `;
}

function renderHeadlineFeed(day) {
  const target = document.querySelector("#headline-feed");
  const timeThreshold = pauseDaySnapshot(day).timeLabel;
  const items = day.headlineFeed.filter((item) => item.time <= timeThreshold);
  target.innerHTML = items.map((item) => `
    <article class="headline-item ${toneClass(item.tone)}">
      <strong>${item.title}</strong>
      <p>${item.body}</p>
      <div class="item-meta">
        <span>${item.source}</span>
        <span>${item.time}</span>
      </div>
    </article>
  `).join("") || `
    <article class="headline-item">
      <strong>暂无新增新闻。</strong>
      <p>当前暂停点之前没有新的公开资讯流。</p>
    </article>
  `;
}

function renderDiscussionFeed(day) {
  const target = document.querySelector("#discussion-feed");
  const timeThreshold = pauseDaySnapshot(day).timeLabel;
  const items = day.discussionFeed.filter((item) => item.time <= timeThreshold);
  target.innerHTML = items.map((item) => `
    <article class="discussion-item ${toneClass(item.tone)}">
      <strong>${item.author}</strong>
      <p>${item.text}</p>
      <div class="item-meta">
        <span>${item.time}</span>
        <span>${item.tone}</span>
      </div>
    </article>
  `).join("") || `
    <article class="discussion-item">
      <strong>暂无新增讨论。</strong>
      <p>当前暂停点之前没有新的社区留言。</p>
    </article>
  `;
}

function renderLog() {
  const target = document.querySelector("#log-body");
  const logs = state.campaignState.actionLog;
  if (!logs.length) {
    target.innerHTML = `<tr><td colspan="14">还没有日度决策记录。</td></tr>`;
    return;
  }
  target.innerHTML = logs.map((entry, index) => `
    <tr>
      <td>${index + 1}</td>
      <td>${entry.dayLabel}</td>
      <td>${entry.action.toUpperCase()}</td>
      <td>${entry.status.toUpperCase()}</td>
      <td>${entry.amount > 0 ? formatMoney(entry.amount) : "-"}</td>
      <td>${entry.shares > 0 ? entry.shares.toFixed(2) : "-"}</td>
      <td>${entry.limitPrice > 0 ? entry.limitPrice.toFixed(2) : "-"}</td>
      <td>${entry.fillPrice > 0 ? entry.fillPrice.toFixed(2) : "-"}</td>
      <td>${formatMoney(entry.cashAfter)}</td>
      <td>${entry.positionAfter > 0 ? `${entry.positionAfter.toFixed(2)} 股` : "Flat"}</td>
      <td>${entry.regimeLabel}</td>
      <td>${formatPct(entry.dayReturnPct)}</td>
      <td>${formatPct(entry.dayDrawdownPct)}</td>
      <td>${entry.note}</td>
    </tr>
  `).join("");
}

function renderSummary() {
  const day = currentDay();
  const pauseSnapshot = pauseDaySnapshot(day);
  const equity = markToMarket(pauseSnapshot.close);
  const netPnl = equity - state.campaignState.capitalBase;
  const totalVolume = pauseSnapshot.volume;
  const previousClose = day.dayIndex > 0 ? state.campaign.days[day.dayIndex - 1].close : day.open;
  const openGapPct = ((pauseSnapshot.open / previousClose) - 1) * 100;
  const dayRangePct = ((pauseSnapshot.high / pauseSnapshot.low) - 1) * 100;
  const sentimentHeat = Math.round(Math.abs(day.noiseSentiment) * 100);
  const campaignStartClose = state.campaign.days[0].close;
  const campaignReturnPct = ((pauseSnapshot.close / campaignStartClose) - 1) * 100;
  document.querySelector("#campaign-chip").textContent = `${state.campaign.dayCount} 个交易日 / 5 分钟线`;
  document.querySelector("#step-chip").textContent = `Day ${state.campaignState.currentDayIndex + 1} / ${state.campaign.dayCount}`;
  document.querySelector("#pause-chip").textContent = `第 ${state.campaignState.currentPauseIndex + 1} 次暂停 / 5`;
  document.querySelector("#campaign-close").textContent = pauseSnapshot.close.toFixed(2);
  document.querySelector("#campaign-return").textContent = formatPct(campaignReturnPct);
  document.querySelector("#campaign-day-label").textContent = day.dateLabel;
  document.querySelector("#scenario-title").textContent = `${day.dateLabel} · ${day.regimeLabel}`;
  document.querySelector("#current-price").textContent = pauseSnapshot.close.toFixed(2);
  document.querySelector("#current-drawdown").textContent = formatPct(pauseSnapshot.drawdownPct);
  document.querySelector("#current-iv").textContent = day.iv.toFixed(2);
  document.querySelector("#current-time").textContent = `盘中暂停点 ${state.campaignState.currentPauseIndex + 1}/5 · 已显示到 ${pauseSnapshot.timeLabel}`;
  document.querySelector("#noise-headline").textContent = day.noiseHeadline;
  document.querySelector("#noise-body").textContent = day.noiseBody;
  document.querySelector("#noise-channel").textContent = `regime:${day.regimeKey}`;
  document.querySelector("#noise-sentiment").textContent = day.noiseSentiment.toFixed(2);
  document.querySelector("#position-state").textContent = state.campaignState.shares > 0 ? `${state.campaignState.shares.toFixed(2)} 股 @ ${state.campaignState.avgEntry.toFixed(2)}` : "Flat";
  document.querySelector("#size-state").textContent = `${((state.campaignState.shares * pauseSnapshot.close) / Math.max(1, equity) * 100).toFixed(1)}%`;
  document.querySelector("#cash-state").textContent = formatMoney(state.campaignState.cash);
  document.querySelector("#pnl-state").textContent = formatMoney(netPnl);
  document.querySelector("#cost-state").textContent = formatMoney(state.campaignState.accumulatedCost);
  document.querySelector("#equity-state").textContent = formatMoney(equity);
  document.querySelector("#day-open").textContent = pauseSnapshot.open.toFixed(2);
  document.querySelector("#day-high").textContent = pauseSnapshot.high.toFixed(2);
  document.querySelector("#day-low").textContent = pauseSnapshot.low.toFixed(2);
  document.querySelector("#day-close").textContent = pauseSnapshot.close.toFixed(2);
  document.querySelector("#day-return").textContent = formatPct(pauseSnapshot.returnPct);
  document.querySelector("#day-rebound").textContent = formatPct(pauseSnapshot.reboundPct);
  document.querySelector("#pattern-label").textContent = day.patternLabel || "-";
  document.querySelector("#day-unrealized").textContent = formatMoney(unrealizedPnl(pauseSnapshot.close));
  document.querySelector("#open-gap").textContent = formatPct(openGapPct);
  document.querySelector("#day-range").textContent = formatPct(dayRangePct);
  document.querySelector("#day-volume").textContent = formatVolume(totalVolume);
  document.querySelector("#sentiment-heat").textContent = `${sentimentHeat}/100`;
  document.querySelector("#order-mode-input").value = state.campaignState.orderMode || "amount";
  document.querySelector("#limit-price-input").value = (state.campaignState.limitPrice || pauseSnapshot.close).toFixed(2);
  document.querySelector("#capital-input").disabled = Boolean(state.campaignState.capitalLocked);
  drawCampaignChart();
  drawIntradayChart(day, pauseSnapshot.bars);
  renderHeadlineFeed(day);
  renderDiscussionFeed(day);
  renderLog();
}

function resolveRequestedNotional(price, forceAll = false) {
  const mode = document.querySelector("#order-mode-input")?.value || state.campaignState.orderMode || "amount";
  const rawValue = Math.max(0, Number(document.querySelector("#order-amount-input")?.value || state.campaignState.orderAmount || 0));
  state.campaignState.orderMode = mode;
  state.campaignState.orderAmount = rawValue;
  if (forceAll) {
    return state.campaignState.shares * price;
  }
  if (mode === "shares") {
    return rawValue * price;
  }
  return rawValue;
}

function resolveLimitPrice(defaultPrice) {
  const rawValue = Number(document.querySelector("#limit-price-input")?.value || state.campaignState.limitPrice || 0);
  const limitPrice = rawValue > 0 ? rawValue : defaultPrice;
  state.campaignState.limitPrice = limitPrice;
  return limitPrice;
}

function findLimitFillPrice(action, day, limitPrice) {
  if (!(limitPrice > 0)) {
    return null;
  }
  const visibleBars = currentVisibleBars(day);
  if (action === "buy") {
    const touched = visibleBars.some((bar) => bar.low <= limitPrice);
    return touched ? limitPrice : null;
  }
  if (action === "sell") {
    const touched = visibleBars.some((bar) => bar.high >= limitPrice);
    return touched ? limitPrice : null;
  }
  return null;
}

function advancePauseOrDay() {
  const isLastPause = state.campaignState.currentPauseIndex >= DAILY_PAUSE_BAR_INDEXES.length - 1;
  const isLastDay = state.campaignState.currentDayIndex >= state.campaign.dayCount - 1;
  if (!isLastPause) {
    state.campaignState.currentPauseIndex += 1;
    return { completed: false, movedToNextDay: false };
  }
  if (isLastDay) {
    state.campaignState.completed = true;
    return { completed: true, movedToNextDay: false };
  }
  state.campaignState.currentDayIndex += 1;
  state.campaignState.currentPauseIndex = 0;
  return { completed: false, movedToNextDay: true };
}

function applyTradeDecision(action, options = {}) {
  const day = currentDay();
  const pauseSnapshot = pauseDaySnapshot(day);
  const costRate = transactionCostRate();
  const referencePrice = pauseSnapshot.close;
  const limitPrice = resolveLimitPrice(referencePrice);
  const fillPrice = action === "hold" ? null : findLimitFillPrice(action, day, limitPrice);
  const requestedAmount = resolveRequestedNotional(fillPrice || limitPrice || referencePrice, options.forceAll === true);
  let executedAmount = 0;
  let executedShares = 0;
  let appliedFillPrice = 0;
  let success = false;
  let message = "已记录观望。";
  let status = "hold";

  if (action === "buy" && state.campaignState.cash > 0 && requestedAmount > 0) {
    if (!fillPrice) {
      return {
        success: false,
      message: `买入限价 ${limitPrice.toFixed(2)} 今日未触发，订单未成交。`,
        executedAmount: 0,
        executedShares: 0,
        fillPrice: 0,
      };
    }
    const notional = Math.min(requestedAmount, state.campaignState.cash);
    const cost = notional * costRate;
    const shares = Math.max(0, (notional - cost) / fillPrice);
    if (shares > 0) {
      state.campaignState.capitalLocked = true;
      const totalPositionCost = state.campaignState.avgEntry * state.campaignState.shares + notional;
      state.campaignState.cash -= notional;
      state.campaignState.shares += shares;
      state.campaignState.avgEntry = state.campaignState.shares > 0 ? totalPositionCost / state.campaignState.shares : 0;
      state.campaignState.accumulatedCost += cost;
      executedAmount = notional;
      executedShares = shares;
      appliedFillPrice = fillPrice;
      success = true;
      message = `买入限价 ${limitPrice.toFixed(2)} 已触发，按 ${fillPrice.toFixed(2)} 成交 ${shares.toFixed(2)} 股。`;
      status = "filled";
    } else {
      message = "买入金额过小，未形成有效成交。";
      status = "rejected";
    }
  } else if (action === "sell" && state.campaignState.shares > 0 && requestedAmount > 0) {
    if (!fillPrice) {
      return {
        success: false,
      message: `卖出限价 ${limitPrice.toFixed(2)} 今日未触发，订单未成交。`,
        executedAmount: 0,
        executedShares: 0,
        fillPrice: 0,
      };
    }
    const maxSellNotional = state.campaignState.shares * fillPrice;
    const gross = Math.min(requestedAmount, maxSellNotional);
    const cost = gross * costRate;
    const sharesToSell = Math.min(state.campaignState.shares, gross / fillPrice);
    if (sharesToSell > 0) {
      state.campaignState.capitalLocked = true;
      const netProceeds = gross - cost;
      const pnl = netProceeds - state.campaignState.avgEntry * sharesToSell;
      state.campaignState.cash += netProceeds;
      state.campaignState.realizedPnl += pnl;
      state.campaignState.accumulatedCost += cost;
      state.campaignState.shares = Math.max(0, state.campaignState.shares - sharesToSell);
      if (state.campaignState.shares === 0) {
        state.campaignState.avgEntry = 0;
      }
      executedAmount = gross;
      executedShares = sharesToSell;
      appliedFillPrice = fillPrice;
      success = true;
      message = options.forceAll
        ? `卖出限价 ${limitPrice.toFixed(2)} 已触发，全部持仓按 ${fillPrice.toFixed(2)} 成交。`
        : `卖出限价 ${limitPrice.toFixed(2)} 已触发，按 ${fillPrice.toFixed(2)} 卖出 ${sharesToSell.toFixed(2)} 股。`;
      status = "filled";
    } else {
      message = "卖出数量不足，未形成有效成交。";
      status = "rejected";
    }
  } else if (action === "hold") {
    success = true;
    state.campaignState.capitalLocked = true;
    message = "已记录观望。";
    status = "hold";
  } else if (action === "buy") {
    message = "可用现金不足，无法买入。";
    status = "rejected";
  } else if (action === "sell") {
    message = "当前没有可卖出的持仓。";
    status = "rejected";
  }

  if (success) {
    state.campaignState.actionLog.push({
      dayIndex: day.dayIndex,
      pauseIndex: state.campaignState.currentPauseIndex,
      dayLabel: day.dateLabel,
      action,
      status,
      amount: executedAmount,
      shares: executedShares,
      limitPrice,
      fillPrice: appliedFillPrice,
      orderMode: state.campaignState.orderMode,
      cashAfter: state.campaignState.cash,
      positionAfter: state.campaignState.shares,
      regimeLabel: day.regimeLabel,
      dayReturnPct: pauseSnapshot.returnPct,
      dayDrawdownPct: pauseSnapshot.drawdownPct,
      noiseSentiment: day.noiseSentiment,
      note: message,
    });
  }

  return { success, message, executedAmount, executedShares, fillPrice: appliedFillPrice };
}

async function writeBehaviorEvent(action) {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    return;
  }
  const day = currentDay();
  await apiRequest(`/api/sessions/${snapshot.session_id}/simulation/events`, {
    method: "POST",
    body: JSON.stringify({
      scenario_id: `campaign-${day.regimeKey}-${day.dayIndex + 1}-pause-${state.campaignState.currentPauseIndex + 1}`,
      price_drawdown_pct: pauseDaySnapshot(day).drawdownPct,
      action,
      noise_level: Math.abs(day.noiseSentiment),
      sentiment_pressure: day.noiseSentiment,
      latency_seconds: 120,
    }),
  });
}

async function handleDecision(action, options = {}) {
  if (state.campaignState.completed) {
    return;
  }
  try {
    const result = applyTradeDecision(action, options);
    if (!result.success) {
      document.querySelector("#simulation-note").textContent = result.message;
      renderSummary();
      return;
    }
    await writeBehaviorEvent(action);
    const progress = advancePauseOrDay();
    persistState();
    if (progress.completed) {
      document.querySelector("#simulation-note").textContent = `${result.message} 全部交易日已完成。`;
    } else if (progress.movedToNextDay) {
      document.querySelector("#simulation-note").textContent = `${result.message} 今日 5 次暂停已结束，已进入下一交易日。`;
    } else {
      document.querySelector("#simulation-note").textContent = `${result.message} 已进入今日下一次暂停。`;
    }
    renderSummary();
  } catch (error) {
    document.querySelector("#simulation-note").textContent = `写入测试行为失败：${error.message}`;
  }
}

async function skipEntireDay() {
  if (state.campaignState.completed) {
    return;
  }
  const day = currentDay();
  state.campaignState.capitalLocked = true;
  state.campaignState.actionLog.push({
    dayIndex: day.dayIndex,
    pauseIndex: "all",
    dayLabel: day.dateLabel,
    action: "skip_day",
    status: "hold",
    amount: 0,
    shares: 0,
    limitPrice: 0,
    fillPrice: 0,
    orderMode: state.campaignState.orderMode,
    cashAfter: state.campaignState.cash,
    positionAfter: state.campaignState.shares,
    regimeLabel: day.regimeLabel,
    dayReturnPct: pauseDaySnapshot(day).returnPct,
    dayDrawdownPct: pauseDaySnapshot(day).drawdownPct,
    noiseSentiment: day.noiseSentiment,
    note: "已跳过今天剩余全部交易机会。",
  });
  await writeBehaviorEvent("hold");
  const isLastDay = state.campaignState.currentDayIndex >= state.campaign.dayCount - 1;
  if (isLastDay) {
    state.campaignState.completed = true;
    persistState();
    document.querySelector("#simulation-note").textContent = "已跳过今天，全部交易日已完成。";
  } else {
    state.campaignState.currentDayIndex += 1;
    state.campaignState.currentPauseIndex = 0;
    persistState();
    document.querySelector("#simulation-note").textContent = "已跳过今天，直接进入下一交易日。";
  }
  renderSummary();
}

async function completeSimulation() {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    document.querySelector("#simulation-note").textContent = "请先创建会话。";
    return;
  }
  if (!state.campaignState.completed) {
    document.querySelector("#simulation-note").textContent = "请先完成全部 30-60 天测试，再生成报告。";
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/simulation/complete`, {
      method: "POST",
      body: JSON.stringify({ symbol: "SIM-5M-DAILY-CAMPAIGN" }),
    });
    storeSnapshot(latest);
    document.querySelector("#simulation-note").textContent = "测试报告已生成。请前往测试报告页查看 Behavioral Profiler 结果。";
    renderShell("simulation");
  } catch (error) {
    document.querySelector("#simulation-note").textContent = `生成测试报告失败：${error.message}`;
  }
}

function resetCampaign() {
  resetCampaignProgress();
  state.campaignState.capitalLocked = false;
  persistState();
  document.querySelector("#capital-input").disabled = false;
  renderSummary();
  document.querySelector("#simulation-note").textContent = "已重置测试。你可以先调整模拟本金，再开始新的交易日。";
}

function syncInputsIntoState() {
  if (state.campaignState.capitalLocked) {
    document.querySelector("#capital-input").value = String(state.campaignState.capitalBase);
    document.querySelector("#simulation-note").textContent = "测试已经开始，模拟本金已锁定。若要修改，请重置整段测试。";
    return;
  }
  const capital = Number(document.querySelector("#capital-input").value || 500000);
  const orderAmount = Number(document.querySelector("#order-amount-input").value || 50000);
  const orderMode = document.querySelector("#order-mode-input").value || "amount";
  const limitPrice = Math.max(0.01, Number(document.querySelector("#limit-price-input").value || 100));
  state.campaignState.capitalBase = capital;
  state.campaignState.cash = capital;
  state.campaignState.orderAmount = Math.max(0, orderAmount);
  state.campaignState.orderMode = orderMode;
  state.campaignState.limitPrice = limitPrice;
  state.campaignState.shares = 0;
  state.campaignState.avgEntry = 0;
  state.campaignState.realizedPnl = 0;
  state.campaignState.accumulatedCost = 0;
  state.campaignState.actionLog = [];
  state.campaignState.currentDayIndex = 0;
  state.campaignState.currentPauseIndex = 0;
  state.campaignState.completed = false;
  persistState();
}

document.querySelector("#buy-day")?.addEventListener("click", () => handleDecision("buy"));
document.querySelector("#sell-day")?.addEventListener("click", () => handleDecision("sell"));
document.querySelector("#sell-all-day")?.addEventListener("click", () => handleDecision("sell", { forceAll: true }));
document.querySelector("#hold-day")?.addEventListener("click", () => handleDecision("hold"));
document.querySelector("#skip-day")?.addEventListener("click", skipEntireDay);
document.querySelector("#complete-simulation")?.addEventListener("click", completeSimulation);
document.querySelector("#reset-sim")?.addEventListener("click", resetCampaign);
document.querySelector("#capital-input")?.addEventListener("change", () => {
  syncInputsIntoState();
  renderSummary();
});
document.querySelector("#order-amount-input")?.addEventListener("change", () => {
  state.campaignState.orderAmount = Math.max(0, Number(document.querySelector("#order-amount-input").value || 50000));
  persistState();
  renderSummary();
});
document.querySelector("#limit-price-input")?.addEventListener("change", () => {
  state.campaignState.limitPrice = Math.max(0.01, Number(document.querySelector("#limit-price-input").value || currentDay().close || 100));
  persistState();
  renderSummary();
});
document.querySelector("#order-mode-input")?.addEventListener("change", () => {
  state.campaignState.orderMode = document.querySelector("#order-mode-input").value || "amount";
  syncOrderInputLabel();
  persistState();
  renderSummary();
});

(function bootstrapSimulationPage() {
  renderShell("simulation");
  state.campaign = loadCampaign();
  state.campaignState = loadCampaignState();
  document.querySelector("#capital-input").value = String(state.campaignState.capitalBase);
  document.querySelector("#capital-input").disabled = Boolean(state.campaignState.capitalLocked);
  document.querySelector("#order-amount-input").value = String(state.campaignState.orderAmount || 50000);
  document.querySelector("#order-mode-input").value = state.campaignState.orderMode || "amount";
  document.querySelector("#limit-price-input").value = (state.campaignState.limitPrice || state.campaign.days[0].close || 100).toFixed(2);
  syncOrderInputLabel();
  renderSummary();
})();
