/* Mineral Scout frontend. Vanilla JS + Leaflet; talks only to our own /api. */
"use strict";

const $ = (id) => document.getElementById(id);
const statusLine = $("status-line");

const STATUS_COLORS = {
  "Producer": "#57b86a",
  "Past Producer": "#e8a33d",
  "Prospect": "#4fa3e3",
  "Occurrence": "#9aa7b4",
  "Plant": "#b07fe0",
  "Unknown": "#6c7a89",
};
const MINE_COLOR = "#e05555";
const TAILINGS_COLOR = "#c96f2f";
const CLAIM_COLOR = "#7f6ae0";
const MINDAT_COLOR = "#3dbfb0";

function loadBookmarks() {
  try {
    const parsed = JSON.parse(localStorage.getItem("mscout.bookmarks") || "[]");
    return Array.isArray(parsed)
      ? parsed.filter((b) => b && typeof b.lat === "number" && typeof b.lon === "number")
      : [];
  } catch (e) { return []; }
}

const state = {
  config: null,
  commodities: [],           // selected commodity filter chips
  allCommodities: [],
  checkLandMode: false,
  bookmarks: loadBookmarks(),
  lastSites: null,           // last GeoJSON for GPX export
  seq: { sites: 0, mines: 0, claims: 0, mindat: 0 }, // stale-response guards
};

/* ---------- map ---------- */
const map = L.map("map", { worldCopyJump: true }).setView([34.2, -111.7], 7); // start over AZ
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);
L.control.scale({ imperial: true }).addTo(map);

const sitesCluster = L.markerClusterGroup({ chunkedLoading: true, maxClusterRadius: 46 });
const minesCluster = L.markerClusterGroup({ chunkedLoading: true, maxClusterRadius: 40 });
const claimsLayer = L.geoJSON(null, {
  style: () => ({ color: CLAIM_COLOR, weight: 1, fillOpacity: 0.12 }),
  pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 5, color: CLAIM_COLOR, fillOpacity: 0.7 }),
  onEachFeature: (f, l) => l.bindPopup(claimPopup(f)),
});
const mindatCluster = L.markerClusterGroup({ chunkedLoading: true, maxClusterRadius: 40 });
let ownershipTiles = null;

map.addLayer(sitesCluster);

/* ---------- helpers ---------- */
/* One status panel, one slot per concern — concurrent layer loads don't
   overwrite each other's progress/errors. */
const statusParts = { global: "Ready. Zoom to an area (z≥6) to load sites." };
function renderStatus() {
  statusLine.innerHTML = Object.values(statusParts).filter(Boolean).join("<br>");
}
function setStatus(msg, spinning = false) {
  statusParts.global = (spinning ? '<span class="spin">⟳</span> ' : "") + msg;
  renderStatus();
}
function setLayerStatus(key, msg, spinning = false) {
  statusParts[key] = msg ? (spinning ? '<span class="spin">⟳</span> ' : "") + msg : "";
  renderStatus();
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function safeUrl(u) {
  // href values from upstream data: allow only http(s)
  return /^https?:\/\//i.test(String(u ?? "")) ? esc(u) : "";
}
const MAX_SPAN_DEG = 6; // wider views get a centered window; upstreams cap at 2000 features anyway
let bboxClamped = false;
function bboxParam() {
  const b = map.getBounds();
  const c = map.getCenter();
  // worldCopyJump can leave lng outside ±180 — normalize to the primary world copy
  const shift = 360 * Math.round(c.lng / 360);
  let w = b.getWest() - shift, s = b.getSouth(), e = b.getEast() - shift, n = b.getNorth();
  const cLng = c.lng - shift;
  bboxClamped = false;
  if (e - w > MAX_SPAN_DEG) { w = cLng - MAX_SPAN_DEG / 2; e = cLng + MAX_SPAN_DEG / 2; bboxClamped = true; }
  if (n - s > MAX_SPAN_DEG) { s = c.lat - MAX_SPAN_DEG / 2; n = c.lat + MAX_SPAN_DEG / 2; bboxClamped = true; }
  w = Math.max(w, -180); e = Math.min(e, 180);
  s = Math.max(s, -90); n = Math.min(n, 90);
  if (w >= e || s >= n) { w = Math.max(-180, e - 0.5); s = Math.max(-90, n - 0.5); }
  return [w.toFixed(4), s.toFixed(4), e.toFixed(4), n.toFixed(4)].join(",");
}
function clampNote() {
  return bboxClamped ? " Showing central ~6° window — zoom in for full coverage." : "";
}
async function api(path, params = {}) {
  const url = new URL(path, location.origin);
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && url.searchParams.set(k, v));
  const resp = await fetch(url);
  if (!resp.ok) {
    let detail = resp.statusText;
    try { detail = (await resp.json()).detail || detail; } catch (e) { /* not json */ }
    throw new Error(detail);
  }
  return resp.json();
}
function selectedStatuses() {
  return [...document.querySelectorAll("#status-filters input:checked")].map((c) => c.value);
}
function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

