const STRATEGY_FOCUS_KEY = "sentinel-alpha:strategy-focus-target";

function jumpToStrategyFocus(target) {
  window.localStorage.setItem(STRATEGY_FOCUS_KEY, target);
  window.location.href = "./strategy.html";
}

function getStrategyResearchEntries(snapshot) {
  return (snapshot?.report_history || [])
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
      };
    })
    .filter((item) => item.version !== "unknown");
}

function populateResearchCompareSelectors(snapshot) {
  const entries = getStrategyResearchEntries(snapshot);
  const selectors = [
    document.querySelector("#report-compare-a"),
    document.querySelector("#report-compare-b"),
    document.querySelector("#report-detail-version"),
  ];
  for (const select of selectors) {
    if (!select) continue;
    const currentValue = select.value;
    select.innerHTML = entries.length
      ? entries.map((item) => `<option value="${item.version}">${item.version}</option>`).join("")
      : `<option value="">暂无版本</option>`;
    if (entries.some((item) => item.version === currentValue)) {
      select.value = currentValue;
    }
  }
  if (entries.length >= 2) {
    if (!document.querySelector("#report-compare-a")?.value) {
      document.querySelector("#report-compare-a").value = entries[0].version;
    }
    if (!document.querySelector("#report-compare-b")?.value) {
      document.querySelector("#report-compare-b").value = entries[1].version;
    }
  }
  if (entries.length && !document.querySelector("#report-detail-version")?.value) {
    document.querySelector("#report-detail-version").value = entries[0].version;
  }
}

function renderReportArchive(snapshot) {
  const reports = snapshot?.report_history || [];
  renderList(
    "report-history-list",
    reports
      .slice()
      .reverse()
      .map((item) => {
        const exportManifest = item.body?.research_export || {};
        const bundleId =
          item.report_type === "strategy_iteration"
            ? exportManifest.data_bundle_id || item.body?.strategy_package?.data_bundle_id || item.body?.training_log_entry?.data_bundle_id
            : null;
        const quality =
          item.report_type === "strategy_iteration"
            ? exportManifest.quality_grade || item.body?.strategy_package?.input_manifest?.data_quality?.quality_grade || item.body?.training_log_entry?.input_manifest?.data_quality?.quality_grade
            : null;
        const readiness =
          item.report_type === "strategy_iteration"
            ? exportManifest.training_readiness || item.body?.strategy_package?.input_manifest?.data_quality?.training_readiness?.status || item.body?.training_log_entry?.input_manifest?.data_quality?.training_readiness?.status
            : null;
        const feedback =
          item.report_type === "strategy_iteration"
            ? item.body?.training_log_entry?.feedback || item.body?.strategy_package?.feedback
            : null;
        const winner = item.report_type === "strategy_iteration" ? exportManifest.winner_variant_id : null;
        const gate = item.report_type === "strategy_iteration" ? exportManifest.gate_status : null;
        return `${item.created_at} / ${item.report_type} / ${item.title}${bundleId ? ` / bundle=${bundleId}` : ""}${quality ? ` / grade=${quality}` : ""}${readiness ? ` / training=${readiness}` : ""}${winner ? ` / winner=${winner}` : ""}${gate ? ` / gate=${gate}` : ""}${feedback ? ` / 用户意见=${feedback}` : ""}`;
      }),
    "当前还没有报告归档。"
  );
}

function renderUserFeedback(snapshot) {
  const feedbackLog = snapshot?.strategy_feedback_log || [];
  renderList(
    "user-feedback-list",
    feedbackLog
      .slice()
      .reverse()
      .map((item) => `${item.timestamp || "unknown"} / ${item.strategy_type || "unknown"} / ${item.feedback || "无"} / source=${item.source_type || "strategy_feedback"}`),
    "当前还没有用户意见记录。"
  );
}

function renderStrategyResearchArchive(snapshot) {
  const reports = getStrategyResearchEntries(snapshot);
  renderList(
    "strategy-research-archive-list",
    reports
      .slice()
      .reverse()
      .map((item) => {
        const research = item.research || {};
        const winner = item.exportManifest?.winner_variant_id || research.winner_selection_summary?.winner_variant_id || "unknown";
        const gate = item.exportManifest?.gate_status || research.final_release_gate_summary?.gate_status || "unknown";
        const robustness = item.exportManifest?.robustness_grade || research.robustness_summary?.grade || "unknown";
        const nextFocus = item.exportManifest?.next_iteration_focus || research.next_iteration_focus || [];
        return `${item.createdAt} / ${item.title} / winner=${winner} / gate=${gate} / robustness=${robustness} / next=${nextFocus.join("；") || "无"}`;
      }),
    "当前还没有策略研究归档。"
  );
}

