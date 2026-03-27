const SYSTEM_HEALTH_POLL_MS = 10000;
const STRATEGY_FOCUS_KEY = "sentinel-alpha:strategy-focus-target";
const TERMINAL_FOCUS_KEY = "sentinel-alpha:terminal-focus-target";
const DEBUG_MODE_KEY = "sentinel-alpha:debug-mode";
let systemHealthTimerId = null;

function strategyPageForFocus(target) {
  if (target?.includes("repair") || target?.includes("check")) return "./strategy-training.html";
  if (target?.includes("research") || target?.includes("backtest")) return "./strategy-results.html";
  return "./strategy.html";
}

function jumpFromHealth(targetPage, focusTarget = "", focusKey = STRATEGY_FOCUS_KEY) {
  if (focusTarget) {
    window.localStorage.setItem(focusKey, focusTarget);
    if (focusKey === STRATEGY_FOCUS_KEY) {
      targetPage = strategyPageForFocus(focusTarget);
    }
  }
  window.location.href = targetPage;
}

function renderCounts(modules) {
  const okCount = modules.filter((item) => item.status === "ok").length;
  const warningCount = modules.filter((item) => item.status === "warning").length;
  const errorCount = modules.filter((item) => item.status === "error").length;
  document.querySelector("#health-ok-count").textContent = String(okCount);
  document.querySelector("#health-warning-count").textContent = String(warningCount);
  document.querySelector("#health-error-count").textContent = String(errorCount);
}



function formatDebugPayload(payload) {
  if (payload === null || typeof payload === "undefined") return "none";
  try {
    const text = JSON.stringify(payload);
    return text.length <= 240 ? text : `${text.slice(0, 240)}...`;
  } catch (error) {
    return String(payload);
  }
}

function isDebugModeEnabled() {
  return window.localStorage.getItem(DEBUG_MODE_KEY) === "1" || new URLSearchParams(window.location.search).get("debug") === "1";
}

function updateDebugModeUi() {
  const shell = document.querySelector("#agent-debug-shell");
  const button = document.querySelector("#toggle-debug-mode");
  const enabled = isDebugModeEnabled();
  if (shell) shell.hidden = !enabled;
  if (button) button.textContent = enabled ? "关闭 DEBUG 模式" : "开启 DEBUG 模式";
}

function toggleDebugMode() {
  const enabled = isDebugModeEnabled();
  if (enabled) {
    window.localStorage.removeItem(DEBUG_MODE_KEY);
  } else {
    window.localStorage.setItem(DEBUG_MODE_KEY, "1");
  }
  updateDebugModeUi();
}

