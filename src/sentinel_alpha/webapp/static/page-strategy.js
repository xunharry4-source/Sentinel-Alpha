const STRATEGY_LOG_PREFIX = "sentinel-alpha:strategy-log:";

function strategyLogKey(sessionId) {
  return `${STRATEGY_LOG_PREFIX}${sessionId || "anonymous"}`;
}

function loadStrategyLogs(sessionId) {
  try {
    return JSON.parse(window.localStorage.getItem(strategyLogKey(sessionId)) || "[]");
  } catch (error) {
    return [];
  }
}

function saveStrategyLogs(sessionId, logs) {
  window.localStorage.setItem(strategyLogKey(sessionId), JSON.stringify(logs));
}

function appendStrategyLog(level, message) {
  const sessionId = loadStoredSnapshot()?.session_id || "anonymous";
  const logs = loadStrategyLogs(sessionId);
  logs.unshift({
    timestamp: new Date().toLocaleString("zh-CN", { hour12: false }),
    level,
    message,
  });
  saveStrategyLogs(sessionId, logs.slice(0, 60));
  renderStrategyLogs();
}

function renderStrategyLogs() {
  const sessionId = loadStoredSnapshot()?.session_id || "anonymous";
  const logs = loadStrategyLogs(sessionId);
  renderList(
    "training-log-list",
    logs.map((item) => `[${item.timestamp}] ${item.level.toUpperCase()} / ${item.message}`),
    "还没有训练日志。"
  );
}

function renderStrategy(snapshot) {
  formatJsonIntoList("strategy-package-list", snapshot?.strategy_package || null, "还没有策略包。");
  renderList(
    "strategy-check-list",
    (snapshot?.strategy_checks || []).map((item) => {
      const fixes = (item.required_fix_actions || []).join("；");
      return `${item.check_type} / ${item.status} / ${item.summary}${fixes ? ` / 修复: ${fixes}` : ""}`;
    }),
    "等待策略检查。"
  );
  renderList(
    "feedback-list",
    (snapshot?.strategy_feedback_log || []).map((item) => `${item.strategy_type} / ${item.feedback}`),
    "还没有训练反馈。"
  );
  if (snapshot?.strategy_training_log?.length) {
    const sessionId = snapshot?.session_id || "anonymous";
    saveStrategyLogs(
      sessionId,
      snapshot.strategy_training_log
        .slice()
        .reverse()
        .map((item) => ({
          timestamp: item.timestamp || new Date().toLocaleString("zh-CN", { hour12: false }),
          level: item.status === "error" ? "error" : item.status === "rework_required" ? "warning" : "info",
          message: `第 ${item.iteration_no} 版 / ${item.strategy_type} / ${item.status}${item.failed_checks?.length ? ` / 失败检查: ${item.failed_checks.join(", ")}` : ""}${item.error ? ` / ${item.error}` : ""}`,
        }))
    );
  }
  renderStrategyLogs();
}

function setButtonBusy(buttonId, busy, busyText) {
  const button = document.querySelector(`#${buttonId}`);
  if (!button) return;
  if (!button.dataset.label) {
    button.dataset.label = button.textContent || "";
  }
  button.disabled = busy;
  button.textContent = busy ? busyText : button.dataset.label;
}

function validateStrategyPrerequisites(snapshot) {
  if (!snapshot?.session_id) {
    return "请先创建会话。";
  }
  if (!snapshot.behavioral_report) {
    return "请先完成模拟测试并生成 Behavioral Profiler 报告。";
  }
  if (!snapshot.trade_universe) {
    return "请先提交交易标的，再开始策略训练。";
  }
  return null;
}

async function submitUniverse() {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("strategy-note", "请先创建会话。");
    appendStrategyLog("error", "提交交易标的失败：没有活动会话。");
    return;
  }
  setButtonBusy("submit-universe", true, "提交中...");
  appendStrategyLog("info", "开始提交交易标的。");
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
    appendStrategyLog("success", `交易标的已提交：${(latest.trade_universe?.expanded || []).join(", ")}`);
  } catch (error) {
    setText("strategy-note", `提交交易标的失败：${error.message}`);
    appendStrategyLog("error", `提交交易标的失败：${error.message}`);
  } finally {
    setButtonBusy("submit-universe", false, "");
  }
}

