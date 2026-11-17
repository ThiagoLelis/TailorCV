"use strict";

const MESSAGES = {
  en: {
    refresh: "Refresh", stage: "Stage", notes: "Notes", jobInfo: "Job info",
    preview: "Preview", edit: "Edit", save: "Save", saved: "Saved", unsaved: "Unsaved changes",
    cancel: "Cancel", closeTitle: "Why is this application closing?", empty: "Nothing here",
    count: (n) => `${n} application${n === 1 ? "" : "s"}`, noJobInfo: "No job info file.",
    jobPosting: "Job posting", apply: "Apply", discard: "Discard unsaved notes?",
    error: "Something went wrong: ",
    stages: { awaiting: "Awaiting Application", applied: "Applied", "in-process": "In Process", offer: "Offer", closed: "Closed" },
    reasons: { rejected: "Rejected", withdrawn: "Withdrawn", "posting-closed": "Posting closed" },
  },
  pt: {
    refresh: "Atualizar", stage: "Etapa", notes: "Anotações", jobInfo: "Info da vaga",
    preview: "Visualizar", edit: "Editar", save: "Salvar", saved: "Salvo", unsaved: "Alterações não salvas",
    cancel: "Cancelar", closeTitle: "Por que esta candidatura está sendo encerrada?", empty: "Nada aqui",
    count: (n) => `${n} candidatura${n === 1 ? "" : "s"}`, noJobInfo: "Sem arquivo de info da vaga.",
    jobPosting: "Vaga", apply: "Aplicar", discard: "Descartar anotações não salvas?",
    error: "Algo deu errado: ",
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
  const column = el("section", { className: "column" },
    el("h2", {}, el("span", { textContent: t.stages[stage] }), el("span", { textContent: apps.length })),
    ...(apps.length ? apps.map(renderCard) : [el("p", { className: "empty", textContent: t.empty })]),
  );
  column.addEventListener("dragover", (e) => { e.preventDefault(); column.classList.add("drop"); });
  column.addEventListener("dragleave", (e) => { if (!column.contains(e.relatedTarget)) column.classList.remove("drop"); });
  column.addEventListener("drop", (e) => {
    e.preventDefault();
    column.classList.remove("drop");
    const id = e.dataTransfer.getData("text/plain");
    if (id) moveTo(id, stage).catch(fail);
  });
  return column;
}

function renderCard(app) {
  const card = el("button", { type: "button", className: "card", draggable: true },
    el("strong", { textContent: app.company || app.id }),
    el("span", { className: "role muted", textContent: app.role || "" }),
    el("span", { className: "meta" },
      el("span", { textContent: formatDate(app.created) }),
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

async function moveTo(id, stage) {
  const app = state.applications.find((a) => a.id === id);
  if (!app || app.stage === stage) return null;
  let closed_reason;
  if (stage === CLOSED) {
    closed_reason = await askClosedReason();
    if (!closed_reason) return null;
  }
  const moved = await api(applicationUrl(id, "move"), { method: "POST", body: { stage, closed_reason } });
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
  $("#d-created").textContent = formatDate(app.created);
  $("#d-reason").textContent = app.closed_reason ? reasonLabel(app.closed_reason) : "";
  $("#d-stage").replaceChildren(...state.stages.map((s) => el("option", { value: s, textContent: t.stages[s], selected: s === app.stage })));

  const fileUrl = (name) => `/files/${encodeURIComponent(app.id)}/${encodeURIComponent(name)}`;
  const link = (href, text) => el("a", { href, textContent: text, target: "_blank", rel: "noopener" });
  $("#d-links").replaceChildren(
    app.apply_url ? link(app.apply_url, t.apply + " ↗") : null,
    app.job_url && app.job_url !== app.apply_url ? link(app.job_url, t.jobPosting + " ↗") : null,
    ...app.files.filter((f) => f.toLowerCase().endsWith(".pdf")).map((f) => link(fileUrl(f), "📄 " + f.replace(/\.pdf$/i, ""))),
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
    current = { ...current, stage: moved.stage, closed_reason: moved.closed_reason };
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
