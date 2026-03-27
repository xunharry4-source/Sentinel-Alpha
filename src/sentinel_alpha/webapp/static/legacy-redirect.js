(() => {
  document.documentElement.style.visibility = "hidden";
  const host = window.location.hostname || "127.0.0.1";
  const params = new URLSearchParams(window.location.search);
  const targetPort = params.get("nicegui_port") || "8010";
  const protocol = window.location.protocol && window.location.protocol !== "file:" ? window.location.protocol : "http:";
  const destination = new URL(`${protocol}//${host}:${targetPort}/`);
  destination.search = window.location.search;
  destination.hash = window.location.hash;

  const targetLink = document.querySelector("[data-legacy-redirect-target]");
  if (targetLink) {
    targetLink.href = destination.toString();
    targetLink.textContent = destination.toString();
  }

  const targetLabel = document.querySelector("[data-legacy-redirect-label]");
  if (targetLabel) {
    targetLabel.textContent = destination.toString();
  }

  if (window.location.href !== destination.toString()) {
    window.location.replace(destination.toString());
    return;
  }
  document.documentElement.style.visibility = "";
})();