async function iterateStrategy() {
  const snapshot = loadStoredSnapshot();
  const prerequisiteError = validateStrategyPrerequisites(snapshot);
  if (prerequisiteError) {
    setText("strategy-note", prerequisiteError);
    appendStrategyLog("warning", prerequisiteError);
    return;
  }
  const feedback = document.querySelector("#strategy-feedback-input").value.trim();
  const strategyType = document.querySelector("#strategy-type-input").value;
  const iterationMode = document.querySelector("#iteration-mode-input").value;
  const autoIterations = Math.max(1, Math.min(10, Number(document.querySelector("#auto-iterations-input").value || 1)));
  setButtonBusy("iterate-strategy", true, "训练中...");
  appendStrategyLog("info", `开始训练策略，类型=${strategyType}，模式=${iterationMode}，轮数=${autoIterations}${feedback ? `，反馈=${feedback}` : ""}`);
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/strategy/iterate`, {
      method: "POST",
      body: JSON.stringify({
        feedback,
        strategy_type: strategyType,
        auto_iterations: autoIterations,
        iteration_mode: iterationMode,
      }),
    });
    storeSnapshot(latest);
    renderShell("strategy");
    renderStrategy(latest);
    const phase = latest.phase || "unknown";
    const checks = latest.strategy_checks || [];
    const failed = checks.filter((item) => item.status === "fail");
    setText("strategy-note", failed.length ? "策略已生成，但检查未通过，必须继续重迭代。" : "策略已完成新一轮迭代。");
    appendStrategyLog("success", `策略训练完成，phase=${phase}，版本=${latest.strategy_package?.iteration_no || "-"}，模式=${iterationMode}`);
    if (latest.strategy_package?.llm_generation_summary) {
      appendStrategyLog("info", latest.strategy_package.llm_generation_summary);
    }
    checks.forEach((item) => {
      appendStrategyLog(item.status === "fail" ? "error" : "info", `${item.check_type}: ${item.summary}`);
    });
  } catch (error) {
    setText("strategy-note", `策略迭代失败：${error.message}`);
    appendStrategyLog("error", `策略迭代失败：${error.message}`);
  } finally {
    setButtonBusy("iterate-strategy", false, "");
  }
}

async function approveStrategy() {
  const snapshot = loadStoredSnapshot();
  const prerequisiteError = validateStrategyPrerequisites(snapshot);
  if (prerequisiteError) {
    setText("strategy-note", prerequisiteError);
    appendStrategyLog("warning", prerequisiteError);
    return;
  }
  setButtonBusy("approve-strategy", true, "确认中...");
  appendStrategyLog("info", "开始确认当前策略。");
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/strategy/approve`, { method: "POST" });
    storeSnapshot(latest);
    renderShell("strategy");
    renderStrategy(latest);
    setText("strategy-note", "策略已确认。");
    appendStrategyLog("success", `策略确认完成，phase=${latest.phase}`);
  } catch (error) {
    setText("strategy-note", `策略确认失败：${error.message}`);
    appendStrategyLog("error", `策略确认失败：${error.message}`);
  } finally {
    setButtonBusy("approve-strategy", false, "");
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
    appendStrategyLog("info", `已应用策略推荐：${report.recommended_strategy_type}`);
  } else {
    setText("strategy-recommendation-note", "当前还没有策略推荐。");
    appendStrategyLog("warning", "应用策略推荐失败：当前没有推荐策略类型。");
  }
});

(async function bootstrapStrategyPage() {
  renderShell("strategy");
  await ensureClientConfig();
  const stored = loadStoredSnapshot();
  let snapshot = stored;
  if (stored?.session_id) {
    try {
      snapshot = await refreshSnapshot();
    } catch (error) {
      appendStrategyLog("warning", `刷新策略页会话快照失败：${error.message}`);
    }
  }
  renderStrategy(snapshot || {});
  if (snapshot?.strategy_package?.strategy_type) {
    document.querySelector("#strategy-type-input").value = snapshot.strategy_package.strategy_type;
  } else if (snapshot?.behavioral_report?.recommended_strategy_type) {
    document.querySelector("#strategy-type-input").value = snapshot.behavioral_report.recommended_strategy_type;
  }
  if (snapshot?.strategy_package?.iteration_mode) {
    document.querySelector("#iteration-mode-input").value = snapshot.strategy_package.iteration_mode;
  }
  if (snapshot?.strategy_package?.auto_iterations_requested) {
    document.querySelector("#auto-iterations-input").value = String(snapshot.strategy_package.auto_iterations_requested);
  }
  if (snapshot?.trade_universe?.requested_symbols) {
    document.querySelector("#universe-symbols-input").value = snapshot.trade_universe.requested_symbols.join(",");
  } else if (snapshot?.trade_universe?.requested) {
    document.querySelector("#universe-symbols-input").value = snapshot.trade_universe.requested.join(",");
  }
  appendStrategyLog("info", "策略训练页已加载。");
})();
