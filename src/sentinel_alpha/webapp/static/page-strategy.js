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

function getStrategyArchiveEntries(snapshot) {
  const reports = (snapshot?.report_history || []).filter((item) => item.report_type === "strategy_iteration");
  return reports
    .map((item) => {
      const body = item.body || {};
      const pkg = body.strategy_package || {};
      return {
        reportId: item.report_id,
        createdAt: item.created_at,
        title: item.title,
        versionLabel: pkg.version_label || "unknown",
        strategyType: pkg.strategy_type || "unknown",
        pkg,
        checks: body.strategy_checks || [],
        logEntry: body.training_log_entry || {},
      };
    })
    .filter((item) => item.versionLabel !== "unknown");
}

function populateVersionSelectors(snapshot) {
  const entries = getStrategyArchiveEntries(snapshot);
  const selectors = [
    document.querySelector("#compare-version-a"),
    document.querySelector("#compare-version-b"),
    document.querySelector("#history-version-select"),
    document.querySelector("#restore-version-select"),
  ];
  selectors.forEach((select) => {
    if (!select) return;
    const currentValue = select.value;
    select.innerHTML = entries.length
      ? entries.map((item) => `<option value="${item.versionLabel}">${item.versionLabel}</option>`).join("")
      : `<option value="">暂无版本</option>`;
    if (entries.some((item) => item.versionLabel === currentValue)) {
      select.value = currentValue;
    }
  });
  const compareA = document.querySelector("#compare-version-a");
  const compareB = document.querySelector("#compare-version-b");
  if (entries.length >= 2 && compareA && compareB) {
    if (!compareA.value) compareA.value = entries[0].versionLabel;
    if (!compareB.value) compareB.value = entries[1].versionLabel;
  }
  if (entries.length && document.querySelector("#history-version-select") && !document.querySelector("#history-version-select").value) {
    document.querySelector("#history-version-select").value = entries[0].versionLabel;
  }
}

function renderStrategyStatus(snapshot) {
  const pkg = snapshot?.strategy_package;
  if (!pkg) {
    renderList("strategy-status-list", [], "当前还没有训练状态。");
    return;
  }
  const recommended = pkg.recommended_variant || {};
  renderList(
    "strategy-status-list",
    [
      `当前阶段: ${snapshot.phase || "unknown"}`,
      `当前版本: ${pkg.version_label || "unknown"}`,
      `策略类型: ${pkg.strategy_type || "unknown"}`,
      `迭代模式: ${pkg.iteration_mode || "unknown"}`,
      `目标函数: ${pkg.objective_metric || "unknown"}`,
      `推荐候选: ${recommended.variant_id || "unknown"}`,
      `推荐理由: ${recommended.reason || "无"}`,
      `当前标的池: ${(pkg.selected_universe || []).join(", ") || "无"}`,
    ],
    "当前还没有训练状态。"
  );
}

function renderStrategyAnalysis(snapshot) {
  const analysis = snapshot?.strategy_package?.analysis;
  if (!analysis) {
    renderList("strategy-analysis-list", [], "还没有分析结果。");
    return;
  }
  const issues = analysis.current_strategy_problems || [];
  const previous = analysis.previous_failure_reasons || {};
  renderList(
    "strategy-analysis-list",
    [
      `目标函数: ${analysis.objective_metric}`,
      `分析摘要: ${analysis.summary}`,
      `当前问题: ${issues.join("；") || "无"}`,
      `上次失败: ${previous.summary || "无"}`,
      `失败检查: ${(previous.failed_checks || []).join(", ") || "无"}`,
      `本轮反馈: ${analysis.feedback || "无"}`,
    ],
    "还没有分析结果。"
  );
}

function renderStrategyHistory(snapshot) {
  const logs = snapshot?.strategy_training_log || [];
  renderList(
    "strategy-history-list",
    logs
      .slice()
      .reverse()
      .map((item) => {
        const target = item.objective_metric ? ` / 目标=${item.objective_metric}` : "";
        const failed = item.failed_checks?.length ? ` / 失败检查=${item.failed_checks.join(", ")}` : "";
        const error = item.error ? ` / 错误=${item.error}` : "";
        return `${item.timestamp} / 第${item.iteration_no || "-"}版 / ${item.strategy_type || "unknown"} / ${item.status || "unknown"}${target}${failed}${error}`;
      }),
    "还没有策略迭代历史。"
  );
}

function renderStrategyArchive(snapshot) {
  const reports = getStrategyArchiveEntries(snapshot);
  renderList(
    "strategy-report-archive-list",
    reports
      .slice()
      .reverse()
      .map((item) => `${item.createdAt} / ${item.title} / ${item.versionLabel} / ${item.strategyType} / ${(item.pkg.selected_universe || []).join(", ") || "no-universe"}`),
    "还没有策略报告归档。"
  );
}

