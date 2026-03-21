const CAMPAIGN_STORAGE_PREFIX = "sentinel-alpha:campaign:";
const CAMPAIGN_STATE_PREFIX = "sentinel-alpha:campaign-state:";
const DEFAULT_CAPITAL_BASE = 30000;
const DAILY_SEGMENT_ENDS = [15, 31, 47, 63, 77];

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

const DAILY_PATTERN_LIBRARY = [
  { key: "stair_up", blocks: ["uptrend", "uptrend", "oscillation", "uptrend"] },
  { key: "panic_then_bounce", blocks: ["gap", "drawdown", "fake_reversal", "oscillation"] },
  { key: "rolling_top", blocks: ["uptrend", "oscillation", "fake_reversal", "downtrend"] },
  { key: "washout", blocks: ["drawdown", "drawdown", "fake_reversal", "downtrend"] },
  { key: "chop_box", blocks: ["oscillation", "oscillation", "gap", "oscillation"] },
];

const INTRADAY_TEMPLATE_LIBRARY = {
  uptrend: [
    {
      key: "stair_push",
      label: "台阶推升",
      segments: [0.45, -0.08, 0.38, -0.05, 0.42],
    },
    {
      key: "dip_and_rip",
      label: "回踩再拉",
      segments: [-0.32, 0.58, 0.12, 0.28, 0.35],
    },
  ],
  gap: [
    {
      key: "gap_fill_battle",
      label: "缺口博弈",
      segments: [-0.62, 0.28, -0.18, 0.22, -0.08],
    },
    {
      key: "gap_and_fade",
      label: "跳空回落",
      segments: [0.22, -0.68, -0.12, 0.06, -0.22],
    },
  ],
  oscillation: [
    {
      key: "box_chop",
      label: "箱体来回",
      segments: [0.18, -0.24, 0.2, -0.18, 0.05],
    },
    {
      key: "false_break_chain",
      label: "连环假突破",
      segments: [0.35, -0.42, 0.3, -0.38, 0.14],
    },
  ],
  drawdown: [
    {
      key: "drift_lower",
      label: "阴跌破位",
      segments: [-0.18, -0.22, -0.16, -0.24, -0.2],
    },
    {
      key: "panic_slide",
      label: "急跌失守",
      segments: [-0.42, -0.18, 0.08, -0.34, -0.12],
    },
  ],
  fake_reversal: [
    {
      key: "bear_trap",
      label: "诱多反杀",
      segments: [-0.36, 0.46, 0.32, -0.58, -0.2],
    },
    {
      key: "dead_cat_bounce",
      label: "死猫跳",
      segments: [-0.42, -0.06, 0.52, -0.48, -0.18],
    },
  ],
  downtrend: [
    {
      key: "trend_dump",
      label: "单边走低",
      segments: [-0.22, -0.18, -0.26, -0.14, -0.24],
    },
    {
      key: "weak_rebound_fail",
      label: "弱反弹失败",
      segments: [-0.28, 0.08, -0.34, 0.04, -0.26],
    },
  ],
};

const SEGMENT_BAR_RANGES = [
  [0, 15],
  [16, 31],
  [32, 47],
  [48, 63],
  [64, 77],
];

function marketPulseLabel(score) {
  if (score >= 0.55) return "偏多热议";
  if (score >= 0.15) return "情绪升温";
  if (score <= -0.55) return "恐慌放大";
  if (score <= -0.15) return "偏空扩散";
  return "分歧拉扯";
}

const HEADLINE_TEMPLATES = {
  uptrend: [
    { source: "盘中快讯", tag: "快讯", title: "龙头股再创盘中新高，追价买盘持续抬升成交重心", body: "多家量化席位盘中持续扫单，短线资金围绕强趋势继续抬价，卖盘并未明显放大。", tone: "positive" },
    { source: "卖方摘要", tag: "研报", title: "机构继续上修区间目标价，但提示短期估值争议加大", body: "核心逻辑仍围绕业绩兑现与资金抱团，部分账户开始讨论是否出现过热回撤风险。", tone: "neutral" },
    { source: "终端要闻", tag: "异动", title: "午后板块联动拉升，场内资金担忧踏空情绪快速升温", body: "资金博弈焦点从“贵不贵”转向“还有没有仓位”，追涨言论明显增多。", tone: "negative" },
  ],
  gap: [
    { source: "盘前突发", tag: "突发", title: "开盘大幅跳空，市场快速消化未经证实的利空传闻", body: "多条消息在开盘前集中扩散，资金优先用价格避险，盘口卖压在集合竞价阶段明显放大。", tone: "negative" },
    { source: "快讯聚合", tag: "追踪", title: "利空传闻与公司回应同时扩散，市场分歧被进一步放大", body: "一边是风险事件猜测，一边是辟谣和稳定情绪的表态，短线交易员正在重新评估缺口是否回补。", tone: "neutral" },
    { source: "交易台播报", tag: "观察", title: "部分资金尝试低吸缺口，但承接质量仍待确认", body: "盘口买单虽有回流，但上方抛压没有明显松动，冲高回落风险仍在。", tone: "positive" },
  ],
  oscillation: [
    { source: "量化观察", tag: "量化", title: "价格继续围绕区间中轴反复拉扯，假突破频率上升", body: "日内多次上穿下破前高前低，但增量资金接力不足，追单和止损盘来回切换。", tone: "neutral" },
    { source: "盘中扫描", tag: "异动", title: "成交放大但趋势未形成，短线信号质量持续下降", body: "盘口波动看似活跃，但方向一致性偏弱，手续费与滑点对高频试错更不友好。", tone: "negative" },
    { source: "社区热帖", tag: "热帖", title: "“要突破了”与“又是假动作”两派观点反复刷屏", body: "市场没有给出真正方向，情绪却在不断催促交易，典型震荡盘特征明显。", tone: "positive" },
  ],
  drawdown: [
    { source: "风险快评", tag: "风险", title: "连续缩量下挫后，市场开始用“便宜”替代真正的估值锚", body: "部分资金将跌幅视为机会，但基本面与流动性压力并未出现实质修复信号。", tone: "negative" },
    { source: "资金流监测", tag: "资金", title: "被动承接占比抬升，主动买盘修复力度仍偏弱", body: "盘口显示下方并非完全没有承接，但增量资金更像试探性接单，尚未形成趋势性反转。", tone: "neutral" },
    { source: "热榜追踪", tag: "热帖", title: "“跌得越深越该分批接”成为社区高频观点", body: "抄底情绪明显扩散，讨论重心从风险控制转向如何摊低成本。", tone: "positive" },
  ],
  fake_reversal: [
    { source: "热点推送", tag: "热搜", title: "反转预期升温，盘中一度出现“底部确认”式买盘追价", body: "午后反弹放大了乐观预期，社群开始传播“这里不上车后面只能更贵”的观点。", tone: "positive" },
    { source: "盘后复盘", tag: "复盘", title: "反弹力度虽然可见，但上方套牢盘与趋势压力仍未真正解除", body: "短线反抽更像情绪修复而非结构性反转，继续向上需要更强成交与持续资金验证。", tone: "negative" },
    { source: "交易台播报", tag: "异动", title: "高位抛压在反弹段再次出现，资金分歧比价格表现更激烈", body: "盘口里一边是抢反弹，一边是逢高减仓，声音越一致的地方往往越容易出现反身性回落。", tone: "neutral" },
  ],
  downtrend: [
    { source: "策略点评", tag: "策略", title: "下跌逻辑持续自我强化，资金更倾向先观望再谈抄底", body: "宏观扰动、盈利担忧与风险偏好下行同时作用，买盘承接整体偏谨慎。", tone: "negative" },
    { source: "市场扫描", tag: "盘面", title: "连续阴跌后，账户回撤与情绪负反馈开始同步放大", body: "价格没有给出像样反弹，持仓者在“割不割”之间不断摇摆，场内观望气氛上升。", tone: "neutral" },
    { source: "快讯终端", tag: "异动", title: "盘中偶有资金试图承接，但持续性不足导致反抽迅速回落", body: "每一次小反弹都被更低位置的卖盘压制，趋势空头结构暂未改变。", tone: "positive" },
  ],
};

