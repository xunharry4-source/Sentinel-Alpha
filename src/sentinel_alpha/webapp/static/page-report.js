async function reloadReportPage() {
  try {
    const snapshot = await refreshSnapshot();
    renderShell("report");
    formatJsonIntoList("report-list", snapshot.behavioral_report || null, "当前还没有测试报告。");
    renderList(
      "evolution-list",
      (snapshot.profile_evolution?.events || []).map((item) => `${item.source_type} / ${item.source_ref} / ${item.note || "no-note"}`),
      "等待画像演化数据。"
    );
    const panel = document.querySelector("#report-json-panel");
    if (panel) {
      panel.textContent = JSON.stringify(snapshot.behavioral_report || {}, null, 2);
    }
    setText("report-note", "测试报告已刷新。");
  } catch (error) {
    setText("report-note", `刷新测试报告失败：${error.message}`);
  }
}

document.querySelector("#refresh-report")?.addEventListener("click", reloadReportPage);

(async function bootstrapReportPage() {
  renderShell("report");
  const snapshot = loadStoredSnapshot();
  formatJsonIntoList("report-list", snapshot?.behavioral_report || null, "当前还没有测试报告。");
  renderList(
    "evolution-list",
    (snapshot?.profile_evolution?.events || []).map((item) => `${item.source_type} / ${item.source_ref} / ${item.note || "no-note"}`),
    "等待画像演化数据。"
  );
  const panel = document.querySelector("#report-json-panel");
  if (panel) {
    panel.textContent = JSON.stringify(snapshot?.behavioral_report || {}, null, 2);
  }
})();
