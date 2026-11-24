"use strict";

const MESSAGES = {
  en: {
    refresh: "Refresh", stage: "Stage", notes: "Notes", jobInfo: "Job info",
    preview: "Preview", edit: "Edit", save: "Save", saved: "Saved", unsaved: "Unsaved changes",
    cancel: "Cancel", closeTitle: "Why is this application closing?", empty: "Nothing here",
    count: (n) => `${n} application${n === 1 ? "" : "s"}`, noJobInfo: "No job info file.",
    jobPosting: "Job posting", apply: "Apply", openFolder: "Open folder", discard: "Discard unsaved notes?",
    error: "Something went wrong: ",
    fit: (n) => `Fit ${n}/5`, sortByFit: "Sort by Fit", sortByFitTitle: "Forget the order you set by hand and sort this column by Fit",
    lessThanDay: "< 1 d", days: (n) => `${n} d`, timeInStage: "Time in this column",
    timePerColumn: "Time spent in each column", sinceApplied: "Time since applying", created: (d) => `Created ${d}`,
    toResponse: "Until a response", toOffer: "Until an offer",
    noResponse: (span) => `no response · closed after ${span}`,
    stages: { awaiting: "Awaiting Application", applied: "Applied", "in-process": "In Process", offer: "Offer", closed: "Closed" },
    reasons: { rejected: "Rejected", withdrawn: "Withdrawn", "posting-closed": "Posting closed" },
  },
  pt: {
    refresh: "Atualizar", stage: "Etapa", notes: "Anotações", jobInfo: "Info da vaga",
    preview: "Visualizar", edit: "Editar", save: "Salvar", saved: "Salvo", unsaved: "Alterações não salvas",
    cancel: "Cancelar", closeTitle: "Por que esta candidatura está sendo encerrada?", empty: "Nada aqui",
    count: (n) => `${n} candidatura${n === 1 ? "" : "s"}`, noJobInfo: "Sem arquivo de info da vaga.",
    jobPosting: "Vaga", apply: "Aplicar", openFolder: "Abrir pasta", discard: "Descartar anotações não salvas?",
    error: "Algo deu errado: ",
    fit: (n) => `Fit ${n}/5`, sortByFit: "Ordenar por Fit", sortByFitTitle: "Esquecer a ordem manual e ordenar esta coluna por Fit",
    lessThanDay: "< 1 d", days: (n) => `${n} d`, timeInStage: "Tempo nesta coluna",
    timePerColumn: "Tempo em cada coluna", sinceApplied: "Tempo desde a aplicação", created: (d) => `Criado em ${d}`,
    toResponse: "Até a resposta", toOffer: "Até a oferta",
    noResponse: (span) => `sem resposta · encerrada após ${span}`,
    stages: { awaiting: "Esperando aplicação", applied: "Aplicado", "in-process": "Em processo", offer: "Oferta", closed: "Encerrado" },
    reasons: { rejected: "Rejeitado", withdrawn: "Desisti", "posting-closed": "Vaga fechada" },
  },
};

const lang = (navigator.language || "en").toLowerCase().startsWith("pt") ? "pt" : "en";
const t = MESSAGES[lang];
document.documentElement.lang = lang === "pt" ? "pt-BR" : "en";

const $ = (sel) => document.querySelector(sel);
const el = (tag, props = {}, ...children) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children.filter((c) => c != null));
  return node;
};

const CLOSED = "closed"; // the only Stage that needs a closed_reason
let state = { stages: [], closedReasons: [], applications: [] };
let current = null; // detail of the open Application
let savedNotes = "";

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

const fail = (err) => alert(t.error + err.message);
const reasonLabel = (reason) => t.reasons[reason] || reason;
const applicationUrl = (id, action = "") => `/api/applications/${encodeURIComponent(id)}${action && "/" + action}`;
// job_info.md holds text scraped from job pages: never inject its HTML unsanitized.
const renderMarkdown = (text) => DOMPurify.sanitize(marked.parse(text || ""));
const formatDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  return isNaN(d) ? iso : d.toLocaleDateString(lang === "pt" ? "pt-BR" : "en-US", { day: "2-digit", month: "short", year: "numeric" });
};

