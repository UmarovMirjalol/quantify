fetch("/data/site.json?v=__VER__").then(r => r.json()).then(D => {
  const F = D.fields;
  const C = D.companies.map(r => Object.fromEntries(F.map((f, i) => [f, r[i]])));
  const byId = Object.fromEntries(C.map(c => [c.id, c]));
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
  const fmt = v => v == null ? '<span class="muted">–</span>' : v.toFixed(1);
  const usd = v => {
    if (v == null) return '<span class="muted">–</span>';
    const a = Math.abs(v), s = v < 0 ? "−$" : "$";
    return a >= 1e6 ? s + (a / 1e6).toFixed(2) + "T" : a >= 1e3 ? s + (a / 1e3).toFixed(1) + "B" : a >= 1 ? s + a.toFixed(0) + "M" : s + (a * 1000).toFixed(0) + "K";
  };
  const cv = D.coverage;
  const pct = (a, b) => Math.round(100 * a / b) + "%";
  const Y = D.years;
  const yLast = Y[Y.length - 1];
  const mac = /Mac|iPhone|iPad/.test(navigator.platform || "");
  const FL = {
    sic_linked: "Industry linked to technology",
    "sic_linked+name": "Industry + company name",
    name_only: "Company name only",
    industry_unlinked: "Industry not linked (score 0)",
    missing_sic: "No industry data",
    uninformative_sic: "Industry code too broad"
  };
  const WHY = {
    missing_sic: "SEC filings list no industry code for this company, so its technology exposure cannot be measured. The index is left blank rather than set to zero.",
    uninformative_sic: "The company’s SEC industry code is a catch-all category that says nothing about its technology domain. The index is left blank rather than set to zero.",
    industry_unlinked: "The company’s industry is not linked to any of the nine tracked technology categories, so its startup-ecosystem exposure is 0."
  };
  const cats = ["AI", "Fintech", "Cloud", "Robotics", "Cybersecurity", "Biotech", "Semiconductors", "Energy", "Quantum"];
  const FAMOUS = ["NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "GOOGL", "GOOG", "META", "INTC", "AMD", "JPM", "PFE"];
  const peerR = D.results.find(x => x.model === "M1" && x.spec === "main_sic2xyear");
  const COEF10 = peerR && peerR.coef != null ? peerR.coef : 0.0831;
  const assocPct = d => (Math.exp(COEF10 * d / 10) - 1) * 100;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  let yi = Y.length - 1, playing = false, touring = false;
  function tdiAt(c, i) {
    i = i == null ? yi : i;
    if (c.history && c.history[i] != null) return c.history[i];
    if (i === Y.length - 1) return c.tdi;
    return null;
  }

  const scored = C.filter(c => c.tdi != null).sort((a, b) => b.tdi - a.tdi || a.name.localeCompare(b.name));
  const rankOf = {};
  scored.forEach((c, i) => { rankOf[c.id] = i + 1; });
  const indPeers = {};
  C.forEach(c => {
    if (!c.industry || c.tdi == null) return;
    (indPeers[c.industry] || (indPeers[c.industry] = [])).push(c);
  });
  Object.values(indPeers).forEach(arr => arr.sort((a, b) => b.tdi - a.tdi));

  function peersOf(c) {
    return c.industry ? (indPeers[c.industry] || []) : [];
  }
  function indRank(c) {
    const p = peersOf(c);
    const i = p.findIndex(x => x.id === c.id);
    return i < 0 ? null : { rank: i + 1, n: p.length, avg: p.reduce((s, x) => s + x.tdi, 0) / p.length };
  }
  function indPath(ind) {
    const peers = C.filter(x => x.industry === ind && x.history);
    return Y.map((_, i) => {
      const xs = peers.map(p => p.history[i]).filter(v => v != null);
      return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
    });
  }

  $("stats").innerHTML = [
    [cv.total_companies.toLocaleString(), "companies in the universe"],
    [pct(cv.index_coverage, cv.total_companies), "with an index score"],
    [D.n_fin.toLocaleString(), "with SEC financials"],
    [D.n_startups.toLocaleString(), "startups analysed"]
  ].map(s => `<div class="stat"><b data-n="${s[0]}">${s[0]}</b><span>${s[1]}</span></div>`).join("");

  cats.forEach(c => $("cat").insertAdjacentHTML("beforeend", `<option>${c}</option>`));
  [...new Set(C.map(c => c.industry).filter(Boolean))].sort()
    .forEach(i => $("ind").insertAdjacentHTML("beforeend", `<option>${esc(i)}</option>`));

  const tickIndex = {};
  C.forEach(c => { if (c.ticker) tickIndex[String(c.ticker).toUpperCase()] = c; });
  function resolveFirm(q) {
    q = (q || "").trim();
    if (!q) return null;
    const hit = tickIndex[q.toUpperCase()];
    if (hit) return hit;
    const list = searchHits(q, 1);
    return list[0] || null;
  }
  function paintTop() {
    const top = C.filter(c => c.listed && c.components == 2 && tdiAt(c) != null)
      .sort((a, b) => tdiAt(b) - tdiAt(a) || a.name.localeCompare(b.name)).slice(0, 10);
    $("top").innerHTML = top.map((c, i) => {
      const t = tdiAt(c);
      return `<div class="tc" data-id="${c.id}"><span class="rk">#${i + 1}</span><div class="s">${t.toFixed(1)}</div>
       <div class="bar"><i style="width:${t}%"></i></div><div class="n">${esc(c.name)}</div>
       <div class="t">${esc(c.ticker)} · ${esc(c.industry)}</div></div>`;
    }).join("");
  }
  $("top").onclick = e => { const t = e.target.closest(".tc"); if (t) openCompany(+t.dataset.id); };
  function setYear(i, rerender) {
    yi = Math.max(0, Math.min(Y.length - 1, i));
    if ($("yslider")) $("yslider").value = yi;
    if ($("yval")) $("yval").textContent = Y[yi];
    if ($("ychip")) $("ychip").textContent = Y[yi];
    paintTop();
    if (typeof paintMovers === "function") paintMovers();
    if (typeof paintLanes === "function") paintLanes();
    if (rerender !== false) { page = 0; render(); }
  }
  const chips = [];
  const seen = new Set();
  FAMOUS.forEach(t => {
    const c = tickIndex[t];
    if (!c || seen.has(c.id)) return;
    seen.add(c.id);
    chips.push(c);
  });
  $("chips").innerHTML = chips.map(c =>
    `<button type="button" class="chip" data-id="${c.id}">${esc(c.ticker)} <span>${c.tdi != null ? c.tdi.toFixed(1) : "–"}</span></button>`
  ).join("") + `<button type="button" class="chip ghost" id="rnd">Random company</button>`;
  $("chips").onclick = e => {
    const b = e.target.closest("[data-id]");
    if (b) openCompany(+b.dataset.id);
    if (e.target.closest("#rnd")) {
      const pool = C.filter(c => c.listed && c.tdi != null);
      openCompany(pool[Math.floor(Math.random() * pool.length)].id);
    }
  };

  const catCount = Object.fromEntries(cats.map(c => [c, 0]));
  C.forEach(c => {
    const s = c.categories || "";
    cats.forEach(k => { if (s.includes(k + "=")) catCount[k]++; });
  });
  const catMax = Math.max(...Object.values(catCount), 1);
  $("techmap").innerHTML = cats.map(k =>
    `<button type="button" class="tm" data-cat="${k}"><span>${k}</span><b>${catCount[k].toLocaleString()}</b>
     <i style="width:${100 * catCount[k] / catMax}%"></i><em>companies tagged</em></button>`
  ).join("");
  $("techmap").onclick = e => {
    const b = e.target.closest(".tm");
    if (!b) return;
    $("cat").value = b.dataset.cat;
    page = 0;
    render();
    $("explore").scrollIntoView({ behavior: "smooth" });
  };

  let sortK = "tdi", dir = -1, page = 0;
  function rows() {
    const q = $("q").value.trim().toLowerCase(), i = $("ind").value, c = $("cat").value, l = $("lst").value;
    return C.filter(x =>
      (!q || x.name.toLowerCase().includes(q) || (x.ticker || "").toLowerCase().includes(q)) &&
      (!i || x.industry === i) && (!c || (x.categories || "").includes(c + "=")) &&
      (l === "" || x.listed == +l)
    ).sort((a, b) => {
      const x = sortK === "tdi" ? tdiAt(a) : a[sortK], y = sortK === "tdi" ? tdiAt(b) : b[sortK];
      if (x == null) return 1;
      if (y == null) return -1;
      return (x > y ? 1 : x < y ? -1 : 0) * dir;
    });
  }
  function spark(v) {
    if (!v || v.filter(x => x != null).length < 2) return "";
    const n = v.length - 1;
    const pts = v.map((s, i) => s == null ? null : `${i},${100 - s}`).filter(Boolean);
    const cur = v[yi] != null ? `<circle cx="${yi}" cy="${100 - v[yi]}" r="8" fill="#d97706"/>` : "";
    return `<svg class="spark" viewBox="0 0 ${n} 100" preserveAspectRatio="none"><polyline fill="none" stroke="#0f172a" stroke-width="10" points="${pts.join(" ")}"/>${cur}</svg>`;
  }
  function render() {
    const r = rows(), PER = +$("per").value || r.length || 1, P = Math.max(1, Math.ceil(r.length / PER));
    page = Math.max(0, Math.min(page, P - 1));
    $("tb").innerHTML = r.slice(page * PER, page * PER + PER).map(c => {
      const t = tdiAt(c);
      return `<tr data-id="${c.id}"><td>${esc(c.name)} ${c.listed ? "" : '<span class="badge">historical</span>'}</td>
       <td>${esc(c.ticker)}</td><td class="muted">${esc(c.industry)}</td>
       <td class="r"><b>${fmt(t)}</b>${t != null ? `<span class="meter"><i style="width:${t}%"></i></span>` : ""}</td>
       <td>${spark(c.history)}</td>
       <td class="r">${fmt(c.startup)}</td><td class="r">${fmt(c.patent)}</td><td class="r">${usd(c.revenue)}</td></tr>`;
    }).join("");
    const a = r.length ? page * PER + 1 : 0, b = Math.min(r.length, page * PER + PER);
    $("pg").textContent = `Showing ${a.toLocaleString()}–${b.toLocaleString()} of ${r.length.toLocaleString()} companies`;
    $("pno").value = page + 1; $("pno").max = P; $("pmax").textContent = P.toLocaleString();
    $("first").disabled = $("prev").disabled = page === 0;
    $("next").disabled = $("last").disabled = page >= P - 1;
    document.querySelector(".tw").classList.toggle("scroll", PER > 100);
  }
  document.querySelectorAll("th[data-k]").forEach(th => th.onclick = () => {
    const k = th.dataset.k;
    dir = sortK === k ? -dir : (["name", "ticker", "industry"].includes(k) ? 1 : -1);
    sortK = k; render();
  });
  ["q", "ind", "cat", "lst", "per"].forEach(id => $(id).oninput = () => { page = 0; render(); });
  $("prev").onclick = () => { page--; render(); };
  $("next").onclick = () => { page++; render(); };
  $("first").onclick = () => { page = 0; render(); };
  $("last").onclick = () => { page = 1e9; render(); };
  $("pno").onchange = () => { page = (+$("pno").value || 1) - 1; render(); };
  $("tb").onclick = e => { const t = e.target.closest("tr"); if (t) openCompany(+t.dataset.id); };

  function chart(series, colors, opt) {
    opt = opt || {};
    const W = 640, H = 210, P = 32;
    const X = i => P + i * (W - 2 * P) / (Y.length - 1);
    const Ys = s => H - P - (s / 100) * (H - 2 * P);
    const grid = [0, 50, 100].map(g =>
      `<line x1="${P}" x2="${W - P}" y1="${Ys(g)}" y2="${Ys(g)}" stroke="#e6e0d4"/><text x="4" y="${Ys(g) + 4}">${g}</text>`
    ).join("");
    const years = Y.map((y, i) => i % 3 == 0 || i == Y.length - 1 ? `<text x="${X(i) - 14}" y="${H - 10}">${y}</text>` : "").join("");
    const mark = `<line x1="${X(yi)}" x2="${X(yi)}" y1="${P}" y2="${H - P}" stroke="#d97706" stroke-dasharray="3 3"/>`;
    const paths = series.map((v, si) => {
      let d = "", o = false;
      v.forEach((s, i) => {
        if (s == null) { o = false; return; }
        d += (o ? "L" : "M") + X(i) + "," + Ys(s);
        o = true;
      });
      const pts = v.map((s, i) => s == null ? null : [X(i), Ys(s)]).filter(Boolean);
      const col = colors[si];
      const gid = "g" + si + Math.round(Math.random() * 1e6);
      const area = !opt.bare && si === 0 && pts.length > 1
        ? `<defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${col}" stop-opacity=".22"/><stop offset="1" stop-color="${col}" stop-opacity="0"/></linearGradient></defs>
           <path d="M${pts[0][0]},${H - P} L${pts.map(p => p.join(",")).join(" L")} L${pts[pts.length - 1][0]},${H - P}Z" fill="url(#${gid})"/>`
        : "";
      const dash = opt.bare || !si ? "" : ' stroke-dasharray="6 5"';
      const dots = (opt.all || !si) ? pts.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="#fff" stroke="${col}" stroke-width="2"/>`).join("") : "";
      const lab = opt.labels && opt.labels[si] && pts.length
        ? `<text x="${Math.min(W - 8, pts[pts.length - 1][0] + 6)}" y="${pts[pts.length - 1][1] + 4}" style="fill:${col}" font-size="11">${esc(opt.labels[si])}</text>`
        : "";
      return `${area}<path d="${d}" fill="none" stroke="${col}" stroke-width="${si ? 2 : 2.5}"${dash}/>${dots}${lab}`;
    }).join("");
    return `<svg viewBox="0 0 ${W} ${H}" width="100%">${grid}${mark}${years}${paths}</svg>`;
  }
  function bars(v) {
    if (!v || v.every(x => x == null)) return "";
    const W = 640, H = 170, P = 32, bw = (W - 2 * P) / Y.length, m = Math.max(...v.map(x => Math.abs(x || 0))) || 1;
    return `<svg viewBox="0 0 ${W} ${H}" width="100%">` + v.map((x, i) => {
      if (x == null) return "";
      const h = Math.abs(x) / m * (H - 2 * P - 10);
      return `<rect x="${P + i * bw + 4}" y="${H - P - h}" width="${bw - 8}" height="${h}" rx="3" fill="${x < 0 ? "#b91c1c" : "#334155"}"><title>${Y[i]}</title></rect>`;
    }).join("") + Y.map((y, i) => i % 3 == 0 || i == Y.length - 1 ? `<text x="${P + i * bw + bw / 2 - 14}" y="${H - 10}">${y}</text>` : "").join("") +
      `<text x="4" y="14">max ${usd(m).replace(/<[^>]+>/g, "")}</text></svg>`;
  }
  function kpi(v, l) { return `<div class="kpi"><b>${v}</b><span>${l}</span></div>`; }
  function tagsOf(c) {
    return (c.categories || "").split(";").map(s => s.trim()).filter(Boolean)
      .map(s => `<span class="pill">${esc(s.replace("=", " · "))}</span>`).join("") ||
      '<span class="muted small">No tracked technology linked</span>';
  }
  function peerBlock(c) {
    const t = tdiAt(c, Y.length - 1);
    const ir = indRank(c);
    if (!ir || t == null) return "";
    const pctile = Math.round(100 * (ir.n - ir.rank) / Math.max(ir.n - 1, 1));
    return `<div class="peerbox">
      <div class="peer"><span>This firm</span><span class="track"><i style="width:${t}%"></i></span><b>${t.toFixed(1)}</b></div>
      <div class="peer"><span>Industry avg</span><span class="track"><i class="avg" style="width:${ir.avg}%"></i></span><b>${ir.avg.toFixed(1)}</b></div>
      <p class="muted small">#${ir.rank} of ${ir.n.toLocaleString()} in ${esc(c.industry)} · higher than ${pctile}% of industry peers · #${rankOf[c.id].toLocaleString()} of ${scored.length.toLocaleString()} overall</p>
    </div>`;
  }
  function impliedHTML(c) {
    const ir = indRank(c);
    if (!ir || c.tdi == null) return "";
    const d = c.tdi - ir.avg, p = assocPct(d), sign = p >= 0 ? "+" : "";
    return `<div class="impl">
      <div class="eyebrow">Associated next-year public float vs industry mean</div>
      <div class="big sm">${sign}${p.toFixed(1)}%</div>
      <p class="muted small">${d >= 0 ? "+" : ""}${d.toFixed(1)} index points vs the ${esc(c.industry)} average of ${ir.avg.toFixed(1)}.
        Formula: exp(β × Δ/10) − 1, with β = ${COEF10.toFixed(3)} from industry×year FE. Predictive, not causal. A firm’s own score changes over time were ~0.</p>
    </div>`;
  }
  function neighborHTML(c) {
    if (c.tdi == null) return "";
    const near = peersOf(c).filter(x => x.id !== c.id)
      .map(x => ({ x, d: Math.abs(x.tdi - c.tdi) }))
      .sort((a, b) => (b.x.listed - a.x.listed) || ((b.x.ticker ? 1 : 0) - (a.x.ticker ? 1 : 0)) || a.d - b.d)
      .slice(0, 5);
    if (!near.length) return "";
    return `<h4>Closest industry peers</h4><div class="near">${near.map(n =>
      `<button type="button" class="chip" data-id="${n.x.id}">${esc(n.x.ticker || n.x.name)} <span>${n.x.tdi.toFixed(1)}</span></button>`
    ).join("")}</div>`;
  }
  function mixHTML(c) {
    if (c.patent == null || c.startup == null) return "";
    const mid = ((c.startup + c.patent) / 2).toFixed(1);
    return `<h4>What-if component mix</h4>
      <p class="muted small">Published index is 50/50 when both scores exist. Drag to reweight <i>this firm only</i> — this does not rerun the regressions.</p>
      <input type="range" id="mix" min="0" max="100" value="50">
      <p class="legend mixleg"><span>Startup ${c.startup.toFixed(1)}</span><b id="mixv">50 / 50 → ${mid}</b><span>Patent ${c.patent.toFixed(1)}</span></p>`;
  }

  let compareA = null;
  function companyHTML(c, compact) {
    const f = c.fin;
    const rdp = f && f[1] > 0 && f[3] != null ? (100 * f[3] / f[1]).toFixed(1) + "%" : '<span class="muted">–</span>';
    const pat = c.patent != null ? fmt(c.patent) : '<span class="muted small">not linked</span>';
    const ind = c.industry ? indPath(c.industry) : null;
    const series = [c.history || []];
    const colors = ["#0f172a"];
    if (ind && ind.some(x => x != null)) { series.push(ind); colors.push("#94a3b8"); }
    return `<div class="vcol"><div class="muted small">${esc(c.ticker || "no ticker")}${c.exchange ? " · " + esc(c.exchange) : ""}${c.listed ? "" : ' · <span class="badge">historical filer</span>'}</div>
      <h3>${esc(c.name)}</h3>
      <div class="muted small">${esc(c.sic || "Industry unknown")}${c.country ? " · " + esc(c.country) : ""}</div>
      <div class="scoreline">
        <div><div class="big">${fmt(c.tdi)}</div><div class="muted small">Index ${yLast}</div></div>
        <div><div class="big sm">${fmt(c.startup)}</div><div class="muted small">Startup</div></div>
        <div><div class="big sm">${pat}</div><div class="muted small">Patent</div></div>
      </div>
      ${peerBlock(c)}
      ${compact ? "" : impliedHTML(c)}
      ${WHY[c.flag] ? `<div class="note">${WHY[c.flag]}</div>` : ""}
      <div>${tagsOf(c)}</div>
      ${c.history && c.history.some(x => x != null) ? `<h4>Index vs industry average</h4>${chart(series, colors)}
        <p class="legend"><span class="lg ink"></span> ${esc(c.ticker || c.name)} <span class="lg grey"></span> ${esc(c.industry || "industry")} average</p>` : ""}
      ${compact ? "" : neighborHTML(c) + mixHTML(c)}
      ${compact ? "" : `<h4>Fundamentals${f ? ` <span class="muted small">(SEC XBRL, FY${f[0]})</span>` : ""}</h4>
      ${f ? `<div class="kpis">${kpi(usd(f[1]), "Revenue")}${kpi(usd(f[2]), "Total assets")}${kpi(rdp, "R&amp;D / revenue")}${kpi(usd(f[4]), "Public float")}${kpi(usd(f[5]), "Cash")}</div>${bars(c.rev) ? '<div class="muted small" style="margin-top:10px">Revenue by year</div>' + bars(c.rev) : ""}` : '<p class="muted small">No XBRL financial statements reported to the SEC for 2015–2024.</p>'}
      <div class="muted small" style="margin-top:8px">Components available: ${c.components}/2 · ${esc(FL[c.flag] || "no data")} · <a href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${c.id}" target="_blank" rel="noopener">SEC filings ↗</a></div>`}</div>`;
  }

  const ov = $("ov"), dbody = $("dbody");
  function closeOv(keepHash) {
    ov.hidden = true;
    dbody.innerHTML = "";
    document.body.style.overflow = "";
    if (!keepHash && /^(#c\/|#vs\/)/.test(location.hash || "")) {
      history.replaceState(null, "", location.pathname + location.search);
    }
  }
  function openOv(html, wide) {
    ov.hidden = false;
    ov.classList.toggle("wide", !!wide);
    dbody.innerHTML = html;
    document.body.style.overflow = "hidden";
    dbody.scrollTop = 0;
  }
  $("ovx").onclick = () => closeOv();
  ov.addEventListener("click", e => { if (e.target === ov) closeOv(); });

  function openCompany(id) {
    const c = byId[id];
    if (!c) return;
    if (typeof paintHist === "function") paintHist(c.tdi);
    history.replaceState(null, "", "#c/" + c.id);
    openOv(`<div class="dhead"><button type="button" class="btn s" id="cmpThis">Compare with…</button>
      <button type="button" class="btn s" id="copyLink">Copy link</button>
      <button type="button" class="btn s" id="copyBrief">Copy brief</button></div>` + companyHTML(c), false);
    $("cmpThis").onclick = () => { compareA = c; openPal(true); };
    $("copyLink").onclick = async () => {
      try { await navigator.clipboard.writeText(location.href); $("copyLink").textContent = "Copied"; }
      catch (err) { $("copyLink").textContent = "Copy failed"; }
    };
    $("copyBrief").onclick = async () => {
      const ir = indRank(c);
      const d = ir && c.tdi != null ? c.tdi - ir.avg : null;
      const p = d == null ? null : assocPct(d);
      const text = `${c.name}${c.ticker ? " (" + c.ticker + ")" : ""} — Technology Disruption Index ${c.tdi != null ? c.tdi.toFixed(1) : "n/a"} (${yLast})
${ir ? "#" + ir.rank + " of " + ir.n + " in " + c.industry + " (avg " + ir.avg.toFixed(1) + ")" : ""}
${p == null ? "" : "Associated next-year public float vs industry mean: " + (p >= 0 ? "+" : "") + p.toFixed(1) + "% (industry×year FE, predictive not causal)."}
Startup ${c.startup != null ? c.startup.toFixed(1) : "–"} · Patent ${c.patent != null ? c.patent.toFixed(1) : "not linked"}
${location.origin}${location.pathname}#c/${c.id}`;
      try { await navigator.clipboard.writeText(text); $("copyBrief").textContent = "Brief copied"; }
      catch (err) { $("copyBrief").textContent = "Copy failed"; }
    };
    const mix = $("mix");
    if (mix) mix.oninput = () => {
      const w = +mix.value;
      const v = (1 - w / 100) * c.startup + (w / 100) * c.patent;
      $("mixv").textContent = `${100 - w} / ${w} → ${v.toFixed(1)}`;
    };
    dbody.onclick = e => {
      const b = e.target.closest(".near [data-id]");
      if (b) openCompany(+b.dataset.id);
    };
  }
  function openCompare(a, b) {
    compareA = null;
    history.replaceState(null, "", "#vs/" + a.id + "/" + b.id);
    const dt = (a.tdi != null && b.tdi != null) ? (a.tdi - b.tdi) : null;
    const lead = dt == null ? "" : (dt === 0 ? "Tied on the latest index." :
      `${esc(dt > 0 ? a.ticker || a.name : b.ticker || b.name)} scores ${Math.abs(dt).toFixed(1)} points higher.`);
    openOv(`<div class="dhead"><h3 style="margin:0">Compare</h3>
      <p class="muted small" style="margin:4px 0 0">${lead} Same scale (0–100), latest year ${yLast}.</p></div>
      <div class="vsgrid">${companyHTML(a, true)}${companyHTML(b, true)}</div>
      <h4>Both index histories</h4>
      ${chart([a.history || [], b.history || []], ["#0f172a", "#d97706"])}
      <p class="legend"><span class="lg ink"></span> ${esc(a.ticker || a.name)} <span class="lg amb"></span> ${esc(b.ticker || b.name)}</p>`, true);
  }

  function searchHits(q, limit) {
    q = (q || "").trim().toLowerCase();
    if (!q) return chips.slice(0, limit);
    const scoredHits = [];
    C.forEach(c => {
      const name = c.name.toLowerCase();
      const tick = (c.ticker || "").toLowerCase();
      let s = 0;
      if (tick === q) s = 100;
      else if (tick.startsWith(q)) s = 80;
      else if (tick.includes(q)) s = 50;
      else if (name.startsWith(q)) s = 40;
      else if (name.includes(q)) s = 20;
      if (s) scoredHits.push([s, c]);
    });
    scoredHits.sort((a, b) => b[0] - a[0] || (b[1].tdi || 0) - (a[1].tdi || 0));
    return scoredHits.slice(0, limit).map(x => x[1]);
  }
  let palMode = false, palIdx = 0, palHits = [];
  const pal = $("pal");
  function paintPal() {
    $("pl").innerHTML = palHits.map((c, i) =>
      `<button type="button" class="hit${i === palIdx ? " on" : ""}" data-i="${i}">
        <b>${esc(c.ticker || "—")}</b><span>${esc(c.name)}</span><em>${c.tdi != null ? c.tdi.toFixed(1) : "–"}</em>
      </button>`).join("") || `<div class="hit muted">No matches</div>`;
  }
  function parseCmd(raw) {
    const s = (raw || "").trim().toLowerCase();
    if (!s) return null;
    if (/^(tour|demo|wow)$/.test(s)) return { type: "tour" };
    if (/^play/.test(s)) return { type: "play" };
    const yr = s.match(/^(?:year|in)\s+(20\d{2})$/) || s.match(/^(20\d{2})$/);
    if (yr && Y.includes(+yr[1])) return { type: "year", y: +yr[1] };
    const topm = s.match(/^top\s+([a-z]+)/);
    if (topm) {
      const cat = cats.find(k => k.toLowerCase() === topm[1] || k.toLowerCase().startsWith(topm[1]));
      if (cat) return { type: "cat", cat };
    }
    const vs = s.match(/^compare\s+(.+?)\s+(?:and|vs|,)\s+(.+)$/) ||
      s.match(/^(.+?)\s+(?:vs\.?|versus)\s+(.+)$/);
    if (vs) return { type: "vs", a: vs[1], b: vs[2] };
    return null;
  }
  function runCmd(cmd) {
    closePal();
    if (cmd.type === "tour") return runTour();
    if (cmd.type === "play") {
      $("explore").scrollIntoView({ behavior: "smooth" });
      return playYears();
    }
    if (cmd.type === "year") {
      setYear(Y.indexOf(cmd.y));
      $("explore").scrollIntoView({ behavior: "smooth" });
      return;
    }
    if (cmd.type === "cat") {
      $("cat").value = cmd.cat;
      page = 0; render();
      $("explore").scrollIntoView({ behavior: "smooth" });
      return;
    }
    if (cmd.type === "vs") {
      const a = resolveFirm(cmd.a), b = resolveFirm(cmd.b);
      if (a && b && a.id !== b.id) return openCompare(a, b);
    }
  }
  function openPal(forCompare) {
    palMode = !!forCompare;
    pal.hidden = false;
    $("pq").value = "";
    $("palhint").textContent = palMode
      ? `Comparing with ${compareA.ticker || compareA.name}. Pick a second company.`
      : "Try NVDA, “NVDA vs INTC”, “top AI”, “2018”, or “tour”.";
    palHits = searchHits("", 10);
    palIdx = 0;
    paintPal();
    $("pq").focus();
  }
  function closePal() { pal.hidden = true; }
  function pickPal(c) {
    closePal();
    if (palMode && compareA && c.id !== compareA.id) openCompare(compareA, c);
    else openCompany(c.id);
  }
  $("pq").oninput = () => { palHits = searchHits($("pq").value, 12); palIdx = 0; paintPal(); };
  $("pl").onclick = e => {
    const h = e.target.closest(".hit[data-i]");
    if (h) pickPal(palHits[+h.dataset.i]);
  };
  $("pq").onkeydown = e => {
    if (e.key === "ArrowDown") { e.preventDefault(); palIdx = Math.min(palHits.length - 1, palIdx + 1); paintPal(); }
    if (e.key === "ArrowUp") { e.preventDefault(); palIdx = Math.max(0, palIdx - 1); paintPal(); }
    if (e.key === "Enter") {
      const cmd = parseCmd($("pq").value);
      if (cmd) { e.preventDefault(); runCmd(cmd); return; }
      if (palHits[palIdx]) pickPal(palHits[palIdx]);
    }
    if (e.key === "Escape") closePal();
  };
  pal.addEventListener("click", e => { if (e.target === pal) closePal(); });
  $("openK").onclick = () => openPal(false);
  $("openK").querySelector("kbd").textContent = mac ? "⌘K" : "Ctrl K";
  $("pq").placeholder = `Search ${cv.total_companies.toLocaleString()} companies by name or ticker…`;

  const LANE = [
    ["NVDA", "#0f172a"], ["INTC", "#d97706"], ["AMD", "#047857"], ["AAPL", "#1d4ed8"],
    ["MSFT", "#7c3aed"], ["GOOGL", "#0e7490"], ["META", "#b45309"], ["TSLA", "#b91c1c"]
  ];
  function paintLanes() {
    if (!$("lanes")) return;
    const firms = LANE.map(([t, col]) => ({ c: tickIndex[t], col, t })).filter(x => x.c);
    if (!firms.length) return;
    $("lanes").innerHTML = chart(
      firms.map(x => x.c.history || []),
      firms.map(x => x.col),
      { bare: true }
    );
    $("laneleg").innerHTML = firms.map(x =>
      `<button type="button" class="chip" data-id="${x.c.id}"><i class="lg" style="background:${x.col};width:12px"></i>${x.t} <span>${tdiAt(x.c) != null ? tdiAt(x.c).toFixed(1) : "–"}</span></button>`
    ).join("");
  }
  if ($("laneleg")) $("laneleg").onclick = e => {
    const b = e.target.closest("[data-id]");
    if (b) openCompany(+b.dataset.id);
  };

  function paintMovers() {
    if (!$("movers")) return;
    if (yi === 0) {
      $("movers").innerHTML = `<p class="muted small">Move the year slider past ${Y[0]} to see who climbed or slipped.</p>`;
      return;
    }
    const rows = C.filter(c => c.listed && c.ticker && c.components == 2
      && tdiAt(c, 0) != null && tdiAt(c, yi) != null)
      .map(c => ({ c, a: tdiAt(c, 0), b: tdiAt(c, yi), d: tdiAt(c, yi) - tdiAt(c, 0) }))
      .filter(x => Math.abs(x.d) >= 1);
    const up = [...rows].sort((a, b) => b.d - a.d || b.b - a.b).slice(0, 8);
    const down = [...rows].sort((a, b) => a.d - b.d || a.b - b.b).slice(0, 8);
    const mk = (list, upFlag) => list.map(x =>
      `<button type="button" class="mv" data-id="${x.c.id}" title="${x.a.toFixed(1)} → ${x.b.toFixed(1)}">
        <b>${esc(x.c.ticker)}</b><span class="muted">${esc(x.c.name)}</span>
        <em class="${upFlag ? "up" : "dn"}">${x.d > 0 ? "+" : ""}${x.d.toFixed(1)}</em>
      </button>`
    ).join("");
    $("movers").innerHTML = `<div class="mvgrid"><div><div class="muted small" style="margin-bottom:6px">Climbed ${Y[0]}–${Y[yi]}</div>${mk(up, true)}</div>
      <div><div class="muted small" style="margin-bottom:6px">Slipped ${Y[0]}–${Y[yi]}</div>${mk(down, false)}</div></div>`;
  }
  if ($("movers")) $("movers").onclick = e => {
    const b = e.target.closest("[data-id]");
    if (b) openCompany(+b.dataset.id);
  };

  let scatPts = [];
  function paintScatter() {
    const cv = $("scat");
    if (!cv) return;
    scatPts = C.filter(c => c.listed && c.patent != null && c.startup != null);
    const wrap = cv.parentElement;
    const cssW = Math.max(280, (wrap && wrap.clientWidth ? wrap.clientWidth : 640) - 48);
    const cssH = 400;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = cssW * dpr;
    cv.height = cssH * dpr;
    cv.style.width = cssW + "px";
    cv.style.height = cssH + "px";
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);
    const pad = 36;
    const X = p => pad + (p / 100) * (cssW - 2 * pad);
    const Yy = s => cssH - pad - (s / 100) * (cssH - 2 * pad);
    ctx.strokeStyle = "#e6e0d4";
    ctx.lineWidth = 1;
    [0, 50, 100].forEach(g => {
      ctx.beginPath(); ctx.moveTo(pad, Yy(g)); ctx.lineTo(cssW - pad, Yy(g)); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(X(g), pad); ctx.lineTo(X(g), cssH - pad); ctx.stroke();
    });
    ctx.fillStyle = "#5b6474";
    ctx.font = "11px ui-sans-serif, system-ui, sans-serif";
    ctx.fillText("Patent →", cssW - pad - 52, cssH - 10);
    ctx.fillText("Startup →", 8, 16);
    scatPts.forEach(c => {
      ctx.fillStyle = "rgba(15,23,42,0.22)";
      ctx.beginPath();
      ctx.arc(X(c.patent), Yy(c.startup), 2.6, 0, Math.PI * 2);
      ctx.fill();
    });
    const named = LANE.map(([t, col]) => ({ c: tickIndex[t], col, t })).filter(x => x.c && x.c.patent != null && x.c.startup != null);
    named.forEach(x => {
      ctx.fillStyle = x.col;
      ctx.beginPath();
      ctx.arc(X(x.c.patent), Yy(x.c.startup), 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.fillStyle = x.col;
      ctx.fillText(x.t, X(x.c.patent) + 7, Yy(x.c.startup) - 6);
    });
    cv._map = { X, Yy, cssW, cssH };
  }
  function nearestDot(mx, my) {
    const m = $("scat") && $("scat")._map;
    if (!m) return null;
    let best = null, bd = 14 * 14;
    scatPts.forEach(c => {
      const dx = m.X(c.patent) - mx, dy = m.Yy(c.startup) - my, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = c; }
    });
    return best;
  }
  if ($("scat")) {
    $("scat").onclick = e => {
      const r = $("scat").getBoundingClientRect();
      const hit = nearestDot(e.clientX - r.left, e.clientY - r.top);
      if (hit) openCompany(hit.id);
    };
    $("scat").onmousemove = e => {
      const r = $("scat").getBoundingClientRect();
      const hit = nearestDot(e.clientX - r.left, e.clientY - r.top);
      $("scat").style.cursor = hit ? "pointer" : "crosshair";
      if ($("scattip")) {
        $("scattip").textContent = hit
          ? `${hit.ticker || hit.name}: patent ${hit.patent.toFixed(1)} · startup ${hit.startup.toFixed(1)} · index ${hit.tdi != null ? hit.tdi.toFixed(1) : "–"}`
          : `${scatPts.length.toLocaleString()} listed firms with both scores. Click a point.`;
      }
    };
  }

  function paintHist(mark) {
    const b = new Array(10).fill(0); let z = 0;
    C.forEach(c => { if (c.tdi == null) return; if (c.tdi === 0) { z++; return; } b[Math.min(9, Math.floor(c.tdi / 10))]++; });
    const bins = [["=0", z], ...b.map((n, i) => [i ? i * 10 + "+" : ">0", n])];
    const W = 640, H = 230, P = 26, m = Math.max(...bins.map(x => x[1])), bw = (W - 2 * P) / bins.length;
    let pin = "";
    if (mark != null) {
      const idx = mark === 0 ? 0 : 1 + Math.min(9, Math.floor(mark / 10));
      const x = P + idx * bw + bw / 2;
      pin = `<line x1="${x}" x2="${x}" y1="8" y2="${H - P}" stroke="#d97706" stroke-width="2"/>
        <text x="${Math.max(4, x - 18)}" y="14" style="fill:#d97706">${mark.toFixed(1)}</text>`;
    }
    $("hist").innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%">` + bins.map((x, i) => {
      const h = x[1] / m * (H - 2 * P - 14);
      return `<rect x="${P + i * bw + 3}" y="${H - P - h}" width="${bw - 6}" height="${h}" rx="3" fill="${i ? "#1e293b" : "#d97706"}"/>
        <text x="${P + i * bw + bw / 2 - 8}" y="${H - 8}">${x[0]}</text>
        <text x="${P + i * bw + bw / 2 - 12}" y="${H - P - h - 6}">${x[1] >= 1000 ? (x[1] / 1000).toFixed(1) + "k" : x[1]}</text>`;
    }).join("") + pin + "</svg>";
  }
  paintHist();

  $("inds").innerHTML = "<table>" + D.industries.map(r =>
    `<tr><td>${esc(r[0])}</td><td class="r"><b>${r[1].toFixed(1)}</b><span class="meter"><i style="width:${r[1]}%"></i></span></td>
     <td class="r muted small">${r[2].toLocaleString()}</td></tr>`).join("") + "</table>";

  (function results() {
    const L = { M1: "Market valuation", M1b: "Valuation change", M2: "Revenue growth", M3: "R&D / assets", M4: "CAPEX / assets" };
    const S = { main_year: "Year FE", main_year_sic2: "+ Industry FE", main_sic2xyear: "Industry×year FE", main_firm_year: "Firm FE" };
    const specs = Object.keys(S);
    let h = "<table><tr><th>Outcome (t+1)</th>" + specs.map(s => `<th class="r">${S[s]}</th>`).join("") + "</tr>";
    Object.keys(L).forEach(m => {
      h += `<tr><td>${L[m]}</td>` + specs.map(s => {
        const r = D.results.find(x => x.model == m && x.spec == s);
        return r && r.coef != null
          ? `<td class="r ${r.p_value < .05 ? "sig" : ""}">${r.coef.toFixed(3)}</td>`
          : '<td class="r muted">–</td>';
      }).join("") + "</tr>";
    });
    $("res").innerHTML = h + "</table>";

    const m1 = specs.map(s => D.results.find(x => x.model === "M1" && x.spec === s)).filter(Boolean);
    const maxAbs = Math.max(...m1.map(r => Math.abs((Math.exp(r.coef) - 1) * 100)), 1);
    $("forest").innerHTML = m1.map(r => {
      const pctV = (Math.exp(r.coef) - 1) * 100;
      const w = Math.max(2, Math.abs(pctV) / maxAbs * 100);
      const lab = S[r.spec];
      const cls = r.p_value < 0.05 ? "pos" : "zero";
      return `<div class="fb"><span>${lab}</span><span class="fbar"><i class="${cls}" style="width:${w}%"></i></span>
        <b class="${cls}">${pctV >= 0 ? "+" : ""}${pctV.toFixed(1)}%</b></div>`;
    }).join("") + '<p class="muted small">Approximate % difference in next-year public float per +10 index points (from exp(coef)−1). Firm FE is the within-company test.</p>';
  })();

  async function playYears() {
    playing = true;
    if ($("yplay")) $("yplay").textContent = "Pause";
    for (let i = 0; i < Y.length && playing; i++) {
      setYear(i);
      await sleep(480);
    }
    playing = false;
    if ($("yplay")) $("yplay").textContent = "Play decade";
  }
  if ($("yslider")) {
    $("yslider").max = Y.length - 1;
    $("yslider").value = yi;
    $("yslider").oninput = () => { playing = false; setYear(+$("yslider").value); };
  }
  if ($("yplay")) $("yplay").onclick = () => {
    if (playing) { playing = false; $("yplay").textContent = "Play decade"; }
    else playYears();
  };
  if ($("tourBtn")) $("tourBtn").onclick = () => runTour();
  if ($("ask")) {
    $("ask").onkeydown = e => {
      if (e.key !== "Enter") return;
      const cmd = parseCmd($("ask").value) || { type: "firm", q: $("ask").value };
      if (cmd.type === "firm") {
        const f = resolveFirm(cmd.q);
        if (f) openCompany(f.id);
        else openPal(false);
      } else runCmd(cmd);
    };
  }

  async function runTour() {
    if (touring) return;
    touring = true;
    const board = $("tour");
    const txt = $("tourtxt");
    const show = m => { if (board) { board.hidden = false; txt.textContent = m; } };
    const skip = () => { touring = playing = false; if (board) board.hidden = true; };
    if ($("tourx")) $("tourx").onclick = skip;
    closePal();
    closeOv();
    setYear(Y.length - 1, false);
    document.querySelector(".finding").scrollIntoView({ behavior: "smooth", block: "center" });
    document.querySelector(".finding").classList.add("pulse");
    show("1 / 5  The result: +8.7% next-year public float vs industry peers. Same firm over time: ~0%.");
    await sleep(3800); if (!touring) return;
    document.querySelector(".finding").classList.remove("pulse");
    const nv = tickIndex.NVDA, intel = tickIndex.INTC;
    show("2 / 5  NVIDIA — score vs its manufacturing peers, and the associated valuation gap.");
    if (nv) openCompany(nv.id);
    await sleep(4200); if (!touring) return;
    show("3 / 5  NVIDIA vs Intel. Same industry, different patent momentum.");
    if (nv && intel) openCompare(nv, intel);
    await sleep(4500); if (!touring) return;
    closeOv();
    show("4 / 5  Time machine: the top-ten list from 2015 to 2024.");
    $("explore").scrollIntoView({ behavior: "smooth" });
    await playYears(); if (!touring) return;
    show("5 / 5  The forest plot: only the within-firm test collapses to zero.");
    $("research").scrollIntoView({ behavior: "smooth" });
    await sleep(4200);
    skip();
  }

  function applyHash() {
    const h = (location.hash || "").replace(/^#/, "");
    if (h === "tour") return runTour();
    const y = h.match(/^y\/(20\d{2})/);
    if (y && Y.includes(+y[1])) {
      closeOv(true);
      setYear(Y.indexOf(+y[1]));
      return;
    }
    const c = h.match(/^c\/(\d+)/);
    const v = h.match(/^vs\/(\d+)\/(\d+)/);
    if (c && byId[+c[1]]) openCompany(+c[1]);
    else if (v && byId[+v[1]] && byId[+v[2]]) openCompare(byId[+v[1]], byId[+v[2]]);
    else closeOv(true);
  }
  window.addEventListener("hashchange", applyHash);

  document.addEventListener("keydown", e => {
    const inField = /INPUT|SELECT|TEXTAREA/.test(e.target.tagName);
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPal(false); }
    if (e.key === "Escape") {
      if (touring) { touring = playing = false; if ($("tour")) $("tour").hidden = true; }
      if (!pal.hidden) closePal(); else if (!ov.hidden) closeOv();
    }
    if (e.key === "/" && !inField) { e.preventDefault(); $("q").focus(); }
  });

  const fig = document.querySelector(".finding .fig");
  if (fig && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const target = parseFloat(fig.textContent);
    if (!isNaN(target)) {
      const t0 = performance.now();
      const tick = now => {
        const k = Math.min(1, (now - t0) / 900);
        const eased = 1 - Math.pow(1 - k, 3);
        fig.textContent = (target >= 0 ? "+" : "") + (target * eased).toFixed(1) + "%";
        if (k < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }
  }

  paintTop();
  paintLanes();
  paintMovers();
  paintScatter();
  window.addEventListener("resize", () => { paintScatter(); });
  render();
  if (location.hash) applyHash();
});
