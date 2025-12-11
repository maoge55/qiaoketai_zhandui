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
    location.reload();
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
  const influence =
    typeof profile.influence === "number" ? profile.influence : 1;
  const rank =
    typeof profile.current_season_rank === "number"
      ? profile.current_season_rank
      : null;

  const card = document.createElement("div");
  card.className = "card member-card member-card-animated";

  card.innerHTML = `
    <a href="/members/${profile.user_id}">
      <div class="member-card-inner">
        <div class="member-card-avatar"
             style="${avatarUrl ? `background-image:url('${avatarUrl}')` : ""}">
        </div>
        <div class="member-card-info">
          <div class="member-card-header">
            <h3>${nickname}</h3>
            <span class="member-card-badge">影响力 ${influence}</span>
          </div>
          <p class="member-card-meta">
            年龄：${age} ｜ 性别：${gender}${
              rank ? ` ｜ 当前赛季排名：${rank}` : ""
            }
          </p>
          <p class="member-card-tags">${tags}</p>
        </div>
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


// 加载文章评论
async function loadComments() {
  if (!window.QK_CURRENT_ARTICLE_ID) return;
  const res = await fetch(
    `/api/articles/${window.QK_CURRENT_ARTICLE_ID}/comments`
  );
  const data = await res.json();
  const container = document.getElementById("comments-list");
  if (!Array.isArray(data) || !container) return;

  // 简单楼中楼（一级 + 回复缩进）
  const byParent = {};
  data.forEach((c) => {
    const pid = c.parent_id || 0;
    byParent[pid] = byParent[pid] || [];
    byParent[pid].push(c);
  });

  function renderList(parentId, indent) {
    (byParent[parentId] || []).forEach((c) => {
      const div = document.createElement("div");
      div.className = "comment-item";
      div.style.marginLeft = indent + "px";
      div.innerHTML = `
        <div class="meta">
          <span>${c.user_nickname}</span>
          <span>${new Date(c.created_at).toLocaleString()}</span>
        </div>
        <div class="content">${c.content}</div>
        <button class="qk-btn qk-btn-outline btn-reply" data-id="${c.id}">回复</button>
      `;
      container.appendChild(div);
      renderList(c.id, indent + 20);
    });
  }
  container.innerHTML = "";
  renderList(0, 0);
}

document.addEventListener("click", async (e) => {
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
    location.reload();
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
    const fullReview = (card.short_review || "").trim();
    let shortReview = fullReview;

    const MAX_REVIEW_LEN = 40;
    if (shortReview.length > MAX_REVIEW_LEN) {
      shortReview = shortReview.slice(0, MAX_REVIEW_LEN) + "…";
    }
    if (!shortReview) {
      shortReview = `<span class="card-review-empty">暂无短评</span>`;
    }

    // 点评人
    const reviewerName =
      card.reviewer_name || card.reviewer || null;
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

    return `
      <div class="card card-small card-eval" data-card-id="${card.id}">
        <div class="card-image-wrap">
          <img
            src="${card.pic || "/static/images/card-placeholder.png"}"
            alt="${card.name || ""}"
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
          <p class="card-reviewer">${reviewerText}</p>
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

  let page = 1;
  const pageSize = 10;
  let total = 0;
  let loading = false;

  function renderReviewItem(r) {
    const date = new Date(r.created_at);
    const timeStr = date.toLocaleString("zh-CN");

    const score = r.score ?? 0;
    let scoreClass = "score-mid";
    if (score < 4) scoreClass = "score-low";
    else if (score > 7) scoreClass = "score-high";

    const expertBadge = r.reviewer.is_expert
      ? `<span class="badge badge-expert">专家</span>`
      : "";

    const version = r.game_version ? ` · 版本 ${r.game_version}` : "";

    return `
      <article class="card-review-item">
        <header class="review-header">
          <div class="reviewer-info">
            <div class="avatar-placeholder">${r.reviewer.name[0] || "玩"}</div>
            <div>
              <div class="reviewer-name">
                ${r.reviewer.name}
                ${expertBadge}
              </div>
              <div class="review-meta">${timeStr}${version}</div>
            </div>
          </div>
          <div class="review-score ${scoreClass}">
            <span class="score-number">${score}</span>
            <span class="score-unit">分</span>
          </div>
        </header>
        <div class="review-body">
          <p class="review-content collapsed">${r.content}</p>
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
}

// 简单全局初始化
document.addEventListener("DOMContentLoaded", () => {
  loadComments();
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
