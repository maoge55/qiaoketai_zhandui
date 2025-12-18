// 简单封装：获取 JWT
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;
function getToken() {
  return localStorage.getItem("qk_token") || getCookie("access_token") || "";
}

function setToken(token, role, nickname) {
  // 本地存储：浏览器不删就一直在
  localStorage.setItem("qk_token", token);

  // 显式设定 cookie 有效期为 1 年
  document.cookie = `access_token=${token};path=/;max-age=${ONE_YEAR_SECONDS}`;
  if (role) {
    document.cookie = `user_role=${role};path=/;max-age=${ONE_YEAR_SECONDS}`;
  }
  if (nickname) {
    document.cookie = `user_nickname=${nickname};path=/;max-age=${ONE_YEAR_SECONDS}`;
  }
}

function clearAuth() {
  localStorage.removeItem("qk_token");
  document.cookie = "access_token=;path=/;max-age=0";
  document.cookie = "user_role=;path=/;max-age=0";
  document.cookie = "user_nickname=;path=/;max-age=0";
}

function getCookie(name) {
  const match = document.cookie.match(
    new RegExp("(^| )" + name + "=([^;]+)")
  );
  if (match) return match[2];
  return "";
}

// 防止 XSS：把用户输入当作纯文本渲染
function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function nl2br(text) {
  return escapeHtml(text).replace(/\n/g, "<br>");
}

// 贴吧表情（最小集）：用 SVG data URL 作为 <img>，避免新增静态资源
const TIEBA_EMOTES = {
  "[滑稽]": "😆",
  "[捂脸]": "🤦",
  "[点赞]": "👍",
  "[生气]": "😠",
  "[泪目]": "🥹",
};

function emoteToImgTag(emojiChar, alt) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22"><text x="50%" y="58%" text-anchor="middle" font-size="18">${emojiChar}</text></svg>`;
  const src = "data:image/svg+xml;utf8," + encodeURIComponent(svg);
  return `<img class="qk-emote" src="${src}" alt="${escapeHtml(alt)}" />`;
}

function renderCommentRichText(text) {
  let html = escapeHtml(text || "");
  Object.keys(TIEBA_EMOTES).forEach((code) => {
    const emojiChar = TIEBA_EMOTES[code];
    // code 里有 []，需要转义
    const re = new RegExp(code.replace(/[\[\]]/g, "\\$&"), "g");
    html = html.replace(re, emoteToImgTag(emojiChar, code));
  });
  return html.replace(/\n/g, "<br>");
}

function insertAtCursor(textarea, text) {
  const start = textarea.selectionStart || 0;
  const end = textarea.selectionEnd || 0;
  const v = textarea.value || "";
  textarea.value = v.slice(0, start) + text + v.slice(end);
  const nextPos = start + text.length;
  textarea.selectionStart = textarea.selectionEnd = nextPos;
  textarea.focus();
}

function initCommentComposer() {
  const textarea = document.getElementById("comment-content");
  const btnEmoji = document.getElementById("btn-emoji");
  const btnTieba = document.getElementById("btn-tieba");
  if (!textarea || (!btnEmoji && !btnTieba)) return;

  const host = textarea.closest(".comment-form") || textarea.parentElement;
  if (!host) return;
  host.style.position = "relative";

  let panel = null;

  function closePanel() {
    if (panel) {
      panel.remove();
      panel = null;
    }
  }

  function openPanel(type) {
    closePanel();
    panel = document.createElement("div");
    panel.className = "qk-emote-panel";
    panel.dataset.type = type;
    panel.style.cssText = "position:absolute; left:0; right:0; bottom:58px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 14px; padding: 10px; display:flex; flex-wrap:wrap; gap:8px; z-index: 50;";

    if (type === "emoji") {
      const emojis = ["😊", "😂", "😍", "🤔", "😎", "🔥", "✨", "🎉", "👍", "👎", "🥹", "😠"]; 
      emojis.forEach((e) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "qk-emote-btn";
        b.textContent = e;
        b.addEventListener("click", () => {
          insertAtCursor(textarea, e);
          closePanel();
        });
        panel.appendChild(b);
      });
    } else {
      Object.keys(TIEBA_EMOTES).forEach((code) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "qk-emote-btn";
        b.innerHTML = `${emoteToImgTag(TIEBA_EMOTES[code], code)} <span class="qk-emote-code">${escapeHtml(code)}</span>`;
        b.addEventListener("click", () => {
          insertAtCursor(textarea, code);
          closePanel();
        });
        panel.appendChild(b);
      });
    }

    host.appendChild(panel);
  }

  if (btnEmoji) {
    btnEmoji.addEventListener("click", (e) => {
      e.preventDefault();
      if (panel && panel.dataset.type === "emoji") closePanel();
      else openPanel("emoji");
    });
  }
  if (btnTieba) {
    btnTieba.addEventListener("click", (e) => {
      e.preventDefault();
      if (panel && panel.dataset.type === "tieba") closePanel();
      else openPanel("tieba");
    });
  }

  document.addEventListener("click", (e) => {
    if (!panel) return;
    if (panel.contains(e.target)) return;
    if (btnEmoji && btnEmoji.contains(e.target)) return;
    if (btnTieba && btnTieba.contains(e.target)) return;
    closePanel();
  });
}

// 影响力 +1 动画
function showInfluenceToast(points = 1, prefix = "作者影响力") {
  const toast = document.createElement("div");
  toast.className = "influence-toast";
  toast.innerHTML = `${prefix} +${points}`;
  document.body.appendChild(toast);

  // 强制重绘
  toast.offsetHeight;

  toast.classList.add("show");

  setTimeout(() => {
    toast.remove();
  }, 2000);
}

// 退出登录
document.addEventListener("click", (e) => {
  if (e.target.id === "btn-logout") {
    e.preventDefault();
    // 告诉后端清除 HttpOnly 的 access_token cookie，然后在前端清除可访问的 cookie/localStorage
    (async () => {
      try {
        await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
      } catch (err) {
        // 忽略网络错误，仍然清除前端状态
      }
      clearAuth();
      window.location.href = "/";
    })();
  }
});

// 登录表单
document.addEventListener("submit", async (e) => {
  if (e.target.id === "login-form") {
    e.preventDefault();
    const form = e.target;
    const usernameOrEmail = form.username_or_email.value.trim();
    const password = form.password.value;
    if (!usernameOrEmail || !password) return alert("请输入账号和密码");

    // 按要求：前端按「用户名前三位 + 密码」做 md5
    // 注意：如果用户输入的是邮箱，需要先向后端请求真实 username 再取前三位
    let prefix = usernameOrEmail.slice(0, 3);
    let usernameForPrefix = usernameOrEmail;
    if (usernameOrEmail.includes('@')) {
      try {
        const r = await fetch('/api/auth/resolve_username', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email_or_username: usernameOrEmail }),
        });
        if (r.ok) {
          const d = await r.json();
          usernameForPrefix = d.username || usernameOrEmail;
        } else {
          const err = await r.json().catch(() => ({}));
          return alert(err.detail || '用户不存在');
        }
      } catch (err) {
        return alert('无法获取用户名');
      }
      prefix = usernameForPrefix.slice(0, 3);
    }

    const md5Input = prefix + password;
    const password_md5 = md5(md5Input);

    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username_or_email: usernameOrEmail,
        password_md5,
      }),
    });
    const data = await res.json();
    if (!res.ok) return alert(data.detail || "登录失败");

    setToken(data.access_token, getCookie("user_role"), getCookie("user_nickname"));
    window.location.href = "/";
  }
});

// 注册表单
document.addEventListener("submit", async (e) => {
  if (e.target.id === "register-form") {
    e.preventDefault();
    const f = e.target;
    const username = f.username.value.trim();
    const nickname = f.nickname.value.trim();
    const email = f.email.value.trim();
    const password = f.password.value;
    const code = f.verification_code.value.trim();
    const membership_code = f.membership_code.value.trim();

    if (!username || !nickname || !email || !password || !code) {
      return alert("请完整填写信息");
    }

    if (username.length < 3) {
      return alert("用户名至少需要3个字符");
    }

    // 登录密码加密规则：用户名前三位 + 密码，然后 md5
    const prefix = username.slice(0, 3);
    const password_md5 = md5(prefix + password);

    // 会员码只做一次 md5，不在传输中明文出现
    let membership_code_md5 = null;
    if (membership_code) {
      membership_code_md5 = md5(membership_code);
    }

    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        nickname,
        email,
        password_md5,
        verification_code: code,
        membership_code_md5: membership_code_md5,
      }),
    });
    const data = await res.json();
    if (!res.ok) return alert(data.detail || "注册失败");
    alert("注册成功，请登录");
    window.location.href = "/login";
  }
});

