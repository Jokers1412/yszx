/* ============================================================
   云枢智学 原型 · 管理端公共框架（侧栏 / 顶栏 / 登录态）
   依赖 base.css / admin.css / ui.js / data.js
   页面约定：<body class="admin-body" data-page="dashboard|subjects|courses|questions|interview-questions|routes|students|users|roles|logs|settings">
   页架：<div class="admin-layout"><aside id="admin-sidebar"></aside><div class="admin-main"><header id="admin-topbar"></header><main class="admin-content">...</main></div></div>
   ============================================================ */
window.YAdmin = (function () {
  "use strict";

  /* ---------- 登录态 ---------- */
  var auth = {
    getUser: function () {
      try { return JSON.parse(localStorage.getItem("yszx_admin")); } catch (e) { return null; }
    },
    login: function (u) { localStorage.setItem("yszx_admin", JSON.stringify(u || DB.admin)); },
    logout: function () { localStorage.removeItem("yszx_admin"); },
    ensureDemo: function () {
      /* 原型首次打开自动登录演示管理员，退出后需从 admin/login 重新登录 */
      if (localStorage.getItem("yszx_admin") === null && localStorage.getItem("yszx_admin_out") !== "1") {
        this.login(DB.admin);
      }
    },
    requireLogin: function () {
      if (!this.getUser()) {
        location.href = "login.html";
        return false;
      }
      return true;
    }
  };

  /* ---------- 菜单（固定 4 组 11 项） ---------- */
  var MENU = [
    { title: "概览", items: [
      { key: "dashboard", icon: "📊", label: "数据看板", href: "dashboard.html" }
    ]},
    { title: "内容管理", items: [
      { key: "subjects", icon: "📚", label: "学科管理", href: "subjects.html" },
      { key: "courses", icon: "🎬", label: "B站课程库", href: "courses.html" },
      { key: "questions", icon: "📝", label: "题库管理", href: "questions.html" },
      { key: "interview-questions", icon: "💬", label: "面试题库管理", href: "interview-questions.html" },
      { key: "routes", icon: "🗺️", label: "学习路线", href: "routes.html" }
    ]},
    { title: "学员管理", items: [
      { key: "students", icon: "👥", label: "学员管理", href: "students.html" }
    ]},
    { title: "系统管理", items: [
      { key: "users", icon: "🔑", label: "用户管理", href: "users.html" },
      { key: "roles", icon: "🛡️", label: "角色管理", href: "roles.html" },
      { key: "logs", icon: "🧾", label: "操作日志", href: "logs.html" },
      { key: "settings", icon: "⚙️", label: "系统设置", href: "settings.html" }
    ]}
  ];
  var TITLES = {
    dashboard: "数据看板", subjects: "学科管理", courses: "B站课程库", questions: "题库管理",
    "interview-questions": "面试题库管理", routes: "学习路线管理", students: "学员管理",
    users: "用户管理", roles: "角色管理", logs: "操作日志", settings: "系统设置"
  };

  /* ---------- 侧栏 ---------- */
  function renderSidebar(page) {
    var host = document.getElementById("admin-sidebar");
    if (!host) return;
    var groups = MENU.map(function (g) {
      return '<div class="menu-group"><div class="menu-group-title">' + g.title + "</div>" +
        g.items.map(function (it) {
          return '<a class="menu-item' + (it.key === page ? " active" : "") + '" href="' + it.href + '" title="' + it.label + '">' +
            '<span class="mi-icon">' + it.icon + "</span><span>" + it.label + "</span></a>";
        }).join("") + "</div>";
    }).join("");
    host.innerHTML =
      '<a class="sidebar-logo" href="dashboard.html" style="text-decoration:none"><span class="logo-mark">云</span><span>云枢智学</span></a>' +
      groups;
  }

  /* ---------- 顶栏 ---------- */
  function renderTopbar(page) {
    var host = document.getElementById("admin-topbar");
    if (!host) return;
    var user = auth.getUser() || DB.admin;
    var unread = DB.notices.filter(function (n) { return n.unread; }).length;
    host.innerHTML =
      '<button class="collapse-btn" id="sidebar-collapse">☰</button>' +
      '<span class="page-title">' + (TITLES[page] || "管理后台") + "</span>" +
      '<div class="topbar-right">' +
      '  <div class="dropdown">' +
      '    <button class="bell-btn dropdown-trigger">🔔<span class="bell-badge">' + unread + "</span></button>" +
      '    <div class="dropdown-menu" style="width:280px">' +
             DB.notices.map(function (n) {
               return '<div class="notice-item' + (n.unread ? " unread" : "") + '"><div style="flex:1"><div style="font-size:13px;color:var(--ink)">' + UI.esc(n.text) + '</div><div class="muted" style="font-size:11px">' + UI.esc(n.time) + "</div></div></div>";
             }).join("") +
      '      <div class="dropdown-divider"></div>' +
      '      <button class="dropdown-item" id="read-all-btn">全部标为已读</button>' +
      "    </div></div>" +
      '  <div class="dropdown">' +
      '    <button class="admin-user-trigger dropdown-trigger"><span class="avatar sm">' + UI.esc((user.name || user.username || "管").slice(0, 1)) + "</span>" + UI.esc(user.name || user.username) + "⌄</button>" +
      '    <div class="dropdown-menu">' +
      '      <a class="dropdown-item" href="../portal/index.html">🌐 返回前台</a>' +
      '      <div class="dropdown-divider"></div>' +
      '      <button class="dropdown-item danger" id="admin-logout-btn">🚪 退出登录</button>' +
      "    </div></div>" +
      "</div>";
    document.getElementById("sidebar-collapse").addEventListener("click", function () {
      document.getElementById("admin-sidebar").classList.toggle("collapsed");
    });
    document.getElementById("admin-logout-btn").addEventListener("click", function () {
      UI.confirm({ title: "退出登录", text: "确定要退出管理后台吗？", okText: "退出", danger: true }).then(function (ok) {
        if (ok) {
          auth.logout();
          localStorage.setItem("yszx_admin_out", "1");
          location.href = "login.html";
        }
      });
    });
    var readAll = document.getElementById("read-all-btn");
    if (readAll) readAll.addEventListener("click", function () {
      DB.notices.forEach(function (n) { n.unread = false; });
      UI.toast("通知已全部标为已读");
      renderTopbar(page);
    });
  }

  /* ---------- 启动 ---------- */
  function init() {
    auth.ensureDemo();
    if (!auth.requireLogin()) return;
    var page = document.body.dataset.page || "dashboard";
    renderSidebar(page);
    renderTopbar(page);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  return { auth: auth, renderSidebar: renderSidebar, renderTopbar: renderTopbar, MENU: MENU, TITLES: TITLES };
})();
