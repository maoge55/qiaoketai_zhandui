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
    const token = getToken();
    if (!token) return (window.location.href = "/login");

    const res = await fetch(`/api/articles/${articleId}/comments`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
      },
      body: JSON.stringify({ content }),
    });
    const data = await res.json();
    if (!res.ok) return alert(data.detail || "评论失败");
    // 不刷新页面，直接重载评论区
    document.getElementById("comment-content").value = "";
    loadComments();
  }
});


// ===== 战队名册：分页加载 & 触底刷新 =====
let membersPage = 1;
let membersPageSize = 12;
let membersLoading = false;
let membersFinished = false;

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

  const card = document.createElement("div");
  card.className = "card member-card member-card-animated";

  card.innerHTML = `
    <a href="/members/${profile.user_id}" class="member-card-link">
      <!-- 左侧：方形头像卡片 -->
      <div class="member-card-avatar"
           style="${avatarUrl ? `background-image:url('${avatarUrl}')` : ""}">
      </div>

      <!-- 中间：基本信息 -->
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
          年龄：${age} ｜ 性别：${gender}
        </p>
        <p class="member-card-tags">${escapeHtml(tags)}</p>
        <p class="member-card-bio">${escapeHtml(bioText)}</p>
      </div>

      <!-- 右侧：影响力等信息 -->
      <div class="member-card-right">
        <span class="member-card-influence">
          影响力 ${influence}
        </span>
      </div>
    </a>
  `;

  return card;
}


async function loadMembersPage() {
  const grid = document.getElementById("members-grid");
  const loadingEl = document.getElementById("members-loading");
  const emptyEl = document.getElementById("members-empty");

  if (!grid || membersLoading || membersFinished) return;

  membersLoading = true;
  if (loadingEl) loadingEl.style.display = "block";
  if (emptyEl) emptyEl.style.display = "none";

  try {
    const res = await fetch(
      `/api/members?page=${membersPage}&page_size=${membersPageSize}`
    );
    const data = await res.json();

    if (!res.ok) {
      console.error("加载成员失败：", data);
      membersFinished = true;
      return;
    }

    if (Array.isArray(data) && data.length > 0) {
      data.forEach((p) => {
        grid.appendChild(buildMemberCard(p));
      });

      membersPage += 1;
      if (data.length < membersPageSize) {
        membersFinished = true;
      }
    } else {
      if (membersPage === 1 && emptyEl) {
        emptyEl.style.display = "block";
      }
      membersFinished = true;
    }
  } catch (err) {
    console.error("加载成员出错：", err);
  } finally {
    membersLoading = false;
    if (loadingEl) loadingEl.style.display = "none";
  }
}

