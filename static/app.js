"use strict";

// State
let META = null;
const gekozenBijlagen = new Set();

// Helpers
const $ = (sel) => document.querySelector(sel);
const el = (tag, props = {}, ...kids) => {
  const n = document.createElement(tag);
  Object.assign(n, props);
  for (const k of kids) n.append(k);
  return n;
};

async function init() {
  try {
    const res = await fetch("/api/meta");
    META = await res.json();
  } catch (e) {
    $("#resultaat").innerHTML =
      '<div class="fout">Kon de configuratie niet laden. Draait de server?</div>';
    return;
  }
  renderAiStatus();
  renderGemeenten();
  renderActiviteiten();
  bindEvents();
}

function renderAiStatus() {
  const node = $("#ai-status");
  if (META.ai_beschikbaar) {
    node.classList.add("aan");
    node.innerHTML = '<span class="dot"></span> AI-analyse actief';
  } else {
    node.innerHTML = '<span class="dot"></span> AI uit — regels + historie';
    node.title =
      "Stel ANTHROPIC_API_KEY in om de volledige AI-analyse te activeren.";
  }
}

function renderGemeenten() {
  const sel = $("#loc-gemeente");
  sel.append(el("option", { value: "", textContent: "— Kies gemeente —" }));
  for (const g of META.gemeenten) {
    sel.append(el("option", { value: g, textContent: g }));
  }
}

const GROEPEN = [
  { cat: "particulier", titel: "Voor bewoners (veelvoorkomend)" },
  { cat: "beide", titel: "Bouwen / verbouwen" },
  { cat: "zakelijk", titel: "Zakelijk" },
];

function activiteitItem(act) {
  const cb = el("input", { type: "checkbox", value: act.code });
  cb.addEventListener("change", renderBijlagen);

  const titelRij = el("div", { className: "ci-titel", textContent: act.naam });
  if (act.vergunningvrij_mogelijk)
    titelRij.append(el("span", { className: "badge-vrij", textContent: "vaak vergunningvrij" }));

  const body = el("div", {}, titelRij, el("div", { className: "ci-sub", textContent: act.toelichting }));
  if (act.vergunningcheck_hint)
    body.append(el("div", { className: "ci-hint", textContent: act.vergunningcheck_hint }));

  return el("label", { className: "check-item" }, cb, body);
}

function renderActiviteiten() {
  const lijst = $("#activiteiten-lijst");
  lijst.innerHTML = "";
  for (const groep of GROEPEN) {
    const items = META.activiteiten.filter((a) => (a.categorie || "beide") === groep.cat);
    if (items.length === 0) continue;
    lijst.append(el("div", { className: "groep-titel", textContent: groep.titel }));
    for (const act of items) lijst.append(activiteitItem(act));
  }
}

function geselecteerdeActiviteiten() {
  return [...document.querySelectorAll("#activiteiten-lijst input:checked")].map(
    (c) => c.value
  );
}

function renderBijlagen() {
  const codes = geselecteerdeActiviteiten();
  const wrap = $("#bijlagen-lijst");
  wrap.innerHTML = "";

  if (codes.length === 0) {
    wrap.append(
      el("p", { className: "leeg", textContent: "Kies eerst een of meer activiteiten." })
    );
    return;
  }

  const verplicht = new Map(); // code -> label
  const aanbevolen = new Map();
  for (const act of META.activiteiten) {
    if (!codes.includes(act.code)) continue;
    for (const b of act.verplichte_bijlagen || [])
      verplicht.set(b, META.bijlage_labels[b] || b);
    for (const b of act.aanbevolen_bijlagen || [])
      if (!verplicht.has(b)) aanbevolen.set(b, META.bijlage_labels[b] || b);
  }

  const groep = (titel, map, isVerplicht) => {
    if (map.size === 0) return;
    wrap.append(el("div", { className: "bijlage-groep", textContent: titel }));
    for (const [code, label] of map) {
      const cb = el("input", { type: "checkbox", value: code });
      cb.checked = gekozenBijlagen.has(code);
      cb.addEventListener("change", (e) => {
        if (e.target.checked) gekozenBijlagen.add(code);
        else gekozenBijlagen.delete(code);
      });
      const inner = el(
        "div",
        {},
        el("span", { className: "ci-titel", textContent: label })
      );
      if (isVerplicht)
        inner.firstChild.after(
          el("span", { className: "badge-verplicht", textContent: "verplicht" })
        );
      wrap.append(el("label", { className: "check-item" }, cb, inner));
    }
  };

  groep("Verplichte bijlagen", verplicht, true);
  groep("Aanbevolen bijlagen", aanbevolen, false);
}