function runResearchCompare(snapshot) {
  const entries = getStrategyResearchEntries(snapshot);
  const versionA = document.querySelector("#report-compare-a")?.value;
  const versionB = document.querySelector("#report-compare-b")?.value;
  const a = entries.find((item) => item.version === versionA);
  const b = entries.find((item) => item.version === versionB);
  if (!a || !b) {
    renderList("report-compare-list", [], "当前还没有研究归档对比。");
    const panel = document.querySelector("#report-research-export");
    if (panel) panel.textContent = "{}";
    return;
  }
  const aWinner = a.research?.winner_selection_summary || {};
  const bWinner = b.research?.winner_selection_summary || {};
  const aGate = a.research?.final_release_gate_summary || {};
  const bGate = b.research?.final_release_gate_summary || {};
  const aRobust = a.research?.robustness_summary || {};
  const bRobust = b.research?.robustness_summary || {};
  renderList(
    "report-compare-list",
    [
      `版本A / ${a.version} / winner=${aWinner.winner_variant_id || "unknown"} / gate=${aGate.gate_status || "unknown"} / robustness=${aRobust.grade || "unknown"}`,
      `版本B / ${b.version} / winner=${bWinner.winner_variant_id || "unknown"} / gate=${bGate.gate_status || "unknown"} / robustness=${bRobust.grade || "unknown"}`,
      `winner 变化 / ${aWinner.winner_variant_id || "unknown"} -> ${bWinner.winner_variant_id || "unknown"}`,
      `gate 变化 / ${aGate.gate_status || "unknown"} -> ${bGate.gate_status || "unknown"}`,
      `robustness 变化 / ${aRobust.grade || "unknown"} -> ${bRobust.grade || "unknown"}`,
      `next_focus A / ${(a.research?.next_iteration_focus || []).join("；") || "无"}`,
      `next_focus B / ${(b.research?.next_iteration_focus || []).join("；") || "无"}`,
    ],
    "当前还没有研究归档对比。"
  );
  const panel = document.querySelector("#report-research-export");
  if (panel) {
    panel.textContent = JSON.stringify(
      {
        version_a: {
          version: a.version,
          created_at: a.createdAt,
          research_summary: a.research,
        },
        version_b: {
          version: b.version,
          created_at: b.createdAt,
          research_summary: b.research,
        },
      },
      null,
      2
    );
  }
}

function renderResearchArchiveDetail(snapshot) {
  const entries = getStrategyResearchEntries(snapshot);
  const version = document.querySelector("#report-detail-version")?.value;
  const entry = entries.find((item) => item.version === version);
  if (!entry) {
    renderList("report-research-detail-list", [], "当前还没有研究归档详情。");
    const panel = document.querySelector("#report-research-detail-export");
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
    "report-research-detail-list",
    [
      `version / ${entry.version}`,
      `created_at / ${entry.createdAt}`,
      `winner / ${winner}`,
      `gate / ${gate}`,
      `robustness / ${robustness}`,
      `bundle / ${exportManifest.data_bundle_id || "unknown"}`,
      `quality / ${exportManifest.quality_grade || "unknown"} / training=${exportManifest.training_readiness || "unknown"}`,
      `check_target / ${exportManifest.check_target_variant_id || "unknown"} / source=${exportManifest.evaluation_source || "unknown"}`,
      `train/validation/test / ${evaluation.train?.objective_score ?? "unknown"} / ${evaluation.validation?.objective_score ?? "unknown"} / ${evaluation.test?.objective_score ?? "unknown"}`,
      `walk_forward / ${evaluation.walk_forward_score ?? "unknown"} / windows=${evaluation.walk_forward_windows ?? 0}`,
      `test_detail / gross=${evaluation.test?.gross_exposure_pct ?? "unknown"} / net=${evaluation.test?.net_exposure_pct ?? "unknown"} / turnover=${evaluation.test?.avg_daily_turnover_proxy_pct ?? "unknown"} / obs=${evaluation.test?.observation_count ?? "unknown"}`,
      `coverage / symbols=${coverage.symbol_count ?? "unknown"} / bars=${coverage.total_bar_count ?? "unknown"} / wf_windows=${coverage.walk_forward_window_count ?? 0}`,
      `coverage_health / ${coverage.coverage_grade || "unknown"} / ${coverage.coverage_health_note || "无"}`,
      `coverage_warnings / ${(coverage.coverage_warnings || []).join("，") || "无"}`,
      `coverage_range / ${coverage.date_range?.start || "unknown"} -> ${coverage.date_range?.end || "unknown"}`,
      `gap / ${evaluation.train_test_gap ?? "unknown"}`,
      `next_focus / ${(exportManifest.next_iteration_focus || []).join("；") || "无"}`,
      `failed_checks / ${(exportManifest.failed_checks || []).join(", ") || "无"}`,
      `primary_repair_route / ${primaryRepairRoute ? `${primaryRepairRoute.lane} / ${primaryRepairRoute.priority} / ${primaryRepairRoute.source || "unknown"}` : "无"}`,
      ...(repairRoutes.length
        ? repairRoutes.flatMap((route) => [
            `repair_route / ${route.lane} / ${route.priority} / ${route.source || "unknown"} / ${route.summary || "无摘要"}`,
            ...((route.actions || []).map((action) => `repair_action / ${action}`)),
          ])
        : ["repair_route / 无"]),
    ],
    "当前还没有研究归档详情。"
  );
  const panel = document.querySelector("#report-research-detail-export");
  if (panel) {
    panel.textContent = JSON.stringify(
      {
        version: entry.version,
        created_at: entry.createdAt,
        research_export: exportManifest,
      },
      null,
      2
    );
  }
}

