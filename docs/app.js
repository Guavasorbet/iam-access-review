// Access Review Dashboard — reads window.ACCESS_REVIEW (docs/findings.js).
(function () {
  const data = window.ACCESS_REVIEW;
  const S = data.summary;
  const F = data.findings;
  const SEVERITIES = ["Critical", "High", "Medium", "Low"];
  const SEV_VAR = { Critical: "--sev-critical", High: "--sev-high", Medium: "--sev-medium", Low: "--sev-low" };
  const STORE_KEY = "iam-review-decisions-" + S.review_date;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---- decisions: saved in this browser only ---------------------------
  let decisions = {};
  try { decisions = JSON.parse(localStorage.getItem(STORE_KEY) || "{}"); } catch (e) { decisions = {}; }
  const save = () => { try { localStorage.setItem(STORE_KEY, JSON.stringify(decisions)); } catch (e) { /* storage unavailable */ } };
  const decisionOf = (id) => (decisions[id] && decisions[id].decision) || "Pending";

  // ---- theme -----------------------------------------------------------
  try { const t = localStorage.getItem("iam-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
  $("theme").addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("iam-theme", root.dataset.theme); } catch (e) {}
  });

  const sevBadge = (s) => `<span class="sev-badge" data-sev="${s}" style="--c: var(${SEV_VAR[s]})">${s}</span>`;

  // ---- header + KPIs ---------------------------------------------------
  $("sub").textContent = `${S.company} · review date ${S.review_date} · ${S.identities} identities, ${S.entitlements} entitlements, ${S.badges_active} active badges`;
  const kpis = [
    `<div class="kpi"><div class="label">People reviewed</div><div class="value">${S.identities}</div><div class="note">${S.accounts_enabled} enabled accounts</div></div>`,
    `<div class="kpi"><div class="label">People flagged</div><div class="value">${S.users_with_findings}</div><div class="note">${(100 - S.clean_pct).toFixed(1)}% need follow-up</div></div>`,
    ...SEVERITIES.map((s) => `<div class="kpi sev" style="--c: var(${SEV_VAR[s]})"><div class="label">${sevBadge(s)}</div><div class="value">${S.by_severity[s]}</div><div class="note">findings</div></div>`),
  ];
  $("kpis").innerHTML = kpis.join("");

  // ---- bar charts ------------------------------------------------------
  const tip = $("tip");
  function showTip(e, html) {
    tip.innerHTML = html; tip.hidden = false;
    const x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    const y = Math.min(e.clientY + 14, window.innerHeight - tip.offsetHeight - 8);
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function bars(el, rows) {
    const max = Math.max(...rows.map((r) => r.count), 1);
    el.innerHTML = rows.map((r, i) => `
      <div class="bar-row" role="listitem" data-i="${i}" tabindex="0" aria-label="${esc(r.label)}: ${r.count}">
        <div class="bar-name">${r.labelHtml}</div>
        <div class="bar-track"><div class="bar" style="width:${(85 * r.count) / max}%"></div><span class="bar-val">${r.count}</span></div>
      </div>`).join("");
    el.querySelectorAll(".bar-row").forEach((row) => {
      const r = rows[+row.dataset.i];
      row.addEventListener("mousemove", (e) => showTip(e, r.tip));
      row.addEventListener("mouseleave", () => (tip.hidden = true));
      row.addEventListener("click", r.onClick);
      row.addEventListener("keydown", (e) => { if (e.key === "Enter") r.onClick(); });
    });
  }
  bars($("by-rule"), S.by_rule.map((r) => ({
    count: r.count, label: `${r.rule_id} ${r.name}`,
    labelHtml: `<span class="rid">${r.rule_id}</span>${esc(r.name)}`,
    tip: `<b>${r.rule_id} · ${esc(r.name)}</b>${sevBadge(r.severity)}<br>${r.count} findings<br><span class="muted">NIST ${esc(r.control)}</span><br><span class="muted">Click to filter the worksheet</span>`,
    onClick: () => { $("f-rule").value = r.rule_id; render(); $("rows").scrollIntoView({ behavior: "smooth", block: "start" }); },
  })));
  bars($("by-dept"), Object.entries(S.by_department).map(([d, n]) => ({
    count: n, label: d, labelHtml: esc(d),
    tip: `<b>${esc(d)}</b>${n} findings<br><span class="muted">Click to filter the worksheet</span>`,
    onClick: () => { $("f-dept").value = d; render(); $("rows").scrollIntoView({ behavior: "smooth", block: "start" }); },
  })));

  // ---- filters ---------------------------------------------------------
  const fill = (sel, items) => items.forEach(([v, t]) => sel.insertAdjacentHTML("beforeend", `<option value="${esc(v)}">${esc(t)}</option>`));
  fill($("f-sev"), SEVERITIES.map((s) => [s, s]));
  fill($("f-rule"), S.by_rule.map((r) => [r.rule_id, `${r.rule_id} ${r.name}`]));
  fill($("f-dept"), Object.keys(S.by_department).sort().map((d) => [d, d]));
  ["q", "f-sev", "f-rule", "f-dept", "f-dec"].forEach((id) => $(id).addEventListener("input", render));

  // ---- worksheet table -------------------------------------------------
  function filtered() {
    const q = $("q").value.trim().toLowerCase();
    return F.filter((f) =>
      (!$("f-sev").value || f.severity === $("f-sev").value) &&
      (!$("f-rule").value || f.rule_id === $("f-rule").value) &&
      (!$("f-dept").value || f.department === $("f-dept").value) &&
      (!$("f-dec").value || decisionOf(f.finding_id) === $("f-dec").value) &&
      (!q || [f.finding_id, f.name, f.user_id, f.detail, f.title, f.rule].join(" ").toLowerCase().includes(q)));
  }
  function progress() {
    const done = F.filter((f) => decisionOf(f.finding_id) !== "Pending").length;
    $("progress-label").textContent = `${done} of ${F.length} findings decided`;
    $("progress-bar").style.width = (100 * done) / F.length + "%";
  }
  function render() {
    const rows = filtered();
    $("count").textContent = `Showing ${rows.length} of ${F.length} findings`;
    $("rows").innerHTML = rows.map((f) => {
      const d = decisions[f.finding_id] || {};
      const dec = d.decision || "Pending";
      return `<tr data-id="${f.finding_id}" data-dec="${dec}">
        <td class="id">${f.finding_id}</td>
        <td>${sevBadge(f.severity)}</td>
        <td>${esc(f.rule)}<div class="muted">${f.rule_id}</div></td>
        <td>${esc(f.name)}<div class="muted">${f.user_id} · ${esc(f.title)} · ${esc(f.department)}${f.employment_type === "Contractor" ? " · Contractor" : ""}</div></td>
        <td>${esc(f.detail)}<div class="action">→ ${esc(f.action)}</div></td>
        <td class="muted">${esc(f.control)}</td>
        <td>
          <select aria-label="Decision for ${f.finding_id}">
            ${["Pending", "Revoke", "Keep", "Needs info"].map((o) => `<option ${o === dec ? "selected" : ""} value="${o}">${o === "Keep" ? "Keep (exception)" : o}</option>`).join("")}
          </select>
          <input type="text" placeholder="Reviewer note" aria-label="Note for ${f.finding_id}" value="${esc(d.note || "")}">
        </td>
      </tr>`;
    }).join("");
    progress();
  }
  $("rows").addEventListener("change", (e) => {
    const tr = e.target.closest("tr"); if (!tr) return;
    const id = tr.dataset.id;
    const cur = decisions[id] || {};
    if (e.target.tagName === "SELECT") { cur.decision = e.target.value; tr.dataset.dec = e.target.value; }
    else cur.note = e.target.value;
    cur.decided_at = new Date().toISOString();
    decisions[id] = cur; save(); progress();
  });

  // ---- export + reset --------------------------------------------------
  $("export").addEventListener("click", () => {
    const cols = ["finding_id", "severity", "rule_id", "rule", "user_id", "name", "department", "control", "detail", "decision", "note", "decided_at"];
    const q = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lines = [cols.join(",")].concat(F.map((f) => {
      const d = decisions[f.finding_id] || {};
      const row = { ...f, decision: d.decision || "Pending", note: d.note || "", decided_at: d.decided_at || "" };
      return cols.map((c) => q(row[c])).join(",");
    }));
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `access-review-decisions-${S.review_date}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  });
  $("reset").addEventListener("click", () => {
    if (!Object.keys(decisions).length) return;
    decisions = {}; save(); render();
  });

  render();
})();
