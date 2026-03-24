const SESSION_STORAGE_KEY = "sentinel-alpha:last-session-snapshot";
const CONFIG_STORAGE_KEY = "sentinel-alpha:web-config";
const GLOBAL_DEBUG_MODE_KEY = "sentinel-alpha:debug-mode";
const GLOBAL_ERROR_STACK_ID = "sa-global-error-stack";
const SESSION_COOKIE_KEY = "sa_session_id";
let saGlobalErrorHooked = false;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function setCookie(name, value, days = 30) {
  try {
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
  } catch (error) {
    // ignore
  }
}

function clearCookie(name) {
  try {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax`;
  } catch (error) {
    // ignore
  }
}

function getCookie(name) {
  try {
    const match = document.cookie.match(new RegExp(`(?:^|; )${name.replace(/[$()*+./?[\\]^{|}-]/g, "\\$&")}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : null;
  } catch (error) {
    return null;
  }
}

function loadStoredSnapshot() {
  try {
    return JSON.parse(window.localStorage.getItem(SESSION_STORAGE_KEY) || "null");
  } catch (error) {
    return null;
  }
}

function loadSnapshotSessionIdFromUrl() {
  try {
    return new URLSearchParams(window.location.search).get("session_id");
  } catch (error) {
    return null;
  }
}

function loadCurrentSnapshot() {
  const stored = loadStoredSnapshot();
  const sessionIdFromUrl = loadSnapshotSessionIdFromUrl();
  if (!sessionIdFromUrl) {
    const cookieSession = getCookie(SESSION_COOKIE_KEY);
    if (cookieSession && !UUID_PATTERN.test(cookieSession)) {
      clearCookie(SESSION_COOKIE_KEY);
      return stored;
    }
    if (cookieSession && stored?.session_id !== cookieSession) {
      return { ...(stored || {}), session_id: cookieSession };
    }
    return stored;
  }
  if (!UUID_PATTERN.test(sessionIdFromUrl)) {
    return stored;
  }
  if (stored?.session_id === sessionIdFromUrl) {
    return stored;
  }
  setCookie(SESSION_COOKIE_KEY, sessionIdFromUrl);
  return { ...(stored || {}), session_id: sessionIdFromUrl };
}

function loadStoredConfig() {
  try {
    return JSON.parse(window.localStorage.getItem(CONFIG_STORAGE_KEY) || "null");
  } catch (error) {
    return null;
  }
}

function storeSnapshot(snapshot) {
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(snapshot));
  if (snapshot?.session_id) {
    setCookie(SESSION_COOKIE_KEY, snapshot.session_id);
  }
}

function storeConfig(config) {
  window.localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(config));
}

function ensureGlobalErrorStack() {
  let stack = document.querySelector(`#${GLOBAL_ERROR_STACK_ID}`);
  if (stack) return stack;
  stack = document.createElement("div");
  stack.id = GLOBAL_ERROR_STACK_ID;
  stack.className = "global-error-stack";
  document.body.appendChild(stack);
  return stack;
}

function showGlobalError(message) {
  if (!message) return;
  const stack = ensureGlobalErrorStack();
  const item = document.createElement("div");
  item.className = "global-error-banner";
  item.textContent = message;
  stack.prepend(item);
  window.setTimeout(() => {
    item.classList.add("global-error-banner-hide");
    window.setTimeout(() => item.remove(), 220);
  }, 6000);
}

window.saReportError = showGlobalError;

function ensureGlobalErrorHooks() {
  if (saGlobalErrorHooked) return;
  saGlobalErrorHooked = true;
  window.addEventListener("error", (event) => {
    const message = event?.error?.message || event?.message;
    if (message) showGlobalError(`页面错误：${message}`);
  });
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event?.reason;
    const message =
      typeof reason === "string"
        ? reason
        : reason?.message || "未处理的异步错误。";
    showGlobalError(`异步错误：${message}`);
  });
}

function resolveConfigPath() {
  return window.location.pathname.includes("/pages/") ? "../config.json" : "./config.json";
}

async function fetchClientConfig() {
  const response = await fetch(resolveConfigPath(), { cache: "no-store" });
  if (!response.ok) {
    throw new Error("frontend config missing");
  }
  const payload = await response.json();
  storeConfig(payload);
  return payload;
}