const DISCUSSION_TEMPLATES = {
  uptrend: [
    { author: "龙头狙击群", handle: "@趋势交易员", text: "这类慢牛最折磨人，回调不给深，等确认的人最后都被迫追价。", tone: "positive" },
    { author: "估值辩论帖", handle: "@逆向研究员", text: "越涨越有人说泡沫，但真正让人难受的是你卖完它继续涨。", tone: "negative" },
    { author: "社群直播间", handle: "@盘中观察", text: "这种走势容易把人洗下车，拿不住比买不到更常见。", tone: "neutral" },
  ],
  gap: [
    { author: "盘前突发群", handle: "@快反资金", text: "这种缺口先别讲逻辑，价格先砍出来再说，跑慢了就是被动。", tone: "negative" },
    { author: "短线打板群", handle: "@低吸选手", text: "一字恐慌最容易砸出机会，关键看承接，不是看谁喊得凶。", tone: "positive" },
    { author: "老交易员串", handle: "@风控先行", text: "先等盘面自己说话，别让流传最广的那条消息替你下单。", tone: "neutral" },
  ],
  oscillation: [
    { author: "震荡猎手群", handle: "@追突破", text: "这次不一样，量能跟上了，再不追等下又没位置。", tone: "positive" },
    { author: "回撤派频道", handle: "@假突破警报", text: "这种来回扫止损的盘最喜欢教育手痒的人。", tone: "negative" },
    { author: "交易室记录", handle: "@值班复盘", text: "真正难的不是看不懂，是明知道噪音很多还总想点一下。", tone: "neutral" },
  ],
  drawdown: [
    { author: "抄底作战群", handle: "@分批摊平", text: "跌这么多再不接，难道真等红盘了再追？这里摊成本最划算。", tone: "positive" },
    { author: "风控日志", handle: "@止损纪律", text: "下跌趋势里最容易犯的错不是亏损，是拿“已经跌很多”当买入理由。", tone: "negative" },
    { author: "老手复盘贴", handle: "@先活下来", text: "很多账户不是死在大跌那天，而是死在连续阴跌里不停补仓。", tone: "neutral" },
  ],
  fake_reversal: [
    { author: "热门弹幕", handle: "@反转来了", text: "底部已经给你画出来了，再犹豫后面只能追更高。", tone: "positive" },
    { author: "冷静观察贴", handle: "@别急着抄底", text: "下降趋势里的反弹最容易让人误以为自己终于抄到最低点。", tone: "negative" },
    { author: "盘后聊天室", handle: "@短线博弈", text: "声音越像共识，越要防这是给套牢盘制造的流动性。", tone: "neutral" },
  ],
  downtrend: [
    { author: "空头观察群", handle: "@趋势空仓", text: "越跌越舍不得卖是常态，真正难的是承认趋势已经错了。", tone: "negative" },
    { author: "套牢盘留言", handle: "@等反弹走", text: "已经亏成这样了，再割等于把亏损坐实，不如等个反抽。", tone: "negative" },
    { author: "风险复盘", handle: "@纪律执行", text: "大多数人不是没有规则，而是在最需要执行的时候开始给自己找理由。", tone: "neutral" },
  ],
};

const state = {
  campaign: null,
  campaignState: null,
  feeRatePct: 0.12,
  slippagePct: 0.18,
  selectedCampaignCandleIndex: null,
  selectedIntradayBarIndex: null,
  chartMode: "intraday",
  chartFocusDayIndex: null,
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
  const schedule = [];
  while (schedule.length < dayCount) {
    const pattern = pick(random, DAILY_PATTERN_LIBRARY);
    for (const key of pattern.blocks) {
      const regime = REGIMES.find((item) => item.key === key) || REGIMES[0];
      const repeat = 2 + Math.floor(random() * 3);
      for (let count = 0; count < repeat && schedule.length < dayCount; count += 1) {
        schedule.push(regime);
      }
      if (schedule.length >= dayCount) {
        break;
      }
    }
  }
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
  const template = pick(random, INTRADAY_TEMPLATE_LIBRARY[regime.key] || INTRADAY_TEMPLATE_LIBRARY.oscillation);

  for (let barIndex = 0; barIndex < 78; barIndex += 1) {
    const t = barIndex / 77;
    const segmentIndex = SEGMENT_BAR_RANGES.findIndex(([start, end]) => barIndex >= start && barIndex <= end);
    const segmentBias = template.segments[Math.max(0, segmentIndex)] || 0;
    const cyclical = Math.sin(barIndex / 9) * regime.volatility * 0.28;
    const shaped = interpolateAnchors(shape.anchors, t) * regime.volatility * 1.2;
    let move = regime.bias + cyclical + shaped + segmentBias * regime.volatility + (random() - 0.5) * regime.volatility * 0.48;
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
    patternLabel: `${shape.label} / ${template.label}`,
    bars,
  };
}

