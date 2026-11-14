"use strict";
const loginForm = document.getElementById("loginForm");
const regForm = document.getElementById("regForm");

document.getElementById("showReg").addEventListener("click", e => {
  e.preventDefault(); loginForm.classList.add("hidden"); regForm.classList.remove("hidden");
});
document.getElementById("showLogin").addEventListener("click", e => {
  e.preventDefault(); regForm.classList.add("hidden"); loginForm.classList.remove("hidden");
});

loginForm.addEventListener("submit", async e => {
  e.preventDefault();
  const err = document.getElementById("l_err");
  err.textContent = "";
  try {
    const data = await api("/api/auth/login", { method: "POST", body: {
      username: document.getElementById("l_user").value,
      password: document.getElementById("l_pass").value,
    } });
    setCsrf(data.csrf_token);
    window.location.href = "index.html";
  } catch (ex) {
    err.textContent = ex.message;
  }
});

regForm.addEventListener("submit", async e => {
  e.preventDefault();
  const err = document.getElementById("r_err");
  err.textContent = "";
  try {
    await api("/api/auth/register", { method: "POST", body: {
      username: document.getElementById("r_user").value,
      full_name: document.getElementById("r_name").value,
      email: document.getElementById("r_email").value,
      password: document.getElementById("r_pass").value,
    } });
    regForm.reset();
    regForm.classList.add("hidden"); loginForm.classList.remove("hidden");
    showToast("Account created. Please sign in.");
  } catch (ex) {
    err.textContent = ex.message;
  }
});