function renderFailureEvolution(snapshot) {
  const logs = snapshot?.strategy_training_log || [];
  const failures = logs.filter((item) => item.status === "rework_required" || item.status === "error");
  const timeline = document.querySelector("#failure-evolution-timeline");
  if (timeline) {
    if (!failures.length) {
      timeline.innerHTML = `<article class="timeline-card"><strong>当前还没有失败原因演化记录。</strong></article>`;
    } else {
      timeline.innerHTML = failures
        .slice()
        .reverse()
        .map((item) => {
          const failedChecks = item.failed_checks?.length ? item.failed_checks.join(", ") : "无";
          const summary = item.analysis_summary || item.error || "无";
          return `
            <article class="timeline-card">
              <strong>${item.timestamp} / 第${item.iteration_no || "-"}版 / ${item.strategy_type || "unknown"}</strong>
              <p>状态: ${item.status || "unknown"}</p>
              <p>失败检查: ${failedChecks}</p>
              <p>原因: ${summary}</p>
            </article>
          `;
        })
        .join("");
    }
  }
  renderList(
    "failure-evolution-list",
    failures
      .slice()
      .reverse()
      .map((item) => {
        const failedChecks = item.failed_checks?.length ? item.failed_checks.join(", ") : "无";
        const summary = item.analysis_summary || item.error || "无";
        return `${item.timestamp} / 第${item.iteration_no || "-"}版 / ${item.strategy_type || "unknown"} / 失败检查=${failedChecks} / 原因=${summary}`;
      }),
    "当前还没有失败原因演化记录。"
  );
}

function renderVersionCode(snapshot) {
  const target = document.querySelector("#history-code-panel");
  if (!target) return;
  const selected = document.querySelector("#history-version-select")?.value;
  const entry = getStrategyArchiveEntries(snapshot).find((item) => item.versionLabel === selected);
  if (!entry) {
    target.textContent = "还没有历史版本代码。";
    return;
  }
  const recommendedId = entry.pkg.recommended_variant?.variant_id;
  const variant = (entry.pkg.candidate_variants || []).find((item) => item.variant_id === recommendedId);
  target.textContent = variant?.generated_code || entry.pkg.generated_strategy_code || "该版本没有代码产物。";
}

function runVersionCompare(snapshot) {
  const entries = getStrategyArchiveEntries(snapshot);
  const versionA = document.querySelector("#compare-version-a")?.value;
  const versionB = document.querySelector("#compare-version-b")?.value;
  const a = entries.find((item) => item.versionLabel === versionA);
  const b = entries.find((item) => item.versionLabel === versionB);
  if (!a || !b) {
    renderList("strategy-compare-list", [], "还没有版本对比结果。");
    return;
  }
  const aEval = a.pkg.recommended_variant?.evaluation || a.pkg.baseline_evaluation || {};
  const bEval = b.pkg.recommended_variant?.evaluation || b.pkg.baseline_evaluation || {};
  renderList(
    "strategy-compare-list",
    [
      `版本A: ${a.versionLabel} / ${a.strategyType}`,
      `版本B: ${b.versionLabel} / ${b.strategyType}`,
      `收益差: ${(Number(bEval.expected_return_pct || 0) - Number(aEval.expected_return_pct || 0)).toFixed(2)}%`,
      `胜率差: ${(Number(bEval.win_rate_pct || 0) - Number(aEval.win_rate_pct || 0)).toFixed(2)}%`,
      `回撤差: ${(Number(bEval.drawdown_pct || 0) - Number(aEval.drawdown_pct || 0)).toFixed(2)}%`,
      `最大亏损差: ${(Number(bEval.max_loss_pct || 0) - Number(aEval.max_loss_pct || 0)).toFixed(2)}%`,
      `目标分差: ${(Number(bEval.objective_score || 0) - Number(aEval.objective_score || 0)).toFixed(4)}`,
      `版本A失败检查: ${(a.logEntry.failed_checks || []).join(", ") || "无"}`,
      `版本B失败检查: ${(b.logEntry.failed_checks || []).join(", ") || "无"}`,
    ],
    "还没有版本对比结果。"
  );
}

function renderProgrammerRuns(snapshot) {
  const runs = snapshot?.programmer_runs || [];
  renderList(
    "programmer-run-list",
    runs
      .slice()
      .reverse()
      .map((item) => `${item.timestamp || "unknown"} / ${item.status || "unknown"} / commit=${item.commit_hash || "none"} / rollback=${item.rollback_commit || "none"} / files=${(item.changed_files || []).join(", ") || "none"}`),
    "还没有 Programmer Agent 记录。"
  );
  const panel = document.querySelector("#programmer-diff-panel");
  if (panel) {
    panel.textContent = runs.length ? (runs[runs.length - 1].diff || runs[runs.length - 1].stderr || "没有差异输出。") : "还没有代码差异。";
  }
}

