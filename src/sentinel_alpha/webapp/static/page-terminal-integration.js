const TERMINAL_FOCUS_KEY = "sentinel-alpha:terminal-focus-target";

function focusTerminalPanel(selector) {
  const panel = document.querySelector(selector);
  if (!panel) return;
  panel.classList.remove("panel-focus");
  void panel.offsetWidth;
  panel.classList.add("panel-focus");
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
  window.setTimeout(() => panel.classList.remove("panel-focus"), 1800);
}

function terminalRuns(snapshot) {
  return snapshot?.terminal_integration_runs || [];
}

function parseTerminalFieldMap() {
  const raw = document.querySelector("#terminal-response-field-map")?.value?.trim() || "";
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`返回字段映射 JSON 解析失败：${error.message}`);
  }
}

function selectedTerminalRun(snapshot) {
  const runs = terminalRuns(snapshot);
  if (!runs.length) return null;
  const selectedRunId = document.querySelector("#terminal-run-select")?.value;
  return runs.find((item) => item.run_id === selectedRunId) || runs[runs.length - 1];
}

function renderTerminalSelect(snapshot) {
  const target = document.querySelector("#terminal-run-select");
  if (!target) return;
  const runs = terminalRuns(snapshot);
  if (!runs.length) {
    target.innerHTML = `<option value="">暂无生成记录</option>`;
    return;
  }
  target.innerHTML = runs
    .slice()
    .reverse()
    .map((item) => `<option value="${item.run_id}">${item.run_id} / ${item.terminal_name} / ${item.terminal_type} / ${item.timestamp}</option>`)
    .join("");
}

