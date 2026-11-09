if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    const script = document.querySelector('script[data-worker][data-scope]');
    if (!script) return;
    navigator.serviceWorker.register(script.dataset.worker, { scope: script.dataset.scope }).catch(error => {
      console.error("PWA service worker registration failed", error);
    });
  });
}