/* ---------- config + commodities ---------- */
function normName(s) {
  return String(s || "").toLowerCase().replace(/[^a-z0-9 ]+/g, "").replace(/\s+/g, " ").trim();
}
const varietyIndex = new Map(); // norm(name/alias) -> variety entry

async function boot() {
  try {
    state.config = await api("/api/config");
    const dl = $("commodity-list");
    state.allCommodities = state.config.commodities || [];
    state.allCommodities.forEach((c) => {
      const o = document.createElement("option");
      o.value = c;
      dl.appendChild(o);
    });
    (state.config.varieties || []).forEach((v) => {
      varietyIndex.set(normName(v.name), v);
      (v.aliases || []).forEach((a) => varietyIndex.set(normName(a), v));
      const o = document.createElement("option");
      o.value = v.name;
      o.label = v.region ? v.region.label : "";
      dl.appendChild(o);
    });
    if (state.config.ownership) buildOwnershipLegend(state.config.ownership.legend || []);
    if (!state.config.mindat_enabled) {
      $("layer-mindat").parentElement.title = "Set MSCOUT_MINDAT_API_KEY to enable (free key at mindat.org)";
    }
    updateBmCount();
    refreshAll();
  } catch (e) {
    setStatus("Backend unreachable: " + esc(e.message));
  }
}

function buildOwnershipLegend(entries) {
  const el = $("ownership-legend");
  el.innerHTML = entries.map((e) =>
    `<span class="key"><span class="swatch" style="background:${esc(e.color)}"></span>${esc(e.label)}</span>`).join("");
}

/* ---------- commodity chips ---------- */
$("commodity-input").addEventListener("change", () => {
  const v = $("commodity-input").value.trim();
  if (!v) return;
  if (!state.commodities.includes(v)) state.commodities.push(v);
  $("commodity-input").value = "";
  renderChips();
  refreshSites();
});
function renderChips() {
  $("commodity-chips").innerHTML = state.commodities
    .map((c, i) => `<span class="chip" data-i="${i}">${esc(c)}</span>`).join("");
  [...document.querySelectorAll(".chip")].forEach((chip) =>
    chip.addEventListener("click", () => {
      state.commodities.splice(Number(chip.dataset.i), 1);
      renderChips();
      refreshSites();
    }));
  renderVarietyCards();
}

function renderVarietyCards() {
  const box = $("variety-cards");
  box.innerHTML = "";
  state.commodities.forEach((term) => {
    const v = varietyIndex.get(normName(term));
    if (!v) return;
    const card = document.createElement("div");
    card.className = "callout variety-card";
    card.innerHTML = `<b>${esc(v.name)}</b><br>${esc(v.blurb)}<br>
      <span class="hint">⚖ ${esc(v.note)}</span>`;
    if (v.region && v.region.bbox) {
      const btn = document.createElement("button");
      btn.textContent = `➤ Go to ${v.region.label}`;
      btn.style.marginTop = "6px";
      btn.addEventListener("click", () => {
        const [w, s, e, n] = v.region.bbox;
        map.fitBounds([[s, w], [n, e]]);
      });
      card.appendChild(btn);
    }
    box.appendChild(card);
  });
}

