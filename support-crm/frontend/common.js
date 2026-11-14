// Shared helpers. SECURITY: all user data is inserted with textContent (never innerHTML),
// so stored XSS payloads are displayed as harmless text.
"use strict";

let csrfToken = null;

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "on") for (const [ev, fn] of Object.entries(v)) node.addEventListener(ev, fn);
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c != null) node.append(c);
  }
  return node;
}

function showToast(message, color = "green") {
  let t = document.getElementById("toast");
  if (!t) { t = el("div", { id: "toast" }); document.body.append(t); }
  t.textContent = message;
  t.className = color === "red" ? "red" : "";
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => t.classList.add("hidden"), 2500);
}

async function api(path, { method = "GET", body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const preLogin = path === "/api/auth/login" || path === "/api/auth/register";
  if (method !== "GET" && !preLogin) {
    if (!csrfToken) {
      const r = await fetch("/api/auth/csrf", { credentials: "same-origin" });
      if (r.ok) csrfToken = (await r.json()).csrf_token;
    }
    headers["X-CSRF-Token"] = csrfToken || "";
  }
  const res = await fetch(path, {
    method, headers, credentials: "same-origin",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const detail = data && data.detail;
    const msg = Array.isArray(detail) ? detail.map(d => d.msg).join("; ") : (detail || "Request failed");
    const err = new Error(msg); err.status = res.status; throw err;
  }
  return data;
}

function setCsrf(t) { csrfToken = t; }

function applyTheme() {
  try { if (localStorage.getItem("theme") === "dark") document.documentElement.classList.add("dark"); }
  catch { /* storage may be blocked */ }
}
function toggleDark() {
  const dark = document.documentElement.classList.toggle("dark");
  try { localStorage.setItem("theme", dark ? "dark" : "light"); } catch { /* ignore */ }
}
applyTheme();

// Redirects to the login page if the session is missing/expired.
async function requireLogin() {
  try {
    return await api("/api/auth/me");
  } catch (e) {
    window.location.href = "login.html";
    throw e;
  }
}

function renderHeader(user, subtitle) {
  const nav = el("nav");
  nav.append(el("a", { class: "link", href: "index.html", text: "Tickets" }));
  nav.append(el("a", { class: "link", href: "create.html", text: "+ New ticket" }));
  if (user.role === "admin") nav.append(el("a", { class: "link", href: "admin.html", text: "Admin" }));
  nav.append(el("span", { class: "muted", text: `${user.full_name} (${user.role})` }));
  nav.append(el("button", { class: "btn dark small", text: "🌙", on: { click: toggleDark } }));
  nav.append(el("button", { class: "btn red small", text: "Logout", on: { click: async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* ignore */ }
    window.location.href = "login.html";
  } } }));

  const header = el("header", { class: "top" }, [
    el("div", { class: "brand" }, [
      el("div", { class: "logo", text: "🎫" }),
      el("div", {}, [el("h1", { text: "Support CRM" }), el("div", { class: "muted", text: subtitle })]),
    ]),
    nav,
  ]);
  document.getElementById("header").replaceChildren(header);
}

function badge(status) {
  return el("span", { class: `badge ${status.replace(/ /g, "")}`, text: status });
}
