const SESSION_STORAGE_KEY = "sentinel-alpha:last-session-snapshot";
const CONFIG_STORAGE_KEY = "sentinel-alpha:web-config";

function loadStoredSnapshot() {
  try {
    return JSON.parse(window.localStorage.getItem(SESSION_STORAGE_KEY) || "null");
  } catch (error) {
    return null;
  }
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
}

function storeConfig(config) {
  window.localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(config));
}

function resolveConfigPath() {
  return window.location.pathname.includes("/pages/") ? "../config.json" : "./config.json";
}

async function ensureClientConfig() {
  const existing = loadStoredConfig();
  if (existing?.apiBase) {
    return existing;
  }
  const response = await fetch(resolveConfigPath());
  if (!response.ok) {
    throw new Error("frontend config missing");
  }
  const payload = await response.json();
  storeConfig(payload);
  return payload;
}

async function apiRequest(path, options = {}) {
  const config = await ensureClientConfig();
  const response = await fetch(`${config.apiBase}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API ${response.status}`);
  }
  return response.json();
}

async function refreshSnapshot() {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    throw new Error("no session");
  }
  const latest = await apiRequest(`/api/sessions/${snapshot.session_id}`);
  storeSnapshot(latest);
  return latest;
}

function renderShell(pageKey) {
  const snapshot = loadStoredSnapshot();
  const config = loadStoredConfig();
  const nav = document.querySelector("[data-shell='nav']");
  const summary = document.querySelector("[data-shell='summary']");
  const pages = [
    { key: "home", href: "../index.html", label: "首页" },
    { key: "session", href: "./session.html", label: "会话创建" },
    { key: "simulation", href: "./simulation.html", label: "模拟测试" },
    { key: "report", href: "./report.html", label: "测试报告" },
    { key: "preferences", href: "./preferences.html", label: "交易偏好" },
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