// Fit: how well the candidate matches the Job Posting, 1-5, set by the CV skill. Ignore anything else.
const fitOf = (app) => (/^[1-5]$/.test(String(app.fit ?? "").trim()) ? Number(app.fit) : null);
function renderFit(app) {
  const fit = fitOf(app);
  if (!fit) return null;
  return el("span", { className: `fit fit-${fit}`, textContent: "★".repeat(fit) + "☆".repeat(5 - fit), title: t.fit(fit), ariaLabel: t.fit(fit) });
}

/* ---------- Time in Stage (docs/adr/0003) ---------- */

// Frontmatter field holding when an Application last entered each Stage, in Stage order.
const ENTERED = { awaiting: "created", applied: "applied_at", "in-process": "in_process_at", offer: "offer_at", closed: "closed_at" };
const DONE = new Set(["offer", CLOSED]); // no running time in these
const DAY = 24 * 60 * 60 * 1000;

// Local time `YYYY-MM-DDTHH:MM`, or a date alone (hand-filled) read as local midnight.
const parseStamp = (value) => {
  if (!value) return null;
  const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? value + "T00:00" : value);
  return isNaN(d) ? null : d;
};
const entered = (app, stage) => parseStamp(app[ENTERED[stage]]);
const between = (from, to) => (from && to && to >= from ? to - from : null);

// Time in `stage`: from its entry to the next later Stage entry on record, or to now if it is the current Stage.
function timeInStage(app, stage) {
  const start = entered(app, stage);
  if (!start) return null;
  if (stage === app.stage) return DONE.has(stage) ? null : between(start, new Date());
  const stages = Object.keys(ENTERED);
  const next = stages.slice(stages.indexOf(stage) + 1).map((s) => entered(app, s)).find(Boolean);
  return between(start, next);
}

const formatSpan = (ms) => (ms == null ? "—" : ms < DAY ? t.lessThanDay : t.days(Math.floor(ms / DAY)));

/* ---------- board ---------- */

async function load() {
  const data = await api("/api/applications");
  state = { stages: data.stages, closedReasons: data.closed_reasons, applications: data.applications };
  render();
}

function render() {
  const board = $("#board");
  board.replaceChildren(...state.stages.map(renderStage));
  $("#count").textContent = t.count(state.applications.length);
}

function renderStage(stage) {
  const apps = state.applications.filter((a) => a.stage === stage);
  // Only offered when someone in the column was placed by hand; otherwise it is already sorted by Fit.
  const sort = apps.some((a) => a.position != null)
    ? el("button", { type: "button", className: "sort", textContent: t.sortByFit, title: t.sortByFitTitle })
    : null;
  sort?.addEventListener("click", () => sortByFit(stage).catch(fail));
  const column = el("section", { className: "column" },
    el("h2", {}, el("span", { textContent: t.stages[stage] }),
      el("span", { className: "column-meta" }, ...[sort].filter(Boolean), el("span", { textContent: apps.length }))),
    ...(apps.length ? apps.map(renderCard) : [el("p", { className: "empty", textContent: t.empty })]),
  );
  column.addEventListener("dragover", (e) => {
    e.preventDefault();
    column.classList.add("drop");
    showMarker(column, dropIndex(column, e.clientY));
  });
  column.addEventListener("dragleave", (e) => { if (!column.contains(e.relatedTarget)) clearDrop(column); });
  column.addEventListener("drop", (e) => {
    e.preventDefault();
    const index = dropIndex(column, e.clientY);
    clearDrop(column);
    const id = e.dataTransfer.getData("text/plain");
    if (id) moveTo(id, stage, index).catch(fail);
  });
  return column;
}

/* ---------- placing within a column ---------- */

// The cards a drop is placed among: the dragged card is left out, matching how the server counts.
const dropTargets = (column) => [...column.querySelectorAll(".card:not(.dragging)")];

function dropIndex(column, y) {
  const cards = dropTargets(column);
  const below = cards.findIndex((c) => { const r = c.getBoundingClientRect(); return y < r.top + r.height / 2; });
  return below === -1 ? cards.length : below;
}