/* ---------- data loading ---------- */
const MIN_ZOOM = 6;

async function refreshSites() {
  const seq = ++state.seq.sites;
  if (!$("layer-sites").checked) { sitesCluster.clearLayers(); setLayerStatus("sites", ""); return; }
  if (map.getZoom() < MIN_ZOOM) { setLayerStatus("sites", `Zoom in (z≥${MIN_ZOOM}) to load mineral sites.`); return; }
  const statuses = selectedStatuses();
  if (!statuses.length) {
    sitesCluster.clearLayers();
    setLayerStatus("sites", "All development statuses unchecked — check at least one to see sites.");
    return;
  }
  setLayerStatus("sites", "Loading mineral sites…", true);
  try {
    const gj = await api("/api/sites", {
      bbox: bboxParam(),
      commodities: state.commodities.join(","),
      statuses: statuses.join(","),
    });
    if (seq !== state.seq.sites) return;                 // stale response
    if (!$("layer-sites").checked) { sitesCluster.clearLayers(); setLayerStatus("sites", ""); return; } // unchecked mid-flight
    state.lastSites = gj;
    sitesCluster.clearLayers();
    const markers = (gj.features || []).map((f) => {
      const [lon, lat] = f.geometry.coordinates;
      const color = STATUS_COLORS[f.properties.dev_status] || STATUS_COLORS.Unknown;
      const m = L.circleMarker([lat, lon], { radius: 6, color, weight: 2, fillColor: color, fillOpacity: 0.75 });
      m.bindPopup(sitePopup(f), { maxWidth: 340 });
      return m;
    });
    sitesCluster.addLayers(markers);
    const warn = (gj.warnings || []).length ? " ⚠ " + esc(gj.warnings.join("; ")) + "." : "";
    setLayerStatus("sites", `${markers.length} mineral sites${gj.truncated ? " (truncated — zoom in)" : ""}. ` +
      `${state.commodities.length ? "Filter: " + esc(state.commodities.join(", ")) : "No mineral filter."}` +
      warn + clampNote());
  } catch (e) {
    if (seq === state.seq.sites) setLayerStatus("sites", "Sites failed: " + esc(e.message));
  }
}

async function refreshMines() {
  const seq = ++state.seq.mines;
  if (!$("layer-mines").checked) { minesCluster.clearLayers(); map.removeLayer(minesCluster); setLayerStatus("mines", ""); return; }
  if (map.getZoom() < MIN_ZOOM) return;
  if (!map.hasLayer(minesCluster)) map.addLayer(minesCluster);
  setLayerStatus("mines", "Loading abandoned mine features…", true);
  try {
    const gj = await api("/api/mines", {
      bbox: bboxParam(),
      tailings_only: $("mines-tailings-only").checked ? "1" : "",
    });
    if (seq !== state.seq.mines) return;
    if (!$("layer-mines").checked) { minesCluster.clearLayers(); map.removeLayer(minesCluster); return; }
    minesCluster.clearLayers();
    const markers = (gj.features || []).map((f) => {
      const [lon, lat] = f.geometry.coordinates;
      const isTailings = /tailing|dump|disturbed/i.test(f.properties.ftr_type || "");
      const color = isTailings ? TAILINGS_COLOR : MINE_COLOR;
      const m = L.circleMarker([lat, lon], { radius: 5, color, weight: 2, fillColor: color, fillOpacity: 0.8 });
      m.bindPopup(minePopup(f), { maxWidth: 340 });
      return m;
    });
    minesCluster.addLayers(markers);
    setLayerStatus("mines", `${markers.length} mine features${gj.truncated ? " (truncated — zoom in)" : ""}.` +
      `${clampNote()} Red=workings, orange=tailings/dumps. Never enter mines.`);
  } catch (e) {
    if (seq === state.seq.mines) setLayerStatus("mines", "Mine features failed: " + esc(e.message));
  }
}