function renderAgentDebug(payload) {
  const target = document.querySelector("#agent-debug-grid");
  const logs = payload?.recent_agent_logs || [];
  const agents = payload?.agents || [];
  if (!target) return;
  if (!logs.length && !agents.length) {
    target.innerHTML = `<article class="check-card"><strong>当前还没有 Agent DEBUG 节点。</strong></article>`;
    renderList("agent-debug-trace-list", [], "当前还没有 DEBUG Trace。");
    renderList("agent-debug-focus-list", [], "当前还没有失败焦点。");
    return;
  }

  const latestByAgent = new Map();
  for (const item of logs) {
    latestByAgent.set(item.agent, item);
  }
  target.innerHTML = agents.map((item) => {
    const latest = latestByAgent.get(item.agent) || {};
    const status = latest.status || item.status || "idle";
    const chip = status === "ok" ? "success-chip" : status === "warning" || status === "idle" ? "warn-chip" : "danger-chip";
    const card = status === "ok" ? "check-pass" : status === "warning" || status === "idle" ? "check-warning" : "check-fail";
    return `
      <article class="check-card ${card}">
        <div class="check-head">
          <strong>${item.agent || item.name}</strong>
          <span class="status-chip ${chip}">${String(status).toUpperCase()}</span>
        </div>
        <p class="check-summary">${latest.detail || item.detail || item.last_detail || "No detail."}</p>
        <p class="check-label">Node</p>
        <p>${latest.operation || item.last_operation || "idle"}</p>
        <p class="check-label">Last Seen</p>
        <p>${latest.timestamp || item.last_seen || "unknown"}</p>
        <p class="check-label">Errors</p>
        <p>${item.error_count || 0}</p>
        <p class="check-label">Session</p>
        <p>${latest.session_id || "global"}</p>
        <p class="check-label">Request</p>
        <p>${formatDebugPayload(latest.request_payload)}</p>
        <p class="check-label">Response</p>
        <p>${formatDebugPayload(latest.response_payload)}</p>
      </article>
    `;
  }).join("");

  const traceLines = logs.slice().reverse().slice(0, 20).map((item) => {
    return `${item.timestamp} / ${item.agent} / ${item.status} / ${item.operation} / session=${item.session_id || "global"} / ${item.detail} / req=${formatDebugPayload(item.request_payload)} / res=${formatDebugPayload(item.response_payload)}`;
  });
  renderList("agent-debug-trace-list", traceLines, "当前还没有 DEBUG Trace。");

  const latestError = logs.slice().reverse().find((item) => item.status === "error");
  if (!latestError) {
    renderList("agent-debug-focus-list", ["当前没有最新失败焦点，Agent 节点整体可用。"], "当前还没有失败焦点。");
    return;
  }
  const focus = logs.filter((item) => item.session_id === latestError.session_id || item.agent === latestError.agent).slice(-8);
  renderList(
    "agent-debug-focus-list",
    [
      `latest_error / ${latestError.timestamp} / ${latestError.agent} / ${latestError.operation}`,
      `latest_error_detail / ${latestError.detail}`,
      `request / ${formatDebugPayload(latestError.request_payload)}`,
      `response / ${formatDebugPayload(latestError.response_payload)}`,
      ...focus.map((item) => `trace / ${item.timestamp} / ${item.agent} / ${item.status} / ${item.operation} / ${item.detail}`),
    ],
    "当前还没有失败焦点。"
  );
}

function renderCards(targetId, items, kind = "module") {
  const target = document.querySelector(`#${targetId}`);
  if (!target) return;
  if (!items?.length) {
    target.innerHTML = `<article class="check-card"><strong>暂无${kind === "module" ? "模块" : "Agent"}状态。</strong></article>`;
    return;
  }
  target.innerHTML = items.map((item) => `
    <article class="check-card check-${item.status === "ok" ? "pass" : item.status === "warning" ? "warning" : item.status === "idle" ? "warning" : "fail"}">
      <div class="check-head">
        <strong>${item.name || item.agent}</strong>
        <span class="status-chip ${item.status === "ok" ? "success-chip" : item.status === "warning" || item.status === "idle" ? "warn-chip" : "danger-chip"}">${String(item.status).toUpperCase()}</span>
      </div>
      <p class="check-summary">${item.detail || item.last_detail || "No detail."}</p>
      ${item.last_operation ? `<p class="check-label">Last Operation</p><p>${item.last_operation}</p>` : ""}
      ${item.last_seen ? `<p class="check-label">Last Seen</p><p>${item.last_seen}</p>` : ""}
      ${typeof item.activity_count === "number" ? `<p class="check-label">Activity</p><p>${item.activity_count} runs / ${item.error_count || 0} errors</p>` : ""}
      <p class="check-label">Fix Recommendation</p>
      <p>${item.recommendation || "No action required."}</p>
    </article>
  `).join("");
}

