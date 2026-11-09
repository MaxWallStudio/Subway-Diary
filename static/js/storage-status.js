(() => {
  const KEY = "station-diary.entries.v1";

  function formatBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes < 0) return "확인 불가";
    if (bytes < 1024) return `${Math.round(bytes)} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let value = bytes / 1024;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit++;
    }
    return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
  }

  async function update(card) {
    const recordSize = card.querySelector("[data-record-size]");
    const remaining = card.querySelector("[data-storage-remaining]");
    try {
      const serialized = localStorage.getItem(KEY) || "";
      recordSize.textContent = formatBytes(new Blob([serialized]).size);
    } catch {
      recordSize.textContent = "확인 불가";
    }

    try {
      if (!navigator.storage?.estimate) throw new Error("unsupported");
      const estimate = await navigator.storage.estimate();
      if (!Number.isFinite(estimate.quota) || estimate.quota <= 0) throw new Error("unavailable");
      const usage = Number.isFinite(estimate.usage) ? estimate.usage : 0;
      const free = Math.max(0, estimate.quota - usage);
      const ratio = Math.min(100, Math.max(0, usage / estimate.quota * 100));
      remaining.textContent = formatBytes(free);
      card.querySelector("[data-storage-used]").textContent = formatBytes(usage);
      card.querySelector("[data-storage-quota]").textContent = formatBytes(estimate.quota);
      card.querySelector(".storage-meter span").style.width = `${ratio}%`;
      card.querySelector(".storage-meter").setAttribute("aria-valuenow", ratio.toFixed(1));
    } catch {
      remaining.textContent = "이 브라우저에서는 확인할 수 없어요";
      card.querySelector("[data-storage-used]").textContent = "확인 불가";
      card.querySelector("[data-storage-quota]").textContent = "확인 불가";
      card.querySelector(".storage-meter span").style.width = "0%";
    }
  }

  function bind(card) {
    if (card.dataset.storageBound) return;
    card.dataset.storageBound = "true";
    card.querySelector(".storage-refresh")?.addEventListener("click", () => update(card));
    update(card);
  }

  window.bindDiaryStorageCard = bind;
  document.querySelectorAll("[data-storage-card]").forEach(bind);
})();
