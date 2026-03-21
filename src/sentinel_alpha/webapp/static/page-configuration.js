const STRATEGY_FOCUS_KEY = "sentinel-alpha:strategy-focus-target";
const TERMINAL_FOCUS_KEY = "sentinel-alpha:terminal-focus-target";

function setValue(id, value) {
  const target = document.querySelector(`#${id}`);
  if (target) {
    target.value = value ?? "";
  }
}

function populateConfigForm(payload) {
  setValue("cfg-market-default", payload?.market_data?.default_provider || "");
  setValue("cfg-fundamentals-default", payload?.fundamentals?.default_provider || "");
  setValue("cfg-dark-pool-default", payload?.dark_pool?.default_provider || "");
  setValue("cfg-options-default", payload?.options_data?.default_provider || "");
  setValue("cfg-market-local-path", payload?.market_data?.providers?.local_file?.base_path || "");
  setValue("cfg-fundamentals-local-path", payload?.fundamentals?.providers?.local_file?.base_path || "");
  setValue("cfg-dark-pool-local-path", payload?.dark_pool?.providers?.local_file?.base_path || "");
  setValue("cfg-options-local-path", payload?.options_data?.providers?.local_file?.base_path || "");
}

function mergeFormIntoPayload(payload) {
  const next = JSON.parse(JSON.stringify(payload));
  next.market_data = next.market_data || {};
  next.fundamentals = next.fundamentals || {};
  next.dark_pool = next.dark_pool || {};
  next.options_data = next.options_data || {};
  next.market_data.providers = next.market_data.providers || {};
  next.fundamentals.providers = next.fundamentals.providers || {};
  next.dark_pool.providers = next.dark_pool.providers || {};
  next.options_data.providers = next.options_data.providers || {};
  next.market_data.providers.local_file = next.market_data.providers.local_file || {};
  next.fundamentals.providers.local_file = next.fundamentals.providers.local_file || {};
  next.dark_pool.providers.local_file = next.dark_pool.providers.local_file || {};
  next.options_data.providers.local_file = next.options_data.providers.local_file || {};

  next.market_data.default_provider = document.querySelector("#cfg-market-default").value.trim();
  next.fundamentals.default_provider = document.querySelector("#cfg-fundamentals-default").value.trim();
  next.dark_pool.default_provider = document.querySelector("#cfg-dark-pool-default").value.trim();
  next.options_data.default_provider = document.querySelector("#cfg-options-default").value.trim();
  next.market_data.providers.local_file.base_path = document.querySelector("#cfg-market-local-path").value.trim();
  next.fundamentals.providers.local_file.base_path = document.querySelector("#cfg-fundamentals-local-path").value.trim();
  next.dark_pool.providers.local_file.base_path = document.querySelector("#cfg-dark-pool-local-path").value.trim();
  next.options_data.providers.local_file.base_path = document.querySelector("#cfg-options-local-path").value.trim();
  return next;
}

function normalizeSnapshotCandidates(snapshot) {
  return (snapshot?.data_source_runs || [])
    .filter((item) => item?.config_candidate?.provider_name)
    .slice()
    .reverse();
}

function normalizeTerminalCandidates(snapshot) {
  return (snapshot?.terminal_integration_runs || [])
    .filter((item) => item?.config_candidate?.terminal_name)
    .slice()
    .reverse();
}

function renderTerminalHealth(snapshot) {
  const runs = snapshot?.terminal_integration_runs || [];
  if (!runs.length) {
    renderList("config-terminal-health-list", [], "当前还没有终端接入健康摘要。");
    return;
  }
  const latest = runs[runs.length - 1] || {};
  const test = latest.terminal_test || {};
  const runtime = latest.terminal_runtime_summary || {};
  const checks = test.checks || [];
  const passed = checks.filter((item) => item.status === "pass").length;
  renderList(
    "config-terminal-health-list",
    [
      `latest_run / ${latest.run_id || "unknown"} / ${latest.terminal_name || "unknown"} / ${latest.terminal_type || "unknown"}`,
      `runtime / ${runtime.status || "unknown"} / ${runtime.note || "无"}`,
      `readiness / ${latest.integration_readiness_summary?.status || "unknown"} / endpoints=${latest.integration_readiness_summary?.endpoint_count || 0}/${latest.integration_readiness_summary?.required_endpoint_count || 0}`,
      `docs / ${latest.docs_context?.docs_fetch_ok ? "ok" : "fail"} / ready=${latest.validation?.ready_for_programmer_agent ? "yes" : "no"}`,
      `test / ${test.status || "not_tested"} / passed=${passed}/${checks.length || 0}`,
      `summary / ${test.summary || "终端方案已生成，但还没有执行 smoke test。"}`,
      `repair / ${test.repair_summary?.primary_route || "none"} / ${test.repair_summary?.priority || "none"}`,
      `module / ${latest.target_module || "unknown"}`,
      `config_hint / ${runtime.next_action || (test.status === "ok" ? "当前终端方案基础契约正常，可继续挂入配置或写入真实文件。" : (test.repair_summary?.actions?.[0] || "先检查 order/cancel/status/positions/balances endpoint 再落配置。"))}`,
    ],
    "当前还没有终端接入健康摘要。"
  );
}

