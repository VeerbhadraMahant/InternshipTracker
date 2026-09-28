(() => {
  "use strict";

  const ELIG = {
    "india-ok":        { label: "Open to India",     glyph: "✓", tone: "strong",  eligible: true },
    "open-worldwide":  { label: "Worldwide",         glyph: "◎", tone: "strong",  eligible: true },
    "unknown":         { label: "Unclear",           glyph: "?", tone: "outline", eligible: false },
    "timezone":        { label: "Timezone-bound",    glyph: "◷", tone: "muted",   eligible: false },
    "needs-work-auth": { label: "Needs work auth",   glyph: "⚑", tone: "muted",   eligible: false },
    "restricted":      { label: "Region-restricted", glyph: "✕", tone: "muted",   eligible: false },
    "onsite-abroad":   { label: "On-site abroad",    glyph: "⌂", tone: "muted",   eligible: false },
  };
  const FIELDS = { "software": "Software", "ai-ml": "AI / ML", "data": "Data", "other": "Other" };
  const DEFAULTS = {
    q: "", loc: "all", stipend: "any", sort: "new", closed: false,
    field: ["software", "ai-ml", "data"],
    elig: ["india-ok", "open-worldwide", "unknown"],
  };
  const DAY = 864e5;

  const $ = (id) => document.getElementById(id);
  const storage = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
  };

  let jobs = [];
  let state = readState();
  const lastVisit = storage.get("lastVisit");

  // ---------- state <-> URL ----------
  function readState() {
    const p = new URLSearchParams(location.search);
    const list = (k) => (p.has(k) ? p.get(k).split(",").filter(Boolean) : DEFAULTS[k]);
    return {
      q: p.get("q") || "", loc: p.get("loc") || DEFAULTS.loc, stipend: p.get("stipend") || DEFAULTS.stipend,
      sort: p.get("sort") || DEFAULTS.sort, closed: p.get("closed") === "1",
      field: list("field"), elig: list("elig"),
    };
  }
  function writeState() {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(state)) {
      const d = DEFAULTS[k];
      const same = Array.isArray(v) ? v.slice().sort().join() === d.slice().sort().join() : v === d;
      if (!same) p.set(k, Array.isArray(v) ? v.join(",") : (v === true ? "1" : v));
    }
    const qs = p.toString();
    history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
  }

  // ---------- helpers ----------
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "#");
  function ago(iso) {
    if (!iso) return "";
    const s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.round(s / 60)} min ago`;
    if (s < 86400) return `${Math.round(s / 3600)} h ago`;
    const d = Math.round(s / 86400);
    return d === 1 ? "yesterday" : `${d} days ago`;
  }
  function inr(n) {
    if (n >= 1e5) return `₹${(n / 1e5).toFixed(n % 1e5 ? 1 : 0)}L`;
    if (n >= 1e3) return `₹${Math.round(n / 1e3)}k`;
    return `₹${n}`;
  }
  const isNew = (j) => !!lastVisit && new Date(j.first_seen) > new Date(lastVisit);
  const isFresh = (j) => Date.now() - new Date(j.first_seen).getTime() < DAY;

  function matches(j, s, skip) {
    if (!s.closed && j.status !== "open") return false;
    if (skip !== "loc" && s.loc !== "all" && !j.location_tags.includes(s.loc)) return false;
    if (skip !== "field" && !j.fields.some((f) => s.field.includes(f))) return false;
    if (skip !== "elig" && !s.elig.includes(j.eligibility)) return false;
    if (s.stipend === "disclosed" && j.stipend_inr_month == null) return false;
    if (/^\d+$/.test(s.stipend) && !(j.stipend_inr_month >= +s.stipend)) return false;
    if (s.q) {
      const hay = `${j.company} ${j.title} ${j.locations.join(" ")} ${j.tags.join(" ")} ${j.description}`.toLowerCase();
      if (!s.q.toLowerCase().split(/\s+/).every((w) => hay.includes(w))) return false;
    }
    return true;
  }

  const SORTS = {
    new: (a, b) => (b.first_seen || "").localeCompare(a.first_seen || ""),
    stipend: (a, b) => (b.stipend_inr_month ?? -1) - (a.stipend_inr_month ?? -1) || SORTS.new(a, b),
    company: (a, b) => a.company.localeCompare(b.company) || a.title.localeCompare(b.title),
  };

  // ---------- rendering ----------
  function renderChips(el, defs, key) {
    el.replaceChildren();
    for (const [value, meta] of Object.entries(defs)) {
      const n = jobs.filter((j) => (key === "elig" ? j.eligibility === value : j.fields.includes(value))
        && matches(j, state, key)).length;
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.dataset.v = value;
      b.setAttribute("aria-pressed", state[key].includes(value));
      if (key === "elig") {
        const g = document.createElement("span");
        g.className = "badge__glyph";
        g.textContent = meta.glyph;
        b.append(g);
      }
      b.append(document.createTextNode(typeof meta === "string" ? meta : meta.label));
      const c = document.createElement("span");
      c.className = "chip__n";
      c.textContent = n;
      b.append(c);
      el.append(b);
    }
  }

  function row(j) {
    const tpl = $("row-tpl").content.firstElementChild.cloneNode(true);
    const q = (sel) => tpl.querySelector(sel);
    if (j.status !== "open") tpl.classList.add("is-closed");

    const company = q(".job__company");
    if (isNew(j)) {
      const dot = document.createElement("span");
      dot.className = "dot-new";
      dot.title = "New since your last visit";
      company.append(dot);
    }
    company.append(document.createTextNode(j.company || "—"));
    if (isFresh(j)) {
      const t = document.createElement("span");
      t.className = "tag-new";
      t.textContent = "New";
      company.append(t);
    }
    q(".job__title").textContent = j.title;
    const where = j.locations.slice(0, 2).join(" · ") || (j.location_tags.includes("remote") ? "Remote" : "Location not stated");
    q(".job__meta").textContent = `${where} · found ${ago(j.first_seen)}`;

    const e = ELIG[j.eligibility] || ELIG.unknown;
    const badge = q(".job__elig");
    badge.classList.add(`badge--${e.tone}`);
    const g = document.createElement("span");
    g.className = "badge__glyph";
    g.textContent = e.glyph;
    badge.append(g, document.createTextNode(e.label));
    badge.title = j.eligibility_detail || e.label;

    const pay = q(".job__pay");
    if (j.stipend_inr_month == null) {
      pay.innerHTML = '<small>Stipend</small>Not disclosed';
    } else if (j.stipend_inr_month === 0) {
      pay.textContent = "Unpaid";
    } else {
      const small = document.createElement("small");
      small.textContent = j.stipend_text;
      pay.append(small, document.createTextNode(`≈ ${inr(j.stipend_inr_month)} / mo`));
    }

    const apply = q(".job__apply");
    apply.href = safeUrl(j.url);
    apply.setAttribute("aria-label", `Apply: ${j.title} at ${j.company}`);

    const main = q(".job__main");
    const detail = q(".job__detail");
    main.addEventListener("click", () => {
      const open = detail.hidden;
      if (open && !detail.dataset.filled) fillDetail(detail, j, e);
      detail.hidden = !open;
      main.setAttribute("aria-expanded", open);
    });
    return tpl;
  }

  function fillDetail(detail, j, e) {
    detail.dataset.filled = "1";
    const ev = detail.querySelector(".evidence");
    ev.textContent = j.eligibility_evidence || "The posting says nothing about who can apply from where.";
    const cite = document.createElement("cite");
    cite.textContent = `${e.label}${j.eligibility_detail ? ": " + j.eligibility_detail : ""}`;
    ev.append(cite);
    const desc = j.description || "";
    detail.querySelector(".job__desc").textContent = desc.length > 600 ? desc.slice(0, 600) + "…" : desc;
    const facts = [
      `source ${j.source}`,
      j.posted_at ? `posted ${j.posted_at.slice(0, 10)}` : null,
      `first seen ${(j.first_seen || "").slice(0, 16).replace("T", " ")} UTC`,
      j.fields.map((f) => FIELDS[f] || f).join(", "),
      j.status !== "open" ? "no longer listed" : null,
    ].filter(Boolean);
    detail.querySelector(".job__facts").textContent = facts.join("  ·  ");
  }

  function render() {
    for (const b of $("loc").querySelectorAll("button")) b.setAttribute("aria-pressed", b.dataset.v === state.loc);
    renderChips($("field"), FIELDS, "field");
    renderChips($("elig"), ELIG, "elig");

    const shown = jobs.filter((j) => matches(j, state)).sort(SORTS[state.sort] || SORTS.new);
    const list = $("list");
    list.replaceChildren(...shown.slice(0, 300).map(row));
    list.hidden = shown.length === 0;
    $("empty").hidden = shown.length !== 0;
    $("count").textContent = `${shown.length} role${shown.length === 1 ? "" : "s"}${shown.length > 300 ? " (showing 300)" : ""}`;
    writeState();
  }

  function renderStats(generatedAt) {
    const open = jobs.filter((j) => j.status === "open");
    $("stat-open").textContent = open.length;
    $("stat-new").textContent = lastVisit ? open.filter(isNew).length : open.filter(isFresh).length;
    if (!lastVisit) $("stat-new").previousElementSibling.textContent = "New in the last 24 hours";
    $("stat-eligible").textContent = open.filter((j) => ELIG[j.eligibility]?.eligible
      && j.fields.some((f) => f !== "other")).length;
    const pill = $("freshness");
    pill.textContent = generatedAt ? `Updated ${ago(generatedAt)}` : "No data yet";
    pill.classList.toggle("is-live", generatedAt && Date.now() - new Date(generatedAt) < 3 * 3600e3);
  }

  function renderHealth(status) {
    const scopes = Object.entries(status.scopes || {}).sort(([a, x], [b, y]) => (x.ok === y.ok ? a.localeCompare(b) : x.ok ? 1 : -1));
    const failing = scopes.filter(([, s]) => !s.ok).length;
    $("health-title").textContent = scopes.length
      ? `${scopes.length - failing} of ${scopes.length} sources healthy${failing ? ` · ${failing} failing` : ""}`
      : "No runs recorded yet";
    const body = $("health-body");
    body.replaceChildren(...scopes.map(([name, s]) => {
      const tr = document.createElement("tr");
      const cells = [name, null, s.fetched ?? "–", s.internships ?? "–", s.last_ok ? ago(s.last_ok) : "never"];
      cells.forEach((c, i) => {
        const td = document.createElement("td");
        if (i === 1) {
          td.className = s.ok ? "ok" : "fail";
          td.textContent = s.ok ? "ok" : `failing ×${s.consecutive_failures || 1}`;
          if (!s.ok && s.error) {
            const err = document.createElement("span");
            err.className = "err";
            err.textContent = s.error;
            td.append(err);
          }
        } else td.textContent = c;
        tr.append(td);
      });
      return tr;
    }));
  }

  // ---------- events ----------
  function bind() {
    $("q").value = state.q;
    $("stipend").value = state.stipend;
    $("sort").value = state.sort;
    $("closed").checked = state.closed;
    let t;
    $("q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); render(); }, 120); });
    $("stipend").addEventListener("change", (e) => { state.stipend = e.target.value; render(); });
    $("sort").addEventListener("change", (e) => { state.sort = e.target.value; render(); });
    $("closed").addEventListener("change", (e) => { state.closed = e.target.checked; render(); });
    $("loc").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (b) { state.loc = b.dataset.v; render(); }
    });
    for (const key of ["field", "elig"]) {
      $(key).addEventListener("click", (e) => {
        const b = e.target.closest("button");
        if (!b) return;
        const v = b.dataset.v;
        state[key] = state[key].includes(v) ? state[key].filter((x) => x !== v) : [...state[key], v];
        render();
      });
    }
  }

  async function load(name) {
    for (const base of ["data/", "../data/"]) {
      try {
        const r = await fetch(`${base}${name}`, { cache: "no-cache" });
        if (r.ok) return await r.json();
      } catch { /* try next */ }
    }
    return null;
  }

  async function init() {
    bind();
    const [data, status] = await Promise.all([load("jobs.json"), load("status.json")]);
    jobs = (data && data.jobs) || [];
    renderStats(data && data.generated_at);
    renderHealth(status || {});
    render();
    // Remember this visit once the user has seen the list, so "new" means new to them.
    const mark = () => storage.set("lastVisit", new Date().toISOString());
    addEventListener("pagehide", mark);
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") mark(); });
  }

  init();
})();
