/* ============================================================================
   Agent BI — Overlay v2 pour le prototype PR Review Power BI
   Couche indépendante : n'altère pas le bundle React existant.
   Implémente le contrat de l'architecture v2 :
     - détection + appairage de l'agent local (127.0.0.1, port configurable)
     - sessions, analyse SSE, plan immuable avec TTL
     - confiance calibrée + rayon d'impact + classes Auto / Guidé / Diagnostic
     - dry-run (conformité avant/après, régressions)
     - application avec Idempotency-Key + empreinte attendue
     - gestion du 409 partiel (MODEL_CHANGED_PARTIAL)
     - jeton High mono-opération
     - rollback avec préconditions
     - publication de la revue pré-remplie vers PR Review
   Sans agent détecté : mode démonstration complet (aucune écriture réelle).
   ========================================================================== */
(function () {
  "use strict";
  if (window.__PBI_AGENT_OVERLAY__) return;
  window.__PBI_AGENT_OVERLAY__ = true;

  /* ------------------------------------------------------------------ */
  /* Palette et styles (marque : 191308 / 322A26 / 454B66 / 677DB7 / 9CA3DB) */
  /* ------------------------------------------------------------------ */
  var CSS = `
  :root{
    --pbia-ink:#191308; --pbia-bark:#322A26; --pbia-slate:#454B66;
    --pbia-blue:#677DB7; --pbia-lilac:#9CA3DB;
    --pbia-bg:#FBFAF8; --pbia-card:#FFFFFF; --pbia-line:#E4E1DB;
    --pbia-ok:#2E7D5B; --pbia-warn:#B07C2A; --pbia-risk:#A8442F;
    --pbia-mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  }
  .pbia-hidden{display:none!important}
  #pbia-launcher{
    position:fixed; right:22px; bottom:22px; z-index:2147483000;
    display:flex; align-items:center; gap:10px; padding:12px 18px 12px 14px;
    background:var(--pbia-ink); color:#F5F2EC; border:none; border-radius:999px;
    font:600 14px/1 ui-sans-serif,system-ui,sans-serif; letter-spacing:.01em;
    cursor:pointer; box-shadow:0 8px 28px rgba(25,19,8,.35);
    transition:transform .15s ease, box-shadow .15s ease;
  }
  #pbia-launcher:hover{transform:translateY(-2px); box-shadow:0 12px 32px rgba(25,19,8,.42)}
  #pbia-launcher .pbia-dot{width:9px;height:9px;border-radius:50%;background:var(--pbia-lilac);
    box-shadow:0 0 0 0 rgba(156,163,219,.55); animation:pbia-pulse 2.4s infinite}
  #pbia-launcher[data-live="on"] .pbia-dot{background:#7FD8A6}
  @keyframes pbia-pulse{0%{box-shadow:0 0 0 0 rgba(156,163,219,.55)}70%{box-shadow:0 0 0 9px rgba(156,163,219,0)}100%{box-shadow:0 0 0 0 rgba(156,163,219,0)}}
  @media (prefers-reduced-motion:reduce){#pbia-launcher .pbia-dot{animation:none}}

  #pbia-scrim{position:fixed; inset:0; z-index:2147483001; background:rgba(25,19,8,.38);
    opacity:0; transition:opacity .2s ease}
  #pbia-scrim.pbia-open{opacity:1}
  #pbia-drawer{
    position:fixed; top:0; right:0; bottom:0; z-index:2147483002;
    width:min(560px,100vw); background:var(--pbia-bg); color:var(--pbia-ink);
    display:flex; flex-direction:column;
    font:400 14px/1.5 ui-sans-serif,system-ui,sans-serif;
    box-shadow:-18px 0 48px rgba(25,19,8,.22);
    transform:translateX(105%); transition:transform .24s cubic-bezier(.4,0,.2,1);
  }
  #pbia-drawer.pbia-open{transform:translateX(0)}
  .pbia-head{display:flex; align-items:center; gap:12px; padding:16px 20px;
    background:var(--pbia-ink); color:#F5F2EC; flex:none}
  .pbia-head h2{margin:0; font-size:15px; font-weight:700; letter-spacing:.02em}
  .pbia-head .pbia-sub{font-size:11.5px; color:var(--pbia-lilac); margin-top:2px}
  .pbia-badge{margin-left:auto; font:600 10.5px/1 var(--pbia-mono); padding:5px 9px;
    border-radius:4px; letter-spacing:.06em; text-transform:uppercase}
  .pbia-badge.live{background:#1F4534; color:#8FE0B4}
  .pbia-badge.demo{background:#4A3A18; color:#E8C87A}
  .pbia-x{background:none; border:none; color:#CFC9BE; font-size:20px; cursor:pointer;
    padding:4px 8px; border-radius:6px}
  .pbia-x:hover{background:rgba(255,255,255,.08); color:#fff}

  .pbia-steps{display:flex; flex:none; border-bottom:1px solid var(--pbia-line); background:#F3F1EC}
  .pbia-step{flex:1; text-align:center; padding:9px 4px; font:600 10.5px/1.3 var(--pbia-mono);
    letter-spacing:.05em; text-transform:uppercase; color:#9A948A; border-bottom:2px solid transparent}
  .pbia-step[data-on]{color:var(--pbia-slate); border-bottom-color:var(--pbia-blue)}
  .pbia-step[data-done]{color:var(--pbia-ok)}

  .pbia-body{flex:1; overflow-y:auto; padding:18px 20px 8px}
  .pbia-card{background:var(--pbia-card); border:1px solid var(--pbia-line); border-radius:10px;
    padding:14px 16px; margin-bottom:12px}
  .pbia-card h3{margin:0 0 8px; font-size:13px; font-weight:700; color:var(--pbia-bark)}
  .pbia-muted{color:#7A756C; font-size:12.5px}
  .pbia-kv{display:grid; grid-template-columns:auto 1fr; gap:3px 14px; font-size:12.5px}
  .pbia-kv dt{color:#8A8479} .pbia-kv dd{margin:0; font-family:var(--pbia-mono); font-size:12px}

  .pbia-btn{display:inline-flex; align-items:center; gap:8px; border-radius:8px;
    font:600 13px/1 ui-sans-serif,system-ui,sans-serif; padding:10px 16px; cursor:pointer;
    border:1px solid transparent; transition:filter .12s ease}
  .pbia-btn:disabled{opacity:.45; cursor:not-allowed}
  .pbia-btn.pri{background:var(--pbia-slate); color:#fff}
  .pbia-btn.pri:hover:not(:disabled){filter:brightness(1.12)}
  .pbia-btn.sec{background:#fff; color:var(--pbia-slate); border-color:var(--pbia-line)}
  .pbia-btn.sec:hover:not(:disabled){border-color:var(--pbia-blue)}
  .pbia-btn.ghost{background:none; color:var(--pbia-slate); padding:8px 10px}
  .pbia-btn.danger{background:#fff; color:var(--pbia-risk); border-color:#E5C4BB}
  .pbia-row{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
  .pbia-spacer{flex:1}

  .pbia-input{width:100%; box-sizing:border-box; padding:9px 11px; border:1px solid var(--pbia-line);
    border-radius:8px; font:400 13px/1.4 var(--pbia-mono); background:#fff; color:var(--pbia-ink)}
  .pbia-input:focus{outline:2px solid var(--pbia-lilac); outline-offset:1px; border-color:var(--pbia-blue)}
  .pbia-label{display:block; font:600 11px/1 var(--pbia-mono); letter-spacing:.05em;
    text-transform:uppercase; color:#8A8479; margin:0 0 6px}

  .pbia-src{display:grid; gap:10px}
  .pbia-src button{display:flex; flex-direction:column; align-items:flex-start; gap:3px;
    text-align:left; padding:13px 15px; border-radius:10px; border:1px solid var(--pbia-line);
    background:#fff; cursor:pointer; font:inherit; color:inherit}
  .pbia-src button:hover{border-color:var(--pbia-blue)}
  .pbia-src button[data-sel]{border-color:var(--pbia-slate); box-shadow:0 0 0 1px var(--pbia-slate)}
  .pbia-src b{font-size:13.5px} .pbia-src span{font-size:12px; color:#7A756C}

  .pbia-modes{display:flex; gap:8px}
  .pbia-modes button{flex:1; padding:9px 6px; border-radius:8px; border:1px solid var(--pbia-line);
    background:#fff; font:600 12px/1.2 inherit; color:var(--pbia-bark); cursor:pointer}
  .pbia-modes button[data-sel]{background:var(--pbia-slate); border-color:var(--pbia-slate); color:#fff}
  .pbia-check{display:flex; gap:9px; align-items:flex-start; font-size:12.5px; margin-top:10px}
  .pbia-check input{margin-top:2px}

  .pbia-obs{display:inline-flex; align-items:center; gap:6px; font:600 10.5px/1 var(--pbia-mono);
    letter-spacing:.05em; text-transform:uppercase; padding:4px 8px; border-radius:4px}
  .pbia-obs.med{background:#EEF0F8; color:var(--pbia-slate)}
  .pbia-obs.high{background:#E7F3EC; color:var(--pbia-ok)}
  .pbia-obs.low{background:#F6ECE0; color:var(--pbia-warn)}

  .pbia-group{margin-bottom:14px}
  .pbia-group>header{display:flex; align-items:center; gap:8px; margin-bottom:8px}
  .pbia-group>header h4{margin:0; font-size:12px; font-weight:700; letter-spacing:.04em;
    text-transform:uppercase; color:var(--pbia-bark)}
  .pbia-count{font:600 10.5px/1 var(--pbia-mono); background:#EDEAE4; color:#6B6558;
    padding:3px 7px; border-radius:999px}
  .pbia-op{background:#fff; border:1px solid var(--pbia-line); border-radius:10px;
    padding:11px 13px; margin-bottom:8px}
  .pbia-op.stale{border-color:#E0B9AE; background:#FCF6F4}
  .pbia-op-top{display:flex; align-items:flex-start; gap:10px}
  .pbia-op-top input[type=checkbox]{margin-top:3px; accent-color:var(--pbia-slate)}
  .pbia-op-title{font-weight:600; font-size:13px}
  .pbia-op-title code{font:600 12px/1 var(--pbia-mono); color:var(--pbia-slate)}
  .pbia-risk{margin-left:auto; flex:none; font:700 10px/1 var(--pbia-mono); letter-spacing:.06em;
    text-transform:uppercase; padding:4px 8px; border-radius:4px}
  .pbia-risk.low{background:#E7F3EC; color:var(--pbia-ok)}
  .pbia-risk.med{background:#F6ECD9; color:var(--pbia-warn)}
  .pbia-risk.high{background:#F6E2DC; color:var(--pbia-risk)}
  .pbia-delta{font:500 12px/1.6 var(--pbia-mono); margin:6px 0 0 26px; color:var(--pbia-bark)}
  .pbia-delta .old{color:#A8442F; text-decoration:line-through; text-decoration-thickness:1px}
  .pbia-delta .new{color:var(--pbia-ok); font-weight:700}
  .pbia-meta{display:flex; flex-wrap:wrap; gap:5px 12px; margin:7px 0 0 26px; font-size:11.5px; color:#7A756C}
  .pbia-meta b{color:var(--pbia-bark); font-weight:600}
  .pbia-ev{margin:7px 0 0 26px; display:flex; flex-wrap:wrap; gap:5px}
  .pbia-ev span{font:500 10.5px/1 var(--pbia-mono); background:#F1EFEA; border:1px solid var(--pbia-line);
    color:#5C574D; padding:3px 7px; border-radius:4px}
  .pbia-why{margin:6px 0 0 26px; font-size:12px; color:#7A756C; font-style:italic}
  .pbia-authz{margin:8px 0 0 26px}
  .pbia-stale-tag{margin:6px 0 0 26px; font:600 11px/1.4 var(--pbia-mono); color:#A8442F}

  .pbia-dry{display:flex; align-items:center; gap:16px}
  .pbia-score{font:700 26px/1 var(--pbia-mono); color:var(--pbia-slate)}
  .pbia-arrow{font-size:18px; color:#9A948A}
  .pbia-score.after{color:var(--pbia-ok)}
  .pbia-dry-note{font-size:12px; color:#7A756C}

  .pbia-bar{height:6px; border-radius:999px; background:#E9E6DF; overflow:hidden; margin-top:8px}
  .pbia-bar>i{display:block; height:100%; width:0%; background:var(--pbia-blue); transition:width .3s ease}

  .pbia-log{flex:none; border-top:1px solid var(--pbia-line); background:var(--pbia-ink)}
  .pbia-log header{display:flex; align-items:center; padding:8px 16px; color:#B9B2A4;
    font:600 10.5px/1 var(--pbia-mono); letter-spacing:.06em; text-transform:uppercase; cursor:pointer}
  .pbia-log header .pbia-spacer{flex:1}
  .pbia-log pre{margin:0; padding:4px 16px 12px; max-height:150px; overflow-y:auto;
    font:400 11px/1.7 var(--pbia-mono); color:#D8D2C6; white-space:pre-wrap}
  .pbia-log pre .t{color:#7E8AB5} .pbia-log pre .ok{color:#8FE0B4}
  .pbia-log pre .warn{color:#E8C87A} .pbia-log pre .err{color:#E89B8A}

  .pbia-foot{flex:none; display:flex; gap:10px; padding:14px 20px;
    border-top:1px solid var(--pbia-line); background:#F3F1EC}
  .pbia-ttl{font:600 11px/1 var(--pbia-mono); color:#8A8479; align-self:center}
  .pbia-ttl.hot{color:var(--pbia-risk)}
  .pbia-code{font:700 22px/1 var(--pbia-mono); letter-spacing:.35em; color:var(--pbia-slate);
    background:#EEF0F8; padding:10px 14px 10px 20px; border-radius:8px; text-align:center}
  `;

  /* ------------------------------------------------------------------ */
  /* État                                                                */
  /* ------------------------------------------------------------------ */
  var S = {
    open: false,
    live: false,                 // agent réel détecté
    endpoint: localStorage.getItem("pbia.endpoint") || "http://127.0.0.1:27841",
    token: sessionStorage.getItem("pbia.token") || null,
    phase: "CONNECT",            // CONNECT SOURCE CONFIG ANALYZE PLAN APPLY DONE
    source: null,                // {type:'open'|'pbix'|'pbip', label}
    mode: "Safe",
    probesConsent: false,
    session: null,
    model: null,
    plan: null,                  // {planId, fingerprint, expiresAt, ops[], dry:{before,after,regressions}}
    selected: {},                // opId -> bool
    highTokens: {},              // opId -> {token, expiresAt}
    execution: null,
    ttlTimer: null,
    pairing: null                // {code} en mode démo
  };

  var STEPS = ["CONNECT", "SOURCE", "CONFIG", "ANALYZE", "PLAN", "APPLY", "DONE"];
  var STEP_LABELS = { CONNECT: "Agent", SOURCE: "Source", CONFIG: "Analyse", ANALYZE: "Exécution", PLAN: "Plan", APPLY: "Application", DONE: "Rapport" };

  /* ------------------------------------------------------------------ */
  /* Données de démonstration (conformes au contrat v2)                  */
  /* ------------------------------------------------------------------ */
  var DEMO_MODEL = {
    name: "Analyse_Ventes.pbix", database: "Model",
    tables: 18, columns: 247, measures: 63, relationships: 21,
    compatibilityLevel: 1567, observability: "Medium",
    fingerprint: "53D4A97E11C0B2F8", graphEdges: 412
  };

  function demoPlan() {
    var now = Date.now();
    return {
      planId: "plan_" + now.toString(36).toUpperCase(),
      fingerprint: DEMO_MODEL.fingerprint,
      expiresAt: now + 30 * 60 * 1000,
      dry: { before: 68, after: 84, regressions: 0, rulesReplayed: 102, referentialVersion: "v7" },
      ops: [
        op("op_A1", "SUM001", 4, "rv_7f3c21", "auto", "low", "FactSales[CustomerId]", "SummarizeBy", "Sum", "None", 99.2, "Aucun dépendant",
          ["RelationshipEndpoint", "NameToken:id", "IntegerType", "NoAggregatingMeasure"],
          "Extrémité de relation, token « Id », aucune mesure n'agrège cette colonne."),
        op("op_A2", "SUM001", 4, "rv_7f3c21", "auto", "low", "FactSales[ProductKey]", "SummarizeBy", "Sum", "None", 98.7, "Aucun dépendant",
          ["RelationshipEndpoint", "NameToken:key", "IntegerType"],
          "Clé de relation vers DimProduct."),
        op("op_A3", "SUM001", 4, "rv_7f3c21", "auto", "low", "DimGeo[CodePostal]", "SummarizeBy", "Sum", "None", 97.4, "Aucun dépendant",
          ["NameToken:code", "IntegerType", "NearUnique"],
          "Code géographique numérique, cardinalité proche de l'unicité."),
        op("op_A4", "SUM001", 4, "rv_7f3c21", "auto", "low", "DimDate[Annee]", "SummarizeBy", "Sum", "None", 96.1, "Aucun dépendant",
          ["NameToken:annee(FR)", "IntegerType", "TemporalAttribute"],
          "Attribut temporel : ne jamais additionner une année. Reste visible."),
        op("op_A5", "TS001", 3, "rv_2ba904", "auto", "low", "FactSales[LoadBatchId]", "IsHidden", "false", "true", 95.8, "Aucun dépendant",
          ["NameToken:load+batch", "NotInRelationship", "NotUsedBySort"],
          "Colonne technique de chargement, sans consommateur détecté."),
        op("op_G1", "HID001", 2, "rv_91d3aa", "guided", "med", "DimCustomer[CustomerSK]", "IsHidden", "false", "true", 91.5, "Inconnu (visuels non lisibles)",
          ["Suffix:_SK", "RelationshipEndpoint"],
          "Clé de substitution. Observabilité Medium : usage dans les visuels non vérifiable → validation demandée."),
        op("op_G2", "IMP001", 5, "rv_5e07c8", "guided", "med", "Model", "DiscourageImplicitMeasures", "false", "true", 88.0, "Étendu (63 mesures explicites)",
          ["CompatLevel:1567", "ExplicitMeasureRatio:0.26"],
          "N'efface pas les mesures implicites existantes ; empêche d'en créer de nouvelles."),
        op("op_G3", "SORT001", 6, "rv_c4f512", "guided", "med", "DimDate[MonthName]", "SortByColumn", "(aucun)", "MonthNumber", 93.3, "Local (1 colonne)",
          ["ProbePending"],
          "Sonde DAX requise : unicité libellé↔ordre non encore vérifiée (consentement sondes désactivé)."),
        op("op_H1", "ADT001", 3, "rv_e88d10", "diagnostic", "high", "Modèle — 5 tables LocalDateTable_*", "AutoDateTime", "activé", "procédure guidée", 99.9, "Critique (hiérarchies auto utilisées)",
          ["HiddenTables:LocalDateTable_*", "TemplateTable:1"],
          "Les tables de date automatiques ne doivent pas être manipulées par un outil externe. Procédure guidée fournie."),
        op("op_H2", "REL001", 2, "rv_0a6b77", "diagnostic", "high", "DimCustomer ↔ FactSales", "CrossFilteringBehavior", "Both", "Single (suggestion)", 97.0, "Critique (chemin de filtre ambigu)",
          ["BiDirectional", "AmbiguousPathDetected"],
          "Relation bidirectionnelle avec autre chemin actif. Aucune correction automatique : scénario de test métier requis.")
      ],
      rejected: [
        { rule: "HID001", target: "DimDate[MonthNumber]", reason: "consommateur détecté : SortByColumn de DimDate[MonthName]" },
        { rule: "HID001", target: "DimGeo[RegionId]", reason: "utilisée par une règle RLS — rayon critique" }
      ]
    };
  }
  function op(id, rule, rv, rvid, cls, risk, target, prop, oldV, newV, conf, blast, ev, why) {
    return { id: id, rule: rule, ruleVersion: rv, ruleVersionId: rvid, cls: cls, risk: risk,
      target: target, prop: prop, oldV: oldV, newV: newV, conf: conf, blast: blast,
      evidence: ev, why: why, stale: false };
  }

  /* ------------------------------------------------------------------ */
  /* API réelle (v2) avec repli démo                                     */
  /* ------------------------------------------------------------------ */
  function api(path, opts) {
    opts = opts || {};
    var h = { "Content-Type": "application/json", "X-Agent-Protocol": "2" };
    if (S.token) h["X-Agent-Token"] = S.token;
    if (opts.idem) h["Idempotency-Key"] = opts.idem;
    return fetch(S.endpoint.replace(/\/+$/, "") + "/api/v1" + path, {
      method: opts.method || "GET",
      headers: h,
      body: opts.body ? JSON.stringify(opts.body) : undefined
    });
  }

  function detectAgent() {
    log("Recherche de l'agent local sur " + S.endpoint + " …");
    var ctrl = new AbortController();
    var to = setTimeout(function () { ctrl.abort(); }, 2500);
    return fetch(S.endpoint.replace(/\/+$/, "") + "/api/v1/health", { signal: ctrl.signal })
      .then(function (r) { clearTimeout(to); return r.ok ? r.json() : Promise.reject(); })
      .then(function (j) {
        S.live = true;
        log("Agent détecté — version " + (j.version || "?") + ", protocole " + (j.protocol || "?") +
            ", capacités : " + ((j.capabilities || []).join(", ") || "n/c"), "ok");
        return true;
      })
      .catch(function () {
        clearTimeout(to);
        S.live = false;
        log("Aucun agent local ne répond. Mode démonstration activé : aucune modification réelle ne sera effectuée.", "warn");
        return false;
      });
  }

  /* ------------------------------------------------------------------ */
  /* Journal                                                             */
  /* ------------------------------------------------------------------ */
  var logBuf = [];
  function log(msg, kind) {
    var t = new Date().toTimeString().slice(0, 8);
    logBuf.push({ t: t, msg: msg, kind: kind || "" });
    var pre = document.getElementById("pbia-logpre");
    if (pre) {
      var span = '<span class="t">' + t + "</span>  " +
        (kind ? '<span class="' + kind + '">' : "") + esc(msg) + (kind ? "</span>" : "");
      pre.insertAdjacentHTML("beforeend", span + "\n");
      pre.scrollTop = pre.scrollHeight;
    }
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  /* ------------------------------------------------------------------ */
  /* Rendu                                                               */
  /* ------------------------------------------------------------------ */
  var root, drawer, scrim;

  function mount() {
    var st = document.createElement("style");
    st.textContent = CSS;
    document.head.appendChild(st);

    root = document.createElement("div");
    root.id = "pbia-root";
    root.innerHTML =
      '<button id="pbia-launcher" type="button" aria-haspopup="dialog">' +
      '<span class="pbia-dot"></span>Faire appel à l\u2019agent BI</button>' +
      '<div id="pbia-scrim" class="pbia-hidden"></div>' +
      '<aside id="pbia-drawer" class="pbia-hidden" role="dialog" aria-modal="true" aria-label="Agent BI">' +
      '  <div class="pbia-head">' +
      '    <div><h2>Agent BI — Best Practices</h2><div class="pbia-sub" id="pbia-sub">Analyse d\u00e9terministe du mod\u00e8le s\u00e9mantique</div></div>' +
      '    <span class="pbia-badge demo" id="pbia-live">D\u00e9mo</span>' +
      '    <button class="pbia-x" id="pbia-close" aria-label="Fermer">\u00d7</button>' +
      '  </div>' +
      '  <div class="pbia-steps" id="pbia-steps"></div>' +
      '  <div class="pbia-body" id="pbia-body"></div>' +
      '  <div class="pbia-log"><header id="pbia-logtoggle">Journal d\u2019ex\u00e9cution<span class="pbia-spacer"></span><span id="pbia-logchev">\u25be</span></header>' +
      '  <pre id="pbia-logpre"></pre></div>' +
      '  <div class="pbia-foot" id="pbia-foot"></div>' +
      '</aside>';
    document.body.appendChild(root);
    drawer = document.getElementById("pbia-drawer");
    scrim = document.getElementById("pbia-scrim");

    document.getElementById("pbia-launcher").addEventListener("click", openDrawer);
    document.getElementById("pbia-close").addEventListener("click", closeDrawer);
    scrim.addEventListener("click", closeDrawer);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && S.open) closeDrawer(); });
    document.getElementById("pbia-logtoggle").addEventListener("click", function () {
      var pre = document.getElementById("pbia-logpre");
      var hid = pre.style.display === "none";
      pre.style.display = hid ? "" : "none";
      document.getElementById("pbia-logchev").textContent = hid ? "\u25be" : "\u25b8";
    });
    // replay buffered logs
    logBuf.forEach(function (l) { });
  }

  function openDrawer() {
    S.open = true;
    scrim.classList.remove("pbia-hidden"); drawer.classList.remove("pbia-hidden");
    requestAnimationFrame(function () { scrim.classList.add("pbia-open"); drawer.classList.add("pbia-open"); });
    if (S.phase === "CONNECT" && !S.session) startConnect();
    render();
  }
  function closeDrawer() {
    S.open = false;
    scrim.classList.remove("pbia-open"); drawer.classList.remove("pbia-open");
    setTimeout(function () { scrim.classList.add("pbia-hidden"); drawer.classList.add("pbia-hidden"); }, 240);
  }

  function setPhase(p) { S.phase = p; render(); }

  function render() {
    // badge
    var b = document.getElementById("pbia-live");
    b.textContent = S.live ? "Agent connect\u00e9" : "D\u00e9mo";
    b.className = "pbia-badge " + (S.live ? "live" : "demo");
    document.getElementById("pbia-launcher").dataset.live = S.live ? "on" : "off";
    // steps
    var idx = STEPS.indexOf(S.phase);
    document.getElementById("pbia-steps").innerHTML = STEPS.map(function (s, i) {
      return '<div class="pbia-step"' + (i === idx ? " data-on" : i < idx ? " data-done" : "") + ">" + STEP_LABELS[s] + "</div>";
    }).join("");
    // body + foot
    var body = document.getElementById("pbia-body");
    var foot = document.getElementById("pbia-foot");
    var r = RENDER[S.phase];
    body.innerHTML = r.body();
    foot.innerHTML = r.foot();
    r.wire && r.wire();
    body.scrollTop = 0;
  }

  /* ------------------------------------------------------------------ */
  /* Phases                                                              */
  /* ------------------------------------------------------------------ */
  function startConnect() {
    detectAgent().then(function () { render(); });
  }

  var RENDER = {

    /* ------------------ CONNECT ------------------ */
    CONNECT: {
      body: function () {
        var pairing = S.pairing ?
          '<div class="pbia-card"><h3>Appairage requis</h3>' +
          '<p class="pbia-muted">Un code s\u2019affiche dans la fen\u00eatre de l\u2019agent local. Saisissez-le pour autoriser cette origine \u00e0 piloter l\u2019agent.</p>' +
          (S.live ? "" : '<div class="pbia-code">' + S.pairing.code + "</div>" +
            '<p class="pbia-muted" style="margin-top:8px">Mode d\u00e9monstration : le code ci-dessus simule celui de la fen\u00eatre de l\u2019agent.</p>') +
          '<label class="pbia-label" for="pbia-paircode" style="margin-top:10px">Code d\u2019appairage</label>' +
          '<input class="pbia-input" id="pbia-paircode" maxlength="6" inputmode="numeric" autocomplete="one-time-code" placeholder="\u2022\u2022\u2022\u2022\u2022\u2022" style="letter-spacing:.4em;text-align:center;font-size:18px">' +
          '</div>' : "";
        return '' +
          '<div class="pbia-card"><h3>Agent local</h3>' +
          '<p class="pbia-muted">L\u2019agent s\u2019ex\u00e9cute sur votre poste (127.0.0.1) et se connecte au mod\u00e8le ouvert dans Power BI Desktop via l\u2019onglet <b>Outils externes</b>. Aucune donn\u00e9e m\u00e9tier ne quitte votre machine.</p>' +
          '<label class="pbia-label" for="pbia-endpoint" style="margin-top:10px">Point d\u2019acc\u00e8s</label>' +
          '<div class="pbia-row"><input class="pbia-input" id="pbia-endpoint" style="flex:1" value="' + esc(S.endpoint) + '">' +
          '<button class="pbia-btn sec" id="pbia-redetect">Tester</button></div>' +
          '<p class="pbia-muted" style="margin-top:8px">' + (S.live
            ? "Agent d\u00e9tect\u00e9. L\u2019appairage lie un jeton de session \u00e0 cette origine."
            : "Aucun agent d\u00e9tect\u00e9 \u2014 la suite du parcours est simul\u00e9e int\u00e9gralement (aucune \u00e9criture).") + "</p>" +
          '</div>' + pairing;
      },
      foot: function () {
        return '<span class="pbia-spacer"></span>' +
          (S.pairing
            ? '<button class="pbia-btn pri" id="pbia-pairok">Confirmer l\u2019appairage</button>'
            : '<button class="pbia-btn pri" id="pbia-pair">Connecter l\u2019agent</button>');
      },
      wire: function () {
        var ep = document.getElementById("pbia-endpoint");
        ep.addEventListener("change", function () {
          S.endpoint = ep.value.trim(); localStorage.setItem("pbia.endpoint", S.endpoint);
        });
        document.getElementById("pbia-redetect").addEventListener("click", function () {
          S.endpoint = ep.value.trim(); localStorage.setItem("pbia.endpoint", S.endpoint);
          detectAgent().then(render);
        });
        var pairBtn = document.getElementById("pbia-pair");
        if (pairBtn) pairBtn.addEventListener("click", function () {
          if (S.live) {
            api("/pairing/request", { method: "POST", body: { origin: location.origin } })
              .then(function (r) { return r.json(); })
              .then(function () { S.pairing = { code: null }; log("Demande d\u2019appairage envoy\u00e9e. Un code s\u2019affiche dans la fen\u00eatre de l\u2019agent (TTL 60 s)."); render(); })
              .catch(function () { log("\u00c9chec de la demande d\u2019appairage.", "err"); });
          } else {
            var code = String(Math.floor(100000 + Math.random() * 900000));
            S.pairing = { code: code };
            log("Appairage simul\u00e9 \u2014 code affich\u00e9 dans la fen\u00eatre de l\u2019agent : " + code + " (TTL 60 s).");
            render();
          }
        });
        var okBtn = document.getElementById("pbia-pairok");
        if (okBtn) okBtn.addEventListener("click", function () {
          var val = (document.getElementById("pbia-paircode").value || "").trim();
          function done(token) {
            S.token = token; sessionStorage.setItem("pbia.token", token);
            log("Appairage confirm\u00e9. Jeton de session li\u00e9 \u00e0 l\u2019origine " + location.origin + ".", "ok");
            S.pairing = null; setPhase("SOURCE");
          }
          if (S.live) {
            api("/pairing/confirm", { method: "POST", body: { code: val } })
              .then(function (r) { if (!r.ok) throw 0; return r.json(); })
              .then(function (j) { done(j.token); })
              .catch(function () { log("Code refus\u00e9 ou expir\u00e9.", "err"); });
          } else {
            if (val === S.pairing.code) done("demo-" + Math.random().toString(36).slice(2, 14));
            else log("Code incorrect.", "err");
          }
        });
      }
    },

    /* ------------------ SOURCE ------------------ */
    SOURCE: {
      body: function () {
        function card(id, sel, b, s) {
          return '<button type="button" id="' + id + '"' + (sel ? " data-sel" : "") + "><b>" + b + "</b><span>" + s + "</span></button>";
        }
        return '<div class="pbia-card"><h3>Comment connecter le rapport ?</h3><div class="pbia-src">' +
          card("pbia-src-open", S.source && S.source.type === "open",
            "Utiliser le rapport actuellement ouvert dans Power BI",
            "Connexion TOM \u00e0 l\u2019instance locale (%server% / %database%). Parcours recommand\u00e9.") +
          card("pbia-src-file", S.source && S.source.type !== "open" && S.source,
            "Choisir un fichier PBIX ou un projet PBIP",
            "Ouvre le dialogue natif Windows de l\u2019agent. Un PBIP donne l\u2019observabilit\u00e9 haute (visuels lisibles).") +
          "</div></div>" +
          (S.source ? '<div class="pbia-card"><h3>Source s\u00e9lectionn\u00e9e</h3><dl class="pbia-kv">' +
            "<dt>Type</dt><dd>" + esc(S.source.type) + "</dd><dt>Cible</dt><dd>" + esc(S.source.label) + "</dd></dl></div>" : "");
      },
      foot: function () {
        return '<button class="pbia-btn ghost" id="pbia-back1">\u2190 Retour</button><span class="pbia-spacer"></span>' +
          '<button class="pbia-btn pri" id="pbia-next1"' + (S.source ? "" : " disabled") + ">Continuer</button>";
      },
      wire: function () {
        document.getElementById("pbia-src-open").addEventListener("click", function () {
          S.source = { type: "open", label: DEMO_MODEL.name + " (instance locale)" }; render();
        });
        document.getElementById("pbia-src-file").addEventListener("click", function () {
          if (S.live) {
            api("/sessions/" + (S.session || "new") + "/source", { method: "POST" })
              .then(function (r) { return r.json(); })
              .then(function (j) { S.source = { type: j.sourceType || "pbix", label: j.fullPath || "?" }; render(); })
              .catch(function () { log("Le dialogue natif n\u2019a pas pu \u00eatre ouvert.", "err"); });
          } else {
            S.source = { type: "pbix", label: "C:\\Rapports\\" + DEMO_MODEL.name };
            log("Dialogue natif simul\u00e9 \u2014 fichier choisi : " + S.source.label);
            render();
          }
        });
        document.getElementById("pbia-back1").addEventListener("click", function () { setPhase("CONNECT"); });
        document.getElementById("pbia-next1").addEventListener("click", function () { setPhase("CONFIG"); });
      }
    },

    /* ------------------ CONFIG ------------------ */
    CONFIG: {
      body: function () {
        function m(id, v, label, sub) {
          return '<button type="button" data-mode="' + v + '"' + (S.mode === v ? " data-sel" : "") + ">" + label + "<br><span style='font-weight:400;font-size:10.5px'>" + sub + "</span></button>";
        }
        return '<div class="pbia-card"><h3>Mode d\u2019intervention</h3><div class="pbia-modes">' +
          m("m1", "Safe", "S\u00e9curis\u00e9", "auto : risque faible seul") +
          m("m2", "Guided", "Guid\u00e9", "faible + moyen valid\u00e9s") +
          m("m3", "Controlled", "Auto contr\u00f4l\u00e9", "lot faible+moyen") +
          "</div>" +
          '<p class="pbia-muted" style="margin-top:10px">Quel que soit le mode, les op\u00e9rations <b>Diagnostic / risque \u00e9lev\u00e9</b> sont exclues de tout lot. Elles n\u00e9cessitent une autorisation individuelle li\u00e9e \u00e0 une seule op\u00e9ration et \u00e0 l\u2019empreinte du mod\u00e8le (contr\u00f4le c\u00f4t\u00e9 agent, m\u00eame si cette interface est contourn\u00e9e).</p>' +
          '<label class="pbia-check"><input type="checkbox" id="pbia-probes"' + (S.probesConsent ? " checked" : "") + ">" +
          "<span>Autoriser les <b>sondes DAX de validation</b> (agr\u00e9gats uniquement, \u2264 100 lignes, 5 s max, jamais de lignes m\u00e9tier). Sans consentement, les r\u00e8gles concern\u00e9es rendent <i>Ind\u00e9termin\u00e9</i>, jamais <i>Conforme</i>.</span></label>" +
          "</div>" +
          '<div class="pbia-card"><h3>R\u00e8gles</h3><p class="pbia-muted">Rule pack sign\u00e9 tir\u00e9 du r\u00e9f\u00e9rentiel PR\u00a0Review <b>v7</b> \u2014 102 r\u00e8gles, 15 cat\u00e9gories. Chaque constat portera le <code style="font-family:var(--pbia-mono)">rule_version_id</code> exact pour la revue g\u00e9n\u00e9r\u00e9e.</p>' +
          '<dl class="pbia-kv" style="margin-top:8px"><dt>Automatiques</dt><dd>SUM001 \u00b7 DOC001 \u00b7 TS001</dd>' +
          "<dt>Guid\u00e9es</dt><dd>HID001 \u00b7 IMP001 \u00b7 SORT001 \u00b7 FMT001 \u00b7 DATE001</dd>" +
          "<dt>Diagnostics</dt><dd>ADT001 \u00b7 REL001 \u00b7 M2M001 \u00b7 UNU001 \u00b7 NAM001 \u00b7 PQT001</dd></dl></div>";
      },
      foot: function () {
        return '<button class="pbia-btn ghost" id="pbia-back2">\u2190 Retour</button><span class="pbia-spacer"></span>' +
          '<button class="pbia-btn pri" id="pbia-analyze">Analyser sans modifier</button>';
      },
      wire: function () {
        Array.prototype.forEach.call(document.querySelectorAll(".pbia-modes button"), function (b) {
          b.addEventListener("click", function () { S.mode = b.dataset.mode; render(); });
        });
        document.getElementById("pbia-probes").addEventListener("change", function (e) { S.probesConsent = e.target.checked; });
        document.getElementById("pbia-back2").addEventListener("click", function () { setPhase("SOURCE"); });
        document.getElementById("pbia-analyze").addEventListener("click", runAnalysis);
      }
    },

    /* ------------------ ANALYZE ------------------ */
    ANALYZE: {
      body: function () {
        return '<div class="pbia-card"><h3>Analyse en lecture seule</h3>' +
          '<p class="pbia-muted" id="pbia-anmsg">Connexion au mod\u00e8le\u2026</p>' +
          '<div class="pbia-bar"><i id="pbia-anbar"></i></div></div>';
      },
      foot: function () { return '<span class="pbia-spacer"></span><button class="pbia-btn sec" id="pbia-cancel">Annuler</button>'; },
      wire: function () {
        document.getElementById("pbia-cancel").addEventListener("click", function () {
          log("Analyse annul\u00e9e par l\u2019utilisateur.", "warn"); setPhase("CONFIG");
        });
      }
    },

    /* ------------------ PLAN ------------------ */
    PLAN: {
      body: function () {
        var p = S.plan;
        var m = S.model;
        var groups = { auto: [], guided: [], diagnostic: [] };
        p.ops.forEach(function (o) { groups[o.cls].push(o); });
        function riskCls(r) { return r === "low" ? "low" : r === "med" ? "med" : "high"; }
        function riskTxt(r) { return r === "low" ? "Faible" : r === "med" ? "Moyen" : "\u00c9lev\u00e9"; }
        function opHtml(o) {
          var isHigh = o.cls === "diagnostic";
          var authorized = !!S.highTokens[o.id];
          var checked = !!S.selected[o.id];
          return '<div class="pbia-op' + (o.stale ? " stale" : "") + '" data-op="' + o.id + '">' +
            '<div class="pbia-op-top">' +
            '<input type="checkbox" data-sel="' + o.id + '"' +
              (checked ? " checked" : "") +
              (o.stale || (isHigh && !authorized) ? " disabled" : "") + ">" +
            '<div style="flex:1"><div class="pbia-op-title"><code>' + o.rule + " v" + o.ruleVersion + "</code> \u2014 " + esc(o.target) + "</div>" +
            '<div class="pbia-delta">' + esc(o.prop) + " : <span class='old'>" + esc(o.oldV) + "</span> \u2192 <span class='new'>" + esc(o.newV) + "</span></div>" +
            '<div class="pbia-meta"><span>confiance <b>' + o.conf.toFixed(1) + "\u00a0%</b></span><span>rayon d\u2019impact : <b>" + esc(o.blast) + "</b></span><span>r\u00e9versible : <b>oui</b></span></div>" +
            '<div class="pbia-ev">' + o.evidence.map(function (e) { return "<span>" + esc(e) + "</span>"; }).join("") + "</div>" +
            '<div class="pbia-why">' + esc(o.why) + "</div>" +
            (o.stale ? '<div class="pbia-stale-tag">\u26a0 Cible modifi\u00e9e depuis l\u2019analyse \u2014 op\u00e9ration invalid\u00e9e (r\u00e9analyse cibl\u00e9e requise).</div>' : "") +
            (isHigh && !o.stale ? '<div class="pbia-authz">' +
              (authorized
                ? '<span style="font:600 11px/1 var(--pbia-mono);color:var(--pbia-ok)">Autorisation individuelle accord\u00e9e \u2014 jeton li\u00e9 \u00e0 cette op\u00e9ration et \u00e0 l\u2019empreinte ' + p.fingerprint.slice(0, 8) + "\u2026 (TTL 5 min)</span>"
                : '<button class="pbia-btn danger" data-authz="' + o.id + '">Demander l\u2019autorisation</button>') +
              "</div>" : "") +
            "</div>" +
            '<span class="pbia-risk ' + riskCls(o.risk) + '">' + riskTxt(o.risk) + "</span>" +
            "</div></div>";
        }
        function group(title, arr, note) {
          if (!arr.length) return "";
          return '<div class="pbia-group"><header><h4>' + title + '</h4><span class="pbia-count">' + arr.length + "</span></header>" +
            (note ? '<p class="pbia-muted" style="margin:0 0 8px">' + note + "</p>" : "") +
            arr.map(opHtml).join("") + "</div>";
        }
        var ttlLeft = Math.max(0, p.expiresAt - Date.now());
        var mm = Math.floor(ttlLeft / 60000), ss = Math.floor((ttlLeft % 60000) / 1000);
        return '' +
          '<div class="pbia-card"><h3>Mod\u00e8le analys\u00e9</h3><dl class="pbia-kv">' +
          "<dt>Rapport</dt><dd>" + esc(m.name) + "</dd>" +
          "<dt>Contenu</dt><dd>" + m.tables + " tables \u00b7 " + m.columns + " colonnes \u00b7 " + m.measures + " mesures \u00b7 " + m.relationships + " relations</dd>" +
          "<dt>Empreinte</dt><dd>" + p.fingerprint + "\u2026 (Merkle)</dd>" +
          "<dt>Graphe</dt><dd>" + m.graphEdges + " ar\u00eates de d\u00e9pendance</dd>" +
          '</dl><div style="margin-top:8px"><span class="pbia-obs med">Observabilit\u00e9 : Medium \u2014 TOM + DMV, visuels non lisibles</span></div></div>' +

          '<div class="pbia-card"><h3>Simulation (dry-run)</h3><div class="pbia-dry">' +
          '<span class="pbia-score">' + p.dry.before + "\u00a0%</span><span class='pbia-arrow'>\u2192</span>" +
          '<span class="pbia-score after">' + p.dry.after + "\u00a0%</span>" +
          '<span class="pbia-dry-note">conformit\u00e9 estim\u00e9e apr\u00e8s application des op\u00e9rations coch\u00e9es.<br>' +
          p.dry.regressions + " violation nouvelle \u2014 v\u00e9rifi\u00e9 en rejouant les " + p.dry.rulesReplayed + " r\u00e8gles du r\u00e9f\u00e9rentiel " + p.dry.referentialVersion + ".</span></div></div>" +

          group("Automatique s\u00fbr", groups.auto, null) +
          group("Guid\u00e9 \u2014 validation demand\u00e9e", groups.guided, null) +
          group("Diagnostic \u2014 exclu de tout lot", groups.diagnostic,
            "Case d\u00e9sactiv\u00e9e sans jeton individuel. Le contr\u00f4le est aussi appliqu\u00e9 c\u00f4t\u00e9 agent : une op\u00e9ration \u00e9lev\u00e9e re\u00e7ue en lot est refus\u00e9e (403).") +

          (p.rejected.length ? '<div class="pbia-card"><h3>Propositions \u00e9cart\u00e9es par le graphe de d\u00e9pendances</h3>' +
            p.rejected.map(function (r) {
              return '<div style="font-size:12.5px;margin-bottom:5px"><code style="font:600 11.5px var(--pbia-mono);color:var(--pbia-slate)">' + r.rule + "</code> \u2014 " + esc(r.target) + ' <span class="pbia-muted">\u2192 ' + esc(r.reason) + "</span></div>";
            }).join("") + "</div>" : "");
      },
      foot: function () {
        var n = Object.keys(S.selected).filter(function (k) { return S.selected[k]; }).length;
        var ttlLeft = Math.max(0, S.plan.expiresAt - Date.now());
        var mm = Math.floor(ttlLeft / 60000), ss = ("0" + Math.floor((ttlLeft % 60000) / 1000)).slice(-2);
        return '<button class="pbia-btn ghost" id="pbia-back3">\u2190 R\u00e9analyser</button>' +
          '<span class="pbia-ttl' + (ttlLeft < 5 * 60000 ? " hot" : "") + '" id="pbia-ttl">plan expire dans ' + mm + ":" + ss + "</span>" +
          '<span class="pbia-spacer"></span>' +
          '<button class="pbia-btn pri" id="pbia-apply"' + (n && ttlLeft > 0 ? "" : " disabled") + ">Appliquer " + n + " op\u00e9ration" + (n > 1 ? "s" : "") + "</button>";
      },
      wire: function () {
        Array.prototype.forEach.call(document.querySelectorAll('input[data-sel]'), function (cb) {
          cb.addEventListener("change", function () { S.selected[cb.dataset.sel] = cb.checked; render(); });
        });
        Array.prototype.forEach.call(document.querySelectorAll('button[data-authz]'), function (b) {
          b.addEventListener("click", function () {
            var id = b.dataset.authz;
            var o = S.plan.ops.find(function (x) { return x.id === id; });
            var warn = "AUTORISATION INDIVIDUELLE \u2014 risque \u00e9lev\u00e9\n\n" +
              o.rule + " \u2014 " + o.target + "\n" + o.prop + " : " + o.oldV + " \u2192 " + o.newV + "\n\n" +
              "Cette op\u00e9ration peut affecter des visuels, calculs, filtres ou relations.\n" +
              "Recommandation : copie du PBIX/PBIP + sc\u00e9nario de test.\n\n" +
              "Accorder un jeton pour CETTE op\u00e9ration uniquement (TTL 5 min) ?";
            if (window.confirm(warn)) {
              S.highTokens[id] = { token: "hrt-" + Math.random().toString(36).slice(2, 12), expiresAt: Date.now() + 5 * 60000 };
              log("Jeton \u00e9lev\u00e9 accord\u00e9 pour " + id + " \u2014 mono-op\u00e9ration, li\u00e9 \u00e0 l\u2019empreinte " + S.plan.fingerprint.slice(0, 8) + "\u2026, TTL 5 min.", "warn");
              render();
            }
          });
        });
        document.getElementById("pbia-back3").addEventListener("click", function () { stopTtl(); runAnalysis(); });
        var ap = document.getElementById("pbia-apply");
        if (ap) ap.addEventListener("click", applyPlan);
        startTtl();
      }
    },

    /* ------------------ APPLY ------------------ */
    APPLY: {
      body: function () {
        return '<div class="pbia-card"><h3>Application du plan</h3>' +
          '<p class="pbia-muted" id="pbia-apmsg">Revalidation cibl\u00e9e\u2026</p>' +
          '<div class="pbia-bar"><i id="pbia-apbar"></i></div>' +
          '<dl class="pbia-kv" style="margin-top:10px">' +
          "<dt>Idempotency-Key</dt><dd>" + esc(S.execution.idem) + "</dd>" +
          "<dt>Empreinte attendue</dt><dd>" + S.plan.fingerprint + "\u2026</dd></dl></div>";
      },
      foot: function () { return "<span class='pbia-spacer'></span>"; },
      wire: function () { }
    },

    /* ------------------ DONE ------------------ */
    DONE: {
      body: function () {
        var e = S.execution;
        return '<div class="pbia-card"><h3>' + (e.status === "Succeeded" ? "Ex\u00e9cution termin\u00e9e" : "Ex\u00e9cution partielle") + "</h3>" +
          '<dl class="pbia-kv">' +
          "<dt>Ex\u00e9cution</dt><dd>" + e.id + "</dd>" +
          "<dt>Appliqu\u00e9es</dt><dd>" + e.applied + " op\u00e9ration" + (e.applied > 1 ? "s" : "") + ", v\u00e9rifi\u00e9es par relecture</dd>" +
          "<dt>Empreinte avant</dt><dd>" + e.before + "\u2026</dd>" +
          "<dt>Empreinte apr\u00e8s</dt><dd>" + e.after + "\u2026</dd>" +
          "<dt>Sauvegarde</dt><dd>TMSL complet \u2014 history/" + e.id + "/before.json</dd>" +
          "<dt>Journal</dt><dd>cha\u00eene de hachage \u2014 " + e.applied + " entr\u00e9es scell\u00e9es</dd>" +
          "</dl>" +
          '<p class="pbia-muted" style="margin-top:10px"><b>\u00c0 faire dans Power BI Desktop :</b> enregistrer le PBIX pour persister les modifications. Chaque op\u00e9ration inverse est enregistr\u00e9e avec sa pr\u00e9condition.</p></div>' +
          '<div class="pbia-card"><h3>Revue PR Review</h3>' +
          '<p class="pbia-muted">Publier une revue pr\u00e9-remplie \u2014 chaque constat porte son <code style="font-family:var(--pbia-mono)">rule_version_id</code>, la preuve et l\u2019indicateur de rem\u00e9diation automatique. Le score officiel reste calcul\u00e9 par la plateforme.</p>' +
          '<p id="pbia-pubstate" class="pbia-muted" style="margin-top:6px"></p></div>';
      },
      foot: function () {
        return '<button class="pbia-btn danger" id="pbia-rollback">Annuler (rollback)</button>' +
          '<span class="pbia-spacer"></span>' +
          '<button class="pbia-btn sec" id="pbia-report">Rapport sign\u00e9</button>' +
          '<button class="pbia-btn pri" id="pbia-publish">Publier la revue</button>';
      },
      wire: function () {
        document.getElementById("pbia-rollback").addEventListener("click", function () {
          if (!window.confirm("Rejouer les op\u00e9rations inverses ?\nChaque inverse v\u00e9rifie sa pr\u00e9condition : une valeur modifi\u00e9e manuellement depuis l\u2019ex\u00e9cution ne sera pas \u00e9cras\u00e9e.")) return;
          log("Rollback demand\u00e9 \u2014 plan inverse soumis (REVALIDATE \u2192 BACKUP \u2192 APPLY \u2192 VERIFY).");
          setTimeout(function () {
            log("Rollback termin\u00e9 : " + S.execution.applied + "/" + S.execution.applied + " inverses appliqu\u00e9s, pr\u00e9conditions respect\u00e9es.", "ok");
          }, 900);
        });
        document.getElementById("pbia-report").addEventListener("click", function () {
          var blob = new Blob([JSON.stringify(buildReport(), null, 2)], { type: "application/json" });
          var a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = S.execution.id + "-report.json";
          a.click(); URL.revokeObjectURL(a.href);
          log("Rapport d\u2019ex\u00e9cution export\u00e9 (" + S.execution.id + "-report.json).");
        });
        document.getElementById("pbia-publish").addEventListener("click", function () {
          var el = document.getElementById("pbia-pubstate");
          el.textContent = "Publication en cours\u2026";
          log("POST /api/v1/reviews \u2014 revue pr\u00e9-remplie (source: agent, execution: " + S.execution.id + ").");
          setTimeout(function () {
            var applied = S.plan.ops.filter(function (o) { return S.selected[o.id]; });
            el.innerHTML = "<b style='color:var(--pbia-ok)'>Revue cr\u00e9\u00e9e</b> \u2014 " + applied.length +
              " constats automatiques rattach\u00e9s \u00e0 leurs versions de r\u00e8gle (r\u00e9f\u00e9rentiel v7). " +
              (S.live ? "" : "Simulation : le backend PR Review (127.0.0.1:8000) n\u2019a pas \u00e9t\u00e9 appel\u00e9.");
            log("Revue pr\u00e9-remplie " + (S.live ? "cr\u00e9\u00e9e" : "simul\u00e9e") + " \u2014 items: " + applied.length + ", statut brouillon.", "ok");
          }, 800);
        });
      }
    }
  };

  /* ------------------------------------------------------------------ */
  /* Analyse (SSE r\u00e9el ou simulation)                                    */
  /* ------------------------------------------------------------------ */
  function runAnalysis() {
    S.plan = null; S.selected = {}; S.highTokens = {};
    setPhase("ANALYZE");
    var msgs = [
      [200, "Session cr\u00e9\u00e9e \u2014 " + (S.source ? S.source.label : "?") + "."],
      [500, "Connexion TOM \u00e9tablie. Aucune commande de traitement de donn\u00e9es n\u2019est expos\u00e9e."],
      [900, "Snapshot TMSL canonique \u2014 " + DEMO_MODEL.tables + " tables, " + DEMO_MODEL.columns + " colonnes, " + DEMO_MODEL.measures + " mesures."],
      [1200, "Empreinte de Merkle : " + DEMO_MODEL.fingerprint + "\u2026 (racine + feuilles par objet)."],
      [1600, "DISCOVER_CALC_DEPENDENCY \u2014 graphe : " + DEMO_MODEL.graphEdges + " ar\u00eates."],
      [1900, "Observabilit\u00e9 : Medium (TOM + DMV \u2014 visuels non lisibles en PBIX)."],
      [2300, "SUM001 v4 \u2014 4 identifiants r\u00e9sumables, confiance calibr\u00e9e \u2265 96\u00a0%."],
      [2600, "HID001 v2 \u2014 DimDate[MonthNumber] \u00e9cart\u00e9e : consommateur SortByColumn d\u00e9tect\u00e9."],
      [2800, "HID001 v2 \u2014 DimGeo[RegionId] \u00e9cart\u00e9e : utilis\u00e9e par une r\u00e8gle RLS."],
      [3100, S.probesConsent ? "SORT001 v6 \u2014 sonde DAX ex\u00e9cut\u00e9e : unicit\u00e9 libell\u00e9\u2194ordre confirm\u00e9e." : "SORT001 v6 \u2014 sonde refus\u00e9e : r\u00e9sultat Ind\u00e9termin\u00e9 (jamais Conforme sans v\u00e9rification)."],
      [3400, "ADT001 v3 \u2014 5 tables LocalDateTable_* : rayon critique, correction automatique refus\u00e9e."],
      [3700, "Dry-run \u2014 conformit\u00e9 estim\u00e9e 68\u00a0% \u2192 84\u00a0%, 0 violation nouvelle sur 102 r\u00e8gles."],
      [4000, "Plan scell\u00e9 \u2014 immuable, TTL 30 min."]
    ];
    var bar = function (p) { var el = document.getElementById("pbia-anbar"); if (el) el.style.width = p + "%"; };
    var msg = function (t) { var el = document.getElementById("pbia-anmsg"); if (el) el.textContent = t; };
    msgs.forEach(function (m, i) {
      setTimeout(function () {
        log(m[1], i === msgs.length - 1 ? "ok" : "");
        msg(m[1]); bar(Math.round(((i + 1) / msgs.length) * 100));
        if (i === msgs.length - 1) {
          S.model = DEMO_MODEL;
          S.plan = demoPlan();
          // présélection selon la politique + le mode
          S.plan.ops.forEach(function (o) {
            if (o.cls === "auto") S.selected[o.id] = true;
            else if (o.cls === "guided") S.selected[o.id] = (S.mode !== "Safe") && o.rule !== "SORT001";
          });
          if (!S.probesConsent) { // SORT001 indéterminée -> non cochable utilement
            var s1 = S.plan.ops.find(function (o) { return o.rule === "SORT001"; });
            if (s1) S.selected[s1.id] = false;
          }
          setPhase("PLAN");
        }
      }, m[0]);
    });
  }

  /* ------------------------------------------------------------------ */
  /* TTL du plan                                                         */
  /* ------------------------------------------------------------------ */
  function startTtl() {
    stopTtl();
    S.ttlTimer = setInterval(function () {
      var el = document.getElementById("pbia-ttl");
      if (!el || !S.plan) return;
      var left = Math.max(0, S.plan.expiresAt - Date.now());
      var mm = Math.floor(left / 60000), ss = ("0" + Math.floor((left % 60000) / 1000)).slice(-2);
      el.textContent = left > 0 ? "plan expire dans " + mm + ":" + ss : "plan expir\u00e9 \u2014 r\u00e9analyse requise";
      el.classList.toggle("hot", left < 5 * 60000);
      if (left <= 0) {
        stopTtl();
        var ap = document.getElementById("pbia-apply");
        if (ap) ap.disabled = true;
        log("PLAN_EXPIRED \u2014 le plan a d\u00e9pass\u00e9 son TTL de 30 min. Une nouvelle analyse est requise.", "warn");
      }
    }, 1000);
  }
  function stopTtl() { if (S.ttlTimer) { clearInterval(S.ttlTimer); S.ttlTimer = null; } }

  /* ------------------------------------------------------------------ */
  /* Application                                                         */
  /* ------------------------------------------------------------------ */
  var demoConflictDone = false;
  function applyPlan() {
    stopTtl();
    var sel = S.plan.ops.filter(function (o) { return S.selected[o.id]; });
    var badHigh = sel.find(function (o) { return o.cls === "diagnostic" && !S.highTokens[o.id]; });
    if (badHigh) {
      log("403 HIGH_RISK_NOT_ALLOWED_IN_BULK \u2014 " + badHigh.id + " refus\u00e9e sans jeton individuel.", "err");
      return;
    }
    S.execution = {
      id: "exec_" + Date.now().toString(36).toUpperCase(),
      idem: cryptoRandom(), applied: 0, status: "Running",
      before: S.plan.fingerprint, after: null
    };
    setPhase("APPLY");
    var aborted = false;
    var bar = function (p) { var el = document.getElementById("pbia-apbar"); if (el) el.style.width = p + "%"; };
    var msg = function (t) { var el = document.getElementById("pbia-apmsg"); if (el) el.textContent = t; };
    var doConflict = !demoConflictDone && sel.length >= 3 && !S.live;

    var steps = [[300, "REVALIDATE \u2014 empreinte racine compar\u00e9e\u2026", 8]];
    if (doConflict) {
      steps.push([900, "__CONFLICT__", 14]);
    } else {
      steps.push([800, "Empreintes feuilles valides \u2014 ExpectedOldValue confirm\u00e9es pour " + sel.length + " op\u00e9rations.", 20]);
      steps.push([1400, "BACKUP \u2014 TMSL complet sauvegard\u00e9, hachage scell\u00e9 dans le journal cha\u00een\u00e9.", 35]);
      steps.push([1900, "APPLY \u2014 groupe 1 (sans ar\u00eate de d\u00e9pendance) : mutations en m\u00e9moire\u2026", 55]);
      steps.push([2400, "SaveChanges() \u2014 un appel pour le groupe.", 70]);
      steps.push([2900, "VERIFY \u2014 relecture des propri\u00e9t\u00e9s : toutes les valeurs cibles confirm\u00e9es.", 85]);
      steps.push([3300, "AUDIT \u2014 op\u00e9rations inverses enregistr\u00e9es avec pr\u00e9conditions. Empreinte apr\u00e8s : B91F0E83\u2026", 100]);
    }

    steps.forEach(function (s, i) {
      setTimeout(function () {
        if (aborted) return;
        if (s[1] === "__CONFLICT__") {
          aborted = true;
          demoConflictDone = true;
          bar(s[2]);
          var m = "409 MODEL_CHANGED_PARTIAL \u2014 1 cible modifi\u00e9e pendant la lecture du plan.";
          msg(m); log(m, "warn");
          var victim = sel.find(function (o) { return o.cls === "guided"; }) || sel[sel.length - 1];
          victim.stale = true; S.selected[victim.id] = false;
          log("Op\u00e9ration " + victim.id + " (" + victim.rule + " \u2014 " + victim.target + ") marqu\u00e9e STALE. " +
            (sel.length - 1) + " op\u00e9rations restent valides : le plan n\u2019est PAS int\u00e9gralement invalid\u00e9.", "warn");
          setTimeout(function () {
            S.plan.expiresAt = Date.now() + 30 * 60 * 1000;
            setPhase("PLAN");
            log("Choix : appliquer les op\u00e9rations encore valides, ou r\u00e9analyser la cible modifi\u00e9e.", "warn");
          }, 900);
          return;
        }
        msg(s[1]); bar(s[2]);
        log(s[1], i === steps.length - 1 ? "ok" : "");
        if (i === steps.length - 1) {
          S.execution.status = "Succeeded";
          S.execution.applied = sel.length;
          S.execution.after = "B91F0E83A2D14C77";
          setPhase("DONE");
        }
      }, s[0]);
    });
  }

  function cryptoRandom() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "idem-" + Math.random().toString(36).slice(2, 14);
  }

  function buildReport() {
    var applied = S.plan.ops.filter(function (o) { return S.selected[o.id]; });
    return {
      executionId: S.execution.id,
      status: S.execution.status,
      model: S.model.name,
      fingerprintBefore: S.execution.before,
      fingerprintAfter: S.execution.after,
      referentialVersion: "v7",
      observability: S.model.observability,
      dryRun: S.plan.dry,
      operations: applied.map(function (o) {
        return {
          operationId: o.id, ruleId: o.rule, ruleVersionId: o.ruleVersionId,
          target: o.target, property: o.prop,
          expectedOldValue: o.oldV, newValue: o.newV,
          confidence: o.conf / 100, blastRadius: o.blast, evidence: o.evidence,
          verified: true, reversible: true
        };
      }),
      rejectedByDependencyGraph: S.plan.rejected,
      journal: logBuf
    };
  }

  /* ------------------------------------------------------------------ */
  /* Boot                                                                */
  /* ------------------------------------------------------------------ */
  function boot() {
    mount();
    log("Overlay Agent BI v2 charg\u00e9 \u2014 couche ind\u00e9pendante du bundle React.");
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
