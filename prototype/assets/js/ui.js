/* ============================================================
   云枢智学 原型 · UI 交互助手（Toast / 弹窗 / 倒计时 / 分页 / 图表提示）
   无依赖，全局 window.UI
   ============================================================ */
window.UI = (function () {
  "use strict";

  /* ---------- 基础 ---------- */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  /* ---------- Toast ---------- */
  function toast(msg, type, duration) {
    type = type || "success"; // success | warn | error
    var wrap = document.getElementById("toast-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "toast-wrap";
      document.body.appendChild(wrap);
    }
    var icon = { success: "✓", warn: "⚠", error: "✕" }[type] || "✓";
    var el = document.createElement("div");
    el.className = "toast toast-" + type;
    el.innerHTML = "<span>" + icon + "</span><span>" + esc(msg) + "</span>";
    wrap.appendChild(el);
    setTimeout(function () {
      el.style.opacity = "0";
      el.style.transform = "translateY(-8px)";
      el.style.transition = "all .25s ease";
      setTimeout(function () { el.remove(); }, 260);
    }, duration || 2600);
  }

  /* ---------- 弹窗 ---------- */
  function openModal(idOrEl) {
    var m = typeof idOrEl === "string" ? document.getElementById(idOrEl) : idOrEl;
    if (!m) return;
    m.hidden = false;
    document.body.classList.add("no-scroll");
  }
  function closeModal(idOrEl) {
    var m = typeof idOrEl === "string" ? document.getElementById(idOrEl) : idOrEl;
    if (!m) return;
    m.hidden = true;
    if (!document.querySelector(".modal-overlay:not([hidden])")) {
      document.body.classList.remove("no-scroll");
    }
  }
  // 统一关闭：[data-close] 按钮；点击遮罩关闭（data-static="true" 的弹窗除外）
  document.addEventListener("click", function (e) {
    var closeBtn = e.target.closest("[data-close]");
    if (closeBtn) {
      var ov = closeBtn.closest(".modal-overlay");
      if (ov) { closeModal(ov); if (ov.dataset.onclose) try { window[ov.dataset.onclose] && window[ov.dataset.onclose](); } catch (x) {} }
      return;
    }
    if (e.target.classList && e.target.classList.contains("modal-overlay") && e.target.dataset.static !== "true") {
      closeModal(e.target);
    }
  });
  // Esc 关闭最上层弹窗
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      var open = $$(".modal-overlay:not([hidden])");
      if (open.length && open[open.length - 1].dataset.static !== "true") closeModal(open[open.length - 1]);
    }
  });

  /* ---------- 确认弹窗（Promise） ---------- */
  var confirmSeq = 0;
  function confirmDialog(opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var id = "ui-confirm-" + (++confirmSeq);
      var wrap = document.createElement("div");
      wrap.className = "modal-overlay";
      wrap.id = id;
      wrap.innerHTML =
        '<div class="modal modal-sm">' +
        '  <div class="modal-header"><h3>' + esc(opts.title || "确认操作") + '</h3>' +
        '    <button class="modal-close" data-close>×</button></div>' +
        '  <div class="modal-body"><p class="mb-0 text-2">' + (opts.html || esc(opts.text || "")) + "</p></div>" +
        '  <div class="modal-footer">' +
        '    <button class="btn btn-ghost" data-close data-act="cancel">' + esc(opts.cancelText || "取消") + "</button>" +
        '    <button class="btn ' + (opts.danger ? "btn-danger" : "btn-primary") + '" data-act="ok">' + esc(opts.okText || "确定") + "</button>" +
        "  </div></div>";
      document.body.appendChild(wrap);
      openModal(wrap);
      wrap.addEventListener("click", function (e) {
        var act = e.target.closest("[data-act]");
        if (!act) return;
        var ok = act.dataset.act === "ok";
        closeModal(wrap);
        wrap.remove();
        resolve(ok);
      });
      wrap.querySelectorAll("[data-close]").forEach(function (b) {
        b.addEventListener("click", function () { wrap.remove(); resolve(false); });
      });
    });
  }

  /* ---------- 下拉（委托） ---------- */
  document.addEventListener("click", function (e) {
    var trig = e.target.closest(".dropdown-trigger, .user-trigger, .admin-user-trigger");
    $$(".dropdown.open").forEach(function (d) {
      if (!trig || !d.contains(trig)) d.classList.remove("open");
    });
    if (trig) {
      var dd = trig.closest(".dropdown");
      if (dd) dd.classList.toggle("open");
    }
  });

  /* ---------- 倒计时按钮 ---------- */
  function countdown(btn, seconds, opts) {
    opts = opts || {};
    var label = opts.label || "获取验证码";
    var left = seconds;
    btn.disabled = true;
    btn.textContent = left + "s 后重新获取";
    var timer = setInterval(function () {
      left -= 1;
      if (left <= 0) {
        clearInterval(timer);
        btn.disabled = false;
        btn.textContent = label;
        if (opts.onDone) opts.onDone();
      } else {
        btn.textContent = left + "s 后重新获取";
      }
    }, 1000);
    return timer;
  }

  /* ---------- 数字递增动画 ---------- */
  function animateNumber(el, target, opts) {
    opts = opts || {};
    var duration = opts.duration || 1400;
    var suffix = opts.suffix || "";
    var decimals = opts.decimals || 0;
    var start = null;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      var val = target * eased;
      el.textContent = (decimals ? val.toFixed(decimals) : Math.round(val).toLocaleString("en-US")) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /* ---------- 时间格式化 ---------- */
  function pad(n) { return n < 10 ? "0" + n : "" + n; }
  function fmtClock(sec) { // 时:分:秒
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return pad(h) + ":" + pad(m) + ":" + pad(s);
  }
  function fmtHumanDur(sec) { // 「12 分 30 秒」
    var m = Math.floor(sec / 60), s = sec % 60;
    return m > 0 ? m + " 分 " + (s ? s + " 秒" : "") : s + " 秒";
  }
  function fmtDate(d) {
    d = d instanceof Date ? d : new Date(d);
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  }
  function fmtDateTime(d) {
    d = d instanceof Date ? d : new Date(d);
    return fmtDate(d) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  /* ---------- 密码强度（文档口径：≥6 位 / 含大小写 / 含数字与特殊字符） ---------- */
  function strength(pwd) {
    var score = 0;
    if (pwd && pwd.length >= 6) score++;
    if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++;
    if (/\d/.test(pwd) && /[^a-zA-Z0-9]/.test(pwd)) score++;
    var labels = ["太短", "弱", "中", "强"];
    return { score: score, label: labels[score] };
  }
  function renderStrength(meterEl, textEl, pwd) {
    var r = strength(pwd);
    var segs = meterEl.querySelectorAll(".seg");
    segs.forEach(function (s, i) {
      s.className = "seg" + (pwd && i < r.score ? " on-" + r.score : "");
    });
    if (textEl) textEl.textContent = pwd ? "密码强度：" + r.label : "建议 6-20 位，含大小写字母、数字与特殊字符";
    return r;
  }

  /* ---------- 分页 ---------- */
  function pager(el, opts) {
    var total = opts.total || 0;
    var page = opts.page || 1;
    var pageSize = opts.pageSize || 10;
    var pages = Math.max(1, Math.ceil(total / pageSize));
    var onChange = opts.onChange || function () {};
    if (!el) return;
    var html = '<div class="pg-info">共 ' + total + " 条 · 第 " + page + "/" + pages + " 页</div>";
    html += '<button class="pg-btn" data-pg="' + (page - 1) + '"' + (page <= 1 ? " disabled" : "") + ">‹</button>";
    var list = [];
    for (var i = 1; i <= pages; i++) {
      if (pages > 7 && i > 2 && i < pages - 1 && Math.abs(i - page) > 1) {
        if (list[list.length - 1] !== "…") list.push("…");
        continue;
      }
      list.push(i);
    }
    list.forEach(function (i) {
      if (i === "…") { html += '<span class="muted">…</span>'; return; }
      html += '<button class="pg-btn' + (i === page ? " active" : "") + '" data-pg="' + i + '">' + i + "</button>";
    });
    html += '<button class="pg-btn" data-pg="' + (page + 1) + '"' + (page >= pages ? " disabled" : "") + ">›</button>";
    el.innerHTML = html;
    el.onclick = function (e) {
      var b = e.target.closest("[data-pg]");
      if (!b || b.disabled) return;
      onChange(parseInt(b.dataset.pg, 10));
    };
  }

  /* ---------- 图表悬浮提示（[data-tip] 委托） ---------- */
  var tipEl = null;
  function showTip(text, x, y) {
    if (!tipEl) {
      tipEl = document.createElement("div");
      tipEl.className = "chart-tip";
      document.body.appendChild(tipEl);
    }
    tipEl.innerHTML = text;
    tipEl.style.display = "block";
    var w = tipEl.offsetWidth, h = tipEl.offsetHeight;
    tipEl.style.left = Math.min(x + 12, window.innerWidth - w - 12) + "px";
    tipEl.style.top = Math.max(8, y - h - 10) + "px";
  }
  document.addEventListener("mousemove", function (e) {
    var t = e.target.closest("[data-tip]");
    if (t) showTip(t.dataset.tip, e.clientX, e.clientY);
    else if (tipEl) tipEl.style.display = "none";
  });

  /* ---------- 杂项 ---------- */
  function debounce(fn, ms) {
    var t = null;
    return function () {
      var args = arguments, self = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(self, args); }, ms || 300);
    };
  }
  function todayStr() { return fmtDate(new Date()); }

  return {
    esc: esc, $: $, $$: $$,
    toast: toast, openModal: openModal, closeModal: closeModal, confirm: confirmDialog,
    countdown: countdown, animateNumber: animateNumber,
    fmtClock: fmtClock, fmtHumanDur: fmtHumanDur, fmtDate: fmtDate, fmtDateTime: fmtDateTime,
    strength: strength, renderStrength: renderStrength,
    pager: pager, debounce: debounce, showTip: showTip, todayStr: todayStr
  };
})();