function renderFeedbackImpact(snapshot) {
  const feedbackLog = snapshot?.strategy_feedback_log || [];
  const trainingLog = snapshot?.strategy_training_log || [];
  const items = feedbackLog
    .map((feedbackItem) => {
      const matched = trainingLog.find((trainItem) => (trainItem.feedback || "") === (feedbackItem.feedback || ""));
      const matchedIndex = trainingLog.findIndex((trainItem) => (trainItem.feedback || "") === (feedbackItem.feedback || ""));
      const previous = matchedIndex > 0 ? trainingLog[matchedIndex - 1] : null;
      const research = matched?.research_summary || {};
      const winner = research.winner_selection_summary || {};
      const gate = research.final_release_gate_summary || {};
      const previousResearch = previous?.research_summary || {};
      const previousWinner = previousResearch.winner_selection_summary || {};
      const previousGate = previousResearch.final_release_gate_summary || {};
      return {
        feedback: feedbackItem.feedback || "无",
        strategyType: feedbackItem.strategy_type || "unknown",
        feedbackTimestamp: feedbackItem.timestamp || "unknown",
        iterationNo: matched?.iteration_no,
        version: matched?.recommended_variant || "unknown",
        status: matched?.status || "unknown",
        gateStatus: gate.gate_status || "unknown",
        nextFocus: (research.next_iteration_focus || []).join("；") || "无",
        winner: winner.winner_variant_id || "unknown",
        previousWinner: previousWinner.winner_variant_id || "unknown",
        previousGate: previousGate.gate_status || "unknown",
        previousFailedChecks: (previous?.failed_checks || []).join(", ") || "无",
        currentFailedChecks: (matched?.failed_checks || []).join(", ") || "无",
      };
    })
    .reverse();
  renderList(
    "feedback-impact-list",
    items.map((item) => `${item.feedbackTimestamp} / ${item.strategyType} / 用户意见=${item.feedback} / 对应迭代=${item.iterationNo || "-"} / 推荐变化=${item.previousWinner} -> ${item.winner} / 发布门变化=${item.previousGate} -> ${item.gateStatus} / 失败检查变化=${item.previousFailedChecks} -> ${item.currentFailedChecks} / 训练状态=${item.status} / 下一轮重点=${item.nextFocus}`),
    "当前还没有用户意见对应结果。"
  );
}

