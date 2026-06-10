/* Wave Trader PWA — fetches the Trade of the Day and renders the card.
   Offline behaviour: last successful pick per style is saved to localStorage;
   if the network is down we render that and show the offline banner. */

const $ = (id) => document.getElementById(id);

const state = {
  style: localStorage.getItem("wave-style") || "auto",
};

function cacheKey(style) {
  return `wave-pick-${style}`;
}

function fmtUsd(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v; // "unlimited"
  return `$${Number(v).toFixed(2)}`;
}

function setActiveStyleButton() {
  document.querySelectorAll("#style-picker button").forEach((b) => {
    b.classList.toggle("active", b.dataset.style === state.style);
  });
}

function show(id) { $(id).classList.remove("hidden"); }
function hide(id) { $(id).classList.add("hidden"); }

function renderPick(pick, fromCache) {
  hide("loading");
  hide("error");
  show("pick-card");
  $("offline-banner").classList.toggle("hidden", !fromCache);

  const sig = pick.signal;
  $("ticker").textContent = pick.ticker;
  $("trade-type").textContent = pick.trade_type.replaceAll("_", " ");

  const badge = $("direction-badge");
  badge.textContent = pick.direction.toUpperCase();
  badge.className = `badge ${pick.direction}`;

  const score = Math.max(0, Math.min(100, pick.score));
  $("score-num").textContent = Math.round(score);
  const circumference = 119.4;
  $("ring-fg").style.strokeDashoffset = circumference * (1 - score / 100);
  $("ring-fg").style.stroke =
    score >= 70 ? "var(--green)" : score >= 50 ? "var(--amber)" : "var(--red)";

  $("spot").textContent = fmtUsd(sig.price.spot);
  $("entry").textContent =
    `${fmtUsd(sig.price.entry_zone[0])}–${fmtUsd(sig.price.entry_zone[1])}`;
  $("stop").textContent = fmtUsd(sig.price.invalidation);
  const t = sig.price.targets && sig.price.targets[0];
  $("target").textContent = t ? fmtUsd(t.price) : "—";

  if (pick.instrument === "options") {
    show("options-block");
    hide("stock-block");
    $("expiry-label").textContent =
      `· exp ${sig.options.expiration} (${sig.options.dte} DTE)`;
    $("legs").innerHTML = "";
    for (const leg of sig.options.legs) {
      const div = document.createElement("div");
      div.className = "leg";
      div.innerHTML =
        `<span><span class="act-${leg.action}">${leg.action.toUpperCase()}</span> ` +
        `${leg.type.toUpperCase()} $${leg.strike}</span>` +
        `<span>${fmtUsd(leg.premium)} <span class="greeks">Δ${leg.delta.toFixed(2)} ` +
        `IV ${(leg.iv * 100).toFixed(0)}%</span></span>`;
      $("legs").appendChild(div);
    }
    $("max-loss").textContent = fmtUsd(sig.options.max_loss);
    $("max-gain").textContent = fmtUsd(sig.options.max_gain);
    $("breakeven").textContent = fmtUsd(sig.options.breakeven);
    $("pop").textContent = `${(sig.options.probability_of_profit * 100).toFixed(0)}%`;
  } else {
    hide("options-block");
    show("stock-block");
    const plan = pick.stock_plan || {};
    $("risk-share").textContent = fmtUsd(plan.risk_per_share);
    $("reward-share").textContent = fmtUsd(plan.reward_per_share);
    $("rr").textContent = plan.reward_risk_ratio ?? "—";
  }

  $("rationale").innerHTML = "";
  for (const line of pick.rationale) {
    const li = document.createElement("li");
    li.textContent = line;
    $("rationale").appendChild(li);
  }

  $("wave-line").textContent =
    `Wave: ${sig.wave.primary_count} · degree ${sig.wave.degree} · ` +
    `p=${(sig.wave.primary_probability * 100).toFixed(0)}%`;
  $("updated").textContent =
    `Generated ${new Date(pick.generated_at).toLocaleString()}` +
    (fromCache ? " (cached)" : "");
}

function renderError(message) {
  hide("loading");
  hide("pick-card");
  show("error");
  $("error").textContent = message;
}

async function loadPick({ force = false } = {}) {
  show("loading");
  hide("error");
  hide("pick-card");
  $("offline-banner").classList.add("hidden");

  const url = force
    ? `/api/pick/refresh?style=${state.style}`
    : `/api/pick/today?style=${state.style}`;
  try {
    const resp = await fetch(url, { method: force ? "POST" : "GET" });
    if (resp.status === 404) {
      const body = await resp.json();
      renderError(body.detail || "No qualifying setup today.");
      return;
    }
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const pick = await resp.json();
    localStorage.setItem(cacheKey(state.style), JSON.stringify(pick));
    renderPick(pick, false);
  } catch (err) {
    const cached = localStorage.getItem(cacheKey(state.style));
    if (cached) {
      renderPick(JSON.parse(cached), true);
    } else {
      renderError(
        "Can't reach the scanner and no saved pick yet. " +
        "Connect to the network and pull to refresh."
      );
    }
  }
}

document.querySelectorAll("#style-picker button").forEach((b) => {
  b.addEventListener("click", () => {
    state.style = b.dataset.style;
    localStorage.setItem("wave-style", state.style);
    setActiveStyleButton();
    loadPick();
  });
});

$("refresh-btn").addEventListener("click", () => loadPick({ force: true }));

$("date-label").textContent = new Date().toLocaleDateString(undefined, {
  weekday: "short", month: "short", day: "numeric",
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

setActiveStyleButton();
loadPick();
