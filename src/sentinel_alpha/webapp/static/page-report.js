function renderReportArchive(snapshot) {
  const reports = snapshot?.report_history || [];
  renderList(
    "report-history-list",
    reports
      .slice()
      .reverse()
      .map((item) => `${item.created_at} / ${item.report_type} / ${item.title}`),
    "当前还没有报告归档。"
  );
}

function renderHistoryTimeline(snapshot) {
  const events = snapshot?.history_events || [];
  renderList(
    "history-list",
    events
      .slice()
      .reverse()
      .map((item) => `${item.timestamp} / ${item.event_type} / ${item.summary}`),
    "当前还没有历史记录。"
  );
}

function renderReportPage(snapshot) {
  renderShell("report");
  formatJsonIntoList("report-list", snapshot?.behavioral_report || null, "当前还没有测试报告。");
  renderList(
    "evolution-list",
    (snapshot?.profile_evolution?.events || [])
      .slice()
      .reverse()
      .map((item) => `${item.timestamp} / ${item.source_type} / ${item.source_ref} / ${item.note || "no-note"}`),
    "等待画像演化数据。"
  );
  renderReportArchive(snapshot);
  renderHistoryTimeline(snapshot);
  const panel = document.querySelector("#report-json-panel");
  if (panel) {
    panel.textContent = JSON.stringify(snapshot?.behavioral_report || {}, null, 2);
  }
}

async function reloadReportPage() {
  try {
    const snapshot = await refreshSnapshot();
    renderReportPage(snapshot);
    setText("report-note", "测试报告、归档与历史记录已刷新。");
  } catch (error) {
    setText("report-note", `刷新测试报告失败：${error.message}`);
  }
}

document.querySelector("#refresh-report")?.addEventListener("click", reloadReportPage);

(async function bootstrapReportPage() {
  renderReportPage(loadStoredSnapshot());
})();
