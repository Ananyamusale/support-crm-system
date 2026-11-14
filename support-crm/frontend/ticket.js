"use strict";
(async () => {
  const me = await requireLogin();
  renderHeader(me, "Ticket details");
  const id = new URLSearchParams(window.location.search).get("id") || "";
  const box = document.getElementById("detail");

  let t;
  try { t = await api(`/api/tickets/${encodeURIComponent(id)}`); }
  catch (e) { box.append(el("div", { class: "card err", text: e.message })); return; }

  const card = el("div", { class: "card" }, [
    el("div", { class: "between" }, [el("h2", { text: t.ticket_id }), badge(t.status)]),
    el("p", { class: "subject", text: t.subject }),
    el("div", { class: "muted", text: `${t.customer_name} <${t.customer_email}>` }),
    el("pre", { class: "desc", text: t.description }),
    el("div", { class: "muted", text: `Created ${new Date(t.created_at + "Z").toLocaleString()} • Updated ${new Date(t.updated_at + "Z").toLocaleString()}` }),
  ]);
  box.append(card);

  if (me.role === "customer") {
    box.append(el("div", { class: "card" }, [el("b", { text: "Agent notes" }), el("pre", { class: "desc", text: t.notes || "No notes yet." })]));
    return;
  }

  // Agents and admins can update status and notes
  const select = el("select", { id: "st" }, ["Open", "In Progress", "Resolved", "Closed"].map(s => el("option", { value: s, text: s })));
  select.value = t.status;
  const notes = el("textarea", { id: "notes", maxlength: "2000" });
  notes.value = t.notes || "";
  const err = el("div", { class: "err" });
  const form = el("form", { class: "card" }, [
    el("h2", { text: "Update ticket" }),
    el("label", { for: "st", text: "Status" }), select,
    el("label", { for: "notes", text: "Notes" }), notes, err,
    el("button", { class: "btn", type: "submit", text: "Save" }),
  ]);
  form.addEventListener("submit", async e => {
    e.preventDefault(); err.textContent = "";
    try {
      await api(`/api/tickets/${encodeURIComponent(id)}`, { method: "PUT", body: { status: select.value, notes: notes.value } });
      showToast("Ticket updated");
    } catch (ex) { err.textContent = ex.message; }
  });
  box.append(form);
})();