function renderTerminalIntegrationPage(snapshot) {
  renderShell("trading-terminal-integration");
  renderTerminalSelect(snapshot);
  const run = selectedTerminalRun(snapshot);
  if (!run) {
    renderList("terminal-validation", [], "等待生成终端接入方案。");
    renderList("terminal-readiness-summary", [], "等待终端联通前置检查。");
    renderList("terminal-docs-context", [], "等待抓取官方文档上下文。");
    renderList("terminal-test-results", [], "等待执行终端 smoke test。");
    renderList("terminal-repair-summary", [], "等待终端 smoke test 修复建议。");
    document.querySelector("#terminal-module-code").textContent = "等待生成终端适配器代码。";
    document.querySelector("#terminal-test-code").textContent = "等待生成终端测试代码。";
    document.querySelector("#terminal-config-candidate").textContent = "等待生成配置候选。";
    document.querySelector("#terminal-test-calls").textContent = "等待终端测试调用记录。";
    document.querySelector("#terminal-diff").textContent = "等待 Programmer Agent 运行结果。";
  } else {
    renderList(
      "terminal-validation",
      [
        `run_id / ${run.run_id}`,
        `terminal / ${run.terminal_name}`,
        `type / ${run.terminal_type}`,
        `target_module / ${run.target_module}`,
        `target_test / ${run.target_test}`,
        `module_syntax_ok / ${run.validation?.module_syntax_ok ? "yes" : "no"}`,
        `test_syntax_ok / ${run.validation?.test_syntax_ok ? "yes" : "no"}`,
        `docs_fetch_ok / ${run.validation?.docs_fetch_ok ? "yes" : "no"}`,
        `ready_for_programmer_agent / ${run.validation?.ready_for_programmer_agent ? "yes" : "no"}`,
      ],
      "等待生成终端接入方案。"
    );
    renderList(
      "terminal-readiness-summary",
      run.integration_readiness_summary
        ? [
            `runtime / ${run.terminal_runtime_summary?.status || "unknown"} / ${run.terminal_runtime_summary?.note || "无"}`,
            `status / ${run.integration_readiness_summary.status || "unknown"}`,
            `base_url_ok / ${run.integration_readiness_summary.base_url_ok ? "yes" : "no"}`,
            `docs_fetch_ok / ${run.integration_readiness_summary.docs_fetch_ok ? "yes" : "no"}`,
            `auth / ${run.integration_readiness_summary.auth_style || "unknown"} / ready=${run.integration_readiness_summary.auth_ready ? "yes" : "no"}`,
            `endpoints / ${run.integration_readiness_summary.endpoint_count || 0}/${run.integration_readiness_summary.required_endpoint_count || 0}`,
            `missing / ${(run.integration_readiness_summary.missing_endpoints || []).join(", ") || "none"}`,
            `field_map / ${Object.entries(run.config_candidate?.provider_config?.response_field_map || {}).map(([key, value]) => `${key}=${value}`).join(", ") || "none"}`,
            `next / ${run.terminal_runtime_summary?.next_action || "none"}`,
            ...((run.integration_readiness_summary.actions || []).map((item) => `action / ${item}`)),
          ]
        : [],
      "等待终端联通前置检查。"
    );
    renderList(
      "terminal-docs-context",
      [
        `official_docs_url / ${run.official_docs_url}`,
        `docs_search_url / ${run.docs_search_url || "n/a"}`,
        `docs_fetch_ok / ${run.docs_context?.docs_fetch_ok ? "yes" : "no"}`,
        `docs_excerpt / ${run.docs_context?.docs_excerpt || "none"}`,
        `search_fetch_ok / ${run.docs_context?.search_fetch_ok ? "yes" : "no"}`,
        `search_excerpt / ${run.docs_context?.search_excerpt || "none"}`,
      ],
      "等待抓取官方文档上下文。"
    );
    document.querySelector("#terminal-module-code").textContent = run.generated_module_code || "";
    document.querySelector("#terminal-test-code").textContent = run.generated_test_code || "";
    document.querySelector("#terminal-config-candidate").textContent = JSON.stringify(run.config_candidate || {}, null, 2);
    renderList(
      "terminal-test-results",
      run.terminal_test
        ? [
            `status / ${run.terminal_test.status || "unknown"}`,
            `summary / ${run.terminal_test.summary || "无"}`,
            ...((run.terminal_test.checks || []).map((item) => `${item.name} / ${item.status} / ${item.detail || "无"}`)),
          ]
        : [],
      "等待执行终端 smoke test。"
    );
    renderList(
      "terminal-repair-summary",
      run.terminal_test?.repair_summary
        ? [
            `status / ${run.terminal_test.repair_summary.status || "unknown"}`,
            `primary_route / ${run.terminal_test.repair_summary.primary_route || "none"}`,
            `priority / ${run.terminal_test.repair_summary.priority || "none"}`,
            `note / ${run.terminal_test.repair_summary.note || "none"}`,
            ...((run.terminal_test.repair_summary.routes || []).map(
              (item) => `${item.check} / ${item.route} / ${item.priority} / ${item.action}`
            )),
          ]
        : [],
      "等待终端 smoke test 修复建议。"
    );
    document.querySelector("#terminal-test-calls").textContent = run.terminal_test
      ? JSON.stringify(run.terminal_test.calls || [], null, 2)
      : "等待终端测试调用记录。";
    document.querySelector("#terminal-diff").textContent = run.programmer_apply?.diff || "等待 Programmer Agent 运行结果。";
  }

  renderList(
    "terminal-run-list",
    terminalRuns(snapshot)
      .slice()
      .reverse()
      .map((item) => {
        const applyStatus = item.programmer_apply?.status || "not_applied";
        const testStatus = item.terminal_test?.status || "not_tested";
        const repairRoute = item.terminal_test?.repair_summary?.primary_route || "none";
        const readiness = item.integration_readiness_summary?.status || "unknown";
        return `${item.timestamp} / ${item.run_id} / ${item.terminal_name} / ${item.terminal_type} / readiness=${readiness} / docs=${item.docs_context?.docs_fetch_ok ? "ok" : "fail"} / test=${testStatus} / repair=${repairRoute} / apply=${applyStatus}`;
      }),
    "当前还没有交易终端接入历史。"
  );
}

async function requireTerminalSession() {
  let snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("terminal-note", "请先创建会话。");
    return null;
  }
  try {
    snapshot = await refreshSnapshot();
  } catch (error) {
    snapshot = loadStoredSnapshot();
  }
  return snapshot;
}