function renderTokenUsage(usage) {
  const totals = Object.values(usage?.totals || {});
  const aggregate = usage?.aggregate || {};
  const recentCalls = usage?.recent_calls || [];
  const calls = Number(aggregate.api_request_count ?? totals.reduce((sum, item) => sum + Number(item.calls || 0), 0));
  const inputTokens = Number(aggregate.input_tokens ?? totals.reduce((sum, item) => sum + Number(item.input_tokens || 0), 0));
  const outputTokens = Number(aggregate.output_tokens ?? totals.reduce((sum, item) => sum + Number(item.output_tokens || 0), 0));
  const providers = new Set(totals.map((item) => item.provider).filter(Boolean));
  document.querySelector("#token-call-count").textContent = String(calls);
  document.querySelector("#token-input-count").textContent = String(inputTokens);
  document.querySelector("#token-output-count").textContent = String(outputTokens);
  document.querySelector("#token-provider-count").textContent = String(providers.size);
  renderList(
    "token-usage-list",
    totals
      .sort((a, b) => Number(b.calls || 0) - Number(a.calls || 0))
      .map((item) => `${item.task} / ${item.provider}/${item.model} / calls=${item.calls} / cache_hits=${item.cache_hits || 0} / in=${item.input_tokens} / out=${item.output_tokens}`),
    "当前还没有 token 使用记录。"
  );
  const summaryTarget = document.querySelector("#token-usage-summary-list");
  if (summaryTarget) {
    renderList(
      "token-usage-summary-list",
      [
        `api_requests / ${aggregate.api_request_count ?? calls}`,
        `total_tokens / ${aggregate.total_tokens ?? inputTokens + outputTokens}`,
        `live_requests / ${aggregate.live_request_count ?? 0}`,
        `fallback_requests / ${aggregate.fallback_request_count ?? 0}`,
      ],
      "当前还没有 token 汇总。"
    );
  }

  renderList(
    "llm-recent-calls-list",
    (recentCalls || []).slice().reverse().slice(0, 20).map((item) => {
      const fallback = item.fallback_reason ? ` / fallback=${item.fallback_reason}` : "";
      const key = item.active_api_key_env ? ` / key=${item.active_api_key_env}` : "";
      return `${item.timestamp} / ${item.task} / ${item.provider}/${item.model} / mode=${item.generation_mode}${key}${fallback} / in=${item.input_tokens} / out=${item.output_tokens}`;
    }),
    "当前还没有 LLM 最近调用。"
  );
}

function renderPerformance(performance) {
  document.querySelector("#perf-mode").textContent = performance?.mode || "-";
  document.querySelector("#perf-dataset-hits").textContent = String(performance?.dataset_plan_cache?.hits || 0);
  document.querySelector("#perf-context-hits").textContent = String(performance?.iteration_context_cache?.hits || 0);
  document.querySelector("#perf-llm-hits").textContent = String(performance?.llm_cache?.hits || 0);
  document.querySelector("#perf-eval-hits").textContent = String(performance?.candidate_evaluation_cache?.hits || 0);
  document.querySelector("#perf-intel-hits").textContent = String(performance?.intelligence_cache?.hits || 0);
  renderList(
    "performance-summary-list",
    [
      `dataset_plan cache: ${performance?.dataset_plan_cache?.entries || 0}/${performance?.dataset_plan_cache?.max_entries || 0} / hits=${performance?.dataset_plan_cache?.hits || 0} / misses=${performance?.dataset_plan_cache?.misses || 0}`,
      `iteration_context cache: ${performance?.iteration_context_cache?.entries || 0}/${performance?.iteration_context_cache?.max_entries || 0} / hits=${performance?.iteration_context_cache?.hits || 0} / misses=${performance?.iteration_context_cache?.misses || 0}`,
      `candidate_evaluation cache: ${performance?.candidate_evaluation_cache?.entries || 0}/${performance?.candidate_evaluation_cache?.max_entries || 0} / hits=${performance?.candidate_evaluation_cache?.hits || 0} / misses=${performance?.candidate_evaluation_cache?.misses || 0}`,
      `intelligence cache: ${performance?.intelligence_cache?.entries || 0}/${performance?.intelligence_cache?.max_entries || 0} / hits=${performance?.intelligence_cache?.hits || 0} / misses=${performance?.intelligence_cache?.misses || 0}`,
      `market_data cache: ${performance?.market_data_cache?.entries || 0}/${performance?.market_data_cache?.max_entries || 0} / hits=${performance?.market_data_cache?.hits || 0} / misses=${performance?.market_data_cache?.misses || 0}`,
      `llm cache: ${performance?.llm_cache?.entries || 0}/${performance?.llm_cache?.max_entries || 0} / hits=${performance?.llm_cache?.hits || 0} / misses=${performance?.llm_cache?.misses || 0}`,
    ],
    "当前还没有性能摘要。"
  );
}

