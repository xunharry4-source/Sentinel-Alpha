const STRATEGY_LOG_PREFIX = "sentinel-alpha:strategy-log:";
const STRATEGY_FOCUS_KEY = "sentinel-alpha:strategy-focus-target";

function focusPanel(selector) {
  const panel = document.querySelector(selector);
  if (!panel) return;
  panel.classList.remove("panel-focus");
  // Force reflow so repeated focus still replays the effect.
  void panel.offsetWidth;
  panel.classList.add("panel-focus");
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
  window.setTimeout(() => panel.classList.remove("panel-focus"), 1800);
}

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

function getStrategyResearchCompareEntries(snapshot) {
  const entries = [];
  const currentPkg = snapshot?.strategy_package || {};
  const currentResearch = currentPkg.research_summary || {};
  if (currentPkg.version_label && Object.keys(currentResearch).length) {
    entries.push({
      id: "current",
      title: "当前实验版本",
      createdAt: snapshot?.updated_at || snapshot?.last_updated || "current",
      version: currentPkg.version_label,
      pkg: currentPkg,
      research: currentResearch,
      isCurrent: true,
    });
  }
  const archived = (snapshot?.report_history || [])
    .filter((item) => item.report_type === "strategy_iteration")
    .map((item) => {
      const pkg = item.body?.strategy_package || {};
      const exportManifest = item.body?.research_export || {};
      const research = exportManifest.research_summary || pkg.research_summary || item.body?.training_log_entry?.research_summary || {};
      return {
        id: item.report_id,
        title: item.title,
        createdAt: item.created_at,
        version: pkg.version_label || "unknown",
        pkg,
        research,
        exportManifest,
        isCurrent: false,
      };
    })
    .filter((item) => item.version !== "unknown");
  for (const item of archived) {
    if (!entries.some((entry) => entry.version === item.version && entry.isCurrent === item.isCurrent)) {
      entries.push(item);
    }
  }
  return entries;
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

function populateResearchArchiveSelectors(snapshot) {
  const entries = getStrategyResearchCompareEntries(snapshot);
  const selectors = [
    document.querySelector("#strategy-research-compare-a"),
    document.querySelector("#strategy-research-compare-b"),
    document.querySelector("#strategy-research-detail-version"),
  ];
  for (const select of selectors) {
    if (!select) continue;
    const currentValue = select.value;
    select.innerHTML = entries.length
      ? entries.map((item) => `<option value="${item.isCurrent ? `current:${item.version}` : item.version}">${item.isCurrent ? `[当前] ` : ""}${item.version}</option>`).join("")
      : `<option value="">暂无版本</option>`;
    if ([...select.options].some((option) => option.value === currentValue)) {
      select.value = currentValue;
    }
  }
  if (entries.length >= 2) {
    if (!document.querySelector("#strategy-research-compare-a")?.value) {
      document.querySelector("#strategy-research-compare-a").value = entries[0].isCurrent ? `current:${entries[0].version}` : entries[0].version;
    }
    if (!document.querySelector("#strategy-research-compare-b")?.value) {
      document.querySelector("#strategy-research-compare-b").value = entries[1].isCurrent ? `current:${entries[1].version}` : entries[1].version;
    }
  } else if (entries.length === 1) {
    const onlyValue = entries[0].isCurrent ? `current:${entries[0].version}` : entries[0].version;
    if (!document.querySelector("#strategy-research-compare-a")?.value) {
      document.querySelector("#strategy-research-compare-a").value = onlyValue;
    }
    if (!document.querySelector("#strategy-research-compare-b")?.value) {
      document.querySelector("#strategy-research-compare-b").value = onlyValue;
    }
  }
  if (entries.length && !document.querySelector("#strategy-research-detail-version")?.value) {
    document.querySelector("#strategy-research-detail-version").value = entries[0].isCurrent ? `current:${entries[0].version}` : entries[0].version;
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

function renderReleaseSnapshot(snapshot) {
  const pkg = snapshot?.strategy_package || {};
  const research = pkg.research_summary || {};
  const checkTarget = research.check_target_summary || {};
  const gate = research.final_release_gate_summary || {};
  const quality = pkg.input_manifest?.data_quality || {};
  const bundle = pkg.data_bundle_id || pkg.input_manifest?.data_bundle_id || "unknown";
  const evaluationSource = checkTarget.evaluation_source || "unknown";
  const gateStatus = gate.gate_status || "unknown";
  const qualityGrade = quality.quality_grade || "unknown";
  const trainingReadiness = quality.training_readiness?.status || "unknown";
  const winner = research.winner_selection_summary?.winner_variant_id || "unknown";
  const grid = document.querySelector("#strategy-release-grid");
  if (grid) {
    if (!pkg.version_label) {
      grid.innerHTML = `<article class="check-card"><strong>还没有研究发布摘要。</strong></article>`;
    } else {
      const gateClass = gateStatus === "passed" ? "check-pass" : gateStatus === "blocked" ? "check-fail" : "check-warning";
      const gateChip = gateStatus === "passed" ? "success-chip" : gateStatus === "blocked" ? "danger-chip" : "warn-chip";
      const qualityClass = qualityGrade === "healthy" ? "check-pass" : qualityGrade === "degraded" ? "check-fail" : "check-warning";
      const qualityChip = qualityGrade === "healthy" ? "success-chip" : qualityGrade === "degraded" ? "danger-chip" : "warn-chip";
      grid.innerHTML = `
        <article class="check-card ${gateClass}">
          <div class="check-head">
            <strong>Gate</strong>
            <span class="status-chip ${gateChip}">${gateStatus}</span>
          </div>
          <p class="check-summary">winner=${winner} / eval_source=${evaluationSource}</p>
        </article>
        <article class="check-card ${qualityClass}">
          <div class="check-head">
            <strong>Input Quality</strong>
            <span class="status-chip ${qualityChip}">${qualityGrade}</span>
          </div>
          <p class="check-summary">training=${trainingReadiness} / bundle=${bundle}</p>
        </article>
      `;
    }
  }
  renderList(
    "strategy-release-list",
    pkg.version_label
      ? [
          `version / ${pkg.version_label}`,
          `winner / ${winner}`,
          `gate / ${gateStatus}`,
          `evaluation_source / ${evaluationSource}`,
          `bundle / ${bundle}`,
          `quality / ${qualityGrade} / training=${trainingReadiness}`,
          `gate_reason / ${gate.reason || "无"}`,
        ]
      : [],
    "还没有研究发布摘要。"
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

function renderResearchSummary(snapshot) {
  const summary = snapshot?.strategy_package?.research_summary;
  if (!summary) {
    renderList("strategy-research-summary-list", [], "还没有研究摘要。");
    return;
  }
  const winner = summary.winner_selection_summary || {};
  const checkTarget = summary.check_target_summary || {};
  const robustness = summary.robustness_summary || {};
  const rejections = summary.rejection_summary || [];
  const releaseGate = summary.final_release_gate_summary || {};
  const checkFailures = summary.check_failure_summary || [];
  const nextFocus = summary.next_iteration_focus || [];
  const rankings = summary.candidate_rankings || [];
  const evaluationSnapshot = summary.evaluation_snapshot || {};
  const evaluationHighlights = summary.evaluation_highlights || [];
  const backtestBinding = summary.backtest_binding_summary || {};
  renderList(
    "strategy-research-summary-list",
    [
      `研究摘要: ${summary.research_summary || "无"}`,
      `选择规则: ${summary.selection_rule || "无"}`,
      `目标函数: ${summary.objective_metric || "unknown"} / 协议=${summary.dataset_protocol || "unknown"} / 候选数=${summary.candidate_count ?? 0}`,
      `最优版本: ${winner.winner_variant_id || "unknown"} / version=${winner.winner_version || "unknown"} / test=${winner.winner_test_objective_score ?? "unknown"} / validation=${winner.winner_validation_objective_score ?? "unknown"} / stability=${winner.winner_stability_score ?? "unknown"}`,
      `胜出原因: ${winner.reason || "无"} / 相对基准 test 差值=${winner.winner_advantage_vs_baseline ?? "unknown"}`,
      `送检目标: ${checkTarget.variant_id || "unknown"} / source=${checkTarget.source || "unknown"} / eval_source=${checkTarget.evaluation_source || "unknown"} / test=${checkTarget.test_objective_score ?? "unknown"} / stability=${checkTarget.stability_score ?? "unknown"}`,
      `送检理由: ${checkTarget.reason || "无"}`,
      `稳健性结论: grade=${robustness.grade || "unknown"} / stability=${robustness.stability_score ?? "unknown"} / gap=${robustness.train_test_gap ?? "unknown"} / ${robustness.note || "无"}`,
      `回测绑定: grade=${backtestBinding.grade || "unknown"} / source=${backtestBinding.evaluation_source || evaluationSnapshot.evaluation_source || "unknown"} / coverage=${backtestBinding.coverage_grade || evaluationSnapshot.coverage_summary?.coverage_grade || "unknown"} / ${backtestBinding.note || "无"}`,
      `评估快照: source=${evaluationSnapshot.evaluation_source || "unknown"} / wf_windows=${evaluationSnapshot.walk_forward_windows ?? 0} / wf_score=${evaluationSnapshot.walk_forward_score ?? "unknown"} / gap=${evaluationSnapshot.train_test_gap ?? "unknown"}`,
      `Train/Validation/Test: ${evaluationSnapshot.train?.objective_score ?? "unknown"} / ${evaluationSnapshot.validation?.objective_score ?? "unknown"} / ${evaluationSnapshot.test?.objective_score ?? "unknown"}`,
      `测试细节: gross=${evaluationSnapshot.test?.gross_exposure_pct ?? "unknown"} / net=${evaluationSnapshot.test?.net_exposure_pct ?? "unknown"} / turnover=${evaluationSnapshot.test?.avg_daily_turnover_proxy_pct ?? "unknown"} / obs=${evaluationSnapshot.test?.observation_count ?? "unknown"}`,
      `发布门: status=${releaseGate.gate_status || "unknown"} / release_ready=${releaseGate.release_ready === true ? "yes" : releaseGate.release_ready === false ? "no" : "unknown"} / failed=${releaseGate.failed_check_count ?? 0} / passed=${releaseGate.passed_check_count ?? 0}`,
      `门控结论: ${releaseGate.reason || "无"}`,
      ...evaluationHighlights.map((item) => `评估结论: ${item}`),
      ...rankings.map((item) => `排名 ${item.rank}: ${item.name} / version=${item.version || "unknown"} / test=${item.test_objective_score ?? "unknown"} / validation=${item.validation_objective_score ?? "unknown"} / stability=${item.stability_score ?? "unknown"}${item.focus ? ` / focus=${item.focus}` : ""}`),
      ...rejections.map((item) => `淘汰 ${item.name}: ${item.reason} / test=${item.test_objective_score ?? "unknown"} / validation=${item.validation_objective_score ?? "unknown"} / stability=${item.stability_score ?? "unknown"} / gap=${item.train_test_gap ?? "unknown"}`),
      ...checkFailures.map((item) => `检查失败 ${item.check_type}: ${item.summary || "无"} / score=${item.score ?? "unknown"} / 修复=${(item.required_fix_actions || []).join("；") || "无"}`),
      ...(nextFocus.length ? [`下一轮重点: ${nextFocus.join("；")}`] : []),
    ],
    "还没有研究摘要。"
  );
}

function renderResearchTrendSummary(snapshot) {
  const logs = (snapshot?.strategy_training_log || []).slice().reverse().slice(0, 5);
  if (!logs.length) {
    renderList("strategy-research-trend-list", [], "还没有研究趋势摘要。");
    return;
  }
  const latest = logs[0] || {};
  const previous = logs[1] || null;
  const latestResearch = latest.research_summary || {};
  const previousResearch = previous?.research_summary || {};
  const latestEval = latestResearch.evaluation_snapshot || {};
  const previousEval = previousResearch.evaluation_snapshot || {};
  const latestGate = latestResearch.final_release_gate_summary?.gate_status || "unknown";
  const previousGate = previousResearch.final_release_gate_summary?.gate_status || "unknown";
  const latestTest = Number(latestEval.test?.objective_score ?? NaN);
  const previousTest = Number(previousEval.test?.objective_score ?? NaN);
  const latestWalk = Number(latestEval.walk_forward_score ?? NaN);
  const previousWalk = Number(previousEval.walk_forward_score ?? NaN);
  const latestGap = Number(latestEval.train_test_gap ?? NaN);
  const previousGap = Number(previousEval.train_test_gap ?? NaN);
  const trendText = (latestValue, previousValue, lowerIsBetter = false) => {
    if (!Number.isFinite(latestValue) || !Number.isFinite(previousValue)) return "unknown";
    if (latestValue === previousValue) return "flat";
    const improved = lowerIsBetter ? latestValue < previousValue : latestValue > previousValue;
    return improved ? "improving" : "degrading";
  };
  renderList(
    "strategy-research-trend-list",
    [
      `最近轮次 / ${logs.map((item) => `v${item.iteration_no || "-"}`).join(" -> ")}`,
      `gate 趋势 / ${previous ? `${previousGate} -> ${latestGate}` : latestGate}`,
      `test 趋势 / ${trendText(latestTest, previousTest)} / ${Number.isFinite(previousTest) ? previousTest : "unknown"} -> ${Number.isFinite(latestTest) ? latestTest : "unknown"}`,
      `walk_forward 趋势 / ${trendText(latestWalk, previousWalk)} / ${Number.isFinite(previousWalk) ? previousWalk : "unknown"} -> ${Number.isFinite(latestWalk) ? latestWalk : "unknown"}`,
      `gap 趋势 / ${trendText(latestGap, previousGap, true)} / ${Number.isFinite(previousGap) ? previousGap : "unknown"} -> ${Number.isFinite(latestGap) ? latestGap : "unknown"}`,
      `当前 focus / ${(latestResearch.next_iteration_focus || []).join("；") || "无"}`,
    ],
    "还没有研究趋势摘要。"
  );
}

function renderRepairTrendSummary(snapshot) {
  const logs = (snapshot?.strategy_training_log || []).slice().reverse().slice(0, 5);
  if (!logs.length) {
    renderList("strategy-repair-trend-list", [], "还没有修复趋势摘要。");
    return;
  }
  const routeLabel = (route) => route?.lane || "无";
  const routePriority = (route) => route?.priority || "unknown";
  const routeSource = (route) => route?.source || "unknown";
  const latest = logs[0] || {};
  const previous = logs[1] || null;
  const latestRoute = (latest.repair_route_summary || [])[0] || null;
  const previousRoute = (previous?.repair_route_summary || [])[0] || null;
  const counts = {};
  for (const item of logs) {
    const route = (item.repair_route_summary || [])[0];
    const key = route?.lane || "无";
    counts[key] = (counts[key] || 0) + 1;
  }
  const routeSet = new Set(logs.map((item) => routeLabel((item.repair_route_summary || [])[0])));
  const prioritySet = new Set(logs.map((item) => routePriority((item.repair_route_summary || [])[0])));
  const sourceSet = new Set(logs.map((item) => routeSource((item.repair_route_summary || [])[0])));
  let convergence = "flat";
  let convergenceNote = "最近修复路线变化有限，整体处于持平状态。";
  if (logs.length >= 3) {
    if (routeSet.size === 1 && prioritySet.size <= 2 && sourceSet.size <= 2) {
      convergence = "converging";
      convergenceNote = "最近几轮主修复路线基本稳定，说明修复目标正在收敛。";
    } else if (routeSet.size >= 3 || sourceSet.size >= 3) {
      convergence = "diverging";
      convergenceNote = "最近几轮主修复路线变化较大，说明问题还在发散或尚未收敛。";
    }
  }
  renderList(
    "strategy-repair-trend-list",
    [
      `最近轮次 / ${logs.map((item) => `v${item.iteration_no || "-"}`).join(" -> ")}`,
      `主修复路线 / ${previous ? `${routeLabel(previousRoute)} -> ${routeLabel(latestRoute)}` : routeLabel(latestRoute)}`,
      `优先级变化 / ${previous ? `${routePriority(previousRoute)} -> ${routePriority(latestRoute)}` : routePriority(latestRoute)}`,
      `来源变化 / ${previous ? `${routeSource(previousRoute)} -> ${routeSource(latestRoute)}` : routeSource(latestRoute)}`,
      `收敛结论 / ${convergence} / ${convergenceNote}`,
      `最近主路线分布 / ${Object.entries(counts).map(([name, count]) => `${name}=${count}`).join(" / ") || "无"}`,
      `当前动作 / ${((latestRoute?.actions || []).slice(0, 3)).join("；") || "无"}`,
    ],
    "还没有修复趋势摘要。"
  );
}

function renderResearchHealthSummary(snapshot) {
  const logs = snapshot?.strategy_training_log || [];
  if (!logs.length) {
    renderList("strategy-research-health-list", [], "还没有研究健康结论。");
    return;
  }
  const latest = logs[logs.length - 1] || {};
  const previous = logs.length > 1 ? logs[logs.length - 2] : null;
  const research = latest.research_summary || {};
  const prevResearch = previous?.research_summary || {};
  const gate = research.final_release_gate_summary?.gate_status || "unknown";
  const robustness = research.robustness_summary?.grade || "unknown";
  const evalSnap = research.evaluation_snapshot || {};
  const prevEval = prevResearch.evaluation_snapshot || {};
  const test = Number(evalSnap.test?.objective_score ?? NaN);
  const prevTest = Number(prevEval.test?.objective_score ?? NaN);
  const walk = Number(evalSnap.walk_forward_score ?? NaN);
  const prevWalk = Number(prevEval.walk_forward_score ?? NaN);
  const gap = Number(evalSnap.train_test_gap ?? NaN);
  const prevGap = Number(prevEval.train_test_gap ?? NaN);
  let status = "warning";
  let note = "研究仍需持续观察。";
  if (gate === "passed" && robustness === "strong") {
    status = "healthy";
    note = "当前研究结果稳定，发布门已通过。";
  } else if (gate === "blocked" || robustness === "fragile") {
    status = "fragile";
    note = "当前研究结果脆弱，仍被检查门阻塞或稳健性不足。";
  }
  const trendNotes = [];
  if (Number.isFinite(test) && Number.isFinite(prevTest)) {
    trendNotes.push(`test ${test > prevTest ? "improving" : test < prevTest ? "degrading" : "flat"} (${prevTest} -> ${test})`);
  }
  if (Number.isFinite(walk) && Number.isFinite(prevWalk)) {
    trendNotes.push(`walk_forward ${walk > prevWalk ? "improving" : walk < prevWalk ? "degrading" : "flat"} (${prevWalk} -> ${walk})`);
  }
  if (Number.isFinite(gap) && Number.isFinite(prevGap)) {
    trendNotes.push(`gap ${gap < prevGap ? "improving" : gap > prevGap ? "degrading" : "flat"} (${prevGap} -> ${gap})`);
  }
  renderList(
    "strategy-research-health-list",
    [
      `status / ${status}`,
      `gate / ${gate}`,
      `robustness / ${robustness}`,
      `note / ${note}`,
      ...(trendNotes.length ? trendNotes.map((item) => `trend / ${item}`) : ["trend / 当前还没有足够历史用于趋势判断。"]),
      `focus / ${(research.next_iteration_focus || []).join("；") || "无"}`,
    ],
    "还没有研究健康结论。"
  );
}

function renderCheckFailureTrend(snapshot) {
  const logs = snapshot?.strategy_training_log || [];
  const counts = {};
  const gateCounts = { passed: 0, blocked: 0 };
  for (const item of logs) {
    const failedChecks = item.failed_checks || [];
    for (const checkType of failedChecks) {
      counts[checkType] = (counts[checkType] || 0) + 1;
    }
    const gateStatus = item.research_summary?.final_release_gate_summary?.gate_status;
    if (gateStatus && gateStatus in gateCounts) {
      gateCounts[gateStatus] += 1;
    }
  }
  const grid = document.querySelector("#strategy-check-trend-grid");
  const entries = Object.entries(counts).sort((a, b) => Number(b[1]) - Number(a[1]));
  if (grid) {
    if (!entries.length && !logs.length) {
      grid.innerHTML = `<article class="check-card"><strong>还没有检查趋势。</strong></article>`;
    } else {
      const checkCards = entries.map(([name, count]) => `
        <article class="check-card check-warning">
          <div class="check-head">
            <strong>${name}</strong>
            <span class="status-chip warn-chip">${count}</span>
          </div>
          <p class="check-summary">最近迭代中，${name} 失败共出现 ${count} 次。</p>
        </article>
      `).join("");
      const gateCards = `
        <article class="check-card ${gateCounts.blocked > 0 ? "check-warning" : "check-pass"}">
          <div class="check-head">
            <strong>release_gate</strong>
            <span class="status-chip ${gateCounts.blocked > 0 ? "warn-chip" : "success-chip"}">${gateCounts.blocked > 0 ? "blocked" : "passed"}</span>
          </div>
          <p class="check-summary">passed=${gateCounts.passed} / blocked=${gateCounts.blocked}</p>
        </article>
      `;
      grid.innerHTML = gateCards + (checkCards || "");
    }
  }
  const recent = logs
    .slice()
    .reverse()
    .slice(0, 8)
    .map((item) => {
      const gateStatus = item.research_summary?.final_release_gate_summary?.gate_status || "unknown";
      const failedChecks = (item.failed_checks || []).join(", ") || "无";
      const nextFocus = (item.research_summary?.next_iteration_focus || []).join("；") || "无";
      return `${item.timestamp} / 第${item.iteration_no || "-"}版 / status=${item.status || "unknown"} / gate=${gateStatus} / failed=${failedChecks} / next=${nextFocus}`;
    });
  const summary = [
    `release_gate / passed=${gateCounts.passed} / blocked=${gateCounts.blocked}`,
    ...entries.map(([name, count]) => `${name}: ${count}`),
    ...recent,
  ];
  renderList("strategy-check-trend-list", summary, "还没有检查趋势。");
}

function renderResearchCodeLoop(snapshot) {
  const logs = snapshot?.strategy_training_log || [];
  const runs = snapshot?.programmer_runs || [];
  const recentStrategy = logs.slice().reverse().slice(0, 6);
  const recentProgrammer = runs.slice().reverse().slice(0, 6);
  const strategyCounts = {};
  const programmerCounts = {};
  for (const item of recentStrategy) {
    for (const checkType of item.failed_checks || []) {
      strategyCounts[checkType] = (strategyCounts[checkType] || 0) + 1;
    }
  }
  for (const run of recentProgrammer) {
    const kind = run.failure_type || (run.status === "ok" ? "success" : run.status || "unknown");
    programmerCounts[kind] = (programmerCounts[kind] || 0) + 1;
  }
  const observations = [];
  if ((strategyCounts.integrity || 0) > 0 && (programmerCounts.compile_failure || 0) > 0) {
    observations.push("完整性失败与 compile_failure 同时偏高，先检查策略代码结构、命名和实现约束。");
  }
  if ((strategyCounts.stress_overfit || 0) > 0 && (programmerCounts.test_failure || 0) > 0) {
    observations.push("过拟合/压力失败与 test_failure 同时偏高，优先修正策略行为和评估预期不一致的问题。");
  }
  if (!observations.length && recentStrategy.length && recentProgrammer.length) {
    observations.push("最近几轮研究失败与代码失败没有明显单一对应，说明问题更可能来自候选逻辑而非单次实现错误。");
  }
  const grid = document.querySelector("#strategy-code-loop-grid");
  if (grid) {
    const cards = [];
    cards.push(`
      <article class="check-card">
        <div class="check-head">
          <strong>Strategy Side</strong>
          <span class="status-chip outline-chip">${recentStrategy.length}</span>
        </div>
        <p class="check-summary">最近 ${recentStrategy.length} 轮策略训练失败分布。</p>
        <p>${Object.entries(strategyCounts).map(([name, count]) => `${name}=${count}`).join(" / ") || "无明显失败"}</p>
      </article>
    `);
    cards.push(`
      <article class="check-card">
        <div class="check-head">
          <strong>Programmer Side</strong>
          <span class="status-chip outline-chip">${recentProgrammer.length}</span>
        </div>
        <p class="check-summary">最近 ${recentProgrammer.length} 次代码修改失败分布。</p>
        <p>${Object.entries(programmerCounts).map(([name, count]) => `${name}=${count}`).join(" / ") || "无明显失败"}</p>
      </article>
    `);
    cards.push(`
      <article class="check-card ${observations.length ? "check-warning" : ""}">
        <div class="check-head">
          <strong>Correlation</strong>
          <span class="status-chip ${observations.length ? "warn-chip" : "success-chip"}">${observations.length ? "attention" : "clear"}</span>
        </div>
        <p class="check-summary">${observations[0] || "当前没有观察到明显联动问题。"}</p>
      </article>
    `);
    grid.innerHTML = cards.join("");
  }
  renderList(
    "strategy-code-loop-list",
    [
      `策略侧: ${Object.entries(strategyCounts).map(([name, count]) => `${name}=${count}`).join(" / ") || "无明显失败"}`,
      `编程侧: ${Object.entries(programmerCounts).map(([name, count]) => `${name}=${count}`).join(" / ") || "无明显失败"}`,
      ...observations,
      ...recentStrategy.map((item) => `策略轮次 ${item.iteration_no || "-"} / failed=${(item.failed_checks || []).join(", ") || "none"} / next=${(item.research_summary?.next_iteration_focus || []).join("；") || "无"}`),
      ...recentProgrammer.map((run) => `编程运行 ${run.timestamp || "unknown"} / ${(run.failure_type || run.status || "unknown")} / ${run.validation_detail || run.error || "no detail"}`),
    ],
    "还没有联动趋势。"
  );
}

function routePriorityRank(priority) {
  if (priority === "P0") return 0;
  if (priority === "P1") return 1;
  return 2;
}

function stricterPriority(left, right) {
  return routePriorityRank(left) <= routePriorityRank(right) ? left : right;
}

function dedupeRouteActions(actions) {
  return [...new Set((actions || []).filter(Boolean))];
}

function buildRepairRoutes(snapshot) {
  const logs = snapshot?.strategy_training_log || [];
  const runs = snapshot?.programmer_runs || [];
  const latestLog = logs[logs.length - 1] || {};
  const latestRun = runs[runs.length - 1] || {};
  const failedChecks = latestLog.failed_checks || [];
  const nextFocus = latestLog.research_summary?.next_iteration_focus || [];
  const programmerFailure = latestRun.failure_type || (latestRun.status === "ok" ? "success" : latestRun.status || "unknown");
  const programmerPlan = latestRun.repair_plan || {};
  const programmerSummary = latestRun.failure_summary || {};
  const routes = [];

  if (failedChecks.includes("integrity")) {
    if (programmerFailure === "compile_failure") {
      routes.push({
        lane: "结构修复",
        priority: "P0",
        summary: "先修编译和代码结构，再处理 integrity 规则。",
        actions: ["修正导入、语法、命名和返回结构", "确保策略输出字段完整", "重新跑 compile + pytest 后再送 integrity 检查"],
        source: "research",
      });
    } else if (programmerFailure === "validation_failure" || programmerFailure === "execution_failure") {
      routes.push({
        lane: "契约修复",
        priority: "P0",
        summary: "当前更像契约或运行时不匹配，先对齐接口和 candidate 结构。",
        actions: ["检查 StrategyCandidate 字段", "检查版本命名和输出契约", "检查 check_target/candidate 对应关系"],
        source: "research",
      });
    } else {
      routes.push({
        lane: "完整性修复",
        priority: "P1",
        summary: "优先按 integrity 失败项修正未来函数、作弊痕迹、硬编码和可疑 rationale。",
        actions: ["检查 future/leakage 线索", "减少可疑高置信度硬编码", "根据 required_fix_actions 逐项修正"],
        source: "research",
      });
    }
  }

  if (failedChecks.includes("stress_overfit")) {
    if (programmerFailure === "test_failure") {
      routes.push({
        lane: "行为修复",
        priority: "P0",
        summary: "策略行为和测试预期同时有问题，先修可测试行为，再降复杂度。",
        actions: ["降低参数密度", "减少过窄 universe 依赖", "优先修复测试暴露出的行为偏差"],
        source: "research",
      });
    } else {
      routes.push({
        lane: "稳健性修复",
        priority: "P1",
        summary: "优先处理过拟合和稳健性问题，降低 train-test gap，提升 walk-forward 稳定性。",
        actions: ["简化规则和参数", "减少对单一 regime 的依赖", "优先看 validation/test/walk-forward 弱点"],
        source: "research",
      });
    }
  }

  if (!failedChecks.length && latestLog.research_summary?.final_release_gate_summary?.gate_status === "passed") {
      routes.push({
        lane: "通过态",
        priority: "P2",
        summary: "当前最优版本已通过门控，不需要强制修复，可进入下一轮研究增强。",
        actions: ["保留当前版本作为稳定基线", "如继续迭代，优先探索增益而非修复"],
        source: "research",
      });
  }

  if (!routes.length && nextFocus.length) {
    routes.push({
      lane: "默认修复",
      priority: "P1",
      summary: "优先按研究摘要给出的 next_iteration_focus 执行。",
      actions: nextFocus,
      source: "research",
    });
  }

  if (!routes.length) {
    routes.push({
      lane: "观察",
      priority: "P2",
      summary: "当前没有足够的失败信号，先继续积累更多训练和修复记录。",
      actions: ["继续训练或执行一次 Programmer Agent", "观察 release gate 和失败类型是否收敛"],
      source: "research",
    });
  }

  if ((programmerPlan.actions || []).length) {
    const dominantFailure = programmerSummary.dominant_failure_type || programmerFailure || "unknown";
    const programmerRoute = {
      lane: "代码修复计划",
      priority: programmerPlan.priority || "P1",
      summary: `Programmer Agent 判断当前主导失败为 ${dominantFailure}，建议先执行代码侧修复计划。`,
      actions: dedupeRouteActions(programmerPlan.actions),
      source: "programmer",
    };
    if (routes.length) {
      const primary = routes[0];
      primary.priority = stricterPriority(primary.priority, programmerRoute.priority);
      primary.summary = `${primary.summary} 代码侧主导失败=${dominantFailure}。`;
      primary.actions = dedupeRouteActions([...programmerRoute.actions, ...(primary.actions || [])]);
      primary.source = primary.source === "research" ? "research+programmer" : primary.source || "research+programmer";
      if (
        dominantFailure !== "success" &&
        dominantFailure !== "unknown" &&
        !routes.some((item) => item.lane === programmerRoute.lane)
      ) {
        routes.push(programmerRoute);
      }
    } else {
      routes.push(programmerRoute);
    }
  }
  return routes;
}

function renderRepairRouting(snapshot) {
  const routes = buildRepairRoutes(snapshot);
  const grid = document.querySelector("#strategy-repair-route-grid");
  if (grid) {
    grid.innerHTML = routes.map((route) => `
      <article class="check-card ${route.priority === "P0" ? "check-fail" : route.priority === "P1" ? "check-warning" : "check-pass"}">
        <div class="check-head">
          <strong>${route.lane}</strong>
          <span class="status-chip ${route.priority === "P0" ? "danger-chip" : route.priority === "P1" ? "warn-chip" : "success-chip"}">${route.priority}</span>
        </div>
        <p class="check-summary">${route.summary}</p>
        <p class="check-label">来源</p>
        <p>${route.source || "research"}</p>
        <p class="check-label">建议动作</p>
        <p>${route.actions.join("；")}</p>
      </article>
    `).join("");
  }

  renderList(
    "strategy-repair-route-list",
    routes.flatMap((route) => [
      `${route.lane} / ${route.priority} / ${route.source || "research"} / ${route.summary}`,
      ...route.actions.map((action) => `动作: ${action}`),
    ]),
    "还没有修复路由建议。"
  );
}

function applyRepairRoutingToFeedback() {
  const snapshot = loadStoredSnapshot() || {};
  const routes = buildRepairRoutes(snapshot);
  const target = document.querySelector("#strategy-feedback-input");
  if (!target || !routes.length) {
    setText("strategy-note", "当前没有可回填的修复反馈。");
    return;
  }
  const text = routes
    .slice(0, 2)
    .map((route) => `${route.lane}: ${route.summary} 动作: ${route.actions.join("；")}`)
    .join(" | ");
  target.value = text;
  setText("strategy-note", "已将修复路由回填到训练反馈。");
  appendStrategyLog("info", "已将修复路由回填到训练反馈输入框。");
}

function applyRepairRoutingToProgrammer() {
  const snapshot = loadStoredSnapshot() || {};
  const routes = buildRepairRoutes(snapshot);
  const instruction = document.querySelector("#programmer-instruction");
  const context = document.querySelector("#programmer-context");
  if (!instruction || !routes.length) {
    setText("strategy-note", "当前没有可回填的修复指令。");
    return;
  }
  const primary = routes[0];
  instruction.value = `按${primary.lane}优先修复当前策略相关代码，重点：${primary.actions.join("；")}。保持现有风控结构、版本规则和输出契约不变。`;
  if (context) {
    context.value = `${primary.summary} 最近优先级=${primary.priority} / 来源=${primary.source || "research"}。如涉及检查失败，先修复对应 required_fix_actions，再重新运行 compile 与 pytest。`;
  }
  setText("strategy-note", "已将修复路由回填到 Programmer Agent。");
  appendStrategyLog("info", "已将修复路由回填到 Programmer Agent 输入框。");
}

async function applyRepairAndIterate() {
  applyRepairRoutingToFeedback();
  await iterateStrategy();
}

async function applyRepairAndRunProgrammer() {
  applyRepairRoutingToProgrammer();
  await runProgrammerAgent();
}

function renderFeatureSnapshot(snapshot) {
  const features = snapshot?.strategy_package?.feature_snapshot || {};
  const lines = [];
  if (features.meta) {
    lines.push(`meta / version=${features.meta.snapshot_version || "unknown"} / hash=${features.meta.snapshot_hash || "unknown"} / bundle=${features.meta.data_bundle_id || "unknown"}`);
  }
  if (features.data_quality) {
    lines.push(`data_quality / coverage=${features.data_quality.section_coverage_score ?? "unknown"} / providers=${features.data_quality.provider_count ?? 0} / grade=${features.data_quality.quality_grade || "unknown"}`);
    lines.push(`data_quality / available=${(features.data_quality.available_sections || []).join(", ") || "none"} / missing=${(features.data_quality.missing_sections || []).join(", ") || "none"}`);
    lines.push(`data_quality / freshness_gap_hours=${features.data_quality.freshness?.max_gap_hours ?? "unknown"} / ts_count=${features.data_quality.freshness?.known_timestamp_count ?? 0}`);
    if ((features.data_quality.alignment_warnings || []).length) {
      lines.push(`data_quality / warnings=${features.data_quality.alignment_warnings.join(", ")}`);
    }
    if (features.data_quality.training_readiness) {
      lines.push(`data_quality / training=${features.data_quality.training_readiness.status || "unknown"} / ${features.data_quality.training_readiness.note || ""}`);
    }
  }
  if (features.source_lineage) {
    const lineage = features.source_lineage;
    lines.push(`lineage / market=${lineage.market?.source || "none"} / intel=${lineage.intelligence?.run_id || "none"} / financials=${lineage.fundamentals?.run_id || "none"}`);
    lines.push(`lineage / dark_pool=${lineage.dark_pool?.run_id || "none"} / options=${lineage.options?.run_id || "none"}`);
  }
  if (features.behavioral) {
    lines.push(`behavioral / noise=${features.behavioral.noise_sensitivity ?? "unknown"} / panic=${features.behavioral.panic_sell_tendency ?? "unknown"} / overtrade=${features.behavioral.overtrading_tendency ?? "unknown"}`);
  }
  if (features.market) {
    lines.push(`market / symbol=${features.market.symbol || "unknown"} / timeframe=${features.market.timeframe || "unknown"} / regime=${features.market.regime_tag || "unknown"}`);
  }
  if (features.preferences) {
    lines.push(`preferences / freq=${features.preferences.trading_frequency || "unknown"} / timeframe=${features.preferences.preferred_timeframe || "unknown"} / conflict=${features.preferences.conflict_level || "none"}`);
  }
  if (features.intelligence?.factors) {
    lines.push(`intelligence / credibility=${features.intelligence.factors.credibility_score ?? "unknown"} / contradiction=${features.intelligence.factors.contradiction_score ?? "unknown"} / docs=${features.intelligence.document_count ?? 0}`);
  }
  if (features.fundamentals?.factors) {
    lines.push(`fundamentals / quality=${features.fundamentals.factors.quality_score ?? "unknown"} / deterioration=${features.fundamentals.factors.deterioration_score ?? "unknown"}`);
  }
  if (features.dark_pool?.factors) {
    lines.push(`dark_pool / accumulation=${features.dark_pool.factors.accumulation_score ?? "unknown"} / records=${features.dark_pool.factors.record_count ?? "unknown"}`);
  }
  if (features.options?.factors) {
    lines.push(`options / pressure=${features.options.factors.options_pressure_score ?? "unknown"} / oi=${features.options.factors.total_open_interest ?? "unknown"}`);
  }
  renderList("strategy-feature-list", lines, "还没有训练特征。");
}

function renderInputManifest(snapshot) {
  const manifest = snapshot?.strategy_package?.input_manifest || {};
  const lineage = manifest.source_lineage || {};
  const lines = [];
  if (manifest.data_bundle_id || manifest.feature_snapshot_version) {
    lines.push(`bundle / ${manifest.data_bundle_id || "unknown"} / snapshot=${manifest.feature_snapshot_version || "unknown"}`);
  }
  if (manifest.dataset_protocol || manifest.objective_metric) {
    lines.push(`dataset / protocol=${manifest.dataset_protocol || "unknown"} / objective=${manifest.objective_metric || "unknown"} / walk_forward=${manifest.walk_forward_windows ?? "unknown"}`);
  }
  if (manifest.selected_universe?.length) {
    lines.push(`universe / size=${manifest.selected_universe_size ?? manifest.selected_universe.length} / ${manifest.selected_universe.join(", ")}`);
  }
  if (manifest.available_sections?.length || manifest.provider_coverage?.length) {
    lines.push(`coverage / sections=${(manifest.available_sections || []).join(", ") || "none"} / providers=${(manifest.provider_coverage || []).join(", ") || "none"}`);
  }
  if (manifest.data_quality?.quality_grade) {
    lines.push(`quality / grade=${manifest.data_quality.quality_grade} / training=${manifest.data_quality.training_readiness?.status || "unknown"}`);
  }
  if (manifest.data_quality?.freshness) {
    lines.push(`freshness / gap_hours=${manifest.data_quality.freshness.max_gap_hours ?? "unknown"} / ts_count=${manifest.data_quality.freshness.known_timestamp_count ?? 0}`);
  }
  if ((manifest.data_quality?.alignment_warnings || []).length) {
    lines.push(`freshness / warnings=${manifest.data_quality.alignment_warnings.join(", ")}`);
  }
  if (lineage.market || lineage.intelligence || lineage.fundamentals || lineage.dark_pool || lineage.options) {
    lines.push(`lineage / market=${lineage.market?.source || "none"} / intel=${lineage.intelligence?.run_id || "none"} / financials=${lineage.fundamentals?.run_id || "none"}`);
    lines.push(`lineage / dark_pool=${lineage.dark_pool?.run_id || "none"} / options=${lineage.options?.run_id || "none"}`);
  }
  renderList("strategy-input-manifest-list", lines, "还没有训练输入说明。");
}

function renderDataBundles(snapshot) {
  const bundles = snapshot?.data_bundles || [];
  renderList(
    "strategy-data-bundles-list",
    bundles
      .slice()
      .reverse()
      .map((item) => `${item.created_at} / ${item.data_bundle_id} / protocol=${item.dataset_protocol || "unknown"} / universe=${item.selected_universe_size || 0} / uses=${item.usage_count || 0}`),
    "还没有输入数据包记录。"
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
        const snapshotVersion = item.feature_snapshot_version ? ` / snapshot=${item.feature_snapshot_version}` : "";
        const bundleId = item.data_bundle_id ? ` / bundle=${item.data_bundle_id}` : "";
        return `${item.timestamp} / 第${item.iteration_no || "-"}版 / ${item.strategy_type || "unknown"} / ${item.status || "unknown"}${target}${snapshotVersion}${bundleId}${failed}${error}`;
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

function runResearchArchiveCompare(snapshot) {
  const entries = getStrategyResearchCompareEntries(snapshot);
  const versionA = document.querySelector("#strategy-research-compare-a")?.value;
  const versionB = document.querySelector("#strategy-research-compare-b")?.value;
  const a = entries.find((item) => (item.isCurrent ? `current:${item.version}` : item.version) === versionA);
  const b = entries.find((item) => (item.isCurrent ? `current:${item.version}` : item.version) === versionB);
  if (!a || !b) {
    renderList("strategy-research-compare-list", [], "还没有研究归档对比结果。");
    const panel = document.querySelector("#strategy-research-export");
    if (panel) panel.textContent = "{}";
    return;
  }
  const aWinner = a.research?.winner_selection_summary || {};
  const bWinner = b.research?.winner_selection_summary || {};
  const aGate = a.research?.final_release_gate_summary || {};
  const bGate = b.research?.final_release_gate_summary || {};
  const aRobust = a.research?.robustness_summary || {};
  const bRobust = b.research?.robustness_summary || {};
  const aCheck = a.research?.check_target_summary || {};
  const bCheck = b.research?.check_target_summary || {};
  const aBundle = a.exportManifest?.data_bundle_id || a.pkg?.data_bundle_id || a.pkg?.input_manifest?.data_bundle_id || "unknown";
  const bBundle = b.exportManifest?.data_bundle_id || b.pkg?.data_bundle_id || b.pkg?.input_manifest?.data_bundle_id || "unknown";
  const aQuality = a.exportManifest?.quality_grade || a.pkg?.input_manifest?.data_quality?.quality_grade || "unknown";
  const bQuality = b.exportManifest?.quality_grade || b.pkg?.input_manifest?.data_quality?.quality_grade || "unknown";
  renderList(
    "strategy-research-compare-list",
    [
      `版本A / ${a.isCurrent ? "[当前] " : ""}${a.version} / winner=${aWinner.winner_variant_id || "unknown"} / gate=${aGate.gate_status || "unknown"} / robustness=${aRobust.grade || "unknown"} / bundle=${aBundle} / quality=${aQuality}`,
      `版本B / ${b.isCurrent ? "[当前] " : ""}${b.version} / winner=${bWinner.winner_variant_id || "unknown"} / gate=${bGate.gate_status || "unknown"} / robustness=${bRobust.grade || "unknown"} / bundle=${bBundle} / quality=${bQuality}`,
      `winner 变化 / ${aWinner.winner_variant_id || "unknown"} -> ${bWinner.winner_variant_id || "unknown"}`,
      `gate 变化 / ${aGate.gate_status || "unknown"} -> ${bGate.gate_status || "unknown"}`,
      `robustness 变化 / ${aRobust.grade || "unknown"} -> ${bRobust.grade || "unknown"}`,
      `check_target 变化 / ${aCheck.variant_id || "unknown"} -> ${bCheck.variant_id || "unknown"}`,
      `eval_source 变化 / ${aCheck.evaluation_source || "unknown"} -> ${bCheck.evaluation_source || "unknown"}`,
      `next_focus A / ${(a.research?.next_iteration_focus || []).join("；") || "无"}`,
      `next_focus B / ${(b.research?.next_iteration_focus || []).join("；") || "无"}`,
    ],
    "还没有研究归档对比结果。"
  );
  const panel = document.querySelector("#strategy-research-export");
  if (panel) {
    panel.textContent = JSON.stringify(
      {
        version_a: {
          version: a.version,
          current: a.isCurrent,
          created_at: a.createdAt,
          data_bundle_id: aBundle,
          quality_grade: aQuality,
          research_summary: a.research,
        },
        version_b: {
          version: b.version,
          current: b.isCurrent,
          created_at: b.createdAt,
          data_bundle_id: bBundle,
          quality_grade: bQuality,
          research_summary: b.research,
        },
      },
      null,
      2
    );
  }
}

function renderResearchArchiveDetail(snapshot) {
  const entries = getStrategyResearchCompareEntries(snapshot);
  const version = document.querySelector("#strategy-research-detail-version")?.value;
  const entry = entries.find((item) => (item.isCurrent ? `current:${item.version}` : item.version) === version);
  if (!entry) {
    renderList("strategy-research-detail-list", [], "还没有研究归档详情。");
    const panel = document.querySelector("#strategy-research-detail-export");
    if (panel) panel.textContent = "{}";
    return;
  }
  const exportManifest = entry.exportManifest || {};
  const research = entry.research || {};
  const winner = exportManifest.winner_variant_id || research.winner_selection_summary?.winner_variant_id || "unknown";
  const gate = exportManifest.gate_status || research.final_release_gate_summary?.gate_status || "unknown";
  const robustness = exportManifest.robustness_grade || research.robustness_summary?.grade || "unknown";
  const evaluation = research.evaluation_snapshot || {};
  const coverage = evaluation.coverage_summary || exportManifest.coverage_summary || {};
  const repairRoutes = exportManifest.repair_route_summary || research.repair_route_summary || [];
  const primaryRepairRoute = exportManifest.primary_repair_route || repairRoutes[0] || null;
  renderList(
    "strategy-research-detail-list",
    [
      `version / ${entry.isCurrent ? "[当前] " : ""}${entry.version}`,
      `created_at / ${entry.createdAt}`,
      `winner / ${winner}`,
      `gate / ${gate}`,
      `robustness / ${robustness}`,
      `bundle / ${exportManifest.data_bundle_id || entry.pkg?.data_bundle_id || "unknown"}`,
      `quality / ${exportManifest.quality_grade || entry.pkg?.input_manifest?.data_quality?.quality_grade || "unknown"} / training=${exportManifest.training_readiness || entry.pkg?.input_manifest?.data_quality?.training_readiness?.status || "unknown"}`,
      `check_target / ${exportManifest.check_target_variant_id || research.check_target_summary?.variant_id || "unknown"} / source=${exportManifest.evaluation_source || research.check_target_summary?.evaluation_source || "unknown"}`,
      `train/validation/test / ${evaluation.train?.objective_score ?? "unknown"} / ${evaluation.validation?.objective_score ?? "unknown"} / ${evaluation.test?.objective_score ?? "unknown"}`,
      `walk_forward / ${evaluation.walk_forward_score ?? "unknown"} / windows=${evaluation.walk_forward_windows ?? 0}`,
      `test_detail / gross=${evaluation.test?.gross_exposure_pct ?? "unknown"} / net=${evaluation.test?.net_exposure_pct ?? "unknown"} / turnover=${evaluation.test?.avg_daily_turnover_proxy_pct ?? "unknown"} / obs=${evaluation.test?.observation_count ?? "unknown"}`,
      `coverage / symbols=${coverage.symbol_count ?? "unknown"} / bars=${coverage.total_bar_count ?? "unknown"} / wf_windows=${coverage.walk_forward_window_count ?? 0}`,
      `coverage_health / ${coverage.coverage_grade || "unknown"} / ${coverage.coverage_health_note || "无"}`,
      `coverage_warnings / ${(coverage.coverage_warnings || []).join("，") || "无"}`,
      `coverage_range / ${coverage.date_range?.start || "unknown"} -> ${coverage.date_range?.end || "unknown"}`,
      `gap / ${evaluation.train_test_gap ?? "unknown"}`,
      `next_focus / ${(exportManifest.next_iteration_focus || research.next_iteration_focus || []).join("；") || "无"}`,
      `failed_checks / ${(exportManifest.failed_checks || []).join(", ") || "无"}`,
      `primary_repair_route / ${primaryRepairRoute ? `${primaryRepairRoute.lane} / ${primaryRepairRoute.priority} / ${primaryRepairRoute.source || "unknown"}` : "无"}`,
      ...(repairRoutes.length
        ? repairRoutes.flatMap((route) => [
            `repair_route / ${route.lane} / ${route.priority} / ${route.source || "unknown"} / ${route.summary || "无摘要"}`,
            ...((route.actions || []).map((action) => `repair_action / ${action}`)),
          ])
        : ["repair_route / 无"]),
    ],
    "还没有研究归档详情。"
  );
  const panel = document.querySelector("#strategy-research-detail-export");
  if (panel) {
    panel.textContent = JSON.stringify(
      {
        version: entry.version,
        current: entry.isCurrent,
        created_at: entry.createdAt,
        research_export: exportManifest,
      },
      null,
      2
    );
  }
}

function renderProgrammerRuns(snapshot) {
  const runs = snapshot?.programmer_runs || [];
  renderList(
    "programmer-run-list",
    runs
      .slice()
      .reverse()
      .flatMap((item) => {
        const summary = item.failure_summary || {};
        const plan = item.repair_plan || {};
        const acceptance = item.acceptance_summary || {};
        const rollback = item.rollback_summary || {};
        const promotion = item.promotion_summary || {};
        const stability = item.stability_summary || {};
        const lines = [
          `${item.timestamp || "unknown"} / ${item.status || "unknown"} / failure=${item.failure_type || "none"} / commit=${item.commit_hash || "none"} / rollback=${item.rollback_commit || "none"} / files=${(item.changed_files || []).join(", ") || "none"}`,
        ];
        if (summary.attempt_count) {
          lines.push(`failure_summary / attempts=${summary.attempt_count} / dominant=${summary.dominant_failure_type || "unknown"} / latest=${summary.latest_failure_type || "unknown"}`);
          lines.push(`progress / ${item.progress_status || summary.progress_status || "unknown"} / ${item.progress_note || summary.progress_note || "无"}`);
          lines.push(`stop / reason=${item.stop_reason || "unknown"} / retry_exhausted=${item.retry_exhausted ? "yes" : "no"} / no_progress=${item.no_progress_detected ? "yes" : "no"} / stable_success_required=${item.stable_success_required ? "yes" : "no"}`);
        }
        if (plan.priority || (plan.actions || []).length) {
          lines.push(`repair_plan / ${plan.priority || "P1"} / ${(plan.actions || []).join("；") || "无"}`);
        }
        if (acceptance.acceptance_status) {
          lines.push(`acceptance / ${acceptance.acceptance_status} / gate=${acceptance.acceptance_gate || "manual_review"} / rollback=${acceptance.rollback_recommended ? "yes" : "no"} / promote=${acceptance.should_promote ? "yes" : "no"}`);
          if (acceptance.note) {
            lines.push(`acceptance_note / ${acceptance.note}`);
          }
        }
        if (rollback.rollback_status) {
          lines.push(`rollback_summary / ${rollback.rollback_status} / ready=${rollback.rollback_ready ? "yes" : "no"} / target=${rollback.rollback_target || "none"}`);
          if (rollback.action) {
            lines.push(`rollback_action / ${rollback.action}`);
          }
        }
        if (promotion.promotion_status) {
          lines.push(`promotion / ${promotion.promotion_status} / gate=${promotion.promotion_gate || "unknown"} / promote=${promotion.should_promote ? "yes" : "no"} / review=${promotion.requires_review ? "yes" : "no"}`);
          if (promotion.note) {
            lines.push(`promotion_note / ${promotion.note}`);
          }
        }
        if (stability.stability_status) {
          lines.push(`stability / ${stability.stability_status} / retry_depth=${stability.retry_depth ?? "unknown"} / stop=${stability.stop_reason || "unknown"}`);
          if (stability.note) {
            lines.push(`stability_note / ${stability.note}`);
          }
        }
        if (item.validation_detail) {
          lines.push(`validation_gate / ${item.validation_detail}`);
        }
        return lines;
      }),
    "还没有 Programmer Agent 记录。"
  );
  const panel = document.querySelector("#programmer-diff-panel");
  if (panel) {
    if (!runs.length) {
      panel.textContent = "还没有代码差异。";
    } else {
      const latest = runs[runs.length - 1];
      const attemptSummary = (latest.attempts || [])
        .map((item) => `attempt=${item.attempt} status=${item.status} failure=${item.failure_type || "none"} validation=${item.validation_ok === false ? "fail" : "pass"}`)
        .join("\n");
      const failureSummary = latest.failure_summary
        ? JSON.stringify(latest.failure_summary, null, 2)
        : "";
      const repairPlan = latest.repair_plan
        ? JSON.stringify(latest.repair_plan, null, 2)
        : "";
      const acceptanceSummary = latest.acceptance_summary
        ? JSON.stringify(latest.acceptance_summary, null, 2)
        : "";
      const rollbackSummary = latest.rollback_summary
        ? JSON.stringify(latest.rollback_summary, null, 2)
        : "";
      const promotionSummary = latest.promotion_summary
        ? JSON.stringify(latest.promotion_summary, null, 2)
        : "";
      const stabilitySummary = latest.stability_summary
        ? JSON.stringify(latest.stability_summary, null, 2)
        : "";
      const stopSummary = JSON.stringify(
        {
          progress_status: latest.progress_status,
          progress_note: latest.progress_note,
          stop_reason: latest.stop_reason,
          retry_exhausted: latest.retry_exhausted,
          no_progress_detected: latest.no_progress_detected,
          stable_success_required: latest.stable_success_required,
        },
        null,
        2
      );
      panel.textContent = [attemptSummary, failureSummary, repairPlan, acceptanceSummary, rollbackSummary, promotionSummary, stabilitySummary, stopSummary, latest.diff || "", latest.stderr || ""].filter(Boolean).join("\n\n");
    }
  }
}

function renderProgrammerStats(snapshot) {
  const runs = snapshot?.programmer_runs || [];
  const counts = {};
  for (const run of runs) {
    const key = run.failure_type || (run.status === "ok" ? "success" : "unknown");
    counts[key] = (counts[key] || 0) + 1;
  }
  const grid = document.querySelector("#programmer-stats-grid");
  if (grid) {
    const entries = Object.entries(counts).sort((a, b) => Number(b[1]) - Number(a[1]));
    if (!entries.length) {
      grid.innerHTML = `<article class="check-card"><strong>还没有 Programmer Agent 趋势视图。</strong></article>`;
    } else {
      grid.innerHTML = entries.map(([name, count]) => `
        <article class="check-card ${name === "success" ? "check-pass" : "check-warning"}">
          <div class="check-head">
            <strong>${name}</strong>
            <span class="status-chip ${name === "success" ? "success-chip" : "warn-chip"}">${count}</span>
          </div>
          <p class="check-summary">最近运行中，类型为 ${name} 的结果出现了 ${count} 次。</p>
        </article>
      `).join("");
    }
  }
  const recentFailures = runs
    .filter((item) => item.failure_type)
    .slice()
    .reverse()
    .slice(0, 5)
    .map((item) => `${item.timestamp || "unknown"} / ${item.failure_type} / ${item.validation_detail || item.stderr || item.error || "no detail"}`);
  const summary = Object.entries(counts)
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .map(([name, count]) => `${name}: ${count}`);
  renderList(
    "programmer-stats-list",
    [...summary, ...recentFailures],
    "还没有 Programmer Agent 统计。"
  );
}

function renderModelRouting(snapshot) {
  const pkg = snapshot?.strategy_package || {};
  const agentMap = pkg.agent_model_map || {};
  const taskMap = pkg.task_model_map || {};
  const grid = document.querySelector("#strategy-model-grid");
  const agentEntries = Object.entries(agentMap);
  const taskEntries = Object.entries(taskMap);
  if (grid) {
    if (!agentEntries.length && !taskEntries.length) {
      grid.innerHTML = `<article class="check-card"><strong>还没有模型路由信息。</strong></article>`;
    } else {
      const agentCards = agentEntries.map(([agent, info]) => `
        <article class="check-card">
          <div class="check-head">
            <strong>${agent}</strong>
            <span class="status-chip outline-chip">agent</span>
          </div>
          <p class="check-summary">${info.provider || "unknown"} / ${info.model || "unknown"}</p>
          <p class="check-label">fallback</p>
          <p>${info.fallback_provider || "n/a"} / ${info.fallback_model || "n/a"}</p>
        </article>
      `).join("");
      const taskCards = taskEntries.map(([task, info]) => `
        <article class="check-card">
          <div class="check-head">
            <strong>${task}</strong>
            <span class="status-chip outline-chip">task</span>
          </div>
          <p class="check-summary">${info.provider || "unknown"} / ${info.model || "unknown"}</p>
          <p class="check-label">temperature</p>
          <p>${info.temperature ?? "default"}</p>
        </article>
      `).join("");
      grid.innerHTML = agentCards + taskCards;
    }
  }
  const lines = [
    ...agentEntries.map(([agent, info]) => `Agent / ${agent}: ${info.provider || "unknown"} / ${info.model || "unknown"}${info.fallback_model ? ` / fallback=${info.fallback_provider || "unknown"}:${info.fallback_model}` : ""}`),
    ...taskEntries.map(([task, info]) => `Task / ${task}: ${info.provider || "unknown"} / ${info.model || "unknown"} / temperature=${info.temperature ?? "default"}`),
  ];
  renderList("strategy-model-list", lines, "还没有模型路由信息。");
}

function renderTokenUsage(snapshot) {
  const usage = snapshot?.token_usage || {};
  const totals = Object.values(usage?.totals || {});
  const recent = usage?.recent_calls || [];
  const calls = totals.reduce((sum, item) => sum + Number(item.calls || 0), 0);
  const inputTokens = totals.reduce((sum, item) => sum + Number(item.input_tokens || 0), 0);
  const outputTokens = totals.reduce((sum, item) => sum + Number(item.output_tokens || 0), 0);
  const cacheHits = totals.reduce((sum, item) => sum + Number(item.cache_hits || 0), 0);
  const grid = document.querySelector("#strategy-token-grid");
  if (grid) {
    if (!totals.length) {
      grid.innerHTML = `<article class="check-card"><strong>还没有 token 使用信息。</strong></article>`;
    } else {
      grid.innerHTML = `
        <article class="check-card">
          <div class="check-head">
            <strong>Calls</strong>
            <span class="status-chip outline-chip">${calls}</span>
          </div>
          <p class="check-summary">本轮及近期会话累计 LLM 调用次数。</p>
        </article>
        <article class="check-card">
          <div class="check-head">
            <strong>Input Tokens</strong>
            <span class="status-chip outline-chip">${inputTokens}</span>
          </div>
          <p class="check-summary">输入 token 估算总量。</p>
        </article>
        <article class="check-card">
          <div class="check-head">
            <strong>Output Tokens</strong>
            <span class="status-chip outline-chip">${outputTokens}</span>
          </div>
          <p class="check-summary">输出 token 估算总量。</p>
        </article>
        <article class="check-card">
          <div class="check-head">
            <strong>Cache Hits</strong>
            <span class="status-chip outline-chip">${cacheHits}</span>
          </div>
          <p class="check-summary">命中 LLM 结果缓存的次数。</p>
        </article>
      `;
    }
  }
  const lines = [
    ...totals
      .slice()
      .sort((a, b) => Number(b.calls || 0) - Number(a.calls || 0))
      .map((item) => `${item.task} / ${item.provider}/${item.model} / calls=${item.calls} / cache_hits=${item.cache_hits || 0} / in=${item.input_tokens} / out=${item.output_tokens}`),
    ...recent.slice(-5).reverse().map((item) => `${item.timestamp || "unknown"} / ${item.task} / ${item.provider}/${item.model} / in=${item.input_tokens} / out=${item.output_tokens}`),
  ];
  renderList("strategy-token-list", lines, "还没有 token 使用信息。");
}

function renderProgrammerTrend(snapshot) {
  const filter = document.querySelector("#programmer-trend-filter")?.value || "all";
  const runs = (snapshot?.programmer_runs || [])
    .filter((run) => {
      if (filter === "all") return true;
      const kind = run.failure_type || (run.status === "ok" ? "success" : run.status || "unknown");
      return kind === filter;
    })
    .slice()
    .reverse()
    .slice(0, 10);
  const grid = document.querySelector("#programmer-trend-grid");
  if (grid) {
    if (!runs.length) {
      grid.innerHTML = `<article class="check-card"><strong>还没有 Programmer Agent 趋势时间线。</strong></article>`;
    } else {
      grid.innerHTML = runs.map((run) => {
        const kind = run.failure_type || (run.status === "ok" ? "success" : run.status || "unknown");
        const ok = kind === "success";
        const statusClass = ok ? "check-pass" : "check-warning";
        const chipClass = ok ? "success-chip" : "warn-chip";
        return `
          <article class="check-card ${statusClass}">
            <div class="check-head">
              <strong>${run.timestamp || "unknown"}</strong>
              <span class="status-chip ${chipClass}">${kind}</span>
            </div>
            <p class="check-summary">status=${run.status || "unknown"} / attempts=${(run.attempts || []).length || 1}</p>
            <p class="check-label">detail</p>
            <p>${run.validation_detail || run.error || run.stderr || "no detail"}</p>
          </article>
        `;
      }).join("");
    }
  }
  renderList(
    "programmer-trend-list",
    runs.map((run) => {
      const kind = run.failure_type || (run.status === "ok" ? "success" : run.status || "unknown");
      return `${run.timestamp || "unknown"} / ${kind} / attempts=${(run.attempts || []).length || 1} / ${run.validation_detail || run.error || run.stderr || "no detail"}`;
    }),
    "还没有 Programmer Agent 趋势时间线。"
  );
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
    renderStrategy(latest);
    const latestRun = (latest.programmer_runs || [])[latest.programmer_runs.length - 1] || {};
    setText("strategy-note", `Programmer Agent 已执行，status=${latestRun.status || "unknown"}。`);
    appendStrategyLog("info", `Programmer Agent 执行完成，commit=${latestRun.commit_hash || "none"}。`);
    focusPanel("#programmer-diff-panel");
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
  const source = evaluation.evaluation_source ? ` / 来源 ${evaluation.evaluation_source}` : "";
  return `${title}: 收益 ${evaluation.expected_return_pct}% / 胜率 ${evaluation.win_rate_pct}% / 回撤 ${evaluation.drawdown_pct}% / 最大亏损 ${evaluation.max_loss_pct}% / 目标分 ${evaluation.objective_score}${source}`;
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

function renderStrategyPerformance(snapshot) {
  const pkg = snapshot?.strategy_package || {};
  const datasetPlan = pkg.dataset_plan || {};
  const parts = [];
  if (datasetPlan.protocol) {
    parts.push(`dataset=${datasetPlan.protocol}`);
  }
  if (datasetPlan.cache_mode) {
    parts.push(`mode=${datasetPlan.cache_mode}`);
  }
  if (datasetPlan.cache_hit !== undefined) {
    parts.push(`dataset_cache_hit=${datasetPlan.cache_hit ? "yes" : "no"}`);
  }
  setText("strategy-performance-note", parts.length ? `增量训练: ${parts.join(" / ")}` : "当前还没有增量训练性能信息。");
}

function renderBacktestSummary(snapshot) {
  const pkg = snapshot?.strategy_package || {};
  const evaluation = pkg.recommended_variant?.evaluation || pkg.baseline_evaluation || null;
  const dataset = evaluation?.dataset_evaluation || {};
  const coverage = evaluation?.coverage_summary || pkg.research_summary?.evaluation_snapshot?.coverage_summary || {};
  if (!evaluation || !dataset.train || !dataset.validation || !dataset.test) {
    const grid = document.querySelector("#strategy-walkforward-grid");
    if (grid) {
      grid.innerHTML = `<article class="check-card"><strong>还没有 walk-forward 热力视图。</strong></article>`;
    }
    renderList("strategy-backtest-list", [], "还没有回测结果。");
    renderList("strategy-walkforward-list", [], "还没有 walk-forward 结果。");
    return;
  }
  renderList(
    "strategy-backtest-list",
    [
      `评估来源: ${evaluation.evaluation_source || "unknown"}`,
      `覆盖摘要: 标的 ${coverage.symbol_count ?? "unknown"} / bars ${coverage.total_bar_count ?? "unknown"} / wf_windows ${coverage.walk_forward_window_count ?? 0}`,
      `覆盖健康: ${coverage.coverage_grade || "unknown"} / ${coverage.coverage_health_note || "无"}`,
      `覆盖警告: ${(coverage.coverage_warnings || []).join("，") || "无"}`,
      `覆盖区间: ${coverage.date_range?.start || "unknown"} -> ${coverage.date_range?.end || "unknown"}`,
      `Train: 收益 ${dataset.train.expected_return_pct}% / 胜率 ${dataset.train.win_rate_pct}% / 回撤 ${dataset.train.drawdown_pct}% / 最大亏损 ${dataset.train.max_loss_pct}% / 分数 ${dataset.train.objective_score}`,
      `Validation: 收益 ${dataset.validation.expected_return_pct}% / 胜率 ${dataset.validation.win_rate_pct}% / 回撤 ${dataset.validation.drawdown_pct}% / 最大亏损 ${dataset.validation.max_loss_pct}% / 分数 ${dataset.validation.objective_score}`,
      `Test: 收益 ${dataset.test.expected_return_pct}% / 胜率 ${dataset.test.win_rate_pct}% / 回撤 ${dataset.test.drawdown_pct}% / 最大亏损 ${dataset.test.max_loss_pct}% / 分数 ${dataset.test.objective_score}`,
      `Stability: score=${dataset.stability?.score ?? "unknown"} / walk_forward=${dataset.stability?.walk_forward_score ?? "unknown"} / gap=${dataset.stability?.train_test_gap ?? "unknown"}`,
    ],
    "还没有回测结果。"
  );
  const walkForward = dataset.walk_forward || [];
  const grid = document.querySelector("#strategy-walkforward-grid");
  if (grid) {
    if (!walkForward.length) {
      grid.innerHTML = `<article class="check-card"><strong>还没有 walk-forward 热力视图。</strong></article>`;
    } else {
      grid.innerHTML = walkForward.map((item) => {
        const score = Number(item.objective_score || 0);
        const statusClass = score >= 0.8 ? "check-pass" : score >= 0.55 ? "check-warning" : "check-fail";
        const chipClass = score >= 0.8 ? "success-chip" : score >= 0.55 ? "warn-chip" : "danger-chip";
        return `
          <article class="check-card ${statusClass}">
            <div class="check-head">
              <strong>${item.window_id}</strong>
              <span class="status-chip ${chipClass}">${score.toFixed(4)}</span>
            </div>
            <p class="check-summary">收益 ${item.expected_return_pct}% / 胜率 ${item.win_rate_pct}% / 回撤 ${item.drawdown_pct}%</p>
            <p class="check-label">窗口</p>
            <p>${item.validation_start} -> ${item.validation_end}</p>
          </article>
        `;
      }).join("");
    }
  }
  renderList(
    "strategy-walkforward-list",
    walkForward.map((item) => `窗口 ${item.window_id}: 收益 ${item.expected_return_pct}% / 胜率 ${item.win_rate_pct}% / 回撤 ${item.drawdown_pct}% / 最大亏损 ${item.max_loss_pct}% / 分数 ${item.objective_score}`),
    "还没有 walk-forward 结果。"
  );
}

function renderStrategy(snapshot) {
  formatJsonIntoList("strategy-package-list", snapshot?.strategy_package || null, "还没有策略包。");
  renderStrategyStatus(snapshot);
  renderReleaseSnapshot(snapshot);
  renderList(
    "strategy-check-list",
    (snapshot?.strategy_checks || []).map((item) => {
      const fixes = (item.required_fix_actions || []).join("；");
      return `${item.check_type} / ${item.status} / ${item.summary}${fixes ? ` / 修复: ${fixes}` : ""}`;
    }),
    "等待策略检查。"
  );
  renderCheckFailureTrend(snapshot);
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
  renderResearchSummary(snapshot);
  renderResearchTrendSummary(snapshot);
  renderRepairTrendSummary(snapshot);
  renderResearchHealthSummary(snapshot);
  renderResearchCodeLoop(snapshot);
  renderRepairRouting(snapshot);
  renderFeatureSnapshot(snapshot);
  renderInputManifest(snapshot);
  renderDataBundles(snapshot);
  renderStrategyHistory(snapshot);
  renderStrategyArchive(snapshot);
  renderFailureEvolution(snapshot);
  populateVersionSelectors(snapshot);
  populateResearchArchiveSelectors(snapshot);
  renderVariantComparison(snapshot);
  renderModelRouting(snapshot);
  renderTokenUsage(snapshot);
  renderBacktestSummary(snapshot);
  renderStrategyCode(snapshot);
  renderStrategyPerformance(snapshot);
  renderVersionCode(snapshot);
  runVersionCompare(snapshot);
  runResearchArchiveCompare(snapshot);
  renderResearchArchiveDetail(snapshot);
  renderProgrammerRuns(snapshot);
  renderProgrammerStats(snapshot);
  renderProgrammerTrend(snapshot);
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
    focusPanel("#strategy-research-summary-list");
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
    renderStrategy(latest);
    setText("strategy-note", "策略已确认。");
    appendStrategyLog("success", `策略确认完成，phase=${latest.phase}`);
    focusPanel("#strategy-status-list");
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
document.querySelector("#run-strategy-research-compare")?.addEventListener("click", () => runResearchArchiveCompare(loadStoredSnapshot() || {}));
document.querySelector("#strategy-research-detail-version")?.addEventListener("change", () => renderResearchArchiveDetail(loadStoredSnapshot() || {}));
document.querySelector("#history-version-select")?.addEventListener("change", () => renderVersionCode(loadStoredSnapshot() || {}));
document.querySelector("#restore-version-button")?.addEventListener("click", () => restoreStrategyVersion(loadStoredSnapshot() || {}));
document.querySelector("#run-programmer-agent")?.addEventListener("click", runProgrammerAgent);
document.querySelector("#programmer-trend-filter")?.addEventListener("change", () => renderProgrammerTrend(loadStoredSnapshot() || {}));
document.querySelector("#apply-repair-feedback")?.addEventListener("click", applyRepairRoutingToFeedback);
document.querySelector("#apply-repair-programmer")?.addEventListener("click", applyRepairRoutingToProgrammer);
document.querySelector("#apply-repair-and-iterate")?.addEventListener("click", () => applyRepairAndIterate().catch((error) => {
  setText("strategy-note", `自动回填并训练失败：${error.message}`);
  appendStrategyLog("error", `自动回填并训练失败：${error.message}`);
}));
document.querySelector("#apply-repair-and-programmer")?.addEventListener("click", () => applyRepairAndRunProgrammer().catch((error) => {
  setText("strategy-note", `自动回填并执行 Programmer Agent 失败：${error.message}`);
  appendStrategyLog("error", `自动回填并执行 Programmer Agent 失败：${error.message}`);
}));
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
  const pendingFocus = window.localStorage.getItem(STRATEGY_FOCUS_KEY);
  if (pendingFocus) {
    window.localStorage.removeItem(STRATEGY_FOCUS_KEY);
    window.setTimeout(() => focusPanel(pendingFocus), 120);
  }
})();