async function generateTerminalRun() {
  const snapshot = await requireTerminalSession();
  if (!snapshot) return;
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/terminal/expand`, {
      method: "POST",
      body: JSON.stringify({
        terminal_name: document.querySelector("#terminal-name").value,
        terminal_type: document.querySelector("#terminal-type").value,
        official_docs_url: document.querySelector("#terminal-docs-url").value,
        docs_search_url: document.querySelector("#terminal-search-url").value || null,
        api_base_url: document.querySelector("#terminal-base-url").value,
        api_key_env: document.querySelector("#terminal-api-key-env").value || null,
        auth_style: document.querySelector("#terminal-auth-style").value,
        order_endpoint: document.querySelector("#terminal-order-endpoint").value,
        cancel_endpoint: document.querySelector("#terminal-cancel-endpoint").value,
        order_status_endpoint: document.querySelector("#terminal-order-status-endpoint").value,
        positions_endpoint: document.querySelector("#terminal-positions-endpoint").value,
        balances_endpoint: document.querySelector("#terminal-balances-endpoint").value,
        docs_summary: document.querySelector("#terminal-docs-summary").value,
        user_notes: document.querySelector("#terminal-user-notes").value || null,
        response_field_map: parseTerminalFieldMap(),
      }),
    });
    storeSnapshot(latest);
    renderTerminalIntegrationPage(latest);
    setText("terminal-note", "终端接入方案已生成。你现在可以直接交给 Programmer Agent 落文件。");
  } catch (error) {
    setText("terminal-note", `生成终端接入方案失败：${error.message}`);
  }
}

async function applyTerminalRun() {
  const snapshot = await requireTerminalSession();
  if (!snapshot) return;
  const run = selectedTerminalRun(snapshot);
  if (!run) {
    setText("terminal-note", "当前没有可应用的终端接入结果。");
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/terminal/apply`, {
      method: "POST",
      body: JSON.stringify({
        run_id: run.run_id,
        commit_changes: true,
      }),
    });
    storeSnapshot(latest);
    renderTerminalIntegrationPage(latest);
    const appliedRun = (latest.terminal_integration_runs || []).find((item) => item.run_id === run.run_id);
    const status = appliedRun?.programmer_apply?.status || "unknown";
    setText("terminal-note", `Programmer Agent 已处理该终端接入结果。状态：${status}`);
  } catch (error) {
    setText("terminal-note", `Programmer Agent 落文件失败：${error.message}`);
  }
}

async function testTerminalRun() {
  const snapshot = await requireTerminalSession();
  if (!snapshot) return;
  const run = selectedTerminalRun(snapshot);
  if (!run) {
    setText("terminal-note", "当前没有可测试的终端接入结果。");
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/terminal/test`, {
      method: "POST",
      body: JSON.stringify({
        run_id: run.run_id,
      }),
    });
    storeSnapshot(latest);
    renderTerminalIntegrationPage(latest);
    const testedRun = (latest.terminal_integration_runs || []).find((item) => item.run_id === run.run_id);
    setText("terminal-note", `终端 smoke test 已完成。状态：${testedRun?.terminal_test?.status || "unknown"}`);
  } catch (error) {
    setText("terminal-note", `终端 smoke test 失败：${error.message}`);
  }
}

function fillTerminalRepairNotes() {
  const snapshot = loadStoredSnapshot();
  const run = selectedTerminalRun(snapshot || {});
  if (!run?.terminal_test?.repair_summary) {
    setText("terminal-note", "当前没有可回填的终端修复说明。");
    return;
  }
  const repair = run.terminal_test.repair_summary;
  const lines = [
    `Primary route: ${repair.primary_route || "none"}`,
    `Priority: ${repair.priority || "none"}`,
    `Note: ${repair.note || "none"}`,
    ...(repair.actions || []).map((item) => `Action: ${item}`),
  ];
  const target = document.querySelector("#terminal-user-notes");
  if (target) {
    target.value = lines.join("\n");
  }
  focusTerminalPanel("#terminal-user-notes");
  setText("terminal-note", "已将终端修复说明回填到“用户补充信息”。");
}

document.querySelector("#generate-terminal")?.addEventListener("click", generateTerminalRun);
document.querySelector("#test-terminal")?.addEventListener("click", testTerminalRun);
document.querySelector("#apply-terminal")?.addEventListener("click", applyTerminalRun);
document.querySelector("#terminal-fill-repair-notes")?.addEventListener("click", fillTerminalRepairNotes);
document.querySelector("#terminal-run-select")?.addEventListener("change", () => renderTerminalIntegrationPage(loadStoredSnapshot()));

(async function bootstrapTerminalIntegrationPage() {
  const snapshot = await requireTerminalSession();
  renderTerminalIntegrationPage(snapshot || loadStoredSnapshot());
  const focusTarget = window.localStorage.getItem(TERMINAL_FOCUS_KEY);
  if (focusTarget) {
    focusTerminalPanel(focusTarget);
    window.localStorage.removeItem(TERMINAL_FOCUS_KEY);
  }
})();