function renderHistoryTimeline(snapshot) {
  const events = snapshot?.history_events || [];
  renderList(
    "history-list",
    events
      .slice()
      .reverse()
      .map((item) => {
        const feedback = item.payload?.feedback ? ` / 用户意见=${item.payload.feedback}` : "";
        const strategyType = item.payload?.strategy_type ? ` / strategy=${item.payload.strategy_type}` : "";
        const winner = item.payload?.winner_variant_id ? ` / winner=${item.payload.winner_variant_id}` : "";
        const gate = item.payload?.gate_status ? ` / gate=${item.payload.gate_status}` : "";
        const source = item.payload?.evaluation_source ? ` / source=${item.payload.evaluation_source}` : "";
        const robustness = item.payload?.robustness_grade ? ` / robustness=${item.payload.robustness_grade}` : "";
        const repairRoute = item.payload?.repair_route_lane ? ` / repair=${item.payload.repair_route_lane}` : "";
        const repairPriority = item.payload?.repair_route_priority ? ` / repair_priority=${item.payload.repair_route_priority}` : "";
        const terminalName = item.payload?.terminal_name ? ` / terminal=${item.payload.terminal_name}` : "";
        const terminalType = item.payload?.terminal_type ? ` / type=${item.payload.terminal_type}` : "";
        const readiness = item.payload?.readiness_status ? ` / readiness=${item.payload.readiness_status}` : "";
        const testCounts =
          typeof item.payload?.passed_check_count !== "undefined"
            ? ` / terminal_checks=${item.payload.passed_check_count}/${item.payload?.total_check_count ?? 0}`
            : "";
        const splitScores =
          typeof item.payload?.test_objective_score !== "undefined"
            ? ` / T/Va/Te=${item.payload?.train_objective_score ?? "unknown"}/${item.payload?.validation_objective_score ?? "unknown"}/${item.payload?.test_objective_score ?? "unknown"}`
            : "";
        const walkForward = typeof item.payload?.walk_forward_score !== "undefined" ? ` / wf=${item.payload.walk_forward_score}` : "";
        const gap = typeof item.payload?.train_test_gap !== "undefined" ? ` / gap=${item.payload.train_test_gap}` : "";
        return `${item.timestamp} / ${item.event_type} / ${item.summary}${strategyType}${feedback}${item.payload?.data_bundle_id ? ` / bundle=${item.payload.data_bundle_id}` : ""}${item.payload?.quality_grade ? ` / grade=${item.payload.quality_grade}` : ""}${item.payload?.training_readiness ? ` / training=${item.payload.training_readiness}` : ""}${winner}${gate}${source}${robustness}${terminalName}${terminalType}${readiness}${testCounts}${repairRoute}${repairPriority}${splitScores}${walkForward}${gap}`;
      }),
    "当前还没有历史记录。"
  );
}

function renderBundleTimeline(snapshot) {
  const bundles = snapshot?.data_bundles || [];
  renderList(
    "bundle-history-list",
    bundles
      .slice()
      .reverse()
      .map((item) => `${item.created_at} / ${item.data_bundle_id} / protocol=${item.dataset_protocol || "unknown"} / grade=${item.quality_grade || "unknown"} / training=${item.training_readiness || "unknown"} / uses=${item.usage_count || 0} / providers=${(item.provider_coverage || []).join(", ") || "none"}`),
    "当前还没有输入数据包记录。"
  );
}

function renderBundleQuality(snapshot) {
  const pkg = snapshot?.strategy_package || {};
  const manifest = pkg.input_manifest || {};
  const quality = manifest.data_quality || {};
  const freshness = quality.freshness || {};
  const lines = [];
  if (pkg.data_bundle_id || pkg.feature_snapshot_version) {
    lines.push(`bundle / ${pkg.data_bundle_id || "unknown"} / snapshot=${pkg.feature_snapshot_version || "unknown"}`);
  }
  if (quality.quality_grade || quality.training_readiness?.status) {
    lines.push(`quality / grade=${quality.quality_grade || "unknown"} / training=${quality.training_readiness?.status || "unknown"}`);
  }
  if (quality.training_readiness?.note) {
    lines.push(`note / ${quality.training_readiness.note}`);
  }
  if (typeof freshness.max_gap_hours !== "undefined") {
    lines.push(`freshness / gap_hours=${freshness.max_gap_hours ?? "unknown"} / ts_count=${freshness.known_timestamp_count ?? 0}`);
  }
  if ((quality.alignment_warnings || []).length) {
    lines.push(`warnings / ${quality.alignment_warnings.join(", ")}`);
  }
  if ((manifest.provider_coverage || []).length) {
    lines.push(`providers / ${(manifest.provider_coverage || []).join(", ")}`);
  }
  renderList("bundle-quality-list", lines, "当前还没有训练输入质量信息。");
}