function renderErrors(errors) {
  renderList(
    "system-error-list",
    (errors || []).slice().reverse().map((item) => `${item.timestamp} / ${item.agent} / ${item.operation} / ${item.detail}`),
    "当前没有错误。"
  );
}

function renderTerminalIntegrationHealth() {
  const snapshot = loadStoredSnapshot() || {};
  const runs = snapshot?.terminal_integration_runs || [];
  if (!runs.length) {
    renderList("terminal-integration-health-list", [], "当前还没有终端接入健康摘要。");
    return;
  }
  const latest = runs[runs.length - 1] || {};
  const test = latest.terminal_test || {};
  const runtime = latest.terminal_runtime_summary || {};
  const reliability = latest.terminal_reliability_summary || {};
  const checks = test.checks || [];
  const passed = checks.filter((item) => item.status === "pass").length;
  const recentRuns = runs.slice(-5);
  const recentStates = recentRuns.map((run) => run.terminal_test?.status || "not_tested");
  const recentRatios = recentRuns.map((run) => {
    const testChecks = run.terminal_test?.checks || [];
    const testPassed = testChecks.filter((item) => item.status === "pass").length;
    return `${run.run_id || "unknown"}:${testPassed}/${testChecks.length || 0}`;
  });
  const recentRoutes = recentRuns
    .map((run) => run.terminal_test?.repair_summary?.primary_route)
    .filter(Boolean);
  const trendStatus =
    recentStates.length >= 2 &&
    recentStates[recentStates.length - 1] === "ok" &&
    recentStates.some((item) => item !== "ok")
      ? "improving"
      : recentStates.length >= 2 &&
          recentStates[recentStates.length - 1] !== "ok" &&
          recentStates[recentStates.length - 2] === recentStates[recentStates.length - 1]
        ? "stalled"
        : recentStates.length >= 2 &&
            recentStates[recentStates.length - 1] === "warning" &&
            recentStates[recentStates.length - 2] === "ok"
          ? "degrading"
          : "flat";
  renderList(
    "terminal-integration-health-list",
    [
      `latest_run / ${latest.run_id || "unknown"} / ${latest.terminal_name || "unknown"} / ${latest.terminal_type || "unknown"}`,
      `runtime / ${runtime.status || "unknown"} / ${runtime.note || "无"} / contract_confidence=${runtime.contract_confidence ?? "none"} / shape_confidence=${runtime.shape_confidence ?? "none"}`,
      `reliability / ${reliability.status || "unknown"} / ${reliability.note || "无"} / revalidate=${reliability.revalidation_required ? "yes" : "no"}`,
      `readiness / ${latest.integration_readiness_summary?.status || "unknown"} / endpoints=${latest.integration_readiness_summary?.endpoint_count || 0}/${latest.integration_readiness_summary?.required_endpoint_count || 0}`,
      `docs / ${latest.docs_context?.docs_fetch_ok ? "ok" : "fail"} / ready=${latest.validation?.ready_for_programmer_agent ? "yes" : "no"}`,
      `test / ${test.status || "not_tested"} / passed=${passed}/${checks.length || 0}`,
      `trend / ${trendStatus} / recent_statuses=${recentStates.join(" -> ") || "none"}`,
      `recent_checks / ${recentRatios.join(" / ") || "none"}`,
      `recent_repairs / ${recentRoutes.join(" -> ") || "none"}`,
      `summary / ${test.summary || "终端方案已生成，但还没有执行 smoke test。"}`,
      `repair / ${test.repair_summary?.primary_route || "none"} / ${test.repair_summary?.priority || "none"}`,
      `module / ${latest.target_module || "unknown"}`,
      `next / ${(reliability.next_action || runtime.next_action) || (test.status === "ok" ? "可继续交给 Programmer Agent 或进入更强联通测试。" : (test.repair_summary?.actions?.[0] || "建议先到终端接入页检查 endpoint 和 smoke test 失败项。"))}`,
    ],
    "当前还没有终端接入健康摘要。"
  );
}