function renderDataHealth(snapshot) {
  const intelligenceRuns = snapshot?.intelligence_runs || [];
  const financialsRuns = snapshot?.financials_runs || [];
  const darkPoolRuns = snapshot?.dark_pool_runs || [];
  const optionsRuns = snapshot?.options_runs || [];
  const latestIntelligence = intelligenceRuns[intelligenceRuns.length - 1];
  const latestFinancials = financialsRuns[financialsRuns.length - 1];
  const latestDarkPool = darkPoolRuns[darkPoolRuns.length - 1];
  const latestOptions = optionsRuns[optionsRuns.length - 1];
  renderList(
    "config-data-health-list",
    [
      `intelligence / ${latestIntelligence?.timestamp || "none"} / ${latestIntelligence?.query || "none"}`,
      `financials / ${latestFinancials?.timestamp || "none"} / ${latestFinancials?.symbol || "none"} / ${latestFinancials?.provider || "none"}`,
      `dark_pool / ${latestDarkPool?.timestamp || "none"} / ${latestDarkPool?.symbol || "none"} / ${latestDarkPool?.provider || "none"}`,
      `options / ${latestOptions?.timestamp || "none"} / ${latestOptions?.symbol || "none"} / ${latestOptions?.provider || "none"}`,
      `run_counts / intelligence=${intelligenceRuns.length} / financials=${financialsRuns.length} / dark_pool=${darkPoolRuns.length} / options=${optionsRuns.length}`,
      `health / ${intelligenceRuns.length || financialsRuns.length || darkPoolRuns.length || optionsRuns.length ? "active" : "fragile"} / 数据查询层建议优先检查最近 provider、时间戳和本地路径是否还有效。`,
    ],
    "当前还没有数据更新健康摘要。"
  );
}

function renderTerminalCandidates(snapshot) {
  const target = document.querySelector("#config-terminal-candidates");
  if (!target) return;
  const candidates = normalizeTerminalCandidates(snapshot);
  if (!candidates.length) {
    target.innerHTML = `
      <article class="candidate-card">
        <strong>当前还没有终端候选项。</strong>
        <p>请先到交易终端接入页生成至少一个终端方案。</p>
      </article>
    `;
    return;
  }
  target.innerHTML = candidates
    .map((item) => {
      const applyStatus = item.programmer_apply?.status || "not_applied";
      const testStatus = item.terminal_test?.status || "not_tested";
      return `
        <article class="candidate-card">
          <p class="eyebrow">${item.terminal_type}</p>
          <h3>${item.terminal_name}</h3>
          <p>${item.target_module}</p>
          <p>Smoke Test / ${testStatus}</p>
          <p>Programmer Agent / ${applyStatus}</p>
          <div class="button-row">
            <button type="button" data-terminal-action="merge" data-run-id="${item.run_id}">挂入终端配置</button>
            <button type="button" data-terminal-action="merge-default" data-run-id="${item.run_id}">挂入并设为默认终端</button>
            <button type="button" data-terminal-action="merge-default-test" data-run-id="${item.run_id}">设为默认并立即测试</button>
          </div>
          <pre class="code-block">${JSON.stringify(item.config_candidate, null, 2)}</pre>
        </article>
      `;
    })
    .join("");
}

