function dataSourceRuns(snapshot) {
  return snapshot?.data_source_runs || [];
}

function selectedDataSourceRun(snapshot) {
  const runs = dataSourceRuns(snapshot);
  if (!runs.length) return null;
  const selectedRunId = document.querySelector("#ds-run-select")?.value;
  return runs.find((item) => item.run_id === selectedRunId) || runs[runs.length - 1];
}

function renderRunSelect(snapshot) {
  const target = document.querySelector("#ds-run-select");
  if (!target) return;
  const runs = dataSourceRuns(snapshot);
  if (!runs.length) {
    target.innerHTML = `<option value="">暂无生成记录</option>`;
    return;
  }
  target.innerHTML = runs
    .slice()
    .reverse()
    .map(
      (item) =>
        `<option value="${item.run_id}">${item.run_id} / ${item.provider_name} / ${item.category} / ${item.timestamp}</option>`
    )
    .join("");
}

function renderDataSourceExpansionPage(snapshot) {
  renderShell("data-source-expansion");
  renderRunSelect(snapshot);
  const run = selectedDataSourceRun(snapshot);
  if (!run) {
    renderList("data-source-validation", [], "等待生成扩充方案。");
    renderList("data-source-apply-summary", [], "当前还没有执行落文件。");
    document.querySelector("#data-source-module-code").textContent = "等待生成模块代码。";
    document.querySelector("#data-source-test-code").textContent = "等待生成测试代码。";
    document.querySelector("#data-source-config-candidate").textContent = "等待生成配置候选。";
    document.querySelector("#data-source-diff").textContent = "等待 Programmer Agent 运行结果。";
  } else {
    renderList(
      "data-source-validation",
      [
        `run_id / ${run.run_id}`,
        `provider / ${run.provider_name}`,
        `category / ${run.category}`,
        `docs_url / ${run.docs_url || "none"}`,
        `target_module / ${run.target_module}`,
        `target_test / ${run.target_test}`,
        `module_syntax_ok / ${run.validation?.module_syntax_ok ? "yes" : "no"}`,
        `test_syntax_ok / ${run.validation?.test_syntax_ok ? "yes" : "no"}`,
        `ready_for_programmer_agent / ${run.validation?.ready_for_programmer_agent ? "yes" : "no"}`,
      ],
      "等待生成扩充方案。"
    );
    renderList(
      "data-source-apply-summary",
      run.programmer_apply
        ? [
            `status / ${run.programmer_apply.status}`,
            `commit_hash / ${run.programmer_apply.commit_hash || "none"}`,
            `rollback_commit / ${run.programmer_apply.rollback_commit || "none"}`,
            `changed_files / ${(run.programmer_apply.changed_files || []).join(", ") || "none"}`,
          ]
        : [],
      "当前还没有执行落文件。"
    );
    document.querySelector("#data-source-module-code").textContent = run.generated_module_code || "";
    document.querySelector("#data-source-test-code").textContent = run.generated_test_code || "";
    document.querySelector("#data-source-config-candidate").textContent = JSON.stringify(run.config_candidate || {}, null, 2);
    document.querySelector("#data-source-diff").textContent = run.programmer_apply?.diff || "等待 Programmer Agent 运行结果。";
  }

  renderList(
    "data-source-run-list",
    dataSourceRuns(snapshot)
      .slice()
      .reverse()
      .map((item) => {
        const applyStatus = item.programmer_apply?.status || "not_applied";
        return `${item.timestamp} / ${item.run_id} / ${item.provider_name} / ${item.category} / apply=${applyStatus}`;
      }),
    "当前还没有数据源扩充历史。"
  );
}

async function requireExpansionSession() {
  let snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("data-source-note", "请先创建会话。");
    return null;
  }
  try {
    snapshot = await refreshSnapshot();
  } catch (error) {
    snapshot = loadStoredSnapshot();
  }
  return snapshot;
}

async function generateDataSourceRun() {
  const snapshot = await requireExpansionSession();
  if (!snapshot) return;
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/data-source/expand`, {
      method: "POST",
      body: JSON.stringify({
        provider_name: document.querySelector("#ds-provider-name").value,
        category: document.querySelector("#ds-category").value,
        base_url: document.querySelector("#ds-base-url").value,
        api_key_envs: (document.querySelector("#ds-api-key-env").value || "").split(/[\n,]/).map((item) => item.trim()).filter(Boolean),
        docs_summary: document.querySelector("#ds-docs-summary").value || null,
        docs_url: document.querySelector("#ds-docs-url").value || null,
        sample_endpoint: document.querySelector("#ds-sample-endpoint").value || null,
        auth_style: document.querySelector("#ds-auth-style").value,
        response_format: document.querySelector("#ds-response-format").value,
      }),
    });
    storeSnapshot(latest);
    renderDataSourceExpansionPage(latest);
    setText("data-source-note", "扩充方案已生成。你现在可以直接交给 Programmer Agent 落文件，也可以去配置页挂入候选配置。");
  } catch (error) {
    setText("data-source-note", `生成扩充方案失败：${error.message}`);
  }
}

async function applyDataSourceRun() {
  const snapshot = await requireExpansionSession();
  if (!snapshot) return;
  const run = selectedDataSourceRun(snapshot);
  if (!run) {
    setText("data-source-note", "当前没有可应用的数据源扩充结果。");
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/data-source/apply`, {
      method: "POST",
      body: JSON.stringify({
        run_id: run.run_id,
        commit_changes: true,
      }),
    });
    storeSnapshot(latest);
    renderDataSourceExpansionPage(latest);
    const appliedRun = (latest.data_source_runs || []).find((item) => item.run_id === run.run_id);
    const status = appliedRun?.programmer_apply?.status || "unknown";
    setText("data-source-note", `Programmer Agent 已处理该数据源扩充结果。状态：${status}`);
  } catch (error) {
    setText("data-source-note", `Programmer Agent 落文件失败：${error.message}`);
  }
}

document.querySelector("#generate-data-source")?.addEventListener("click", generateDataSourceRun);
document.querySelector("#apply-data-source")?.addEventListener("click", applyDataSourceRun);
document.querySelector("#ds-run-select")?.addEventListener("change", () => renderDataSourceExpansionPage(loadStoredSnapshot()));

(async function bootstrapDataSourceExpansionPage() {
  const snapshot = await requireExpansionSession();
  renderDataSourceExpansionPage(snapshot || loadStoredSnapshot());
})();
