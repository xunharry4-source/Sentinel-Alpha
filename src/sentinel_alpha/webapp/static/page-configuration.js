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
    setText("config-note", "当前配置已加载。保存后会自动执行有效性检测。");
  } catch (error) {
    setText("config-note", `配置加载失败：${error.message}`);
  }
}

function renderValidation(validation) {
  if (!validation) {
    renderList("config-validation-summary", [], "等待配置测试。");
    renderList("config-validation-checks", [], "等待配置测试。");
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

document.querySelector("#reload-config")?.addEventListener("click", loadConfigPage);
document.querySelector("#save-config")?.addEventListener("click", saveConfig);
document.querySelector("#test-config")?.addEventListener("click", testConfigOnly);
document.querySelector("#test-sec-provider")?.addEventListener("click", () => testSingleConfigItem("fundamentals", "sec"));
document.querySelector("#test-finra-provider")?.addEventListener("click", () => testSingleConfigItem("dark_pool", "finra"));
document.querySelector("#test-yahoo-options-provider")?.addEventListener("click", () => testSingleConfigItem("options_data", "yahoo_options"));
document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const action = target.dataset.candidateAction;
  const runId = target.dataset.runId;
  if (!action || !runId) return;
  applyGeneratedCandidate(runId, action === "merge-default");
});

loadConfigPage();
