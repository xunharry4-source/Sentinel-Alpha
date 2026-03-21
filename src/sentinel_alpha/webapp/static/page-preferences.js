const tradingPreferenceOptions = {
  low: {
    note: "低频适合不想频繁盯盘的用户，更适合日线和周线。",
    timeframes: [
      { value: "daily", label: "日线", note: "日线更容易过滤噪音。" },
      { value: "weekly", label: "周线", note: "周线更适合慢节奏波段。" },
    ],
  },
  medium: {
    note: "中频适合希望有节奏参与，但不想被分钟噪音拖着走的用户。",
    timeframes: [
      { value: "minute", label: "分钟线", note: "分钟线需要更高盯盘强度。" },
      { value: "daily", label: "日线", note: "日线是中频用户默认更稳的核心周期。" },
      { value: "weekly", label: "周线", note: "周线适合做更大的过滤层。" },
    ],
  },
  high: {
    note: "高频意味着更高成本和更强执行压力，不适合模糊表达。",
    timeframes: [
      { value: "minute", label: "分钟线", note: "分钟线贴近高频，但要求最高。" },
      { value: "daily", label: "日线", note: "如果不愿持续盯盘，日线更现实。" },
    ],
  },
};

function renderTimeframeOptions() {
  const frequency = document.querySelector("#frequency-input").value;
  const input = document.querySelector("#timeframe-input");
  const note = document.querySelector("#frequency-note");
  const config = tradingPreferenceOptions[frequency] || tradingPreferenceOptions.low;
  note.textContent = config.note;
  const currentValue = input.value;
  input.innerHTML = config.timeframes.map((item) => `<option value="${item.value}">${item.label}</option>`).join("");
  input.value = config.timeframes.some((item) => item.value === currentValue) ? currentValue : config.timeframes[0].value;
  renderTimeframeNote();
}

function renderTimeframeNote() {
  const frequency = document.querySelector("#frequency-input").value;
  const timeframe = document.querySelector("#timeframe-input").value;
  const config = tradingPreferenceOptions[frequency] || tradingPreferenceOptions.low;
  const selected = config.timeframes.find((item) => item.value === timeframe) || config.timeframes[0];
  setText("timeframe-note", selected.note);
}

function applyRecommendation(report) {
  if (!report?.recommended_trading_frequency) {
    setText("recommendation-note", "当前还没有可应用的测试推荐。");
    return;
  }
  document.querySelector("#frequency-input").value = report.recommended_trading_frequency;
  renderTimeframeOptions();
  document.querySelector("#timeframe-input").value = report.recommended_timeframe;
  renderTimeframeNote();
  setText("recommendation-note", report.trading_preference_recommendation_note || "已应用测试推荐。");
}

async function savePreferences() {
  const snapshot = loadStoredSnapshot();
  if (!snapshot?.session_id) {
    setText("preferences-note", "请先创建会话。");
    return;
  }
  try {
    const latest = await apiRequest(`/api/sessions/${snapshot.session_id}/trading-preferences`, {
      method: "POST",
      body: JSON.stringify({
        trading_frequency: document.querySelector("#frequency-input").value,
        preferred_timeframe: document.querySelector("#timeframe-input").value,
        rationale: document.querySelector("#preference-rationale-input").value || null,
      }),
    });
    storeSnapshot(latest);
    renderShell("preferences");
    formatJsonIntoList("preference-list", latest.trading_preferences || null, "当前还没有偏好设置。");
    const warning = latest.trading_preferences?.conflict_warning || "当前没有明显冲突。";
    setText("preference-conflict-note", warning);
    setText("preferences-note", "交易偏好已保存。");
  } catch (error) {
    setText("preferences-note", `保存交易偏好失败：${error.message}`);
  }
}

document.querySelector("#frequency-input")?.addEventListener("change", renderTimeframeOptions);
document.querySelector("#timeframe-input")?.addEventListener("change", renderTimeframeNote);
document.querySelector("#apply-recommendation")?.addEventListener("click", () => {
  const snapshot = loadStoredSnapshot();
  applyRecommendation(snapshot?.behavioral_report || {});
});
document.querySelector("#save-preferences")?.addEventListener("click", savePreferences);

(function bootstrapPreferencesPage() {
  renderShell("preferences");
  const snapshot = loadStoredSnapshot();
  renderTimeframeOptions();
  if (snapshot?.trading_preferences) {
    document.querySelector("#frequency-input").value = snapshot.trading_preferences.trading_frequency;
    renderTimeframeOptions();
    document.querySelector("#timeframe-input").value = snapshot.trading_preferences.preferred_timeframe;
    document.querySelector("#preference-rationale-input").value = snapshot.trading_preferences.rationale || "";
    renderTimeframeNote();
  }
  formatJsonIntoList("preference-list", snapshot?.trading_preferences || null, "当前还没有偏好设置。");
  renderList(
    "preference-rec-list",
    snapshot?.behavioral_report?.recommended_trading_frequency ? [
      `recommended_trading_frequency: ${snapshot.behavioral_report.recommended_trading_frequency}`,
      `recommended_timeframe: ${snapshot.behavioral_report.recommended_timeframe}`,
      snapshot.behavioral_report.trading_preference_recommendation_note || "无说明",
    ] : [],
    "等待行为测试推荐。"
  );
  setText("preference-conflict-note", snapshot?.trading_preferences?.conflict_warning || "如果你的选择和测试结果冲突，这里会提示风险。");
})();