// 发送验证码按钮
document.addEventListener("click", async (e) => {
  if (e.target.id === "btn-send-code") {
    e.preventDefault();
    const email = document.getElementById("email-input").value.trim();
    if (!email) return alert("请输入邮箱");

    const res = await fetch("/api/auth/send_verification_code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) return alert(data.detail || "发送失败");
    alert("验证码已发送，请检查邮箱");
  }
});

// 评论提交
document.addEventListener("click", async (e) => {
  if (e.target.id === "btn-comment-submit") {
    const articleId = e.target.dataset.articleId;
    const content = document
      .getElementById("comment-content")
      .value.trim();
    if (!content) return alert("请输入评论内容");

    const res = await fetch(`/api/articles/${articleId}/comments`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content }),
      credentials: "same-origin",
    });
    const data = await res.json();
    if (!res.ok) return alert(data.detail || "评论失败");
    // 不刷新页面，直接重载评论区
    document.getElementById("comment-content").value = "";
    loadComments();
  }
});


// ===== 战队名册：分页加载 =====

function buildMemberCard(profile) {
  const nickname =
    (profile.user && profile.user.nickname) || "未知成员";
  const avatarUrl = profile.avatar_url || "";
  const age =
    typeof profile.age === "number" ? profile.age : "-";
  const gender = profile.gender || "-";
  const tags = profile.other_tags || "竞技场爱好者";
  const bioRaw = (profile.bio || "").trim();
  const bioText = bioRaw || "这个人还没有写简介～";
  const influence =
    typeof profile.influence === "number" ? profile.influence : 1;
  const rank =
    typeof profile.current_season_rank === "number"
      ? profile.current_season_rank
      : null;
  const seasonScore =
    typeof profile.current_season_score === "number"
      ? profile.current_season_score
      : null;
  const bestScore =
    typeof profile.best_season_score === "number"
      ? profile.best_season_score
      : null;
  const bestRank = profile.arena_best_rank || null;

  const card = document.createElement("div");
  card.className = "card member-card member-card-animated";

  card.innerHTML = `
    <a href="/members/${profile.user_id}" class="member-card-link">
      <div class="member-card-avatar" style="${avatarUrl ? `background-image:url('${avatarUrl}')` : ""}"></div>
      <div class="member-card-info">
        <div class="member-card-top">
          <h3 class="member-card-name">${escapeHtml(nickname)}</h3>
          ${
            rank
              ? `<span class="member-card-rank">当前赛季第 ${rank} 名</span>`
              : ""
          }
        </div>
        <p class="member-card-meta">
          ${seasonScore ? `当前分数：${seasonScore}` : ""}${seasonScore && bestScore ? " ｜ " : ""}${bestScore ? `本赛季最高分：${bestScore}` : ""}${(seasonScore || bestScore) && bestRank ? " ｜ " : ""}${bestRank ? `本赛季高排名：${escapeHtml(bestRank)}` : (!(seasonScore || bestScore) ? `年龄：${age} ｜ 性别：${gender}` : "")}
        </p>
        <p class="member-card-tags">${escapeHtml(tags)}</p>
        <p class="member-card-bio">${escapeHtml(bioText)}</p>
      </div>
      <div class="member-card-stats">
        <div class="stat-item">
          <span class="stat-value">${influence}</span>
          <span class="stat-label">影响力</span>
        </div>
      </div>
    </a>
  `;

  return card;
}

// ===== 战队名册分页模式 =====
let membersCurrentPage = 1;
let membersTotalPages = 1;
const membersPageSizeNew = 12;

async function loadMembersPageData(page) {
  const grid = document.getElementById("members-grid");
  const loadingEl = document.getElementById("members-loading");
  const emptyEl = document.getElementById("members-empty");
  const paginationEl = document.getElementById("members-pagination");

  if (!grid) return;

  if (loadingEl) loadingEl.style.display = "block";
  if (emptyEl) emptyEl.style.display = "none";
  grid.innerHTML = "";

  try {
    const res = await fetch(
      `/api/members?page=${page}&page_size=${membersPageSizeNew}`
    );
    const data = await res.json();

    if (!res.ok) {
      console.error("加载成员失败：", data);
      return;
    }

    const items = data.items || [];
    const total = data.total || 0;
    membersTotalPages = Math.ceil(total / membersPageSizeNew) || 1;
    membersCurrentPage = page;

    if (items.length > 0) {
      items.forEach((p) => {
        grid.appendChild(buildMemberCard(p));
      });
      if (paginationEl) paginationEl.style.display = "flex";
      updateMembersPagination();
    } else {
      if (emptyEl) emptyEl.style.display = "block";
      if (paginationEl) paginationEl.style.display = "none";
    }
  } catch (err) {
    console.error("加载成员出错：", err);
  } finally {
    if (loadingEl) loadingEl.style.display = "none";
  }
}

function updateMembersPagination() {
  const pageNumbers = document.getElementById("members-page-numbers");
  const pageInfo = document.getElementById("members-page-info");
  const prevBtn = document.getElementById("members-prev");
  const nextBtn = document.getElementById("members-next");

  if (pageInfo) {
    pageInfo.textContent = `第 ${membersCurrentPage} / ${membersTotalPages} 页`;
  }

  if (prevBtn) {
    prevBtn.disabled = membersCurrentPage <= 1;
  }
  if (nextBtn) {
    nextBtn.disabled = membersCurrentPage >= membersTotalPages;
  }

  if (pageNumbers) {
    pageNumbers.innerHTML = "";
    
    // 计算显示的页码范围（最多显示5个）
    let startPage = Math.max(1, membersCurrentPage - 2);
    let endPage = Math.min(membersTotalPages, startPage + 4);
    
    // 调整起始页，确保显示5个（如果有足够页数）
    if (endPage - startPage < 4) {
      startPage = Math.max(1, endPage - 4);
    }

    for (let i = startPage; i <= endPage; i++) {
      const btn = document.createElement("button");
      btn.className = "pagination-num" + (i === membersCurrentPage ? " active" : "");
      btn.textContent = i;
      btn.addEventListener("click", () => {
        if (i !== membersCurrentPage) {
          loadMembersPageData(i);
        }
      });
      pageNumbers.appendChild(btn);
    }
  }
}

function initMembersPage() {
  const grid = document.getElementById("members-grid");
  if (!grid) return; // 不在战队名册页面

  const prevBtn = document.getElementById("members-prev");
  const nextBtn = document.getElementById("members-next");
  const jumpBtn = document.getElementById("members-jump-btn");
  const jumpInput = document.getElementById("members-jump-input");

  // 首次加载
  loadMembersPageData(1);

  // 上一页
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (membersCurrentPage > 1) {
        loadMembersPageData(membersCurrentPage - 1);
      }
    });
  }

  // 下一页
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (membersCurrentPage < membersTotalPages) {
        loadMembersPageData(membersCurrentPage + 1);
      }
    });
  }

  // 跳转
  if (jumpBtn && jumpInput) {
    const doJump = () => {
      const targetPage = parseInt(jumpInput.value, 10);
      if (targetPage >= 1 && targetPage <= membersTotalPages) {
        loadMembersPageData(targetPage);
        jumpInput.value = "";
      } else {
        alert(`请输入 1 到 ${membersTotalPages} 之间的页码`);
      }
    };

    jumpBtn.addEventListener("click", doJump);
    jumpInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        doJump();
      }
    });
  }
}


