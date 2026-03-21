async function setDeployment(mode) {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("operations-note", "请先创建会话。");
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/deployment`, {
      method: "POST",
      body: JSON.stringify({ execution_mode: mode }),
    });
    storeSnapshot(latest);
    renderShell("operations");
    renderOperations(latest);
    setText("operations-note", `执行模式已切换到 ${mode}。`);
  } catch (error) {
    setText("operations-note", `设置执行模式失败：${error.message}`);
  }
}

function renderOperations(snapshot) {
  renderList(
    "deployment-list",
    snapshot?.execution_mode ? [`execution_mode: ${snapshot.execution_mode}`, `phase: ${snapshot.phase}`, `status: ${snapshot.status}`] : [],
    "当前还没有部署信息。"
  );
  renderList(
    "monitor-list-page",
    (snapshot?.monitors || []).map((item) => `${item.monitor_type} / ${item.severity} / ${item.detail}`),
    "当前还没有监控结果。"
  );
  renderList(
    "trade-list",
    (snapshot?.trade_records || []).map((item) => `${item.symbol} / ${item.side} / pnl ${item.realized_pnl_pct}%`),
    "当前还没有交易记录。"
  );
  renderList(
    "market-list",
    (snapshot?.market_snapshots || []).map((item) => `${item.symbol} / ${item.timeframe} / close ${item.close_price}`),
    "当前还没有市场快照。"
  );
}

document.querySelector("#set-autonomous")?.addEventListener("click", () => setDeployment("autonomous"));
document.querySelector("#set-advice-only")?.addEventListener("click", () => setDeployment("advice_only"));

(function bootstrapOperationsPage() {
  renderShell("operations");
  renderOperations(loadStoredSnapshot() || {});
})();
