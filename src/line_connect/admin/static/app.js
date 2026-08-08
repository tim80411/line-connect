(function () {
  "use strict";

  // ============================================================
  // LINE Connect Dashboard — Application Logic
  // ============================================================

  // === GLOBALS ===
  var Locales = {
    "en_US": {
      "loading_connecting": "Connecting to LINE Connect...", "login_sub": "Admin Dashboard", "login_pw_ph": "Enter admin password", "btn_signin": "Sign In", "btn_cancel": "Cancel", "btn_confirm": "Confirm", "nav_dashboard": "Dashboard", "nav_conversations": "Conversations", "nav_analytics": "Analytics", "nav_settings": "Settings", "nav_dark_mode": "Dark Mode", "nav_signout": "Sign Out"
    },
    "th_TH": {
      "loading_connecting": "กำลังเชื่อมต่อ LINE Connect...", "login_sub": "ระบบจัดการหลังบ้าน", "login_pw_ph": "ใส่รหัสผ่านแอดมิน", "btn_signin": "เข้าสู่ระบบ", "btn_cancel": "ยกเลิก", "btn_confirm": "ยืนยัน", "nav_dashboard": "หน้าหลัก", "nav_conversations": "บทสนทนา", "nav_analytics": "สถิติ", "nav_settings": "ตั้งค่า", "nav_dark_mode": "โหมดมืด", "nav_signout": "ออกจากระบบ",
      "Dashboard": "หน้าหลัก", "Overview of your LINE Connect workspace": "ภาพรวมเวิร์กสเปซ LINE Connect ของคุณ",
      "Unique Users": "ผู้ใช้ที่ไม่ซ้ำ", "Messages In": "ข้อความเข้า", "Messages Out": "ข้อความออก", "Avg Response Time": "เวลาตอบกลับเฉลี่ย",
      "Message Activity": "กิจกรรมข้อความ", "Last 7 days": "7 วันที่ผ่านมา", "Recent Activity": "กิจกรรมล่าสุด",
      "Connected LINE Account": "บัญชี LINE ที่เชื่อมต่อ", "Webhook Status": "สถานะ Webhook", "Storage Usage": "การใช้งานพื้นที่",
      "Total Conversations": "บทสนทนาทั้งหมด", "Active Today": "ใช้งานวันนี้", "Messages Today": "ข้อความวันนี้", "Avg Response": "เวลาตอบกลับ",
      "Conversations": "บทสนทนา", "Search conversations...": "ค้นหาบทสนทนา...", "Search chats...": "ค้นหาแชท...",
      "All": "ทั้งหมด", "Direct": "ข้อความตรง", "Group": "กลุ่ม", "Starred": "ติดดาว", "User": "ผู้ใช้", "Room": "ห้อง",
      "Select a Conversation": "เลือกบทสนทนา", "No conversations": "ไม่มีบทสนทนา", "No messages yet": "ยังไม่มีข้อความ",
      "Analytics": "สถิติ", "Performance metrics and usage statistics": "ตัวชี้วัดประสิทธิภาพและสถิติ",
      "Total Queries": "คำถามทั้งหมด", "Avg Success Rate": "อัตราสำเร็จเฉลี่ย", "Response Time": "เวลาตอบกลับ", "Failed Messages": "ข้อความล้มเหลว",
      "Interaction Volume": "ปริมาณโต้ตอบ", "Response Times": "เวลาตอบกลับ",
      "Settings": "ตั้งค่า", "Manage application preferences and LINE integrations": "จัดการการตั้งค่าและเชื่อมต่อ LINE",
      "Messages & Tags": "ข้อความและแท็ก", "System": "ระบบ",
      "Quick Reply Templates": "เทมเพลตตอบกลับ", "Template name": "ชื่อเทมเพลต", "Template content...": "เนื้อหา...", "Add Template": "เพิ่มเทมเพลต",
      "Tag Management": "จัดการแท็ก", "New tag name": "ชื่อแท็กใหม่", "Add": "เพิ่ม",
      "Default Auto-Reply": "ตอบอัตโนมัติเริ่มต้น", "This message is sent when the bot is active and no matching Quick Replies or Webhooks handle the message.": "ส่งเมื่อบอททำงาน",
      "Webhook Configuration": "ตั้งค่า Webhook", "Forward incoming messages to Dify to handle LLM responses. Requires a properly configured Dify Chatflow.": "ใช้โมเดล Dify ตอบ",
      "Save Webhook": "บันทึก Webhook", "Test Connection": "ทดสอบเชื่อมต่อ",
      "LINE Channel Credentials": "LINE ข้อมูล",
      "Storage Info": "ข้อมูลพื้นที่", "Appearance": "รูปแบบ", "Switch between light and dark themes": "ธีม",
      "Switched to light mode": "เปลี่ยนเป็นธีมสว่าง", "Switched to dark mode": "เปลี่ยนเป็นธีมมืด",
      "Refreshed": "รีเฟรชแล้ว", "Connection error": "ผิดพลาด", "Failed to update": "อัปเดตล้มเหลว",
      "History cleared": "ล้างแล้ว", "Failed to clear": "ล้างส้มเหลว", "Failed to save notes": "ล้มเหลว",
      "Failed to remove tag": "ลบแท็กล้มเหลว", "Tag added": "เพิ่มแท็กแล้ว", "Failed to add tag": "เพิ่มแท็กล้มเหลว",
      "Chat exported as CSV": "ส่งออกแล้ว",
      "No data to export": "ไม่มีข้อมูล", "Analytics exported": "ส่งออกแล้ว",
      "Please fill in title and body": "กรุณากรอกข้อมูล", "Template added": "เพิ่มเทมเพลตแล้ว",
      "Failed to add template": "ล้มเหลว",
      "Theme updated": "เปลี่ยนธีมแล้ว", "Template deleted": "ลบเทมเพลตแล้ว", "Failed to delete": "ลบข้อมูลล้มเหลว", "Tag removed": "ลบแท็กแล้ว"
    },
    "ja_JP": {
      "loading_connecting": "LINE Connectに接続中...", "login_sub": "管理ダッシュボード", "login_pw_ph": "パスワードを入力", "btn_signin": "サインイン", "btn_cancel": "キャンセル", "btn_confirm": "確認", "nav_dashboard": "ダッシュボード", "nav_conversations": "会話", "nav_analytics": "分析", "nav_settings": "設定", "nav_dark_mode": "ダークモード", "nav_signout": "サインアウト",
      "Dashboard": "ダッシュボード", "Overview of your LINE Connect workspace": "LINE Connectの概要",
      "Conversations": "チャット", "Analytics": "サマリー", "Settings": "設定", "System": "システム", "Messages & Tags": "メッセ＆タグ",
      "Unique Users": "ユーザー", "Messages In": "受信", "Messages Out": "送信", "Avg Response Time": "平均応答",
      "Connected LINE Account": "LINEアカウント", "Webhook Status": "Webhookの状況", "Storage Usage": "ストレージ",
      "All": "すべて", "Direct": "ユーザー", "Group": "グループ", "Room": "ルーム"
    },
    "zh_Hans": {
      "loading_connecting": "正在连接到 LINE Connect...", "login_sub": "管理后台", "login_pw_ph": "输入管理员密码", "btn_signin": "登录", "btn_cancel": "取消", "btn_confirm": "确认", "nav_dashboard": "仪表盘", "nav_conversations": "对话", "nav_analytics": "数据分析", "nav_settings": "设置", "nav_dark_mode": "深色模式", "nav_signout": "退出登录",
      "Dashboard": "仪表盘", "Overview of your LINE Connect workspace": "LINE Connect 工作区",
      "Unique Users": "用户数", "Messages In": "消息收", "Messages Out": "消息发", "Avg Response Time": "平均响应",
      "Connected LINE Account": "LINE 账号", "Webhook Status": "Webhook 状态", "Storage Usage": "存储使用",
      "Conversations": "对话", "Search chats...": "搜索...", "All": "所有", "Direct": "私聊", "Group": "群", "Room": "房间", "Settings": "设置", "Analytics": "数据", "System": "系统"
    },
    "zh_Hant": {
      "loading_connecting": "正在連接到 LINE Connect...", "login_sub": "管理後台", "login_pw_ph": "輸入管理員密碼", "btn_signin": "登入", "btn_cancel": "取消", "btn_confirm": "確認", "nav_dashboard": "儀表板", "nav_conversations": "對話", "nav_analytics": "數據", "nav_settings": "設定", "nav_dark_mode": "深色", "nav_signout": "登出",
      "Dashboard": "儀表板", "Overview of your LINE Connect workspace": "LINE Connect 工作區",
      "Settings": "設定"
    }
  };
  var currentLang = localStorage.getItem("lc_lang") || "en_US";
  function t(key) {
    if (Locales[currentLang] && Locales[currentLang][key]) return Locales[currentLang][key];
    if (Locales["en_US"][key]) return Locales["en_US"][key];
    return key;
  }
  function updateStaticI18n() {
    document.querySelectorAll("[data-i18n]").forEach(function(el) {
      if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
        el.placeholder = t(el.getAttribute("data-i18n"));
      } else {
        el.textContent = t(el.getAttribute("data-i18n"));
      }
    });
    document.querySelectorAll("[data-i18n-title]").forEach(function(el) {
      el.title = t(el.getAttribute("data-i18n-title"));
    });
    var labelMap = { "en_US":"EN", "zh_Hans":"简", "zh_Hant":"繁", "ja_JP":"JA", "th_TH":"TH" };
    var labelEl = document.getElementById("cur-lang-label");
    if (labelEl) labelEl.textContent = labelMap[currentLang] || "EN";
  }
  updateStaticI18n();

  var API = location.href.split("?")[0].split("#")[0].replace(/\/$/, "");
  var authToken = sessionStorage.getItem("lc_token") || "";
  var chats = [];
  var activeChat = null;
  var allMsgs = [];
  var shownMsgs = 0;
  var loadingMore = false;
  var forceScroll = false;
  var lastMsgSig = "";
  var PAGE_SIZE = 20;
  var isBotTyping = false;

  // Polling intervals
  var listPoll = null;
  var histPoll = null;
  var statsPoll = null;

  // Chart instances (destroy before recreate)
  var chartActivity = null;
  var chartVolume = null;
  var chartResponseTime = null;
  var chartUserGrowth = null;
  var chartRtTrend = null;

  // State
  var currentPage = "dashboard";
  var currentFilter = "all";
  var analyticsRange = "7d";
  var allTags = [];
  var allTemplates = [];

  // ============================================================
  // UTILITIES
  // ============================================================

  /** HTML-escape to prevent XSS */
  function esc(s) {
    if (!s) return "";
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** Relative time display */
  function relTime(iso) {
    if (!iso) return "";
    var d = (Date.now() - new Date(iso).getTime()) / 1000;
    if (d < 60) return "just now";
    if (d < 3600) return Math.floor(d / 60) + "m ago";
    if (d < 86400) return Math.floor(d / 3600) + "h ago";
    if (d < 604800) return Math.floor(d / 86400) + "d ago";
    return new Date(iso).toLocaleDateString("en-US", {
      day: "numeric",
      month: "short",
    });
  }

  /** Formatted timestamp */
  function fmtTime(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      day: "numeric",
      month: "short",
    });
  }

  /** Avatar color from name */
  var COLORS = [
    "#3B82F6", "#8B5CF6", "#EC4899", "#F43F5E", "#F97316",
    "#EAB308", "#10B981", "#14B8A6", "#06B6D4", "#6366F1",
  ];
  function avColor(name) {
    var h = 0;
    for (var i = 0; i < name.length; i++)
      h = ((h << 5) - h + name.charCodeAt(i)) | 0;
    return COLORS[Math.abs(h) % COLORS.length];
  }

  /** Avatar character */
  function avChar(chat) {
    if (chat.type === "group") return "G";
    if (chat.type === "room") return "R";
    var c = chat.name ? chat.name.trim().charAt(0).toUpperCase() : "";
    // Denylist, not a whitelist: this lands both as raw HTML text and inside
    // the single-quoted JS string of an inline onerror handler, so these are
    // the characters that could break out. Everything else — including CJK —
    // keeps a real initial.
    if (!c || /['"\\<>&\r\n]/.test(c)) return "?";
    return c;
  }

  /** Type label */
  function typeLabel(t) {
    return { user: "Direct", group: "Group", room: "Room" }[t] || t;
  }

  /** Toast notification */
  function toast(msg) {
    var el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(el._timer);
    el._timer = setTimeout(function () {
      el.classList.remove("show");
    }, 3000);
  }

  /** Confirmation modal */
  function modal(title, body, onConfirm) {
    var overlay = document.getElementById("modal");
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-body").innerHTML = body;
    overlay.style.display = "flex";

    var confirmBtn = document.getElementById("modal-confirm");
    var cancelBtn = document.getElementById("modal-cancel");
    var closeBtn = document.getElementById("modal-close");

    function close() {
      overlay.style.display = "none";
      confirmBtn.onclick = null;
      cancelBtn.onclick = null;
      closeBtn.onclick = null;
    }

    confirmBtn.onclick = function () {
      close();
      if (onConfirm) onConfirm();
    };
    cancelBtn.onclick = close;
    closeBtn.onclick = close;
  }

  /** Skeleton loading placeholder */
  function skeleton(container, type) {
    var html = "";
    if (type === "cards") {
      for (var i = 0; i < 4; i++) {
        html +=
          '<div class="skeleton skeleton-card" style="height:130px"></div>';
      }
    } else if (type === "chat-list") {
      for (var j = 0; j < 6; j++) {
        html +=
          '<div class="skeleton-chat">' +
          '<div class="skeleton skeleton-circle"></div>' +
          '<div class="skeleton-chat-lines">' +
          '<div class="skeleton skeleton-text medium"></div>' +
          '<div class="skeleton skeleton-text short"></div>' +
          "</div></div>";
      }
    } else if (type === "chart") {
      html = '<div class="skeleton" style="height:280px;border-radius:12px"></div>';
    } else {
      html =
        '<div class="skeleton skeleton-text"></div>' +
        '<div class="skeleton skeleton-text medium"></div>' +
        '<div class="skeleton skeleton-text short"></div>';
    }
    if (typeof container === "string") {
      container = document.getElementById(container);
    }
    if (container) container.innerHTML = html;
  }

  /** Mini SVG sparkline */
  function sparkline(container, data, color) {
    if (!data || !data.length) return;
    color = color || "#06C755";
    if (typeof container === "string") {
      container = document.getElementById(container);
    }
    if (!container) return;
    // Skip if data unchanged
    var sig = data.join(",");
    if (container._lastSig === sig) return;
    container._lastSig = sig;
    var w = 120,
      h = 40;
    var max = Math.max.apply(null, data) || 1;
    var min = Math.min.apply(null, data);
    var range = max - min || 1;
    var step = w / (data.length - 1 || 1);

    var points = data.map(function (v, i) {
      var x = i * step;
      var y = h - ((v - min) / range) * (h - 4) - 2;
      return x.toFixed(1) + "," + y.toFixed(1);
    });

    var polyline = points.join(" ");
    // area fill
    var area =
      "0," + h + " " + polyline + " " + (w).toFixed(1) + "," + h;

    var svg =
      '<svg viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none" style="width:100%;height:100%">' +
      '<defs><linearGradient id="sparkGrad-' + color.replace("#", "") + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="' + color + '" stop-opacity="0.3"/>' +
      '<stop offset="100%" stop-color="' + color + '" stop-opacity="0.02"/>' +
      "</linearGradient></defs>" +
      '<polygon points="' + area + '" fill="url(#sparkGrad-' + color.replace("#", "") + ')"/>' +
      '<polyline points="' + polyline + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>' +
      "</svg>";

    container.innerHTML = svg;
  }

  /** Animate counting up (skips animation if value unchanged) */
  function countUp(el, target, duration, suffix) {
    suffix = suffix || "";
    duration = duration || 800;
    target = parseFloat(target) || 0;
    var display = target.toLocaleString() + suffix;

    // Skip if value hasn't changed
    if (el._lastValue === target) return;
    var start = el._lastValue || 0;
    el._lastValue = target;

    // First load or big jump: just set directly
    if (start === 0 && target === 0) { el.textContent = display; return; }

    var startTime = null;
    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min((timestamp - startTime) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var current = Math.round(start + (target - start) * eased);
      el.textContent = current.toLocaleString() + suffix;
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /** Navigate to page */
  function navigate(page) {
    location.hash = "#" + page;
  }

  /** Download helper */
  function downloadFile(content, filename, mime) {
    var blob = new Blob([content], { type: mime || "text/plain" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ============================================================
  // API MODULE
  // ============================================================

  function api(action, params) {
    var body = Object.assign({ token: authToken, action: action }, params || {});
    return fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) {
      // Handle image binary responses
      if (action === "get_image") {
        if (!r.ok) throw new Error("Image fetch failed");
        return r.blob();
      }
      return r.json().then(function (d) {
        if (r.status === 401) {
          showLogin();
          throw new Error("unauthorized");
        }
        if (d.error && d.error !== "unauthorized") throw new Error(d.error);
        return d;
      });
    });
  }

  // ============================================================
  // AUTH
  // ============================================================

  function hideLoading() {
    var el = document.getElementById("loading");
    if (el) el.style.display = "none";
  }

  function showLogin() {
    hideLoading();
    document.getElementById("login").style.display = "flex";
    document.getElementById("app").classList.remove("show");
    stopAllPolling();
    fetchLoginBotInfo();
  }

  /** Fetch bot info (no auth) and update login screen with OA logo + name */
  function fetchLoginBotInfo() {
    fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "get_bot_info" }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.error) return;
        var logoEl = document.getElementById("login-logo");
        var titleEl = document.getElementById("login-title");
        var subEl = document.getElementById("login-sub");
        if (d.pictureUrl && logoEl) {
          logoEl.innerHTML = '<img src="' + esc(d.pictureUrl) + '" alt="' + esc(d.displayName || "Bot") + '">';
          logoEl.style.background = "none";
        }
        if (d.displayName && titleEl) {
          titleEl.textContent = d.displayName;
        }
        if (subEl) {
          subEl.textContent = "LINE Connect Admin";
        }
      })
      .catch(function () {});
  }

  function hideLogin() {
    hideLoading();
    document.getElementById("login").style.display = "none";
    document.getElementById("app").classList.add("show");
  }

  function doLogin() {
    var pw = document.getElementById("pw").value;
    if (!pw) return;
    var errEl = document.getElementById("login-err");
    errEl.style.display = "none";

    // Exchange password for token
    fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "login", password: pw }),
    })
      .then(function (r) { return r.json().then(function(d) { d._status = r.status; return d; }); })
      .then(function (d) {
        if (d._status === 429) throw new Error("too_many_attempts");
        if (d.error) throw new Error(d.error);
        authToken = d.token;
        sessionStorage.setItem("lc_token", authToken);
        // Now fetch chats with the token
        return api("list_chats");
      })
      .then(function (d) {
        chats = d.chats || [];
        hideLogin();
        initApp();
      })
      .catch(function (e) {
        if (e.message === "too_many_attempts") {
          errEl.textContent = "Too many failed attempts. Please wait 5 minutes.";
        } else {
          errEl.textContent = "Incorrect password. Please try again.";
        }
        errEl.style.display = "block";
      });
  }

  function doLogout() {
    sessionStorage.removeItem("lc_token");
    authToken = "";
    stopAllPolling();
    showLogin();
  }

  // Login event listeners
  document
    .getElementById("btn-login")
    .addEventListener("click", doLogin);
  document
    .getElementById("pw")
    .addEventListener("keydown", function (e) {
      if (e.key === "Enter") doLogin();
    });
  document
    .getElementById("btn-logout")
    .addEventListener("click", doLogout);

  // ============================================================
  // THEME
  // ============================================================

  function getTheme() {
    return localStorage.getItem("lc_theme") || "light";
  }

  function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("lc_theme", theme);
    // Update icons
    try { lucide.createIcons(); } catch (e) {}
  }

  function toggleTheme() {
    var next = getTheme() === "dark" ? "light" : "dark";
    setTheme(next);
    toast(t("Switched to " + next + " mode"));
  }

  // Theme listeners
  document
    .getElementById("btn-theme")
    .addEventListener("click", toggleTheme);
  document
    .getElementById("btn-theme-mobile")
    .addEventListener("click", toggleTheme);

  // Language switcher listeners
  document.getElementById("btn-lang").addEventListener("click", function(e) {
    e.stopPropagation();
    document.getElementById("lang-menu").classList.toggle("show");
  });
  document.addEventListener("click", function(e) {
    if (!e.target.closest(".lang-dropdown")) {
      var dropdown = document.getElementById("lang-menu");
      if (dropdown && dropdown.classList.contains("show")) {
        dropdown.classList.remove("show");
      }
    }
  });
  document.querySelectorAll(".lang-option").forEach(function(btn) {
    btn.addEventListener("click", function(e) {
      e.preventDefault();
      document.getElementById("lang-menu").classList.remove("show");
      var lang = this.getAttribute("data-lang");
      if (lang && Locales[lang]) {
        currentLang = lang;
        localStorage.setItem("lc_lang", lang);
        updateStaticI18n();
        document.querySelectorAll(".lang-option").forEach(function(el) {
          el.classList.toggle("active", el.getAttribute("data-lang") === lang);
        });
        renderPage(currentPage);
      }
    });
  });
  
  // Init lang option active state
  document.querySelectorAll(".lang-option").forEach(function(el) {
    el.classList.toggle("active", el.getAttribute("data-lang") === currentLang);
  });

  // Apply saved theme
  setTheme(getTheme());

  // ============================================================
  // SIDEBAR & MOBILE NAVIGATION
  // ============================================================

  var sidebarEl = document.getElementById("sidebar");
  var overlayEl = document.getElementById("sidebar-overlay");

  function openSidebar() {
    sidebarEl.classList.add("open");
    overlayEl.classList.add("show");
  }

  function closeSidebar() {
    sidebarEl.classList.remove("open");
    overlayEl.classList.remove("show");
  }

  document
    .getElementById("btn-menu")
    .addEventListener("click", openSidebar);
  overlayEl.addEventListener("click", closeSidebar);

  // Nav item clicks
  document.querySelectorAll(".nav-item").forEach(function (item) {
    item.addEventListener("click", function (e) {
      e.preventDefault();
      var page = this.getAttribute("data-page");
      navigate(page);
      closeSidebar();
    });
  });

  // ============================================================
  // ROUTER
  // ============================================================

  function getHash() {
    return (location.hash || "#dashboard").replace("#", "");
  }

  function handleRoute() {
    var page = getHash();
    if (
      !["dashboard", "inbox", "analytics", "settings"].includes(page)
    ) {
      page = "dashboard";
    }
    currentPage = page;

    // Update nav active state
    document.querySelectorAll(".nav-item").forEach(function (item) {
      item.classList.toggle(
        "active",
        item.getAttribute("data-page") === page
      );
    });

    // Render page
    renderPage(page);
  }

  window.addEventListener("hashchange", handleRoute);

  function renderPage(page) {
    var content = document.getElementById("main-content");
    stopHistPoll();
    activeChat = null;

    // Destroy chart instances before DOM wipe
    if (chartActivity) { chartActivity.destroy(); chartActivity = null; }
    if (chartVolume) { chartVolume.destroy(); chartVolume = null; }
    if (chartResponseTime) { chartResponseTime.destroy(); chartResponseTime = null; }
    if (chartUserGrowth) { chartUserGrowth.destroy(); chartUserGrowth = null; }
    if (chartRtTrend) { chartRtTrend.destroy(); chartRtTrend = null; }

    switch (page) {
      case "dashboard":
        renderDashboard(content);
        break;
      case "inbox":
        renderInbox(content);
        break;
      case "analytics":
        renderAnalytics(content);
        break;
      case "settings":
        renderSettings(content);
        break;
    }

    // Re-init lucide icons
    try { lucide.createIcons(); } catch (e) {}
  }

  // ============================================================
  // POLLING
  // ============================================================

  function startListPoll() {
    stopListPoll();
    listPoll = setInterval(function () {
      if (document.hidden) return;
      api("list_chats")
        .then(function (d) {
          chats = d.chats || [];
          // Update inbox badge to compute c._unread first
          updateInboxBadge();
          // Update inbox list if on inbox page
          if (currentPage === "inbox") {
            renderChatList();
          }
        })
        .catch(function () {});
    }, 5000);
  }

  function stopListPoll() {
    if (listPoll) { clearInterval(listPoll); listPoll = null; }
  }

  function startHistPoll() {
    stopHistPoll();
    if (!activeChat) return;
    lastMsgSig = "";
    fetchHistory();
    histPoll = setInterval(function () {
      if (document.hidden || !activeChat) return;
      fetchHistory();
    }, 3000);
  }

  function stopHistPoll() {
    if (histPoll) { clearInterval(histPoll); histPoll = null; }
  }

  function startStatsPoll() {
    stopStatsPoll();
    statsPoll = setInterval(function () {
      if (document.hidden || currentPage !== "dashboard") return;
      loadDashboardData();
    }, 10000);
  }

  function stopStatsPoll() {
    if (statsPoll) { clearInterval(statsPoll); statsPoll = null; }
  }

  function stopAllPolling() {
    stopListPoll();
    stopHistPoll();
    stopStatsPoll();
  }

  function updateInboxBadge() {
    var badge = document.getElementById("nav-badge-inbox");
    if (!badge) return;
    var now = Date.now();
    var count = 0;
    chats.forEach(function(c) {
      c._unread = false;
      c._unreadCount = 0;
      if (c.disabled || !c.last_active) return;
      if (activeChat && activeChat.id === c.id) {
        localStorage.setItem("lc_read_" + c.id, c.last_active);
        localStorage.setItem("lc_readmc_" + c.id, String(c.mc || 0));
        return;
      }
      var readStr = localStorage.getItem("lc_read_" + c.id);
      if (readStr && readStr >= c.last_active) return;
      var age = (now - new Date(c.last_active).getTime()) / 1000;
      if (!readStr && age > 86400) return;
      c._unread = true;
      // Estimate unread count from message count diff
      var mcStr = localStorage.getItem("lc_readmc_" + c.id);
      if (mcStr !== null) {
        c._unreadCount = Math.max(0, (c.mc || 0) - parseInt(mcStr, 10));
        if (c._unreadCount === 0) c._unreadCount = 1;
      } else {
        c._unreadCount = 0;
      }
      count++;
    });
    if (count > 0) {
      badge.textContent = count > 99 ? "99+" : count;
      badge.style.display = "";
      document.title = "(" + count + ") LINE Connect Dashboard";
    } else {
      badge.style.display = "none";
      document.title = "LINE Connect Dashboard";
    }
  }

  // ============================================================
  // BOT INFO
  // ============================================================

  var _botInfo = null;

  function loadBotInfo() {
    api("get_bot_info")
      .then(function (d) {
        if (d.error) return;
        _botInfo = d;
        renderBotBadge();
      })
      .catch(function () {});
  }

  function renderBotBadge() {
    if (!_botInfo) return;

    // Sidebar brand — add bot name
    var brandText = document.querySelector(".sidebar-brand-text");
    if (brandText && _botInfo.displayName) {
      brandText.innerHTML = "LINE Connect" +
        '<span class="sidebar-bot-name">' + esc(_botInfo.displayName) + "</span>";
    }

    // Sidebar logo — use bot picture
    if (_botInfo.pictureUrl) {
      // Update favicon dynamically with a green ring using Canvas
      var imgForFavicon = new Image();
      imgForFavicon.crossOrigin = "Anonymous";
      imgForFavicon.onload = function() {
        var canvas = document.createElement('canvas');
        canvas.width = 64; canvas.height = 64;
        var ctx = canvas.getContext('2d');
        
        // Green ring (outer)
        ctx.beginPath(); ctx.arc(32, 32, 32, 0, Math.PI*2);
        ctx.fillStyle = "#06C755"; ctx.fill(); // var(--brand)
        
        // White gap
        ctx.beginPath(); ctx.arc(32, 32, 28, 0, Math.PI*2);
        ctx.fillStyle = "#FFFFFF"; ctx.fill();
        
        // Profile image
        ctx.save();
        ctx.beginPath(); ctx.arc(32, 32, 26, 0, Math.PI*2);
        ctx.clip();
        ctx.drawImage(imgForFavicon, 6, 6, 52, 52);
        ctx.restore();
        
        var link = document.querySelector("link[rel~='icon']");
        if (!link) {
            link = document.createElement('link');
            link.rel = 'icon';
            document.head.appendChild(link);
        }
        link.href = canvas.toDataURL("image/png");
      };
      // For cross-origin canvas taint bypass if image is external, though LINE pictures usually allow it
      // or we can fall back if it fails.
      imgForFavicon.onerror = function() {
        var link = document.querySelector("link[rel~='icon']");
        if (!link) {
            link = document.createElement('link');
            link.rel = 'icon';
            document.head.appendChild(link);
        }
        link.href = _botInfo.pictureUrl;
      };
      imgForFavicon.src = _botInfo.pictureUrl;

      var logos = document.querySelectorAll(".sidebar-logo, .topbar-logo");
      logos.forEach(function (el) {
        el.style.background = "transparent";
        el.style.overflow = "visible";
        el.innerHTML = '<img src="' + esc(_botInfo.pictureUrl) + '" style="width:100%;height:100%;border-radius:50%;object-fit:cover;border:2px solid var(--brand);box-shadow:0 0 0 3px var(--brand-subtle);box-sizing:border-box;">';
      });
    }

    // Dashboard bot info card
    var el = document.getElementById("bot-info-card");
    if (el) renderBotInfoCard(el);
  }

  function renderBotInfoCard(el) {
    if (!_botInfo || !el) return;
    var pic = _botInfo.pictureUrl
      ? '<img src="' + esc(_botInfo.pictureUrl) + '" class="bot-info-pic">'
      : '<div class="bot-info-pic-placeholder"><i data-lucide="bot"></i></div>';

    el.innerHTML =
      '<div class="bot-info-row">' +
      pic +
      '<div class="bot-info-detail">' +
      '<div class="bot-info-name">' + esc(_botInfo.displayName || "Unknown") + "</div>" +
      (_botInfo.basicId ? '<div class="bot-info-id">@' + esc(_botInfo.basicId) + "</div>" : "") +
      (_botInfo.premiumId ? '<div class="bot-info-id">Premium: @' + esc(_botInfo.premiumId) + "</div>" : "") +
      '<div class="bot-info-status"><span class="status-dot online"></span> Connected</div>' +
      "</div></div>";
    try { lucide.createIcons(); } catch (e) {}
  }

  // ============================================================
  // APP INIT
  // ============================================================

  function initApp() {
    loadBotInfo();
    handleRoute();
    startListPoll();
    startStatsPoll();
    updateInboxBadge();
  }

  // ============================================================
  // PAGE: DASHBOARD
  // ============================================================

  function renderDashboard(container) {
    container.innerHTML =
      '<div class="page" id="page-dashboard">' +
      '<div class="page-header">' +
      "<h1>" + t("Dashboard") + "</h1>" +
      "<p>" + t("Overview of your LINE Connect workspace") + "</p>" +
      "</div>" +
      // KPI cards
      '<div class="kpi-grid" id="kpi-grid">' +
      kpiCardHtml(t("Total Conversations"), "--", "message-square", "green", "kpi-total") +
      kpiCardHtml(t("Active Today"), "--", "users", "blue", "kpi-active") +
      kpiCardHtml(t("Messages Today"), "--", "mail", "amber", "kpi-messages") +
      kpiCardHtml(t("Avg Response"), "--", "clock", "purple", "kpi-response") +
      "</div>" +
      // Charts
      '<div class="chart-grid">' +
      '<div class="chart-card">' +
      '<div class="chart-card-title">' + t("Message Activity") + ' <span>' + t("Last 7 days") + '</span></div>' +
      '<div class="chart-wrap"><canvas id="chart-activity"></canvas></div>' +
      "</div>" +
      '<div class="dashboard-panel">' +
      '<div class="panel-header"><h2>' + t("Recent Activity") + '</h2></div>' +
      '<div id="recent-chats" class="recent-list"></div>' +
      "</div>" +
      "</div>" +
      // Status
      '<div class="status-grid" id="status-grid">' +
      '<div class="status-card">' +
      '<div class="chart-card-title">' + t("Connected LINE Account") + '</div>' +
      '<div id="bot-info-card"></div>' +
      "</div>" +
      '<div class="status-card">' +
      '<div class="chart-card-title">' + t("Webhook Status") + '</div>' +
      '<div id="webhook-status"></div>' +
      "</div>" +
      '<div class="status-card">' +
      '<div class="chart-card-title">' + t("Storage Usage") + '</div>' +
      '<div id="storage-status"></div>' +
      "</div>" +
      "</div>" +
      "</div>";

    loadDashboardData();
  }

  function kpiCardHtml(label, value, icon, color, id) {
    return (
      '<div class="kpi-card">' +
      '<div class="kpi-card-header">' +
      '<span class="kpi-card-label">' + esc(label) + "</span>" +
      '<div class="kpi-card-icon ' + color + '"><i data-lucide="' + icon + '"></i></div>' +
      "</div>" +
      '<div class="kpi-card-value" id="' + id + '">' + value + "</div>" +
      '<div class="kpi-sparkline" id="' + id + '-spark"></div>' +
      "</div>"
    );
  }

  function loadDashboardData() {
    // Fetch realtime stats
    api("get_analytics_realtime")
      .then(function (d) {
        var today = d.today || {};
        var allTime = d.all_time || {};

        // Animate KPI numbers
        var totalEl = document.getElementById("kpi-total");
        var activeEl = document.getElementById("kpi-active");
        var msgEl = document.getElementById("kpi-messages");
        var respEl = document.getElementById("kpi-response");

        if (totalEl) countUp(totalEl, allTime.total_users || chats.length, 800);
        if (activeEl) countUp(activeEl, today.unique_users || 0, 800);
        if (msgEl) countUp(msgEl, (today.messages_in || 0) + (today.messages_out || 0), 800);
        if (respEl) {
          var avgResp = today.avg_response_time || 0;
          var respText = avgResp < 1 ? (avgResp * 1000).toFixed(0) + "ms" : avgResp.toFixed(1) + "s";
          if (respEl.textContent !== respText) respEl.textContent = respText;
        }

        // Sparklines from hourly data
        if (today.hourly && today.hourly.length) {
          var hourlyIn = today.hourly.map(function (h) { return h.messages_in || 0; });
          sparkline("kpi-messages-spark", hourlyIn, "#F59E0B");
          var hourlyOut = today.hourly.map(function (h) { return h.messages_out || 0; });
          sparkline("kpi-active-spark", hourlyOut, "#3B82F6");
        }
      })
      .catch(function () {});

    // Fetch 7-day analytics for chart
    api("get_analytics", { days: 7 })
      .then(function (d) {
        renderActivityChart(d.daily || []);

        // Generate sparklines from daily data
        if (d.daily && d.daily.length) {
          var dailyTotal = d.daily.map(function (day) {
            return (day.messages_in || 0) + (day.messages_out || 0);
          });
          sparkline("kpi-total-spark", dailyTotal, "#06C755");
          var dailyUsers = d.daily.map(function (day) { return day.unique_users || 0; });
          sparkline("kpi-response-spark", dailyUsers, "#8B5CF6");
        }
      })
      .catch(function () {});

    // Recent chats
    renderRecentChats();

    // Storage & Webhook status
    api("get_storage_info")
      .then(function (d) {
        renderStorageStatus(d);
      })
      .catch(function () {});

    renderWebhookStatus();
    renderBotInfoCard(document.getElementById("bot-info-card"));
  }

  function renderActivityChart(daily) {
    var canvas = document.getElementById("chart-activity");
    if (!canvas) return;

    var labels = daily.map(function (d) {
      return new Date(d.date).toLocaleDateString("en-US", {
        weekday: "short",
        day: "numeric",
      });
    });
    var dataIn = daily.map(function (d) { return d.messages_in || 0; });
    var dataOut = daily.map(function (d) { return d.messages_out || 0; });

    var isDark = getTheme() === "dark";
    var gridColor = isDark ? "rgba(148,163,184,0.1)" : "rgba(15,23,42,0.06)";
    var textColor = isDark ? "#94A3B8" : "#64748B";

    if (chartActivity && chartActivity.canvas === canvas) {
      chartActivity.data.labels = labels;
      chartActivity.data.datasets[0].data = dataIn;
      chartActivity.data.datasets[1].data = dataOut;
      chartActivity.update('none');
      return;
    }

    if (chartActivity) { chartActivity.destroy(); chartActivity = null; }

    chartActivity = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Incoming",
            data: dataIn,
            backgroundColor: "rgba(6, 199, 85, 0.7)",
            borderRadius: 6,
            borderSkipped: false,
          },
          {
            label: "Outgoing",
            data: dataOut,
            backgroundColor: "rgba(59, 130, 246, 0.7)",
            borderRadius: 6,
            borderSkipped: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "top",
            align: "end",
            labels: { color: textColor, usePointStyle: true, pointStyle: "circle", padding: 16, font: { family: "Prompt", size: 12 } },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: textColor, font: { family: "Prompt", size: 11 } } },
          y: { grid: { color: gridColor }, ticks: { color: textColor, font: { family: "Prompt", size: 11 } }, beginAtZero: true },
        },
      },
    });
  }

  function renderRecentChats() {
    var el = document.getElementById("recent-chats");
    if (!el) return;

    // Skip re-render if data unchanged
    var sig = chats.slice(0, 5).map(function (c) { return c.id + c.last_active; }).join("|");
    if (el._lastSig === sig) return;
    el._lastSig = sig;

    var recent = chats.slice(0, 5);
    if (!recent.length) {
      el.innerHTML =
        '<div class="empty-state" style="padding:24px">' +
        '<p style="font-size:13px;color:var(--text-muted)">No conversations yet</p></div>';
      return;
    }

    el.innerHTML = recent
      .map(function (c) {
        var avInner = c.pic
          ? '<img src="' + esc(c.pic) + '" onerror="this.parentNode.textContent=\'' + avChar(c) + '\'">'
          : avChar(c);
        return (
          '<div class="recent-item" data-chat-id="' + esc(c.id) + '">' +
          '<div class="recent-avatar" style="background:' + avColor(c.name) + '">' + avInner + "</div>" +
          '<div class="recent-info">' +
          '<div class="recent-name">' + esc(c.name) + "</div>" +
          '<div class="recent-msg">' + esc(c.last_message || "No messages") + "</div>" +
          "</div>" +
          '<span class="recent-time">' + relTime(c.last_active) + "</span>" +
          "</div>"
        );
      })
      .join("");

    // Click handler
    el.querySelectorAll(".recent-item").forEach(function (item) {
      item.addEventListener("click", function () {
        navigate("inbox");
        setTimeout(function () {
          var id = item.getAttribute("data-chat-id");
          openChat(id);
        }, 100);
      });
    });
  }

  function renderWebhookStatus() {
    var el = document.getElementById("webhook-status");
    if (!el) return;

    var lastActive = chats.length ? chats[0].last_active : null;

    // Skip re-render if unchanged
    var sig = (lastActive || "") + chats.length;
    if (el._lastSig === sig) return;
    el._lastSig = sig;
    var isOnline = lastActive && (Date.now() - new Date(lastActive).getTime()) < 3600000;

    el.innerHTML =
      '<div class="status-row">' +
      '<span class="status-label">Status</span>' +
      '<span class="status-value"><span class="status-dot ' + (isOnline ? "online" : "offline") + '"></span>' +
      (isOnline ? "Connected" : "Idle") + "</span>" +
      "</div>" +
      '<div class="status-row">' +
      '<span class="status-label">Last Activity</span>' +
      '<span class="status-value">' + (lastActive ? relTime(lastActive) : "N/A") + "</span>" +
      "</div>" +
      '<div class="status-row">' +
      '<span class="status-label">Total Chats</span>' +
      '<span class="status-value">' + chats.length + "</span>" +
      "</div>";
  }

  function renderStorageStatus(data) {
    var el = document.getElementById("storage-status");
    if (!el) return;

    var sizeMB = data.media_size_mb || 0;
    var maxMB = 100; // reasonable limit display
    var pct = Math.min((sizeMB / maxMB) * 100, 100);

    el.innerHTML =
      '<div class="status-row">' +
      '<span class="status-label">Media Files</span>' +
      '<span class="status-value">' + (data.media_count || 0) + " files</span>" +
      "</div>" +
      '<div class="status-row">' +
      '<span class="status-label">Storage Used</span>' +
      '<span class="status-value">' + sizeMB.toFixed(1) + " MB</span>" +
      "</div>" +
      '<div class="status-row">' +
      '<span class="status-label">Chat Records</span>' +
      '<span class="status-value">' + (data.chat_count || 0) + "</span>" +
      "</div>" +
      '<div class="progress-bar"><div class="progress-fill" style="width:' + pct.toFixed(1) + '%"></div></div>';
  }

  // ============================================================
  // PAGE: CONVERSATIONS (INBOX)
  // ============================================================

  function renderInbox(container) {
    container.innerHTML =
      '<div class="inbox-layout">' +
      // Sidebar with chat list
      '<div class="inbox-sidebar" id="inbox-sidebar">' +
      '<div class="inbox-header">' +
      '<div class="inbox-title">' +
      "<h2>" + t("Conversations") + "</h2>" +
      '<div class="inbox-actions">' +
      '<button class="btn-icon" id="btn-refresh-chats" title="Refresh"><i data-lucide="refresh-cw"></i></button>' +
      "</div></div>" +
      '<div class="inbox-search"><i data-lucide="search"></i>' +
      '<input type="text" id="inbox-search" placeholder="' + t("Search conversations...") + '" autocomplete="off">' +
      "</div>" +
      '<div class="filter-tabs" id="filter-tabs">' +
      '<button class="filter-tab active" data-filter="all">' + t("All") + '</button>' +
      '<button class="filter-tab" data-filter="user">' + t("Direct") + '</button>' +
      '<button class="filter-tab" data-filter="group">' + t("Group") + '</button>' +
      '<button class="filter-tab" data-filter="starred">' + t("Starred") + '</button>' +
      "</div></div>" +
      '<div class="chat-list" id="chat-list"></div>' +
      "</div>" +
      // Chat detail area
      '<div class="chat-detail hidden" id="chat-detail">' +
      '<div class="chat-empty" id="chat-empty">' +
      '<div class="chat-empty-icon"><i data-lucide="message-circle"></i></div>' +
      "<h3>" + t("Select a Conversation") + "</h3>" +
      "<p>Choose a chat from the list to view messages and manage settings.</p>" +
      "</div></div>" +
      "</div>";

    // Bind events
    bindInboxEvents();
    renderChatList();
  }

  function bindInboxEvents() {
    // Search
    var searchInput = document.getElementById("inbox-search");
    if (searchInput) {
      searchInput.addEventListener("input", function () {
        renderChatList();
      });
    }

    // Filter tabs
    var filterTabs = document.getElementById("filter-tabs");
    if (filterTabs) {
      filterTabs.addEventListener("click", function (e) {
        var tab = e.target.closest(".filter-tab");
        if (!tab) return;
        currentFilter = tab.getAttribute("data-filter");
        filterTabs.querySelectorAll(".filter-tab").forEach(function (t) {
          t.classList.toggle("active", t === tab);
        });
        renderChatList();
      });
    }

    // Refresh
    var refreshBtn = document.getElementById("btn-refresh-chats");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        api("list_chats")
          .then(function (d) {
            chats = d.chats || [];
            renderChatList();
            toast(t("Refreshed"));
          })
          .catch(function () { toast(t("Connection error")); });
      });
    }

    // Load tag filter tabs dynamically
    api("manage_tags", { op: "list" })
      .then(function (d) {
        allTags = d.tags || [];
        if (allTags.length && filterTabs) {
          allTags.forEach(function (t) {
            var btn = document.createElement("button");
            btn.className = "filter-tab filter-tab-tag" + (currentFilter === "tag:" + t ? " active" : "");
            btn.setAttribute("data-filter", "tag:" + t);
            btn.innerHTML = '<i data-lucide="tag" style="width:10px;height:10px"></i> ' + esc(t);
            filterTabs.appendChild(btn);
          });
          try { lucide.createIcons(); } catch (e) {}
        }
      })
      .catch(function () {});
  }

  function filterChats() {
    var q = "";
    var searchEl = document.getElementById("inbox-search");
    if (searchEl) q = searchEl.value.toLowerCase();

    return chats.filter(function (c) {
      // Text search
      var matchText = !q || c.name.toLowerCase().indexOf(q) >= 0 || c.source_id.toLowerCase().indexOf(q) >= 0;
      if (!matchText) return false;

      // Filter tab
      switch (currentFilter) {
        case "user": return c.type === "user";
        case "group": return c.type === "group" || c.type === "room";
        case "starred": return c.starred;
        default:
          if (currentFilter.indexOf("tag:") === 0) {
            var filterTag = currentFilter.slice(4);
            return (c.tags || []).indexOf(filterTag) !== -1;
          }
          return true;
      }
    });
  }

  function renderChatList() {
    var listEl = document.getElementById("chat-list");
    if (!listEl) return;

    var filtered = filterChats();

    if (!filtered.length) {
      listEl.innerHTML =
        '<div class="empty-state">' +
        '<div class="empty-state-icon"><i data-lucide="inbox"></i></div>' +
        "<h3>" + t("No conversations") + "</h3>" +
        "<p>No chats match your current filters.</p>" +
        "</div>";
      try { lucide.createIcons({ nameAttr: "data-lucide", attrs: {} }); } catch (e) {}
      return;
    }

    listEl.innerHTML = filtered
      .map(function (c) {
        var isActive = activeChat && activeChat.id === c.id;
        var avInner = c.pic
          ? '<img src="' + esc(c.pic) + '" onerror="this.parentNode.textContent=\'' + avChar(c) + '\'">'
          : avChar(c);

        var tagsHtml = "";
        if (c.tags && c.tags.length) {
          tagsHtml = c.tags
            .slice(0, 2)
            .map(function (t) {
              var cls = "";
              if (t === "vip") cls = " vip";
              else if (t === "complaint") cls = " complaint";
              else if (t === "new") cls = " new";
              return '<span class="tag-pill' + cls + '" data-filter-tag="' + esc(t) + '">' + esc(t) + "</span>";
            })
            .join("");
        }

        var unreadBadge = "";
        if (c._unread && c._unreadCount > 0) {
          unreadBadge = '<span class="unread-badge">' + (c._unreadCount > 99 ? "99+" : c._unreadCount) + '</span>';
        }

        return (
          '<div class="chat-item' +
          (c.disabled ? " disabled" : "") +
          (isActive ? " active" : "") +
          (c._unread ? " unread" : "") +
          '" data-chat-id="' + esc(c.id) + '">' +
          '<div class="chat-avatar" style="background:' + avColor(c.name) + '">' +
          avInner +
          '<span class="status-indicator ' + (c.disabled ? "off" : "on") + '"></span>' +
          unreadBadge +
          "</div>" +
          '<div class="chat-body">' +
          '<div class="chat-body-top">' +
          '<span class="chat-name">' + esc(c.name) + "</span>" +
          '<span class="chat-time">' + relTime(c.last_active) + "</span>" +
          "</div>" +
          '<div class="chat-preview">' + esc(c.last_message || "") + "</div>" +
          '<div class="chat-meta">' +
          (c.mc ? '<span class="chat-badge">' + c.mc + "</span>" : "") +
          tagsHtml +
          '<span class="chat-star' + (c.starred ? " starred" : "") + '" data-star-id="' + esc(c.id) + '">' +
          '<i data-lucide="' + (c.starred ? "star" : "star") + '"></i></span>' +
          "</div></div></div>"
        );
      })
      .join("");

    // Click handlers
    listEl.querySelectorAll(".chat-item").forEach(function (item) {
      item.addEventListener("click", function (e) {
        // Ignore star clicks
        if (e.target.closest(".chat-star")) return;
        // Tag pill click → filter by tag
        var tagPill = e.target.closest("[data-filter-tag]");
        if (tagPill) {
          e.stopPropagation();
          currentFilter = "tag:" + tagPill.getAttribute("data-filter-tag");
          var filterTabs = document.getElementById("filter-tabs");
          if (filterTabs) {
            filterTabs.querySelectorAll(".filter-tab").forEach(function (t) {
              t.classList.toggle("active", t.getAttribute("data-filter") === currentFilter);
            });
          }
          renderChatList();
          return;
        }
        var id = item.getAttribute("data-chat-id");
        openChat(id);
      });
    });

    // Star toggle handlers
    listEl.querySelectorAll(".chat-star").forEach(function (star) {
      star.addEventListener("click", function (e) {
        e.stopPropagation();
        var id = star.getAttribute("data-star-id");
        var chat = chats.find(function (c) { return c.id === id; });
        if (!chat) return;
        var newStarred = !chat.starred;
        api("update_chat_meta", { chat_id: id, starred: newStarred })
          .then(function () {
            chat.starred = newStarred;
            renderChatList();
            toast(newStarred ? "Chat starred" : "Star removed");
          })
          .catch(function () { toast(t("Failed to update")); });
      });
    });

    try { lucide.createIcons(); } catch (e) {}
  }

  // === OPEN CHAT ===

  function openChat(id) {
    var c = chats.find(function (x) { return x.id === id; });
    if (!c) return;
    activeChat = c;
    if (c.last_active) {
      localStorage.setItem("lc_read_" + c.id, c.last_active);
      localStorage.setItem("lc_readmc_" + c.id, String(c.mc || 0));
      c._unread = false;
      c._unreadCount = 0;
      updateInboxBadge();
    }

    // On mobile, hide the list and show detail
    var sidebarPanel = document.getElementById("inbox-sidebar");
    if (sidebarPanel) sidebarPanel.classList.add("hidden-mobile");

    var detailEl = document.getElementById("chat-detail");
    if (!detailEl) return;
    detailEl.classList.remove("hidden", "hidden-mobile");

    var avInner = c.pic
      ? '<img src="' + esc(c.pic) + '" onerror="this.parentNode.textContent=\'' + avChar(c) + '\'">'
      : avChar(c);

    var origLabel = c.custom_name ? '<span class="original-name-label">LINE: ' + esc(c.original_name || c.name) + "</span>" : "";

    detailEl.innerHTML =
      '<div class="chat-detail-header">' +
      '<button class="chat-detail-back" id="btn-chat-back"><i data-lucide="arrow-left"></i></button>' +
      '<div class="chat-avatar" style="background:' + avColor(c.original_name || c.name) + ';width:40px;height:40px;font-size:14px">' + avInner + "</div>" +
      '<div class="chat-detail-info">' +
      '<div class="chat-name-row">' +
      '<h3 id="chat-display-name">' + esc(c.name) + "</h3>" +
      '<button class="btn-icon btn-edit-name" id="btn-edit-name" title="Edit name"><i data-lucide="pencil" style="width:14px;height:14px"></i></button>' +
      "</div>" +
      origLabel +
      '<span class="type-badge">' + typeLabel(c.type) + "</span>" +
      "</div>" +
      '<div class="chat-detail-actions">' +
      '<div class="desktop-actions desktop-only">' +
      '<button class="btn-icon" id="btn-export-chat" title="Export chat"><i data-lucide="download"></i></button>' +
      '<button class="btn-icon" id="btn-clear-chat" title="Clear history" style="color:var(--danger)"><i data-lucide="trash-2"></i></button>' +
      '</div>' +
      '<button class="btn-icon mobile-only" id="btn-mobile-actions" style="margin-left:auto"><i data-lucide="more-vertical"></i></button>' +
      '<div class="mobile-actions-dropdown hidden" id="mobile-actions-dropdown">' +
      '<div class="dropdown-item" id="btn-export-chat-mobile"><i data-lucide="download"></i> Export Chat</div>' +
      '<div class="dropdown-item danger" id="btn-clear-chat-mobile"><i data-lucide="trash-2"></i> Clear History</div>' +
      '</div>' +
      "</div></div>" +
      '<div class="messages-area" id="messages-area">' +
      '<div style="padding:40px;text-align:center"><div class="loading-spinner"></div></div>' +
      "</div>" +
      '<div class="chat-composer">' +
      '<textarea id="composer-input" placeholder="Type a message..." rows="1"></textarea>' +
      '<button class="btn-send" id="btn-send-msg" title="Send"><i data-lucide="send"></i></button>' +
      "</div>" +
      '<div class="chat-tags-section">' +
      '<div style="display:flex; align-items:center; gap:12px; min-height:24px;">' +
      '<label style="margin:0; flex-shrink:0;">TAGS</label>' +
      '<div class="chat-tags-row" id="chat-tags-row" style="margin:0; flex:1;"></div>' +
      '<div style="position:relative; flex-shrink:0;">' +
      '<button class="btn-add-tag-inline" id="btn-show-tag-picker" title="Add tag"><i data-lucide="plus" style="width:14px;height:14px"></i></button>' +
      '<div class="tag-picker-dropdown hidden" id="tag-picker-dropdown" style="right:0; left:auto; bottom:100%; top:auto; margin-bottom:4px;"></div>' +
      "</div></div></div>" +
      '<div class="chat-notes">' +
      "<label>Notes</label>" +
      '<textarea id="chat-notes-input" placeholder="Add notes about this chat..."></textarea>' +
      "</div>";

    // Bind detail events
    bindChatDetailEvents(c);

    // Load messages
    forceScroll = true;
    allMsgs = [];
    shownMsgs = 0;
    startHistPoll();

    // Load notes & tags
    loadChatNotes(c.id);
    loadChatTags(c);

    // Update list highlight
    renderChatList();

    try { lucide.createIcons(); } catch (e) {}
  }

  function bindChatDetailEvents(chat) {
    // Back button
    var backBtn = document.getElementById("btn-chat-back");
    if (backBtn) {
      backBtn.addEventListener("click", function () {
        closeChatDetail();
      });
    }

    // Edit name
    var editNameBtn = document.getElementById("btn-edit-name");
    if (editNameBtn) {
      editNameBtn.addEventListener("click", function () {
        var h3 = document.getElementById("chat-display-name");
        if (!h3) return;
        var current = chat.custom_name || chat.name || "";
        var orig = chat.original_name || chat.name || "";
        h3.innerHTML =
          '<input type="text" id="input-custom-name" class="inline-name-input" value="' + esc(current) + '" placeholder="' + esc(orig) + '">' +
          '<button class="btn-icon btn-save-name" id="btn-save-name" title="Save"><i data-lucide="check" style="width:14px;height:14px;color:var(--green)"></i></button>' +
          '<button class="btn-icon btn-cancel-name" id="btn-cancel-name" title="Cancel"><i data-lucide="x" style="width:14px;height:14px"></i></button>';
        try { lucide.createIcons(); } catch (e) {}
        var inp = document.getElementById("input-custom-name");
        if (inp) { inp.focus(); inp.select(); }

        document.getElementById("btn-save-name").addEventListener("click", function () {
          var newName = (document.getElementById("input-custom-name").value || "").trim();
          api("update_chat_meta", { chat_id: chat.id, custom_name: newName })
            .then(function () {
              chat.custom_name = newName;
              chat.name = newName || orig;
              h3.textContent = chat.name;
              renderChatList();
              toast(newName ? "Name updated" : "Name reset to LINE display name");
            })
            .catch(function () { toast(t("Failed to update name")); });
        });

        document.getElementById("btn-cancel-name").addEventListener("click", function () {
          h3.textContent = chat.name;
        });

        inp.addEventListener("keydown", function (e) {
          if (e.key === "Enter") document.getElementById("btn-save-name").click();
          if (e.key === "Escape") document.getElementById("btn-cancel-name").click();
        });
      });
    }

    // Mobile actions toggle
    var btnMobile = document.getElementById("btn-mobile-actions");
    var mobileDropdown = document.getElementById("mobile-actions-dropdown");
    if (btnMobile && mobileDropdown) {
      btnMobile.addEventListener("click", function(e) {
        e.stopPropagation();
        mobileDropdown.classList.toggle("hidden");
      });
      document.addEventListener("click", function(e) {
        if (!mobileDropdown.contains(e.target) && e.target !== btnMobile && !btnMobile.contains(e.target)) {
          mobileDropdown.classList.add("hidden");
        }
      });
    }

    // Export
    var doExport = function() { exportCurrentChat(); if(mobileDropdown) mobileDropdown.classList.add("hidden"); };
    var exportBtn = document.getElementById("btn-export-chat");
    if (exportBtn) exportBtn.addEventListener("click", doExport);
    var exportBtnMobile = document.getElementById("btn-export-chat-mobile");
    if (exportBtnMobile) exportBtnMobile.addEventListener("click", doExport);

    // Clear history
    var doClear = function() {
      if(mobileDropdown) mobileDropdown.classList.add("hidden");
      modal("Clear History", "<p>This will permanently delete all messages in this conversation. This cannot be undone.</p>", function() {
        api("clear_history", { chat_id: chat.id })
          .then(function() {
            allMsgs = []; shownMsgs = 0; renderMessages(); toast(t("History cleared"));
          }).catch(function() { toast(t("Failed to clear")); });
      });
    };
    var clearBtn = document.getElementById("btn-clear-chat");
    if (clearBtn) clearBtn.addEventListener("click", doClear);
    var clearBtnMobile = document.getElementById("btn-clear-chat-mobile");
    if (clearBtnMobile) clearBtnMobile.addEventListener("click", doClear);

    // Notes auto-save
    var notesInput = document.getElementById("chat-notes-input");
    if (notesInput) {
      notesInput.addEventListener("blur", function () {
        var notes = this.value;
        api("update_chat_meta", { chat_id: chat.id, notes: notes })
          .then(function () { /* silent save */ })
          .catch(function () { toast(t("Failed to save notes")); });
      });
    }

    // Scroll to load older messages
    var msgsArea = document.getElementById("messages-area");
    if (msgsArea) {
      msgsArea.addEventListener("scroll", function () {
        if (this.scrollTop < 50 && shownMsgs < allMsgs.length && !loadingMore) {
          loadOlderMessages();
        }
      });
    }

    // Composer (admin reply)
    var composerInput = document.getElementById("composer-input");
    var sendMsgBtn = document.getElementById("btn-send-msg");
    if (composerInput && sendMsgBtn) {
      var sendComposerMsg = function () {
        var text = composerInput.value.trim();
        if (!text) return;
        composerInput.disabled = true;
        sendMsgBtn.disabled = true;
        api("send_message", { chat_id: chat.id, text: text })
          .then(function () {
            composerInput.value = "";
            composerInput.disabled = false;
            sendMsgBtn.disabled = false;
            composerInput.focus();
            fetchHistory();
          })
          .catch(function () {
            composerInput.disabled = false;
            sendMsgBtn.disabled = false;
            toast(t("Connection error"));
          });
      };
      sendMsgBtn.addEventListener("click", sendComposerMsg);
      composerInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendComposerMsg();
        }
      });
    }
  }

  function closeChatDetail() {
    activeChat = null;
    isBotTyping = false;
    stopHistPoll();

    var sidebarPanel = document.getElementById("inbox-sidebar");
    if (sidebarPanel) sidebarPanel.classList.remove("hidden-mobile");

    var detailEl = document.getElementById("chat-detail");
    if (detailEl) {
      detailEl.classList.add("hidden");
      detailEl.innerHTML =
        '<div class="chat-empty" id="chat-empty">' +
        '<div class="chat-empty-icon"><i data-lucide="message-circle"></i></div>' +
        "<h3>" + t("Select a Conversation") + "</h3>" +
        "<p>Choose a chat from the list to view messages and manage settings.</p>" +
        "</div>";
    }

    renderChatList();
    try { lucide.createIcons(); } catch (e) {}
  }

  function loadChatNotes(chatId) {
    api("get_chat_meta", { chat_id: chatId })
      .then(function (d) {
        var meta = d.meta || {};
        var notesInput = document.getElementById("chat-notes-input");
        if (notesInput) notesInput.value = meta.notes || "";
      })
      .catch(function () {});
  }

  function loadChatTags(chat) {
    api("get_chat_meta", { chat_id: chat.id })
      .then(function (d) {
        var meta = d.meta || {};
        chat.tags = meta.tags || [];
        var c = chats.find(function (x) { return x.id === chat.id; });
        if (c) c.tags = chat.tags;
        renderChatTags(chat);
      })
      .catch(function () {});
  }

  function renderChatTags(chat) {
    var row = document.getElementById("chat-tags-row");
    if (!row) return;
    var tags = chat.tags || [];
    if (!tags.length) {
      row.innerHTML = '<span style="font-size:11px;color:var(--text-light);font-style:italic;">No tags</span>';
    } else {
      row.innerHTML = tags.map(function (t) {
        var cls = t === "vip" ? " vip" : t === "complaint" ? " complaint" : t === "new" ? " new" : "";
        return '<span class="tag-pill' + cls + '">' + esc(t) +
          '<button class="tag-pill-remove" data-tag="' + esc(t) + '">\u00d7</button></span>';
      }).join("");
    }

    row.querySelectorAll(".tag-pill-remove").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var tag = this.getAttribute("data-tag");
        var newTags = (chat.tags || []).filter(function (t) { return t !== tag; });
        api("update_chat_meta", { chat_id: chat.id, tags: newTags })
          .then(function () {
            chat.tags = newTags;
            var c = chats.find(function (x) { return x.id === chat.id; });
            if (c) c.tags = newTags;
            renderChatTags(chat);
            renderChatList();
          })
          .catch(function () { toast(t("Failed to remove tag")); });
      });
    });

    // Tag picker button
    var pickerBtn = document.getElementById("btn-show-tag-picker");
    if (pickerBtn) {
      pickerBtn.onclick = function (e) {
        e.stopPropagation();
        var dropdown = document.getElementById("tag-picker-dropdown");
        if (!dropdown) return;
        var currentTags = chat.tags || [];
        var available = allTags.filter(function (t) { return currentTags.indexOf(t) === -1; });
        if (!available.length) {
          dropdown.innerHTML = '<div class="tag-picker-empty">No more tags available</div>';
        } else {
          dropdown.innerHTML = available.map(function (t) {
            return '<div class="tag-picker-option" data-tag="' + esc(t) + '">' + esc(t) + '</div>';
          }).join("");
        }
        dropdown.classList.toggle("hidden");

        dropdown.querySelectorAll(".tag-picker-option").forEach(function (opt) {
          opt.addEventListener("click", function () {
            var tag = this.getAttribute("data-tag");
            var newTags = (chat.tags || []).concat([tag]);
            api("update_chat_meta", { chat_id: chat.id, tags: newTags })
              .then(function () {
                chat.tags = newTags;
                var c = chats.find(function (x) { return x.id === chat.id; });
                if (c) c.tags = newTags;
                dropdown.classList.add("hidden");
                renderChatTags(chat);
                renderChatList();
                toast(t("Tag added"));
              })
              .catch(function () { toast(t("Failed to add tag")); });
          });
        });
      };
    }

    // Close picker on outside click
    document.addEventListener("click", function closePicker(e) {
      var d = document.getElementById("tag-picker-dropdown");
      if (d && !d.contains(e.target) && e.target.id !== "btn-show-tag-picker") {
        d.classList.add("hidden");
      }
    });

    try { lucide.createIcons(); } catch (e) {}
  }

  // === MESSAGES ===

  function fetchHistory() {
    if (!activeChat) return;
    api("get_history", { chat_id: activeChat.id })
      .then(function (d) {
        var history = d.history || [];
        var typing = !!d.typing;
        var sig = history.length + ":" + (history.length ? history[history.length - 1].ts + history[history.length - 1].t : "");

        if (sig !== lastMsgSig) {
          var isFirst = lastMsgSig === "";
          lastMsgSig = sig;
          var oldLen = allMsgs.length;
          allMsgs = history;

          if (isFirst || forceScroll) {
            shownMsgs = Math.min(PAGE_SIZE, allMsgs.length);
            renderMessages();
            forceScroll = false;
          } else {
            var diff = allMsgs.length - oldLen;
            if (diff > 0 && diff < 20) {
              shownMsgs += diff;
              appendNewMessages(diff);
            } else if (diff !== 0) {
              renderMessages();
            }
          }
        }

        // Update typing indicator
        if (typing !== isBotTyping) {
          isBotTyping = typing;
          updateTypingIndicator();
        }
      })
      .catch(function () {});
  }

  function msgHtml(m) {
    var isImg = m.tp === "image" || (m.t && m.t.indexOf("[") === 0 && m.t.indexOf("]") > 0 && m.t.toLowerCase().indexOf("image") >= 0);
    var body = "";

    if (isImg && m.mid) {
      body = '<div data-mid="' + esc(m.mid) + '" style="min-height:60px;display:flex;align-items:center;justify-content:center"><div class="loading-spinner"></div></div>';
    } else if (isImg) {
      body = '<span style="opacity:.8;font-size:13px">Sent an image</span>';
    } else {
      body = esc(m.t);
    }

    return (
      '<div class="msg ' + m.r + '">' +
      (m.r === "user" && m.n ? '<div class="sender-name">' + esc(m.n) + "</div>" : "") +
      body +
      '<div class="msg-time">' + fmtTime(m.ts) + "</div></div>"
    );
  }

  function renderMessages() {
    var el = document.getElementById("messages-area");
    if (!el) return;

    if (!allMsgs || !allMsgs.length) {
      el.innerHTML =
        '<div class="empty-state" style="flex:1">' +
        '<div class="empty-state-icon"><i data-lucide="message-square"></i></div>' +
        "<h3>" + t("No messages yet") + "</h3>" +
        "<p>Messages will appear here when they arrive.</p></div>";
      try { lucide.createIcons(); } catch (e) {}
      return;
    }

    var slice = allMsgs.slice(-shownMsgs);
    var hasMore = shownMsgs < allMsgs.length;

    el.innerHTML =
      (hasMore
        ? '<div id="load-more" style="text-align:center;padding:12px;"><span style="font-size:12px;color:var(--text-light)">Loading older messages...</span></div>'
        : "") + slice.map(msgHtml).join("");

    var loadBtn = document.getElementById("load-more");
    if (loadBtn && window.IntersectionObserver) {
      new IntersectionObserver(function(entries, observer) {
        if (entries[0].isIntersecting) {
          loadOlderMessages();
          observer.disconnect();
        }
      }).observe(loadBtn);
    }

    // Re-add typing indicator if bot is currently typing
    if (isBotTyping) {
      el.insertAdjacentHTML("beforeend",
        '<div class="typing-indicator" id="typing-bubble">' +
        '<div class="typing-dots">' +
        '<div class="typing-dot"></div>' +
        '<div class="typing-dot"></div>' +
        '<div class="typing-dot"></div>' +
        '</div></div>');
    }

    setTimeout(function () {
      el.scrollTop = el.scrollHeight;
    }, 50);

    loadImages(slice, true);
  }

  function appendNewMessages(count) {
    var el = document.getElementById("messages-area");
    if (!el) return;

    var wasAtBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 100;
    var newMsgs = allMsgs.slice(-count);
    el.insertAdjacentHTML("beforeend", newMsgs.map(msgHtml).join(""));

    if (wasAtBottom) {
      setTimeout(function () {
        el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      }, 20);
    }

    loadImages(newMsgs, wasAtBottom ? "smooth" : false);
  }

  function updateTypingIndicator() {
    var el = document.getElementById("messages-area");
    if (!el) return;
    var existing = document.getElementById("typing-bubble");
    if (isBotTyping) {
      if (!existing) {
        var html =
          '<div class="typing-indicator" id="typing-bubble">' +
          '<div class="typing-dots">' +
          '<div class="typing-dot"></div>' +
          '<div class="typing-dot"></div>' +
          '<div class="typing-dot"></div>' +
          '</div></div>';
        el.insertAdjacentHTML("beforeend", html);
        var wasAtBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 120;
        if (wasAtBottom) {
          setTimeout(function () {
            el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
          }, 20);
        }
      }
    } else {
      if (existing) existing.remove();
    }
  }

  function loadOlderMessages() {
    if (loadingMore || shownMsgs >= allMsgs.length) return;
    loadingMore = true;

    var el = document.getElementById("messages-area");
    if (!el) { loadingMore = false; return; }

    var prevH = el.scrollHeight;
    var prev = shownMsgs;
    shownMsgs = Math.min(shownMsgs + PAGE_SIZE, allMsgs.length);
    var olderSlice = allMsgs.slice(-shownMsgs, -prev);

    var btn = document.getElementById("load-more");
    if (btn) btn.remove();

    var hasMore = shownMsgs < allMsgs.length;
    var html =
      (hasMore
        ? '<div id="load-more" style="text-align:center;padding:12px;"><span style="font-size:12px;color:var(--text-light)">Loading older messages...</span></div>'
        : "") + olderSlice.map(msgHtml).join("");

    el.insertAdjacentHTML("afterbegin", html);
    
    var newLoadBtn = document.getElementById("load-more");
    if (newLoadBtn && window.IntersectionObserver) {
      new IntersectionObserver(function(entries, observer) {
        if (entries[0].isIntersecting) {
          loadOlderMessages();
          observer.disconnect();
        }
      }).observe(newLoadBtn);
    }

    el.scrollTop = el.scrollHeight - prevH;
    loadImages(olderSlice, false);
    loadingMore = false;
  }

  function loadImages(list, scrollMode) {
    list.forEach(function (m) {
      if (!m.mid) return;
      var mid = m.mid;
      api("get_image", { message_id: mid })
        .then(function (blob) {
          var url = URL.createObjectURL(blob);
          var d = document.querySelector('[data-mid="' + mid + '"]');
          if (d) {
            d.innerHTML = '<img src="' + url + '" style="max-width:260px;width:100%;border-radius:8px;display:block;cursor:zoom-in">';
            d.querySelector("img").addEventListener("click", function () {
              previewImg(url);
            });
            d.querySelector("img").onload = function () {
              var msgsEl = document.getElementById("messages-area");
              if (!msgsEl) return;
              if (scrollMode === true) {
                msgsEl.scrollTop = msgsEl.scrollHeight;
              } else if (scrollMode === "smooth") {
                msgsEl.scrollTo({ top: msgsEl.scrollHeight, behavior: "smooth" });
              }
            };
          }
        })
        .catch(function () {
          var d = document.querySelector('[data-mid="' + mid + '"]');
          if (d) d.innerHTML = '<span style="opacity:.6;font-size:12px">Image unavailable</span>';
        });
    });
  }

  /** Lightbox preview */
  function previewImg(src) {
    var lb = document.getElementById("lightbox");
    var img = document.getElementById("lightbox-img");
    img.src = src;
    lb.style.display = "flex";
    lb.onclick = function () {
      lb.style.display = "none";
      img.src = "";
    };
  }

  /** Export current chat (server-side CSV; not limited to the loaded page of messages) */
  function exportCurrentChat() {
    if (!activeChat) return;
    var chatId = activeChat.id;

    fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "export_chat", chat_id: chatId, format: "csv", token: authToken }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error("export failed");
        return r.blob();
      })
      .then(function (blob) {
        downloadFile(blob, "chat-" + chatId + ".csv", "text/csv");
        toast(t("Chat exported as CSV"));
      })
      .catch(function () {
        toast(t("Connection error"));
      });
  }

  // ============================================================
  // PAGE: ANALYTICS
  // ============================================================

  function renderAnalytics(container) {
    container.innerHTML =
      '<div class="page" id="page-analytics">' +
      '<div class="page-header">' +
      "<h1>" + t("Analytics") + "</h1>" +
      "<p>" + t("Performance metrics and usage statistics") + "</p>" +
      "</div>" +
      // Controls
      '<div class="analytics-controls">' +
      '<div class="date-range-tabs" id="date-range-tabs">' +
      '<button class="date-range-tab active" data-range="7d">7 Days</button>' +
      '<button class="date-range-tab" data-range="30d">30 Days</button>' +
      '<button class="date-range-tab" data-range="90d">90 Days</button>' +
      "</div>" +
      '<button class="btn-secondary btn-sm" id="btn-export-analytics"><i data-lucide="download" style="width:14px;height:14px"></i> Export CSV</button>' +
      "</div>" +
      // Summary cards
      '<div class="analytics-summary" id="analytics-summary">' +
      analyticsSummaryCardHtml("Total Messages", "--", "analytics-sum-msgs", "message-square") +
      analyticsSummaryCardHtml("Unique Users", "--", "analytics-sum-users", "users") +
      analyticsSummaryCardHtml("New Users", "--", "analytics-sum-new", "user-plus") +
      analyticsSummaryCardHtml("Images Sent", "--", "analytics-sum-img", "image") +
      "</div>" +
      // Performance stats with trends
      '<div class="perf-grid" id="perf-grid">' +
      perfStatHtml("--", "Total Queries", "perf-queries", "trend-queries") +
      perfStatHtml("--", "Success Rate", "perf-success", "trend-success") +
      perfStatHtml("--", "Avg Response", "perf-avgtime", "trend-avgtime") +
      perfStatHtml("--", "Error Rate", "perf-errors", "trend-errors") +
      "</div>" +
      // Charts
      '<div class="analytics-grid">' +
      '<div class="chart-card">' +
      '<div class="chart-card-title">Message Volume</div>' +
      '<div class="chart-wrap"><canvas id="chart-volume"></canvas></div>' +
      "</div>" +
      '<div class="chart-card">' +
      '<div class="chart-card-title">Response Time Distribution</div>' +
      '<div class="chart-wrap"><canvas id="chart-response"></canvas></div>' +
      "</div></div>" +
      // User Growth + RT Trend
      '<div class="analytics-grid">' +
      '<div class="chart-card">' +
      '<div class="chart-card-title">User Growth <span>New users per day</span></div>' +
      '<div class="chart-wrap"><canvas id="chart-user-growth"></canvas></div>' +
      "</div>" +
      '<div class="chart-card">' +
      '<div class="chart-card-title">Avg Response Time <span>Daily trend</span></div>' +
      '<div class="chart-wrap"><canvas id="chart-rt-trend"></canvas></div>' +
      "</div></div>" +
      // Heatmap
      '<div class="chart-card" style="margin-bottom:var(--sp-5)">' +
      '<div class="chart-card-title">Peak Hours Heatmap <span>Messages by day and hour</span></div>' +
      '<div class="heatmap-container" id="heatmap-container"></div>' +
      "</div>" +
      // Top chats table
      '<div class="chart-card">' +
      '<div class="chart-card-title">Most Active Chats</div>' +
      '<div id="top-chats-table"></div>' +
      "</div>" +
      "</div>";

    bindAnalyticsEvents();
    loadAnalyticsData();
  }

  function analyticsSummaryCardHtml(label, value, id, icon) {
    return (
      '<div class="analytics-summary-card">' +
      '<div class="analytics-summary-card-icon"><i data-lucide="' + icon + '"></i></div>' +
      '<div class="analytics-summary-card-value" id="' + id + '">' + value + "</div>" +
      '<div class="analytics-summary-card-label">' + esc(label) + "</div></div>"
    );
  }

  function perfStatHtml(value, label, id, trendId) {
    return (
      '<div class="perf-stat">' +
      '<div class="perf-stat-value" id="' + id + '">' + value + "</div>" +
      '<div class="perf-stat-label">' + esc(label) + "</div>" +
      (trendId ? '<div class="perf-stat-trend" id="' + trendId + '"></div>' : '') +
      "</div>"
    );
  }

  function bindAnalyticsEvents() {
    // Date range tabs
    var tabs = document.getElementById("date-range-tabs");
    if (tabs) {
      tabs.addEventListener("click", function (e) {
        var tab = e.target.closest(".date-range-tab");
        if (!tab) return;
        analyticsRange = tab.getAttribute("data-range");
        tabs.querySelectorAll(".date-range-tab").forEach(function (t) {
          t.classList.toggle("active", t === tab);
        });
        loadAnalyticsData();
      });
    }

    // Export
    var exportBtn = document.getElementById("btn-export-analytics");
    if (exportBtn) {
      exportBtn.addEventListener("click", function () {
        exportAnalytics();
      });
    }
  }

  var _analyticsDaily = [];

  function loadAnalyticsData() {
    var days = analyticsRange === "90d" ? 90 : analyticsRange === "30d" ? 30 : 7;

    // Analytics data
    api("get_analytics", { days: days })
      .then(function (d) {
        _analyticsDaily = d.daily || [];
        renderVolumeChart(_analyticsDaily);
        renderHeatmap(_analyticsDaily);
        renderTopChatsTable();
        renderUserGrowthChart(_analyticsDaily);
        renderRtTrendChart(_analyticsDaily);

        // Summary cards
        var totalMsgs = _analyticsDaily.reduce(function (s, x) { return s + (x.messages_in || 0) + (x.messages_out || 0); }, 0);
        var maxUsers = _analyticsDaily.reduce(function (s, x) { return Math.max(s, x.unique_users || 0); }, 0);
        var totalNew = _analyticsDaily.reduce(function (s, x) { return s + (x.new_users || 0); }, 0);
        var totalImg = _analyticsDaily.reduce(function (s, x) { return s + (x.images || 0); }, 0);
        var el;
        el = document.getElementById("analytics-sum-msgs"); if (el) countUp(el, totalMsgs, 600);
        el = document.getElementById("analytics-sum-users"); if (el) countUp(el, maxUsers, 600);
        el = document.getElementById("analytics-sum-new"); if (el) countUp(el, totalNew, 600);
        el = document.getElementById("analytics-sum-img"); if (el) countUp(el, totalImg, 600);

        // Response times chart
        if (d.response_times) {
          renderResponseChart(d.response_times);
        }
      })
      .catch(function () {});

    // Performance data with trend comparison
    api("get_performance", { days: days })
      .then(function (d) {
        var t = d.totals || {};
        var prev = d.prev_totals || {};
        var qEl = document.getElementById("perf-queries");
        var sEl = document.getElementById("perf-success");
        var aEl = document.getElementById("perf-avgtime");
        var eEl = document.getElementById("perf-errors");

        if (qEl) countUp(qEl, t.queries || 0, 600);
        if (sEl) sEl.textContent = (t.success_rate || 0).toFixed(1) + "%";
        if (aEl) {
          var avg = t.avg_response_time || 0;
          aEl.textContent = avg < 1 ? (avg * 1000).toFixed(0) + "ms" : avg.toFixed(2) + "s";
        }
        if (eEl) eEl.textContent = (t.errors || 0).toLocaleString();

        // Trend indicators vs previous period
        renderTrend("trend-queries", t.queries, prev.queries);
        renderTrend("trend-success", t.success_rate, prev.success_rate);
        renderTrend("trend-errors", t.errors, prev.errors, true);
      })
      .catch(function () {});
  }

  function renderVolumeChart(daily) {
    var canvas = document.getElementById("chart-volume");
    if (!canvas) return;
    if (chartVolume) chartVolume.destroy();

    var labels = daily.map(function (d) {
      return new Date(d.date).toLocaleDateString("en-US", { month: "short", day: "numeric" });
    });
    var dataIn = daily.map(function (d) { return d.messages_in || 0; });
    var dataOut = daily.map(function (d) { return d.messages_out || 0; });
    var dataImg = daily.map(function (d) { return d.images || 0; });

    var isDark = getTheme() === "dark";
    var gridColor = isDark ? "rgba(148,163,184,0.1)" : "rgba(15,23,42,0.06)";
    var textColor = isDark ? "#94A3B8" : "#64748B";

    chartVolume = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Incoming",
            data: dataIn,
            borderColor: "#06C755",
            backgroundColor: "rgba(6, 199, 85, 0.1)",
            fill: true,
            tension: 0.4,
            pointRadius: 3,
            pointHoverRadius: 6,
          },
          {
            label: "Outgoing",
            data: dataOut,
            borderColor: "#3B82F6",
            backgroundColor: "rgba(59, 130, 246, 0.08)",
            fill: true,
            tension: 0.4,
            pointRadius: 3,
            pointHoverRadius: 6,
          },
          {
            label: "Images",
            data: dataImg,
            borderColor: "#EC4899",
            backgroundColor: "rgba(236, 72, 153, 0.08)",
            fill: false,
            tension: 0.4,
            pointRadius: 2,
            borderDash: [4, 4],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "top", align: "end",
            labels: { color: textColor, usePointStyle: true, pointStyle: "circle", padding: 16, font: { family: "Prompt", size: 12 } },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: textColor, font: { family: "Prompt", size: 11 }, maxTicksLimit: 10 } },
          y: { grid: { color: gridColor }, ticks: { color: textColor, font: { family: "Prompt", size: 11 } }, beginAtZero: true },
        },
        interaction: { mode: "index", intersect: false },
      },
    });
  }

  function renderResponseChart(responseTimes) {
    var canvas = document.getElementById("chart-response");
    if (!canvas) return;
    if (chartResponseTime) chartResponseTime.destroy();

    // Bucket response times
    var buckets = { "<1s": 0, "1-3s": 0, "3-5s": 0, "5-10s": 0, ">10s": 0 };
    if (Array.isArray(responseTimes)) {
      responseTimes.forEach(function (t) {
        if (t < 1) buckets["<1s"]++;
        else if (t < 3) buckets["1-3s"]++;
        else if (t < 5) buckets["3-5s"]++;
        else if (t < 10) buckets["5-10s"]++;
        else buckets[">10s"]++;
      });
    } else if (typeof responseTimes === "object") {
      buckets = responseTimes;
    }

    var isDark = getTheme() === "dark";
    var textColor = isDark ? "#94A3B8" : "#64748B";

    chartResponseTime = new Chart(canvas.getContext("2d"), {
      type: "doughnut",
      data: {
        labels: Object.keys(buckets),
        datasets: [{
          data: Object.values(buckets),
          backgroundColor: [
            "#06C755", "#3B82F6", "#F59E0B", "#F97316", "#EF4444",
          ],
          borderWidth: 0,
          spacing: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "65%",
        plugins: {
          legend: {
            position: "right",
            labels: { color: textColor, usePointStyle: true, padding: 12, font: { family: "Prompt", size: 12 } },
          },
        },
      },
    });
  }

  function renderHeatmap(daily) {
    var container = document.getElementById("heatmap-container");
    if (!container) return;

    var dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

    // Build hourly matrix: 7 days x 24 hours
    var matrix = {};
    daily.forEach(function (d) {
      var dayOfWeek = new Date(d.date).getDay(); // 0=Sun
      var adjustedDay = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // 0=Mon
      if (d.hourly) {
        d.hourly.forEach(function (h, hourIdx) {
          var key = adjustedDay + "-" + hourIdx;
          matrix[key] = (matrix[key] || 0) + (h.messages_in || 0) + (h.messages_out || 0);
        });
      }
    });

    // Find max for intensity scaling
    var maxVal = 1;
    Object.values(matrix).forEach(function (v) { if (v > maxVal) maxVal = v; });

    // Header row
    var html = '<div class="heatmap-grid">';
    html += '<div class="heatmap-label"></div>'; // corner
    for (var h = 0; h < 24; h++) {
      html += '<div class="heatmap-header">' + (h < 10 ? "0" : "") + h + "</div>";
    }

    // Data rows
    for (var d = 0; d < 7; d++) {
      html += '<div class="heatmap-label">' + dayNames[d] + "</div>";
      for (var hr = 0; hr < 24; hr++) {
        var val = matrix[d + "-" + hr] || 0;
        var intensity = Math.ceil((val / maxVal) * 5);
        if (val === 0) intensity = 0;
        html +=
          '<div class="heatmap-cell" data-intensity="' + intensity + '" title="' +
          dayNames[d] + " " + (hr < 10 ? "0" : "") + hr + ":00 - " + val + ' messages"></div>';
      }
    }
    html += "</div>";
    container.innerHTML = html;
  }

  // KPI trend indicator
  function renderTrend(elId, current, previous, invertColor) {
    var el = document.getElementById(elId);
    if (!el || previous == null) return;
    if (!previous && !current) { el.textContent = ""; return; }
    if (!previous) { el.innerHTML = '<span class="trend-up">New</span>'; return; }
    var pct = ((current - previous) / previous * 100).toFixed(1);
    var isUp = pct >= 0;
    // For errors, up is bad (invert)
    var cls = invertColor ? (isUp ? "trend-down" : "trend-up") : (isUp ? "trend-up" : "trend-down");
    el.innerHTML = '<span class="' + cls + '">' + (isUp ? "\u25b2 +" : "\u25bc ") + pct + "% vs prev</span>";
  }

  // User Growth chart (new users bar + cumulative line)
  function renderUserGrowthChart(daily) {
    var canvas = document.getElementById("chart-user-growth");
    if (!canvas) return;
    if (chartUserGrowth) { chartUserGrowth.destroy(); chartUserGrowth = null; }

    var labels = daily.map(function (d) {
      return new Date(d.date).toLocaleDateString("en-US", { month: "short", day: "numeric" });
    });
    var newUsers = daily.map(function (d) { return d.new_users || 0; });
    var cumulative = [];
    var running = 0;
    newUsers.forEach(function (n) { running += n; cumulative.push(running); });

    var isDark = getTheme() === "dark";
    var gridColor = isDark ? "rgba(148,163,184,0.1)" : "rgba(15,23,42,0.06)";
    var textColor = isDark ? "#94A3B8" : "#64748B";

    chartUserGrowth = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          { label: "New Users", data: newUsers, backgroundColor: "rgba(139, 92, 246, 0.7)", borderRadius: 4, order: 2 },
          { label: "Cumulative", data: cumulative, type: "line", borderColor: "#8B5CF6",
            backgroundColor: "transparent", tension: 0.4, pointRadius: 2, order: 1 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "top", align: "end", labels: { color: textColor, usePointStyle: true, pointStyle: "circle", padding: 16, font: { family: "Prompt", size: 12 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { color: textColor, font: { family: "Prompt", size: 11 }, maxTicksLimit: 10 } },
          y: { grid: { color: gridColor }, ticks: { color: textColor, font: { family: "Prompt", size: 11 } }, beginAtZero: true },
        },
      },
    });
  }

  // Average Response Time trend line
  function renderRtTrendChart(daily) {
    var canvas = document.getElementById("chart-rt-trend");
    if (!canvas) return;
    if (chartRtTrend) { chartRtTrend.destroy(); chartRtTrend = null; }

    var labels = daily.map(function (d) {
      return new Date(d.date).toLocaleDateString("en-US", { month: "short", day: "numeric" });
    });
    var rtData = daily.map(function (d) { return d.avg_response_time || null; });

    var isDark = getTheme() === "dark";
    var gridColor = isDark ? "rgba(148,163,184,0.1)" : "rgba(15,23,42,0.06)";
    var textColor = isDark ? "#94A3B8" : "#64748B";

    chartRtTrend = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Avg Response (s)",
          data: rtData,
          borderColor: "#F59E0B",
          backgroundColor: "rgba(245, 158, 11, 0.08)",
          fill: true, tension: 0.4, pointRadius: 3,
          spanGaps: true,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "top", align: "end", labels: { color: textColor, usePointStyle: true, font: { family: "Prompt", size: 12 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { color: textColor, font: { family: "Prompt", size: 11 }, maxTicksLimit: 10 } },
          y: { beginAtZero: true, grid: { color: gridColor }, ticks: { color: textColor, font: { family: "Prompt", size: 11 }, callback: function (v) { return v + "s"; } } },
        },
      },
    });
  }

  // Sortable Top Chats Table
  var _topChatsSort = { col: "mc", dir: "desc" };

  function renderTopChatsTable() {
    var el = document.getElementById("top-chats-table");
    if (!el) return;

    var sorted = chats.slice().sort(function (a, b) {
      var aVal, bVal;
      switch (_topChatsSort.col) {
        case "name": aVal = (a.name || "").toLowerCase(); bVal = (b.name || "").toLowerCase(); break;
        case "last_active": aVal = a.last_active || ""; bVal = b.last_active || ""; break;
        default: aVal = a.mc || 0; bVal = b.mc || 0;
      }
      if (aVal < bVal) return _topChatsSort.dir === "asc" ? -1 : 1;
      if (aVal > bVal) return _topChatsSort.dir === "asc" ? 1 : -1;
      return 0;
    });
    var top = sorted.slice(0, 10);

    if (!top.length) {
      el.innerHTML = '<p style="padding:16px;color:var(--text-muted);font-size:13px">No data available</p>';
      return;
    }

    function sortIcon(col) {
      if (_topChatsSort.col !== col) return '<span class="sort-icon">\u2195</span>';
      return '<span class="sort-icon active">' + (_topChatsSort.dir === "asc" ? "\u25b2" : "\u25bc") + "</span>";
    }

    el.innerHTML =
      '<div style="overflow-x: auto; width: 100%;">' +
      '<table class="stats-table">' +
      "<thead><tr>" +
      '<th data-sort="name">Name ' + sortIcon("name") + "</th>" +
      "<th>Type</th>" +
      '<th data-sort="mc">Messages ' + sortIcon("mc") + "</th>" +
      '<th data-sort="last_active">Last Active ' + sortIcon("last_active") + "</th>" +
      "<th>Tags</th>" +
      "<th>Status</th>" +
      "</tr></thead><tbody>" +
      top.map(function (c) {
        var tagsPills = (c.tags || []).slice(0, 2).map(function (t) {
          var cls = t === "vip" ? " vip" : t === "complaint" ? " complaint" : t === "new" ? " new" : "";
          return '<span class="tag-pill small' + cls + '">' + esc(t) + "</span>";
        }).join("");
        return (
          "<tr>" +
          "<td>" + esc(c.name) + "</td>" +
          "<td><span class='type-badge'>" + typeLabel(c.type) + "</span></td>" +
          "<td>" + (c.mc || 0) + "</td>" +
          "<td>" + relTime(c.last_active) + "</td>" +
          "<td>" + (tagsPills || '<span style="color:var(--text-muted)">-</span>') + "</td>" +
          "<td>" +
          '<span class="status-dot ' + (c.disabled ? "offline" : "online") + '" style="vertical-align:middle"></span>' +
          (c.disabled ? "Off" : "Active") +
          "</td></tr>"
        );
      }).join("") +
      "</tbody></table></div>";

    // Sortable headers
    el.querySelectorAll("th[data-sort]").forEach(function (th) {
      th.addEventListener("click", function () {
        var col = this.getAttribute("data-sort");
        if (_topChatsSort.col === col) {
          _topChatsSort.dir = _topChatsSort.dir === "asc" ? "desc" : "asc";
        } else {
          _topChatsSort.col = col;
          _topChatsSort.dir = "desc";
        }
        renderTopChatsTable();
      });
    });
  }

  function exportAnalytics() {
    if (!_analyticsDaily.length) {
      toast(t("No data to export"));
      return;
    }

    var rows = ["Date,Messages In,Messages Out,Unique Users,New Users,Images,Avg Response Time"];
    _analyticsDaily.forEach(function (d) {
      rows.push(
        d.date + "," + (d.messages_in || 0) + "," + (d.messages_out || 0) + "," +
        (d.unique_users || 0) + "," + (d.new_users || 0) + "," + (d.images || 0) + "," +
        (d.avg_response_time || 0)
      );
    });
    downloadFile(rows.join("\n"), "analytics-" + analyticsRange + ".csv", "text/csv");
    toast(t("Analytics exported"));
  }

  // ============================================================
  // PAGE: SETTINGS
  // ============================================================

  function renderSettings(container) {
    container.innerHTML =
      '<div class="page" id="page-settings">' +
      '<div class="page-header">' +
      "<h1>" + t("Settings") + "</h1>" +
      "<p>" + t("Manage application preferences and LINE integrations") + "</p>" +
      "</div>" +
      // --- Tabs Header ---
      '<div class="settings-tabs">' +
      '<button class="settings-tab active" data-tab="tab-messaging"><i data-lucide="message-square"></i> ' + t("Messages & Tags") + '</button>' +
      '<button class="settings-tab" data-tab="tab-system"><i data-lucide="settings"></i> ' + t("System") + '</button>' +
      '</div>' +
      
      // --- TAB 1: Messaging & Tags ---
      '<div class="settings-tab-content active" id="tab-messaging">' +
      '<div class="settings-grid">' +
      // Quick Reply Templates
      '<div class="settings-section">' +
      '<div class="settings-section-title"><i data-lucide="file-text"></i> ' + t("Quick Reply Templates") + '</div>' +
      '<div id="template-list" class="template-list"></div>' +
      '<div style="margin-top:var(--sp-3)">' +
      '<div class="form-group"><label>Title</label><input type="text" class="form-input" id="tpl-title" placeholder="Template name"></div>' +
      '<div class="form-group"><label>Body</label><textarea class="form-textarea" id="tpl-body" placeholder="Template content..." style="min-height:60px"></textarea></div>' +
      '<button class="btn-primary" style="width:auto;padding:8px 20px;font-size:13px" id="btn-add-tpl">' + t("Add Template") + '</button>' +
      '<button class="btn-secondary" style="width:auto;padding:8px 20px;font-size:13px;display:none;margin-left:8px;" id="btn-cancel-tpl">' + t("Cancel") + '</button>' +
      "</div></div>" +
      // Tag Management
      '<div class="settings-section">' +
      '<div class="settings-section-title"><i data-lucide="tags"></i> ' + t("Tag Management") + '</div>' +
      '<div class="tag-list" id="tag-list"></div>' +
      '<div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-2)">' +
      '<input type="text" class="form-input" id="new-tag" placeholder="New tag name" style="flex:1">' +
      '<button class="btn-secondary btn-sm" id="btn-add-tag">Add</button>' +
      "</div></div>" +
      "</div></div>" + // End TAB 1

      // --- TAB 3: System ---
      '<div class="settings-tab-content" id="tab-system">' +
      '<div class="settings-grid">' +
      // Storage Info
      '<div class="settings-section">' +
      '<div class="settings-section-title"><i data-lucide="hard-drive"></i> ' + t("Storage Info") + '</div>' +
      '<div id="settings-storage"></div>' +
      "</div>" +
      // Dark Mode Toggle
      '<div class="settings-section">' +
      '<div class="settings-section-title"><i data-lucide="moon"></i> ' + t("Appearance") + '</div>' +
      '<div style="display:flex;align-items:center;justify-content:space-between">' +
      '<div><p style="font-size:14px;font-weight:600;color:var(--text-primary)">' + t("Dark Mode") + '</p>' +
      '<p style="font-size:12px;color:var(--text-muted)">' + t("Switch between light and dark themes") + '</p></div>' +
      '<label class="switch"><input type="checkbox" id="settings-theme-toggle"' +
      (getTheme() === "dark" ? " checked" : "") +
      '><span class="switch-track"><span class="switch-thumb"></span></span></label>' +
      "</div></div>" +
      // Danger Zone
      '<div class="settings-section danger-zone full-width">' +
      '<div class="settings-section-title"><i data-lucide="alert-triangle"></i> Danger Zone</div>' +
      '<p class="danger-desc">These actions are destructive and cannot be undone. Please proceed with caution.</p>' +
      '<button class="btn-danger" id="btn-clear-all">Clear All Chat History</button>' +
      "</div>" +
      "</div></div>" + // End TAB 3

      "</div>"; // End page-settings

    // Tab interaction logic
    container.querySelectorAll('.settings-tab').forEach(function(btn) {
      btn.addEventListener('click', function() {
        container.querySelectorAll('.settings-tab').forEach(function(t) { t.classList.remove('active'); });
        container.querySelectorAll('.settings-tab-content').forEach(function(c) { c.classList.remove('active'); });
        btn.classList.add('active');
        container.querySelector('#' + btn.getAttribute('data-tab')).classList.add('active');
      });
    });

    bindSettingsEvents();
    loadSettingsData();
  }

  function bindSettingsEvents() {
    // Add template
    var addTplBtn = document.getElementById("btn-add-tpl");
    var cancelTplBtn = document.getElementById("btn-cancel-tpl");
    if (addTplBtn) {
      addTplBtn.addEventListener("click", function () {
        var title = document.getElementById("tpl-title").value.trim();
        var body = document.getElementById("tpl-body").value.trim();
        if (!title || !body) { toast(t("Please fill in title and body")); return; }
        var editId = addTplBtn.getAttribute("data-edit-id");
        var op = editId ? "edit" : "add";
        var payload = { op: op, title: title, body: body };
        if (editId) payload.id = editId;
        
        addTplBtn.disabled = true;
        api("manage_templates", payload)
          .then(function (d) {
            addTplBtn.disabled = false;
            allTemplates = d.templates || [];
            renderTemplateList();
            document.getElementById("tpl-title").value = "";
            document.getElementById("tpl-body").value = "";
            addTplBtn.removeAttribute("data-edit-id");
            addTplBtn.textContent = t("Add Template");
            if(cancelTplBtn) cancelTplBtn.style.display = 'none';
            toast(editId ? t("Template updated") : t("Template added"));
          })
          .catch(function () { 
            addTplBtn.disabled = false;
            toast(editId ? t("Failed to update template") : t("Failed to add template")); 
          });
      });
    }
    if (cancelTplBtn) {
      cancelTplBtn.addEventListener("click", function () {
        document.getElementById("tpl-title").value = "";
        document.getElementById("tpl-body").value = "";
        addTplBtn.removeAttribute("data-edit-id");
        addTplBtn.textContent = t("Add Template");
        cancelTplBtn.style.display = 'none';
      });
    }

    // Add tag
    var addTagBtn = document.getElementById("btn-add-tag");
    var tagInput = document.getElementById("new-tag");
    if (addTagBtn) {
      addTagBtn.addEventListener("click", addTag);
    }
    if (tagInput) {
      tagInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") addTag();
      });
    }

    function addTag() {
      var tag = document.getElementById("new-tag").value.trim().toLowerCase();
      if (!tag) return;
      api("manage_tags", { op: "add", tag: tag })
        .then(function (d) {
          allTags = d.tags || [];
          renderTagList();
          document.getElementById("new-tag").value = "";
          toast(t("Tag added"));
        })
        .catch(function () { toast(t("Failed to add tag")); });
    }

    // Theme toggle in settings
    var themeToggle = document.getElementById("settings-theme-toggle");
    if (themeToggle) {
      themeToggle.addEventListener("change", function () {
        setTheme(this.checked ? "dark" : "light");
        toast(t("Theme updated"));
      });
    }

    // Clear all history
    var clearAllBtn = document.getElementById("btn-clear-all");
    if (clearAllBtn) {
      clearAllBtn.addEventListener("click", function () {
        modal(
          "Clear All History",
          "<p>This will <strong>permanently delete</strong> all chat history across every conversation. This action cannot be undone.</p>",
          function () {
            api("clear_all_chats")
              .then(function () {
                chats = [];
                toast(t("All history cleared"));
                navigate("inbox");
              })
              .catch(function () { toast(t("Failed to clear history")); });
          }
        );
      });
    }
  }

  function loadSettingsData() {
    // Templates
    api("manage_templates", { op: "list" })
      .then(function (d) {
        allTemplates = d.templates || [];
        renderTemplateList();
      })
      .catch(function () {});

    // Tags
    api("manage_tags", { op: "list" })
      .then(function (d) {
        allTags = d.tags || [];
        renderTagList();
      })
      .catch(function () {});

    // Storage
    api("get_storage_info")
      .then(function (d) {
        var el = document.getElementById("settings-storage");
        if (el) {
          el.innerHTML =
            '<div class="status-row"><span class="status-label">Media Files</span><span class="status-value">' + (d.media_count || 0) + "</span></div>" +
            '<div class="status-row"><span class="status-label">Storage Used</span><span class="status-value">' + (d.media_size_mb || 0).toFixed(1) + " MB</span></div>" +
            '<div class="status-row"><span class="status-label">Chat Records</span><span class="status-value">' + (d.chat_count || 0) + "</span></div>" +
            '<div class="progress-bar" style="margin-top:8px"><div class="progress-fill" style="width:' + Math.min(((d.media_size_mb || 0) / 100) * 100, 100).toFixed(1) + '%"></div></div>';
        }
      })
      .catch(function () {});
  }

  function renderTemplateList() {
    var el = document.getElementById("template-list");
    if (!el) return;

    if (!allTemplates.length) {
      el.innerHTML = '<p style="font-size:13px;color:var(--text-muted);padding:8px 0">No templates yet. Add one below.</p>';
      return;
    }

    el.innerHTML = allTemplates
      .map(function (t) {
        return (
          '<div class="template-item">' +
          '<div class="template-item-body">' +
          '<div class="template-item-title">' + esc(t.title) + "</div>" +
          '<div class="template-item-preview">' + esc(t.body) + "</div>" +
          "</div>" +
          '<div class="template-item-actions">' +
          '<button class="btn-icon" style="width:30px;height:30px;margin-right:4px;" data-edit-tpl="' + esc(t.id) + '" title="Edit"><i data-lucide="edit-3" style="width:14px;height:14px;color:var(--text-muted)"></i></button>' +
          '<button class="btn-icon" style="width:30px;height:30px" data-delete-tpl="' + esc(t.id) + '" title="Delete"><i data-lucide="trash-2" style="width:14px;height:14px;color:var(--danger)"></i></button>' +
          "</div></div>"
        );
      })
      .join("");

    // Delete handlers
    el.querySelectorAll("[data-delete-tpl]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = this.getAttribute("data-delete-tpl");
        if(!confirm("Are you sure you want to delete this template?")) return;
        api("manage_templates", { op: "delete", id: id })
          .then(function (d) {
            allTemplates = d.templates || [];
            renderTemplateList();
            toast(t("Template deleted"));
            var addTplBtn = document.getElementById("btn-add-tpl");
            if (addTplBtn && addTplBtn.getAttribute("data-edit-id") === id) {
               document.getElementById("btn-cancel-tpl").click();
            }
          })
          .catch(function () { toast(t("Failed to delete")); });
      });
    });

    // Edit handlers
    el.querySelectorAll("[data-edit-tpl]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = this.getAttribute("data-edit-tpl");
        var tpl = allTemplates.find(function(t) { return t.id === id; });
        if (tpl) {
          document.getElementById("tpl-title").value = tpl.title || '';
          document.getElementById("tpl-body").value = tpl.body || '';
          var addTplBtn = document.getElementById("btn-add-tpl");
          var cancelTplBtn = document.getElementById("btn-cancel-tpl");
          if (addTplBtn) {
            addTplBtn.setAttribute("data-edit-id", id);
            addTplBtn.textContent = t("Save Changes");
          }
          if (cancelTplBtn) {
            cancelTplBtn.style.display = 'inline-block';
          }
          document.getElementById("tpl-title").focus();
        }
      });
    });

    try { lucide.createIcons(); } catch (e) {}
  }

  function renderTagList() {
    var el = document.getElementById("tag-list");
    if (!el) return;

    if (!allTags.length) {
      el.innerHTML = '<p style="font-size:13px;color:var(--text-muted)">No tags defined yet.</p>';
      return;
    }

    el.innerHTML = allTags
      .map(function (tag) {
        return (
          '<div class="tag-item">' + esc(tag) +
          '<button class="tag-remove" data-remove-tag="' + esc(tag) + '"><i data-lucide="x"></i></button>' +
          "</div>"
        );
      })
      .join("");

    // Remove handlers
    el.querySelectorAll("[data-remove-tag]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var tag = this.getAttribute("data-remove-tag");
        
        var inUseCount = chats.filter(function(c) {
          return c.tags && c.tags.includes(tag);
        }).length;

        var doRemove = function() {
          api("manage_tags", { op: "remove", tag: tag })
            .then(function (d) {
              allTags = d.tags || [];
              renderTagList();
              toast(t("Tag removed"));
            })
            .catch(function () { toast(t("Failed to remove tag")); });
        };

        if (inUseCount > 0) {
          modal(
            "Tag is in use",
            "This tag is currently assigned to <b>" + inUseCount + "</b> conversation(s).<br><br>Deleting this tag will also remove it from all assigned chats. Are you sure you want to proceed?",
            doRemove
          );
        } else {
          doRemove();
        }
      });
    });

    try { lucide.createIcons(); } catch (e) {}
  }

  // ============================================================
  // INIT
  // ============================================================

  // Try auto-login with stored token
  api("list_chats")
    .then(function (d) {
      chats = d.chats || [];
      hideLogin();
      initApp();
    })
    .catch(function () {
      showLogin();
    });

  // Initialize Lucide icons
  try { lucide.createIcons(); } catch (e) {}
})();
