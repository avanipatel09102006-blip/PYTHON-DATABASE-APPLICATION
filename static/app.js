const $ = id => document.getElementById(id);
const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
const inr = n => "₹" + Math.round(n).toLocaleString("en-IN");
let tab = "employees", depts = [], editing = null, tt;
const toast = m => { const t = $("toast"); t.textContent = m; t.classList.add("show"); clearTimeout(tt); tt = setTimeout(() => t.classList.remove("show"), 2800); };
const call = async (url, method = "GET", body) => { const r = await fetch(url, {method, headers: {"Content-Type": "application/json"}, body: body && JSON.stringify(body)}); return {ok: r.ok, d: await r.json()}; };

const FORMS = {
  employees: {title: "employee", url: "/api/employees", fields: () => [
    ["name", "Full name", "text"], ["emp_code", "Employee code", "text"], ["email", "Email", "email"], ["designation", "Designation", "text"],
    ["department_id", "Department", "select", depts.map(d => [d.id, d.name])], ["salary", "Monthly salary (₹)", "number"], ["hire_date", "Hire date", "date"]]},
  departments: {title: "department", url: "/api/departments", fields: () => [["name", "Department name", "text"], ["location", "Location", "text"]]},
};

function table(headId, bodyId, cols, rows, onEdit, onDel) {
  const h = $(headId), b = $(bodyId); h.innerHTML = b.innerHTML = "";
  const hr = el("tr"); cols.forEach(c => hr.append(el("th", "", c.label))); hr.append(el("th")); h.append(hr);
  rows.forEach(r => {
    const tr = el("tr");
    cols.forEach(c => { const td = el("td"); td.dataset.l = c.label; c.render(td, r); tr.append(td); });
    const td = el("td", "none"), a = el("div", "acts"), e = el("button", "", "Edit"), d = el("button", "del", "Delete");
    e.onclick = () => onEdit(r); d.onclick = () => onDel(r); a.append(e, d); td.append(a); tr.append(td); b.append(tr);
  });
}
const txt = k => (td, r) => td.textContent = r[k];

async function loadDepts() {
  const r = await call("/api/departments"); depts = r.d;
  const sel = $("deptFilter"), cur = sel.value; sel.innerHTML = ""; sel.append(new Option("All departments", ""));
  depts.forEach(d => sel.append(new Option(d.name, d.id))); sel.value = cur;
  table("depHead", "depBody", [
    {label: "Department", render: txt("name")}, {label: "Location", render: (td, r) => td.textContent = r.location || "-"},
    {label: "Employees", render: (td, r) => td.append(el("span", "tag", r.employees))}], depts, openForm.bind(null, "departments"), delDept);
  $("depBody").parentElement.parentElement.parentElement.classList.add("cards");
}

async function loadEmployees() {
  const p = new URLSearchParams({q: $("q").value.trim(), dept: $("deptFilter").value, sort: $("sort").value});
  const rows = (await call("/api/employees?" + p)).d;
  $("empEmpty").hidden = rows.length > 0;
  table("empHead", "empBody", [
    {label: "Employee", render: (td, r) => { td.append(el("b", "", r.name), el("small", "sub", r.email)); }},
    {label: "Code", render: txt("emp_code")}, {label: "Role", render: txt("designation")},
    {label: "Department", render: (td, r) => td.append(el("span", "tag", r.department))},
    {label: "Salary", render: (td, r) => td.textContent = inr(r.salary)}, {label: "Hired", render: txt("hire_date")}],
    rows, r => openForm("employees", r), async r => {
      if (!confirm(`Delete ${r.name}?`)) return; await call("/api/employees/" + r.id, "DELETE"); toast("Employee deleted"); loadEmployees(); });
  $("empBody").parentElement.parentElement.parentElement.classList.add("cards");
}

