// Admin panel page module.
//
// Extracted from app.js. Owns: admin dashboard / users / feedback sections,
// action CRUD, test report, filters, quick-nav scroll, and panel event
// binding. App-level helpers (state, els, apiGet, authHeaders, fetchWithTimeout,
// escape, toasts, demo/error notices, debounce) are injected via `ctx`.
//
// ctx shape:
//   state, els,
//   apiGet(path, opts), apiSend(method, path, body, opts),
//   fetchWithTimeout(url, opts, timeoutMs), authHeaders(extra),
//   parseApiError(response),
//   escapeHtml, escapeAdminText, formatShortDate, debounce,
//   showToast, showErrorToast, renderDemoNotice, renderLoadError

export function createAdminPage(ctx) {
  const {
    state,
    els,
    apiGet,
    apiSend,
    fetchWithTimeout,
    authHeaders,
    parseApiError,
    escapeHtml,
    escapeAdminText,
    formatShortDate,
    debounce,
    showToast,
    showErrorToast,
    renderDemoNotice,
    renderLoadError,
  } = ctx;

  const adminFilterDebounced = debounce(() => loadAdminActions({ silent: true }), 300);
  const adminUserFilterDebounced = debounce(() => loadAdminActions({ silent: true }), 300);

  function getApiDocsUrl() {
    const apiBase = window.APP_CONFIG.API_BASE || "";
    if (apiBase.endsWith("/api")) {
      return `${apiBase.slice(0, -4)}/docs`;
    }
    return `${window.location.protocol}//${window.location.hostname}:8000/docs`;
  }

  function parseAdminList(value) {
    return String(value || "")
      .split(/[,，]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function joinAdminList(items) {
    return Array.isArray(items) ? items.join("，") : "";
  }

  function buildAdminActionsUrl(filters = state.adminFilters) {
    const params = new URLSearchParams();
    if (filters.q?.trim()) params.set("q", filters.q.trim());
    if (filters.bodyRegion) params.set("body_region", filters.bodyRegion);
    const query = params.toString();
    return `${window.APP_CONFIG.API_BASE}/admin/actions${query ? `?${query}` : ""}`;
  }

  function renderAdminActionFormFields(action = {}, prefix = "admin") {
    const id = action.id || "";
    const idField =
      prefix === "create"
        ? `<label class="admin-field admin-field-wide">动作 ID <span class="required">*</span>
            <input name="id" type="text" placeholder="例如：neck_chin_tuck" value="${escapeAdminText(id)}" required />
            <span class="hint">2-64 位字母、数字、下划线或连字符</span>
          </label>`
        : `<input name="id" type="hidden" value="${escapeAdminText(id)}" />`;

    return `
      ${idField}
      <label class="admin-field admin-field-wide">动作名称 <span class="required">*</span>
        <input name="name" type="text" value="${escapeAdminText(action.name || "")}" required />
      </label>
      <label class="admin-field">组数
        <input name="sets" type="number" min="1" max="20" value="${action.sets ?? 3}" />
      </label>
      <label class="admin-field">次数
        <input name="reps" type="number" min="1" max="200" value="${action.reps ?? 10}" />
      </label>
      <label class="admin-field admin-field-wide">频次
        <input name="frequency" type="text" value="${escapeAdminText(action.frequency || "")}" placeholder="例如：每日1-2次" />
      </label>
      <label class="admin-field admin-field-wide">训练部位
        <input name="body_regions" type="text" value="${escapeAdminText(joinAdminList(action.body_regions))}" placeholder="颈部，肩部" />
      </label>
      <label class="admin-field admin-field-wide">适应症状
        <input name="target_conditions" type="text" value="${escapeAdminText(joinAdminList(action.target_conditions))}" placeholder="颈椎病，肩颈疼痛" />
      </label>
      <label class="admin-field admin-field-full">动作说明
        <textarea name="description" rows="2">${escapeAdminText(action.description || action.note || "")}</textarea>
      </label>
      <label class="admin-field admin-field-full">禁忌说明
        <textarea name="contraindications" rows="2">${escapeAdminText(action.contraindications || "")}</textarea>
      </label>
    `;
  }

  function readAdminActionForm(form) {
    const formData = new FormData(form);
    const payload = {
      name: formData.get("name")?.toString().trim() || "",
      sets: Number(formData.get("sets") || 1),
      reps: Number(formData.get("reps") || 1),
      frequency: formData.get("frequency")?.toString().trim() || null,
      description: formData.get("description")?.toString().trim() || null,
      contraindications: formData.get("contraindications")?.toString().trim() || null,
      body_regions: parseAdminList(formData.get("body_regions")),
      target_conditions: parseAdminList(formData.get("target_conditions")),
    };
    const id = formData.get("id")?.toString().trim();
    if (id) payload.id = id;
    return payload;
  }

  function renderAdminTestReport(report) {
    if (!report) {
      return `<div class="admin-test-report" id="admin-test-report-section">
        <h3>测试报告</h3>
        <p class="hint">暂无报告。可在 backend 目录运行 <code>python run_backend_tests.py</code> 生成。</p>
      </div>`;
    }
    const statusClass = report.status === "passed" ? "admin-status-passed" : "admin-status-failed";
    return `<div class="admin-test-report" id="admin-test-report-section">
      <h3>测试报告</h3>
      <p class="admin-test-summary ${statusClass}">
        ${report.passed}/${report.total} 通过 · 状态 ${escapeAdminText(report.status)}
        ${report.generated_at ? ` · ${escapeAdminText(report.generated_at.slice(0, 19).replace("T", " "))}` : ""}
      </p>
      <ul class="admin-test-cases">
        ${(report.cases || [])
          .map(
            (item) =>
              `<li class="${item.status === "passed" ? "passed" : "failed"}">${escapeAdminText(item.name)} · ${escapeAdminText(item.detail || item.status)}</li>`
          )
          .join("")}
      </ul>
      ${report.note ? `<p class="hint">${escapeAdminText(report.note)}</p>` : ""}
    </div>`;
  }

  function getAdminScrollOffset() {
    const header = document.querySelector(".app-header");
    const quickNav = document.getElementById("admin-quick-nav");
    let offset = (header?.getBoundingClientRect().height || 0) + 16;
    if (quickNav && !quickNav.hidden) {
      offset += quickNav.getBoundingClientRect().height + 12;
    }
    return offset;
  }

  function clearAdminScrollFocusTimer() {
    if (state.adminScrollFocusTimer) {
      clearTimeout(state.adminScrollFocusTimer);
      state.adminScrollFocusTimer = null;
    }
  }

  async function scrollAdminSection(sectionId, options = {}) {
    clearAdminScrollFocusTimer();

    let section = document.querySelector(`#page-admin #${sectionId}`);
    if (!section && options.waitForLoad) {
      await loadAdminActions({ silent: true });
      section = document.querySelector(`#page-admin #${sectionId}`);
    }
    if (!section) return;

    if (options.blurActive !== false && document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }

    const top = section.getBoundingClientRect().top + window.scrollY - getAdminScrollOffset();
    window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });

    if (options.focusSelector) {
      state.adminScrollFocusTimer = window.setTimeout(() => {
        section.querySelector(options.focusSelector)?.focus({ preventScroll: true });
        state.adminScrollFocusTimer = null;
      }, 350);
    }
  }

  function bindAdminQuickNavEvents() {
    if (!els.adminQuickNav || els.adminQuickNav.dataset.bound === "true") return;
    els.adminQuickNav.dataset.bound = "true";

    els.adminQuickNav.addEventListener("click", (event) => {
      const button = event.target.closest("[data-admin-target]");
      if (!button) return;

      const target = button.dataset.adminTarget;
      if (target === "admin-create-section") {
        scrollAdminSection(target, {
          waitForLoad: true,
          focusSelector: 'input[name="id"]',
        });
        return;
      }

      scrollAdminSection(target, { waitForLoad: true, blurActive: true });
    });
  }

  function renderAdminActionCard(action) {
    const editing = state.adminEditingId === action.id;
    const regions = (action.body_regions || []).join("、") || "未标注";
    const conditions = (action.target_conditions || []).slice(0, 3).join("、") || "未标注";
    return `
      <article class="admin-action-card" data-action-id="${escapeAdminText(action.id)}">
        <div class="admin-action-head">
          <div>
            <h4>${escapeAdminText(action.name)}</h4>
            <p class="admin-action-meta"><code>${escapeAdminText(action.id || "无ID")}</code> · ${action.sets ?? "-"} 组 × ${action.reps ?? "-"} 次${action.frequency ? ` · ${escapeAdminText(action.frequency)}` : ""}</p>
            <p class="hint">部位：${escapeAdminText(regions)} · 适应：${escapeAdminText(conditions)}</p>
          </div>
          <div class="admin-action-buttons">
            <button class="btn btn-secondary btn-small admin-edit-action" type="button" data-action-id="${escapeAdminText(action.id)}">${editing ? "收起" : "编辑"}</button>
            <button class="btn btn-secondary btn-small admin-delete-action" type="button" data-action-id="${escapeAdminText(action.id)}">删除</button>
          </div>
        </div>
        ${
          editing
            ? `<form class="admin-form admin-edit-form" data-action-id="${escapeAdminText(action.id)}">
                ${renderAdminActionFormFields(action, "edit")}
                <div class="admin-form-actions">
                  <button class="btn btn-primary btn-small" type="submit">保存修改</button>
                  <button class="btn btn-secondary btn-small admin-cancel-edit" type="button">取消</button>
                </div>
              </form>`
            : ""
        }
      </article>
    `;
  }

  function renderAdminActionListInner(actions) {
    if (!actions.length) {
      return `<p class="hint">没有匹配的动作，请调整筛选条件或新增动作。</p>`;
    }
    return `<div class="admin-action-cards">${actions.map((action) => renderAdminActionCard(action)).join("")}</div>`;
  }

  function renderAdminDashboardSection(dashboard) {
    if (!dashboard) {
      return `<section class="admin-section" id="admin-dashboard-section">
        <h3>数据统计</h3>
        <p class="hint">暂无统计数据。</p>
      </section>`;
    }
    const totals = dashboard.totals || {};
    const recent = dashboard.recent_activity || {};
    const feedback = dashboard.feedback_summary || {};
    const risk = dashboard.risk_summary || {};
    return `<section class="admin-section" id="admin-dashboard-section">
      <h3>数据统计</h3>
      <div class="admin-meta-grid">
        <div class="admin-meta-card"><span class="admin-meta-value">${totals.users ?? 0}</span><span class="admin-meta-label">注册用户</span></div>
        <div class="admin-meta-card"><span class="admin-meta-value">${totals.prescriptions ?? 0}</span><span class="admin-meta-label">处方总数</span></div>
        <div class="admin-meta-card"><span class="admin-meta-value">${totals.training_checkins ?? 0}</span><span class="admin-meta-label">训练打卡</span></div>
        <div class="admin-meta-card"><span class="admin-meta-value">${totals.user_feedback ?? 0}</span><span class="admin-meta-label">用户反馈</span></div>
        <div class="admin-meta-card"><span class="admin-meta-value">${totals.actions ?? 0}</span><span class="admin-meta-label">动作库条目</span></div>
        <div class="admin-meta-card"><span class="admin-meta-value">${feedback.open_count ?? 0}</span><span class="admin-meta-label">待处理反馈</span></div>
      </div>
      <div class="admin-meta-grid">
        <div class="admin-meta-card admin-meta-wide">
          <span class="admin-meta-label">近 7 日活跃</span>
          <span class="hint">新用户 ${recent.new_users_7d ?? 0} · 新处方 ${recent.new_prescriptions_7d ?? 0} · 打卡 ${recent.training_checkins_7d ?? 0} · 反馈 ${recent.feedback_7d ?? 0}</span>
        </div>
        <div class="admin-meta-card admin-meta-wide">
          <span class="admin-meta-label">影像风险预警</span>
          <span class="hint">中高风险报告 ${risk.red_flag_reports ?? 0} 条</span>
        </div>
      </div>
    </section>`;
  }

  function renderAdminUsersSection(users) {
    const rows = (users || [])
      .map(
        (user) => `<tr>
          <td>${escapeAdminText(user.nickname)}<br><span class="hint">${escapeAdminText(user.account)}</span></td>
          <td>${escapeAdminText(user.role)}</td>
          <td>${user.prescription_count ?? 0}</td>
          <td>${user.training_checkin_count ?? 0}</td>
          <td>${user.feedback_count ?? 0}</td>
          <td>${formatShortDate(user.created_at)}</td>
        </tr>`
      )
      .join("");
    return `<section class="admin-section" id="admin-users-section">
      <div class="admin-section-head">
        <h3>用户管理</h3>
        <span class="hint">共 ${(users || []).length} 条</span>
      </div>
      <div class="admin-toolbar">
        <label class="admin-filter">搜索用户
          <input id="admin-user-filter-q" type="search" placeholder="账号、昵称…" value="${escapeAdminText(state.adminUserFilter.q)}" />
        </label>
        <button class="btn btn-secondary btn-small" id="admin-refresh-users" type="button">刷新</button>
      </div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr><th>用户</th><th>角色</th><th>处方</th><th>打卡</th><th>反馈</th><th>注册时间</th></tr></thead>
          <tbody>${rows || "<tr><td colspan=\"6\" class=\"hint\">暂无用户数据</td></tr>"}</tbody>
        </table>
      </div>
    </section>`;
  }

  function renderAdminFeedbackCard(item) {
    const statusOptions = ["open", "processing", "resolved", "closed"]
      .map(
        (s) =>
          `<option value="${s}"${item.status === s ? " selected" : ""}>${s === "open" ? "待处理" : s === "processing" ? "处理中" : s === "resolved" ? "已解决" : "已关闭"}</option>`
      )
      .join("");
    const stars = item.rating ? "★".repeat(item.rating) + "☆".repeat(5 - item.rating) : "未评分";
    return `<article class="admin-feedback-card" data-feedback-id="${item.id}">
      <div class="admin-feedback-head">
        <div>
          <strong>${escapeAdminText(item.user_nickname || item.user_account || "匿名用户")}</strong>
          <span class="admin-feedback-meta">${escapeAdminText(item.category)} · ${stars} · ${formatShortDate(item.created_at)}</span>
        </div>
        <span class="admin-feedback-status status-${escapeAdminText(item.status)}">${escapeAdminText(item.status)}</span>
      </div>
      <p>${escapeAdminText(item.content)}</p>
      <form class="admin-feedback-update-form" data-feedback-id="${item.id}">
        <label class="admin-field">处理状态
          <select name="status">${statusOptions}</select>
        </label>
        <label class="admin-field admin-field-wide">管理员备注
          <input name="admin_note" type="text" value="${escapeAdminText(item.admin_note || "")}" placeholder="可选" />
        </label>
        <button class="btn btn-primary btn-small" type="submit">更新</button>
      </form>
    </article>`;
  }

  function renderAdminFeedbackSection(feedbackItems) {
    const statusFilter = state.adminFeedbackFilters.status;
    const categoryFilter = state.adminFeedbackFilters.category;
    const cards = (feedbackItems || []).map(renderAdminFeedbackCard).join("");
    return `<section class="admin-section" id="admin-feedback-section">
      <div class="admin-section-head">
        <h3>反馈管理</h3>
        <span class="hint">共 ${(feedbackItems || []).length} 条</span>
      </div>
      <div class="admin-toolbar">
        <label class="admin-filter">状态
          <select id="admin-feedback-status">
            <option value="">全部</option>
            <option value="open"${statusFilter === "open" ? " selected" : ""}>待处理</option>
            <option value="processing"${statusFilter === "processing" ? " selected" : ""}>处理中</option>
            <option value="resolved"${statusFilter === "resolved" ? " selected" : ""}>已解决</option>
            <option value="closed"${statusFilter === "closed" ? " selected" : ""}>已关闭</option>
          </select>
        </label>
        <label class="admin-filter">类别
          <select id="admin-feedback-category">
            <option value="">全部</option>
            <option value="prescription"${categoryFilter === "prescription" ? " selected" : ""}>处方反馈</option>
            <option value="general"${categoryFilter === "general" ? " selected" : ""}>一般反馈</option>
          </select>
        </label>
        <button class="btn btn-secondary btn-small" id="admin-refresh-feedback" type="button">刷新</button>
      </div>
      <div class="admin-feedback-list">${cards || "<p class=\"hint\">暂无反馈记录</p>"}</div>
    </section>`;
  }

  function renderAdminPanel({ actions, meta, deploy, testReport, dashboard, users, feedbackItems }) {
    const regionOptions = (meta?.body_regions || [])
      .map(
        (region) =>
          `<option value="${escapeAdminText(region)}"${state.adminFilters.bodyRegion === region ? " selected" : ""}>${escapeAdminText(region)}</option>`
      )
      .join("");

    return `
      ${renderAdminDashboardSection(dashboard)}
      ${renderAdminUsersSection(users)}
      ${renderAdminFeedbackSection(feedbackItems)}

      <div class="admin-toolbar">
        <label class="admin-filter">关键词
          <input id="admin-filter-q" type="search" placeholder="名称、ID、说明…" value="${escapeAdminText(state.adminFilters.q)}" />
        </label>
        <label class="admin-filter">部位
          <select id="admin-filter-region">
            <option value="">全部部位</option>
            ${regionOptions}
          </select>
        </label>
        <button class="btn btn-secondary btn-small" id="admin-refresh" type="button">刷新</button>
        <button class="btn btn-secondary btn-small" id="admin-open-docs" type="button">打开 API 文档</button>
      </div>

      <div class="admin-meta-grid">
        <div class="admin-meta-card">
          <span class="admin-meta-value">${meta?.total ?? actions.length}</span>
          <span class="admin-meta-label">知识库动作</span>
        </div>
        <div class="admin-meta-card">
          <span class="admin-meta-value" id="admin-filtered-count">${actions.length}</span>
          <span class="admin-meta-label">当前筛选结果</span>
        </div>
        ${
          deploy
            ? `<div class="admin-meta-card admin-meta-wide">
                <span class="admin-meta-label">部署环境</span>
                <span class="hint">${escapeAdminText(deploy.environment)} · 数据库 ${escapeAdminText(deploy.database)}</span>
              </div>`
            : ""
        }
      </div>

      ${renderAdminTestReport(testReport)}

      <section class="admin-section" id="admin-create-section">
        <h3>新增动作</h3>
        <form class="admin-form" id="admin-create-form">
          ${renderAdminActionFormFields({}, "create")}
          <div class="admin-form-actions">
            <button class="btn btn-primary" type="submit">添加动作</button>
          </div>
        </form>
      </section>

      <section class="admin-section" id="admin-list-section">
        <div class="admin-section-head">
          <h3>动作列表</h3>
          <span class="hint" id="admin-action-count">共 ${actions.length} 条</span>
        </div>
        <div id="admin-action-list-root">
          ${renderAdminActionListInner(actions)}
        </div>
      </section>
    `;
  }

  function renderAdminPanelToDom(data) {
    if (!els.adminActionsPanel) return;
    els.adminActionsPanel.innerHTML = renderAdminPanel(data);
    state.adminPanelData = data;
  }

  function refreshAdminActionList(options = {}) {
    const data = state.adminPanelData;
    if (!data || !els.adminActionsPanel) return;

    const listRoot = els.adminActionsPanel.querySelector("#admin-action-list-root");
    if (!listRoot) {
      renderAdminPanelToDom(data);
      return;
    }

    listRoot.innerHTML = renderAdminActionListInner(data.actions);
    const countEl = els.adminActionsPanel.querySelector("#admin-action-count");
    if (countEl) countEl.textContent = `共 ${data.actions.length} 条`;
    const filteredCountEl = els.adminActionsPanel.querySelector("#admin-filtered-count");
    if (filteredCountEl) filteredCountEl.textContent = String(data.actions.length);

    if (options.focusActionId) {
      requestAnimationFrame(() => {
        const card = listRoot.querySelector(
          `.admin-action-card[data-action-id="${CSS.escape(options.focusActionId)}"]`
        );
        card?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      });
    }
  }

  function toggleAdminActionEdit(actionId) {
    state.adminEditingId = state.adminEditingId === actionId ? null : actionId;
    refreshAdminActionList({
      focusActionId: state.adminEditingId,
    });
  }

  async function fetchAdminTestReport() {
    try {
      const response = await fetchWithTimeout(`${window.APP_CONFIG.API_BASE}/admin/test_report`, {
        headers: authHeaders(),
      });
      if (response.status === 404) return null;
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  }

  async function fetchAdminUsers() {
    const params = new URLSearchParams();
    if (state.adminUserFilter.q?.trim()) params.set("q", state.adminUserFilter.q.trim());
    params.set("limit", "50");
    const query = params.toString();
    return apiGet(`/admin/users${query ? `?${query}` : ""}`);
  }

  async function fetchAdminFeedback() {
    const params = new URLSearchParams();
    if (state.adminFeedbackFilters.status) params.set("status", state.adminFeedbackFilters.status);
    if (state.adminFeedbackFilters.category) params.set("category", state.adminFeedbackFilters.category);
    params.set("limit", "50");
    const query = params.toString();
    return apiGet(`/admin/feedback${query ? `?${query}` : ""}`);
  }

  async function fetchAdminDashboard() {
    return apiGet(`/admin/dashboard`);
  }

  async function updateAdminFeedback(feedbackId, payload) {
    try {
      return await apiSend("PUT", `/admin/feedback/${feedbackId}`, payload);
    } catch (error) {
      throw new Error(error.message || "更新失败");
    }
  }

  async function loadAdminActions(options = {}) {
    if (!els.adminActionsPanel) return;
    const { silent = false } = options;
    const scrollY = window.scrollY;

    if (window.APP_CONFIG.DEMO_MODE) {
      if (!silent) {
        renderDemoNotice(els.adminActionsPanel, { featureName: "管理后台" });
      }
      return;
    }
    if (state.currentUser?.role !== "admin") {
      if (!silent) {
        els.adminActionsPanel.innerHTML = "<p class=\"hint\">需要管理员账号才能访问管理后台。</p>";
      }
      return;
    }

    if (!silent) {
      els.adminActionsPanel.innerHTML = `<p class="hint">正在加载管理后台…</p>`;
    }

    try {
      const [actionsRes, metaRes, deployRes, testReport, dashboard, users, feedbackItems] = await Promise.all([
        fetchWithTimeout(buildAdminActionsUrl(), { headers: authHeaders() }, window.APP_CONFIG.LIST_TIMEOUT_MS),
        fetchWithTimeout(`${window.APP_CONFIG.API_BASE}/admin/actions/meta`, { headers: authHeaders() }, window.APP_CONFIG.LIST_TIMEOUT_MS),
        fetchWithTimeout(`${window.APP_CONFIG.API_BASE}/deployment/info`, {}, window.APP_CONFIG.LIST_TIMEOUT_MS),
        fetchAdminTestReport(),
        fetchAdminDashboard().catch(() => null),
        fetchAdminUsers().catch(() => []),
        fetchAdminFeedback().catch(() => []),
      ]);
      if (!actionsRes.ok) throw new Error("admin actions unavailable");
      const actions = await actionsRes.json();
      const meta = metaRes.ok ? await metaRes.json() : null;
      const deploy = deployRes.ok ? await deployRes.json() : null;
      renderAdminPanelToDom({ actions, meta, deploy, testReport, dashboard, users, feedbackItems });
      if (silent) {
        window.scrollTo(0, scrollY);
      }
    } catch {
      renderLoadError(els.adminActionsPanel, {
        message: "管理员面板加载失败，请确认账号具备 admin 权限且后端已启动。",
        onRetry: () => loadAdminActions(),
      });
      state.adminPanelData = null;
    }
  }

  async function submitAdminCreate(form) {
    const payload = readAdminActionForm(form);
    if (!payload.id || !payload.name) {
      showToast("请填写动作 ID 和名称");
      return;
    }
    const response = await fetchWithTimeout(`${window.APP_CONFIG.API_BASE}/admin/actions`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await parseApiError(response);
      throw new Error(typeof detail === "string" ? detail : "新增动作失败");
    }
    form.reset();
    showToast("动作已添加");
    state.adminEditingId = null;
    await loadAdminActions({ silent: true });
  }

  async function submitAdminEdit(actionId, form) {
    const payload = readAdminActionForm(form);
    delete payload.id;
    const response = await fetchWithTimeout(`${window.APP_CONFIG.API_BASE}/admin/actions/${encodeURIComponent(actionId)}`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await parseApiError(response);
      throw new Error(typeof detail === "string" ? detail : "保存失败");
    }
    showToast("动作已更新");
    state.adminEditingId = null;
    await loadAdminActions({ silent: true });
  }

  async function deleteAdminAction(actionId) {
    if (!actionId) return;
    if (!window.confirm(`确定删除动作「${actionId}」吗？此操作不可撤销。`)) return;
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/admin/actions/${encodeURIComponent(actionId)}`,
      {
        method: "DELETE",
        headers: authHeaders(),
      }
    );
    if (!response.ok) {
      const detail = await parseApiError(response);
      throw new Error(typeof detail === "string" ? detail : "删除失败");
    }
    showToast("动作已删除");
    if (state.adminEditingId === actionId) state.adminEditingId = null;
    await loadAdminActions({ silent: true });
  }

  function bindAdminPanelEvents() {
    if (!els.adminActionsPanel || els.adminActionsPanel.dataset.bound === "true") return;
    els.adminActionsPanel.dataset.bound = "true";

    els.adminActionsPanel.addEventListener("click", async (event) => {
      if (state.currentUser?.role !== "admin") return;

      const docsButton = event.target.closest("#admin-open-docs");
      if (docsButton) {
        window.open(getApiDocsUrl(), "_blank", "noopener");
        return;
      }

      const refreshButton = event.target.closest("#admin-refresh");
      if (refreshButton) {
        await loadAdminActions();
        showToast("已刷新");
        return;
      }

      const refreshUsersButton = event.target.closest("#admin-refresh-users");
      if (refreshUsersButton) {
        await loadAdminActions({ silent: true });
        showToast("用户列表已刷新");
        return;
      }

      const refreshFeedbackButton = event.target.closest("#admin-refresh-feedback");
      if (refreshFeedbackButton) {
        await loadAdminActions({ silent: true });
        showToast("反馈列表已刷新");
        return;
      }

      const editButton = event.target.closest(".admin-edit-action");
      if (editButton) {
        toggleAdminActionEdit(editButton.dataset.actionId);
        return;
      }

      const cancelButton = event.target.closest(".admin-cancel-edit");
      if (cancelButton) {
        state.adminEditingId = null;
        refreshAdminActionList();
        return;
      }

      const deleteButton = event.target.closest(".admin-delete-action");
      if (deleteButton) {
        try {
          await deleteAdminAction(deleteButton.dataset.actionId);
        } catch (error) {
          showErrorToast(error.message || "删除失败");
        }
        return;
      }
    });

    els.adminActionsPanel.addEventListener("change", async (event) => {
      if (state.currentUser?.role !== "admin") return;
      if (event.target.id === "admin-filter-region") {
        state.adminFilters.bodyRegion = event.target.value;
        await loadAdminActions({ silent: true });
      }
      if (event.target.id === "admin-feedback-status") {
        state.adminFeedbackFilters.status = event.target.value;
        await loadAdminActions({ silent: true });
      }
      if (event.target.id === "admin-feedback-category") {
        state.adminFeedbackFilters.category = event.target.value;
        await loadAdminActions({ silent: true });
      }
    });

    els.adminActionsPanel.addEventListener("input", (event) => {
      if (state.currentUser?.role !== "admin") return;
      if (event.target.id === "admin-user-filter-q") {
        state.adminUserFilter.q = event.target.value;
        adminUserFilterDebounced();
        return;
      }
      if (event.target.id !== "admin-filter-q") return;
      state.adminFilters.q = event.target.value;
      adminFilterDebounced();
    });

    els.adminActionsPanel.addEventListener("submit", async (event) => {
      if (state.currentUser?.role !== "admin") return;
      const createForm = event.target.closest("#admin-create-form");
      if (createForm) {
        event.preventDefault();
        try {
          await submitAdminCreate(createForm);
        } catch (error) {
          showErrorToast(error.message || "新增动作失败");
        }
        return;
      }

      const editForm = event.target.closest(".admin-edit-form");
      if (editForm) {
        event.preventDefault();
        try {
          await submitAdminEdit(editForm.dataset.actionId, editForm);
        } catch (error) {
          showErrorToast(error.message || "保存失败");
        }
        return;
      }

      const feedbackForm = event.target.closest(".admin-feedback-update-form");
      if (feedbackForm) {
        event.preventDefault();
        const formData = new FormData(feedbackForm);
        const payload = {
          status: formData.get("status")?.toString() || undefined,
          admin_note: formData.get("admin_note")?.toString().trim() || undefined,
        };
        try {
          await updateAdminFeedback(Number(feedbackForm.dataset.feedbackId), payload);
          showToast("反馈已更新");
          await loadAdminActions({ silent: true });
        } catch (error) {
          showErrorToast(error.message || "更新失败");
        }
      }
    });
  }

  return {
    loadAdminActions,
    bindAdminPanelEvents,
    bindAdminQuickNavEvents,
    scrollAdminSection,
    refreshAdminActionList,
  };
}