async function refreshClaims() {
  const seq = ++state.seq.claims;
  if (!$("layer-claims").checked) { claimsLayer.clearLayers(); map.removeLayer(claimsLayer); setLayerStatus("claims", ""); return; }
  if (map.getZoom() < 8) { setLayerStatus("claims", "Zoom in (z≥8) to load mining claims."); return; }
  if (!map.hasLayer(claimsLayer)) map.addLayer(claimsLayer);
  setLayerStatus("claims", "Loading active mining claims…", true);
  try {
    const gj = await api("/api/claims", { bbox: bboxParam() });
    if (seq !== state.seq.claims) return;
    if (!$("layer-claims").checked) { claimsLayer.clearLayers(); map.removeLayer(claimsLayer); return; }
    claimsLayer.clearLayers();
    claimsLayer.addData(gj);
    setLayerStatus("claims", `${(gj.features || []).length} active claims${gj.truncated ? " (truncated)" : ""}. Don't collect the claimed mineral on someone's claim.`);
  } catch (e) {
    if (seq === state.seq.claims) setLayerStatus("claims", "Claims failed: " + esc(e.message));
  }
}

async function refreshMindat() {
  if (!$("layer-mindat").checked) { mindatCluster.clearLayers(); map.removeLayer(mindatCluster); setLayerStatus("mindat", ""); return; }
  if (!state.config?.mindat_enabled) {
    setStatus('Mindat needs an API key — free at <a href="https://www.mindat.org" target="_blank" rel="noopener">mindat.org</a>, then set MSCOUT_MINDAT_API_KEY.');
    $("layer-mindat").checked = false;
    return;
  }
  if (map.getZoom() < MIN_ZOOM) return;
  if (!map.hasLayer(mindatCluster)) map.addLayer(mindatCluster);
  const seq = ++state.seq.mindat;
  setLayerStatus("mindat", "Loading mindat localities…", true);
  try {
    const gj = await api("/api/mindat/localities", { bbox: bboxParam() });
    if (seq !== state.seq.mindat) return;
    if (!$("layer-mindat").checked) { mindatCluster.clearLayers(); map.removeLayer(mindatCluster); setLayerStatus("mindat", ""); return; }
    mindatCluster.clearLayers();
    const markers = (gj.features || []).map((f) => {
      const [lon, lat] = f.geometry.coordinates;
      const m = L.circleMarker([lat, lon], { radius: 5, color: MINDAT_COLOR, weight: 2, fillColor: MINDAT_COLOR, fillOpacity: 0.8 });
      m.bindPopup(mindatPopup(f), { maxWidth: 340 });
      return m;
    });
    mindatCluster.addLayers(markers);
    setLayerStatus("mindat", `${markers.length} mindat localities.`);
  } catch (e) {
    if (seq === state.seq.mindat) setLayerStatus("mindat", "Mindat failed: " + esc(e.message));
  }
}

function toggleOwnership() {
  if ($("layer-ownership").checked) {
    const cfg = state.config?.ownership;
    if (!cfg) { setStatus("Ownership overlay unavailable (backend has no tile config)."); return; }
    if (!ownershipTiles) {
      ownershipTiles = L.tileLayer(cfg.tiles, { opacity: 0.5, maxZoom: 15, attribution: cfg.attribution || "BLM" });
    }
    ownershipTiles.addTo(map);
    $("ownership-legend").classList.remove("hidden");
  } else {
    if (ownershipTiles) map.removeLayer(ownershipTiles);
    $("ownership-legend").classList.add("hidden");
  }
}

const refreshAll = debounce(() => { refreshSites(); refreshMines(); refreshClaims(); refreshMindat(); }, 350);
map.on("moveend", refreshAll);

/* ---------- popups ----------
   Built as DOM elements: action buttons get real event listeners, so site
   names with quotes/apostrophes can't break out of onclick attributes. */