function showMarker(column, index) {
  const marker = column.querySelector(".drop-marker") || el("div", { className: "drop-marker" });
  const cards = dropTargets(column);
  const anchor = cards[index] || null;
  if (anchor) anchor.before(marker); else column.append(marker);
}

function clearDrop(column) {
  column.classList.remove("drop");
  column.querySelector(".drop-marker")?.remove();
}

function renderCard(app) {
  const card = el("button", { type: "button", className: "card", draggable: true },
    el("span", { className: "card-head" }, el("strong", { textContent: app.company || app.id }), renderFit(app)),
    el("span", { className: "role muted", textContent: app.role || "" }),
    el("span", { className: "meta" },
      el("span", { textContent: formatDate(app.created) }),
      DONE.has(app.stage) ? null
        : el("span", { textContent: "⏱ " + formatSpan(timeInStage(app, app.stage)), title: t.timeInStage }),
      app.closed_reason ? el("span", { className: "badge", textContent: reasonLabel(app.closed_reason) }) : null),
  );
  card.addEventListener("click", () => openDetail(app.id).catch(fail));
  card.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", app.id);
    card.classList.add("dragging");
  });
  card.addEventListener("dragend", () => card.classList.remove("dragging"));
  return card;
}

/* ---------- moving between Stages ---------- */

function askClosedReason() {
  const dialog = $("#close-dialog");
  return new Promise((resolve) => {
    $("#reasons").replaceChildren(...state.closedReasons.map((r) =>
      el("button", { value: r, textContent: reasonLabel(r) })));
    dialog.addEventListener("close", () => resolve(state.closedReasons.includes(dialog.returnValue) ? dialog.returnValue : null), { once: true });
    dialog.returnValue = "";
    dialog.showModal();
  });
}

async function sortByFit(stage) {
  const data = await api(`/api/stages/${encodeURIComponent(stage)}/sort-by-fit`, { method: "POST", body: {} });
  state.applications = data.applications;
  render();
}

// Put Application `id` at `index` of `stage`'s column (0 = top), counted without the card itself, where it stays.
// Without an index it takes its Fit's spot in the column.
async function moveTo(id, stage, index = null) {
  const app = state.applications.find((a) => a.id === id);
  if (!app) return null;
  if (app.stage === stage) {
    if (index == null) return null;
    const others = state.applications.filter((a) => a.stage === stage && a.id !== id);
    const at = state.applications.filter((a) => a.stage === stage).indexOf(app);
    if (Math.min(index, others.length) === at) return null; // dropped where it already was
  }
  let closed_reason;
  if (stage === CLOSED && app.stage !== CLOSED) {
    closed_reason = await askClosedReason();
    if (!closed_reason) return null;
  }
  const moved = await api(applicationUrl(id, "move"), { method: "POST", body: { stage, closed_reason, index } });
  await load();
  return moved;
}

/* ---------- detail ---------- */

async function openDetail(id) {
  current = await api(applicationUrl(id));
  savedNotes = current.notes;
  fillDetail();
  selectTab(current.notes.trim() || !current.job_info ? "notes" : "info");
  setPreview(false);
  history.replaceState(null, "", "#" + encodeURIComponent(id));
  if (!$("#detail").open) $("#detail").showModal();
}

