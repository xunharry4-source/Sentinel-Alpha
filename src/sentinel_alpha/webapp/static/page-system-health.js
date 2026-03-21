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

function renderModuleCards(modules) {
  const target = document.querySelector("#system-health-grid");
  if (!target) return;
  if (!modules?.length) {
    target.innerHTML = `<article class="check-card"><strong>暂无模块状态。</strong><p>系统健康检查还没有返回结果。</p></article>`;
    return;
  }
  target.innerHTML = modules.map((item) => `
    <article class="check-card check-${item.status === "ok" ? "pass" : item.status === "warning" ? "warning" : "fail"}">
      <div class="check-head">
        <strong>${item.name}</strong>
        <span class="status-chip ${item.status === "ok" ? "success-chip" : item.status === "warning" ? "warn-chip" : "danger-chip"}">${item.status.toUpperCase()}</span>
      </div>
      <p class="check-summary">${item.detail}</p>
      <p class="check-label">Fix Recommendation</p>
      <p>${item.recommendation || "No action required."}</p>
    </article>
  `).join("");
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
    const modules = payload.modules || [];
    renderCounts(modules);
    renderModuleCards(modules);
  } catch (error) {
    document.querySelector("#system-health-status").textContent = "ERROR";
    document.querySelector("#system-health-note").textContent = `系统健康检查失败：${error.message}`;
    renderCounts([]);
    renderModuleCards([]);
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
