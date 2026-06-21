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
    // Show the chosen size's own photo on the selected product card.
    const size = sizeById(productById(state.saunaId), id);
    const cardImg = els.grid.querySelector(".pcard.sel .pcard__img");
    if (cardImg && size && size.image) cardImg.src = size.image;
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
      const annotated = await annotateRender(data.image, product, size, data.bbox);
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

  // On phones, share the image file so the OS share sheet offers "Save Image" /
  // "Add to Photos"; on desktop (or if sharing is unsupported), download it.
  async function saveResult() {
    const src = els.resultImg.getAttribute("src");
    if (!src) return;
    const name = `found-space-${state.saunaId || "render"}-${state.sizeId || ""}.jpg`;
    try {
      const blob = await (await fetch(src)).blob();
      const file = new File([blob], name, { type: blob.type || "image/jpeg" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: "Found—Space", text: "My space with a Found—Space" });
        return;
      }
    } catch (err) {
      if (err && err.name === "AbortError") return;   // user dismissed the share sheet
      /* otherwise fall through to download */
    }
    const a = document.createElement("a");
    a.href = src; a.download = name;
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

  const BRONZE = "#A1611C", BONE = "#efe9e1";

  function roundRect(ctx, x, y, w, h, r) {
    if (ctx.roundRect) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); return; }
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // A premium label plate: dark translucent, bronze hairline, bronze label + bone value.
  function drawPlate(ctx, cx, cy, label, value, u, W, H) {
    const padH = 13 * u, padV = 9 * u, gap = 8 * u;
    const labFont = `600 ${Math.round(15 * u)}px Montserrat, sans-serif`;
    const valFont = `700 ${Math.round(21 * u)}px Montserrat, sans-serif`;
    const lab = label.toUpperCase(), val = value.replace("m", " m");
    ctx.font = labFont; const lw = ctx.measureText(lab).width + 2.5 * u * (lab.length - 1);
    ctx.font = valFont; const vw = ctx.measureText(val).width;
    const bw = lw + gap + vw + padH * 2, bh = Math.round(38 * u);
    let x = cx - bw / 2, y = cy - bh / 2;
    x = Math.max(6 * u, Math.min(W - bw - 6 * u, x));
    y = Math.max(6 * u, Math.min(H - bh - 6 * u, y));
    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.45)"; ctx.shadowBlur = 6 * u; ctx.shadowOffsetY = 1 * u;
    roundRect(ctx, x, y, bw, bh, 5 * u);
    ctx.fillStyle = "rgba(8,8,8,0.88)"; ctx.fill();
    ctx.shadowColor = "transparent";
    ctx.lineWidth = Math.max(1, 1.2 * u); ctx.strokeStyle = BRONZE; ctx.stroke();
    ctx.textBaseline = "middle";
    let tx = x + padH; const ty = y + bh / 2;
    ctx.font = labFont; ctx.fillStyle = BRONZE;
    if ("letterSpacing" in ctx) ctx.letterSpacing = `${2.5 * u}px`;
    ctx.fillText(lab, tx, ty); tx += lw + gap;
    if ("letterSpacing" in ctx) ctx.letterSpacing = "0px";
    ctx.font = valFont; ctx.fillStyle = BONE;
    ctx.fillText(val, tx, ty);
    ctx.restore();
  }

  function dimLine(ctx, x1, y1, x2, y2, u) {
    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.5)"; ctx.shadowBlur = 4 * u;
    ctx.strokeStyle = BRONZE; ctx.lineWidth = Math.max(1.5, 2 * u); ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    ctx.restore();
  }

  // Architectural dimension lines hugging the product (uses detected bbox).
  function drawDimLines(ctx, w, h, u, bbox, dims, product, size) {
    let bx0 = bbox[0] * w, by0 = bbox[1] * h, bx1 = bbox[2] * w, by1 = bbox[3] * h;
    const off = 34 * u, tick = 9 * u, ext = 10 * u;

    const heightDim = dims.find((d) => d.label === "Height");
    const horiz = dims.filter((d) => d.label !== "Height").sort((a, b) => parseFloat(b.value) - parseFloat(a.value));
    const frontDim = horiz[0], depthDim = horiz[1];

    // WIDTH — along the base, below the product (or above if no room).
    if (frontDim) {
      let wy = by1 + off, edge = by1;
      if (wy > h - 70 * u) { wy = by0 - off; edge = by0; }
      dimLine(ctx, bx0, edge - (edge === by0 ? -ext : ext), bx0, wy, u);
      dimLine(ctx, bx1, edge - (edge === by0 ? -ext : ext), bx1, wy, u);
      dimLine(ctx, bx0, wy, bx1, wy, u);
      dimLine(ctx, bx0, wy - tick, bx0, wy + tick, u);
      dimLine(ctx, bx1, wy - tick, bx1, wy + tick, u);
      drawPlate(ctx, (bx0 + bx1) / 2, wy, frontDim.label, frontDim.value, u, w, h);
    }

    // HEIGHT — up the side with the most room.
    if (heightDim) {
      const onRight = (w - bx1) >= bx0;
      let hx = onRight ? bx1 + off : bx0 - off;
      const edge = onRight ? bx1 : bx0;
      dimLine(ctx, edge + (onRight ? -ext : ext), by0, hx, by0, u);
      dimLine(ctx, edge + (onRight ? -ext : ext), by1, hx, by1, u);
      dimLine(ctx, hx, by0, hx, by1, u);
      dimLine(ctx, hx - tick, by0, hx + tick, by0, u);
      dimLine(ctx, hx - tick, by1, hx + tick, by1, u);
      drawPlate(ctx, hx, (by0 + by1) / 2, heightDim.label, heightDim.value, u, w, h);
    }

    // DEPTH — tagged at the front-bottom corner (can't be a true 2D line).
    if (depthDim) {
      const onRight = (w - bx1) >= bx0;     // height is on this side; put depth opposite
      const cornerX = onRight ? bx0 : bx1;
      drawPlate(ctx, cornerX, by1 + off, depthDim.label, depthDim.value, u, w, h);
    }
  }

  // Fallback: clean caption strip when no bounding box is available.
  function drawCaption(ctx, w, h, u, dims) {
    const padX = Math.round(34 * u);
    const gh = Math.max(h * 0.2, 130 * u);
    const grad = ctx.createLinearGradient(0, h - gh, 0, h);
    grad.addColorStop(0, "rgba(0,0,0,0)"); grad.addColorStop(1, "rgba(0,0,0,0.8)");
    ctx.fillStyle = grad; ctx.fillRect(0, h - gh, w, gh);
    const baseY = h - Math.round(30 * u);
    let valSize = Math.round(32 * u), guard = 0;
    const measure = (vs) => {
      let t = 0;
      dims.forEach((d, i) => {
        ctx.font = `600 ${Math.round(vs * 0.62)}px Montserrat, sans-serif`;
        if (i) t += ctx.measureText("    ").width;
        t += ctx.measureText(d.label.toUpperCase() + "  ").width;
        ctx.font = `700 ${vs}px Montserrat, sans-serif`;
        t += ctx.measureText(d.value).width;
      });
      return t;
    };
    while (measure(valSize) > w - padX * 2 && valSize > 9 && guard++ < 80) valSize -= 1;
    ctx.textBaseline = "alphabetic";
    let x = padX;
    dims.forEach((d, i) => {
      if (i) { ctx.font = `600 ${Math.round(valSize * 0.62)}px Montserrat, sans-serif`; x += ctx.measureText("    ").width; }
      ctx.font = `600 ${Math.round(valSize * 0.62)}px Montserrat, sans-serif`; ctx.fillStyle = BRONZE;
      const lab = d.label.toUpperCase() + "  ";
      ctx.fillText(lab, x, baseY); x += ctx.measureText(lab).width;
      ctx.font = `700 ${valSize}px Montserrat, sans-serif`; ctx.fillStyle = BONE;
      ctx.fillText(d.value, x, baseY); x += ctx.measureText(d.value).width;
    });
  }

  // Load the white wordmark once for the on-render badge.
  let _logoPromise = null;
  function loadLogo() {
    if (_logoPromise) return _logoPromise;
    _logoPromise = new Promise((res) => {
      const im = new Image();
      im.onload = () => res(im);
      im.onerror = () => res(null);
      im.src = "/found-space-logo.png";
    });
    return _logoPromise;
  }

  // Top-left brand badge: Found—Space logo + product name & size, on a dark plate.
  function drawBadge(ctx, w, h, u, product, size, logo) {
    const padX = 30 * u, padY = 28 * u, padH = 16 * u, padV = 13 * u, gap = 10 * u;
    let title = size ? size.label : (product ? product.name : "");
    const fw = product && product.name ? product.name.split(" ")[0].toLowerCase() : "";
    if (product && fw && !title.toLowerCase().includes(fw)) title = product.name + " · " + title;
    const titleFont = `600 ${Math.round(17 * u)}px Montserrat, sans-serif`;
    const lh = logo ? 15 * u : 0;
    const lw = logo ? lh * (logo.naturalWidth / logo.naturalHeight) : 0;
    ctx.font = titleFont; const tw = ctx.measureText(title).width;
    const bw = Math.max(lw, tw) + padH * 2;
    const bh = padV * 2 + lh + (logo ? gap : 0) + Math.round(22 * u);
    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.45)"; ctx.shadowBlur = 8 * u; ctx.shadowOffsetY = 1 * u;
    roundRect(ctx, padX, padY, bw, bh, 6 * u);
    ctx.fillStyle = "rgba(8,8,8,0.82)"; ctx.fill();
    ctx.shadowColor = "transparent";
    ctx.lineWidth = Math.max(1, 1.2 * u); ctx.strokeStyle = BRONZE; ctx.stroke();
    let cy = padY + padV;
    if (logo) { ctx.drawImage(logo, padX + padH, cy, lw, lh); cy += lh + gap; }
    ctx.textBaseline = "top"; ctx.font = titleFont; ctx.fillStyle = BONE;
    ctx.fillText(title, padX + padH, cy);
    ctx.restore();
  }

  // Bake branding + dimensions onto the render (lines around the product if we
  // have a bounding box, otherwise a caption strip). Accurate — drawn, not AI text.
  async function annotateRender(dataUrl, product, size, bbox) {
    const dims = size && size.dimensions ? parseDims(size.dimensions) : [];
    try { await document.fonts.ready; } catch (e) { /* fall back to default font */ }
    const logo = await loadLogo();

    return await new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        try {
          const w = img.naturalWidth, h = img.naturalHeight;
          const c = document.createElement("canvas");
          c.width = w; c.height = h;
          const ctx = c.getContext("2d");
          ctx.drawImage(img, 0, 0, w, h);
          const u = w / 1000;
          if (dims.length) {
            const valid = Array.isArray(bbox) && bbox.length === 4 && bbox[2] > bbox[0] && bbox[3] > bbox[1];
            if (valid) drawDimLines(ctx, w, h, u, bbox, dims, product, size);
            else drawCaption(ctx, w, h, u, dims);
          }
          drawBadge(ctx, w, h, u, product, size, logo);
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
  els.download.addEventListener("click", saveResult);
  els.redo.addEventListener("click", () => { window.scrollTo({ top: document.querySelector(".studio").offsetTop, behavior: "smooth" }); });
  els.leadForm.addEventListener("submit", submitLead);

  loadCatalog();
})();
