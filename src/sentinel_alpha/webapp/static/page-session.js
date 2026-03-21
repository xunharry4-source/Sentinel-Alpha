async function updateHealth() {
  try {
    const health = await apiRequest("/api/health");
    setText("session-health-note", `${health.api.detail} ${health.database.detail}`);
  } catch (error) {
    setText("session-health-note", `后端暂不可用：${error.message}`);
  }
}

function renderSessionDetails(snapshot) {
  formatJsonIntoList("session-current-list", snapshot, "当前还没有会话。");
}

async function createSessionFlow() {
  const userName = document.querySelector("#user-name-input").value || "User";
  const startingCapital = Number(document.querySelector("#starting-capital-input").value || 500000);
  try {
    setText("session-page-note", "正在创建会话并生成测试数据...");
    const created = await apiRequest("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ user_name: userName, starting_capital: startingCapital }),
    });
    const snapshot = await apiRequest(`/api/sessions/${created.session_id}/generate-scenarios`, { method: "POST" });
    storeSnapshot(snapshot);
    renderSessionDetails(snapshot);
    renderShell("session");
    setText("session-page-note", "会话已创建，测试数据已生成。下一步进入模拟测试页。");
  } catch (error) {
    setText("session-page-note", `创建会话失败：${error.message}`);
  }
}

async function generateOnly() {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("session-page-note", "请先创建会话。");
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/generate-scenarios`, { method: "POST" });
    storeSnapshot(latest);
    renderSessionDetails(latest);
    renderShell("session");
    setText("session-page-note", "测试数据已重新生成。");
  } catch (error) {
    setText("session-page-note", `生成测试数据失败：${error.message}`);
  }
}

document.querySelector("#create-session")?.addEventListener("click", createSessionFlow);
document.querySelector("#generate-scenarios")?.addEventListener("click", generateOnly);

(async function bootstrapSessionPage() {
  renderShell("session");
  await ensureClientConfig();
  await updateHealth();
  const snapshot = loadStoredSnapshot();
  if (snapshot) {
    renderSessionDetails(snapshot);
  }
})();