function popupEl(html, actions) {
  const el = document.createElement("div");
  el.innerHTML = html; // html is built from esc()'d values only
  if (actions && actions.length) {
    const bar = document.createElement("div");
    bar.className = "actions";
    actions.forEach(({ label, fn }) => {
      const btn = document.createElement("button");
      btn.textContent = label;
      btn.addEventListener("click", fn);
      bar.appendChild(btn);
    });
    el.appendChild(bar);
  }
  return el;
}
function sitePopup(f) {
  const p = f.properties;
  const [lon, lat] = f.geometry.coordinates;
  const name = p.name || "Unnamed site";
  const actions = [
    { label: "🏷 Land status here", fn: () => landStatusAt(lat, lon, name) },
    { label: "★ Bookmark", fn: () => addBookmark(lat, lon, name, p.commodity_names || p.commodities || "") },
  ];
  if (p.id) actions.unshift({ label: "🔎 What's here", fn: () => siteDetails(p.id, name) });
  return popupEl(`<b>${esc(name)}</b><br>
    <span class="badge" style="background:${STATUS_COLORS[p.dev_status] || "#6c7a89"};color:#14181d">${esc(p.dev_status || "Unknown")}</span><br>
    <b>Minerals:</b> ${esc(p.commodity_names || p.commodities || "n/a")}<br>
    ${safeUrl(p.url) ? `<a href="${safeUrl(p.url)}" target="_blank" rel="noopener">USGS record ↗</a><br>` : ""}`,
    actions);
}

/* generic renderer for MRDS record sub-objects ({tp:'Ore', material:'Galena'} -> 'Ore: Galena') */
function recordLine(item) {
  if (item == null) return "";
  if (typeof item !== "object") return esc(item);
  const vals = Object.values(item).filter((v) => v != null && v !== "" && typeof v !== "object");
  return esc(vals.join(" — "));
}

window.siteDetails = async function (depId, label) {
  openDrawer(`<h2>${esc(label || "Site")}</h2><p><span class="spin">⟳</span> Loading USGS record…</p>`);
  try {
    const r = await api(`/api/sites/${encodeURIComponent(depId)}`);
    const primary = (r.commodities || []).filter((c) => c.import === "Primary");
    const secondary = (r.commodities || []).filter((c) => c.import !== "Primary");
    let html = `<h2>${esc(label || "Site")}</h2>`;
    const names = (r.names || []).map((n) => `${esc(n.name)}${n.status === "Previous" ? " (previous)" : ""}`);
    if (names.length > 1) html += `<p class="hint">Also known as: ${names.slice(1).join(", ")}</p>`;
    html += `<h3>Minerals / commodities here</h3><table>`;
    primary.forEach((c) => { html += `<tr><td>Primary</td><td><b>${esc(c.commod)}</b>${c.commod_tp ? ` <span class="hint">(${esc(c.commod_tp)})</span>` : ""}</td></tr>`; });
    secondary.forEach((c) => { html += `<tr><td>${esc(c.import || "Other")}</td><td>${esc(c.commod)}</td></tr>`; });
    if (!(r.commodities || []).length) html += `<tr><td colspan="2">No commodity list in this record.</td></tr>`;
    html += `</table>`;
    if ((r.materials || []).length) {
      html += `<h3>Ore / gangue materials</h3><p>${r.materials.map(recordLine).filter(Boolean).join("<br>")}</p>`;
    }
    if ((r.rocks || []).length) {
      html += `<h3>Host rocks</h3><p>${r.rocks.map(recordLine).filter(Boolean).join("<br>")}</p>`;
    }
    const d = r.deposit || {};
    html += `<h3>Deposit</h3><table>
      ${d.dev_st ? `<tr><td>Status</td><td>${esc(d.dev_st)}</td></tr>` : ""}
      ${d.dep_tp ? `<tr><td>Type</td><td>${esc(d.dep_tp)}</td></tr>` : ""}
      ${d.prod_size ? `<tr><td>Production size</td><td>${esc(d.prod_size)}</td></tr>` : ""}
    </table>`;
    const loc = r.location || {};
    if (loc.state_prov || loc.county) {
      html += `<p class="hint">${esc([loc.county, loc.state_prov, loc.country].filter(Boolean).join(", "))}</p>`;
    }
    (r.comment || []).forEach((c) => {
      const full = c.cmt_txt || c.cmt || c.comment || "";
      const txt = full.slice(0, 400);
      if (txt) html += `<div class="callout">${esc(txt)}${full.length > 400 ? "…" : ""}</div>`;
    });
    html += `<div class="actions"><a href="${safeUrl(r.url)}" target="_blank" rel="noopener"><button>Full USGS record ↗</button></a></div>`;
    openDrawer(html);
  } catch (e) {
    openDrawer(`<h2>${esc(label || "Site")}</h2><div class="callout danger">Record load failed: ${esc(e.message)}</div>`);
  }
};
function minePopup(f) {
  const p = f.properties;
  const [lon, lat] = f.geometry.coordinates;
  const name = p.name || "Mine feature";
  return popupEl(`<b>${esc(name)}</b><br>
    <b>Type:</b> ${esc(p.ftr_type || "?")}${p.area_feature ? " (mapped area — marker at centroid)" : ""}<br>
    ${p.topo_name ? `<b>Source topo:</b> ${esc(p.topo_name)} ${esc(p.topo_date || "")}<br>` : ""}
    <div class="callout danger">Never enter abandoned mines — Stay Out, Stay Alive.</div>`,
    [
      { label: "🏷 Land status here", fn: () => landStatusAt(lat, lon, name) },
      { label: "★ Bookmark", fn: () => addBookmark(lat, lon, name, p.ftr_type || "") },
    ]);
}
function claimPopup(f) {
  const p = f.properties;
  return `<b>${esc(p.name || "Mining claim")}</b><br>
    <b>Serial:</b> ${esc(p.serial || "?")}<br>
    <b>Type:</b> ${esc(p.case_type || "?")}<br>
    <b>Status:</b> ${esc(p.disposition || "?")}<br>
    <span class="hint">Active claim: the claimed mineral belongs to the claimant.</span>`;
}
function mindatPopup(f) {
  const p = f.properties;
  return `<b>${esc(p.name || "Locality")}</b><br>
    ${p.minerals ? `<b>Minerals:</b> ${esc(p.minerals)}<br>` : ""}
    ${p.id ? `<a href="https://www.mindat.org/loc-${encodeURIComponent(p.id)}.html" target="_blank" rel="noopener">mindat.org ↗</a>` : ""}`;
}