function formatCnAmountBillion(value) {
  return `${value.toFixed(1)} 亿元`;
}

function buildNoiseSummary(regime, generated, random) {
  const targetPrice = Math.max(1, generated.close * (1.12 + random() * 0.18));
  const orderValue = 8 + random() * 28;
  const issue = pick(random, [
    "应收账款回款节奏",
    "毛利率可持续性",
    "海外订单兑现节奏",
    "客户集中度风险",
    "监管问询的不确定性",
    "库存去化压力",
  ]);
  const bullishDesk = pick(random, ["中信建投", "国泰君安", "中金公司", "华泰证券", "海通证券"]);
  const skepticalDesk = pick(random, ["高盛", "摩根士丹利", "瑞银", "摩根大通"]);

  const byRegime = {
    uptrend: {
      headline: `${bullishDesk} 上调目标价至 ${targetPrice.toFixed(0)} 元，市场继续围绕订单与业绩兑现交易`,
      body: `公司被传新增 ${formatCnAmountBillion(orderValue)} 级别订单，同时也有观点担心当前位置估值过热。`,
    },
    gap: {
      headline: `缺口波动放大，市场同时交易“新增订单”与“${issue} 风险”两条线索`,
      body: `${bullishDesk} 维持看多观点，但 ${skepticalDesk} 盘中提醒仍需关注 ${issue}。`,
    },
    oscillation: {
      headline: `多空都在引用研报与订单数据，价格却仍在区间内反复拉扯`,
      body: `一边是 ${bullishDesk} 给出 ${targetPrice.toFixed(0)} 元目标价，一边是市场质疑 ${issue}。`,
    },
    drawdown: {
      headline: `下跌后抄底声量抬升，市场讨论焦点转向“订单能否对冲 ${issue}”`,
      body: `公司据传拿下 ${formatCnAmountBillion(orderValue)} 新订单，但交易席位更关注现金流与 ${issue}。`,
    },
    fake_reversal: {
      headline: `反弹段里“目标价上修”和“风险未解”两种声音同时放大`,
      body: `${bullishDesk} 称合理估值可看至 ${targetPrice.toFixed(0)} 元，但 ${skepticalDesk} 仍提示 ${issue} 没有被完全定价。`,
    },
    downtrend: {
      headline: `价格走弱时，利多订单消息难以压过“${issue}”的市场担忧`,
      body: `公司虽被传新增 ${formatCnAmountBillion(orderValue)} 合同，但市场更在意 ${skepticalDesk} 对 ${issue} 的提示。`,
    },
  };
  return byRegime[regime.key] || byRegime.oscillation;
}

function buildHeadlineFeed(regime, generated, random) {
  const targetPrice = Math.max(1, generated.close * (1.08 + random() * 0.22));
  const orderValue = 6 + random() * 36;
  const marginPct = 18 + random() * 19;
  const issue = pick(random, [
    "商誉减值风险",
    "大客户砍单传闻",
    "现金流承压",
    "海外监管审查",
    "应收账款周转放缓",
    "存货计提压力",
  ]);
  const desks = ["中信建投", "中金公司", "华泰证券", "国泰君安", "申万宏源"];
  const skeptics = ["高盛", "摩根士丹利", "野村", "瑞银"];
  const issuer = pick(random, ["公司公告", "交易所互动", "盘后公告", "董秘回应"]);
  const bullishDesk = pick(random, desks);
  const skepticalDesk = pick(random, skeptics);

  const map = {
    uptrend: [
      { source: bullishDesk, tag: "目标价", title: `${bullishDesk} 维持“买入”，目标价上调至 ${targetPrice.toFixed(0)} 元`, body: `报告称新增订单与利润率改善超预期，预计未来两个季度毛利率有望维持在 ${marginPct.toFixed(1)}% 附近。`, tone: "positive" },
      { source: issuer, tag: "订单", title: `公司称新签 ${formatCnAmountBillion(orderValue)} 订单，覆盖未来 12 个月主要产能`, body: "市场开始围绕订单兑现节奏与业绩弹性重新定价，盘中追价明显增多。", tone: "positive" },
      { source: skepticalDesk, tag: "风险", title: `${skepticalDesk} 提醒当前位置仍需关注 ${issue}`, body: "部分资金担心估值抬升快于基本面兑现，短线分歧开始升温。", tone: "negative" },
    ],
    gap: [
      { source: "盘前快讯", tag: "突发", title: `盘前传出 ${issue} 相关消息，股价开盘出现明显缺口`, body: "利空传闻与公司回应同时扩散，市场先以价格重新划定风险区间。", tone: "negative" },
      { source: issuer, tag: "澄清", title: `公司回应称当前经营正常，${formatCnAmountBillion(orderValue)} 在手订单尚在执行`, body: "尽管回应偏稳，但短线资金仍在观察市场是否愿意为缺口提供承接。", tone: "neutral" },
      { source: bullishDesk, tag: "观点", title: `${bullishDesk} 称若缺口快速回补，中线目标仍可看至 ${targetPrice.toFixed(0)} 元`, body: "报告强调订单与收入确认节奏未发生结构性变化。", tone: "positive" },
    ],
    oscillation: [
      { source: bullishDesk, tag: "目标价", title: `${bullishDesk} 给出 ${targetPrice.toFixed(0)} 元目标价，但强调需等待突破确认`, body: "报告认可基本面改善，但提示区间震荡阶段不宜过度追单。", tone: "neutral" },
      { source: "行业快讯", tag: "订单", title: `产业链消息称公司有望新增 ${formatCnAmountBillion(orderValue)} 项目订单`, body: "消息刺激短线情绪回暖，但资金并未形成持续单边共识。", tone: "positive" },
      { source: skepticalDesk, tag: "疑点", title: `${skepticalDesk} 认为当前仍需核实 ${issue}`, body: "市场一边看订单，一边看风险，区间博弈被进一步放大。", tone: "negative" },
    ],
    drawdown: [
      { source: issuer, tag: "订单", title: `公司披露新增 ${formatCnAmountBillion(orderValue)} 订单，但股价仍延续弱势`, body: "市场更关注订单能否真正转化为现金流和利润，而不是单纯的金额规模。", tone: "positive" },
      { source: skepticalDesk, tag: "风险", title: `${skepticalDesk} 提示 ${issue} 仍可能压制估值修复`, body: "即使价格已显著回撤，机构仍未完全转向乐观口径。", tone: "negative" },
      { source: "卖方电话会", tag: "跟踪", title: `部分买方开始讨论“是否已经跌出安全边际”`, body: "抄底讨论升温，但风险提示并未消失，市场仍处在犹豫状态。", tone: "neutral" },
    ],
    fake_reversal: [
      { source: bullishDesk, tag: "目标价", title: `${bullishDesk} 表示若反弹延续，阶段目标可看至 ${targetPrice.toFixed(0)} 元`, body: "报告把近期反弹解释为对前期过度悲观的修复，并强调订单和利润率具备支撑。", tone: "positive" },
      { source: "交易台快评", tag: "异动", title: `反弹过程中关于“底部已现”的观点明显增多`, body: `部分账户开始引用 ${formatCnAmountBillion(orderValue)} 订单与低估值逻辑推动追价。`, tone: "positive" },
      { source: skepticalDesk, tag: "质疑", title: `${skepticalDesk} 称反弹未能消除 ${issue} 的核心担忧`, body: "卖方分歧并未收敛，套牢盘是否借反弹离场仍是观察重点。", tone: "negative" },
    ],
    downtrend: [
      { source: "盘中快讯", tag: "承压", title: `尽管传出 ${formatCnAmountBillion(orderValue)} 新订单，股价仍未摆脱下行趋势`, body: "市场更在意宏观和风险偏好的同步转弱，利多消息未能带来持续承接。", tone: "neutral" },
      { source: skepticalDesk, tag: "风险", title: `${skepticalDesk} 继续提示 ${issue} 可能拖累估值中枢`, body: "部分资金认为没有必要在趋势未稳前为单一利多消息买单。", tone: "negative" },
      { source: bullishDesk, tag: "目标价", title: `${bullishDesk} 仍维持 ${targetPrice.toFixed(0)} 元目标价，但下调短期节奏判断`, body: "中线看法未完全转空，短线则明显更保守。", tone: "positive" },
    ],
  };
  return map[regime.key] || map.oscillation;
}

