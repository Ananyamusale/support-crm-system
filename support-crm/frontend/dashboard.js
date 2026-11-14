"use strict";
let me;

async function loadTickets() {
  const params = new URLSearchParams();
  const search = document.getElementById("search").value.trim();
  const status = document.getElementById("status").value;
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  try {
    const data = await api(`/api/tickets?${params}`);
    render(data);
    document.getElementById("total").textContent = data.length;
    document.getElementById("open").textContent = data.filter(t => t.status === "Open").length;
    document.getElementById("closed").textContent = data.filter(t => t.status === "Closed").length;
  } catch (e) {
    showToast(e.message, "red");
  }
}

function render(data) {
  const box = document.getElementById("tickets");
  box.replaceChildren();
  if (!data.length) { box.append(el("div", { class: "card muted", text: "No tickets found." })); return; }
  for (const t of data) {
    const actions = el("div", { class: "mt8" }, [
      el("a", { class: "link", href: `ticket.html?id=${encodeURIComponent(t.ticket_id)}`, text: "View" }),
    ]);
    if (me.role === "admin") {
      actions.append(el("button", { class: "btn red small", text: "Delete", on: { click: () => deleteTicket(t.ticket_id) } }));
    }
    box.append(el("div", { class: "card" }, [
      el("div", { class: "between" }, [el("b", { text: t.ticket_id }), badge(t.status)]),
      el("p", { class: "subject", text: t.subject }),
      el("div", { class: "muted", text: `${t.customer_name} • ${new Date(t.created_at + "Z").toLocaleString()}` }),
      actions,
    ]));
  }
}

async function deleteTicket(id) {
  if (!confirm("Delete this ticket?")) return;
  try {
    await api(`/api/tickets/${encodeURIComponent(id)}`, { method: "DELETE" });
    showToast("Ticket deleted");
    loadTickets();
  } catch (e) { showToast(e.message, "red"); }
}

(async () => {
  me = await requireLogin();
  renderHeader(me, me.role === "customer" ? "My support tickets" : "Customer support ticket management");
  document.getElementById("searchBtn").addEventListener("click", loadTickets);
  document.getElementById("search").addEventListener("keydown", e => { if (e.key === "Enter") loadTickets(); });
  loadTickets();
})();
