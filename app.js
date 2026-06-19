/* Found—Space Visualiser — front-end logic */
(() => {
  const MAX_BYTES = 12 * 1024 * 1024;

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
      card.className = "pcard";
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
  function handleFile(file) {
    els.renderErr.style.display = "none";
    if (!file) return;
    if (!file.type.startsWith("image/")) return showRenderErr("Please choose an image file (JPG or PNG).");
    if (file.size > MAX_BYTES) return showRenderErr("That image is over 12MB — please use a smaller photo.");
    const reader = new FileReader();
    reader.onload = (e) => {
      state.imageDataUrl = e.target.result;
      state.imageMime = file.type;
      els.previewImg.src = state.imageDataUrl;
      els.preview.style.display = "block";
      els.drop.style.display = "none";
      refreshAction();
    };
    reader.readAsDataURL(file);
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
      els.resultImg.src = data.image;
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
    a.download = `found-space-${state.saunaId || "render"}-${state.sizeId || ""}.png`;
    document.body.appendChild(a); a.click(); a.remove();
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