function renderGeneratedCandidates(snapshot) {
  const target = document.querySelector("#config-generated-candidates");
  if (!target) return;
  const candidates = normalizeSnapshotCandidates(snapshot);
  if (!candidates.length) {
    target.innerHTML = `
      <article class="candidate-card">
        <strong>当前还没有候选项。</strong>
        <p>请先到数据源扩充页生成至少一个适配器方案。</p>
      </article>
    `;
    return;
  }
  target.innerHTML = candidates
    .map((item) => {
      const applyStatus = item.programmer_apply?.status || "not_applied";
      return `
        <article class="candidate-card">
          <p class="eyebrow">${item.category}</p>
          <h3>${item.provider_name}</h3>
          <p>${item.target_module}</p>
          <p>Programmer Agent / ${applyStatus}</p>
          <div class="button-row">
            <button type="button" data-candidate-action="merge" data-run-id="${item.run_id}">挂入配置</button>
            <button type="button" data-candidate-action="merge-default" data-run-id="${item.run_id}">挂入并设为默认</button>
          </div>
          <pre class="code-block">${JSON.stringify(item.config_candidate, null, 2)}</pre>
        </article>
      `;
    })
    .join("");
}

function applyCandidatePayload(payload, candidate, setDefaultProvider) {
  const next = JSON.parse(JSON.stringify(payload));
  const category = candidate.category;
  const providerName = candidate.provider_name;
  next[category] = next[category] || {};
  next[category].providers = next[category].providers || {};
  next[category].enabled_providers = next[category].enabled_providers || [];
  next.generated_sources = next.generated_sources || {};
  next.generated_sources.providers = next.generated_sources.providers || {};

  next[category].providers[providerName] = {
    ...(next[category].providers[providerName] || {}),
    ...(candidate.provider_config || {}),
  };
  if (!next[category].enabled_providers.includes(providerName)) {
    next[category].enabled_providers.push(providerName);
  }
  if (setDefaultProvider) {
    next[category].default_provider = providerName;
  }
  if (candidate.generated_sources?.providers?.[providerName]) {
    next.generated_sources.providers[providerName] = {
      ...(next.generated_sources.providers[providerName] || {}),
      ...candidate.generated_sources.providers[providerName],
    };
  }
  return next;
}

function applyTerminalCandidatePayload(payload, candidate, setDefaultTerminal) {
  const next = JSON.parse(JSON.stringify(payload));
  const terminalName = candidate.terminal_name;
  next.generated_terminals = next.generated_terminals || {};
  next.generated_terminals.providers = next.generated_terminals.providers || {};
  next.terminal_integration = next.terminal_integration || {};
  next.terminal_integration.providers = next.terminal_integration.providers || {};

  next.generated_terminals.providers[terminalName] = {
    ...(next.generated_terminals.providers[terminalName] || {}),
    ...(candidate.generated_terminals?.providers?.[terminalName] || {}),
  };
  next.terminal_integration.providers[terminalName] = {
    ...(next.terminal_integration.providers[terminalName] || {}),
    ...(candidate.provider_config || {}),
  };
  if (setDefaultTerminal) {
    next.terminal_integration.default_terminal = terminalName;
  }
  return next;
}

function currentEditorPayload() {
  const raw = document.querySelector("#config-editor").value;
  return JSON.parse(raw);
}

async function loadConfigPage() {
  renderShell("configuration");
  try {
    let snapshot = loadStoredSnapshot();
    if (snapshot?.session_id) {
      try {
        snapshot = await refreshSnapshot();
      } catch (error) {
        snapshot = loadStoredSnapshot();
      }
    }
    const payload = await apiRequest("/api/config");
    document.querySelector("#config-editor").value = JSON.stringify(payload.payload, null, 2);
    populateConfigForm(payload.payload);
    renderValidation(payload.validation);
    renderGeneratedCandidates(snapshot);
    renderTerminalHealth(snapshot);
    renderDataHealth(snapshot);
    renderTerminalCandidates(snapshot);
    setText("config-note", "当前配置已加载。保存后会自动执行有效性检测。");
  } catch (error) {
    setText("config-note", `配置加载失败：${error.message}`);
  }
}

