/* ============================================================
   云枢智学 原型 · 学员端公共框架（导航 / 页脚 / 登录态）
   依赖 base.css / portal.css / ui.js / data.js
   页面约定：<body data-page="home|routes|questions|practice|wrongbook|profile|interview|...">
   页架：<header id="site-header"></header> ... <footer id="site-footer"></footer>
   ============================================================ */
window.YS = (function () {
  "use strict";

  /* ---------- 登录态（原型：localStorage 模拟） ---------- */
  var auth = {
    getUser: function () {
      try { return JSON.parse(localStorage.getItem("yszx_user")); } catch (e) { return null; }
    },
    login: function (user) {
      localStorage.setItem("yszx_user", JSON.stringify(user || DB.user));
    },
    logout: function () {
      localStorage.removeItem("yszx_user");
    },
    /* 首次打开原型自动登录演示账号，便于浏览；退出登录后可体验游客流程 */
    ensureDemo: function () {
      if (localStorage.getItem("yszx_user") === null && localStorage.getItem("yszx_logged_out") !== "1") {
        this.login(DB.user);
      }
    },
    isGuest: function () { return !this.getUser(); },
    markLoggedOut: function () { localStorage.setItem("yszx_logged_out", "1"); },
    /* 受限页面调用：游客跳登录页 */
    requireLogin: function () {
      if (this.isGuest()) {
        UI.toast("请先登录后再继续", "warn");
        setTimeout(function () { location.href = "login.html?redirect=" + encodeURIComponent(location.pathname.split("/").pop() + location.search); }, 600);
        return false;
      }
      return true;
    }
  };

  /* ---------- 顶栏 ---------- */
  var NAV = [
    { key: "home", label: "首页", href: "index.html" },
    { key: "routes", label: "学习路线", href: "routes.html" },
    { key: "questions", label: "题库", href: "questions.html" },
    { key: "interview", label: "AI面试", href: "interview-config.html" }
  ];
  var NAV_GROUP = { home: "home", routes: "routes", questions: "questions", practice: "questions", wrongbook: "questions", interview: "interview", "interview-config": "interview", "interview-run": "interview", "interview-report": "interview", "interview-records": "interview", profile: "", login: "", register: "", forgot: "" };

  function renderHeader() {
    var host = document.getElementById("site-header");
    if (!host) return;
    var page = document.body.dataset.page || "home";
    var active = NAV_GROUP[page] != null ? NAV_GROUP[page] : page;
    var user = auth.getUser();
    var navHtml = NAV.map(function (n) {
      return '<a href="' + n.href + '"' + (n.key === active ? ' class="active"' : "") + ">" + n.label + "</a>";
    }).join("");
    var rightHtml;
    if (user) {
      /* 后台账号登录学员端时显示「管理后台」入口 */
      var adminEntry = user.role === "超级管理员" || user.role === "内容审核" || user.role === "运营人员" || user.isAdminAccount
        ? '<a class="dropdown-item" href="../admin/dashboard.html">🖥️ 管理后台</a><div class="dropdown-divider"></div>' : "";
      rightHtml =
        '<div class="dropdown">' +
        '  <button class="user-trigger dropdown-trigger"><span class="avatar sm">' + UI.esc(user.name.slice(0, 1)) + '</span><span class="user-name">' + UI.esc(user.name) + "</span>⌄</button>" +
        '  <div class="dropdown-menu">' +
             adminEntry +
        '    <a class="dropdown-item" href="profile.html">👤 个人中心</a>' +
        '    <a class="dropdown-item" href="wrongbook.html">📕 我的错题</a>' +
        '    <a class="dropdown-item" href="interview-records.html">🎙️ 面试记录</a>' +
        '    <div class="dropdown-divider"></div>' +
        '    <button class="dropdown-item danger" id="logout-btn">🚪 退出登录</button>' +
        "  </div></div>";
    } else {
      rightHtml =
        '<a class="btn btn-ghost btn-sm" href="login.html">登录</a>' +
        '<a class="btn btn-primary btn-sm" href="register.html">免费注册</a>';
    }
    host.innerHTML =
      '<div class="container header-inner">' +
      '  <a class="logo" href="index.html"><span class="logo-mark">云</span>云枢智学</a>' +
      '  <nav class="main-nav">' + navHtml + "</nav>" +
      '  <div class="header-right">' + rightHtml + "</div>" +
      "</div>";
    var logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", function () {
        UI.confirm({ title: "退出登录", text: "确定要退出当前账号吗？", okText: "退出" }).then(function (ok) {
          if (ok) {
            auth.logout();
            auth.markLoggedOut();
            UI.toast("已退出登录");
            setTimeout(function () { location.href = "index.html"; }, 500);
          }
        });
      });
    }
  }

  /* ---------- 页脚 ---------- */
  function renderFooter() {
    var host = document.getElementById("site-footer");
    if (!host) return;
    host.innerHTML =
      '<div class="container footer-grid">' +
      '  <div class="footer-brand">' +
      '    <div class="logo"><span class="logo-mark">云</span>云枢智学</div>' +
      "    <p>AI 赋能的智能面试训练平台。海量题库 × AI 模拟面试 × 学习路线，助你高效备战技术面试。</p>" +
      "  </div>" +
      '  <div><h4>产品</h4><ul>' +
      '    <li><a href="routes.html">学习路线</a></li><li><a href="questions.html">题库</a></li><li><a href="interview-config.html">AI面试</a></li></ul></div>' +
      '  <div><h4>支持</h4><ul>' +
      '    <li><a href="javascript:void(0)" data-ph>帮助中心</a></li><li><a href="javascript:void(0)" data-ph>意见反馈</a></li><li><a href="javascript:void(0)" data-ph>联系我们</a></li></ul></div>' +
      '  <div><h4>关于</h4><ul>' +
      '    <li><a href="javascript:void(0)" data-ph>关于我们</a></li><li><a href="javascript:void(0)" data-ph>用户协议</a></li><li><a href="javascript:void(0)" data-ph>隐私政策</a></li></ul></div>' +
      "</div>" +
      '<div class="container footer-bottom">' +
      "  <span>© 2026 云枢智学 · 仅原型演示</span>" +
      '  <a class="footer-admin-entry" href="../admin/login.html">🖥️ 管理后台</a>' +
      "</div>";
    host.querySelectorAll("[data-ph]").forEach(function (a) {
      a.addEventListener("click", function () { UI.toast("该页面为占位链接，本期不开发", "warn"); });
    });
  }

  /* ---------- 启动 ---------- */
  function init() {
    auth.ensureDemo();
    renderHeader();
    renderFooter();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  return { auth: auth, renderHeader: renderHeader, renderFooter: renderFooter };
})();
