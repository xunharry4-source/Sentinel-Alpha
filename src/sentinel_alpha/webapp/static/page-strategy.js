function renderStrategy(snapshot) {
  formatJsonIntoList("strategy-package-list", snapshot?.strategy_package || null, "还没有策略包。");
  renderList(
    "strategy-check-list",
    (snapshot?.strategy_checks || []).map((item) => `${item.check_type} / ${item.status} / ${item.summary}`),
    "等待策略检查。"
  );
  renderList(
    "feedback-list",
    (snapshot?.strategy_feedback_log || []).map((item) => `${item.strategy_type} / ${item.feedback}`),
    "还没有训练反馈。"
  );
}

async function submitUniverse() {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("strategy-note", "请先创建会话。");
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/trade-universe`, {
      method: "POST",
      body: JSON.stringify({
        input_type: document.querySelector("#universe-type-input").value,
        symbols: document.querySelector("#universe-symbols-input").value.split(",").map((item) => item.trim()).filter(Boolean),
        allow_overfit_override: false,
      }),
    });
    storeSnapshot(latest);
    renderShell("strategy");
    renderStrategy(latest);
    setText("strategy-note", "交易标的已提交。");
  } catch (error) {
    setText("strategy-note", `提交交易标的失败：${error.message}`);
  }
}

async function iterateStrategy() {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("strategy-note", "请先创建会话。");
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/strategy/iterate`, {
      method: "POST",
      body: JSON.stringify({
        feedback: document.querySelector("#strategy-feedback-input").value,
        strategy_type: document.querySelector("#strategy-type-input").value,
      }),
    });
    storeSnapshot(latest);
    renderShell("strategy");
    renderStrategy(latest);
    setText("strategy-note", "策略已完成新一轮迭代。");
  } catch (error) {
    setText("strategy-note", `策略迭代失败：${error.message}`);
  }
}

async function approveStrategy() {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("strategy-note", "请先创建会话。");
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/strategy/approve`, { method: "POST" });
    storeSnapshot(latest);
    renderShell("strategy");
    renderStrategy(latest);
    setText("strategy-note", "策略已确认。");
  } catch (error) {
    setText("strategy-note", `策略确认失败：${error.message}`);
  }
}

document.querySelector("#submit-universe")?.addEventListener("click", submitUniverse);
document.querySelector("#iterate-strategy")?.addEventListener("click", iterateStrategy);
document.querySelector("#approve-strategy")?.addEventListener("click", approveStrategy);
document.querySelector("#apply-strategy-recommendation")?.addEventListener("click", () => {
  const report = loadStoredSnapshot()?.behavioral_report || {};
  if (report.recommended_strategy_type) {
    document.querySelector("#strategy-type-input").value = report.recommended_strategy_type;
    setText("strategy-recommendation-note", report.strategy_type_recommendation_note || "已应用策略推荐。");
  } else {
    setText("strategy-recommendation-note", "当前还没有策略推荐。");
  }
});

(function bootstrapStrategyPage() {
  renderShell("strategy");
  const snapshot = loadStoredSnapshot();
  renderStrategy(snapshot || {});
  if (snapshot?.strategy_package?.strategy_type) {
    document.querySelector("#strategy-type-input").value = snapshot.strategy_package.strategy_type;
  } else if (snapshot?.behavioral_report?.recommended_strategy_type) {
    document.querySelector("#strategy-type-input").value = snapshot.behavioral_report.recommended_strategy_type;
  }
  if (snapshot?.trade_universe?.requested_symbols) {
    document.querySelector("#universe-symbols-input").value = snapshot.trade_universe.requested_symbols.join(",");
  }
})();