function renderValidation(validation) {
  if (!validation) {
    renderList("config-validation-summary", [], "等待配置测试。");
    renderList("config-validation-checks", [], "等待配置测试。");
    renderList("config-fix-routing-list", [], "等待配置测试结果。");
    return;
  }
  renderList(
    "config-validation-summary",
    [
      `status / ${validation.status}`,
      `config_path / ${validation.config_path}`,
      `ok / ${validation.summary?.ok ?? 0}`,
      `warnings / ${validation.summary?.warnings ?? 0}`,
      `errors / ${validation.summary?.errors ?? 0}`,
      `restart_required / ${validation.restart_required ? "yes" : "no"}`,
    ],
    "无验证摘要。"
  );
  renderList(
    "config-validation-checks",
    (validation.checks || []).map(
      (item) => `${item.status.toUpperCase()} / ${item.name} / ${item.detail} / ${item.recommendation}`
    ),
    "无验证明细。"
  );
  renderFixRouting(validation);
}

function renderFixRouting(validation) {
  const checks = validation?.checks || [];
  const errors = checks.filter((item) => item.status === "error");
  const warnings = checks.filter((item) => item.status === "warning");
  const lines = [];
  if (!checks.length) {
    renderList("config-fix-routing-list", [], "等待配置测试结果。");
    return;
  }
  if (errors.some((item) => String(item.name || "").includes("llm."))) {
    lines.push("检测到 LLM 配置问题，优先跳到系统健康或策略页检查模型与运行状态。");
  }
  if (errors.some((item) => String(item.name || "").includes("programmer_agent"))) {
    lines.push("检测到 Programmer Agent 配置问题，优先修正 repo_path 或运行环境。");
  }
  if (checks.some((item) => String(item.name || "").includes("local_file"))) {
    lines.push("检测到本地文件路径相关问题，优先回到 Provider 配置区修正本地目录。");
  }
  if (errors.some((item) => String(item.name || "").includes("default_provider"))) {
    lines.push("默认 Provider 未启用或未定义，优先修正 Provider 默认值和 enabled 列表。");
  }
  if (!lines.length) {
    lines.push(`当前配置状态为 ${validation.status}，暂无强制跳转建议，可继续在当前页修正。`);
  }
  lines.push(`errors=${errors.length} / warnings=${warnings.length} / restart_required=${validation.restart_required ? "yes" : "no"}`);
  renderList("config-fix-routing-list", lines, "等待配置测试结果。");
}

function jumpFromConfig(targetPage, focusTarget = "", focusKey = STRATEGY_FOCUS_KEY) {
  if (focusTarget) {
    window.localStorage.setItem(focusKey, focusTarget);
  }
  window.location.href = targetPage;
}

function parseEditorPayload() {
  const raw = document.querySelector("#config-editor").value;
  try {
    return mergeFormIntoPayload(JSON.parse(raw));
  } catch (error) {
    throw new Error(`配置 JSON 解析失败：${error.message}`);
  }
}

async function saveConfig() {
  try {
    const payload = parseEditorPayload();
    const result = await apiRequest("/api/config", {
      method: "POST",
      body: JSON.stringify({ payload }),
    });
    document.querySelector("#config-editor").value = JSON.stringify(result.payload, null, 2);
    populateConfigForm(result.payload);
    renderValidation(result.validation);
    setText("config-note", `配置已保存并完成测试。结果：${result.validation.status}`);
  } catch (error) {
    setText("config-note", `保存配置失败：${error.message}`);
  }
}

async function testConfigOnly() {
  try {
    const payload = parseEditorPayload();
    const result = await apiRequest("/api/config/test", {
      method: "POST",
      body: JSON.stringify({ payload }),
    });
    renderValidation(result.validation);
    setText("config-note", `配置测试完成。结果：${result.validation.status}`);
  } catch (error) {
    setText("config-note", `测试配置失败：${error.message}`);
  }
}

async function testSingleConfigItem(family, provider) {
  try {
    const payload = parseEditorPayload();
    const result = await apiRequest("/api/config/test-item", {
      method: "POST",
      body: JSON.stringify({ payload, family, provider }),
    });
    renderList(
      "config-single-test-results",
      (result.validation?.checks || []).map(
        (item) => `${item.status.toUpperCase()} / ${item.name} / ${item.detail} / ${item.recommendation}`
      ),
      "单项测试没有返回结果。"
    );
    setText("config-note", `单项测试完成：${family}${provider ? ` / ${provider}` : ""} / ${result.validation.status}`);
  } catch (error) {
    setText("config-note", `单项测试失败：${error.message}`);
  }
}

