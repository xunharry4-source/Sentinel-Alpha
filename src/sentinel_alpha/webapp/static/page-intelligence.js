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
    renderShell("intelligence");
    renderList(
      "intelligence-list",
      (latest.intelligence_documents || []).map((item) => `${item.source} / ${item.title} / ${item.url}`),
      "当前还没有情报结果。"
    );
    setText("intelligence-note", "情报搜索完成。");
  } catch (error) {
    setText("intelligence-note", `情报搜索失败：${error.message}`);
  }
}

document.querySelector("#search-intelligence")?.addEventListener("click", searchIntelligence);

(function bootstrapIntelligencePage() {
  renderShell("intelligence");
  const snapshot = loadStoredSnapshot();
  renderList(
    "intelligence-list",
    (snapshot?.intelligence_documents || []).map((item) => `${item.source} / ${item.title} / ${item.url}`),
    "当前还没有情报结果。"
  );
})();