function renderDataHealth(payload) {
  const dataHealth = payload?.data_health || {};
  renderList(
    "data-health-list",
    [
      `status / ${dataHealth.status || "unknown"} / ${dataHealth.note || "无"}`,
      `sessions_with_data / ${dataHealth.sessions_with_data ?? 0}`,
      `latest_market / ${dataHealth.latest_market_timestamp || "none"} / ${dataHealth.latest_market_symbol || "none"}`,
      `latest_intelligence / ${dataHealth.latest_intelligence_timestamp || "none"} / ${dataHealth.latest_intelligence_query || "none"}`,
      `latest_financials / ${dataHealth.latest_financials_timestamp || "none"} / ${dataHealth.latest_financials_provider || "none"}`,
      `latest_dark_pool / ${dataHealth.latest_dark_pool_timestamp || "none"} / ${dataHealth.latest_dark_pool_provider || "none"}`,
      `latest_options / ${dataHealth.latest_options_timestamp || "none"} / ${dataHealth.latest_options_provider || "none"}`,
      `freshness / max_stale_hours=${dataHealth.max_stale_hours ?? "none"} / stale=${(dataHealth.stale_sources || []).join(", ") || "none"} / critical=${(dataHealth.critical_stale_sources || []).join(", ") || "none"}`,
      `recent_failures / ${dataHealth.recent_failure_count ?? 0}`,
      `failure_ops / ${(dataHealth.recent_failure_operations || []).join(" -> ") || "none"}`,
      `failure_counts / ${Object.entries(dataHealth.recent_failure_counts || {}).map(([name, count]) => `${name}=${count}`).join(" / ") || "none"}`,
    ],
    "当前还没有数据健康摘要。"
  );
}

function renderRuntimeHealth(payload) {
  const runtime = payload?.runtime_health || {};
  const research = runtime.research || {};
  const repair = runtime.repair || {};
  const terminal = runtime.terminal || {};
  const data = runtime.data || {};
  const llm = runtime.llm || {};
  const recovery = runtime.runtime_recovery_summary || {};
  renderList(
    "runtime-health-list",
    [
      `overall / ${runtime.status || "unknown"} / ${runtime.note || "无"} / revalidate=${runtime.revalidation_required ? "yes" : "no"}`,
      `runtime_recovery / ${recovery.status || "unknown"} / mode=${recovery.next_mode || "unknown"} / blockers=${(recovery.blockers || []).join(", ") || "none"}`,
      `runtime_recovery_note / ${recovery.note || "无"}`,
      `research / ${research.status || "unknown"} / ${research.note || "无"} / ${research.timestamp || "none"} / age=${research.age_hours ?? "none"} / revalidate=${research.revalidation_required ? "yes" : "no"}`,
      `research_next / ${(research.recovery_actions || []).join("；") || "none"}`,
      `repair / ${repair.status || "unknown"} / ${repair.note || "无"} / ${repair.timestamp || "none"} / age=${repair.age_hours ?? "none"} / revalidate=${repair.revalidation_required ? "yes" : "no"}`,
      `repair_next / ${(repair.recovery_actions || []).join("；") || "none"}`,
      `terminal / ${terminal.status || "unknown"} / ${terminal.note || "无"} / ${terminal.timestamp || "none"} / age=${terminal.age_hours ?? "none"} / revalidate=${terminal.revalidation_required ? "yes" : "no"}`,
      `terminal_next / ${terminal.next_action || "none"} / route=${terminal.primary_route || "none"}`,
      `terminal_recovery / ${(terminal.recovery_actions || []).join("；") || "none"}`,
      `data / ${data.status || "unknown"} / ${data.note || "无"} / revalidate=${data.revalidation_required ? "yes" : "no"}`,
      `data_next / ${(data.recovery_actions || []).join("；") || "none"}`,
      `llm / ${llm.status || "unknown"} / ${llm.note || "无"} / live=${llm.live_task_count ?? 0} / fallback=${llm.fallback_task_count ?? 0} / revalidate=${llm.revalidation_required ? "yes" : "no"}`,
      `llm_usage / api_requests=${llm.api_request_count ?? 0} / total_tokens=${llm.total_tokens ?? 0} / live_requests=${llm.live_request_count ?? 0} / fallback_requests=${llm.fallback_request_count ?? 0}`,
      `llm_quality / fallback_ratio=${llm.fallback_ratio ?? 0} / recent_fallback_ratio=${llm.recent_fallback_ratio ?? 0} / cache_hit_ratio=${llm.cache_hit_ratio ?? 0} / recent_calls=${llm.recent_call_count ?? 0}`,
      `llm_keys / active=${(llm.active_api_key_envs || []).join(", ") || "none"} / rotations=${llm.rotated_credential_count ?? 0}`,
      ...Object.entries(llm.provider_runtime || {}).map(([provider, info]) => `llm_provider / ${provider} / active=${info.active_api_key_env || "none"} / available=${(info.available_api_key_envs || []).join(", ") || "none"} / creds=${info.credential_count ?? 0} / rotations=${info.rotated_credential_count ?? 0}`),
      `llm_next / ${(llm.recovery_actions || []).join("；") || "none"}`,
      `llm_fallback_tasks / ${(llm.fallback_tasks || []).join(", ") || "none"}`,
      `overall_next / ${(recovery.actions || runtime.recommended_actions || []).join("；") || "none"}`,
    ],
    "当前还没有长期运行健康结论。"
  );
}