function bindEvents() {
  $("#aanvrager-type").addEventListener("change", (e) => {
    $("#kvk-wrap").classList.toggle("hidden", e.target.value !== "bedrijf");
  });
  $("#aanvraag-form").addEventListener("submit", onSubmit);
  $("#voorbeeld-btn").addEventListener("click", vulVoorbeeld);
}

function bouwAanvraag() {
  return {
    aanvrager: {
      naam: $("#aanvrager-naam").value,
      type: $("#aanvrager-type").value,
      kvk: $("#aanvrager-kvk").value || null,
    },
    locatie: {
      adres: $("#loc-adres").value,
      postcode: $("#loc-postcode").value,
      gemeente: $("#loc-gemeente").value,
      kadastrale_aanduiding: $("#loc-kadaster").value || null,
    },
    activiteiten: geselecteerdeActiviteiten(),
    omschrijving: $("#omschrijving").value,
    bouwkosten: parseFloat($("#bouwkosten").value) || 0,
    vooroverleg: $("#vooroverleg").checked,
    startdatum: $("#startdatum").value || null,
    bijlagen: [...gekozenBijlagen],
  };
}

async function onSubmit(e) {
  e.preventDefault();
  const btn = $("#check-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Bezig met controleren…';

  try {
    const res = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bouwAanvraag()),
    });
    if (!res.ok) throw new Error("Serverfout " + res.status);
    renderResultaat(await res.json());
  } catch (err) {
    $("#resultaat").className = "card resultaat";
    $("#resultaat").innerHTML =
      '<div class="fout">Er ging iets mis bij de controle: ' + err.message + "</div>";
  } finally {
    btn.disabled = false;
    btn.textContent = "Controleer aanvraag";
  }
}

const SEV = {
  blokkerend: { ico: "✕", naam: "Blokkerend" },
  waarschuwing: { ico: "!", naam: "Waarschuwing" },
  info: { ico: "i", naam: "Info" },
};

function kleurVoorScore(score) {
  if (score >= 80) return "#1f8a4d";
  if (score >= 55) return "#1f8a82";
  if (score >= 30) return "#e0922f";
  return "#c0392b";
}