/* ---------- land status ---------- */
window.landStatusAt = async function (lat, lon, label) {
  openDrawer(`<h2>Land status</h2><p><span class="spin">⟳</span> Checking ${esc(label || "location")}…</p>`);
  try {
    const r = await api("/api/land-status", { lat, lon });
    const badgeClass = { public: "public", private: "private", state_trust: "state-trust", restricted: "warn" }[r.verdict] || "unknown";
    let html = `<h2>Land status</h2>
      <p><span class="badge ${badgeClass}">${esc(r.verdict_label)}</span></p>
      <table>
        <tr><td>Coordinates</td><td>${lat.toFixed(5)}, ${lon.toFixed(5)}</td></tr>
        ${r.manager ? `<tr><td>Managed by</td><td>${esc(r.manager)}</td></tr>` : ""}
        ${r.unit ? `<tr><td>Unit</td><td>${esc(r.unit)}</td></tr>` : ""}
        ${r.designation ? `<tr><td>Designation</td><td>${esc(r.designation)}</td></tr>` : ""}
        ${r.state_name ? `<tr><td>State</td><td>${esc(r.state_name)} (${esc(r.state_code || "")})</td></tr>` : ""}
        ${r.county ? `<tr><td>County</td><td>${esc(r.county)}</td></tr>` : ""}
      </table>`;
    (r.notes || []).forEach((n) => { html += `<div class="callout">${esc(n)}</div>`; });
    if ((r.claims || []).length) {
      html += `<h3>Active claims here</h3><table>` + r.claims.map((c) =>
        `<tr><td>${esc(c.serial || "?")}</td><td>${esc(c.name || "")} — ${esc(c.case_type || "?")}, ${esc(c.disposition || "?")}</td></tr>`).join("") + `</table>`;
    }
    if (r.verdict === "private") {
      html += `<h3>Find &amp; ask the owner</h3>`;
      if (r.owner) {
        html += `<table>
          <tr><td>Assessor-record owner</td><td><b>${esc(r.owner)}</b></td></tr>
          ${r.apn ? `<tr><td>Parcel (APN)</td><td>${esc(r.apn)}</td></tr>` : ""}
        </table>`;
      }
      html += `<div class="callout ok">${esc(r.trespass_note || "")}</div><div class="actions">`;
      (r.owner_lookup || []).forEach((o) => {
        const u = safeUrl(o.url);
        if (u) html += `<a href="${u}" target="_blank" rel="noopener"><button>${esc(o.label)} ↗</button></a>`;
      });
      html += `</div>`;
    }
    if (r.state_code) {
      html += `<div class="actions"><button onclick="showLaws('${esc(r.state_code)}')">⚖ ${esc(r.state_code)} collecting rules</button></div>`;
    }
    html += `<p class="hint">${esc(r.disclaimer || "")}</p>`;
    openDrawer(html);
  } catch (e) {
    openDrawer(`<h2>Land status</h2><div class="callout danger">Lookup failed: ${esc(e.message)}</div>`);
  }
};

