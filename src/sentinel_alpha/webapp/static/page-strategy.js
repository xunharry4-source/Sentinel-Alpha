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

function renderFeatureSnapshot(snapshot) {
  const features = snapshot?.strategy_package?.feature_snapshot || {};
  const lines = [];
  if (features.meta) {
    lines.push(`meta / version=${features.meta.snapshot_version || "unknown"} / hash=${features.meta.snapshot_hash || "unknown"} / bundle=${features.meta.data_bundle_id || "unknown"}`);
  }
  if (features.data_quality) {
    lines.push(`data_quality / coverage=${features.data_quality.section_coverage_score ?? "unknown"} / providers=${features.data_quality.provider_count ?? 0}`);
    lines.push(`data_quality / available=${(features.data_quality.available_sections || []).join(", ") || "none"} / missing=${(features.data_quality.missing_sections || []).join(", ") || "none"}`);
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

function renderProgrammerRuns(snapshot) {
  const runs = snapshot?.programmer_runs || [];
  renderList(
    "programmer-run-list",
    runs
      .slice()
      .reverse()
      .map((item) => `${item.timestamp || "unknown"} / ${item.status || "unknown"} / failure=${item.failure_type || "none"} / commit=${item.commit_hash || "none"} / rollback=${item.rollback_commit || "none"} / files=${(item.changed_files || []).join(", ") || "none"}`),
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
      panel.textContent = [attemptSummary, latest.diff || "", latest.stderr || ""].filter(Boolean).join("\n\n");
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
  renderFeatureSnapshot(snapshot);
  renderInputManifest(snapshot);
  renderDataBundles(snapshot);
  renderStrategyHistory(snapshot);
  renderStrategyArchive(snapshot);
  renderFailureEvolution(snapshot);
  populateVersionSelectors(snapshot);
  renderVariantComparison(snapshot);
  renderModelRouting(snapshot);
  renderTokenUsage(snapshot);
  renderBacktestSummary(snapshot);
  renderStrategyCode(snapshot);
  renderStrategyPerformance(snapshot);
  renderVersionCode(snapshot);
  runVersionCompare(snapshot);
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
document.querySelector("#programmer-trend-filter")?.addEventListener("change", () => renderProgrammerTrend(loadStoredSnapshot() || {}));
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