function renderResultaat(r) {
  const node = $("#resultaat");
  node.className = "card resultaat";
  node.innerHTML = "";

  // Score-gauge
  const omtrek = 2 * Math.PI * 50;
  const offset = omtrek * (1 - r.score / 100);
  const kleur = kleurVoorScore(r.score);
  const gauge = el("div", { className: "gauge" });
  gauge.style.setProperty("--kleur", kleur);
  gauge.innerHTML = `
    <svg width="116" height="116" viewBox="0 0 116 116">
      <circle class="track" cx="58" cy="58" r="50"></circle>
      <circle class="val" cx="58" cy="58" r="50"
        stroke-dasharray="${omtrek}" stroke-dashoffset="${omtrek}"></circle>
    </svg>
    <div class="num">${r.score}</div>`;

  const klaarBadge = el("span", {
    className: "badge-klaar " + (r.klaar_voor_indienen ? "ja" : "nee"),
    textContent: r.klaar_voor_indienen
      ? "Klaar om in te dienen"
      : "Nog niet indienen",
  });

  const scoreTekst = el(
    "div",
    { className: "score-tekst" },
    el("h2", { textContent: "Kans op acceptatie" }),
    el("div", { className: "label", textContent: r.score_label, style: `color:${kleur}` }),
    klaarBadge
  );

  node.append(el("div", { className: "score-blok" }, gauge, scoreTekst));

  // Bron-indicatie
  const bron = el("div", { className: "bron-ai" });
  bron.innerHTML = r.ai_gebruikt
    ? '<span class="pill">AI</span> Analyse met Claude op basis van nationale + lokale richtlijnen en historische data.'
    : '<span class="pill heur">Regels</span> Analyse op basis van regels en historische data (AI niet actief).';
  node.append(bron);

  // Samenvatting
  node.append(el("div", { className: "samenvatting", textContent: r.samenvatting }));

  // Bevindingen
  if (r.bevindingen.length) {
    node.append(el("h3", { textContent: `Bevindingen (${r.bevindingen.length})` }));
    for (const b of r.bevindingen) {
      const meta = SEV[b.severity] || SEV.info;
      const inner = el(
        "div",
        {},
        el("span", { className: "cat", textContent: b.categorie + ": " }),
        document.createTextNode(b.bericht)
      );
      if (b.bron) inner.append(el("span", { className: "bron", textContent: "Richtlijn: " + b.bron }));
      node.append(
        el(
          "div",
          { className: "bevinding " + b.severity },
          el("span", { className: "ico", textContent: meta.ico }),
          inner
        )
      );
    }
  }

  // Tips
  if (r.tips.length) {
    node.append(el("h3", { textContent: "Tips om je kans te vergroten" }));
    for (const t of r.tips) {
      const kop = el(
        "div",
        { className: "tip-kop" },
        el("span", { className: "tip-titel", textContent: t.titel }),
        el("span", { className: "impact " + t.impact, textContent: "impact " + t.impact })
      );
      const advies = el("div", { className: "tip-advies", textContent: t.advies });
      if (t.bron)
        advies.append(el("span", { className: "bron", textContent: " (richtlijn: " + t.bron + ")" }));
      node.append(el("div", { className: "tip" }, kop, advies));
    }
  }

  // Historische context
  const h = r.historische_context;
  node.append(el("h3", { textContent: "Historische context" }));
  const hist = el("div", { className: "hist" });
  if (h.acceptatiepercentage !== null && h.acceptatiepercentage !== undefined) {
    hist.append(
      el(
        "div",
        { className: "hist-stat" },
        el("span", { className: "pct", textContent: h.acceptatiepercentage + "%" }),
        el("span", { textContent: `verleend bij ${h.aantal_vergelijkbaar} vergelijkbare aanvragen` })
      )
    );
  }
  hist.append(el("p", { textContent: h.toelichting, style: "margin:8px 0 0" }));
  if (h.veelvoorkomende_weigeringsredenen.length) {
    hist.append(el("p", { textContent: "Veelvoorkomende weigeringsredenen:", style: "margin:10px 0 2px;font-weight:600" }));
    const ul = el("ul");
    for (const reden of h.veelvoorkomende_weigeringsredenen)
      ul.append(el("li", { textContent: reden }));
    hist.append(ul);
  }
  node.append(hist);

  // Animatie van de gauge
  requestAnimationFrame(() => {
    gauge.querySelector(".val").setAttribute("stroke-dashoffset", offset);
  });
  node.scrollIntoView({ behavior: "smooth", block: "start" });
}

function vulVoorbeeld() {
  // Voorbeeld van een particulier/bewoner: een dakkapel.
  $("#aanvrager-naam").value = "Familie Jansen";
  $("#aanvrager-type").value = "particulier";
  $("#kvk-wrap").classList.add("hidden");
  $("#aanvrager-kvk").value = "";
  $("#loc-adres").value = "Bergstraat 12";
  $("#loc-postcode").value = "6711 AA";
  $("#loc-gemeente").value = "Ede";
  $("#loc-kadaster").value = "";
  $("#omschrijving").value =
    "Het plaatsen van een dakkapel van circa 3 meter breed op het achterdakvlak " +
    "van onze woning, om de zolder als slaapkamer te kunnen gebruiken.";
  $("#bouwkosten").value = "9000";
  $("#vooroverleg").checked = false;

  const cb = document.querySelector('#activiteiten-lijst input[value="dakkapel"]');
  if (cb) cb.checked = true;
  // Vink één verplichte bijlage aan, laat de rest open om de check te demonstreren.
  gekozenBijlagen.clear();
  gekozenBijlagen.add("situatietekening");
  renderBijlagen();
}

init();