map.on("click", (ev) => {
  if (!state.checkLandMode) return;
  landStatusAt(ev.latlng.lat, ev.latlng.lng, "clicked point");
});
$("btn-check-land").addEventListener("click", () => {
  state.checkLandMode = !state.checkLandMode;
  $("btn-check-land").classList.toggle("active", state.checkLandMode);
  map.getContainer().style.cursor = state.checkLandMode ? "help" : "";
});

/* ---------- laws ---------- */
window.showLaws = async function (code) {
  openModal(`<h2>Collecting laws</h2><p><span class="spin">⟳</span> Loading…</p>`);
  try {
    if (!code) {
      const list = await api("/api/laws");
      let html = `<h2>⚖ Collecting laws by state</h2><p class="hint">Click a state. Federal rules (BLM/USFS/NPS) apply inside every state.</p>`;
      list.states.forEach((s) => {
        html += `<p><button onclick="showLaws('${esc(s.code)}')">${esc(s.code)}</button> <b>${esc(s.name)}</b> — ${esc(s.headline)}</p>`;
      });
      openModal(html);
      return;
    }
    const r = await api(`/api/laws/${encodeURIComponent(code)}`);
    let html = `<h2>⚖ ${esc(r.name)} — collecting rules</h2>
      <p>${esc(r.headline)}</p>
      <div class="callout danger">${esc(r.safety)}</div>`;
    (r.rules || []).forEach((rule) => {
      html += `<h4>${esc(rule.title)}</h4><p>${esc(rule.summary)}</p>` +
        rule.citations.map((c) => `<div class="cite"><a href="${safeUrl(c)}" target="_blank" rel="noopener">${esc(c)}</a></div>`).join("");
    });
    html += `<h4>Federal rules (apply in every state)</h4>`;
    Object.values(r.federal || {}).forEach((rule) => {
      html += `<p><b>${esc(rule.title)}.</b> ${esc(rule.summary)}</p>` +
        rule.citations.map((c) => `<div class="cite"><a href="${safeUrl(c)}" target="_blank" rel="noopener">${esc(c)}</a></div>`).join("");
    });
    html += `<h4>Private land</h4><p>${esc(r.trespass)}</p>
      <p class="hint">${esc(r.disclaimer)} Verified ${esc(r.verified)}.</p>`;
    openModal(html);
  } catch (e) {
    openModal(`<h2>Laws</h2><div class="callout danger">${esc(e.message)}</div>`);
  }
};
$("btn-laws").addEventListener("click", () => showLaws(""));