function applyGeneratedCandidate(runId, setDefaultProvider) {
  try {
    const snapshot = loadStoredSnapshot();
    const run = (snapshot?.data_source_runs || []).find((item) => item.run_id === runId);
    if (!run?.config_candidate) {
      throw new Error("未找到可应用的数据源候选项。");
    }
    const nextPayload = applyCandidatePayload(currentEditorPayload(), run.config_candidate, setDefaultProvider);
    document.querySelector("#config-editor").value = JSON.stringify(nextPayload, null, 2);
    populateConfigForm(nextPayload);
    setText(
      "config-note",
      setDefaultProvider
        ? `已挂入 ${run.provider_name} 并设为 ${run.category} 默认 Provider。`
        : `已将 ${run.provider_name} 挂入配置候选区。`
    );
  } catch (error) {
    setText("config-note", `应用候选配置失败：${error.message}`);
  }
}

async function applyTerminalCandidate(runId, setDefaultTerminal, testNow = false) {
  try {
    const snapshot = loadStoredSnapshot();
    const run = (snapshot?.terminal_integration_runs || []).find((item) => item.run_id === runId);
    if (!run?.config_candidate) {
      throw new Error("未找到可应用的终端候选项。");
    }
    const nextPayload = applyTerminalCandidatePayload(currentEditorPayload(), run.config_candidate, setDefaultTerminal);
    document.querySelector("#config-editor").value = JSON.stringify(nextPayload, null, 2);
    populateConfigForm(nextPayload);
    if (testNow) {
      const saved = await apiRequest("/api/config", {
        method: "POST",
        body: JSON.stringify({ payload: nextPayload }),
      });
      renderValidation(saved.validation);
      if (!snapshot?.session_id) {
        throw new Error("当前没有活动会话，无法执行终端测试。");
      }
      const tested = await apiRequest(`/api/sessions/${snapshot.session_id}/terminal/test`, {
        method: "POST",
        body: JSON.stringify({ run_id: runId }),
      });
      storeSnapshot(tested);
      renderTerminalHealth(tested);
      renderTerminalCandidates(tested);
      setText("config-note", `已挂入 ${run.terminal_name}、设为默认终端，并完成 smoke test：${tested.terminal_integration_runs?.slice(-1)[0]?.terminal_test?.status || "unknown"}`);
      return;
    }
    setText(
      "config-note",
      setDefaultTerminal
        ? `已挂入 ${run.terminal_name} 并设为默认终端。`
        : `已将 ${run.terminal_name} 挂入终端配置候选区。`
    );
  } catch (error) {
    setText("config-note", `应用终端候选失败：${error.message}`);
  }
}

document.querySelector("#reload-config")?.addEventListener("click", loadConfigPage);
document.querySelector("#save-config")?.addEventListener("click", saveConfig);
document.querySelector("#test-config")?.addEventListener("click", testConfigOnly);
document.querySelector("#test-sec-provider")?.addEventListener("click", () => testSingleConfigItem("fundamentals", "sec"));
document.querySelector("#test-finra-provider")?.addEventListener("click", () => testSingleConfigItem("dark_pool", "finra"));
document.querySelector("#test-yahoo-options-provider")?.addEventListener("click", () => testSingleConfigItem("options_data", "yahoo_options"));
document.querySelector("#jump-config-to-providers")?.addEventListener("click", () => jumpFromConfig("./configuration.html"));
document.querySelector("#jump-config-to-strategy")?.addEventListener("click", () => jumpFromConfig("./strategy.html", "#strategy-repair-route-list"));
document.querySelector("#jump-config-to-health")?.addEventListener("click", () => jumpFromConfig("./system-health.html"));
document.querySelector("#jump-config-to-terminal")?.addEventListener("click", () => jumpFromConfig("./trading-terminal-integration.html", "#terminal-repair-summary", TERMINAL_FOCUS_KEY));
document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const action = target.dataset.candidateAction;
  const runId = target.dataset.runId;
  if (action && runId) {
    applyGeneratedCandidate(runId, action === "merge-default");
    return;
  }
  const terminalAction = target.dataset.terminalAction;
  const terminalRunId = target.dataset.runId;
  if (!terminalAction || !terminalRunId) return;
  applyTerminalCandidate(
    terminalRunId,
    terminalAction === "merge-default" || terminalAction === "merge-default-test",
    terminalAction === "merge-default-test"
  );
});

loadConfigPage();