function renderLatestResearch(snapshot) {
  const pkg = snapshot?.strategy_package || {};
  const research = pkg.research_summary || {};
  const winner = research.winner_selection_summary || {};
  const gate = research.final_release_gate_summary || {};
  const robustness = research.robustness_summary || {};
  const evaluation = research.evaluation_snapshot || {};
  const coverage = evaluation.coverage_summary || {};
  const backtestBinding = research.backtest_binding_summary || {};
  const checks = research.check_failure_summary || [];
  const lines = [];
  if (pkg.version_label) {
    lines.push(`version / ${pkg.version_label} / winner=${winner.winner_variant_id || "unknown"} / gate=${gate.gate_status || "unknown"}`);
  }
  if (research.research_summary) {
    lines.push(`summary / ${research.research_summary}`);
  }
  if (robustness.grade) {
    lines.push(`robustness / grade=${robustness.grade} / stability=${robustness.stability_score ?? "unknown"} / gap=${robustness.train_test_gap ?? "unknown"}`);
  }
  if (backtestBinding.grade || evaluation.evaluation_source) {
    lines.push(`backtest_binding / grade=${backtestBinding.grade || "unknown"} / source=${backtestBinding.evaluation_source || evaluation.evaluation_source || "unknown"} / coverage=${backtestBinding.coverage_grade || coverage.coverage_grade || "unknown"}`);
    lines.push(`backtest_binding / ${backtestBinding.note || "无"}`);
  }
  if (evaluation.evaluation_source || evaluation.test || evaluation.validation) {
    lines.push(`evaluation / source=${evaluation.evaluation_source || "unknown"} / train=${evaluation.train?.objective_score ?? "unknown"} / validation=${evaluation.validation?.objective_score ?? "unknown"} / test=${evaluation.test?.objective_score ?? "unknown"}`);
    lines.push(`evaluation / walk_forward=${evaluation.walk_forward_score ?? "unknown"} / windows=${evaluation.walk_forward_windows ?? 0} / gap=${evaluation.train_test_gap ?? "unknown"}`);
    lines.push(`evaluation / gross=${evaluation.test?.gross_exposure_pct ?? "unknown"} / net=${evaluation.test?.net_exposure_pct ?? "unknown"} / turnover=${evaluation.test?.avg_daily_turnover_proxy_pct ?? "unknown"} / obs=${evaluation.test?.observation_count ?? "unknown"}`);
    lines.push(`coverage / symbols=${coverage.symbol_count ?? "unknown"} / bars=${coverage.total_bar_count ?? "unknown"} / wf_windows=${coverage.walk_forward_window_count ?? 0}`);
    lines.push(`coverage_health / ${coverage.coverage_grade || "unknown"} / ${coverage.coverage_health_note || "无"}`);
    lines.push(`coverage_warnings / ${(coverage.coverage_warnings || []).join("，") || "无"}`);
  }
  if (gate.reason) {
    lines.push(`release_gate / ${gate.reason}`);
  }
  for (const item of checks) {
    lines.push(`check_failure / ${item.check_type} / ${item.summary || "无"} / 修复=${(item.required_fix_actions || []).join("；") || "无"}`);
  }
  if ((research.next_iteration_focus || []).length) {
    lines.push(`next_focus / ${(research.next_iteration_focus || []).join("；")}`);
  }
  for (const item of (research.evaluation_highlights || [])) {
    lines.push(`evaluation_highlight / ${item}`);
  }
  renderList("latest-research-list", lines, "当前还没有策略研究结论。");
}

function renderReportResearchTrend(snapshot) {
  const logs = (snapshot?.strategy_training_log || []).slice().reverse().slice(0, 5);
  if (!logs.length) {
    renderList("report-research-trend-list", [], "当前还没有研究趋势摘要。");
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
    "report-research-trend-list",
    [
      `最近轮次 / ${logs.map((item) => `v${item.iteration_no || "-"}`).join(" -> ")}`,
      `gate 趋势 / ${previous ? `${previousGate} -> ${latestGate}` : latestGate}`,
      `test 趋势 / ${trendText(latestTest, previousTest)} / ${Number.isFinite(previousTest) ? previousTest : "unknown"} -> ${Number.isFinite(latestTest) ? latestTest : "unknown"}`,
      `walk_forward 趋势 / ${trendText(latestWalk, previousWalk)} / ${Number.isFinite(previousWalk) ? previousWalk : "unknown"} -> ${Number.isFinite(latestWalk) ? latestWalk : "unknown"}`,
      `gap 趋势 / ${trendText(latestGap, previousGap, true)} / ${Number.isFinite(previousGap) ? previousGap : "unknown"} -> ${Number.isFinite(latestGap) ? latestGap : "unknown"}`,
      `当前 focus / ${(latestResearch.next_iteration_focus || []).join("；") || "无"}`,
    ],
    "当前还没有研究趋势摘要。"
  );
}

