(() => {
  const helperScript = document.currentScript;
  const ua = navigator.userAgent || "";
  const platform = /iPhone|iPad|iPod/i.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
    ? "ios"
    : /Android/i.test(ua) ? "android" : "desktop";
  const browser = /Edg\//i.test(ua) ? "Edge"
    : /SamsungBrowser/i.test(ua) ? "Samsung Internet"
    : /CriOS|Chrome\//i.test(ua) ? "Chrome"
    : /Firefox|FxiOS/i.test(ua) ? "Firefox"
    : /Safari/i.test(ua) ? "Safari" : "현재 브라우저";
  const inApp = /Instagram|KAKAOTALK|KakaoTalk|FBAN|FBAV|Messenger|Line\//i.test(ua);
  const guideSteps = document.getElementById("install-steps");
  let deferredInstallPrompt = null;
  const installPromptButton = document.getElementById("install-now-button");

  window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault();
    deferredInstallPrompt = event;
  });

  installPromptButton?.addEventListener("click", async () => {
    if (!deferredInstallPrompt) {
      const installPage = helperScript?.dataset.installUrl;
      const installUrl = installPage ? new URL(installPage, location.href) : null;
      if (installUrl && installUrl.pathname !== location.pathname) location.href = installUrl.href;
      else document.getElementById("install-steps")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    const promptEvent = deferredInstallPrompt;
    deferredInstallPrompt = null;
    promptEvent.prompt();
    const choice = await promptEvent.userChoice;
    if (choice.outcome === "accepted") {
      installPromptButton.textContent = "설치 완료";
      installPromptButton.disabled = true;
    }
  });

  window.addEventListener("appinstalled", () => {
    if (!installPromptButton) return;
    installPromptButton.textContent = "설치 완료";
    installPromptButton.disabled = true;
  });

  if (guideSteps) {
    const browserName = document.getElementById("install-browser-name");
    const title = document.getElementById("install-device-title");
    if (inApp) {
      title.textContent = "앱 안에서 페이지를 열고 있어요";
      browserName.textContent = `${platform === "ios" ? "iPhone·iPad" : platform === "android" ? "Android" : "기기"} · ${browser} 인앱 브라우저`;
      guideSteps.innerHTML = platform === "ios"
        ? "<li>공유 버튼 또는 오른쪽 위 <strong>⋯</strong>를 누르세요.</li><li><strong>Safari에서 열기</strong> 또는 <strong>브라우저에서 열기</strong>를 선택하세요.</li><li>Safari에서 공유 버튼을 누른 뒤 <strong>홈 화면에 추가</strong>를 선택하세요.</li>"
        : "<li>기본 브라우저로 열기를 시도합니다.</li><li>열리지 않으면 아래 외부 브라우저 안내에서 주소를 복사해 Chrome 또는 다른 브라우저에 붙여넣으세요.</li><li>브라우저 메뉴에서 <strong>앱 설치</strong> 또는 <strong>홈 화면에 추가</strong>를 선택하세요.</li>";
    } else if (platform === "ios") {
      browserName.textContent = `iPhone·iPad · ${browser}`;
      guideSteps.innerHTML = "<li>Safari에서 이 페이지를 여세요.</li><li>화면 아래의 <strong>공유</strong> 버튼을 누르세요.</li><li><strong>홈 화면에 추가</strong>를 선택하고 <strong>추가</strong>를 누르세요.</li>";
    } else if (platform === "android") {
      browserName.textContent = `Android · ${browser}`;
      guideSteps.innerHTML = browser === "Samsung Internet"
        ? "<li>화면 아래 또는 위의 <strong>메뉴</strong>를 여세요.</li><li><strong>현재 페이지 추가</strong> → <strong>홈 화면</strong>을 선택하세요.</li>"
        : "<li>Chrome에서 화면 오른쪽 위 <strong>⋮</strong> 메뉴를 여세요.</li><li><strong>앱 설치</strong> 또는 <strong>홈 화면에 추가</strong>를 누르세요.</li><li>확인 창에서 <strong>설치</strong> 또는 <strong>추가</strong>를 선택하세요.</li>";
    } else {
      browserName.textContent = `데스크톱 · ${browser}`;
      guideSteps.innerHTML = "<li>Chrome 또는 Edge에서 이 페이지를 여세요.</li><li>주소창 오른쪽의 설치 아이콘을 누르거나 브라우저 메뉴에서 <strong>앱 설치</strong>를 선택하세요.</li><li>설치 메뉴가 없으면 페이지를 북마크에 추가해 사용할 수 있어요.</li>";
    }
  }

  const copyButton = document.getElementById("copy-page-address");
  copyButton?.addEventListener("click", async () => {
    const status = document.getElementById("copy-status");
    try {
      await navigator.clipboard.writeText(location.href);
      status.textContent = "주소를 복사했어요. Safari 또는 Chrome에 붙여넣어 주세요.";
    } catch {
      status.textContent = `주소를 길게 눌러 복사해 주세요: ${location.href}`;
    }
  });

  function openAndroidExternal() {
    const fallback = new URL(location.href);
    fallback.searchParams.set("open_in_browser", "1");
    const intent = `intent://${location.host}${location.pathname}${location.search}#Intent;scheme=${location.protocol.slice(0, -1)};action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;S.browser_fallback_url=${encodeURIComponent(fallback.href)};end`;
    location.href = intent;
  }

  if (inApp) {
    const banner = document.createElement("aside");
    banner.className = "browser-help-banner";
    banner.setAttribute("role", "status");
    const message = document.createElement("span");
    message.textContent = platform === "ios"
      ? "앱 설치와 사진 선택을 위해 Safari에서 여는 것을 권장해요."
      : "앱 안 브라우저에서는 일부 기능이 제한될 수 있어요.";
    banner.append(message);
    if (platform === "android") {
      const openButton = document.createElement("button");
      openButton.type = "button";
      openButton.textContent = "기본 브라우저에서 열기";
      openButton.addEventListener("click", openAndroidExternal);
      banner.append(openButton);
    } else {
      const helpLink = document.createElement("a");
      const installPage = helperScript?.dataset.installUrl || (location.pathname.endsWith(".html") ? "./install.html" : "/install");
      helpLink.href = `${installPage}#external-browser-help`;
      helpLink.textContent = "여는 방법";
      banner.append(helpLink);
    }
    document.body.prepend(banner);

    const params = new URLSearchParams(location.search);
    if (platform === "android" && !params.has("open_in_browser") && location.host) {
      window.setTimeout(openAndroidExternal, 350);
    }
  }
})();