// ===== 攻略列表：筛选 + 分页 UI（异步加载） =====
function initGuidesPage() {
  const listEl = document.getElementById("guides-list");
  if (!listEl) return; // 不在攻略列表页

  const searchInput = document.getElementById("guide-search");
  const categoryInput = document.getElementById("guide-category");
  const tagInput = document.getElementById("guide-tag");
  const btnFilter = document.getElementById("btn-guide-filter");
  const btnReset = document.getElementById("btn-guide-reset");
  const btnPrev = document.getElementById("guides-prev");
  const btnNext = document.getElementById("guides-next");
  const pageInfo = document.getElementById("guides-page-info");

  let page = 1;
  const pageSize = 10;
  let total = 0;

  function readUrlState() {
    const url = new URL(window.location.href);
    const p = Number(url.searchParams.get("page") || "1");
    page = Number.isFinite(p) && p > 0 ? p : 1;
    const s = url.searchParams.get("search") || "";
    const c = url.searchParams.get("category") || "";
    const t = url.searchParams.get("tag") || "";
    if (searchInput) searchInput.value = s;
    if (categoryInput) categoryInput.value = c;
    if (tagInput) tagInput.value = t;
  }

  function writeUrlState() {
    const url = new URL(window.location.href);
    url.searchParams.set("page", String(page));
    if (searchInput && searchInput.value.trim()) url.searchParams.set("search", searchInput.value.trim());
    else url.searchParams.delete("search");
    if (categoryInput && categoryInput.value.trim()) url.searchParams.set("category", categoryInput.value.trim());
    else url.searchParams.delete("category");
    if (tagInput && tagInput.value.trim()) url.searchParams.set("tag", tagInput.value.trim());
    else url.searchParams.delete("tag");
    window.history.replaceState({}, "", url.toString());
  }

  // 获取当前用户角色（用于判断是否显示管理按钮）
  const ctx = window.QK_GUIDES_CTX || {};
  const isAdmin = ctx.currentUser && ["admin", "super_admin"].includes(ctx.currentUser.role);

  function render(items) {
    listEl.innerHTML = "";
    if (!items || items.length === 0) {
      listEl.innerHTML = `<div class="card"><p class="meta">没有找到符合条件的攻略～</p></div>`;
      return;
    }

    items.forEach((a) => {
      const tags = Array.isArray(a.tags) ? a.tags : [];
      const tagHtml = tags
        .map((t) => `<button type="button" class="guide-tag-chip" data-tag="${escapeHtml(t)}">#${escapeHtml(t)}</button>`)
        .join(" ");

      const created = a.created_at ? new Date(a.created_at).toLocaleDateString() : "";

      const up = Number(a.upvote_count || 0);
      const down = Number(a.downvote_count || 0);
      const currentAction = a.current_user_action || "";
      const isPinned = !!a.is_pinned;

      // 置顶标志
      const pinnedBadge = isPinned ? `<span class="guide-pinned-badge">📌 置顶</span>` : "";
      
      // 管理员置顶按钮
      const pinBtn = isAdmin
        ? `<button type="button" class="qk-btn qk-btn-outline qk-btn-sm btn-pin-guide" data-guide-id="${a.id}" data-is-pinned="${isPinned}">${isPinned ? "取消置顶" : "置顶"}</button>`
        : "";

      const card = document.createElement("div");
      card.className = "card guide-card" + (isPinned ? " is-pinned" : "");
      card.innerHTML = `
        <div class="guide-card-head">
          <div class="guide-title-row">
            ${pinnedBadge}
            <a class="guide-title" href="/guides/${a.id}">${escapeHtml(a.title)}</a>
          </div>
          <div class="meta">作者：${escapeHtml(a.author_nickname || "未知")} · ${created}</div>
        </div>
        <div class="guide-excerpt"></div>
        <div class="guide-item-actions">
          <div class="qk-vote qk-guide-vote" data-guide-id="${a.id}" data-current-action="${escapeHtml(currentAction)}">
            <button class="qk-vote-btn ${currentAction === "up" ? "is-active" : ""}" type="button" data-action="up" aria-label="点赞">
              👍 <span class="qk-vote-count" data-role="up-count">${up}</span>
            </button>
            <button class="qk-vote-btn ${currentAction === "down" ? "is-active" : ""}" type="button" data-action="down" aria-label="拉踩">
              👎 <span class="qk-vote-count" data-role="down-count">${down}</span>
            </button>
          </div>
          ${pinBtn}
        </div>
        ${tagHtml ? `<div class="guide-tags">${tagHtml}</div>` : ""}
      `;
      const excerptEl = card.querySelector(".guide-excerpt");
      // 后端已对内容做 sanitize，这里直接渲染 HTML 以保留格式。
      excerptEl.innerHTML = a.excerpt || "";
      listEl.appendChild(card);
    });
  }

  function updatePager() {
    const pages = Math.max(1, Math.ceil((total || 0) / pageSize));
    if (pageInfo) pageInfo.textContent = `第 ${page} / ${pages} 页 · 共 ${total} 篇`;
    if (btnPrev) btnPrev.disabled = page <= 1;
    if (btnNext) btnNext.disabled = page >= pages;
  }

  async function load() {
    writeUrlState();
    listEl.innerHTML = `<div class="card"><p class="meta">加载中...</p></div>`;

    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    const s = searchInput ? searchInput.value.trim() : "";
    const c = categoryInput ? categoryInput.value.trim() : "";
    const t = tagInput ? tagInput.value.trim() : "";
    if (s) params.set("search", s);
    if (c) params.set("category", c);
    if (t) params.set("tag", t);

    const res = await fetch(`/api/articles/paged?${params.toString()}`, { credentials: "same-origin" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      listEl.innerHTML = `<div class="card"><p class="meta">加载失败：${escapeHtml(data.detail || "请稍后再试")}</p></div>`;
      return;
    }
    total = data.total || 0;
    render(data.items || []);
    updatePager();
  }

  // 初始
  readUrlState();
  load();

  // 操作
  if (btnFilter) {
    btnFilter.addEventListener("click", () => {
      page = 1;
      load();
    });
  }
  if (btnReset) {
    btnReset.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      if (categoryInput) categoryInput.value = "";
      if (tagInput) tagInput.value = "";
      page = 1;
      load();
    });
  }

  [searchInput, categoryInput, tagInput].forEach((el) => {
    if (!el) return;
    el.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        page = 1;
        load();
      }
    });
  });

  if (btnPrev) {
    btnPrev.addEventListener("click", () => {
      if (page > 1) page -= 1;
      load();
    });
  }
  if (btnNext) {
    btnNext.addEventListener("click", () => {
      page += 1;
      load();
    });
  }

  // 点击 tag chip 直接筛选
  listEl.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".guide-tag-chip");
    if (!btn) return;
    const t = btn.dataset.tag || "";
    if (tagInput) tagInput.value = t;
    page = 1;
    load();
  });

  // 攻略列表投票（乐观更新）
  listEl.addEventListener("click", async (ev) => {
    const btn = ev.target.closest(".qk-guide-vote .qk-vote-btn");
    if (!btn) return;
    ev.preventDefault();

    const root = btn.closest(".qk-guide-vote");
    const guideId = root.dataset.guideId;
    const action = btn.dataset.action;
    const upEl = root.querySelector('[data-role="up-count"]');
    const downEl = root.querySelector('[data-role="down-count"]');

    const prevAction = root.dataset.currentAction || "";
    const prevUp = Number(upEl.textContent || "0");
    const prevDown = Number(downEl.textContent || "0");

    let nextAction = prevAction;
    let nextUp = prevUp;
    let nextDown = prevDown;
    if (prevAction === action) {
      nextAction = "";
      if (action === "up") nextUp = Math.max(0, prevUp - 1);
      else nextDown = Math.max(0, prevDown - 1);
    } else {
      if (prevAction === "up") nextUp = Math.max(0, prevUp - 1);
      if (prevAction === "down") nextDown = Math.max(0, prevDown - 1);
      if (action === "up") nextUp += 1;
      else nextDown += 1;
      nextAction = action;
    }

    // optimistic
    root.dataset.currentAction = nextAction;
    upEl.textContent = String(nextUp);
    downEl.textContent = String(nextDown);
    root.querySelector('[data-action="up"]').classList.toggle("is-active", nextAction === "up");
    root.querySelector('[data-action="down"]').classList.toggle("is-active", nextAction === "down");

    try {
      const res = await fetch(`/api/guides/${guideId}/vote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
        credentials: "same-origin",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "投票失败");

      root.dataset.currentAction = data.current_action || "";
      upEl.textContent = String(data.upvote_count ?? 0);
      downEl.textContent = String(data.downvote_count ?? 0);
      root.querySelector('[data-action="up"]').classList.toggle("is-active", data.current_action === "up");
      root.querySelector('[data-action="down"]').classList.toggle("is-active", data.current_action === "down");

      if (data.influence_changed && data.influence_changed > 0) {
        showInfluenceToast(data.influence_changed);
      }
    } catch (err) {
      // rollback
      root.dataset.currentAction = prevAction;
      upEl.textContent = String(prevUp);
      downEl.textContent = String(prevDown);
      root.querySelector('[data-action="up"]').classList.toggle("is-active", prevAction === "up");
      root.querySelector('[data-action="down"]').classList.toggle("is-active", prevAction === "down");
      alert(err.message || "投票失败");
    }
  });

  // 管理员置顶按钮点击
  listEl.addEventListener("click", async (ev) => {
    const btn = ev.target.closest(".btn-pin-guide");
    if (!btn) return;
    ev.preventDefault();

    const guideId = btn.dataset.guideId;
    const wasPinned = btn.dataset.isPinned === "true";

    btn.disabled = true;
    btn.textContent = "处理中...";

    try {
      const res = await fetch(`/api/articles/${guideId}/pin`, {
        method: "POST",
        credentials: "same-origin",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "操作失败");

      // 刷新列表
      load();
    } catch (err) {
      alert(err.message || "操作失败");
      btn.disabled = false;
      btn.textContent = wasPinned ? "取消置顶" : "置顶";
    }
  });
}


// 加载文章评论
async function loadComments() {
  if (!window.QK_CURRENT_ARTICLE_ID) return;
  const res = await fetch(
    `/api/articles/${window.QK_CURRENT_ARTICLE_ID}/comments`
  );
  const data = await res.json();
  const container = document.getElementById("comments-list");
  if (!Array.isArray(data) || !container) return;

  const ctx = window.QK_COMMENT_CTX || {};
  const currentUser = ctx.currentUser || null;
  const articleAuthorId = ctx.articleAuthorId || null;

  function canDelete(c) {
    if (!currentUser) return false;
    return (
      currentUser.role === "admin" ||
      currentUser.id === c.user_id ||
      (articleAuthorId && currentUser.id === articleAuthorId)
    );
  }

  function canPin(c) {
    if (!currentUser) return false;
    if (c.parent_id) return false; // 仅一级评论可置顶
    return currentUser.role === "admin" || (articleAuthorId && currentUser.id === articleAuthorId);
  }

  // 楼中楼（一级 + 回复缩进）
  const byParent = {};
  data.forEach((c) => {
    const pid = c.parent_id || 0;
    byParent[pid] = byParent[pid] || [];
    byParent[pid].push(c);
  });

  // 回复按时间排序（一级评论顺序使用后端排序：置顶优先）
  Object.keys(byParent).forEach((pid) => {
    if (pid !== "0") {
      byParent[pid].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );
    }
  });

  function renderList(parentId, indent) {
    (byParent[parentId] || []).forEach((c) => {
      const div = document.createElement("div");
      div.className = "comment-item";
      div.id = `comment-${c.id}`;
      div.style.marginLeft = indent + "px";

      const pinnedBadge = c.is_pinned && !c.parent_id ? `<span class="comment-pin-badge">置顶</span>` : "";

      const actions = [];
      actions.push(
        `<button class="qk-btn qk-btn-outline btn-reply" data-id="${c.id}">回复</button>`
      );
      if (canDelete(c)) {
        actions.push(
          `<button class="qk-btn qk-btn-outline btn-comment-delete" data-id="${c.id}">删除</button>`
        );
      }
      if (canPin(c)) {
        actions.push(
          `<button class="qk-btn qk-btn-outline btn-comment-pin" data-id="${c.id}" data-next="${c.is_pinned ? 0 : 1}">${c.is_pinned ? "取消置顶" : "置顶"}</button>`
        );
      }

      div.innerHTML = `
        <div class="meta">
          ${pinnedBadge}
          <span>${escapeHtml(c.user_nickname)}</span>
          <span>${new Date(c.created_at).toLocaleString()}</span>
        </div>
        <div class="content">${renderCommentRichText(c.content)}</div>
        <div class="comment-actions">${actions.join(" ")}</div>
      `;
      container.appendChild(div);
      renderList(c.id, indent + 20);
    });
  }
  container.innerHTML = "";
  renderList(0, 0);

  // 跳转定位高亮：/guides/{id}?comment_id=123
  const url = new URL(window.location.href);
  const targetId = url.searchParams.get("comment_id");
  if (targetId) {
    const el = document.getElementById(`comment-${targetId}`);
    if (el) {
      el.classList.add("comment-highlight");
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => el.classList.remove("comment-highlight"), 2500);
    }
  }
}

document.addEventListener("click", async (e) => {
  // 回复
  if (e.target.classList.contains("btn-reply")) {
    const parentId = e.target.dataset.id;
    const content = prompt("请输入回复内容：");
    if (!content) return;
    const res = await fetch(`/api/comments/${parentId}/reply`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content }),
      credentials: "same-origin",
    });
    const data = await res.json();
    if (!res.ok) return alert(data.detail || "回复失败");
    
    // 评论成功不加影响力，或者你可以加
    loadComments();
    return;
  }

  // 删除评论
  if (e.target.classList.contains("btn-comment-delete")) {
    const id = e.target.dataset.id;
    if (!confirm("确定要删除这条评论吗？（会同时删除其回复）")) return;
    const res = await fetch(`/api/comments/${id}`, {
      method: "DELETE",
      credentials: "same-origin",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.detail || "删除失败");
    loadComments();
    return;
  }

  // 置顶/取消置顶
  if (e.target.classList.contains("btn-comment-pin")) {
    const id = e.target.dataset.id;
    const next = Number(e.target.dataset.next || "1") === 1;
    const res = await fetch(`/api/comments/${id}/pin`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ pinned: next }),
      credentials: "same-origin",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.detail || "操作失败");
    loadComments();
    return;
  }
});

// ===== 攻略投票（列表/详情） =====
async function initGuideVoting() {
  const guideVoteRoot = document.getElementById("guide-vote");
  if (!guideVoteRoot) return;

  const guideId = guideVoteRoot.dataset.guideId;
  const btnUp = guideVoteRoot.querySelector('[data-action="up"]');
  const btnDown = guideVoteRoot.querySelector('[data-action="down"]');
  const upCountEl = guideVoteRoot.querySelector('[data-role="up-count"]');
  const downCountEl = guideVoteRoot.querySelector('[data-role="down-count"]');

  let currentAction = guideVoteRoot.dataset.currentAction || null;

  function setActive(action) {
    btnUp.classList.toggle("is-active", action === "up");
    btnDown.classList.toggle("is-active", action === "down");
  }

  async function postVote(action) {
    // optimistic
    const prevAction = currentAction;
    const prevUp = Number(upCountEl.textContent || "0");
    const prevDown = Number(downCountEl.textContent || "0");

    // apply optimistic delta
    let nextUp = prevUp;
    let nextDown = prevDown;
    if (prevAction === action) {
      // cancel
      if (action === "up") nextUp = Math.max(0, prevUp - 1);
      else nextDown = Math.max(0, prevDown - 1);
      currentAction = null;
    } else {
      // switch/add
      if (prevAction === "up") nextUp = Math.max(0, prevUp - 1);
      if (prevAction === "down") nextDown = Math.max(0, prevDown - 1);
      if (action === "up") nextUp = nextUp + 1;
      else nextDown = nextDown + 1;
      currentAction = action;
    }
    upCountEl.textContent = String(nextUp);
    downCountEl.textContent = String(nextDown);
    setActive(currentAction);

    try {
      const res = await fetch(`/api/guides/${guideId}/vote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
        credentials: "same-origin",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "投票失败");

      upCountEl.textContent = String(data.upvote_count ?? 0);
      downCountEl.textContent = String(data.downvote_count ?? 0);
      currentAction = data.current_action || null;
      setActive(currentAction);
      if (data.influence_changed && data.influence_changed > 0) {
        showInfluenceToast(data.influence_changed);
      }
    } catch (err) {
      // rollback
      currentAction = prevAction;
      upCountEl.textContent = String(prevUp);
      downCountEl.textContent = String(prevDown);
      setActive(currentAction);
      alert(err.message || "投票失败");
    }
  }

  btnUp.addEventListener("click", () => postVote("up"));
  btnDown.addEventListener("click", () => postVote("down"));
  setActive(currentAction);
}

