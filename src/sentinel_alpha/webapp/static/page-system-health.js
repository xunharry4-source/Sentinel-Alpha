const SYSTEM_HEALTH_POLL_MS = 10000;
let systemHealthTimerId = null;

function renderCounts(modules) {
  const okCount = modules.filter((item) => item.status === "ok").length;
  const warningCount = modules.filter((item) => item.status === "warning").length;
  const errorCount = modules.filter((item) => item.status === "error").length;
  document.querySelector("#health-ok-count").textContent = String(okCount);
  document.querySelector("#health-warning-count").textContent = String(warningCount);
  document.querySelector("#health-error-count").textContent = String(errorCount);
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
  const calls = totals.reduce((sum, item) => sum + Number(item.calls || 0), 0);
  const inputTokens = totals.reduce((sum, item) => sum + Number(item.input_tokens || 0), 0);
  const outputTokens = totals.reduce((sum, item) => sum + Number(item.output_tokens || 0), 0);
  const providers = new Set(totals.map((item) => item.provider).filter(Boolean));
  document.querySelector("#token-call-count").textContent = String(calls);
  document.querySelector("#token-input-count").textContent = String(inputTokens);
  document.querySelector("#token-output-count").textContent = String(outputTokens);
  document.querySelector("#token-provider-count").textContent = String(providers.size);
  renderList(
    "token-usage-list",
    totals
      .sort((a, b) => Number(b.calls || 0) - Number(a.calls || 0))
      .map((item) => `${item.task} / ${item.provider}/${item.model} / calls=${item.calls} / in=${item.input_tokens} / out=${item.output_tokens}`),
    "当前还没有 token 使用记录。"
  );
}

function renderErrors(errors) {
  renderList(
    "system-error-list",
    (errors || []).slice().reverse().map((item) => `${item.timestamp} / ${item.agent} / ${item.operation} / ${item.detail}`),
    "当前没有错误。"
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
    renderErrors(payload.recent_errors || []);
    renderAgentLogs(payload.recent_agent_logs || []);
    renderTokenUsage(payload.token_usage || {});
  } catch (error) {
    document.querySelector("#system-health-status").textContent = "ERROR";
    document.querySelector("#system-health-note").textContent = `系统健康检查失败：${error.message}`;
    renderCounts([]);
    renderCards("system-health-grid", [], "module");
    renderCards("library-health-grid", [], "module");
    renderCards("agent-health-grid", [], "agent");
    renderErrors([]);
    renderAgentLogs([]);
    renderTokenUsage({});
  } finally {
    scheduleNextRefresh();
  }
}

document.querySelector("#refresh-system-health")?.addEventListener("click", refreshSystemHealth);

(async function bootstrapSystemHealthPage() {
  renderShell("system-health");
  await ensureClientConfig();
  await refreshSystemHealth();
})();
