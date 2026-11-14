"use strict";
(async () => {
  const me = await requireLogin();
  renderHeader(me, "Create a support ticket");
  document.getElementById("form").addEventListener("submit", async e => {
    e.preventDefault();
    const err = document.getElementById("err");
    err.textContent = "";
    try {
      const r = await api("/api/tickets", { method: "POST", body: {
        subject: document.getElementById("subject").value,
        description: document.getElementById("description").value,
      } });
      showToast(`Ticket ${r.ticket_id} created`);
      setTimeout(() => { window.location.href = "index.html"; }, 800);
    } catch (ex) { err.textContent = ex.message; }
  });
})();