// ===== 通知🔔 =====
async function initNotifications() {
  const btn = document.getElementById("qk-notify-btn");
  const panel = document.getElementById("qk-notify-panel");
  const badge = document.getElementById("qk-notify-badge");
  const list = document.getElementById("qk-notify-list");
  const empty = document.getElementById("qk-notify-empty");
  if (!btn || !panel || !badge || !list || !empty) return;

  let open = false;

  function setBadge(n) {
    const v = Number(n || 0);
    if (v > 0) {
      badge.style.display = "inline-flex";
      badge.textContent = String(v);
    } else {
      badge.style.display = "none";
      badge.textContent = "0";
    }
  }

  async function refreshCount() {
    try {
      const res = await fetch("/api/notifications/unread_count", { credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      setBadge(data.count || 0);
    } catch (e) {
      // ignore
    }
  }

  function renderItems(items) {
    list.innerHTML = "";
    if (!items || items.length === 0) {
      empty.style.display = "block";
      return;
    }
    empty.style.display = "none";

    items.forEach((it) => {
      const row = document.createElement("a");
      row.href = `/guides/${it.article_id}?comment_id=${it.comment_id}`;
      row.className = "qk-notify-item" + (it.is_read ? "" : " is-unread");
      row.dataset.nid = it.id;
      row.dataset.articleId = it.article_id;
      row.dataset.commentId = it.comment_id;
      row.innerHTML = `
        <div class="qk-notify-title">${escapeHtml(it.sender_nickname || "有人")} 评论了《${escapeHtml(it.article_title || "") }》</div>
        <div class="qk-notify-time">${new Date(it.created_at).toLocaleString()}</div>
      `;
      list.appendChild(row);
    });
  }

  async function refreshList() {
    try {
      const res = await fetch("/api/notifications?limit=20", { credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      renderItems(data.items || []);
    } catch (e) {
      // ignore
    }
  }

  btn.addEventListener("click", async (e) => {
    e.preventDefault();
    open = !open;
    panel.style.display = open ? "block" : "none";
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      await refreshList();
      await refreshCount();
    }
  });

  document.addEventListener("click", (e) => {
    if (!open) return;
    const wrap = document.getElementById("qk-notify");
    if (wrap && !wrap.contains(e.target)) {
      open = false;
      panel.style.display = "none";
      btn.setAttribute("aria-expanded", "false");
    }
  });

  list.addEventListener("click", async (e) => {
    const a = e.target.closest(".qk-notify-item");
    if (!a) return;
    const nid = a.dataset.nid;
    try {
      await fetch(`/api/notifications/${nid}/read`, { method: "POST", credentials: "same-origin" });
    } catch (err) {
      // ignore
    }
    // 让浏览器正常跳转
    open = false;
    panel.style.display = "none";
    btn.setAttribute("aria-expanded", "false");
    setTimeout(refreshCount, 300);
  });

  // 初始拉一次未读数
  refreshCount();
}

// ===== 点评投票（卡牌详情） =====
async function initReviewVoting() {
  const list = document.getElementById("card-review-list");
  if (!list) return;

  function setActive(root, action) {
    const up = root.querySelector('[data-vote="up"]');
    const down = root.querySelector('[data-vote="down"]');
    if (up) up.classList.toggle("is-active", action === "up");
    if (down) down.classList.toggle("is-active", action === "down");
  }

  async function postVote(reviewId, action, root) {
    const upCountEl = root.querySelector('[data-role="up-count"]');
    const downCountEl = root.querySelector('[data-role="down-count"]');
    const prevAction = root.dataset.currentAction || "";
    const prevUp = Number(upCountEl.textContent || "0");
    const prevDown = Number(downCountEl.textContent || "0");

    let nextAction = prevAction;
    let nextUp = prevUp;
    let nextDown = prevDown;

    if (prevAction === action) {
      nextAction = "";
      if (action === "up") nextUp = Math.max(0, prevUp - 1);
      else nextDown = Math.max(0, prevDown - 1);
    } else {
      if (prevAction === "up") nextUp = Math.max(0, prevUp - 1);
      if (prevAction === "down") nextDown = Math.max(0, prevDown - 1);
      if (action === "up") nextUp += 1;
      else nextDown += 1;
      nextAction = action;
    }

    // optimistic
    root.dataset.currentAction = nextAction;
    upCountEl.textContent = String(nextUp);
    downCountEl.textContent = String(nextDown);
    setActive(root, nextAction || null);

    try {
      const res = await fetch(`/api/reviews/${reviewId}/vote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
        credentials: "same-origin",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "投票失败");

      root.dataset.currentAction = data.current_action || "";
      upCountEl.textContent = String(data.upvote_count ?? 0);
      downCountEl.textContent = String(data.downvote_count ?? 0);
      setActive(root, data.current_action || null);
    } catch (err) {
      // rollback
      root.dataset.currentAction = prevAction;
      upCountEl.textContent = String(prevUp);
      downCountEl.textContent = String(prevDown);
      setActive(root, prevAction || null);
      alert(err.message || "投票失败");
    }
  }

  list.addEventListener("click", (e) => {
    const btn = e.target.closest(".qk-review-vote-btn");
    if (!btn) return;
    const root = btn.closest(".qk-review-vote");
    const reviewId = root.dataset.reviewId;
    const action = btn.dataset.vote;
    postVote(reviewId, action, root);
  });
}

// 卡牌评测页面逻辑
async function initCardsPage() {
  const expansionSelect = document.getElementById("expansion-select");
  const cardsGrid = document.getElementById("cards-grid");
  if (!expansionSelect || !cardsGrid) return;

  const classSelect = document.getElementById("class-filter");
  const raritySelect = document.getElementById("rarity-filter");
  const searchInput = document.getElementById("card-search");
  const sortSelect = document.getElementById("cards-sort-by");
  const sortOrderBtn = document.getElementById("cards-sort-order");
  
  // 分页控件
  const paginationEl = document.getElementById("cards-pagination");
  const pageNumbersEl = document.getElementById("cards-page-numbers");
  const pageInfoEl = document.getElementById("cards-page-info");
  const prevBtn = document.getElementById("cards-prev");
  const nextBtn = document.getElementById("cards-next");
  const jumpInput = document.getElementById("cards-jump-input");
  const jumpBtn = document.getElementById("cards-jump-btn");
  
  // 新增：已点评/未点评筛选
  const btnFilterReviewed = document.getElementById("btn-filter-reviewed");
  const btnFilterUnreviewed = document.getElementById("btn-filter-unreviewed");
  let reviewedFilter = null; // null=all, true=reviewed, false=unreviewed

  // 新增：竞技场卡牌筛选
  const btnFilterArena = document.getElementById("btn-filter-arena");
  let arenaFilter = false; // false=不筛选, true=只显示竞技场卡牌
  let arenaPoolVersions = []; // 竞技场卡池版本列表
  let allExpansions = []; // 所有版本列表（用于切换时恢复）

  // 分页状态
  let currentPage = 1;
  let totalPages = 1;
  const pageSize = 24; // PC端一页24张
  let loading = false;
  let sortOrder = (sortOrderBtn && sortOrderBtn.dataset.order) || "asc";

  // 只有“战队成员及以上”才显示点评按钮（后端接口仍会校验权限）
  const roleCookie = decodeURIComponent(getCookie("user_role") || "");
  const canReview = ["member", "elite_member", "admin", "super_admin"].includes(roleCookie);

  // ---------- 工具函数 ----------

  function getFilters() {
    return {
      expansion: expansionSelect.value || "",
      cardClass: classSelect ? classSelect.value : "",
      rarity: raritySelect ? raritySelect.value : "",
      search: searchInput ? searchInput.value.trim() : "",
      sortBy: sortSelect ? sortSelect.value : "score",
      sortOrder: sortOrder,
      // 改为使用 my_reviewed 参数（当前用户是否点评过）
      my_reviewed: reviewedFilter,
      // 竞技场模式下直接用选中的版本筛选，不再传递所有版本
      arena_versions: "",
    };
  }

  function buildCardHtml(card, selectedClass) {
    // 评分：优先用点评均分，其次用单卡 arena_score，统一 0-5 量表
    let scoreText = "？";
    let scoreClass = "score-neutral";

    const pickedScore =
      card.average_score != null
        ? Number(card.average_score)
        : card.arena_score != null
          ? Number(card.arena_score)
          : null;

    if (pickedScore !== null && !Number.isNaN(pickedScore)) {
      scoreText = pickedScore.toFixed(1);

      if (pickedScore >= 4.5) {
        scoreClass = "score-epic"; // 顶级
      } else if (pickedScore >= 3) {
        scoreClass = "score-good"; // 还不错
      } else {
        scoreClass = "score-bad";  // 较差
      }
    }

    // 胜率
    let winrateText = "暂无胜率数据";
    let winData = card.arena_win_rates || null;

    if (typeof winData === "string") {
      try {
        winData = JSON.parse(winData);
      } catch (e) {
        winData = null;
      }
    }

    if (winData && typeof winData === "object") {
      const values = [];

      // 如果有选职业，优先显示该职业胜率
      if (selectedClass && winData[selectedClass] != null) {
        const v = Number(winData[selectedClass]);
        if (!Number.isNaN(v)) {
          winrateText = `${selectedClass} 胜率：${v.toFixed(1)}%`;
        }
      } else {
        // 否则展示平均胜率
        Object.values(winData).forEach((v) => {
          const n = Number(v);
          if (!Number.isNaN(n)) values.push(n);
        });
        if (values.length) {
          const avg =
            values.reduce((sum, v) => sum + v, 0) / values.length;
          winrateText = `平均胜率：${avg.toFixed(1)}%`;
        }
      }
    }

    // 短评（列表页只展示一部分）
    const fullReviewRaw = (card.short_review || "").trim();
    let shortReviewText = fullReviewRaw;

    const MAX_REVIEW_LEN = 40;
    if (shortReviewText.length > MAX_REVIEW_LEN) {
      shortReviewText = shortReviewText.slice(0, MAX_REVIEW_LEN) + "…";
    }
    const shortReview = shortReviewText
      ? escapeHtml(shortReviewText)
      : `<span class="card-review-empty">暂无短评</span>`;

    // 点评人
    const reviewerName =
      card.reviewer_nickname || card.reviewer_name || card.reviewer || null;
    const reviewerText = reviewerName
      ? `点评人：${reviewerName}`
      : "点评人：暂时无人点评";

    const cardClass = card.card_class || "中立";
    const rarity = card.rarity || "";

    // 稀有度颜色 class 映射
    let rarityClass = "rarity-common";
    switch (rarity) {
      case "稀有":
        rarityClass = "rarity-rare";
        break;
      case "史诗":
        rarityClass = "rarity-epic";
        break;
      case "传说":
        rarityClass = "rarity-legendary";
        break;
      case "免费":
      case "普通":
      default:
        rarityClass = "rarity-common"; // 免费和普通都用白色
        break;
    }

    const imgSrc = card.pic || "/static/image/Sylv.png";
    const nameSafe = escapeHtml(card.name || "");
    const reviewBtn = canReview
      ? `<a class="qk-btn qk-btn-outline card-review-btn" href="/cards/${card.id}#write-review" title="写点评">点评</a>`
      : "";

    return `
      <div class="card card-small card-eval" data-card-id="${card.id}">
        <div class="card-image-wrap">
          <img
            src="${imgSrc}"
            alt="${nameSafe}"
            class="card-art"
            loading="lazy"
          />
        </div>
        <div class="card-body">
          <p class="card-meta">
            ${cardClass} · <span class="${rarityClass}">${rarity || "免费"}</span>
          </p>
          <p class="card-score ${scoreClass}">评分：${scoreText}</p>
          <p class="card-winrate">${winrateText}</p>
          <p class="card-review">${shortReview}</p>
          <div class="card-eval-footer">
            <span class="card-reviewer">${escapeHtml(reviewerText)}</span>
            ${reviewBtn}
          </div>
        </div>
      </div>
    `;
  }

  async function loadExpansions() {
    try {
      const res = await fetch("/api/cards/expansions");
      if (!res.ok) return;
      const expansions = await res.json();

      expansionSelect.innerHTML = "";

      // 按“(年份)”倒序排序
      expansions.sort((a, b) => {
        const yearA = parseInt((a.match(/\((\d{4})\)/) || [])[1] || "0", 10);
        const yearB = parseInt((b.match(/\((\d{4})\)/) || [])[1] || "0", 10);
        return yearB - yearA;
      });

      for (const exp of expansions) {
        const option = document.createElement("option");
        option.value = exp;
        option.textContent = exp;
        expansionSelect.appendChild(option);
      }

      // 保存所有版本列表
      allExpansions = expansions;
    } catch (err) {
      console.error("加载版本列表失败", err);
    }
  }

  // 渲染版本下拉选项
  function renderExpansionOptions(versions) {
    expansionSelect.innerHTML = "";
    for (const exp of versions) {
      const option = document.createElement("option");
      option.value = exp;
      option.textContent = exp;
      expansionSelect.appendChild(option);
    }
  }

  // 加载竞技场卡池版本列表
  async function loadArenaPoolVersions() {
    try {
      const res = await fetch("/api/arena-pool-versions");
      if (!res.ok) return;
      arenaPoolVersions = await res.json();
    } catch (err) {
      console.error("加载竞技场卡池版本失败", err);
    }
  }

  async function loadCards(page = 1) {
    if (loading) return;
    loading = true;
    cardsGrid.innerHTML = '<p class="cards-loading">加载中...</p>';

    const { expansion, cardClass, rarity, search, sortBy, sortOrder, my_reviewed, arena_versions } = getFilters();
    const params = new URLSearchParams();
    params.append("page", String(page));
    params.append("page_size", String(pageSize));
    if (arena_versions) params.append("arena_versions", arena_versions);
    else if (expansion) params.append("version", expansion);
    if (cardClass) params.append("card_class", cardClass);
    if (rarity) params.append("rarity", rarity);
    if (search) params.append("search", search);
    if (sortBy) params.append("sort_by", sortBy);
    if (sortOrder) params.append("sort_order", sortOrder);
    if (my_reviewed !== null) params.append("my_reviewed", String(my_reviewed));

    try {
      const res = await fetch(`/api/cards?${params.toString()}`);
      if (!res.ok) throw new Error("加载卡牌失败");
      const data = await res.json();

      const cards = data.items || [];
      const total = data.total || 0;
      totalPages = Math.ceil(total / pageSize) || 1;
      currentPage = page;

      const selectedClass = classSelect ? classSelect.value : "";
      if (cards.length === 0) {
        cardsGrid.innerHTML =
          '<p class="cards-empty">当前筛选条件下没有卡牌。</p>';
        if (paginationEl) paginationEl.style.display = "none";
      } else {
        const html = cards
          .map((card) => buildCardHtml(card, selectedClass))
          .join("");
        cardsGrid.innerHTML = html;
        if (paginationEl) paginationEl.style.display = "flex";
        updateCardsPagination();
      }
    } catch (err) {
      console.error(err);
      cardsGrid.innerHTML = '<p class="cards-empty">加载失败，请刷新重试。</p>';
    } finally {
      loading = false;
    }
  }

  // 更新分页控件
  function updateCardsPagination() {
    if (pageInfoEl) {
      pageInfoEl.textContent = `第 ${currentPage} / ${totalPages} 页`;
    }

    if (prevBtn) {
      prevBtn.disabled = currentPage <= 1;
    }
    if (nextBtn) {
      nextBtn.disabled = currentPage >= totalPages;
    }

    if (pageNumbersEl) {
      pageNumbersEl.innerHTML = "";
      
      // 计算显示的页码范围（最多显示5个）
      let startPage = Math.max(1, currentPage - 2);
      let endPage = Math.min(totalPages, startPage + 4);
      
      // 调整起始页，确保显示5个（如果有足够页数）
      if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
      }

      for (let i = startPage; i <= endPage; i++) {
        const btn = document.createElement("button");
        btn.className = "pagination-num" + (i === currentPage ? " active" : "");
        btn.textContent = i;
        btn.addEventListener("click", () => {
          if (i !== currentPage) {
            loadCards(i);
          }
        });
        pageNumbersEl.appendChild(btn);
      }
    }
  }

  // ---------- 事件监听 ----------

  await loadExpansions();
  await loadArenaPoolVersions();
  await loadCards(1);

  // 分页按钮事件
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (currentPage > 1) {
        loadCards(currentPage - 1);
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (currentPage < totalPages) {
        loadCards(currentPage + 1);
      }
    });
  }

  if (jumpBtn && jumpInput) {
    const doJump = () => {
      const targetPage = parseInt(jumpInput.value, 10);
      if (targetPage >= 1 && targetPage <= totalPages) {
        loadCards(targetPage);
        jumpInput.value = "";
      } else {
        alert(`请输入 1 到 ${totalPages} 之间的页码`);
      }
    };

    jumpBtn.addEventListener("click", doJump);
    jumpInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        doJump();
      }
    });
  }

  expansionSelect.addEventListener("change", () => {
    // 竞技场模式下切换版本，保持筛选状态
    loadCards(1);
  });
  if (classSelect) {
    classSelect.addEventListener("change", () => loadCards(1));
  }
  if (raritySelect) {
    raritySelect.addEventListener("change", () => loadCards(1));
  }
  if (sortSelect) {
    sortSelect.addEventListener("change", () => loadCards(1));
  }
  if (sortOrderBtn) {
    sortOrderBtn.addEventListener("click", () => {
      sortOrder = sortOrder === "asc" ? "desc" : "asc";
      sortOrderBtn.dataset.order = sortOrder;
      const arrow = sortOrderBtn.querySelector(".order-arrow");
      const text = sortOrderBtn.querySelector(".order-text");
      if (arrow) arrow.textContent = sortOrder === "asc" ? "\u2191" : "\u2193";
      if (text) text.textContent = sortOrder === "asc" ? "正序" : "倒序";
      loadCards(1);
    });
  }
  if (searchInput) {
    let timer = null;
    searchInput.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => loadCards(1), 300);
    });
  }
  
  // 筛选按钮事件
  if (btnFilterArena) {
    btnFilterArena.addEventListener("click", () => {
      if (arenaPoolVersions.length === 0) {
        alert("竞技场卡池未配置，请联系管理员设置！");
        return;
      }
      arenaFilter = !arenaFilter;
      btnFilterArena.classList.toggle("active", arenaFilter);
      // 切换版本下拉框选项
      if (arenaFilter) {
        // 只显示竞技场卡池版本
        const arenaVersionsSorted = arenaPoolVersions.slice().sort((a, b) => {
          const yearA = parseInt((a.match(/\((\d{4})\)/) || [])[1] || "0", 10);
          const yearB = parseInt((b.match(/\((\d{4})\)/) || [])[1] || "0", 10);
          return yearB - yearA;
        });
        renderExpansionOptions(arenaVersionsSorted);
        // 默认选中第一个版本
        if (arenaVersionsSorted.length > 0) {
          expansionSelect.value = arenaVersionsSorted[0];
        }
      } else {
        // 恢复显示所有版本
        renderExpansionOptions(allExpansions);
      }
      loadCards(1);
    });
  }

  if (btnFilterReviewed) {
    btnFilterReviewed.addEventListener("click", () => {
      if (reviewedFilter === true) {
        reviewedFilter = null;
        btnFilterReviewed.classList.remove("active");
      } else {
        reviewedFilter = true;
        btnFilterReviewed.classList.add("active");
        if (btnFilterUnreviewed) btnFilterUnreviewed.classList.remove("active");
      }
      loadCards(1);
    });
  }
  
  if (btnFilterUnreviewed) {
    btnFilterUnreviewed.addEventListener("click", () => {
      if (reviewedFilter === false) {
        reviewedFilter = null;
        btnFilterUnreviewed.classList.remove("active");
      } else {
        reviewedFilter = false;
        btnFilterUnreviewed.classList.add("active");
        if (btnFilterReviewed) btnFilterReviewed.classList.remove("active");
      }
      loadCards(1);
    });
  }

  // 点击卡牌跳详情
  cardsGrid.addEventListener("click", (e) => {
    // 点击“点评”按钮时，不劫持跳转（让 a 标签自己带 hash 跳转）
    if (e.target.closest(".card-review-btn")) return;
    const cardEl = e.target.closest(".card-eval");
    if (!cardEl) return;
    const id = cardEl.dataset.cardId;
    if (id) {
      window.location.href = `/cards/${id}`;
    }
  });
}

async function initCardDetailPage() {
  const root = document.querySelector(".card-detail-page");
  if (!root) return;

  const cardId = root.dataset.cardId;
  const reviewList = document.getElementById("card-review-list");
  const btnMore = document.getElementById("btn-review-load-more");
  const selSort = document.getElementById("review-sort");
  const chkHighScore = document.getElementById("filter-high-score");
  const chkLatestVersion = document.getElementById("filter-latest-version");

  // 写点评表单（只有符合权限的用户才会渲染这些 DOM）
  const myScoreEl = document.getElementById("my-review-score");
  const myContentEl = document.getElementById("my-review-content");
  const myVersionEl = document.getElementById("my-review-version");
  const mySubmitBtn = document.getElementById("btn-submit-my-review");
  const myStatusEl = document.getElementById("my-review-status");

  let page = 1;
  const pageSize = 10;
  let total = 0;
  let loading = false;

  async function loadMyReview() {
    if (!myScoreEl || !myContentEl || !mySubmitBtn) return;
    const token = getToken();
    if (!token) return;

    try {
      const res = await fetch(`/api/v1/cards/${cardId}/reviews/me`, {
        headers: { Authorization: "Bearer " + token },
      });
      if (res.status === 404) {
        if (myStatusEl) myStatusEl.textContent = "你还没有点评过这张卡";
        return;
      }
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        if (myStatusEl) myStatusEl.textContent = "";
        return;
      }
      const d = await res.json().catch(() => ({}));
      if (d && d.id) {
        myScoreEl.value = d.score ?? "";
        myContentEl.value = d.content ?? "";
        if (myVersionEl) myVersionEl.value = d.game_version ?? "";
        if (myStatusEl) myStatusEl.textContent = "已加载你的历史点评（再次提交会覆盖更新）";
      }
    } catch (e) {
      // ignore
    }
  }

  function renderReviewItem(r) {
    const date = new Date(r.created_at);
    const timeStr = date.toLocaleString("zh-CN");

    const reviewerName = r?.reviewer?.name ? String(r.reviewer.name) : "匿名";
    const reviewerInitial = reviewerName.trim().charAt(0) || "玩";

    const score = r.score ?? 0;
    let scoreClass = "score-mid";
    if (score < 3) scoreClass = "score-low";
    else if (score > 4) scoreClass = "score-high";

    const expertBadge = r.reviewer && r.reviewer.is_expert
      ? `<span class="badge badge-expert">专家</span>`
      : "";

    const version = r.game_version ? ` · 版本 ${r.game_version}` : "";

    const scoreText = Number(score);
    const scoreShow = Number.isNaN(scoreText) ? "0.0" : scoreText.toFixed(1);
    const contentSafe = escapeHtml(r.content || "").replace(/\n/g, "<br>");

    // 判断当前用户是否为管理员
    const currentUser = window.QK_CARD_DETAIL?.currentUser;
    const isAdmin = currentUser && ["admin", "super_admin"].includes(currentUser.role);
    const deleteBtn = isAdmin
      ? `<button class="review-delete-btn" data-review-id="${r.review_id}" title="删除点评">🗑️</button>`
      : "";

    const up = Number(r.upvote_count || 0);
    const down = Number(r.downvote_count || 0);
    const currentAction = r.current_user_action || "";

    return `
      <article class="card-review-item" id="review-${r.review_id}" data-review-id="${r.review_id}">
        <header class="review-header">
          <div class="reviewer-info">
            <div class="avatar-placeholder">${escapeHtml(reviewerInitial)}</div>
            <div>
              <div class="reviewer-name">
                ${escapeHtml(reviewerName)}
                ${expertBadge}
              </div>
              <div class="review-meta">${timeStr}${version}</div>
            </div>
          </div>
          <div class="review-header-right" style="display:flex;align-items:center;gap:12px;">
            ${deleteBtn}
            <div class="review-score ${scoreClass}">
              <span class="score-number">${scoreShow}</span>
              <span class="score-unit">分</span>
            </div>
          </div>
        </header>
        <div class="review-body">
          <p class="review-content collapsed">${contentSafe}</p>
          <button class="review-toggle" type="button">展开</button>
        </div>
        <div class="qk-review-vote" data-review-id="${r.review_id}" data-current-action="${escapeHtml(currentAction)}">
          <button class="qk-review-vote-btn ${currentAction === "up" ? "is-active" : ""}" type="button" data-vote="up" aria-label="点赞">
            👍 <span class="qk-vote-count" data-role="up-count">${up}</span>
          </button>
          <button class="qk-review-vote-btn ${currentAction === "down" ? "is-active" : ""}" type="button" data-vote="down" aria-label="拉踩">
            👎 <span class="qk-vote-count" data-role="down-count">${down}</span>
          </button>
        </div>
      </article>
    `;
  }

  function updateAvgScore(avg) {
    const scoreWrap = document.querySelector(".card-avg-score");
    if (!scoreWrap) return;
    const span = scoreWrap.querySelector(".score-number");
    const v = avg == null ? "—" : avg.toFixed(1);
    span.textContent = v;

    scoreWrap.classList.remove("score-low", "score-mid", "score-high");
    let cls = "score-mid";
    if (avg != null) {
      if (avg < 3) cls = "score-low";
      else if (avg > 4) cls = "score-high";
    }
    scoreWrap.classList.add(cls);
  }

  async function loadReviews(reset = false) {
    if (loading) return;
    loading = true;

    if (reset) {
      page = 1;
      reviewList.innerHTML = "";
    }

    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    params.set("sort", selSort.value || "time_desc");
    if (chkHighScore.checked) params.set("min_score", "4");
    if (chkLatestVersion.checked) params.set("latest_version_only", "true");

    const res = await fetch(`/api/v1/cards/${cardId}/reviews?` + params.toString());
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "加载点评失败");
      loading = false;
      return;
    }

    updateAvgScore(data.card_info.average_score);

    data.reviews.forEach((r) => {
      reviewList.insertAdjacentHTML("beforeend", renderReviewItem(r));
    });

    total = data.pagination.total;
    const loadedCount = reviewList.querySelectorAll(".card-review-item").length;

    if (loadedCount >= total || total === 0) {
      btnMore.style.display = "none";
    } else {
      btnMore.style.display = "inline-flex";
    }

    page += 1;
    loading = false;
  }

  // 提交 / 更新我的点评
  if (mySubmitBtn) {
    mySubmitBtn.addEventListener("click", async () => {
      const token = getToken();
      if (!token) {
        alert("请先登录再点评");
        window.location.href = "/login";
        return;
      }

      const score = Number(myScoreEl.value);
      if (Number.isNaN(score) || score < 0 || score > 5) {
        alert("评分请输入 0~5 之间的数字（支持 0.5 步进）");
        return;
      }

      const content = (myContentEl.value || "").trim();
      if (!content) {
        alert("请填写短评内容");
        return;
      }
      if (content.length > 200) {
        alert("短评最多 200 字，请精简一下～");
        return;
      }

      const payload = {
        score: score,
        content: content,
        game_version: myVersionEl ? (myVersionEl.value || "").trim() || null : null,
      };

      if (myStatusEl) myStatusEl.textContent = "提交中...";

      const res = await fetch(`/api/v1/cards/${cardId}/reviews`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (myStatusEl) myStatusEl.textContent = "";
        alert(data.detail || "提交失败");
        return;
      }

      if (myStatusEl) myStatusEl.textContent = "已保存 ✔";
      
      // 提交成功后，如果是首次点评（之前没有加载到 review_id），弹出影响力 +1 提示
      // 这里简单判断：如果之前 myScoreEl.value 是空的，说明可能是新增
      // 或者更严谨一点，loadMyReview 会填充 value。
      // 简单起见，只要成功就弹个提示，或者后端返回 flag。
      // 由于后端没返回 flag，这里前端简单处理：总是提示，或者只在第一次提示。
      // 为了体验，每次成功都提示一下也无妨，或者只提示“影响力+1”如果确实加了。
      // 既然需求是“每点评一张卡牌...弹出”，那就弹吧。
      showInfluenceToast(1, "我的影响力");

      // 刷新列表 + 均分
      await loadReviews(true);
    });
  }

  // 事件绑定
  btnMore.addEventListener("click", () => {
    loadReviews(false);
  });

  selSort.addEventListener("change", () => loadReviews(true));
  chkHighScore.addEventListener("change", () => loadReviews(true));
  chkLatestVersion.addEventListener("change", () => loadReviews(true));

  // 展开 / 收起 长评 + 删除点评
  reviewList.addEventListener("click", async (e) => {
    // 删除按钮
    const deleteBtn = e.target.closest(".review-delete-btn");
    if (deleteBtn) {
      e.preventDefault();
      const reviewId = deleteBtn.dataset.reviewId;
      if (!confirm("确定要删除这条点评吗？")) return;

      const token = getToken();
      if (!token) {
        alert("请先登录");
        return;
      }

      try {
        const res = await fetch(`/api/v1/cards/${cardId}/reviews/${reviewId}`, {
          method: "DELETE",
          headers: {
            Authorization: "Bearer " + token,
          },
        });
        if (res.ok) {
          // 移除 DOM 元素
          const item = deleteBtn.closest(".card-review-item");
          if (item) item.remove();
          alert("删除成功");
          // 刷新点评列表和平均分
          loadReviews(true);
        } else {
          const d = await res.json().catch(() => ({}));
          alert(d.detail || "删除失败");
        }
      } catch (err) {
        console.error(err);
        alert("网络错误");
      }
      return;
    }

    // 展开/收起
    const btn = e.target.closest(".review-toggle");
    if (!btn) return;
    const item = btn.closest(".card-review-item");
    const p = item.querySelector(".review-content");
    p.classList.toggle("collapsed");
    btn.textContent = p.classList.contains("collapsed") ? "展开" : "收起";
  });

  // 首次加载
  await loadReviews(true);
  await loadMyReview();

  // 检查 URL hash，滚动到对应评论并高亮
  const hash = window.location.hash;
  if (hash && hash.startsWith("#review-")) {
    const targetEl = document.getElementById(hash.substring(1));
    if (targetEl) {
      targetEl.scrollIntoView({ behavior: "smooth", block: "center" });
      targetEl.classList.add("highlight-review");
      setTimeout(() => targetEl.classList.remove("highlight-review"), 3000);
    }
  }
}

// 简单全局初始化
document.addEventListener("DOMContentLoaded", () => {
  loadComments();
  initCommentComposer();
  initGuidesPage();
  initCardsPage();
  initCardDetailPage && initCardDetailPage();
  initMembersPage(); // ✅ 战队名册页面初始化
  initGuideVoting();
  initReviewVoting();
  initNotifications();

  // 移动端菜单开关
  const menuBtn = document.getElementById("qk-menu-toggle");
  const nav = document.getElementById("qk-nav");
  const navOverlay = document.getElementById("qk-nav-overlay");
  if (menuBtn && nav) {
    const closeNav = () => {
      nav.classList.remove("open");
      menuBtn.setAttribute("aria-expanded", "false");
      document.body.classList.remove("nav-open");
    };

    menuBtn.addEventListener("click", () => {
      const isOpen = nav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
      document.body.classList.toggle("nav-open", isOpen);
    });

    // 点击导航链接后收起侧栏（仅移动端）
    nav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        if (window.innerWidth <= 768) {
          // 不阻止默认行为，让浏览器正常跳转
          // 稍微延迟关闭菜单，确保点击有效
          setTimeout(closeNav, 100);
        }
      });
    });

    // 点击遮罩或外部区域关闭（仅移动端）
    if (navOverlay) {
      navOverlay.addEventListener("click", () => {
        if (window.innerWidth <= 768) closeNav();
      });
    }

    document.addEventListener("click", (e) => {
      if (
        window.innerWidth <= 768 &&
        nav.classList.contains("open") &&
        !nav.contains(e.target) &&
        !menuBtn.contains(e.target)
      ) {
        closeNav();
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && nav.classList.contains("open")) {
        closeNav();
      }
    });
  }

  // 解码并显示昵称（后端对 nickname 做了 percent-encode）
  const rawNick = getCookie("user_nickname");
  if (rawNick) {
    try {
      const nick = decodeURIComponent(rawNick);
      document.querySelectorAll(".qk-user .nick").forEach((el) => {
        el.textContent = nick;
      });
    } catch (err) {
      // 无操作：如果 decode 失败则保留原始值
    }
  }

  // 点击切换用户菜单：仅点击固定/取消固定（不依赖悬停）
  const userDropdown = document.querySelector('.qk-user-dropdown');
  if (userDropdown) {
    const toggleTargets = userDropdown.querySelectorAll('.avatar, .nick');
    const menu = userDropdown.querySelector('.qk-user-menu');
    let pinned = false; // 被点击固定时为 true

    function openMenu() {
      userDropdown.classList.add('open');
      toggleTargets.forEach((t) => t.setAttribute('aria-expanded', 'true'));
    }
    function closeMenu() {
      userDropdown.classList.remove('open');
      toggleTargets.forEach((t) => t.setAttribute('aria-expanded', 'false'));
      pinned = false;
    }

    // 点击在头像 / 昵称上切换固定状态：第一次点击固定打开，第二次取消固定并关闭
    toggleTargets.forEach((t) => {
      t.addEventListener('click', (ev) => {
        ev.stopPropagation();
        pinned = !pinned;
        if (pinned) openMenu();
        else closeMenu();
      });
      t.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          ev.stopPropagation();
          pinned = !pinned;
          if (pinned) openMenu();
          else closeMenu();
        }
      });
    });

    // 点击菜单内部不关闭（以便点击链接）
    // 注意：不要阻止事件冒泡，这样 document 上的登出处理器能正常收到点击事件

    // 点击页面其它位置或按 Esc：取消固定并关闭菜单
    document.addEventListener('click', (e) => {
      if (!userDropdown.contains(e.target)) {
        pinned = false;
        closeMenu();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        pinned = false;
        closeMenu();
      }
    });
  }
});