async function ensureClientConfig(forceRefresh = false) {
  const existing = loadStoredConfig();
  if (existing?.apiBase && !forceRefresh) {
    return existing;
  }
  try {
    return await fetchClientConfig();
  } catch (error) {
    if (existing?.apiBase) {
      return existing;
    }
    throw error;
  }
}

async function apiRequest(path, options = {}) {
  const attempt = async (config) => {
    const response = await fetch(`${config.apiBase}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const payload = await response.json();
        throw new Error(payload?.detail || payload?.message || `API ${response.status}`);
      }
      const detail = await response.text();
      throw new Error(detail || `API ${response.status}`);
    }
    return response.json();
  };

  const config = await ensureClientConfig();
  try {
    return await attempt(config);
  } catch (error) {
    const message = String(error?.message || error || "");
    showGlobalError(`请求失败：${message}`);
    if (!message.includes("Not Found")) {
      throw error;
    }
    const freshConfig = await ensureClientConfig(true);
    if (freshConfig.apiBase === config.apiBase) {
      throw error;
    }
    return attempt(freshConfig);
  }
}

async function refreshSnapshot() {
  const snapshot = loadCurrentSnapshot();
  const sessionId = snapshot?.session_id || loadSnapshotSessionIdFromUrl();
  if (!sessionId) {
    throw new Error("no session");
  }
  try {
    const latest = await apiRequest(`/api/sessions/${sessionId}`);
    storeSnapshot(latest);
    return latest;
  } catch (error) {
    const message = String(error?.message || "");
    if (message.includes("Session not found")) {
      window.localStorage.removeItem(SESSION_STORAGE_KEY);
      clearCookie(SESSION_COOKIE_KEY);
    }
    throw error;
  }
}

async function resolveCurrentSnapshot() {
  const current = loadCurrentSnapshot();
  if (!current?.session_id) {
    return current;
  }
  try {
    return await refreshSnapshot();
  } catch (error) {
    return loadCurrentSnapshot();
  }
}

function renderShell(pageKey) {
  ensureGlobalErrorHooks();
  const snapshot = loadCurrentSnapshot();
  const config = loadStoredConfig();
  const nav = document.querySelector("[data-shell='nav']");
  const summary = document.querySelector("[data-shell='summary']");
  const pages = [
    { key: "home", href: "../index.html", label: "首页" },
    { key: "session", href: "./session.html", label: "会话创建" },
    { key: "simulation", href: "./simulation.html", label: "模拟测试" },
    { key: "report", href: "./report.html", label: "测试报告" },
    { key: "preferences", href: "./preferences.html", label: "交易偏好" },
    { key: "configuration", href: "./configuration.html", label: "配置管理" },
    { key: "data-source-expansion", href: "./data-source-expansion.html", label: "数据源扩充" },
    { key: "trading-terminal-integration", href: "./trading-terminal-integration.html", label: "终端接入" },
    { key: "strategy", href: "./strategy.html", label: "策略训练" },
    { key: "intelligence", href: "./intelligence.html", label: "情报中心" },
    { key: "system-health", href: "./system-health.html", label: "系统健康" },
    { key: "operations", href: "./operations.html", label: "部署监控" },
  ];

  if (nav) {
    nav.innerHTML = pages
      .map((item) => `<a class="shell-link ${item.key === pageKey ? "shell-link-active" : ""}" href="${item.href}">${item.label}</a>`)
      .join("");
  }

  if (summary) {
    if (!snapshot) {
      summary.innerHTML = `
        <div class="panel">
          <p class="eyebrow">Session Summary</p>
          <h3>还没有活动会话</h3>
          <p>请先在 <a href="./session.html">会话创建页</a> 创建测试会话并完成至少一步流程，子页面才会显示当前状态。</p>
        </div>
      `;
      ensureGlobalAgentDebugPanel(pageKey);
      updateGlobalAgentDebugUi(pageKey);
      return;
    }
    summary.innerHTML = `
      <div class="panel shell-summary-panel">
        <div>
          <p class="eyebrow">Current Session</p>
          <h3>${snapshot.user_name}</h3>
        </div>
        <div class="shell-kv-grid">
          <div><span>Session</span><strong>${snapshot.session_id}</strong></div>
          <div><span>Phase</span><strong>${snapshot.phase}</strong></div>
          <div><span>Status</span><strong>${snapshot.status}</strong></div>
          <div><span>API</span><strong>${config?.apiBase || "unknown"}</strong></div>
        </div>
      </div>
    `;
  }
  ensureGlobalAgentDebugPanel(pageKey);
  updateGlobalAgentDebugUi(pageKey);
  if (saIsDebugModeEnabled() && pageKey !== "system-health") {
    void refreshGlobalAgentDebug(pageKey);
  }
}

function renderList(targetId, items, emptyText = "暂无数据。") {
  const target = document.querySelector(`#${targetId}`);
  if (!target) return;
  if (!items || items.length === 0) {
    target.innerHTML = `<li>${emptyText}</li>`;
    return;
  }
  target.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
}

function formatJsonIntoList(targetId, payload, emptyText = "暂无数据。") {
  const target = document.querySelector(`#${targetId}`);
  if (!target) return;
  if (!payload || Object.keys(payload).length === 0) {
    target.innerHTML = `<li>${emptyText}</li>`;
    return;
  }
  target.innerHTML = Object.entries(payload)
    .map(([key, value]) => `<li>${key}: ${typeof value === "object" ? JSON.stringify(value) : value}</li>`)
    .join("");
}

function setText(id, text) {
  const target = document.querySelector(`#${id}`);
  if (target) {
    target.textContent = text;
  }
}



function formatDebugPayload(payload) {
  if (payload === null || typeof payload === "undefined") return "none";
  try {
    const text = JSON.stringify(payload);
    return text.length <= 240 ? text : `${text.slice(0, 240)}...`;
  } catch (error) {
    return String(payload);
  }
}

function saIsDebugModeEnabled() {
  return window.localStorage.getItem(GLOBAL_DEBUG_MODE_KEY) === "1" || new URLSearchParams(window.location.search).get("debug") === "1";
}

function setGlobalDebugMode(enabled) {
  if (enabled) {
    window.localStorage.setItem(GLOBAL_DEBUG_MODE_KEY, "1");
  } else {
    window.localStorage.removeItem(GLOBAL_DEBUG_MODE_KEY);
  }
}

function globalDebugPanelIds(pageKey) {
  return {
    shell: `global-debug-shell-${pageKey}`,
    button: `global-debug-toggle-${pageKey}`,
    grid: `global-debug-grid-${pageKey}`,
    trace: `global-debug-trace-${pageKey}`,
    focus: `global-debug-focus-${pageKey}`,
  };
}

function ensureGlobalAgentDebugPanel(pageKey) {
  if (pageKey === "system-health") return;
  const grid = document.querySelector(".page-grid");
  if (!grid) return;
  const ids = globalDebugPanelIds(pageKey);
  if (document.querySelector(`#${ids.shell}`)) return;
  const article = document.createElement("article");
  article.className = "panel";
  article.innerHTML = `
    <p class="eyebrow">Agent Debug</p>
    <h3>DEBUG Agent 节点</h3>
    <div class="action-buttons secondary compact-actions">
      <button id="${ids.button}">${saIsDebugModeEnabled() ? "关闭 DEBUG 模式" : "开启 DEBUG 模式"}</button>
    </div>
    <div id="${ids.shell}" ${saIsDebugModeEnabled() ? "" : "hidden"}>
      <p class="profiler-note">显示各 Agent 节点、最近执行链和失败焦点，便于快速定位卡点。</p>
      <section class="check-grid" id="${ids.grid}"></section>
      <ul id="${ids.trace}" class="result-list"><li>当前还没有 DEBUG Trace。</li></ul>
      <ul id="${ids.focus}" class="result-list"><li>当前还没有失败焦点。</li></ul>
    </div>
  `;
  grid.appendChild(article);
  document.querySelector(`#${ids.button}`)?.addEventListener("click", async () => {
    const enabled = !saIsDebugModeEnabled();
    setGlobalDebugMode(enabled);
    updateGlobalAgentDebugUi(pageKey);
    if (enabled) {
      await refreshGlobalAgentDebug(pageKey);
    }
  });
}

function updateGlobalAgentDebugUi(pageKey) {
  if (pageKey === "system-health") return;
  const ids = globalDebugPanelIds(pageKey);
  const shell = document.querySelector(`#${ids.shell}`);
  const button = document.querySelector(`#${ids.button}`);
  const enabled = saIsDebugModeEnabled();
  if (shell) shell.hidden = !enabled;
  if (button) button.textContent = enabled ? "关闭 DEBUG 模式" : "开启 DEBUG 模式";
}

function renderGlobalAgentDebug(pageKey, payload) {
  const ids = globalDebugPanelIds(pageKey);
  const grid = document.querySelector(`#${ids.grid}`);
  if (!grid) return;
  const agents = payload?.agents || [];
  const logs = payload?.recent_agent_logs || [];
  if (!agents.length) {
    grid.innerHTML = `<article class="check-card"><strong>当前还没有 Agent DEBUG 节点。</strong></article>`;
    renderList(ids.trace, [], "当前还没有 DEBUG Trace。");
    renderList(ids.focus, [], "当前还没有失败焦点。");
    return;
  }
  const latestByAgent = new Map();
  for (const item of logs) latestByAgent.set(item.agent, item);
  grid.innerHTML = agents.map((item) => {
    const latest = latestByAgent.get(item.agent) || {};
    const status = latest.status || item.status || "idle";
    const chip = status === "ok" ? "success-chip" : status === "warning" || status === "idle" ? "warn-chip" : "danger-chip";
    const card = status === "ok" ? "check-pass" : status === "warning" || status === "idle" ? "check-warning" : "check-fail";
    return `
      <article class="check-card ${card}">
        <div class="check-head">
          <strong>${item.agent || item.name}</strong>
          <span class="status-chip ${chip}">${String(status).toUpperCase()}</span>
        </div>
        <p class="check-summary">${latest.detail || item.detail || item.last_detail || "No detail."}</p>
        <p class="check-label">Node</p><p>${latest.operation || item.last_operation || "idle"}</p>
        <p class="check-label">Last Seen</p><p>${latest.timestamp || item.last_seen || "unknown"}</p>
        <p class="check-label">Errors</p><p>${item.error_count || 0}</p>
        <p class="check-label">Session</p><p>${latest.session_id || "global"}</p>
        <p class="check-label">Request</p><p>${formatDebugPayload(latest.request_payload)}</p>
        <p class="check-label">Response</p><p>${formatDebugPayload(latest.response_payload)}</p>
      </article>
    `;
  }).join("");
  renderList(
    ids.trace,
    logs.slice().reverse().slice(0, 20).map((item) => `${item.timestamp} / ${item.agent} / ${item.status} / ${item.operation} / session=${item.session_id || "global"} / ${item.detail}`),
    "当前还没有 DEBUG Trace。"
  );
  const latestError = logs.slice().reverse().find((item) => item.status === "error");
  if (!latestError) {
    renderList(ids.focus, ["当前没有最新失败焦点，Agent 节点整体可用。"], "当前还没有失败焦点。");
    return;
  }
  const focus = logs.filter((item) => item.session_id === latestError.session_id || item.agent === latestError.agent).slice(-8);
  renderList(
    ids.focus,
    [
      `latest_error / ${latestError.timestamp} / ${latestError.agent} / ${latestError.operation}`,
      `latest_error_detail / ${latestError.detail}`,
      `request / ${formatDebugPayload(latestError.request_payload)}`,
      `response / ${formatDebugPayload(latestError.response_payload)}`,
      ...focus.map((item) => `trace / ${item.timestamp} / ${item.agent} / ${item.status} / ${item.operation} / ${item.detail}`),
    ],
    "当前还没有失败焦点。"
  );
}

async function refreshGlobalAgentDebug(pageKey) {
  if (!saIsDebugModeEnabled() || pageKey === "system-health") return;
  try {
    const payload = await apiRequest("/api/system-health");
    renderGlobalAgentDebug(pageKey, payload);
  } catch (error) {
    const ids = globalDebugPanelIds(pageKey);
    renderList(ids.trace, [`DEBUG 加载失败 / ${error.message}`], "当前还没有 DEBUG Trace。");
    renderList(ids.focus, [], "当前还没有失败焦点。");
  }
}
