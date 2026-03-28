const STRATEGY_FOCUS_KEY = "sentinel-alpha:strategy-focus-target";

function strategyPageForFocus(target) {
  if (target?.includes("research")) return "./strategy-results.html";
  if (target?.includes("repair") || target?.includes("check")) return "./strategy-training.html";
  return "./strategy.html";
}

function jumpFromIntelligence(targetPage, focusTarget = "") {
  if (focusTarget) {
    window.localStorage.setItem(STRATEGY_FOCUS_KEY, focusTarget);
    targetPage = strategyPageForFocus(focusTarget);
  }
  window.location.href = targetPage;
}

function latestIntelligenceReport(snapshot) {
  const runs = snapshot?.intelligence_runs || [];
  return runs.length ? runs[runs.length - 1].report || null : null;
}

function latestPayload(snapshot) {
  const financials = snapshot?.financials_runs || [];
  const darkPool = snapshot?.dark_pool_runs || [];
  const options = snapshot?.options_runs || [];
  if (options.length) return options[options.length - 1].payload || {};
  if (darkPool.length) return darkPool[darkPool.length - 1].payload || {};
  if (financials.length) return financials[financials.length - 1].payload || {};
  return latestIntelligenceReport(snapshot) || {};
}

function latestRun(runs) {
  return runs && runs.length ? runs[runs.length - 1] : null;
}

function intelligenceRunStamp(run) {
  return run?.timestamp || run?.generated_at || "unknown";
}

function summarizeIntelligenceRunForHistory(run) {
  if (!run) return "无";
  const report = run.report || {};
  const translatedDocuments = report.translated_documents || run.documents || [];
  const firstTranslated = translatedDocuments[0] || {};
  const translatedTitle = firstTranslated.translated_title || firstTranslated.title || "无标题";
  const translatedSummary = firstTranslated.brief_summary_cn || firstTranslated.translated_summary || firstTranslated.summary || "无摘要";
  const localizedSummary = report.summary || "无中文总结";
  return `${intelligenceRunStamp(run)} / ${run.query} / ${run.document_count} docs / 总结=${localizedSummary} / 首条=${translatedTitle} / 摘要=${translatedSummary}`;
}

function summarizeIntelligenceHistoryEvent(event) {
  const payload = event?.payload || {};
  const localizedSummary = payload.localized_summary || "无中文总结";
  const translatedCount = payload.translated_document_count;
  const translationStatus = payload.translation_status || "unknown";
  return `${event.timestamp} / ${event.event_type} / ${event.summary} / 翻译=${translatedCount ?? 0} / status=${translationStatus} / 总结=${localizedSummary}`;
}

function summarizeFactors(factors) {
  if (!factors || typeof factors !== "object") return [];
  return Object.entries(factors).map(([key, value]) => `${key} / ${typeof value === "object" ? JSON.stringify(value) : value}`);
}

function buildInformationClusters(events) {
  const clusters = new Map();
  (events || []).forEach((item) => {
    const anchor = item.anchor || "unknown";
    const current = clusters.get(anchor) || {
      anchor,
      categories: new Set(),
      providers: new Set(),
      latest: item.timestamp,
      count: 0,
      summaries: [],
    };
    current.categories.add(item.category || "unknown");
    if (item.provider) current.providers.add(item.provider);
    current.count += 1;
    current.latest = !current.latest || String(item.timestamp) > String(current.latest) ? item.timestamp : current.latest;
    if (item.summary) current.summaries.push(item.summary);
    clusters.set(anchor, current);
  });
  return Array.from(clusters.values()).map((item) => ({
    anchor: item.anchor,
    categories: Array.from(item.categories),
    providers: Array.from(item.providers),
    latest: item.latest,
    count: item.count,
    summary: item.summaries[item.summaries.length - 1] || "无",
  }));
}

function summarizeFinancials(run) {
  const payload = run?.payload || {};
  const normalized = payload.normalized || {};
  const statements = normalized.statements || [];
  const first = statements[0] || {};
  return [
    `symbol / ${run?.symbol || payload.symbol || "unknown"}`,
    `provider / ${run?.provider || payload.provider || "unknown"}`,
    `entity / ${normalized.entity_name || payload.entity_name || payload.company_name || payload.name || "unknown"}`,
    `report / ${normalized.report_period || payload.fiscal_period || payload.report_period || payload.fiscalDateEnding || "unknown"}`,
    `dedupe / ${normalized.dedupe_summary?.output_count || statements.length} / ${normalized.dedupe_summary?.input_count || statements.length}`,
    `weight / ${normalized.overall_weight ?? "unknown"}`,
    `headline / revenue=${first.revenue ?? "unknown"} / net_income=${first.net_income ?? "unknown"}`,
  ];
}

