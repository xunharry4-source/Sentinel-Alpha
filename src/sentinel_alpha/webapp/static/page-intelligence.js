function latestIntelligenceReport(snapshot) {
  const runs = snapshot?.intelligence_runs || [];
  return runs.length ? runs[runs.length - 1].report || null : null;
}

function renderIntelligencePage(snapshot) {
  renderShell("intelligence");
  renderList(
    "intelligence-list",
    (snapshot?.intelligence_documents || []).map((item) => `${item.source} / ${item.title} / ${item.url}`),
    "当前还没有情报结果。"
  );
  const report = latestIntelligenceReport(snapshot);
  formatJsonIntoList("intelligence-report-list", report, "当前还没有情报摘要报告。");
  const reportPanel = document.querySelector("#intelligence-report-json");
  if (reportPanel) {
    reportPanel.textContent = JSON.stringify(report || {}, null, 2);
  }
  renderList(
    "intelligence-run-list",
    (snapshot?.intelligence_runs || [])
      .slice()
      .reverse()
      .map((item) => `${item.generated_at} / ${item.query} / ${item.document_count} docs`),
    "当前还没有查询历史。"
  );
  renderList(
    "intelligence-history-list",
    (snapshot?.history_events || [])
      .filter((item) => String(item.event_type || "").includes("intelligence"))
      .slice()
      .reverse()
      .map((item) => `${item.timestamp} / ${item.event_type} / ${item.summary}`),
    "当前还没有历史记录。"
  );
}

async function searchIntelligence() {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("intelligence-note", "请先创建会话。");
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/intelligence/search`, {
      method: "POST",
      body: JSON.stringify({
        query: document.querySelector("#intelligence-query-input").value,
        max_documents: Number(document.querySelector("#intelligence-max-input").value || 5),
      }),
    });
    storeSnapshot(latest);
    renderIntelligencePage(latest);
    setText("intelligence-note", "情报搜索、摘要分析与历史归档已完成。");
  } catch (error) {
    setText("intelligence-note", `情报搜索失败：${error.message}`);
  }
}

document.querySelector("#search-intelligence")?.addEventListener("click", searchIntelligence);

(function bootstrapIntelligencePage() {
  renderIntelligencePage(loadStoredSnapshot());
})();