async function loadReports() {
  const d = (await call("/api/reports")).d;
  $("stats").innerHTML = "";
  [[d.total, "Employees"], [inr(d.payroll), "Monthly payroll"], [inr(d.avg), "Average salary"], [d.top ? d.top.name : "-", "Top earner"]].forEach(([v, l]) => {
    const s = el("div", "stat"); s.append(el("span", "", v), el("small", "", l)); $("stats").append(s); });
  const max = Math.max(1, ...d.by_dept.map(x => x.payroll)); $("deptBars").innerHTML = "";
  d.by_dept.forEach(x => { const r = el("div", "bar"), t = el("div", "t"), i = el("i"); i.style.width = x.payroll / max * 100 + "%"; t.append(i);
    r.append(el("span", "", `${x.name} (${x.headcount})`), t, el("span", "", inr(x.payroll))); $("deptBars").append(r); });
  $("recent").innerHTML = "";
  d.recent.forEach(x => { const li = el("li"); li.append(el("b", "", x.name), el("small", "sub", `${x.designation}, ${x.department} · ${x.hire_date}`)); $("recent").append(li); });
}

async function loadSchema() {
  const s = (await call("/api/schema")).d; $("schema").innerHTML = "";
  Object.entries(s).forEach(([t, cols]) => { const b = el("div", "t"), n = el("b", "", t); n.onclick = () => { $("sql").value = `SELECT * FROM ${t} LIMIT 20`; };
    b.append(n); cols.forEach(c => b.append(el("small", "", `${c.name} ${c.type}${c.pk ? " (PK)" : ""}`))); $("schema").append(b); });
}

async function runQuery() {
  $("qErr").textContent = ""; const r = await call("/api/query", "POST", {sql: $("sql").value}); const t = $("result"); t.innerHTML = "";
  if (!r.ok) { $("qErr").textContent = r.d.error; return; }
  const hr = el("tr"); r.d.columns.forEach(c => hr.append(el("th", "", c))); const th = el("thead"); th.append(hr); t.append(th);
  const tb = el("tbody"); r.d.rows.forEach(row => { const tr = el("tr"); row.forEach(v => tr.append(el("td", "", v === null ? "NULL" : v))); tb.append(tr); }); t.append(tb);
  if (r.d.truncated) $("qErr").textContent = "Showing first 200 rows.";
}

function openForm(kind, item) {
  editing = {kind, id: item ? item.id : null}; const cfg = FORMS[kind];
  $("dlgTitle").textContent = (item ? "Edit " : "Add ") + cfg.title; $("formErr").textContent = ""; $("fields").innerHTML = "";
  cfg.fields().forEach(([name, label, type, opts]) => {
    const l = el("label", "", label); let i;
    if (type === "select") { i = el("select"); opts.forEach(([v, t]) => i.append(new Option(t, v))); } else { i = el("input"); i.type = type; if (type === "number") { i.min = 0; i.step = "any"; } }
    i.name = name; i.required = name !== "location"; if (item) i.value = item[name] ?? ""; l.append(i); $("fields").append(l); });
  $("dlg").showModal();
}

$("form").addEventListener("submit", async e => {
  e.preventDefault(); if (!e.target.checkValidity()) return e.target.reportValidity();
  const {kind, id} = editing, body = Object.fromEntries(new FormData(e.target));
  const r = await call(FORMS[kind].url + (id ? "/" + id : ""), id ? "PUT" : "POST", body);
  if (!r.ok) { $("formErr").textContent = r.d.error; return; }
  $("dlg").close(); toast("Saved"); await loadDepts(); refresh();
});
async function delDept(d) {
  if (!confirm(`Delete department ${d.name}?`)) return;
  const r = await call("/api/departments/" + d.id, "DELETE"); toast(r.ok ? "Department deleted" : r.d.error); loadDepts();
}

function refresh() { ({employees: loadEmployees, departments: loadDepts, reports: loadReports, console: loadSchema})[tab](); }
$("tabs").onclick = e => { const b = e.target.closest("button"); if (!b) return; tab = b.dataset.t;
  document.querySelectorAll("#tabs button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll(".panel").forEach(p => p.hidden = p.id !== tab);
  $("addBtn").textContent = tab === "departments" ? "Add department" : "Add employee"; $("addBtn").hidden = tab === "reports" || tab === "console"; refresh(); };
$("addBtn").onclick = () => openForm(tab === "departments" ? "departments" : "employees");
$("cancel").onclick = () => $("dlg").close();
let st; $("q").oninput = () => { clearTimeout(st); st = setTimeout(loadEmployees, 250); };
$("deptFilter").onchange = $("sort").onchange = loadEmployees;
$("run").onclick = runQuery; $("sql").onkeydown = e => { if (e.ctrlKey && e.key === "Enter") runQuery(); };
loadDepts().then(loadEmployees);