async function runProgrammerAgent() {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("strategy-note", "请先创建会话。");
    appendStrategyLog("warning", "Programmer Agent 执行失败：没有活动会话。");
    return;
  }
  setButtonBusy("run-programmer-agent", true, "执行中...");
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/programmer/execute`, {
      method: "POST",
      body: JSON.stringify({
        instruction: document.querySelector("#programmer-instruction").value.trim(),
        target_files: document.querySelector("#programmer-target-files").value.split(",").map((item) => item.trim()).filter(Boolean),
        context: document.querySelector("#programmer-context").value.trim(),
        commit_changes: true,
      }),
    });
    storeSnapshot(latest);
    renderShell("strategy");
    renderStrategy(latest);
    const latestRun = (latest.programmer_runs || [])[latest.programmer_runs.length - 1] || {};
    setText("strategy-note", `Programmer Agent 已执行，status=${latestRun.status || "unknown"}。`);
    appendStrategyLog("info", `Programmer Agent 执行完成，commit=${latestRun.commit_hash || "none"}。`);
  } catch (error) {
    setText("strategy-note", `Programmer Agent 执行失败：${error.message}`);
    appendStrategyLog("error", `Programmer Agent 执行失败：${error.message}`);
  } finally {
    setButtonBusy("run-programmer-agent", false, "");
  }
}

function restoreStrategyVersion(snapshot) {
  const selected = document.querySelector("#restore-version-select")?.value;
  const entry = getStrategyArchiveEntries(snapshot).find((item) => item.versionLabel === selected);
  if (!entry) {
    setText("strategy-note", "没有可恢复的版本。");
    appendStrategyLog("warning", "恢复版本失败：未找到目标版本。");
    return;
  }
  const pkg = entry.pkg || {};
  if (pkg.strategy_type) {
    document.querySelector("#strategy-type-input").value = pkg.strategy_type;
  }
  if (pkg.feedback !== undefined && document.querySelector("#strategy-feedback-input")) {
    document.querySelector("#strategy-feedback-input").value = pkg.feedback || "";
  }
  if (pkg.objective_metric) {
    document.querySelector("#objective-metric-input").value = pkg.objective_metric;
  }
  if (pkg.objective_targets) {
    document.querySelector("#target-return-input").value = String(pkg.objective_targets.target_return_pct ?? 18);
    document.querySelector("#target-winrate-input").value = String(pkg.objective_targets.target_win_rate_pct ?? 58);
    document.querySelector("#target-drawdown-input").value = String(pkg.objective_targets.target_drawdown_pct ?? 12);
    document.querySelector("#target-maxloss-input").value = String(pkg.objective_targets.target_max_loss_pct ?? 6);
  }
  if (pkg.iteration_mode) {
    document.querySelector("#iteration-mode-input").value = pkg.iteration_mode;
  }
  if (pkg.auto_iterations_requested) {
    document.querySelector("#auto-iterations-input").value = String(pkg.auto_iterations_requested);
  }
  if (pkg.selected_universe?.length && document.querySelector("#universe-symbols-input")) {
    document.querySelector("#universe-symbols-input").value = pkg.selected_universe.join(",");
  }
  setText("strategy-note", `已恢复版本 ${entry.versionLabel} 到当前实验配置。`);
  appendStrategyLog("info", `已恢复版本 ${entry.versionLabel} 到当前实验配置。`);
}

function variantScoreLine(title, evaluation) {
  if (!evaluation) return `${title}: 无评估`;
  return `${title}: 收益 ${evaluation.expected_return_pct}% / 胜率 ${evaluation.win_rate_pct}% / 回撤 ${evaluation.drawdown_pct}% / 最大亏损 ${evaluation.max_loss_pct}% / 目标分 ${evaluation.objective_score}`;
}

function renderVariantComparison(snapshot) {
  const target = document.querySelector("#strategy-variant-grid");
  if (!target) return;
  const pkg = snapshot?.strategy_package;
  if (!pkg?.baseline_evaluation || !pkg?.candidate_variants?.length) {
    target.innerHTML = `<article class="check-card"><strong>还没有方案对比。</strong><p>完成一轮策略训练后，这里会显示 baseline 与两个方案的结果。</p></article>`;
    return;
  }
  const recommended = pkg.recommended_variant || {};
  const baselineCard = `
    <article class="check-card">
      <div class="check-head">
        <strong>Baseline</strong>
        <span class="status-chip outline-chip">基准</span>
      </div>
      <p class="check-summary">${variantScoreLine("基准结果", pkg.baseline_evaluation)}</p>
    </article>
  `;
  const variantCards = pkg.candidate_variants.map((variant) => {
    const plan = variant.plan || {};
    const evaluation = variant.evaluation || {};
    const selected = recommended.variant_id === variant.variant_id;
    return `
      <article class="check-card ${selected ? "check-pass" : ""}">
        <div class="check-head">
          <strong>${plan.plan_name || variant.variant_id}</strong>
          <span class="status-chip ${selected ? "success-chip" : "outline-chip"}">${selected ? "推荐" : "候选"}</span>
        </div>
        <p class="check-summary">${plan.focus || "无说明"}</p>
        <p>${variantScoreLine("评估结果", evaluation)}</p>
        <p class="check-label">改进点</p>
        <p>${(plan.changes || []).join("；") || "无"}</p>
      </article>
    `;
  }).join("");
  target.innerHTML = baselineCard + variantCards;
}

function renderStrategyCode(snapshot) {
  const target = document.querySelector("#strategy-code-panel");
  if (!target) return;
  const pkg = snapshot?.strategy_package;
  if (!pkg?.generated_strategy_code) {
    target.textContent = "还没有策略代码。";
    return;
  }
  const recommended = pkg.recommended_variant?.variant_id;
  const variant = (pkg.candidate_variants || []).find((item) => item.variant_id === recommended);
  target.textContent = variant?.generated_code || pkg.generated_strategy_code;
}

function renderStrategy(snapshot) {
  formatJsonIntoList("strategy-package-list", snapshot?.strategy_package || null, "还没有策略包。");
  renderStrategyStatus(snapshot);
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
  renderStrategyAnalysis(snapshot);
  renderStrategyHistory(snapshot);
  renderStrategyArchive(snapshot);
  renderFailureEvolution(snapshot);
  populateVersionSelectors(snapshot);
  renderVariantComparison(snapshot);
  renderStrategyCode(snapshot);
  renderVersionCode(snapshot);
  runVersionCompare(snapshot);
  renderProgrammerRuns(snapshot);
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
  const objectiveMetric = document.querySelector("#objective-metric-input").value;
  const targetReturn = Number(document.querySelector("#target-return-input").value || 18);
  const targetWinRate = Number(document.querySelector("#target-winrate-input").value || 58);
  const targetDrawdown = Number(document.querySelector("#target-drawdown-input").value || 12);
  const targetMaxLoss = Number(document.querySelector("#target-maxloss-input").value || 6);
  setButtonBusy("iterate-strategy", true, "训练中...");
  appendStrategyLog("info", `开始训练策略，类型=${strategyType}，模式=${iterationMode}，轮数=${autoIterations}，目标=${objectiveMetric}${feedback ? `，反馈=${feedback}` : ""}`);
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/strategy/iterate`, {
      method: "POST",
      body: JSON.stringify({
        feedback,
        strategy_type: strategyType,
        auto_iterations: autoIterations,
        iteration_mode: iterationMode,
        objective_metric: objectiveMetric,
        target_return_pct: targetReturn,
        target_win_rate_pct: targetWinRate,
        target_drawdown_pct: targetDrawdown,
        target_max_loss_pct: targetMaxLoss,
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
document.querySelector("#run-version-compare")?.addEventListener("click", () => runVersionCompare(loadStoredSnapshot() || {}));
document.querySelector("#history-version-select")?.addEventListener("change", () => renderVersionCode(loadStoredSnapshot() || {}));
document.querySelector("#restore-version-button")?.addEventListener("click", () => restoreStrategyVersion(loadStoredSnapshot() || {}));
document.querySelector("#run-programmer-agent")?.addEventListener("click", runProgrammerAgent);
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
  if (snapshot?.strategy_package?.objective_metric) {
    document.querySelector("#objective-metric-input").value = snapshot.strategy_package.objective_metric;
  }
  if (snapshot?.strategy_package?.objective_targets) {
    document.querySelector("#target-return-input").value = String(snapshot.strategy_package.objective_targets.target_return_pct ?? 18);
    document.querySelector("#target-winrate-input").value = String(snapshot.strategy_package.objective_targets.target_win_rate_pct ?? 58);
    document.querySelector("#target-drawdown-input").value = String(snapshot.strategy_package.objective_targets.target_drawdown_pct ?? 12);
    document.querySelector("#target-maxloss-input").value = String(snapshot.strategy_package.objective_targets.target_max_loss_pct ?? 6);
  }
  if (snapshot?.trade_universe?.requested_symbols) {
    document.querySelector("#universe-symbols-input").value = snapshot.trade_universe.requested_symbols.join(",");
  } else if (snapshot?.trade_universe?.requested) {
    document.querySelector("#universe-symbols-input").value = snapshot.trade_universe.requested.join(",");
  }
  appendStrategyLog("info", "策略训练页已加载。");
})();
