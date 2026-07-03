/* MailSaaS front-end behaviours — dependency-free. */
(function () {
  "use strict";

  // ---- CSRF: auto-attach the token to every POST form ------------------- //
  function csrfToken() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  }
  function attachCsrf() {
    var t = csrfToken();
    if (!t) return;
    document.querySelectorAll("form").forEach(function (f) {
      var method = (f.getAttribute("method") || "get").toLowerCase();
      if (method === "post" && !f.querySelector('input[name="csrf_token"]')) {
        var i = document.createElement("input");
        i.type = "hidden";
        i.name = "csrf_token";
        i.value = t;
        f.appendChild(i);
      }
    });
  }

  // ---- Theme toggle (dark / light), persisted in localStorage ----------- //
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("mailsaas-theme", theme); } catch (e) {}
    var btn = document.getElementById("themeToggle");
    if (btn) btn.textContent = theme === "light" ? "🌙" : "☀️";
  }
  function initTheme() {
    // The product ships light-only now — a previously saved "dark" choice is
    // ignored so every page renders the clean light template.
    applyTheme("light");
    var btn = document.getElementById("themeToggle");
    if (btn) btn.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme") || "dark";
      applyTheme(cur === "dark" ? "light" : "dark");
    });
  }

  // ---- Simple / Advanced sidebar mode ----------------------------------- //
  function applyMode(mode) {
    document.body.setAttribute("data-mode", mode);
    try { localStorage.setItem("mailsaas-mode", mode); } catch (e) {}
    document.querySelectorAll("#modeSwitch .ms-btn").forEach(function (b) {
      b.classList.toggle("on", b.getAttribute("data-mode") === mode);
    });
  }
  function initMode() {
    var sw = document.getElementById("modeSwitch");
    if (!sw) return;
    var saved = null;
    try { saved = localStorage.getItem("mailsaas-mode"); } catch (e) {}
    // New users (onboarding incomplete) default to Simple; others to Advanced.
    var def = document.body.getAttribute("data-simple-default") === "1"
      ? "simple" : "advanced";
    applyMode(saved || def);
    sw.querySelectorAll(".ms-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        applyMode(b.getAttribute("data-mode"));
      });
    });
  }

  // ---- Collapsible sidebar sections ------------------------------------- //
  function initSections() {
    var KEY = "mailsaas-open-secs";
    var openSet = {};
    try { openSet = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
    document.querySelectorAll(".nav-sec").forEach(function (sec, i) {
      var btn = sec.querySelector(".nav-toggle");
      var sub = sec.querySelector(".nav-sub");
      if (!btn || !sub) return;
      var id = btn.textContent.trim().slice(0, 24) + i;
      // Restore persisted state (unless the active item forced it open).
      if (!btn.classList.contains("open") && openSet[id]) {
        btn.classList.add("open"); sub.removeAttribute("hidden");
      }
      btn.addEventListener("click", function () {
        var isOpen = btn.classList.toggle("open");
        if (isOpen) sub.removeAttribute("hidden"); else sub.setAttribute("hidden", "");
        openSet[id] = isOpen;
        try { localStorage.setItem(KEY, JSON.stringify(openSet)); } catch (e) {}
      });
    });
  }

  // ---- Mobile sidebar toggle -------------------------------------------- //
  function initNav() {
    var burger = document.getElementById("navToggle");
    var sidebar = document.querySelector(".sidebar");
    if (burger && sidebar) {
      burger.addEventListener("click", function () { sidebar.classList.toggle("open"); });
      sidebar.querySelectorAll("a").forEach(function (a) {
        a.addEventListener("click", function () { sidebar.classList.remove("open"); });
      });
    }
  }

  // ---- Toast notifications (from server flash messages) ----------------- //
  function initToasts() {
    var data = document.getElementById("flash-data");
    if (!data) return;
    var items = [];
    try { items = JSON.parse(data.textContent || "[]"); } catch (e) { return; }
    if (!items.length) return;
    var wrap = document.createElement("div");
    wrap.className = "toast-wrap";
    document.body.appendChild(wrap);
    items.forEach(function (it, idx) {
      setTimeout(function () {
        var el = document.createElement("div");
        el.className = "toast " + (it.cat || "success");
        el.innerHTML = "<span>" + (it.cat === "error" ? "⚠️" : "✅") + "</span><span>" +
          it.msg.replace(/</g, "&lt;") + "</span>";
        wrap.appendChild(el);
        requestAnimationFrame(function () { el.classList.add("show"); });
        setTimeout(function () {
          el.classList.remove("show");
          setTimeout(function () { el.remove(); }, 300);
        }, 4200);
      }, idx * 250);
    });
  }

  // ---- Animated stat counters ------------------------------------------- //
  function initCounters() {
    var els = document.querySelectorAll(".stat .v");
    els.forEach(function (el) {
      var raw = el.firstChild;
      if (!raw || raw.nodeType !== 3) return;       // text node only
      var txt = raw.textContent.trim();
      var m = txt.match(/^([0-9][0-9,]*\.?[0-9]*)$/);
      if (!m) return;
      var hasComma = txt.indexOf(",") !== -1;
      var decimals = (txt.split(".")[1] || "").length;
      var target = parseFloat(txt.replace(/,/g, ""));
      if (!isFinite(target) || target === 0) return;
      var start = null, dur = 700;
      function fmt(n) {
        var s = decimals ? n.toFixed(decimals) : String(Math.round(n));
        return hasComma ? Number(s).toLocaleString() : s;
      }
      function step(ts) {
        if (start === null) start = ts;
        var p = Math.min(1, (ts - start) / dur);
        raw.textContent = fmt(target * (0.2 + 0.8 * p * p));
        if (p < 1) requestAnimationFrame(step); else raw.textContent = fmt(target);
      }
      requestAnimationFrame(step);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    attachCsrf();
    initTheme();
    initMode();
    initSections();
    initNav();
    initToasts();
    initCounters();
  });
})();