/* ---------- bookmarks ---------- */
window.addBookmark = function (lat, lon, name, extra) {
  state.bookmarks.push({ lat, lon, name, extra, added: new Date().toISOString().slice(0, 10) });
  localStorage.setItem("mscout.bookmarks", JSON.stringify(state.bookmarks));
  updateBmCount();
  setStatus(`Bookmarked “${esc(name)}”.`);
};
function updateBmCount() { $("bm-count").textContent = state.bookmarks.length; }
$("btn-bookmarks").addEventListener("click", () => {
  if (!state.bookmarks.length) { openModal("<h2>★ Bookmarks</h2><p>No bookmarks yet. Use ★ on any site popup.</p>"); return; }
  let html = `<h2>★ Bookmarks</h2><div class="actions"><button onclick="exportBookmarksGpx()">⬇ Export bookmarks GPX</button></div>`;
  state.bookmarks.forEach((b, i) => {
    html += `<p><a href="#" onclick="map.setView([${b.lat},${b.lon}],13);closeModal();return false;">${esc(b.name)}</a>
      <span class="hint">${esc(b.extra || "")} · ${b.lat.toFixed(4)}, ${b.lon.toFixed(4)} · ${esc(b.added)}</span>
      <button onclick="removeBookmark(${i})">remove</button></p>`;
  });
  openModal(html);
});
window.removeBookmark = function (i) {
  state.bookmarks.splice(i, 1);
  localStorage.setItem("mscout.bookmarks", JSON.stringify(state.bookmarks));
  updateBmCount();
  $("btn-bookmarks").click();
};
window.exportBookmarksGpx = function () {
  const wpts = state.bookmarks.map((b) =>
    `<wpt lat="${b.lat}" lon="${b.lon}"><name>${esc(b.name)}</name><desc>${esc(b.extra || "")}</desc></wpt>`).join("\n");
  const gpx = `<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Mineral Scout" xmlns="http://www.topografix.com/GPX/1/1">\n${wpts}\n</gpx>`;
  const blob = new Blob([gpx], { type: "application/gpx+xml" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "mineral-scout-bookmarks.gpx";
  a.click();
  URL.revokeObjectURL(a.href);
};

/* ---------- GPX export of current view ---------- */
$("btn-export").addEventListener("click", () => {
  const params = new URLSearchParams({
    bbox: bboxParam(),
    commodities: state.commodities.join(","),
    statuses: selectedStatuses().join(","),
    include_mines: $("layer-mines").checked ? "1" : "",
  });
  window.open(`/api/export.gpx?${params}`, "_blank");
});

/* ---------- place search (Nominatim) ---------- */
async function goPlace() {
  const q = $("place-search").value.trim();
  if (!q) return;
  setStatus("Searching place…", true);
  try {
    const resp = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(q)}`);
    const results = await resp.json();
    if (!results.length) { setStatus("Place not found."); return; }
    const r = results[0];
    map.setView([Number(r.lat), Number(r.lon)], 10);
    setStatus(`Moved to ${esc(r.display_name)}`);
  } catch (e) {
    setStatus("Place search failed: " + esc(e.message));
  }
}
$("place-go").addEventListener("click", goPlace);
$("place-search").addEventListener("keydown", (e) => { if (e.key === "Enter") goPlace(); });

/* ---------- drawer & modal ---------- */
function openDrawer(html) { $("detail-body").innerHTML = html; $("detail").classList.remove("hidden"); }
$("detail-close").addEventListener("click", () => $("detail").classList.add("hidden"));
function openModal(html) { $("modal-body").innerHTML = html; $("modal").classList.remove("hidden"); }
window.closeModal = function () { $("modal").classList.add("hidden"); };
$("modal-close").addEventListener("click", closeModal);
$("modal").addEventListener("click", (e) => { if (e.target === $("modal")) closeModal(); });

/* ---------- filter listeners ---------- */
document.querySelectorAll("#status-filters input").forEach((c) => c.addEventListener("change", refreshSites));
$("layer-sites").addEventListener("change", refreshSites);
$("layer-mines").addEventListener("change", refreshMines);
$("mines-tailings-only").addEventListener("change", refreshMines);
$("layer-claims").addEventListener("change", refreshClaims);
$("layer-mindat").addEventListener("change", refreshMindat);
$("layer-ownership").addEventListener("change", toggleOwnership);

boot();
