 (async () => {
  const KEY = "station-diary.entries.v1";
  const entries = read();
  const allStations = await fetch("./data/stations.json").then(response => response.json()).catch(() => [...document.querySelectorAll(".station-card")].map(card => {
    const id = Number((card.getAttribute("href") || "").match(/station-(\d+)/)?.[1]);
    return { id, name: card.querySelector(".station-info h3")?.textContent.trim() || "", line: card.dataset.line || "" };
  }).filter(station => station.id));
  const colors = { "1호선":"#0052a4", "2호선":"#00a84d", "3호선":"#ef7c1c", "4호선":"#00a5de", "5호선":"#996cac", "6호선":"#cd7c2f", "7호선":"#747f00", "8호선":"#e6186c", "9호선":"#bdb092" };
  const dialog = document.createElement("main");
  dialog.id = "diary-dialog";
  dialog.hidden = true;
  dialog.innerHTML = `<form method="dialog" class="diary-modal"><button class="diary-close" aria-label="닫기">×</button><p class="diary-kicker">MY SUBWAY MEMORIES</p><h2 class="diary-title"></h2><div class="diary-visits"></div><div class="diary-form"><label>방문 날짜<input name="date" type="date" required></label><label>오늘의 기분<input name="emotion" maxlength="30" placeholder="예: 설렘, 편안함"></label><label>오늘의 기록<textarea name="diary" rows="4" placeholder="이 역에서의 기억을 적어 보세요"></textarea></label><button class="diary-save" type="button">기록 저장</button></div><div class="diary-tools" hidden><p class="diary-empty"></p><button type="button" class="diary-backup">기록 백업</button><label class="diary-restore">백업 불러오기<input type="file" accept="application/json"></label></div></form>`;
  document.body.append(dialog);
  dialog.querySelector(".diary-close").type = "button";
  dialog.querySelector(".diary-close").textContent = "← 홈으로";
  dialog.querySelector(".diary-close").addEventListener("click", () => {
    window.location.href = document.body.dataset.page === "record"
      ? `./station.html?id=${dialog.dataset.stationId}`
      : "./index.html";
  });
  dialog.showModal = () => {
    document.querySelectorAll("body > :not(#diary-dialog)").forEach(node => node.hidden = true);
    dialog.hidden = false;
    dialog.classList.add("page-open");
  };

  function read() {
    try {
      const data = JSON.parse(localStorage.getItem(KEY) || "{}");
      for (const [id, value] of Object.entries(data)) {
        if (Array.isArray(value)) continue;
        if (value && typeof value === "object" && (value.visited || value.note || value.diary)) {
          data[id] = [{ date: value.date || new Date().toISOString().slice(0, 10), diary: value.diary || value.note || "", emotion: value.emotion || "" }];
        } else delete data[id];
      }
      return data;
    } catch { return {}; }
  }
  function localDate() { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`; }
  function esc(value) { return String(value).replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c])); }
  function persist() { localStorage.setItem(KEY, JSON.stringify(entries)); refresh(); }
  function visitsFor(id) { return Array.isArray(entries[id]) ? entries[id] : []; }
  function refresh() {
    const visited = Object.keys(entries).filter(id => visitsFor(id).length).length;
    const total = allStations.length;
    const pct = total ? visited * 100 / total : 0;
    const fill = document.querySelector(".progress-fill");
    if (fill) { fill.dataset.progress = pct; requestAnimationFrame(() => fill.style.width = `${pct}%`); }
    const count = document.querySelector(".progress-header h2");
    if (count) { count.childNodes[0].nodeValue = `\n                        ${visited}\n                        `; count.querySelector("span").textContent = `/ ${total}`; }
    const percent = document.querySelector(".progress-percent");
    if (percent) percent.textContent = `${pct.toFixed(1)}%`;
    const description = document.querySelector(".progress-description");
    if (description) description.innerHTML = visited === 0 ? "아직 방문한 역이 없어요. 첫 번째 역을 기록해 보세요!" : visited === total ? "모든 역을 방문했어요!" : `지금까지 <strong>${visited}개</strong> 역을 방문했어요.`;
    const mapCount = document.querySelector(".map-section .section-title span");
    if (mapCount) mapCount.textContent = `${visited}개 역`;
    document.querySelectorAll(".station-card").forEach(card => {
      const id = Number((card.getAttribute("href") || "").match(/station-(\d+)/)?.[1]);
      card.dataset.visited = visitsFor(id).length ? "true" : "false";
    });
    renderToday();
    renderMap();
  }
  function renderToday() {
    const today = localDate();
    const todayVisits = allStations.flatMap(s => visitsFor(s.id).filter(v => v.date === today).map(v => ({ ...v, station: s })));
    let section = document.querySelector(".memory-today-section");
    if (!todayVisits.length) { section?.remove(); return; }
    if (!section) {
      section = document.createElement("section"); section.className = "memory-today-section";
      const map = document.querySelector(".map-section"); map?.before(section);
    }
    section.innerHTML = `<div class="section-title"><h2>오늘의 추억</h2><span>${todayVisits.length}개의 기록</span></div><div class="today-memory-list">${todayVisits.slice(0, 5).map(v => `<article class="today-memory-card"><div class="today-memory-date">${esc(v.date)}</div><h3>🚉 ${esc(v.station.name)}</h3>${v.emotion ? `<div class="today-memory-emotion">${esc(v.emotion)}</div>` : ""}<p>${esc(v.diary || "남겨둔 일기가 없어요.")}</p></article>`).join("")}</div>`;
  }
  function renderMap() {
    if (!window.diaryMap || !window.L) return;
    if (window.diaryMarkerLayer) window.diaryMap.removeLayer(window.diaryMarkerLayer);
    window.diaryMarkerLayer = L.layerGroup().addTo(window.diaryMap);
    const bounds = [];
    allStations.forEach(s => {
      if (!visitsFor(s.id).length) return;
      const node = document.querySelector(`.station-data-item[data-station-id="${s.id}"]`);
      if (!node) return;
      const point = [Number(node.dataset.latitude), Number(node.dataset.longitude)];
      L.marker(point).addTo(window.diaryMarkerLayer).bindPopup(`<a href="./station.html?id=${s.id}">🚉 ${esc(s.name)}</a>`);
      bounds.push(point);
    });
    if (bounds.length > 1) window.diaryMap.fitBounds(bounds, { padding:[35,35], maxZoom:13 });
    else if (bounds.length === 1) window.diaryMap.setView(bounds[0], 14);
  }
  function showStation(id) {
    const station = allStations.find(s => s.id === id); if (!station) return;
    document.title = `${station.name}역 | 지하철 일기`;
    dialog.dataset.stationId = id;
    dialog.querySelector(".diary-title").textContent = `${station.name}역`;
    dialog.querySelector("[name=date]").value = localDate();
    dialog.querySelector("[name=emotion]").value = "";
    dialog.querySelector("[name=diary]").value = "";
    dialog.querySelector(".diary-form").hidden = true;
    dialog.querySelector(".diary-tools").hidden = true;
    const visits = visitsFor(id);
    dialog.querySelector(".diary-visits").innerHTML = `${visits.length ? `<h3>나의 추억 · ${visits.length}개</h3>${[...visits].reverse().map((v, i) => `<article class="diary-entry"><div><b>${esc(v.date)}</b>${v.emotion ? ` · ${esc(v.emotion)}` : ""}</div><p>${esc(v.diary || "기록한 메모가 없어요.")}</p><button type="button" class="diary-delete" data-index="${visits.length - 1 - i}">삭제</button></article>`).join("")}` : `<p class="diary-empty">아직 기록이 없어요.</p>`}<a class="diary-write-link" href="./record.html?id=${id}">이 역의 기록 작성하기</a>`;
    dialog.querySelectorAll(".diary-delete").forEach(button => button.addEventListener("click", () => {
      const list = visitsFor(id); list.splice(Number(button.dataset.index), 1); if (!list.length) delete entries[id]; persist(); showStation(id);
    }));
    dialog.showModal();
  }
  function showCollection() {
    document.title = "방문 기록 | 지하철 일기";
    const visited = allStations.filter(s => visitsFor(s.id).length);
    dialog.dataset.stationId = "";
    dialog.querySelector(".diary-title").textContent = "내가 방문한 역";
    dialog.querySelector(".diary-visits").innerHTML = visited.length ? visited.map(s => `<article class="diary-entry"><b>${esc(s.line)} · ${esc(s.name)}역</b><p>${visitsFor(s.id).length}개의 추억</p><button type="button" class="diary-open" data-id="${s.id}">기록 보기</button></article>`).join("") : '<p class="diary-empty">아직 방문 기록이 없어요.</p>';
    dialog.querySelector(".diary-form").hidden = true; dialog.querySelector(".diary-tools").hidden = true; dialog.showModal();
    dialog.querySelectorAll(".diary-open").forEach(b => b.addEventListener("click", () => { window.location.href = `./station.html?id=${b.dataset.id}`; }));
  }
  function showProfile() {
    document.title = "내 기록 | 지하철 일기";
    dialog.dataset.stationId = "";
    const visited = Object.keys(entries).filter(id => visitsFor(id).length).length;
    dialog.querySelector(".diary-title").textContent = "나의 기록";
    dialog.querySelector(".diary-visits").innerHTML = `<p class="diary-empty">${visited}개 역을 방문하고 ${Object.values(entries).reduce((n, list) => n + (Array.isArray(list) ? list.length : 0), 0)}개의 추억을 기록했어요.</p><p class="diary-empty">기록은 이 브라우저에 저장됩니다. 다른 기기에서도 사용하려면 백업 파일을 옮겨 주세요.</p>`;
    dialog.querySelector(".diary-form").hidden = true;
    const tools = dialog.querySelector(".diary-tools"); tools.hidden = false;
    dialog.showModal();
  }
  function showRecord(id) {
    const station = allStations.find(item => item.id === id);
    if (!station) { window.location.href = "./index.html"; return; }
    document.title = `${station.name}역 기록 작성 | 지하철 일기`;
    dialog.dataset.stationId = id;
    dialog.querySelector(".diary-close").textContent = "← 역 기록으로";
    dialog.querySelector(".diary-title").textContent = `${station.name}역의 기억`;
    dialog.querySelector(".diary-visits").hidden = true;
    dialog.querySelector(".diary-form").hidden = false;
    dialog.querySelector(".diary-tools").hidden = true;
    dialog.querySelector("[name=date]").value = localDate();
    dialog.showModal();
  }
  dialog.querySelector(".diary-backup").addEventListener("click", () => {
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify({ version: 1, entries }, null, 2)], { type: "application/json" })); a.download = "station-diary-backup.json"; a.click(); URL.revokeObjectURL(a.href);
  });
  dialog.querySelector(".diary-restore input").addEventListener("change", async event => {
    try { const data = JSON.parse(await event.target.files[0].text()); const imported = data.entries || data; if (!imported || typeof imported !== "object") throw Error(); Object.assign(entries, imported); persist(); alert("백업 기록을 불러왔어요."); }
    catch { alert("백업 파일을 읽지 못했어요."); }
    event.target.value = "";
  });
  dialog.addEventListener("close", () => { dialog.querySelector(".diary-form").hidden = false; dialog.querySelector(".diary-tools").hidden = true; });
  dialog.querySelector(".diary-save").addEventListener("click", () => {
    const id = Number(dialog.dataset.stationId); if (!id) return;
    const form = dialog.querySelector(".diary-form"), date = form.querySelector("[name=date]").value;
    const diary = form.querySelector("[name=diary]").value.trim(), emotion = form.querySelector("[name=emotion]").value.trim();
    if (!date) return;
    (entries[id] ||= []).push({ date, diary, emotion }); persist(); window.location.href = `./station.html?id=${id}`;
  });
  const page = document.body.dataset.page;
  if (page === "station") showStation(Number(new URLSearchParams(location.search).get("id")));
  else if (page === "record") showRecord(Number(new URLSearchParams(location.search).get("id")));
  else if (page === "collection") showCollection();
  else if (page === "profile") showProfile();
  refresh();
  window.addEventListener("load", () => setTimeout(renderMap, 250));
})();