function summarizeDarkPool(run) {
  const payload = run?.payload || {};
  const normalized = payload.normalized || {};
  const items = normalized.records || [];
  const first = items[0] || {};
  return [
    `symbol / ${run?.symbol || payload.symbol || "unknown"}`,
    `provider / ${run?.provider || payload.provider || "unknown"}`,
    `records / ${normalized.dedupe_summary?.output_count || items.length}`,
    `dedupe / ${normalized.dedupe_summary?.output_count || items.length} / ${normalized.dedupe_summary?.input_count || items.length}`,
    `weight / ${normalized.overall_weight ?? "unknown"}`,
    `latest_volume / ${first.shares || first.volume || "unknown"}`,
    `venue / ${first.venue || "unknown"}`,
  ];
}

function summarizeOptions(run) {
  const payload = run?.payload || {};
  const normalized = payload.normalized || {};
  const items = normalized.contracts || [];
  const first = items[0] || {};
  return [
    `symbol / ${run?.symbol || payload.symbol || "unknown"}`,
    `provider / ${run?.provider || payload.provider || "unknown"}`,
    `expiration / ${run?.expiration || payload.expiration || normalized.expiration_dates?.[0] || "default"}`,
    `contracts / ${normalized.dedupe_summary?.output_count || items.length}`,
    `dedupe / ${normalized.dedupe_summary?.output_count || items.length} / ${normalized.dedupe_summary?.input_count || items.length}`,
    `weight / ${normalized.overall_weight ?? "unknown"}`,
    `anchor / strike=${first.strike || "unknown"} / iv=${first.implied_volatility || first.iv || "unknown"} / oi=${first.open_interest || "unknown"}`,
  ];
}

function populateProviderSelect(selectId, providers, defaultProvider) {
  const target = document.querySelector(`#${selectId}`);
  if (!target) return;
  target.innerHTML = [
    `<option value="">默认 Provider (${defaultProvider || "none"})</option>`,
    ...(providers || []).map((item) => `<option value="${item.provider}">${item.provider}</option>`),
  ].join("");
}

async function loadProviderOptions() {
  try {
    const payload = await apiRequest("/api/market-data/providers");
    populateProviderSelect("financials-provider-input", payload.fundamentals_providers, payload.fundamentals_default_provider);
    populateProviderSelect("dark-pool-provider-input", payload.dark_pool_providers, payload.dark_pool_default_provider);
    populateProviderSelect("options-provider-input", payload.options_providers, payload.options_default_provider);
  } catch (error) {
    setText("intelligence-note", `加载 Provider 列表失败：${error.message}`);
  }
}