function initMembersPage() {
  const grid = document.getElementById("members-grid");
  if (!grid) return; // 不在战队名册页面

  // 首次加载
  loadMembersPage();

  // 触底刷新：滚动接近底部时继续加载
  window.addEventListener("scroll", () => {
    if (
      window.innerHeight + window.scrollY >=
      document.body.offsetHeight - 200
    ) {
      loadMembersPage();
    }
  });
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

      const card = document.createElement("div");
      card.className = "card guide-card";
      card.innerHTML = `
        <div class="guide-card-head">
          <a class="guide-title" href="/guides/${a.id}">${escapeHtml(a.title)}</a>
          <div class="meta">作者：${escapeHtml(a.author_nickname || "未知")} · ${created}</div>
        </div>
        <div class="guide-excerpt">${escapeHtml(a.excerpt || "")}</div>
        ${tagHtml ? `<div class="guide-tags">${tagHtml}</div>` : ""}
      `;
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

    const res = await fetch(`/api/articles/paged?${params.toString()}`);
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
        <div class="content">${nl2br(c.content)}</div>
        <div class="comment-actions">${actions.join(" ")}</div>
      `;
      container.appendChild(div);
      renderList(c.id, indent + 20);
    });
  }
  container.innerHTML = "";
  renderList(0, 0);
}

document.addEventListener("click", async (e) => {
  // 回复
  if (e.target.classList.contains("btn-reply")) {
    const parentId = e.target.dataset.id;
    const content = prompt("请输入回复内容：");
    if (!content) return;
    const token = getToken();
    if (!token) return (window.location.href = "/login");

    const res = await fetch(`/api/comments/${parentId}/reply`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
      },
      body: JSON.stringify({ content }),
    });
    const data = await res.json();
    if (!res.ok) return alert(data.detail || "回复失败");
    loadComments();
    return;
  }

  // 删除评论
  if (e.target.classList.contains("btn-comment-delete")) {
    const id = e.target.dataset.id;
    if (!confirm("确定要删除这条评论吗？（会同时删除其回复）")) return;
    const token = getToken();
    if (!token) return (window.location.href = "/login");

    const res = await fetch(`/api/comments/${id}`, {
      method: "DELETE",
      headers: {
        Authorization: "Bearer " + token,
      },
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
    const token = getToken();
    if (!token) return (window.location.href = "/login");

    const res = await fetch(`/api/comments/${id}/pin`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
      },
      body: JSON.stringify({ pinned: next }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.detail || "操作失败");
    loadComments();
    return;
  }
});

// 卡牌评测页面逻辑
async function initCardsPage() {
  const expansionSelect = document.getElementById("expansion-select");
  const cardsGrid = document.getElementById("cards-grid");
  if (!expansionSelect || !cardsGrid) return;

  const classSelect = document.getElementById("class-filter");
  const raritySelect = document.getElementById("rarity-filter");
  const searchInput = document.getElementById("card-search");
  const loadMoreBtn = document.getElementById("cards-load-more");

  let page = 1;
  const pageSize = 40;
  let loading = false;
  let hasMore = true;

  // 只有“战队成员及以上”才显示点评按钮（后端接口仍会校验权限）
  const roleCookie = decodeURIComponent(getCookie("user_role") || "");
  const canReview = ["member", "elite_member", "admin"].includes(roleCookie);

  // ---------- 工具函数 ----------

  function getFilters() {
    return {
      expansion: expansionSelect.value || "",
      cardClass: classSelect ? classSelect.value : "",
      rarity: raritySelect ? raritySelect.value : "",
      search: searchInput ? searchInput.value.trim() : "",
    };
  }

  function buildCardHtml(card, selectedClass) {
    // 评分
    let scoreText = "？";
    let scoreClass = "score-neutral";

    if (card.arena_score !== null && card.arena_score !== undefined) {
      const n = Number(card.arena_score);
      if (!Number.isNaN(n)) {
        scoreText = n.toFixed(1);

        if (n >= 4.5) {
          // 顶级卡
          scoreClass = "score-epic";
        } else if (n >= 3) {
          // 还不错
          scoreClass = "score-good";
        } else {
          // 较差
          scoreClass = "score-bad";
        }
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
          <p class="card-score ${scoreClass}">竞技场评分：${scoreText}</p>
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
    } catch (err) {
      console.error("加载版本列表失败", err);
    }
  }

  async function loadCards(reset = false) {
    if (loading) return;
    if (!hasMore && !reset) return;

    loading = true;

    if (reset) {
      page = 1;
      hasMore = true;
      cardsGrid.innerHTML = "";
    }

    const { expansion, cardClass, rarity, search } = getFilters();
    const params = new URLSearchParams();
    params.append("page", String(page));
    params.append("page_size", String(pageSize));
    if (expansion) params.append("version", expansion);
    if (cardClass) params.append("card_class", cardClass);
    if (rarity) params.append("rarity", rarity);
    if (search) params.append("search", search);

    try {
      const res = await fetch(`/api/cards?${params.toString()}`);
      if (!res.ok) throw new Error("加载卡牌失败");
      const cards = await res.json();

      const selectedClass = classSelect ? classSelect.value : "";
      if (cards.length === 0 && page === 1) {
        cardsGrid.innerHTML =
          `<p class="cards-empty">当前筛选条件下没有卡牌。</p>`;
        hasMore = false;
      } else {
        const html = cards
          .map((card) => buildCardHtml(card, selectedClass))
          .join("");
        cardsGrid.insertAdjacentHTML("beforeend", html);
        if (cards.length < pageSize) {
          hasMore = false;
        } else {
          page += 1;
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      loading = false;
      if (loadMoreBtn) {
        loadMoreBtn.style.display = hasMore ? "inline-flex" : "none";
      }
    }
  }

  // ---------- 事件监听 ----------

  await loadExpansions();
  await loadCards(true);

  expansionSelect.addEventListener("change", () => loadCards(true));
  if (classSelect) {
    classSelect.addEventListener("change", () => loadCards(true));
  }
  if (raritySelect) {
    raritySelect.addEventListener("change", () => loadCards(true));
  }
  if (searchInput) {
    let timer = null;
    searchInput.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => loadCards(true), 300);
    });
  }
  if (loadMoreBtn) {
    loadMoreBtn.addEventListener("click", () => loadCards(false));
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
    if (score < 4) scoreClass = "score-low";
    else if (score > 7) scoreClass = "score-high";

    const expertBadge = r.reviewer && r.reviewer.is_expert
      ? `<span class="badge badge-expert">专家</span>`
      : "";

    const version = r.game_version ? ` · 版本 ${r.game_version}` : "";

    const scoreText = Number(score);
    const scoreShow = Number.isNaN(scoreText) ? "0.0" : scoreText.toFixed(1);
    const contentSafe = escapeHtml(r.content || "").replace(/\n/g, "<br>");

    return `
      <article class="card-review-item">
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
          <div class="review-score ${scoreClass}">
            <span class="score-number">${scoreShow}</span>
            <span class="score-unit">分</span>
          </div>
        </header>
        <div class="review-body">
          <p class="review-content collapsed">${contentSafe}</p>
          <button class="review-toggle" type="button">展开</button>
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
      if (avg < 4) cls = "score-low";
      else if (avg > 7) cls = "score-high";
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
    if (chkHighScore.checked) params.set("min_score", "7");
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
      if (Number.isNaN(score) || score < 0 || score > 10) {
        alert("评分请输入 0~10 之间的数字（支持 0.5 步进）");
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

  // 展开 / 收起 长评
  reviewList.addEventListener("click", (e) => {
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
}

// 简单全局初始化
document.addEventListener("DOMContentLoaded", () => {
  loadComments();
  initGuidesPage();
  initCardsPage();
  initCardDetailPage && initCardDetailPage();
  initMembersPage(); // ✅ 战队名册页面初始化

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
