/* Found—Space Visualiser — front-end logic */
(() => {
  const MAX_BYTES = 25 * 1024 * 1024;

  const state = { imageDataUrl: null, imageMime: null, saunaId: null, sizeId: null, products: [] };

  const $ = (id) => document.getElementById(id);
  const els = {
    drop: $("drop"), file: $("file"), preview: $("preview"), previewImg: $("previewImg"),
    resetImg: $("resetImg"), grid: $("grid"), sizes: $("sizes"), sizePills: $("sizePills"),
    sizesFor: $("sizesFor"), visualise: $("visualise"), actionHint: $("actionHint"),
    renderErr: $("renderErr"), resultStep: $("resultStep"), resultSub: $("resultSub"),
    loader: $("loader"), resultImg: $("resultImg"), resultLabel: $("resultLabel"),
    download: $("download"), redo: $("redo"),
    lead: $("lead"), leadForm: $("leadForm"), leadBtn: $("leadBtn"), leadErr: $("leadErr"),
  };

  const productById = (id) => state.products.find((p) => p.id === id);
  const sizeById = (product, id) => (product && product.sizes || []).find((s) => s.id === id);

  /* ---------- catalog ---------- */
  async function loadCatalog() {
    try {
      const r = await fetch("/saunas.json");
      const data = await r.json();
      state.products = data.products || [];
    } catch (e) { state.products = []; }
    renderGrid();
  }

  function renderGrid() {
    els.grid.innerHTML = "";
    state.products.forEach((p) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "pcard glass";
      card.dataset.id = p.id;
      card.innerHTML = `
        <img class="pcard__img" src="${p.image}" alt="${p.name}" loading="lazy" />
        <div class="pcard__check">✓</div>
        <div class="pcard__body">
          <div class="pcard__type">${p.type}</div>
          <div class="pcard__name">${p.name}</div>
          <div class="pcard__tag">${p.tagline}</div>
        </div>`;
      card.addEventListener("click", () => selectSauna(p.id, card));
      els.grid.appendChild(card);
    });
  }

  function selectSauna(id, card) {
    state.saunaId = id;
    state.sizeId = null;
    [...els.grid.children].forEach((c) => c.classList.toggle("sel", c === card));
    renderSizes(productById(id));
    refreshAction();
  }

  function renderSizes(product) {
    const sizes = (product && product.sizes) || [];
    els.sizePills.innerHTML = "";
    els.sizesFor.textContent = product ? `${product.name} size` : "size";
    sizes.forEach((s) => {
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "pill";
      pill.dataset.id = s.id;
      pill.innerHTML = `${s.label}<small>${s.dimensions || ""}</small>`;
      pill.addEventListener("click", () => selectSize(s.id, pill));
      els.sizePills.appendChild(pill);
    });
    els.sizes.hidden = sizes.length === 0;
    // Auto-select when there's only one size option.
    if (sizes.length === 1) selectSize(sizes[0].id, els.sizePills.firstChild);
  }

  function selectSize(id, pill) {
    state.sizeId = id;
    [...els.sizePills.children].forEach((c) => c.classList.toggle("sel", c === pill));
    refreshAction();
  }

  /* ---------- upload ---------- */
  async function handleFile(file) {
    els.renderErr.style.display = "none";
    if (!file) return;
    const isHeic = /heic|heif/i.test(file.type) || /\.(heic|heif)$/i.test(file.name);
    if (!file.type.startsWith("image/") && !isHeic) {
      return showRenderErr("Please choose an image file (JPG, PNG or HEIC).");
    }
    if (file.size > MAX_BYTES) return showRenderErr("That image is over 25MB — please use a smaller photo.");

    setPreparing(true);
    try {
      // Convert iPhone HEIC and normalise everything to a right-sized JPEG,
      // so it both previews and sends reliably across all browsers.
      const jpeg = await toNormalisedJpeg(file, isHeic);
      state.imageDataUrl = jpeg;
      state.imageMime = "image/jpeg";
      els.previewImg.src = jpeg;
      els.preview.style.display = "block";
      els.drop.style.display = "none";
      refreshAction();
    } catch (err) {
      showRenderErr(err.message || "Couldn't read that photo. Please try a JPG or PNG.");
    } finally {
      setPreparing(false);
    }
  }

  function setPreparing(on) {
    const h = els.drop.querySelector("h3");
    if (h) h.textContent = on ? "Preparing your photo…" : "Drop your front-on photo here";
  }

  function readAsDataURL(blob) {
    return new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = (e) => res(e.target.result);
      r.onerror = () => rej(new Error("Couldn't read that file."));
      r.readAsDataURL(blob);
    });
  }

  async function toNormalisedJpeg(file, isHeic) {
    let blob = file;
    if (isHeic) {
      if (!window.heic2any) throw new Error("Couldn't read this iPhone (HEIC) photo. Please upload a JPG or PNG, or set your iPhone camera to ‘Most Compatible’.");
      const out = await window.heic2any({ blob: file, toType: "image/jpeg", quality: 0.9 });
      blob = Array.isArray(out) ? out[0] : out;
    }
    const dataUrl = await readAsDataURL(blob);
    return await new Promise((res, rej) => {
      const img = new Image();
      img.onload = () => {
        const max = 1600;
        let w = img.naturalWidth, h = img.naturalHeight;
        if (Math.max(w, h) > max) { const s = max / Math.max(w, h); w = Math.round(w * s); h = Math.round(h * s); }
        const c = document.createElement("canvas");
        c.width = w; c.height = h;
        c.getContext("2d").drawImage(img, 0, 0, w, h);
        res(c.toDataURL("image/jpeg", 0.85));
      };
      img.onerror = () => rej(new Error("Couldn't read that photo. Please try a JPG or PNG."));
      img.src = dataUrl;
    });
  }

  function resetImage() {
    state.imageDataUrl = null; state.imageMime = null;
    els.file.value = "";
    els.preview.style.display = "none";
    els.drop.style.display = "grid";
    refreshAction();
  }

  function refreshAction() {
    const ready = !!state.imageDataUrl && !!state.saunaId && !!state.sizeId;
    els.visualise.disabled = !ready;
    if (ready) els.actionHint.textContent = "Ready — this takes 10–30 seconds.";
    else if (!state.imageDataUrl) els.actionHint.textContent = "Upload a front-on photo of your space to begin.";
    else if (!state.saunaId) els.actionHint.textContent = "Now choose a Found—Space model above.";
    else els.actionHint.textContent = "Choose a size to finish.";
  }

  function showRenderErr(msg) { els.renderErr.textContent = msg; els.renderErr.style.display = "block"; }

  /* ---------- visualise ---------- */
  async function visualise() {
    if (!state.imageDataUrl || !state.saunaId || !state.sizeId) return;
    els.renderErr.style.display = "none";
    els.resultStep.style.display = "block";
    els.loader.classList.add("on");
    els.resultImg.removeAttribute("src");
    const product = productById(state.saunaId);
    const size = sizeById(product, state.sizeId);
    if (product && size) els.resultSub.textContent = `${product.name} · ${size.label} rendered to scale. Request a detailed quote below for this exact setup.`;
    els.resultStep.scrollIntoView({ behavior: "smooth", block: "start" });
    setVisualising(true);

    try {
      const r = await fetch("/api/visualise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: state.imageDataUrl, saunaId: state.saunaId, sizeId: state.sizeId }),
      });
      const data = await r.json();
      if (!r.ok || !data.image) throw new Error(data.error || "Render failed. Please try again.");
      const annotated = await annotateRender(data.image, product, size);
      els.resultImg.classList.remove("revealing");
      els.resultImg.onload = () => {
        void els.resultImg.offsetWidth; /* reflow so the reveal restarts each render */
        els.resultImg.classList.add("revealing");
      };
      els.resultImg.src = annotated;
      els.resultLabel.textContent = data.mode === "demo" ? "Demo preview (connect AI key for live render)" : "AI preview render";
    } catch (err) {
      els.resultStep.style.display = "none";
      showRenderErr(err.message || "Something went wrong. Please try again.");
    } finally {
      els.loader.classList.remove("on");
      setVisualising(false);
    }
  }

  function setVisualising(on) {
    els.visualise.disabled = on;
    els.visualise.textContent = on ? "Rendering…" : "Visualise in my space";
  }

  function downloadResult() {
    const src = els.resultImg.getAttribute("src");
    if (!src) return;
    const a = document.createElement("a");
    a.href = src;
    a.download = `found-space-${state.saunaId || "render"}-${state.sizeId || ""}.jpg`;
    document.body.appendChild(a); a.click(); a.remove();
  }

  /* ---------- dimension overlay ---------- */
  // Parse a catalogue dimensions string ("1.80m W × 1.15m D × 2.09m H",
  // "tub 1.35m L × 0.65m W × 0.75m H") into ordered {label, value} pairs.
  function parseDims(str) {
    const names = { W: "Width", D: "Depth", H: "Height", L: "Length" };
    const out = [];
    const re = /([\d.]+)\s*m\s*([WDHL])/gi;
    let m;
    while ((m = re.exec(str))) out.push({ label: names[m[2].toUpperCase()] || m[2], value: m[1] + "m" });
    return out;
  }

  function dimsLineWidth(ctx, dims, valSize) {
    let total = 0;
    const labFont = `600 ${Math.round(valSize * 0.62)}px Montserrat, sans-serif`;
    const valFont = `700 ${valSize}px Montserrat, sans-serif`;
    dims.forEach((d, i) => {
      ctx.font = labFont;
      if (i) total += ctx.measureText("    ").width;
      total += ctx.measureText(d.label.toUpperCase() + "  ").width;
      ctx.font = valFont;
      total += ctx.measureText(d.value).width;
    });
    return total;
  }

  // Bake a clean, accurate dimensions callout onto the rendered image so it's
  // visible on screen and included in any download/share.
  async function annotateRender(dataUrl, product, size) {
    const dims = size && size.dimensions ? parseDims(size.dimensions) : [];
    if (!dims.length) return dataUrl;
    try { await document.fonts.ready; } catch (e) { /* fall back to default font */ }

    return await new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        try {
          const w = img.naturalWidth, h = img.naturalHeight;
          const c = document.createElement("canvas");
          c.width = w; c.height = h;
          const ctx = c.getContext("2d");
          ctx.drawImage(img, 0, 0, w, h);

          const u = w / 1000;               // scale unit relative to width
          const padX = Math.round(34 * u);

          // Legibility gradient along the bottom.
          const gh = Math.max(h * 0.26, 150 * u);
          const grad = ctx.createLinearGradient(0, h - gh, 0, h);
          grad.addColorStop(0, "rgba(0,0,0,0)");
          grad.addColorStop(1, "rgba(0,0,0,0.80)");
          ctx.fillStyle = grad;
          ctx.fillRect(0, h - gh, w, gh);

          // Fit the dimensions line to the image width.
          let valSize = Math.round(34 * u);
          let guard = 0;
          while (dimsLineWidth(ctx, dims, valSize) > w - padX * 2 && valSize > 9 && guard++ < 80) valSize -= 1;

          const baseY = h - Math.round(30 * u);

          // Eyebrow (model + size), bronze, tracked.
          let title = size.label;
          const firstWord = (product && product.name ? product.name.split(" ")[0] : "").toLowerCase();
          if (firstWord && !title.toLowerCase().includes(firstWord)) title = product.name + " " + title;
          const eyebrow = ("Found—Space · " + title).toUpperCase();
          const eyeSize = Math.max(Math.round(valSize * 0.42), 10);
          ctx.font = `300 ${eyeSize}px Montserrat, sans-serif`;
          ctx.fillStyle = "#A1611C";
          ctx.textBaseline = "alphabetic";
          if ("letterSpacing" in ctx) ctx.letterSpacing = `${Math.max(1, 2 * u)}px`;
          ctx.fillText(eyebrow, padX, baseY - valSize - Math.round(14 * u));
          if ("letterSpacing" in ctx) ctx.letterSpacing = "0px";

          // Dimensions line: bronze labels + bone values, aligned on one baseline.
          const labFont = `600 ${Math.round(valSize * 0.62)}px Montserrat, sans-serif`;
          const valFont = `700 ${valSize}px Montserrat, sans-serif`;
          let x = padX;
          dims.forEach((d, i) => {
            if (i) { ctx.font = labFont; x += ctx.measureText("    ").width; }
            ctx.font = labFont; ctx.fillStyle = "#A1611C";
            const lab = d.label.toUpperCase() + "  ";
            ctx.fillText(lab, x, baseY); x += ctx.measureText(lab).width;
            ctx.font = valFont; ctx.fillStyle = "#efe9e1";
            ctx.fillText(d.value, x, baseY); x += ctx.measureText(d.value).width;
          });

          resolve(c.toDataURL("image/jpeg", 0.92));
        } catch (e) {
          resolve(dataUrl);             // never block the render on overlay issues
        }
      };
      img.onerror = () => resolve(dataUrl);
      img.src = dataUrl;
    });
  }

  /* ---------- lead ---------- */
  async function submitLead(e) {
    e.preventDefault();
    els.leadErr.style.display = "none";
    const f = els.leadForm;
    const payload = {
      firstName: f.firstName.value.trim(),
      lastName: f.lastName.value.trim(),
      email: f.email.value.trim(),
      phone: f.phone.value.trim(),
      postcode: f.postcode.value.trim(),
      saunaId: state.saunaId,
      sizeId: state.sizeId,
      render: els.resultImg.getAttribute("src") || null,
    };
    if (!payload.firstName || !payload.email || !payload.phone) {
      els.leadErr.textContent = "Please add your name, email and contact number.";
      els.leadErr.style.display = "block";
      return;
    }
    els.leadBtn.disabled = true; els.leadBtn.textContent = "Sending…";
    try {
      const r = await fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || "Could not submit."); }
      els.lead.classList.add("done");
    } catch (err) {
      els.leadErr.textContent = err.message || "Could not submit — please try again.";
      els.leadErr.style.display = "block";
      els.leadBtn.disabled = false; els.leadBtn.textContent = "Request my detailed quote";
    }
  }

  /* ---------- wire up ---------- */
  els.file.addEventListener("change", (e) => handleFile(e.target.files[0]));
  els.resetImg.addEventListener("click", (e) => { e.preventDefault(); resetImage(); });
  ["dragenter", "dragover"].forEach((ev) => els.drop.addEventListener(ev, (e) => { e.preventDefault(); els.drop.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => els.drop.addEventListener(ev, (e) => { e.preventDefault(); els.drop.classList.remove("drag"); }));
  els.drop.addEventListener("drop", (e) => { if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); });
  els.visualise.addEventListener("click", visualise);
  els.download.addEventListener("click", downloadResult);
  els.redo.addEventListener("click", () => { window.scrollTo({ top: document.querySelector(".studio").offsetTop, behavior: "smooth" }); });
  els.leadForm.addEventListener("submit", submitLead);

  loadCatalog();
})();