function renderReportRepairTrend(snapshot) {
  const logs = (snapshot?.strategy_training_log || []).slice().reverse().slice(0, 5);
  if (!logs.length) {
    renderList("report-repair-trend-list", [], "当前还没有修复趋势摘要。");
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
    "report-repair-trend-list",
    [
      `最近轮次 / ${logs.map((item) => `v${item.iteration_no || "-"}`).join(" -> ")}`,
      `主修复路线 / ${previous ? `${routeLabel(previousRoute)} -> ${routeLabel(latestRoute)}` : routeLabel(latestRoute)}`,
      `优先级变化 / ${previous ? `${routePriority(previousRoute)} -> ${routePriority(latestRoute)}` : routePriority(latestRoute)}`,
      `来源变化 / ${previous ? `${routeSource(previousRoute)} -> ${routeSource(latestRoute)}` : routeSource(latestRoute)}`,
      `收敛结论 / ${convergence} / ${convergenceNote}`,
      `最近主路线分布 / ${Object.entries(counts).map(([name, count]) => `${name}=${count}`).join(" / ") || "无"}`,
      `当前动作 / ${((latestRoute?.actions || []).slice(0, 3)).join("；") || "无"}`,
    ],
    "当前还没有修复趋势摘要。"
  );
}

function renderReportResearchHealth(snapshot) {
  const logs = snapshot?.strategy_training_log || [];
  if (!logs.length) {
    renderList("report-research-health-list", [], "当前还没有研究健康结论。");
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
    "report-research-health-list",
    [
      `status / ${status}`,
      `gate / ${gate}`,
      `robustness / ${robustness}`,
      `note / ${note}`,
      ...(trendNotes.length ? trendNotes.map((item) => `trend / ${item}`) : ["trend / 当前还没有足够历史用于趋势判断。"]),
      `focus / ${(research.next_iteration_focus || []).join("；") || "无"}`,
    ],
    "当前还没有研究健康结论。"
  );
}

function renderReportReleaseSnapshot(snapshot) {
  const pkg = snapshot?.strategy_package || {};
  const research = pkg.research_summary || {};
  const gate = research.final_release_gate_summary || {};
  const quality = pkg.input_manifest?.data_quality || {};
  const checkTarget = research.check_target_summary || {};
  const winner = research.winner_selection_summary?.winner_variant_id || "unknown";
  const gateStatus = gate.gate_status || "unknown";
  const qualityGrade = quality.quality_grade || "unknown";
  const trainingReadiness = quality.training_readiness?.status || "unknown";
  const bundle = pkg.data_bundle_id || pkg.input_manifest?.data_bundle_id || "unknown";
  const evaluationSource = checkTarget.evaluation_source || "unknown";
  const grid = document.querySelector("#report-release-grid");
  if (grid) {
    if (!pkg.version_label) {
      grid.innerHTML = `<article class="check-card"><strong>当前还没有研究发布摘要。</strong></article>`;
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
    "report-release-list",
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
    "当前还没有研究发布摘要。"
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
  renderStrategyResearchArchive(snapshot);
  populateResearchCompareSelectors(snapshot);
  renderResearchArchiveDetail(snapshot);
  renderUserFeedback(snapshot);
  renderFeedbackImpact(snapshot);
  renderHistoryTimeline(snapshot);
  renderBundleTimeline(snapshot);
  renderBundleQuality(snapshot);
  renderLatestResearch(snapshot);
  renderReportResearchTrend(snapshot);
  renderReportRepairTrend(snapshot);
  renderReportResearchHealth(snapshot);
  renderReportReleaseSnapshot(snapshot);
  runResearchCompare(snapshot);
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
document.querySelector("#jump-to-strategy-research")?.addEventListener("click", () => jumpToStrategyFocus("#strategy-research-summary-list"));
document.querySelector("#jump-to-strategy-repair")?.addEventListener("click", () => jumpToStrategyFocus("#strategy-repair-route-list"));
document.querySelector("#jump-to-feedback-loop")?.addEventListener("click", () => jumpToStrategyFocus("#strategy-code-loop-list"));
document.querySelector("#run-report-compare")?.addEventListener("click", () => runResearchCompare(loadStoredSnapshot() || {}));
document.querySelector("#report-detail-version")?.addEventListener("change", () => renderResearchArchiveDetail(loadStoredSnapshot() || {}));

(async function bootstrapReportPage() {
  renderReportPage(loadStoredSnapshot());
})();