function renderIntelligencePage(snapshot) {
  renderShell("intelligence");
  renderList(
    "intelligence-list",
    (snapshot?.intelligence_documents || []).map((item) => {
      const translatedTitle = item.translated_title || item.title || "untitled";
      const translatedSummary = item.brief_summary_cn || item.translated_summary || item.summary || "无摘要";
      const originalTitle = item.title && item.title !== translatedTitle ? ` / 原文=${item.title}` : "";
      return `${item.source} / ${translatedTitle}${originalTitle} / ${translatedSummary} / ${item.url}`;
    }),
    "当前还没有情报结果。"
  );

  const report = latestIntelligenceReport(snapshot);
  formatJsonIntoList("intelligence-report-list", report, "当前还没有情报摘要报告。");
  const reportPanel = document.querySelector("#intelligence-report-json");
  if (reportPanel) {
    reportPanel.textContent = JSON.stringify(report || {}, null, 2);
  }
  renderList("financials-summary-list", summarizeFinancials(latestRun(snapshot?.financials_runs)), "当前还没有财报摘要。");
  renderList("dark-pool-summary-list", summarizeDarkPool(latestRun(snapshot?.dark_pool_runs)), "当前还没有暗池摘要。");
  renderList("options-summary-list", summarizeOptions(latestRun(snapshot?.options_runs)), "当前还没有期权摘要。");
  renderList("intelligence-factors-list", summarizeFactors(report?.factors), "当前还没有情报因子。");
  renderList("financials-factors-list", summarizeFactors(latestRun(snapshot?.financials_runs)?.factors), "当前还没有财报因子。");
  renderList("dark-pool-factors-list", summarizeFactors(latestRun(snapshot?.dark_pool_runs)?.factors), "当前还没有暗池因子。");
  renderList("options-factors-list", summarizeFactors(latestRun(snapshot?.options_runs)?.factors), "当前还没有期权因子。");
  renderList(
    "information-cluster-list",
    buildInformationClusters(snapshot?.information_events)
      .slice()
      .reverse()
      .map((item) => `${item.latest} / ${item.anchor} / 类别=${item.categories.join(", ")} / providers=${item.providers.join(", ") || "none"} / 次数=${item.count} / ${item.summary}`),
    "当前还没有事件聚合视图。"
  );

  renderList(
    "intelligence-run-list",
    (snapshot?.intelligence_runs || [])
      .slice()
      .reverse()
      .map((item) => summarizeIntelligenceRunForHistory(item)),
    "当前还没有查询历史。"
  );
  renderList(
    "financials-run-list",
    (snapshot?.financials_runs || [])
      .slice()
      .reverse()
      .map((item) => `${intelligenceRunStamp(item)} / ${item.symbol} / ${item.provider}`),
    "当前还没有财报查询历史。"
  );
  renderList(
    "dark-pool-run-list",
    (snapshot?.dark_pool_runs || [])
      .slice()
      .reverse()
      .map((item) => `${intelligenceRunStamp(item)} / ${item.symbol} / ${item.provider}`),
    "当前还没有暗池查询历史。"
  );
  renderList(
    "options-run-list",
    (snapshot?.options_runs || [])
      .slice()
      .reverse()
      .map((item) => `${intelligenceRunStamp(item)} / ${item.symbol} / ${item.provider} / ${item.expiration || "default"}`),
    "当前还没有期权查询历史。"
  );
  renderList(
    "intelligence-history-list",
    (snapshot?.history_events || [])
      .filter((item) => {
        const eventType = String(item.event_type || "");
        return (
          eventType.includes("intelligence") ||
          eventType.includes("financials") ||
          eventType.includes("dark_pool") ||
          eventType.includes("options")
        );
      })
      .slice()
      .reverse()
      .map((item) => String(item.event_type || "").includes("intelligence_search_completed") ? summarizeIntelligenceHistoryEvent(item) : `${item.timestamp} / ${item.event_type} / ${item.summary}`),
    "当前还没有历史记录。"
  );

  const payloadPanel = document.querySelector("#intelligence-market-json");
  if (payloadPanel) {
    payloadPanel.textContent = JSON.stringify(latestPayload(snapshot), null, 2);
  }

  const latestIntelRun = latestRun(snapshot?.intelligence_runs);
  const latestFinancialsRun = latestRun(snapshot?.financials_runs);
  const latestDarkPoolRun = latestRun(snapshot?.dark_pool_runs);
  const latestOptionsRun = latestRun(snapshot?.options_runs);
  const cacheLines = [
    report?.profile?.generation_mode ? `摘要来源: ${report.profile.generation_mode}` : null,
    report?.profile?.generation_mode === "template_fallback" ? "警告: 当前摘要为模板回退，不是 live LLM 完整总结" : null,
    latestIntelRun ? `情报搜索: ${latestIntelRun.cache_hit ? "命中缓存" : "实时获取"}` : null,
    latestFinancialsRun ? `财报: ${latestFinancialsRun.cache_hit ? "命中缓存" : "实时获取"}` : null,
    latestDarkPoolRun ? `暗池: ${latestDarkPoolRun.cache_hit ? "命中缓存" : "实时获取"}` : null,
    latestOptionsRun ? `期权: ${latestOptionsRun.cache_hit ? "命中缓存" : "实时获取"}` : null,
  ].filter(Boolean);
  setText("intelligence-cache-note", cacheLines.length ? cacheLines.join(" / ") : "当前还没有缓存命中信息。");
}

async function requireSession() {
  const snapshot = await resolveCurrentSnapshot();
  if (!snapshot?.session_id) {
    setText("intelligence-note", "请先创建会话，或带上 session_id 重新打开情报中心页面。");
    return null;
  }
  return snapshot;
}

