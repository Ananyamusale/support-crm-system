"use strict";
(async () => {
  const me = await requireLogin();
  if (me.role !== "admin") { window.location.href = "index.html"; return; }
  renderHeader(me, "Administration");

  async function loadUsers() {
    const users = await api("/api/admin/users");
    const table = el("table", {}, [
      el("tr", {}, ["ID", "Username", "Name", "Email", "Role", "Active"].map(h => el("th", { text: h }))),
    ]);
    for (const u of users) {
      const roleSel = el("select", {}, ["customer", "agent", "admin"].map(r => el("option", { value: r, text: r })));
      roleSel.value = u.role;
      roleSel.disabled = u.id === me.id;
      roleSel.addEventListener("change", async () => {
        try { await api(`/api/admin/users/${u.id}/role`, { method: "PUT", body: { role: roleSel.value } }); showToast("Role updated"); loadAudit(); }
        catch (e) { showToast(e.message, "red"); loadUsers(); }
      });
      const activeBtn = el("button", { class: `btn small ${u.is_active ? "red" : "green"}`, text: u.is_active ? "Deactivate" : "Activate" });
      activeBtn.disabled = u.id === me.id;
      activeBtn.addEventListener("click", async () => {
        try { await api(`/api/admin/users/${u.id}/active`, { method: "PUT", body: { is_active: !u.is_active } }); loadUsers(); loadAudit(); }
        catch (e) { showToast(e.message, "red"); }
      });
      table.append(el("tr", {}, [
        el("td", { text: u.id }), el("td", { text: u.username }), el("td", { text: u.full_name }),
        el("td", { text: u.email }), el("td", {}, roleSel), el("td", {}, activeBtn),
      ]));
    }
    document.getElementById("users").replaceChildren(table);
  }

  async function loadAudit() {
    const rows = await api("/api/admin/audit");
    const table = el("table", {}, [
      el("tr", {}, ["Time (UTC)", "User", "Action", "Target", "Detail", "IP"].map(h => el("th", { text: h }))),
    ]);
    for (const r of rows) {
      table.append(el("tr", {}, [r.timestamp.replace("T", " ").slice(0, 19), r.username || "", r.action, r.target || "", r.detail || "", r.ip_address || ""]
        .map(v => el("td", { text: v }))));
    }
    document.getElementById("audit").replaceChildren(table);
  }

  loadUsers(); loadAudit();
})();
