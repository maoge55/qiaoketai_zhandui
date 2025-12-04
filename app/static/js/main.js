// 简单封装：获取 JWT
function getToken() {
  return localStorage.getItem("qk_token") || getCookie("access_token") || "";
}

function setToken(token, role, nickname) {
  localStorage.setItem("qk_token", token);
  document.cookie = `access_token=${token};path=/`;
  if (role) document.cookie = `user_role=${role};path=/`;
  if (nickname) document.cookie = `user_nickname=${nickname};path=/`;
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

// 卡牌页面逻辑
async function initCardsPage() {
  const sel = document.getElementById("expansion-select");
  const grid = document.getElementById("cards-grid");
  if (!sel || !grid) return;

  const expRes = await fetch("/api/cards/expansions");
  const exps = await expRes.json();
  sel.innerHTML = exps
    .map((e) => `<option value="${e}">${e}</option>`)
    .join("");

  async function loadCards() {
    const expansion = sel.value;
    const res = await fetch(
      `/api/cards?expansion=${encodeURIComponent(expansion)}&page=1&page_size=50`
    );
    const cards = await res.json();
    grid.innerHTML = cards
      .map(
        (c) => `
        <div class="card card-small">
          <div class="card-header">
            <span class="mana">${c.mana_cost}</span>
            <h3>${c.name}</h3>
          </div>
          <p class="meta">${c.card_class} · ${c.rarity}</p>
          <p class="score">竞技场评分：${c.arena_score || "?"}</p>
          <p class="review">${c.short_review || ""}</p>
        </div>
      `
      )
      .join("");
  }

  sel.addEventListener("change", loadCards);
  if (exps.length) {
    sel.value = exps[0];
    loadCards();
  }
}

// 简单全局初始化
document.addEventListener("DOMContentLoaded", () => {
  loadComments();
  initCardsPage();

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