function renderAgentLogs(logs) {
  renderList(
    "agent-log-list",
    (logs || []).slice().reverse().map((item) => `${item.timestamp} / ${item.agent} / ${item.status} / ${item.operation} / ${item.detail}`),
    "当前还没有 Agent 运行日志。"
  );
}

function scheduleNextRefresh() {
  if (systemHealthTimerId !== null) {
    window.clearTimeout(systemHealthTimerId);
  }
  systemHealthTimerId = window.setTimeout(() => {
    refreshSystemHealth();
  }, SYSTEM_HEALTH_POLL_MS);
}

async function refreshSystemHealth() {
  try {
    const payload = await apiRequest("/api/system-health");
    document.querySelector("#system-health-status").textContent = `${payload.status.toUpperCase()} / ${payload.service_mode}`;
    document.querySelector("#system-health-note").textContent = `更新时间 ${payload.timestamp}`;
    renderCounts(payload.modules || []);
    renderCards("system-health-grid", payload.modules || [], "module");
    renderCards("library-health-grid", payload.libraries || [], "module");
    renderCards("agent-health-grid", payload.agents || [], "agent");
    renderPerformance(payload.performance || {});
    renderErrors(payload.recent_errors || []);
    renderTerminalIntegrationHealth();
    renderDataHealth(payload);
    renderRuntimeHealth(payload);
    renderAgentLogs(payload.recent_agent_logs || []);
    renderAgentDebug(payload);
    renderTokenUsage(payload.token_usage || {});
  } catch (error) {
    document.querySelector("#system-health-status").textContent = "ERROR";
    document.querySelector("#system-health-note").textContent = `系统健康检查失败：${error.message}`;
    renderCounts([]);
    renderCards("system-health-grid", [], "module");
    renderCards("library-health-grid", [], "module");
    renderCards("agent-health-grid", [], "agent");
    renderPerformance({});
    renderErrors([]);
    renderTerminalIntegrationHealth();
    renderDataHealth({});
    renderRuntimeHealth({});
    renderAgentLogs([]);
    renderTokenUsage({});
  } finally {
    scheduleNextRefresh();
  }
}

document.querySelector("#refresh-system-health")?.addEventListener("click", refreshSystemHealth);
document.querySelector("#jump-health-to-config")?.addEventListener("click", () => jumpFromHealth("./configuration.html"));
document.querySelector("#jump-health-to-strategy")?.addEventListener("click", () => jumpFromHealth("./strategy-training.html", "#strategy-repair-route-list"));
document.querySelector("#jump-health-to-terminal")?.addEventListener("click", () => jumpFromHealth("./trading-terminal-integration.html", "#terminal-repair-summary", TERMINAL_FOCUS_KEY));
document.querySelector("#toggle-debug-mode")?.addEventListener("click", toggleDebugMode);

(async function bootstrapSystemHealthPage() {
  renderShell("system-health");
  updateDebugModeUi();
  await ensureClientConfig();
  await refreshSystemHealth();
})();