function fillDetail() {
  const app = current;
  $("#d-company").textContent = app.company || app.id;
  $("#d-role").textContent = app.role || "";
  $("#d-created").textContent = app.created ? t.created(formatDate(app.created)) : "";
  $("#d-fit").replaceChildren(...[renderFit(app)].filter(Boolean));
  $("#d-reason").textContent = app.closed_reason ? reasonLabel(app.closed_reason) : "";
  $("#d-stage").replaceChildren(...state.stages.map((s) => el("option", { value: s, textContent: t.stages[s], selected: s === app.stage })));

  const fileUrl = (name) => `/files/${encodeURIComponent(app.id)}/${encodeURIComponent(name)}`;
  const link = (href, text) => el("a", { href, textContent: text, target: "_blank", rel: "noopener" });
  $("#d-links").replaceChildren(
    app.apply_url ? link(app.apply_url, t.apply + " ↗") : null,
    app.job_url && app.job_url !== app.apply_url ? link(app.job_url, t.jobPosting + " ↗") : null,
    ...app.files.filter((f) => f.toLowerCase().endsWith(".pdf")).map((f) => link(fileUrl(f), "📄 " + f.replace(/\.pdf$/i, ""))),
    el("button", {
      type: "button", textContent: "📂 " + t.openFolder,
      onclick: () => api(applicationUrl(app.id, "open-folder"), { method: "POST", body: {} }).catch(fail),
    }),
  );

  const applied = entered(app, "applied");
  const closedUnanswered = app.stage === CLOSED && !app.in_process_at && applied;
  const item = (label, value) => el("li", {}, el("span", { className: "muted", textContent: label + " " }), value);
  const group = (title, ...items) => el("div", {}, el("h3", { textContent: title }), el("ul", {}, ...items));
  $("#d-times").replaceChildren(
    group(t.timePerColumn,
      ...state.stages.filter((s) => !DONE.has(s)).map((s) => item(t.stages[s], formatSpan(timeInStage(app, s))))),
    group(t.sinceApplied,
      closedUnanswered
        ? item(t.toResponse, t.noResponse(formatSpan(between(applied, entered(app, CLOSED)))))
        : item(t.toResponse, formatSpan(between(applied, entered(app, "in-process")))),
      item(t.toOffer, formatSpan(between(applied, entered(app, "offer"))))),
  );

  $("#n-text").value = app.notes;
  $("#n-status").textContent = "";
  $("#tab-info").innerHTML = app.job_info ? renderMarkdown(app.job_info) : "";
  if (!app.job_info) $("#tab-info").append(el("p", { className: "muted", textContent: t.noJobInfo }));
}

function selectTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  $("#tab-notes").hidden = name !== "notes";
  $("#tab-info").hidden = name !== "info";
}

function setPreview(on) {
  $("#n-preview").hidden = !on;
  $("#n-text").hidden = on;
  $("#n-toggle").textContent = on ? t.edit : t.preview;
  if (on) $("#n-preview").innerHTML = renderMarkdown($("#n-text").value);
}

const dirty = () => current && $("#n-text").value !== savedNotes;
const showDirty = () => { $("#n-status").textContent = dirty() ? t.unsaved : ""; };
const confirmDiscard = (e) => { if (dirty() && !confirm(t.discard)) e.preventDefault(); };

async function saveNotes() {
  current = await api(applicationUrl(current.id, "notes"), { method: "PUT", body: { notes: $("#n-text").value } });
  savedNotes = current.notes;
  $("#n-status").textContent = t.saved;
}

/* ---------- wiring ---------- */

document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t[node.dataset.i18n]; });
$("#refresh").addEventListener("click", () => load().catch(fail));
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => selectTab(b.dataset.tab)));
$("#n-toggle").addEventListener("click", () => setPreview($("#n-preview").hidden));
$("#n-save").addEventListener("click", () => saveNotes().catch(fail));
$("#n-text").addEventListener("input", showDirty);
$("#n-text").addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); saveNotes().catch(fail); }
});
$("#d-stage").addEventListener("change", async (e) => {
  const stage = e.target.value;
  try {
    const moved = await moveTo(current.id, stage);
    if (!moved) { e.target.value = current.stage; return; }
    const draft = $("#n-text").value;
    // The move returns the new summary; keep only what it lacks, so cleared timestamps disappear too.
    current = { ...moved, notes: current.notes, job_info: current.job_info, files: current.files };
    fillDetail();
    $("#n-text").value = draft;
    showDirty();
  } catch (err) {
    e.target.value = current.stage;
    fail(err);
  }
});
$("#detail").addEventListener("cancel", confirmDiscard);
$("#detail form").addEventListener("submit", confirmDiscard);
$("#detail").addEventListener("close", () => {
  current = null;
  history.replaceState(null, "", location.pathname);
});
window.addEventListener("beforeunload", (e) => { if (dirty()) e.preventDefault(); });

load()
  .then(() => {
    const id = decodeURIComponent(location.hash.slice(1));
    if (id && state.applications.some((a) => a.id === id)) return openDetail(id);
  })
  .catch(fail);
