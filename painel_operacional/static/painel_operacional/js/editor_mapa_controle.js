(function () {
  const frameVisual = document.getElementById("poMapaDedicadoFrameVisual");
  const loading = document.getElementById("poMapaDedicadoLoading");
  const btnEditarMapa = document.getElementById("btnEditarMapa");
  if (!frameVisual) return;
  let bridgedDeltaY = 0;
  let bridgeRaf = 0;
  let restoreParentScrollY = null;

  function hideLoading() {
    if (loading) loading.style.display = "none";
  }

  function resizeFrameToContent() {
    try {
      const doc = frameVisual.contentDocument;
      if (!doc) return;
      const body = doc.body;
      const html = doc.documentElement;
      const nextHeight = Math.max(
        Number(body && body.scrollHeight) || 0,
        Number(html && html.scrollHeight) || 0,
        520,
      );
      frameVisual.style.height = `${nextHeight}px`;
    } catch (e) {
      void e;
    }
  }

  frameVisual.addEventListener("load", () => {
    hideLoading();
    resizeFrameToContent();
    window.setTimeout(resizeFrameToContent, 120);
    if (typeof restoreParentScrollY === "number") {
      const targetY = restoreParentScrollY;
      restoreParentScrollY = null;
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: targetY, left: 0, behavior: "auto" });
      });
    }
  });

  frameVisual.addEventListener("error", () => {
    if (!loading) return;
    loading.textContent = "Falha ao carregar o mapa de controle.";
    loading.style.display = "flex";
  });

  if (btnEditarMapa) {
    btnEditarMapa.addEventListener("click", (event) => {
      try {
        const href = btnEditarMapa.getAttribute("href") || "";
        const currentHref = String(frameVisual.contentWindow.location.href || "");
        if (!href || !currentHref) return;
        const current = new URL(currentHref);
        const rel = `${current.pathname}${current.search}${current.hash || ""}`;
        const target = new URL(href, window.location.origin);
        target.searchParams.set("next_mapa", rel);
        btnEditarMapa.setAttribute("href", target.pathname + target.search);
      } catch (e) {
        void e;
      }
      // Mantém comportamento padrão de navegação.
      event.stopPropagation();
    });
  }

  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin) return;
    if (event.source !== frameVisual.contentWindow) return;
    const data = event.data;
    if (!data || typeof data !== "object") return;
    if (data.type === "po:iframe-nav-start") {
      restoreParentScrollY = window.scrollY;
      return;
    }
    if (data.type !== "po:iframe-scroll-bridge") return;
    const payload = data.payload;
    const dy = Number(payload && payload.deltaY);
    if (!Number.isFinite(dy) || dy === 0) return;
    bridgedDeltaY += dy;
    if (bridgeRaf) return;
    bridgeRaf = window.requestAnimationFrame(() => {
      bridgeRaf = 0;
      const delta = bridgedDeltaY;
      bridgedDeltaY = 0;
      if (!delta) return;
      window.scrollBy({ top: delta, left: 0, behavior: "auto" });
    });
  });

  // Fallback de UX em caso de carregamento lento.
  window.setTimeout(hideLoading, 6500);
  window.addEventListener("resize", () => {
    resizeFrameToContent();
  });
})();