function buildDiscussionFeed(regime, generated, random) {
  const targetPrice = Math.max(1, generated.close * (1.1 + random() * 0.2));
  const orderValue = 5 + random() * 25;
  const issue = pick(random, [
    "财务真实性",
    "订单水分",
    "大客户依赖",
    "监管问询",
    "存货风险",
    "现金流问题",
  ]);
  const map = {
    uptrend: [
      { author: "券商点评群", handle: "@上调目标价派", text: `都看到 ${targetPrice.toFixed(0)} 元了，现在因为怕高不敢上，后面大概率更难买。`, tone: "positive" },
      { author: "持仓群聊", handle: "@订单派", text: `公司都公告新增 ${formatCnAmountBillion(orderValue)} 订单了，这种级别的增量不该只值现在这个价。`, tone: "positive" },
      { author: "逆向讨论区", handle: "@估值警惕", text: `目标价喊得越整齐越要小心，别最后变成给高位接力找理由。`, tone: "negative" },
    ],
    gap: [
      { author: "快反群", handle: "@先跑再说", text: `盘前都在传 ${issue}，这种时候先撤才是正解，别跟消息赌命。`, tone: "negative" },
      { author: "低吸讨论串", handle: "@缺口回补", text: `如果只是情绪杀，等澄清一出来这缺口反而是送钱的位置。`, tone: "positive" },
      { author: "盘口室", handle: "@看承接", text: `别看谁嗓门大，看承接和回补速度，价格比消息诚实。`, tone: "neutral" },
    ],
    oscillation: [
      { author: "热帖", handle: "@看多订单派", text: `新增 ${formatCnAmountBillion(orderValue)} 订单还不给涨，这票一旦突破就是加速。`, tone: "positive" },
      { author: "做空笔记", handle: "@假突破预警", text: `市场天天拿目标价说事，但 ${issue} 没解决之前，冲高就是给你卖。`, tone: "negative" },
      { author: "交易吐槽", handle: "@被来回打脸", text: `最烦这种盘，利多利空都能讲通，最后就专门磨手续费。`, tone: "neutral" },
    ],
    drawdown: [
      { author: "抄底吧", handle: "@越跌越香", text: `都跌成这样了还有 ${formatCnAmountBillion(orderValue)} 订单，怎么可能一点价值都没有。`, tone: "positive" },
      { author: "风险贴", handle: "@别摊平", text: `订单数字再大也掩盖不了 ${issue}，别把消息当成补仓许可。`, tone: "negative" },
      { author: "老股民", handle: "@先看现金流", text: `市场最爱在下跌里放大利多，因为大家都希望自己不是最后接棒的人。`, tone: "neutral" },
    ],
    fake_reversal: [
      { author: "弹幕区", handle: "@底部确认派", text: `目标价都还在 ${targetPrice.toFixed(0)} 元，今天这根反抽就是送钱上车点。`, tone: "positive" },
      { author: "冷静区", handle: "@反弹不是反转", text: `最怕的就是拿一份利多纪要，硬解释成趋势已经回来了。`, tone: "negative" },
      { author: "群聊记录", handle: "@追还是不追", text: `大家现在不是没理由买，是理由太多了，越像共识越要小心。`, tone: "neutral" },
    ],
    downtrend: [
      { author: "空头观察", handle: "@趋势优先", text: `就算有订单，市场也在担心 ${issue}，趋势没走完之前别急着讲底。`, tone: "negative" },
      { author: "套牢群", handle: "@等反弹走", text: `已经亏这么多了，不如等公司把订单落地，目标价修回来再说。`, tone: "positive" },
      { author: "纪律讨论", handle: "@先少亏", text: `很多人不是不知道风险，而是总觉得下一条利多会刚好救自己。`, tone: "neutral" },
    ],
  };
  return map[regime.key] || map.oscillation;
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
    const noiseSummary = buildNoiseSummary(regime, generated, random);
    const headlineFeed = buildHeadlineFeed(regime, generated, random).map((item, index) => ({
      ...item,
      time: generated.bars[Math.min(generated.bars.length - 1, 6 + index * 18)].timeLabel,
    }));
    const discussionFeed = buildDiscussionFeed(regime, generated, random).map((item, index) => ({
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
      noiseHeadline: noiseSummary.headline,
      noiseBody: noiseSummary.body,
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

function normalizeTemplateDay(day, dayIndex) {
  const bars = (day.bars || []).map((bar, index) => ({
    index,
    time: bar.time,
    timeLabel: bar.timeLabel,
    open: Number(bar.open),
    high: Number(bar.high),
    low: Number(bar.low),
    close: Number(bar.close),
    volume: Number(bar.volume || 0),
  }));
  const previousClose = dayIndex > 0 ? Number(day.previousClose || bars[0]?.open || day.open) : Number(bars[0]?.open || day.open);
  const high = Number(day.high);
  const low = Number(day.low);
  const close = Number(day.close);
  return {
    dayIndex,
    dateLabel: day.dateLabel,
    regimeKey: day.market_regime || day.regimeKey || "template_library",
    regimeLabel: day.regimeLabel || day.symbol,
    open: Number(day.open),
    high,
    low,
    close,
    closeReturnPct: previousClose > 0 ? ((close / previousClose) - 1) * 100 : 0,
    drawdownPct: previousClose > 0 ? ((low / previousClose) - 1) * 100 : 0,
    reboundPct: low > 0 ? ((high / low) - 1) * 100 : 0,
    iv: 0.18 + Math.abs(((close / Math.max(previousClose, 0.0001)) - 1) * 100) * 0.08,
    patternKey: day.shape_family || "template",
    patternLabel: day.pattern_label || day.regimeLabel || day.symbol,
    noiseHeadline: `${day.symbol} ${day.regimeLabel || ""}`.trim(),
    noiseBody: `真实片段模板 · ${day.market_regime || "mixed"} / ${day.shape_family || "pattern"}`,
    noiseSentiment: 0,
    headlineFeed: [],
    discussionFeed: [],
    bars,
    segments: day.segments || [],
    symbol: day.symbol,
  };
}

async function loadTemplateCampaign(dayCount = 40) {
  try {
    const payload = await apiRequest(`/api/market-template-campaign?day_count=${dayCount}`);
    if (!payload?.days?.length) {
      return null;
    }
    return {
      sessionId: activeSessionId(),
      createdAt: new Date().toISOString(),
      dayCount: payload.days.length,
      timeframe: "5m",
      cadence: "intraday_segment_decision",
      source: "template_library",
      days: payload.days.map((day, index) => normalizeTemplateDay(day, index)),
    };
  } catch (error) {
    return null;
  }
}

function initialCampaignState() {
  const capital = DEFAULT_CAPITAL_BASE;
  const orderAmount = Number(document.querySelector("#order-amount-input")?.value || 5000);
  const orderMode = document.querySelector("#order-mode-input")?.value || "amount";
  const initialLimitPrice = Number(document.querySelector("#limit-price-input")?.value || 100);
  return {
    currentDayIndex: 0,
    currentSegmentIndex: 0,
    cash: capital,
    capitalBase: capital,
    capitalLocked: true,
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

async function loadCampaign() {
  const stored = readJson(campaignKey());
  if (stored?.days?.length) {
    return stored;
  }
  const templateCampaign = await loadTemplateCampaign();
  if (templateCampaign?.days?.length) {
    writeJson(campaignKey(), templateCampaign);
    return templateCampaign;
  }
  const generated = generateCampaign(activeSessionId());
  writeJson(campaignKey(), generated);
  return generated;
}

function loadCampaignState() {
  const stored = readJson(campaignStateKey());
  if (stored?.capitalBase) {
    if (stored.capitalBase !== DEFAULT_CAPITAL_BASE) {
      const reset = initialCampaignState();
      writeJson(campaignStateKey(), reset);
      return reset;
    }
    stored.capitalLocked = true;
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

function viewedDay() {
  const focusedIndex = state.chartFocusDayIndex;
  if (Number.isInteger(focusedIndex) && focusedIndex >= 0 && focusedIndex < state.campaign.days.length) {
    return state.campaign.days[focusedIndex];
  }
  return currentDay();
}

function currentSegmentEndIndex() {
  return DAILY_SEGMENT_ENDS[Math.min(state.campaignState.currentSegmentIndex || 0, DAILY_SEGMENT_ENDS.length - 1)];
}

function currentVisibleBars(day = currentDay()) {
  return day.bars.slice(0, currentSegmentEndIndex() + 1);
}

function visibleBarsForDay(day) {
  if (day.dayIndex === currentDay().dayIndex) {
    return currentVisibleBars(day);
  }
  return day.bars;
}

function pauseDaySnapshot(day = currentDay()) {
  const visibleBars = visibleBarsForDay(day);
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

function visibleDailyCandles() {
  const currentIndex = state.campaignState.currentDayIndex;
  const visible = state.campaign.days.slice(0, currentIndex).map((day) => ({ ...day }));
  const current = currentDay();
  const currentPartial = pauseDaySnapshot(current);
  visible.push({
    ...current,
    open: currentPartial.open,
    high: currentPartial.high,
    low: currentPartial.low,
    close: currentPartial.close,
  });
  return visible.slice(-28);
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
      input.value = "5000";
    }
  }
}

function syncLimitPriceToCurrentClose() {
  const day = currentDay();
  if (!day) return;
  const pauseSnapshot = pauseDaySnapshot(day);
  state.campaignState.limitPrice = pauseSnapshot.close;
  const input = document.querySelector("#limit-price-input");
  if (input) {
    input.value = pauseSnapshot.close.toFixed(2);
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
  const candleWidth = Math.max(4.5, usableW / Math.max(1, points.length) * 0.68);
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
    const isSelected = state.selectedIntradayBarIndex === index;
    const selectedStroke = isSelected ? `stroke="rgba(124,47,28,0.95)" stroke-width="2.4"` : "";
    const selectedOutline = isSelected ? `<rect x="${(stepX - candleWidth / 2 - 2).toFixed(2)}" y="${(Math.min(highY, volumeY) - 2).toFixed(2)}" width="${(candleWidth + 4).toFixed(2)}" height="${(volumeTop + volumeHeight - Math.min(highY, volumeY) + 4).toFixed(2)}" rx="4" fill="none" stroke="rgba(124,47,28,0.8)" stroke-width="1.6"></rect>` : "";
    return `
      <g class="chart-candle clickable-candle" data-bar-index="${index}" data-price="${point.close.toFixed(2)}">
        ${selectedOutline}
        <line x1="${stepX.toFixed(2)}" y1="${highY.toFixed(2)}" x2="${stepX.toFixed(2)}" y2="${lowY.toFixed(2)}" stroke="${candleClass}" stroke-width="1.4" ${selectedStroke}></line>
        <rect x="${(stepX - candleWidth / 2).toFixed(2)}" y="${bodyY.toFixed(2)}" width="${candleWidth.toFixed(2)}" height="${bodyHeight.toFixed(2)}" rx="1.5" fill="${candleClass}"></rect>
        <rect x="${(stepX - candleWidth / 2).toFixed(2)}" y="${volumeY.toFixed(2)}" width="${candleWidth.toFixed(2)}" height="${volumeBarHeight.toFixed(2)}" rx="1.5" fill="rgba(133,115,95,0.55)"></rect>
      </g>
    `;
  }).join("");
  document.querySelector("#price-chart").innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" rx="20" fill="rgba(255,255,255,0.18)"></rect>
    ${backgroundLines}
    ${candles}
  `;
}

function drawCampaignChart() {
  const days = visibleDailyCandles();
  const width = 720;
  const height = 250;
  const padX = 24;
  const padY = 18;
  const values = days.flatMap((day) => [day.high, day.low]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const usableW = width - padX * 2;
  const usableH = height - padY * 2;
  const candleWidth = Math.max(8, usableW / Math.max(1, days.length) * 0.66);
  const yFor = (price) => padY + (max === min ? usableH / 2 : ((max - price) / (max - min)) * usableH);
  const currentIndex = days.length - 1;
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
    const isSelected = state.selectedCampaignCandleIndex === index;
    const selectedOutline = isSelected ? `<rect x="${(x - candleWidth / 2 - 3).toFixed(2)}" y="${(highY - 3).toFixed(2)}" width="${(candleWidth + 6).toFixed(2)}" height="${(lowY - highY + 6).toFixed(2)}" rx="4" fill="none" stroke="rgba(124,47,28,0.85)" stroke-width="1.8"></rect>` : "";
    return `
      <g class="chart-candle clickable-candle" data-campaign-index="${index}" data-price="${day.close.toFixed(2)}">
        ${selectedOutline}
        <line x1="${x.toFixed(2)}" y1="${highY.toFixed(2)}" x2="${x.toFixed(2)}" y2="${lowY.toFixed(2)}" ${highlight}></line>
        <rect x="${(x - candleWidth / 2).toFixed(2)}" y="${bodyY.toFixed(2)}" width="${candleWidth.toFixed(2)}" height="${bodyHeight.toFixed(2)}" rx="1.5" fill="${color}" opacity="${index === currentIndex ? "1" : "0.78"}"></rect>
      </g>
    `;
  }).join("");
  document.querySelector("#campaign-chart").innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" rx="20" fill="rgba(255,255,255,0.18)"></rect>
    ${gridLines}
    ${candles}
  `;
}

function bindChartInteractions() {
  const intradayChart = document.querySelector("#price-chart");
  const campaignChart = document.querySelector("#campaign-chart");
  intradayChart?.addEventListener("click", handleIntradayChartClick);
  campaignChart?.addEventListener("click", handleCampaignChartClick);
}

function setChartMode(mode) {
  state.chartMode = mode === "daily" ? "daily" : "intraday";
  if (state.chartMode === "intraday" && state.chartFocusDayIndex === null) {
    state.selectedCampaignCandleIndex = null;
  }
  const intradayStage = document.querySelector("#intraday-stage");
  const campaignStage = document.querySelector("#campaign-stage");
  const intradayButton = document.querySelector("#show-intraday-chart");
  const dailyButton = document.querySelector("#show-daily-chart");
  if (intradayStage) intradayStage.hidden = state.chartMode !== "intraday";
  if (campaignStage) campaignStage.hidden = state.chartMode !== "daily";
  intradayButton?.classList.toggle("active", state.chartMode === "intraday");
  dailyButton?.classList.toggle("active", state.chartMode === "daily");
}

function findDatasetNode(event, key) {
  const path = typeof event.composedPath === "function" ? event.composedPath() : [];
  for (const node of path) {
    if (node?.dataset && Object.prototype.hasOwnProperty.call(node.dataset, key)) {
      return node;
    }
  }
  let current = event.target;
  while (current) {
    if (current.dataset && Object.prototype.hasOwnProperty.call(current.dataset, key)) {
      return current;
    }
    current = current.parentNode;
  }
  return null;
}

function handleIntradayChartClick(event) {
  const candle = findDatasetNode(event, "barIndex");
  if (!candle) return;
  const day = currentDay();
  const visibleBars = currentVisibleBars(day);
  const barIndex = Number(candle.dataset.barIndex);
  const bar = visibleBars[barIndex];
  if (!bar) return;
  state.selectedIntradayBarIndex = barIndex;
  document.querySelector("#simulation-note").textContent = `已选中 ${bar.timeLabel} 的 5 分钟K线。O ${bar.open.toFixed(2)} / H ${bar.high.toFixed(2)} / L ${bar.low.toFixed(2)} / C ${bar.close.toFixed(2)}。`;
  persistState();
  renderSummary();
}

function handleCampaignChartClick(event) {
  const candle = findDatasetNode(event, "campaignIndex");
  if (!candle) return;
  const days = visibleDailyCandles();
  const campaignIndex = Number(candle.dataset.campaignIndex);
  const day = days[campaignIndex];
  if (!day) return;
  state.selectedCampaignCandleIndex = campaignIndex;
  state.chartFocusDayIndex = day.dayIndex;
  setChartMode("intraday");
  document.querySelector("#simulation-note").textContent = `${day.dateLabel} 日线已选中，已切换到该日的 5 分钟图。O ${day.open.toFixed(2)} / H ${day.high.toFixed(2)} / L ${day.low.toFixed(2)} / C ${day.close.toFixed(2)}。`;
  persistState();
  renderSummary();
}

function selectedCandleSnapshot(day, pauseSnapshot) {
  const selectedBar = visibleBarsForDay(day)[state.selectedIntradayBarIndex ?? -1];
  if (selectedBar) {
    return {
      label: `${selectedBar.timeLabel} · 5m`,
      open: selectedBar.open,
      high: selectedBar.high,
      low: selectedBar.low,
      close: selectedBar.close,
    };
  }
  const selectedDay = visibleDailyCandles()[state.selectedCampaignCandleIndex ?? -1];
  if (selectedDay) {
    return {
      label: `${selectedDay.dateLabel} · 日线`,
      open: selectedDay.open,
      high: selectedDay.high,
      low: selectedDay.low,
      close: selectedDay.close,
    };
  }
  const fallbackBar = currentVisibleBars(day)[currentVisibleBars(day).length - 1];
  if (fallbackBar) {
    return {
      label: `${fallbackBar.timeLabel} · 5m`,
      open: fallbackBar.open,
      high: fallbackBar.high,
      low: fallbackBar.low,
      close: fallbackBar.close,
    };
  }
  return {
    label: "未选中",
    open: pauseSnapshot.open,
    high: pauseSnapshot.high,
    low: pauseSnapshot.low,
    close: pauseSnapshot.close,
  };
}

function renderHeadlineFeed(day) {
  const target = document.querySelector("#headline-feed");
  const visibleBars = visibleBarsForDay(day);
  const currentTime = visibleBars[visibleBars.length - 1]?.timeLabel || "23:59";
  const items = day.headlineFeed.filter((item) => item.time <= currentTime);
  target.innerHTML = items.map((item) => `
    <article class="headline-item ${toneClass(item.tone)}">
      <div class="feed-head">
        <span class="feed-source">${item.source}</span>
        <span class="feed-tag">${item.tag || "快讯"}</span>
      </div>
      <strong>${item.title}</strong>
      <p>${item.body}</p>
      <div class="item-meta">
        <span>${marketPulseLabel(day.noiseSentiment)}</span>
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
  const visibleBars = visibleBarsForDay(day);
  const currentTime = visibleBars[visibleBars.length - 1]?.timeLabel || "23:59";
  const items = day.discussionFeed.filter((item) => item.time <= currentTime);
  target.innerHTML = items.map((item) => `
    <article class="discussion-item ${toneClass(item.tone)}">
      <div class="feed-head">
        <strong>${item.author}</strong>
        <span class="feed-handle">${item.handle || "@匿名"}</span>
      </div>
      <p>${item.text}</p>
      <div class="item-meta">
        <span>${item.time}</span>
        <span>${marketPulseLabel(day.noiseSentiment)}</span>
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
  const tradingDay = currentDay();
  const day = viewedDay();
  const pauseSnapshot = pauseDaySnapshot(day);
  const selectedSnapshot = selectedCandleSnapshot(day, pauseSnapshot);
  const tradingPauseSnapshot = pauseDaySnapshot(tradingDay);
  const equity = markToMarket(tradingPauseSnapshot.close);
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
  document.querySelector("#segment-chip").textContent = `第 ${state.campaignState.currentSegmentIndex + 1} 时段 / 5`;
  document.querySelector("#campaign-close").textContent = pauseSnapshot.close.toFixed(2);
  document.querySelector("#campaign-return").textContent = formatPct(campaignReturnPct);
  document.querySelector("#campaign-day-label").textContent = day.dateLabel;
  document.querySelector("#scenario-title").textContent = `${day.dateLabel} · ${day.regimeLabel}${day.dayIndex === tradingDay.dayIndex ? "" : " · 历史查看"}`;
  document.querySelector("#current-price").textContent = pauseSnapshot.close.toFixed(2);
  document.querySelector("#current-drawdown").textContent = formatPct(pauseSnapshot.drawdownPct);
  document.querySelector("#current-iv").textContent = day.iv.toFixed(2);
  const segmentBars = visibleBarsForDay(day);
  document.querySelector("#current-time").textContent = `第 ${state.campaignState.currentSegmentIndex + 1} 时段 / 5 · ${segmentBars[0]?.timeLabel || "-"} - ${segmentBars[segmentBars.length - 1]?.timeLabel || "-"}`;
  document.querySelector("#selected-k-label").textContent = selectedSnapshot.label;
  document.querySelector("#selected-k-open").textContent = Number(selectedSnapshot.open).toFixed(2);
  document.querySelector("#selected-k-high").textContent = Number(selectedSnapshot.high).toFixed(2);
  document.querySelector("#selected-k-low").textContent = Number(selectedSnapshot.low).toFixed(2);
  document.querySelector("#selected-k-close").textContent = Number(selectedSnapshot.close).toFixed(2);
  document.querySelector("#noise-headline").textContent = day.noiseHeadline;
  document.querySelector("#noise-body").textContent = day.noiseBody;
  document.querySelector("#noise-channel").textContent = `regime:${day.regimeKey}`;
  document.querySelector("#noise-sentiment").textContent = `${marketPulseLabel(day.noiseSentiment)} · ${day.noiseSentiment.toFixed(2)}`;
  document.querySelector("#position-state").textContent = state.campaignState.shares > 0 ? `${state.campaignState.shares.toFixed(2)} 股 @ ${state.campaignState.avgEntry.toFixed(2)}` : "Flat";
  document.querySelector("#size-state").textContent = `${((state.campaignState.shares * tradingPauseSnapshot.close) / Math.max(1, equity) * 100).toFixed(1)}%`;
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
  document.querySelector("#day-unrealized").textContent = formatMoney(unrealizedPnl(tradingPauseSnapshot.close));
  document.querySelector("#open-gap").textContent = formatPct(openGapPct);
  document.querySelector("#day-range").textContent = formatPct(dayRangePct);
  document.querySelector("#day-volume").textContent = formatVolume(totalVolume);
  document.querySelector("#sentiment-heat").textContent = `${sentimentHeat}/100`;
  document.querySelector("#order-mode-input").value = state.campaignState.orderMode || "amount";
  document.querySelector("#limit-price-input").value = (state.campaignState.limitPrice || tradingPauseSnapshot.close).toFixed(2);
  document.querySelector("#capital-input").value = String(DEFAULT_CAPITAL_BASE);
  document.querySelector("#capital-input").disabled = true;
  drawCampaignChart();
  drawIntradayChart(day, pauseSnapshot.bars);
  updateSegmentControls();
  renderHeadlineFeed(day);
  renderDiscussionFeed(day);
  renderLog();
  updateTradingControls(day.dayIndex === tradingDay.dayIndex);
}

function updateTradingControls(isTradingDayView) {
  const tradeButtons = ["#buy-day", "#sell-day", "#sell-all-day", "#hold-day"];
  for (const selector of tradeButtons) {
    const element = document.querySelector(selector);
    if (element) {
      element.disabled = !isTradingDayView || state.campaignState.completed;
    }
  }
}

function updateSegmentControls() {
  const nextButton = document.querySelector("#next-segment");
  if (!nextButton) return;
  if (state.campaignState.completed) {
    nextButton.disabled = true;
    nextButton.textContent = "已完成";
    return;
  }
  const isLastSegment = state.campaignState.currentSegmentIndex >= DAILY_SEGMENT_ENDS.length - 1;
  nextButton.disabled = false;
  nextButton.textContent = isLastSegment ? "进入下一交易日" : "进入下一段";
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

function advanceSegmentOrDay() {
  const isLastSegment = state.campaignState.currentSegmentIndex >= DAILY_SEGMENT_ENDS.length - 1;
  const isLastDay = state.campaignState.currentDayIndex >= state.campaign.dayCount - 1;
  if (!isLastSegment) {
    state.campaignState.currentSegmentIndex += 1;
    return { completed: false, movedToNextDay: false, movedToNextSegment: true };
  }
  if (isLastDay) {
    state.campaignState.completed = true;
    return { completed: true, movedToNextDay: false, movedToNextSegment: false };
  }
  state.campaignState.currentDayIndex += 1;
  state.campaignState.currentSegmentIndex = 0;
  return { completed: false, movedToNextDay: true, movedToNextSegment: false };
}

function advanceToNextDay(noteWhenMoved, noteWhenCompleted) {
  if (state.campaignState.completed) {
    return;
  }
  const isLastDay = state.campaignState.currentDayIndex >= state.campaign.dayCount - 1;
  if (isLastDay) {
    state.campaignState.completed = true;
    persistState();
    document.querySelector("#simulation-note").textContent = noteWhenCompleted;
    renderSummary();
    return;
  }
  state.campaignState.currentDayIndex += 1;
  state.campaignState.currentSegmentIndex = 0;
  syncLimitPriceToCurrentClose();
  persistState();
  document.querySelector("#simulation-note").textContent = noteWhenMoved;
  renderSummary();
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
  let message = "本次未下单。";
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
    message = "本次未下单。";
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
      scenario_id: `campaign-${day.regimeKey}-${day.dayIndex + 1}`,
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
    persistState();
    document.querySelector("#simulation-note").textContent = `${result.message} 如需继续，请点击“进入下一段”。`;
    renderSummary();
  } catch (error) {
    document.querySelector("#simulation-note").textContent = `写入测试行为失败：${error.message}`;
  }
}

function nextSegment() {
  if (state.campaignState.completed) {
    return;
  }
  const progress = advanceSegmentOrDay();
  state.chartFocusDayIndex = null;
  state.selectedIntradayBarIndex = null;
  state.selectedCampaignCandleIndex = null;
  if (!progress.completed) {
    syncLimitPriceToCurrentClose();
  }
  persistState();
  if (progress.completed) {
    document.querySelector("#simulation-note").textContent = "全部交易日已完成。你可以现在生成测试报告。";
  } else if (progress.movedToNextDay) {
    document.querySelector("#simulation-note").textContent = "今日 5 个交易时段已结束，已进入下一交易日。";
  } else {
    document.querySelector("#simulation-note").textContent = `已进入第 ${state.campaignState.currentSegmentIndex + 1} 时段 / 5。`;
  }
  renderSummary();
}

function endCurrentDay() {
  advanceToNextDay("今日已结束，已进入下一交易日。", "今日已结束，全部交易日已完成。");
}

async function skipEntireDay() {
  if (state.campaignState.completed) {
    return;
  }
  const day = currentDay();
  state.campaignState.capitalLocked = true;
  state.campaignState.actionLog.push({
    dayIndex: day.dayIndex,
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
  advanceToNextDay("已跳过今天，直接进入下一交易日。", "已跳过今天，全部交易日已完成。");
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
  state.chartFocusDayIndex = null;
  state.campaignState.capitalBase = DEFAULT_CAPITAL_BASE;
  state.campaignState.cash = DEFAULT_CAPITAL_BASE;
  state.campaignState.capitalLocked = true;
  state.campaignState.currentSegmentIndex = 0;
  state.campaignState.orderAmount = 5000;
  syncLimitPriceToCurrentClose();
  persistState();
  document.querySelector("#capital-input").value = String(DEFAULT_CAPITAL_BASE);
  document.querySelector("#capital-input").disabled = true;
  document.querySelector("#order-amount-input").value = "5000";
  renderSummary();
  document.querySelector("#simulation-note").textContent = "已重置测试。模拟本金固定为 30000，已开始新的测试序列。";
}

function syncInputsIntoState() {
  const orderAmount = Number(document.querySelector("#order-amount-input").value || 5000);
  const orderMode = document.querySelector("#order-mode-input").value || "amount";
  const limitPrice = Math.max(0.01, Number(document.querySelector("#limit-price-input").value || 100));
  state.campaignState.capitalBase = DEFAULT_CAPITAL_BASE;
  state.campaignState.orderAmount = Math.max(0, orderAmount);
  state.campaignState.orderMode = orderMode;
  state.campaignState.limitPrice = limitPrice;
  persistState();
}

document.querySelector("#buy-day")?.addEventListener("click", () => handleDecision("buy"));
document.querySelector("#sell-day")?.addEventListener("click", () => handleDecision("sell"));
document.querySelector("#sell-all-day")?.addEventListener("click", () => handleDecision("sell", { forceAll: true }));
document.querySelector("#hold-day")?.addEventListener("click", () => handleDecision("hold"));
document.querySelector("#show-intraday-chart")?.addEventListener("click", () => setChartMode("intraday"));
document.querySelector("#show-intraday-chart")?.addEventListener("click", () => {
  state.chartFocusDayIndex = null;
  renderSummary();
});
document.querySelector("#show-daily-chart")?.addEventListener("click", () => setChartMode("daily"));
document.querySelector("#next-segment")?.addEventListener("click", nextSegment);
document.querySelector("#end-day")?.addEventListener("click", endCurrentDay);
document.querySelector("#skip-day")?.addEventListener("click", skipEntireDay);
document.querySelector("#complete-simulation")?.addEventListener("click", completeSimulation);
document.querySelector("#reset-sim")?.addEventListener("click", resetCampaign);
document.querySelector("#capital-input")?.addEventListener("change", () => {
  document.querySelector("#capital-input").value = String(DEFAULT_CAPITAL_BASE);
  document.querySelector("#simulation-note").textContent = "模拟本金固定为 30000，测试过程中不可修改。";
  renderSummary();
});
document.querySelector("#order-amount-input")?.addEventListener("change", () => {
  state.campaignState.orderAmount = Math.max(0, Number(document.querySelector("#order-amount-input").value || 5000));
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

(async function bootstrapSimulationPage() {
  renderShell("simulation");
  state.campaign = await loadCampaign();
  state.campaignState = loadCampaignState();
  document.querySelector("#capital-input").value = String(DEFAULT_CAPITAL_BASE);
  document.querySelector("#capital-input").disabled = true;
  document.querySelector("#order-amount-input").value = String(state.campaignState.orderAmount || 5000);
  document.querySelector("#order-mode-input").value = state.campaignState.orderMode || "amount";
  syncLimitPriceToCurrentClose();
  syncOrderInputLabel();
  bindChartInteractions();
  setChartMode("intraday");
  renderSummary();
})();