async function searchIntelligence() {
  const snapshot = await requireSession();
  if (!snapshot) return;
  const query = (document.querySelector("#intelligence-query-input")?.value || "").trim();
  const maxDocuments = Number(document.querySelector("#intelligence-max-input")?.value || 5);
  if (!query) {
    setText("intelligence-note", "请输入搜索词。");
    return;
  }
  setText("intelligence-note", "情报搜索进行中，请稍候...");
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/intelligence/search`, {
      method: "POST",
      body: JSON.stringify({
        query,
        max_documents: maxDocuments,
      }),
    });
    storeSnapshot(latest);
    renderIntelligencePage(latest);
    const run = latestRun(latest.intelligence_runs);
    const mode = run?.report?.profile?.generation_mode || "unknown";
    setText("intelligence-note", run?.cache_hit ? `情报搜索命中缓存，已直接复用上次结果。摘要来源=${mode}` : `情报搜索、摘要分析与历史归档已完成。摘要来源=${mode}`);
  } catch (error) {
    setText("intelligence-note", `情报搜索失败：${error.message}`);
  }
}

async function searchFinancials() {
  const snapshot = await requireSession();
  if (!snapshot) return;
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/intelligence/financials`, {
      method: "POST",
      body: JSON.stringify({
        symbol: document.querySelector("#financials-symbol-input").value,
        provider: document.querySelector("#financials-provider-input").value || null,
      }),
    });
    storeSnapshot(latest);
    renderIntelligencePage(latest);
    const run = latestRun(latest.financials_runs);
    setText("intelligence-note", run?.cache_hit ? "财报查询命中缓存，已直接复用上次结果。" : "财报查询、历史记录与报告归档已完成。");
  } catch (error) {
    setText("intelligence-note", `财报查询失败：${error.message}`);
  }
}

async function searchDarkPool() {
  const snapshot = await requireSession();
  if (!snapshot) return;
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/intelligence/dark-pool`, {
      method: "POST",
      body: JSON.stringify({
        symbol: document.querySelector("#dark-pool-symbol-input").value,
        provider: document.querySelector("#dark-pool-provider-input").value || null,
      }),
    });
    storeSnapshot(latest);
    renderIntelligencePage(latest);
    const run = latestRun(latest.dark_pool_runs);
    setText("intelligence-note", run?.cache_hit ? "暗池查询命中缓存，已直接复用上次结果。" : "暗池查询、历史记录与报告归档已完成。");
  } catch (error) {
    setText("intelligence-note", `暗池查询失败：${error.message}`);
  }
}

async function searchOptions() {
  const snapshot = await requireSession();
  if (!snapshot) return;
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/intelligence/options`, {
      method: "POST",
      body: JSON.stringify({
        symbol: document.querySelector("#options-symbol-input").value,
        provider: document.querySelector("#options-provider-input").value || null,
        expiration: document.querySelector("#options-expiration-input").value || null,
      }),
    });
    storeSnapshot(latest);
    renderIntelligencePage(latest);
    const run = latestRun(latest.options_runs);
    setText("intelligence-note", run?.cache_hit ? "期权查询命中缓存，已直接复用上次结果。" : "期权查询、历史记录与报告归档已完成。");
  } catch (error) {
    setText("intelligence-note", `期权查询失败：${error.message}`);
  }
}

document.querySelector("#search-intelligence")?.addEventListener("click", searchIntelligence);
document.querySelector("#intelligence-query-input")?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchIntelligence().catch((error) => {
      setText("intelligence-note", `情报搜索失败：${error.message}`);
    });
  }
});
document.querySelector("#search-financials")?.addEventListener("click", searchFinancials);
document.querySelector("#search-dark-pool")?.addEventListener("click", searchDarkPool);
document.querySelector("#search-options")?.addEventListener("click", searchOptions);
document.querySelector("#jump-intel-to-strategy")?.addEventListener("click", () => jumpFromIntelligence("./strategy-results.html", "#strategy-research-summary-list"));
document.querySelector("#jump-intel-to-config")?.addEventListener("click", () => jumpFromIntelligence("./configuration.html"));

(async function bootstrapIntelligencePage() {
  const snapshot = await resolveCurrentSnapshot();
  renderIntelligencePage(snapshot || loadCurrentSnapshot());
  loadProviderOptions();
})();
