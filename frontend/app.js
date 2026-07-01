import { PoseTracker } from "./pose.js?v=20260630e";
import {
  escapeHtml,
  escapeAdminText,
  formatShortDate,
  todayIsoDate,
  formatVasAxisLabel,
  vasChartLabelStep,
  debounce,
  renderDemoNotice,
  renderLoadError,
} from "./shared/ui.js";
import {
  ApiError,
  parseApiError,
  parseApiErrorDetail,
} from "./shared/api.js";
import { state, registerStepLoader, setStepNavEl, makeGoToStep } from "./shared/state.js";
import { createKnowledgePage } from "./pages/knowledge.js";
import { createAdminPage } from "./pages/admin.js";
import { createProfilesPage } from "./pages/profiles.js";
import { createCollaborationPage } from "./pages/collaboration.js";

// Debounced filter reloads (replaces the previous window.*Timer globals).
// knowledgeFilterDebounced is declared alongside the knowledge page module below.
const libraryFilterDebounced = debounce(() => renderActionLibraryGrid(), 200);

const els = {
  stepButtons: () => document.querySelectorAll(".step-item"),
  pages: () => document.querySelectorAll(".page"),
  apiLoginPanel: document.getElementById("api-login-panel"),
  authLoginWrap: document.getElementById("auth-login-wrap"),
  authRegisterWrap: document.getElementById("auth-register-wrap"),
  authLoginForm: document.getElementById("auth-login-form"),
  authRegisterForm: document.getElementById("auth-register-form"),
  authTabs: () => document.querySelectorAll(".auth-tab"),
  userIdentity: document.getElementById("user-identity"),
  userAvatar: document.getElementById("user-avatar"),
  userDisplayName: document.getElementById("user-display-name"),
  painRegions: document.getElementById("pain-regions"),
  mobilityScore: document.getElementById("mobility-score"),
  mobilityValue: document.getElementById("mobility-value"),
  intakeForm: document.getElementById("intake-form"),
  symptomsError: document.getElementById("symptoms-error"),
  painRegionsError: document.getElementById("pain-regions-error"),
  prescriptionMeta: document.getElementById("prescription-meta"),
  prescriptionRecap: document.getElementById("prescription-recap"),
  prescriptionSummary: document.getElementById("prescription-summary"),
  actionList: document.getElementById("action-list"),
  prescriptionHistory: document.getElementById("prescription-history"),
  historyUserName: document.getElementById("history-user-name"),
  historyUserMeta: document.getElementById("history-user-meta"),
  doubaoResultPanel: document.getElementById("doubao-result-panel"),
  doubaoResult: document.getElementById("doubao-result"),
  loadingOverlay: document.getElementById("loading-overlay"),
  loadingText: document.getElementById("loading-text"),
  loadingProgressBar: document.getElementById("loading-progress-bar"),
  loadingPercent: document.getElementById("loading-percent"),
  trainingActionName: document.getElementById("training-action-name"),
  videoShell: document.getElementById("video-shell"),
  video: document.getElementById("video"),
  overlay: document.getElementById("overlay"),
  videoPlaceholder: document.getElementById("video-placeholder"),
  cameraLoading: document.getElementById("camera-loading"),
  cameraLoadingText: document.getElementById("camera-loading-text"),
  startCameraButton: document.getElementById("start-camera"),
  feedbackOverlay: document.getElementById("feedback-overlay"),
  scoreBadge: document.getElementById("score-badge"),
  statusDot: document.getElementById("status-dot"),
  statusText: document.getElementById("status-text"),
  feedbackList: document.getElementById("feedback-list"),
  modeBadge: document.getElementById("mode-badge"),
  toast: document.getElementById("toast"),
  toastMessage: document.getElementById("toast-message"),
  toastClose: document.getElementById("toast-close"),
  authAccount: document.getElementById("auth-account"),
  authPassword: document.getElementById("auth-password"),
  authRegisterAccount: document.getElementById("auth-register-account"),
  authRegisterPassword: document.getElementById("auth-register-password"),
  authNickname: document.getElementById("auth-nickname"),
  authGender: document.getElementById("auth-gender"),
  authAge: document.getElementById("auth-age"),
  logoutButton: document.getElementById("logout-button"),
  testDoubaoButton: document.getElementById("test-doubao"),
  headerActions: document.getElementById("header-actions"),
  headerMenuToggle: document.getElementById("header-menu-toggle"),
  patientProfileSelect: document.getElementById("patient-profile-select"),
  prescriptionExportBar: document.getElementById("prescription-export-bar"),
  trainingStatsPanel: document.getElementById("training-stats-panel"),
  checkinPainBefore: document.getElementById("checkin-pain-before"),
  checkinPainAfter: document.getElementById("checkin-pain-after"),
  checkinNote: document.getElementById("checkin-note"),
  adminEntryButton: document.getElementById("go-admin"),
  profilesEntryButton: document.getElementById("go-profiles"),
  libraryEntryButton: document.getElementById("go-library"),
  adminActionsPanel: document.getElementById("admin-actions-panel"),
  adminQuickNav: document.getElementById("admin-quick-nav"),
  mobilityTier: document.getElementById("mobility-tier"),
  mobilityGuideCards: document.getElementById("mobility-guide-cards"),
  redFlagOverlay: document.getElementById("red-flag-overlay"),
  redFlagMessage: document.getElementById("red-flag-message"),
  redFlagList: document.getElementById("red-flag-list"),
  mobilitySummary: document.getElementById("mobility-summary"),
  imagingSectionWrap: document.getElementById("imaging-section-wrap"),
  imagingSection: document.getElementById("imaging-section"),
  imagingReportsList: document.getElementById("imaging-reports-list"),
  profilesList: document.getElementById("profiles-list"),
  profileFormCard: document.getElementById("profile-form-card"),
  profileForm: document.getElementById("profile-form"),
  profilePainRegions: document.getElementById("profile-pain-regions"),
  libraryGrid: document.getElementById("library-grid"),
  goProgressButton: document.getElementById("go-progress"),
  progressStatsGrid: document.getElementById("progress-stats-grid"),
  progressVasChart: document.getElementById("progress-vas-chart"),
  progressCompletion: document.getElementById("progress-completion"),
  progressReport: document.getElementById("progress-report"),
  progressReportActions: document.getElementById("progress-report-actions"),
  knowledgeEntryButton: document.getElementById("go-knowledge"),
  knowledgeArticlesList: document.getElementById("knowledge-articles-list"),
  knowledgePreventionList: document.getElementById("knowledge-prevention-list"),
  knowledgeQaResult: document.getElementById("knowledge-qa-result"),
  knowledgePainRegions: document.getElementById("knowledge-pain-regions"),
  prescriptionFeedbackCard: document.getElementById("prescription-feedback-card"),
  prescriptionFeedbackForm: document.getElementById("prescription-feedback-form"),
  prescriptionCollaborationCard: document.getElementById("prescription-collaboration-card"),
  progressAdjustments: document.getElementById("progress-adjustments"),
  collaborationEntryButton: document.getElementById("go-collaboration"),
  collaborationPanel: document.getElementById("collaboration-panel"),
  doctorEntryButton: document.getElementById("go-doctor"),
  doctorWorkspace: document.getElementById("doctor-workspace"),
};

const AUTH_TOKEN_KEY = "kj_auth_token";
const AUTH_USER_KEY = "kj_auth_user";
const LEGACY_AUTH_KEY = "kj_auth";

function readStoredAuth() {
  try {
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY);
    const userRaw = localStorage.getItem(AUTH_USER_KEY);
    if (token && userRaw) {
      return { token, user: JSON.parse(userRaw) };
    }
    const legacyRaw = localStorage.getItem(LEGACY_AUTH_KEY);
    if (legacyRaw) {
      const legacy = JSON.parse(legacyRaw);
      if (legacy?.token) {
        saveAuth(legacy);
        return legacy;
      }
    }
    return null;
  } catch (error) {
    return null;
  }
}

function saveAuth(auth) {
  if (auth?.token) {
    state.auth = auth;
    sessionStorage.setItem(AUTH_TOKEN_KEY, auth.token);
    if (auth.user) {
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(auth.user));
    }
    localStorage.removeItem(LEGACY_AUTH_KEY);
    syncCurrentUserFromAuth();
  } else {
    state.auth = null;
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    localStorage.removeItem(LEGACY_AUTH_KEY);
  }
  updateAuthStatus();
}

function syncCurrentUserFromAuth() {
  if (!state.auth?.user) return;
  state.currentUser = {
    id: state.auth.user.id,
    account: state.auth.user.account,
    name: state.auth.user.nickname,
    age: state.auth.user.age ?? null,
    gender: state.auth.user.gender ?? null,
    role: state.auth.user.role ?? "user",
  };
  updateUserIdentity();
  updateAdminEntry();
}

function isSessionReady() {
  return Boolean(state.auth?.token);
}

function authHeaders(extra = {}) {
  return state.auth?.token
    ? { ...extra, Authorization: `Bearer ${state.auth.token}` }
    : extra;
}

function requireLogin() {
  if (isSessionReady()) {
    return true;
  }
  showWarnToast("请先登录或注册后再继续");
  goToStep("login");
  return false;
}

function updateAuthStatus() {
  const loggedIn = isSessionReady();
  if (els.logoutButton) {
    els.logoutButton.hidden = !loggedIn;
  }
  updateUserIdentity();
}

function switchAuthTab(tab) {
  state.authTab = tab;
  els.authTabs().forEach((button) => {
    const active = button.dataset.authTab === tab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
  if (els.authLoginWrap) els.authLoginWrap.hidden = tab !== "login";
  if (els.authRegisterWrap) els.authRegisterWrap.hidden = tab !== "register";
}

function clearAuthErrors() {
  [
    "auth-account-error",
    "auth-password-error",
    "auth-register-account-error",
    "auth-register-password-error",
    "auth-nickname-error",
    "auth-age-error",
  ].forEach((id) => {
    const node = document.getElementById(id);
    if (node) node.textContent = "";
  });
}

function readAuthPayload(mode) {
  if (mode === "login") {
    const formData = new FormData(els.authLoginForm);
    return {
      account: formData.get("account")?.toString().trim() || "",
      password: formData.get("password")?.toString() || "",
    };
  }

  const formData = new FormData(els.authRegisterForm);
  const ageValue = formData.get("age");
  return {
    account: formData.get("account")?.toString().trim() || "",
    password: formData.get("password")?.toString() || "",
    nickname: formData.get("nickname")?.toString().trim() || "",
    gender: formData.get("gender")?.toString().trim() || null,
    age: ageValue ? Number(ageValue) : null,
  };
}

function validateAuthPayload(mode, payload) {
  clearAuthErrors();
  let valid = true;

  const setError = (id, message) => {
    const node = document.getElementById(id);
    if (node) node.textContent = message;
    valid = false;
  };

  if (!payload.account) {
    setError(mode === "login" ? "auth-account-error" : "auth-register-account-error", "请输入账号");
  }
  if (!payload.password) {
    setError(mode === "login" ? "auth-password-error" : "auth-register-password-error", "请输入密码");
  } else if (payload.password.length < 6) {
    setError(mode === "login" ? "auth-password-error" : "auth-register-password-error", "密码至少 6 位");
  }
  if (mode === "register" && !payload.nickname) {
    setError("auth-nickname-error", "请输入姓名");
  }
  if (mode === "register" && (payload.age == null || payload.age < 1 || payload.age > 120)) {
    setError("auth-age-error", "请输入有效年龄");
  }

  return valid;
}

async function submitAuth(mode) {
  const payload = readAuthPayload(mode);
  if (!validateAuthPayload(mode, payload)) return;

  const endpoint = mode === "login" ? "login" : "register";
  setLoading(true, mode === "login" ? "正在登录…" : "正在注册…");
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/${endpoint}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      window.APP_CONFIG.AUTH_TIMEOUT_MS
    );

    if (!response.ok) {
      const detail = await parseApiError(response);
      showErrorToast(typeof detail === "string" ? detail : "账号或密码错误");
      return;
    }

    if (mode === "register") {
      showToast("注册成功，正在自动登录…");
      const loginResponse = await fetchWithTimeout(
        `${window.APP_CONFIG.API_BASE}/login`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            account: payload.account,
            password: payload.password,
          }),
        },
        window.APP_CONFIG.AUTH_TIMEOUT_MS
      );
      if (!loginResponse.ok) {
        switchAuthTab("login");
        if (els.authAccount) els.authAccount.value = payload.account;
        showToast("注册成功，请手动登录");
        return;
      }
      const loginData = await loginResponse.json();
      saveAuth({ token: loginData.token, user: loginData.user });
      clearPrescriptionSession();
      showToast(`欢迎你，${resolveDisplayName(loginData.user)}`);
      loadPatientProfiles();
      updateAdminEntry();
      goToStep("intake");
      return;
    }

    const data = await response.json();
    saveAuth({ token: data.token, user: data.user });
    clearPrescriptionSession();
    showToast(`欢迎你，${resolveDisplayName(data.user)}`);
    loadPatientProfiles();
    updateAdminEntry();
    goToStep("intake");
  } catch (error) {
    const isNetworkError = error instanceof TypeError;
    showErrorToast(
      error?.name === "AbortError"
        ? "登录请求超时，请确认后端已启动"
        : isNetworkError
          ? "无法连接后端，请确认后端服务已启动"
          : "登录失败，请稍后重试"
    );
  } finally {
    setLoading(false);
  }
}

function logoutSession() {
  saveAuth(null);
  state.currentUser = null;
  state.prescription = null;
  state.currentAction = null;
  stopCamera();
  clearPrescriptionSession();
  updateUserIdentity();
  if (els.prescriptionHistory) {
    els.prescriptionHistory.textContent = "请先登录后再查看历史处方。";
  }
  if (els.trainingStatsPanel) {
    els.trainingStatsPanel.hidden = true;
    els.trainingStatsPanel.innerHTML = "";
  }
  goToStep("login");
  showToast("已退出登录");
}

function hideToast() {
  if (!els.toast) return;
  window.clearTimeout(showToast.timer);
  els.toast.classList.remove("show", "toast-error", "toast-warn");
}

function showToast(message, options = {}) {
  if (!els.toast || !els.toastMessage) return;
  const type = options.type || "info";
  const duration =
    options.duration ??
    (type === "error" ? 5600 : type === "warn" ? 4800 : 3200);

  els.toastMessage.textContent = message;
  els.toast.classList.remove("toast-error", "toast-warn");
  if (type === "error") els.toast.classList.add("toast-error");
  if (type === "warn") els.toast.classList.add("toast-warn");
  els.toast.classList.add("show");

  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(hideToast, duration);
}

function showErrorToast(message, options = {}) {
  showToast(message, { ...options, type: "error" });
}

function showWarnToast(message, options = {}) {
  showToast(message, { ...options, type: "warn" });
}

function setLoading(active, text = "正在处理…", progress = null) {
  els.loadingOverlay.classList.toggle("active", active);
  els.loadingOverlay.setAttribute("aria-hidden", active ? "false" : "true");
  els.loadingText.textContent = text;
  const pct =
    progress === null
      ? active
        ? 35
        : 0
      : Math.max(0, Math.min(100, progress));
  if (els.loadingProgressBar) els.loadingProgressBar.style.width = `${pct}%`;
  if (els.loadingPercent) els.loadingPercent.textContent = `${Math.round(pct)}%`;
}

let prescriptionProgressTimer = null;

function startPrescriptionLoading() {
  stopPrescriptionLoading(false);
  const steps = window.APP_CONFIG.DEMO_MODE
    ? [
        { text: "正在验证问诊信息…", progress: 25 },
        { text: "正在匹配康复动作…", progress: 55 },
        { text: "正在生成本地 Mock 处方…", progress: 82 },
      ]
    : [
        { text: "正在验证问诊信息…", progress: 12 },
        { text: "正在匹配康复动作…", progress: 28 },
        { text: "正在调用 DeepSeek 大模型…", progress: 48 },
        { text: "正在生成处方摘要…", progress: 68 },
        { text: "正在整理处方内容…", progress: 86 },
      ];
  let stepIndex = 0;
  setLoading(true, steps[0].text, steps[0].progress);
  prescriptionProgressTimer = window.setInterval(() => {
    if (stepIndex < steps.length - 1) {
      stepIndex += 1;
      setLoading(true, steps[stepIndex].text, steps[stepIndex].progress);
    }
  }, 1800);
}

function finishPrescriptionLoading() {
  stopPrescriptionLoading(false);
  setLoading(true, "处方生成完成", 100);
  window.setTimeout(() => setLoading(false), 450);
}

function stopPrescriptionLoading(resetOverlay = true) {
  if (prescriptionProgressTimer) {
    window.clearInterval(prescriptionProgressTimer);
    prescriptionProgressTimer = null;
  }
  if (resetOverlay) setLoading(false);
}

const goToStep = makeGoToStep({
  isSessionReady,
  setHeaderMenuOpen,
  updateUserIdentity: () => updateUserIdentity(),
  onNavigate: () => setHeaderSecondaryOpen(false),
});

function sessionKey(base) {
  const userId = state.auth?.user?.id;
  return userId ? `${base}_${userId}` : base;
}

function savePrescriptionToSession(prescription, formData) {
  try {
    sessionStorage.setItem(sessionKey("kj_prescription"), JSON.stringify(prescription));
    if (formData) sessionStorage.setItem(sessionKey("kj_form_data"), JSON.stringify(formData));
    sessionStorage.setItem(sessionKey("kj_current_step"), state.currentStep || "prescription");
  } catch { /* quota exceeded or private mode */ }
}

function loadPrescriptionFromSession() {
  try {
    const raw = sessionStorage.getItem(sessionKey("kj_prescription"));
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function loadFormDataFromSession() {
  try {
    const raw = sessionStorage.getItem(sessionKey("kj_form_data"));
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function clearPrescriptionSession() {
  sessionStorage.removeItem(sessionKey("kj_prescription"));
  sessionStorage.removeItem(sessionKey("kj_form_data"));
  sessionStorage.removeItem(sessionKey("kj_current_step"));
  state.prescription = null;
}

function resolveDisplayName(user) {
  if (!user) return "未登录";
  const nickname = String(user.name || user.nickname || "").trim();
  if (nickname && !/^[\?？]+$/.test(nickname)) return nickname;
  return user.account || "用户";
}

function getMobilityTier(score) {
  if (score == null) return { label: "未评估", tier: "unknown" };
  if (score <= 4) return { label: "低活动度 · 低强度方案", tier: "low" };
  if (score <= 7) return { label: "中等活动度 · 常规方案", tier: "normal" };
  return { label: "较高活动度 · 可适当增加频次", tier: "high" };
}

function renderPrescriptionRecap(formData) {
  if (!els.prescriptionRecap || !formData) {
    if (els.prescriptionRecap) els.prescriptionRecap.hidden = true;
    return;
  }
  const mobility = getMobilityTier(formData.mobility_score);
  const regions = formData.pain_regions?.length
    ? formData.pain_regions.join("、")
    : "未选择";
  els.prescriptionRecap.hidden = false;
  els.prescriptionRecap.innerHTML = `
    <dl class="recap-grid">
      <dt>疼痛部位</dt><dd>${escapeHtml(regions)}</dd>
      <dt>主诉</dt><dd>${escapeHtml(formData.symptoms || "未填写")}</dd>
      <dt>伤病史</dt><dd>${escapeHtml(formData.history || "无")}</dd>
      <dt>活动度自评</dt><dd><span class="recap-mobility recap-mobility-${escapeHtml(mobility.tier)}">${escapeHtml(formData.mobility_score ?? "—")}/10 · ${escapeHtml(mobility.label)}</span></dd>
    </dl>
  `;
}

async function fetchWithTimeout(url, options = {}, timeoutMs = window.APP_CONFIG.FETCH_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

// True when the backend API is available (not in Demo mode) and the user is logged in.
function apiEnabled() {
  return isSessionReady() && !window.APP_CONFIG.DEMO_MODE;
}

// True when the backend API is available regardless of login state.
function apiReady() {
  return !window.APP_CONFIG.DEMO_MODE;
}

// Guard for handlers that need both login and a live backend.
// Shows a toast guiding the user and returns false; callers do `if (!requireApi()) return;`.
function requireApi() {
  if (window.APP_CONFIG.DEMO_MODE) {
    showWarnToast("该功能需要切换到 API 模式并登录后使用");
    return false;
  }
  return requireLogin();
}

// GET JSON with auth + timeout. Throws on non-2xx.
async function apiGet(path, { timeoutMs } = {}) {
  const response = await fetchWithTimeout(
    `${window.APP_CONFIG.API_BASE}${path}`,
    { headers: authHeaders() },
    timeoutMs
  );
  if (!response.ok) throw new ApiError(`HTTP ${response.status}`, response);
  return response.json();
}

// POST/PUT/DELETE with JSON body + auth + timeout. Returns parsed JSON (or null for empty).
async function apiSend(method, path, body, { timeoutMs } = {}) {
  const headers = authHeaders({ "Content-Type": "application/json" });
  const response = await fetchWithTimeout(
    `${window.APP_CONFIG.API_BASE}${path}`,
    {
      method,
      headers,
      body: body == null ? undefined : JSON.stringify(body),
    },
    timeoutMs
  );
  if (!response.ok) {
    const detail = await parseApiError(response);
    throw new ApiError(typeof detail === "string" ? detail : `${method} ${path} 失败`, response);
  }
  if (response.status === 204) return null;
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

function readFormData() {
  const formData = new FormData(els.intakeForm);
  const profileId = els.patientProfileSelect?.value;
  return {
    name: state.currentUser?.name || null,
    age: state.currentUser?.age || null,
    symptoms: formData.get("symptoms")?.toString().trim() || "",
    history: formData.get("history")?.toString().trim() || null,
    pain_regions: Array.from(state.selectedPainRegions),
    mobility_score: Number(formData.get("mobility_score") || 5),
    patient_profile_id: profileId ? Number(profileId) : null,
  };
}

const MEDICAL_HINTS = [
  "痛", "疼", "酸", "胀", "麻", "受限", "不适", "僵硬", "无力",
  "肿胀", "损伤", "劳损", "突出", "扭伤", "康复", "活动", "弯曲",
  "拉伸", "久坐", "炎症", "术后", "复发", "疲劳", "劳累", "受伤",
  "拉伤", "挫伤", "骨折", "压迫", "抽搐", "痉挛", "水肿",
];

const BODY_PART_HINTS = [
  "颈", "脖子", "肩", "肩膀", "腰", "背", "后背", "膝", "膝盖", "踝",
  "肘", "腕", "髋", "腿", "足", "头", "胸", "肌", "关节", "椎", "肩周",
  "腰椎", "颈椎", "胸椎", "髌", "跟腱", "足底", "手臂", "小腿", "大腿", "肩胛",
];

function isRehabRelated(text) {
  if (MEDICAL_HINTS.some((hint) => text.includes(hint))) return true;
  if (BODY_PART_HINTS.some((hint) => text.includes(hint))) return true;
  return false;
}

function validatePainRegions(painRegions = []) {
  if (!painRegions.length) {
    return "请至少选择一个疼痛部位";
  }
  return null;
}

function validateSymptoms(symptoms) {
  const text = symptoms.trim();
  if (!text) return "请填写主诉信息";
  if (text.length < 4) return "主诉描述过短，请至少用一句话说明症状与部位";
  if (/^\d+$/.test(text)) {
    return "主诉不能使用纯数字，请描述具体疼痛或活动受限情况";
  }
  if (/^[a-zA-Z]+$/.test(text)) {
    return "请使用中文描述症状，例如：颈部疼痛两周，转头受限";
  }
  if (/(.)\1{5,}/.test(text)) {
    return "主诉内容重复异常，请填写真实的伤病描述";
  }

  const chineseCount = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  if (chineseCount < 1) {
    return "主诉信息不明确，请描述部位、症状与持续时间，例如：腰痛一月，弯腰加重";
  }
  if (!isRehabRelated(text)) {
    return "主诉内容与康复伤病描述不符，请用规范语言描述具体症状，例如：腰部酸痛一月，久坐后加重";
  }
  return null;
}

function validateForm(formData) {
  const painRegionError = validatePainRegions(formData.pain_regions);
  const symptomError = validateSymptoms(formData.symptoms);

  els.painRegionsError.textContent = painRegionError || "";
  els.symptomsError.textContent = symptomError || "";

  if (painRegionError) {
    focusIntakeField(document.querySelector(".pain-field") || els.painRegions);
    return false;
  }
  if (symptomError) {
    focusIntakeField(document.getElementById("symptoms"));
    return false;
  }
  return true;
}

function focusIntakeField(element) {
  if (!element) return;
  const collapsible = element.closest("details.intake-collapsible");
  if (collapsible && !collapsible.open) collapsible.open = true;
  window.requestAnimationFrame(() => {
    element.scrollIntoView({ behavior: "smooth", block: "center" });
    const focusTarget =
      element.matches("textarea, input, select, button")
        ? element
        : element.querySelector("textarea, input, select, button");
    focusTarget?.focus({ preventScroll: true });
  });
}

function formatSummary(summary) {
  const text = normalizeSummaryText(summary);
  return text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => `<p>${escapeAdminText(line)}</p>`)
    .join("");
}

function normalizeSummaryText(summary, _depth) {
  if (_depth > 3) return "";
  const depth = (_depth || 0) + 1;

  if (summary == null) return "";

  if (typeof summary === "string") {
    const trimmed = summary.trim();
    if (!trimmed) return "";
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        const parsed = JSON.parse(trimmed);
        const text = normalizeSummaryText(parsed, depth);
        return text || trimmed;
      } catch {
        return trimmed;
      }
    }
    return trimmed;
  }

  if (Array.isArray(summary)) {
    return summary
      .map((item) => normalizeSummaryText(item, depth))
      .filter(Boolean)
      .join("；");
  }

  if (typeof summary === "object") {
    const lines = [];
    const appendLine = (label, value) => {
      if (value == null || value === "") return;
      if (typeof value === "object") {
        const inner = normalizeSummaryText(value, depth);
        if (inner) lines.push(label ? `${label}${inner}` : inner);
        return;
      }
      const text = String(value).trim();
      if (text && text !== "[object Object]")
        lines.push(label ? `${label}${text}` : text);
    };

    const KNOWN_KEYS = [
      ["summary", ""],
      ["text", ""],
      ["content", ""],
      ["warnings", "注意事项："],
      ["warning", "注意事项："],
      ["follow_up", "随访建议："],
      ["followUp", "随访建议："],
      ["recommendation", "建议："],
      ["recommendations", "建议："],
    ];

    let matched = false;
    for (const [key, label] of KNOWN_KEYS) {
      if (summary[key] != null) {
        appendLine(label, summary[key]);
        matched = true;
      }
    }

    if (!matched) {
      for (const value of Object.values(summary)) {
        if (typeof value === "string") {
          const text = value.trim();
          if (text && text !== "[object Object]") lines.push(text);
        }
      }
    }

    return lines.join("\n");
  }

  return String(summary).trim();
}

function showDoubaoResult(content) {
  els.doubaoResultPanel.hidden = false;
  if (typeof content === "string") {
    els.doubaoResult.textContent = content;
    return;
  }
  els.doubaoResult.textContent = JSON.stringify(content, null, 2);
}

function hideDoubaoResult() {
  els.doubaoResultPanel.hidden = true;
  els.doubaoResult.textContent = "";
}

function updateAdminEntry() {
  const loggedIn = isSessionReady();
  const isAdmin = state.currentUser?.role === "admin";
  if (els.adminEntryButton) {
    els.adminEntryButton.hidden = !isAdmin || !loggedIn;
  }
  if (els.adminQuickNav) {
    els.adminQuickNav.hidden = !isAdmin || window.APP_CONFIG.DEMO_MODE;
  }
  if (els.profilesEntryButton) {
    els.profilesEntryButton.hidden = !loggedIn;
  }
  if (els.libraryEntryButton) {
    els.libraryEntryButton.hidden = !loggedIn;
  }
  if (els.goProgressButton) {
    els.goProgressButton.hidden = !loggedIn;
  }
  if (els.knowledgeEntryButton) {
    els.knowledgeEntryButton.hidden = !loggedIn;
  }
  const isDoctor = state.currentUser?.role === "doctor" || state.currentUser?.role === "admin";
  if (els.collaborationEntryButton) {
    els.collaborationEntryButton.hidden = !loggedIn || isDoctor || window.APP_CONFIG.DEMO_MODE;
  }
  if (els.doctorEntryButton) {
    els.doctorEntryButton.hidden = !loggedIn || !isDoctor || window.APP_CONFIG.DEMO_MODE;
  }
  if (els.imagingSectionWrap) {
    els.imagingSectionWrap.hidden = window.APP_CONFIG.DEMO_MODE;
  }
  // Reveal the "更多" dropdown only when at least one secondary entry is visible.
  const secondaryGroup = document.getElementById("header-secondary-group");
  const secondaryToggle = document.getElementById("header-secondary-toggle");
  if (secondaryGroup && secondaryToggle) {
    const anySecondaryVisible = loggedIn && (
      !els.profilesEntryButton?.hidden ||
      !els.libraryEntryButton?.hidden ||
      !els.goProgressButton?.hidden ||
      !els.knowledgeEntryButton?.hidden ||
      !els.collaborationEntryButton?.hidden ||
      !els.doctorEntryButton?.hidden ||
      !els.adminEntryButton?.hidden
    );
    secondaryToggle.hidden = !anySecondaryVisible;
    if (!anySecondaryVisible) {
      secondaryGroup.hidden = true;
      secondaryToggle.setAttribute("aria-expanded", "false");
      secondaryToggle.textContent = "更多 ▾";
    }
  }
}

function setHeaderSecondaryOpen(open) {
  const group = document.getElementById("header-secondary-group");
  const toggle = document.getElementById("header-secondary-toggle");
  if (!group || !toggle) return;
  group.hidden = !open;
  toggle.setAttribute("aria-expanded", open ? "true" : "false");
  toggle.textContent = open ? "收起 ▴" : "更多 ▾";
}

function hideRedFlagAlert() {
  if (els.redFlagOverlay) {
    els.redFlagOverlay.hidden = true;
    els.redFlagOverlay.setAttribute("aria-hidden", "true");
  }
  if (els.redFlagMessage) els.redFlagMessage.innerHTML = "";
  if (els.redFlagList) {
    els.redFlagList.innerHTML = "";
    els.redFlagList.hidden = true;
  }
}

function formatRedFlagMessageHtml(message, redFlags = []) {
  const labels =
    redFlags.map((item) => item.label).filter(Boolean).join("、") ||
    (message.match(/检测到红旗症状：([^。]+)/)?.[1] ?? "需立即就医的相关症状");
  const rest = message.replace(/检测到红旗症状：[^。]+。?/, "").trim();
  const urgentMatch = rest.match(/(请尽快.+)$/);
  const urgentText = urgentMatch?.[1]?.trim() || "请尽快前往医院或咨询专业医生/康复治疗师。";
  const bodyText = (urgentMatch ? rest.slice(0, urgentMatch.index) : rest)
    .replace(/[，,]\s*$/, "")
    .trim() || "为避免延误病情，系统已暂停生成普通居家康复训练处方";

  return `
    <p class="red-flag-lead">检测到红旗症状：</p>
    <p class="red-flag-highlight">${escapeAdminText(labels)}</p>
    <p class="red-flag-body">${escapeAdminText(bodyText)}</p>
    <p class="red-flag-urgent">${escapeAdminText(urgentText)}</p>
  `;
}

function showRedFlagAlert(message, redFlags = []) {
  if (!els.redFlagOverlay) return;
  els.redFlagOverlay.hidden = false;
  els.redFlagOverlay.setAttribute("aria-hidden", "false");
  if (els.redFlagMessage) {
    els.redFlagMessage.innerHTML = formatRedFlagMessageHtml(message || "", redFlags);
  }
  if (els.redFlagList) {
    const extraFlags = (redFlags || []).filter(
      (item) => !message?.includes(item.label || "")
    );
    if (extraFlags.length) {
      els.redFlagList.hidden = false;
      els.redFlagList.innerHTML = extraFlags
        .map((item) => `<li>${escapeAdminText(item.label || item.code || "未知风险")}</li>`)
        .join("");
    } else {
      els.redFlagList.innerHTML = "";
      els.redFlagList.hidden = true;
    }
  }
}

function updateMobilitySummary(score) {
  const tier = getMobilityTier(score);
  const shortLabel = tier.label.split(" · ")[0] || tier.label;
  if (els.mobilitySummary) {
    els.mobilitySummary.textContent = `${score}/10 · ${shortLabel}`;
  }
}

function updateMobilityGuide() {
  if (!els.mobilityGuideCards) return;
  const regions = Array.from(state.selectedPainRegions);
  const guides = regions.length
    ? regions.map((region) => ({
        region,
        ...(window.APP_CONFIG.MOBILITY_GUIDES[region] || window.APP_CONFIG.DEFAULT_MOBILITY_GUIDE),
      }))
    : [{ region: "通用", ...window.APP_CONFIG.DEFAULT_MOBILITY_GUIDE }];

  els.mobilityGuideCards.innerHTML = guides
    .map(
      (guide) => `
      <article class="mobility-guide-card">
        <div class="guide-icon">${escapeAdminText(guide.icon || "📋")}</div>
        <h4>${escapeAdminText(guide.title)}${guide.region && guide.region !== "通用" ? ` · ${escapeAdminText(guide.region)}` : ""}</h4>
        <p>${escapeAdminText(guide.instruction)}</p>
      </article>`
    )
    .join("");
}

function updateMobilityTierDisplay(score) {
  const tier = getMobilityTier(score);
  if (els.mobilityTier) els.mobilityTier.textContent = tier.label;
  updateMobilitySummary(score);
}

function renderActionMetaTags(action) {
  const parts = [];
  if (action.sets) parts.push(`${action.sets} 组`);
  if (action.reps) parts.push(`${action.reps} 次/组`);
  if (action.frequency) parts.push(action.frequency);
  if (action.difficulty_level) {
    let cls = "tag-difficulty";
    if (action.difficulty_level === "中级") cls += " mid";
    if (action.difficulty_level === "高级") cls += " advanced";
    parts.push(`<span class="tag ${cls}">${escapeAdminText(action.difficulty_level)}</span>`);
  }
  if (action.category) parts.push(`<span class="tag">${escapeAdminText(action.category)}</span>`);
  return parts.map((p) => (p.startsWith("<span") ? p : `<span class="tag">${escapeAdminText(p)}</span>`)).join("");
}

function setDemoCollapsible(id, visible, summaryText) {
  const details = document.getElementById(id);
  if (!details) return;
  details.hidden = !visible;
  if (!visible) {
    details.open = false;
    return;
  }
  const summary = details.querySelector("summary");
  if (summary && summaryText) summary.textContent = summaryText;
}

function renderActionDetailSections(action) {
  const stepsEl = document.getElementById("demo-action-steps");
  const comparisonsEl = document.getElementById("demo-error-comparisons");
  const fallbackEl = document.getElementById("demo-mistake-fallback");
  const mistakesEl = document.getElementById("demo-common-mistakes");
  const cuesEl = document.getElementById("demo-correct-cues");
  const difficultyCurrent = document.getElementById("demo-difficulty-current");
  const difficultyProfilesEl = document.getElementById("demo-difficulty-profiles");

  const steps = action.steps || [];
  setDemoCollapsible("demo-steps-collapsible", steps.length > 0, `分步要领（${steps.length} 步）`);
  if (stepsEl) stepsEl.innerHTML = steps.map((step) => `<li>${escapeAdminText(step)}</li>`).join("");

  const comparisons = action.error_comparisons || [];
  if (comparisonsEl && fallbackEl) {
    if (comparisons.length) {
      comparisonsEl.hidden = false;
      fallbackEl.hidden = true;
      comparisonsEl.innerHTML = comparisons
        .map(
          (item) => `
        <article class="error-comparison-card">
          <div class="error-comparison-row mistake-wrong">
            <span class="error-comparison-label">❌ 常见错误</span>
            <p>${escapeAdminText(item.mistake || "")}</p>
          </div>
          <div class="error-comparison-row mistake-right">
            <span class="error-comparison-label">✅ 正确要点</span>
            <p>${escapeAdminText(item.correct || "")}</p>
          </div>
          ${item.risk ? `<p class="hint error-comparison-risk">风险：${escapeAdminText(item.risk)}</p>` : ""}
        </article>`
        )
        .join("");
      setDemoCollapsible(
        "demo-mistakes-collapsible",
        true,
        `常见错误动作对比（${comparisons.length} 项）`
      );
    } else {
      comparisonsEl.innerHTML = "";
      comparisonsEl.hidden = true;
      const mistakes = action.common_mistakes || [];
      const cues = action.correct_cues || [];
      fallbackEl.hidden = !mistakes.length && !cues.length;
      if (mistakesEl) mistakesEl.innerHTML = mistakes.map((item) => `<li>${escapeAdminText(item)}</li>`).join("");
      if (cuesEl) cuesEl.innerHTML = cues.map((item) => `<li>${escapeAdminText(item)}</li>`).join("");
      setDemoCollapsible(
        "demo-mistakes-collapsible",
        mistakes.length > 0 || cues.length > 0,
        "常见错误 vs 正确要点"
      );
    }
  }

  const profiles = action.difficulty_profiles || [];
  setDemoCollapsible("demo-difficulty-collapsible", profiles.length > 0, "难度分级（初 / 中 / 高）");
  if (difficultyProfilesEl) {
    if (difficultyCurrent) {
      difficultyCurrent.textContent = action.difficulty_level
        ? `当前推荐难度：${action.difficulty_level}（下方三档为可执行的初/中/高训练方案）`
        : "以下为初、中、高三个难度档位的训练参数参考。";
    }
    difficultyProfilesEl.innerHTML = profiles
      .map((profile) => {
        const active = profile.level === action.difficulty_level ? " is-current" : "";
        const levelClass =
          profile.level === "中级" ? " mid" : profile.level === "高级" ? " advanced" : "";
        return `
        <article class="difficulty-profile-card${active}">
          <h4><span class="tag tag-difficulty${levelClass}">${escapeAdminText(profile.level || "难度")}</span>${active ? " · 推荐" : ""}</h4>
          <p><strong>${profile.sets ?? "-"}</strong> 组 × <strong>${profile.reps ?? "-"}</strong> 次</p>
          ${profile.tempo ? `<p class="hint">${escapeAdminText(profile.tempo)}</p>` : ""}
          ${profile.guidance ? `<p>${escapeAdminText(profile.guidance)}</p>` : ""}
        </article>`;
      })
      .join("");
  }

  setDemoCollapsible(
    "demo-contraindications-collapsible",
    Boolean(action.contraindications),
    "禁忌事项"
  );
  setDemoCollapsible(
    "demo-progression-collapsible",
    Boolean(action.progression),
    "进阶条件"
  );
}

async function fetchActionDetail(action) {
  const actionId = action?.id || action?.backendId;
  if (!actionId || window.APP_CONFIG.DEMO_MODE) {
    return window.MockService.enrichAction(action);
  }
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/actions/${encodeURIComponent(actionId)}`,
      {},
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (!response.ok) return window.MockService.enrichAction(action);
    return window.MockService.enrichAction(await response.json());
  } catch {
    return window.MockService.enrichAction(action);
  }
}

function filterActionLibrary(actions) {
  const { q, bodyRegion, difficulty } = state.libraryFilters;
  return actions.filter((action) => {
    if (bodyRegion && !(action.body_regions || []).includes(bodyRegion)) return false;
    if (difficulty && action.difficulty_level !== difficulty) return false;
    if (q) {
      const haystack = [
        action.name,
        action.id,
        action.description,
        ...(action.body_regions || []),
        ...(action.target_conditions || []),
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(q.toLowerCase())) return false;
    }
    return true;
  });
}

function renderLibraryActionCard(action) {
  const poseSupported = isActionPoseSupported(action);
  return `
    <article class="action-card card">
      <div class="action-image-wrap">
        <img src="${window.APP_CONFIG.assetUrl(action.image)}" alt="${escapeAdminText(action.name)}示意图" loading="lazy" onerror="handleActionImageError(this)" />
        <span class="action-image-placeholder">示意图待上传</span>
      </div>
      <div class="action-card-body">
        <h3>${escapeAdminText(action.name)}</h3>
        <div class="action-meta">${renderActionMetaTags(action)}</div>
        <p>${escapeAdminText(action.description || "")}</p>
        <p class="hint">${escapeAdminText((action.body_regions || []).join("、"))}${action.stage ? ` · ${escapeAdminText(action.stage)}` : ""}</p>
        <button class="btn btn-primary btn-small library-view-demo" type="button" data-action-id="${escapeAdminText(action.id || "")}">
          查看详情${poseSupported ? " / 跟练" : ""}
        </button>
      </div>
    </article>`;
}

async function loadActionLibrary() {
  if (!els.libraryGrid) return;
  els.libraryGrid.innerHTML = "<p class=\"hint\">正在加载动作库…</p>";
  try {
    if (window.APP_CONFIG.DEMO_MODE) {
      state.actionLibrary = Object.values(window.ACTION_CATALOG).map((item) =>
        window.MockService.enrichAction(item)
      );
    } else {
      const response = await fetchWithTimeout(
        `${window.APP_CONFIG.API_BASE}/actions`,
        {},
        window.APP_CONFIG.LIST_TIMEOUT_MS
      );
      if (!response.ok) throw new Error("actions unavailable");
      const data = await response.json();
      state.actionLibrary = data.map((action) => window.MockService.enrichAction(action));
    }
    populateLibraryRegionFilter();
    renderActionLibraryGrid();
  } catch {
    renderLoadError(els.libraryGrid, { message: "动作库加载失败，请确认后端已启动。", onRetry: loadActionLibrary });
  }
}

function populateLibraryRegionFilter() {
  const select = document.getElementById("library-filter-region");
  if (!select) return;
  const regions = new Set();
  state.actionLibrary.forEach((action) => (action.body_regions || []).forEach((r) => regions.add(r)));
  const current = select.value;
  select.innerHTML = `<option value="">全部部位</option>${Array.from(regions)
    .sort()
    .map((region) => `<option value="${escapeAdminText(region)}">${escapeAdminText(region)}</option>`)
    .join("")}`;
  select.value = current;
}

function renderActionLibraryGrid() {
  if (!els.libraryGrid) return;
  const filtered = filterActionLibrary(state.actionLibrary);
  if (!filtered.length) {
    els.libraryGrid.innerHTML = "<p class=\"hint\">没有匹配的动作。</p>";
    return;
  }
  els.libraryGrid.innerHTML = filtered.map(renderLibraryActionCard).join("");
  els.libraryGrid.querySelectorAll(".library-view-demo").forEach((button) => {
    button.addEventListener("click", () => {
      const action = state.actionLibrary.find((item) => item.id === button.dataset.actionId);
      if (action) void showDemo(action);
    });
  });
}

// ── M5: Voice cue ──
let lastVoiceAnnouncedText = "";
let voiceSpeaking = false;
let pendingVoiceCue = null;

function setVoiceCueText(text) {
  const textEl = document.getElementById("voice-cue-text");
  if (textEl && text) textEl.textContent = text;
}

function resetVoiceCueState() {
  lastVoiceAnnouncedText = "";
  pendingVoiceCue = null;
  voiceSpeaking = false;
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

function normalizeVoiceFeedbackText(feedback) {
  if (feedback == null) return "动作已记录，请保持稳定呼吸。";
  const items = Array.isArray(feedback) ? feedback.filter(Boolean) : [String(feedback)];
  const text = items.slice(0, 2).join("；").trim();
  return text || "动作已记录，请保持稳定呼吸。";
}

function pickChineseSpeechVoice() {
  if (!("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((voice) => voice.lang === "zh-CN") ||
    voices.find((voice) => voice.lang.startsWith("zh")) ||
    null
  );
}

function primeSpeechSynthesis() {
  if (!("speechSynthesis" in window)) return false;
  window.speechSynthesis.getVoices();
  if (window.speechSynthesis.paused) window.speechSynthesis.resume();
  return true;
}

function flushPendingVoiceCue() {
  if (!pendingVoiceCue || voiceSpeaking) return;
  const next = pendingVoiceCue;
  pendingVoiceCue = null;
  if (next.text === lastVoiceAnnouncedText) return;
  lastVoiceAnnouncedText = next.text;
  startVoiceUtterance(next.text, next.rate);
}

function startVoiceUtterance(text, rate = 1) {
  if (!text || !("speechSynthesis" in window)) return;

  const speakNow = () => {
    voiceSpeaking = true;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.rate = rate;
    utterance.volume = 1;
    const voice = pickChineseSpeechVoice();
    if (voice) utterance.voice = voice;
    const finish = () => {
      voiceSpeaking = false;
      flushPendingVoiceCue();
    };
    utterance.onend = finish;
    utterance.onerror = finish;
    window.speechSynthesis.resume();
    window.speechSynthesis.speak(utterance);
  };

  if (window.speechSynthesis.getVoices().length) {
    speakNow();
  } else {
    window.speechSynthesis.addEventListener("voiceschanged", speakNow, { once: true });
    primeSpeechSynthesis();
  }
}

/** Short UI prompt (e.g. toggle on); does not affect pose cue dedupe. */
function speakVoicePrompt(text, rate = 1) {
  if (!text || !("speechSynthesis" in window)) return;
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  voiceSpeaking = false;
  pendingVoiceCue = null;
  startVoiceUtterance(text, rate);
}

function playVoiceCue(feedback, status, score, voiceCue) {
  const text = voiceCue?.text || normalizeVoiceFeedbackText(feedback);
  setVoiceCueText(text);

  if (!state.voiceEnabled) return;
  // Each distinct cue is spoken at most once until the message changes.
  if (text === lastVoiceAnnouncedText) return;

  const rate = voiceCue?.rate || (status === "error" || (typeof score === "number" && score < 45) ? 0.92 : 1);

  if (voiceSpeaking) {
    pendingVoiceCue = { text, rate };
    return;
  }

  lastVoiceAnnouncedText = text;
  startVoiceUtterance(text, rate);
}

function syncVoiceToggleUi() {
  const btn = document.getElementById("toggle-voice");
  if (btn) btn.textContent = state.voiceEnabled ? "关闭语音播报" : "开启语音播报";
  const indicator = document.getElementById("voice-indicator");
  if (indicator) indicator.classList.toggle("active", state.voiceEnabled);
}

function toggleVoice() {
  if (!("speechSynthesis" in window)) {
    showWarnToast("当前浏览器不支持语音播报");
    return;
  }
  primeSpeechSynthesis();
  state.voiceEnabled = !state.voiceEnabled;
  syncVoiceToggleUi();
  if (state.voiceEnabled) {
    setVoiceCueText("语音播报已开启");
    speakVoicePrompt("语音播报已开启");
  } else {
    resetVoiceCueState();
    setVoiceCueText("语音播报已关闭，纠错文字仍会显示");
  }
}

// ── M5: Training counter ──
function startTrainingCounter() {
  state.trainingStartTime = Date.now();
  state.trainingRepCount = 0;
  state.trainingSetCount = 0;
  state.lastRepStatus = null;
  updateCounterDisplay();
  if (state.trainingTimer) clearInterval(state.trainingTimer);
  state.trainingTimer = setInterval(updateCounterDisplay, 1000);
}

function stopTrainingCounter() {
  if (state.trainingTimer) { clearInterval(state.trainingTimer); state.trainingTimer = null; }
}

function updateCounterDisplay() {
  const elapsed = state.trainingStartTime ? Math.floor((Date.now() - state.trainingStartTime) / 1000) : 0;
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  const durationEl = document.getElementById("counter-duration");
  const repsEl = document.getElementById("counter-reps");
  const setsEl = document.getElementById("counter-sets");
  if (durationEl) durationEl.textContent = `${mins}:${String(secs).padStart(2, "0")}`;
  if (repsEl) repsEl.textContent = String(state.trainingRepCount);
  if (setsEl) setsEl.textContent = String(state.trainingSetCount);
}

function countRep(status) {
  if (status === "ok" && state.lastRepStatus !== "ok") {
    state.trainingRepCount++;
    const targetReps = state.currentAction?.reps || 10;
    if (state.trainingRepCount > 0 && state.trainingRepCount % targetReps === 0) {
      state.trainingSetCount++;
    }
    updateCounterDisplay();
  }
  state.lastRepStatus = status;
}

// ── M6: Progress tracking page ──
async function loadProgressPage() {
  if (!apiEnabled()) {
    renderDemoNotice(els.progressStatsGrid, { featureName: "康复进度追踪" });
    if (els.progressVasChart) els.progressVasChart.innerHTML = "";
    if (els.progressCompletion) els.progressCompletion.innerHTML = "";
    if (els.progressReport) els.progressReport.innerHTML = "";
    if (els.progressAdjustments) els.progressAdjustments.innerHTML = "";
    return;
  }
  await Promise.all([loadProgressStats(), loadProgressReport(), collaborationPage.loadAdjustments()]);
}

async function loadProgressStats() {
  const grid = els.progressStatsGrid;
  const vasChart = els.progressVasChart;
  const completionEl = els.progressCompletion;
  if (!grid) return;
  grid.innerHTML = '<p class="hint">正在加载…</p>';
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/training_checkins/visualization?days=30`,
      { headers: authHeaders() },
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (!response.ok) throw new Error();
    const data = await response.json();
    const trend = data.trend?.points || [];
    grid.innerHTML = `
      <div class="progress-stat-card"><span class="progress-stat-value">${data.total_checkins}</span><span class="progress-stat-label">打卡次数</span></div>
      <div class="progress-stat-card"><span class="progress-stat-value">${data.active_days}</span><span class="progress-stat-label">活跃天数</span></div>
      <div class="progress-stat-card"><span class="progress-stat-value">${data.avg_score ?? "—"}</span><span class="progress-stat-label">平均得分</span></div>
      <div class="progress-stat-card"><span class="progress-stat-value">${data.avg_pain_change != null ? (data.avg_pain_change > 0 ? "+" : "") + data.avg_pain_change.toFixed(1) : "—"}</span><span class="progress-stat-label">疼痛变化</span></div>
    `;
    if (vasChart && trend.length) {
      const maxPain = 10;
      const labelStep = vasChartLabelStep(trend.length);
      const barW = Math.max(32, Math.min(56, Math.floor(720 / trend.length)));
      vasChart.innerHTML = `
        <div class="vas-chart">
          ${trend.map((p, index) => {
            const before = p.avg_pain_before ?? 0;
            const after = p.avg_pain_after ?? 0;
            const showLabel = index % labelStep === 0 || index === trend.length - 1;
            const dateLabel = showLabel ? formatVasAxisLabel(p.date) : "";
            const dateTitle = p.date ? `${p.date} · 训练前 ${before.toFixed(1)} / 训练后 ${after.toFixed(1)}` : "";
            return `<div class="vas-bar-group" style="min-width:${barW}px" title="${escapeHtml(dateTitle)}">
              <div class="vas-bars">
                <div class="vas-bar vas-before" style="height:${(before / maxPain) * 100}%" title="训练前:${before.toFixed(1)}"></div>
                <div class="vas-bar vas-after" style="height:${(after / maxPain) * 100}%" title="训练后:${after.toFixed(1)}"></div>
              </div>
              <span class="vas-date${showLabel ? "" : " vas-date-spacer"}" aria-hidden="${showLabel ? "false" : "true"}">${escapeHtml(dateLabel)}</span>
            </div>`;
          }).join("")}
        </div>
        <div class="vas-legend"><span class="vas-legend-item"><span class="vas-dot vas-before"></span>训练前</span><span class="vas-legend-item"><span class="vas-dot vas-after"></span>训练后</span></div>
      `;
    } else if (vasChart) {
      vasChart.innerHTML = '<p class="hint">暂无疼痛记录数据</p>';
    }
    if (completionEl && trend.length) {
      const totalDays = trend.length;
      const activeDays = trend.filter(p => p.checkin_count > 0).length;
      const rate = totalDays > 0 ? Math.round((activeDays / totalDays) * 100) : 0;
      completionEl.innerHTML = `
        <div class="completion-bar-wrap"><div class="completion-bar" style="width:${rate}%"></div></div>
        <p>${activeDays}/${totalDays} 天完成训练 · 完成率 <strong>${rate}%</strong></p>
      `;
    }
  } catch {
    renderLoadError(grid, { message: "进度数据加载失败，请确认后端已启动后重试。", onRetry: loadProgressStats });
  }
}

async function loadProgressReport() {
  const reportEl = els.progressReport;
  const actionsEl = els.progressReportActions;
  if (!reportEl) return;
  const period = state.progressReportPeriod || "weekly";
  const periodLabel = period === "monthly" ? "月报" : "周报";
  reportEl.innerHTML = `<p class="hint">正在生成${periodLabel}…</p>`;
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/training_checkins/report?period=${period}`,
      { headers: authHeaders() },
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (!response.ok) throw new Error();
    const r = await response.json();
    reportEl.innerHTML = `
      <p><strong>周期：</strong>${r.start_date} 至 ${r.end_date}</p>
      <p><strong>完成率：</strong>${(r.completion_rate * 100).toFixed(0)}%（${r.active_days}/${r.expected_days} 天）</p>
      <p><strong>平均得分：</strong>${r.avg_score ?? "—"}</p>
      <p><strong>疼痛变化：</strong>${r.vas_summary || "暂无"}</p>
      ${r.action_summaries?.length ? `<h4>动作统计</h4><ul>${r.action_summaries.map(a => `<li>${escapeAdminText(a.action_name)}：${a.count} 次${a.avg_score != null ? `，均分 ${a.avg_score}` : ""}</li>`).join("")}</ul>` : ""}
      ${r.highlights?.length ? `<h4>亮点</h4><ul>${r.highlights.map(h => `<li>${escapeAdminText(h)}</li>`).join("")}</ul>` : ""}
      ${r.risks?.length ? `<h4>风险</h4><ul>${r.risks.map(h => `<li>${escapeAdminText(h)}</li>`).join("")}</ul>` : ""}
      ${r.recommendations?.length ? `<h4>建议</h4><ul>${r.recommendations.map(h => `<li>${escapeAdminText(h)}</li>`).join("")}</ul>` : ""}
    `;
    if (actionsEl) actionsEl.hidden = false;
  } catch {
    reportEl.innerHTML = `<p class="hint">${periodLabel}生成失败，请确认有训练打卡记录。</p>`;
  }
}

async function exportProgressReport() {
  const period = state.progressReportPeriod || "weekly";
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/training_checkins/report/export?period=${period}&format=markdown`,
      { headers: authHeaders() },
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (!response.ok) throw new Error();
    const text = await response.text();
    const blob = new Blob([text], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = period === "monthly" ? "康复月报.md" : "康复周报.md";
    a.click();
    URL.revokeObjectURL(url);
    showToast("报告已导出");
  } catch {
    showErrorToast("报告导出失败");
  }
}

// ── M7: Knowledge education page ──
// Page logic lives in pages/knowledge.js as a factory (createKnowledgePage)
// to keep this file focused on wiring. Dependencies (state, els, api helpers,
// ui helpers) are injected via the ctx object so the page module has no
// global coupling. The thin wrappers below keep call sites in goToStep /
// bindEvents unchanged.
const knowledgePage = createKnowledgePage({
  state,
  els,
  apiGet,
  apiSend,
  escapeHtml,
  renderLoadError,
  showToast,
});
const loadKnowledgePage = knowledgePage.loadKnowledgePage;
const switchKnowledgeTab = knowledgePage.switchKnowledgeTab;
// Debounced reload for the keyword filter input.
const knowledgeFilterDebounced = debounce(() => loadKnowledgePage(), 300);
function bindKnowledgePageEvents() {
  // Delegate to the page module, forwarding the debounced reload so the
  // filter input uses the same cadence as the rest of the app.
  knowledgePage.bindKnowledgePageEvents(knowledgeFilterDebounced);
}

// ── Admin panel page ──
// Extracted to pages/admin.js. Inject app-level helpers; the returned
// methods keep existing call sites (goToStep, bindEvents) unchanged.
const adminPage = createAdminPage({
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
});
const loadAdminActions = adminPage.loadAdminActions;
const bindAdminPanelEvents = adminPage.bindAdminPanelEvents;
const bindAdminQuickNavEvents = adminPage.bindAdminQuickNavEvents;

const collaborationPage = createCollaborationPage({
  state,
  els,
  apiGet,
  apiSend,
  escapeHtml,
  formatShortDate,
  showToast,
  showErrorToast,
  showWarnToast,
  renderDemoNotice,
  renderLoadError,
  requireApi,
});
const loadAdjustments = collaborationPage.loadAdjustments;
const loadCollaborationPage = collaborationPage.loadCollaborationPage;
const loadDoctorWorkspace = collaborationPage.loadDoctorWorkspace;
const renderPrescriptionCollaboration = collaborationPage.renderPrescriptionCollaboration;

// ── Patient profiles + imaging reports page ──
// Extracted to pages/profiles.js. Owns profile CRUD, imaging upload/list,
// and the profile select used by intake.
const profilesPage = createProfilesPage({
  state,
  els,
  fetchWithTimeout,
  authHeaders,
  parseApiError,
  escapeAdminText,
  isSessionReady,
  requireLogin,
  requireApi,
  apiEnabled,
  showToast,
  showErrorToast,
  renderDemoNotice,
  renderLoadError,
  setLoading,
  showRedFlagAlert,
  updateMobilityGuide,
  goToStep,
});
const loadProfilesPage = profilesPage.loadProfilesPage;
const loadPatientProfiles = profilesPage.loadPatientProfiles;
const renderPatientProfileSelect = profilesPage.renderPatientProfileSelect;
const createPatientProfileFromIntake = profilesPage.createPatientProfileFromIntake;
const saveProfileForm = profilesPage.saveProfileForm;
const resetProfileForm = profilesPage.resetProfileForm;
const initProfilePainRegions = profilesPage.initProfilePainRegions;
const bindProfilesPageEvents = profilesPage.bindProfilesPageEvents;
const loadImagingReports = profilesPage.loadImagingReports;
const uploadImagingReport = profilesPage.uploadImagingReport;
const bindImagingReportEvents = profilesPage.bindImagingReportEvents;
const applyPatientProfileToIntake = profilesPage.applyPatientProfileToIntake;

// ── M8: Prescription satisfaction feedback (user side) ──
// Submitted via POST /feedback with category="prescription"; admins review
// these in the admin panel's feedback-management section.
function updatePrescriptionFeedbackCard() {
  if (!els.prescriptionFeedbackCard) return;
  // Only show when a real prescription exists and the backend is live
  // (Demo mode has no persistence target for feedback).
  const show = Boolean(state.prescription) && !window.APP_CONFIG.DEMO_MODE;
  els.prescriptionFeedbackCard.hidden = !show;
}

function updateFeedbackStarRating(rating) {
  state.feedbackRating = rating;
  const input = document.getElementById("feedback-rating-value");
  if (input) input.value = rating ? String(rating) : "";
  document.querySelectorAll("#feedback-star-rating .star-btn").forEach((btn) => {
    const value = Number(btn.dataset.rating);
    btn.classList.toggle("active", value <= rating);
  });
}

async function submitPrescriptionFeedback(event) {
  event.preventDefault();
  if (!requireLogin()) return;
  const content = document.getElementById("feedback-content")?.value?.trim() || "";
  const rating = state.feedbackRating || null;
  if (!rating && !content) {
    showToast("请选择满意度评分或填写反馈内容");
    return;
  }
  try {
    await apiSend("POST", "/feedback", {
      category: "prescription",
      rating,
      content,
      source: "prescription_page",
    });
    showToast("感谢您的反馈！");
    els.prescriptionFeedbackForm?.reset();
    updateFeedbackStarRating(0);
  } catch (error) {
    showErrorToast(error.message || "反馈提交失败");
  }
}

function bindPrescriptionFeedbackEvents() {
  document.querySelectorAll("#feedback-star-rating .star-btn").forEach((btn) => {
    btn.addEventListener("click", () => updateFeedbackStarRating(Number(btn.dataset.rating)));
  });
  els.prescriptionFeedbackForm?.addEventListener("submit", submitPrescriptionFeedback);
}

async function exportPrescription(format) {
  const prescriptionId = state.prescription?.id;
  if (!prescriptionId || window.APP_CONFIG.DEMO_MODE) {
    showWarnToast("请先登录并在 API 模式下生成可导出的处方");
    return;
  }
  if (!requireLogin()) return;
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/prescriptions/${prescriptionId}/export?format=${format}`,
      { headers: authHeaders() },
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `prescription_${prescriptionId}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
    showToast(`处方已导出为 ${format.toUpperCase()}`);
  } catch {
    showErrorToast("处方导出失败，请确认已登录且后端可用");
  }
}

async function submitTrainingCheckin(action, options = {}) {
  if (!apiEnabled()) return null;
  const payload = {
    prescription_id: state.prescription?.id ?? null,
    patient_profile_id: state.prescription?.patient_profile_id ?? state.selectedPatientProfileId ?? null,
    action_id: getPoseActionId(action),
    action_name: action.name,
    trained_on: todayIsoDate(),
    completed_sets: action.sets ?? null,
    completed_reps: action.reps ?? null,
    pain_before: options.painBefore ?? null,
    pain_after: options.painAfter ?? null,
    score: options.score ?? state.trainingLastScore ?? null,
    note: options.note || null,
  };
  const response = await fetchWithTimeout(
    `${window.APP_CONFIG.API_BASE}/training_checkins`,
    {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    }
  );
  if (!response.ok) {
    const detail = await parseApiError(response);
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

async function loadTrainingStats() {
  if (!els.trainingStatsPanel) return;
  if (!apiEnabled()) {
    els.trainingStatsPanel.hidden = true;
    return;
  }
  els.trainingStatsPanel.hidden = false;
  els.trainingStatsPanel.innerHTML = `<p class="hint">正在加载训练统计…</p>`;
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/training_checkins/visualization?days=30`,
      { headers: authHeaders() },
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const trend = data.trend?.points || [];
    const recent = trend.slice(-7);
    const accountLabel = state.currentUser?.account || "当前账号";
    els.trainingStatsPanel.innerHTML = `
      <h3>训练统计（近 30 天）</h3>
      <p class="hint">以下数据仅统计账号 <strong>${escapeHtml(accountLabel)}</strong> 的训练打卡。</p>
      <div class="stats-grid">
        <div class="stat-card"><span class="stat-value">${data.total_checkins}</span><span class="stat-label">打卡次数</span></div>
        <div class="stat-card"><span class="stat-value">${data.active_days}</span><span class="stat-label">活跃天数</span></div>
        <div class="stat-card"><span class="stat-value">${data.avg_score ?? "—"}</span><span class="stat-label">平均得分</span></div>
      </div>
      ${
        recent.length
          ? `<ul class="trend-list">${recent
              .map(
                (point) =>
                  `<li><strong>${point.date}</strong>：打卡 ${point.checkin_count} 次${
                    point.avg_score != null ? `，均分 ${point.avg_score}` : ""
                  }</li>`
              )
              .join("")}</ul>`
          : `<p class="hint">暂无训练打卡记录，完成跟练后会自动记录。</p>`
      }
    `;
  } catch {
    renderLoadError(els.trainingStatsPanel, {
      message: "训练统计加载失败，请确认后端已启动后重试。",
      onRetry: loadTrainingStats,
    });
  }
}

function updatePrescriptionExportBar() {
  if (!els.prescriptionExportBar) return;
  const canExport = Boolean(state.prescription?.id) && !window.APP_CONFIG.DEMO_MODE && isSessionReady();
  els.prescriptionExportBar.hidden = !canExport;
}

function updateUserIdentity() {
  const onLoginPage = state.currentStep === "login";

  if (!isSessionReady() || !state.currentUser || onLoginPage) {
    els.userIdentity.hidden = true;
    els.historyUserName.textContent = "当前用户：未登录";
    els.historyUserMeta.textContent = "登录后可查看该账号的历史处方";
    return;
  }

  els.userIdentity.hidden = false;
  const displayName = resolveDisplayName(state.currentUser);
  els.userDisplayName.textContent = displayName;
  els.userAvatar.textContent = displayName.slice(0, 1);
  els.historyUserName.textContent = `当前用户：${displayName}`;
  els.historyUserMeta.textContent = state.currentUser.age
    ? `年龄：${state.currentUser.age} 岁 · 账号：${state.currentUser.account}`
    : `账号：${state.currentUser.account}`;
}

function formatPrescriptionLabel(prescription) {
  const sequenceNo = prescription?.sequence_no ?? prescription?.id;
  return sequenceNo ? `#${sequenceNo}` : "N/A";
}

function renderHistoryCard(prescription) {
  const header = [
    prescription.patient_name ? `患者：${escapeHtml(prescription.patient_name)}` : "",
    prescription.patient_age ? `年龄：${escapeHtml(prescription.patient_age)}` : "",
  ]
    .filter(Boolean)
    .join(" | ");

  return `
    <article class="history-card">
      <h4>处方 ${escapeHtml(formatPrescriptionLabel(prescription))}</h4>
      ${header ? `<div class="meta">${header}</div>` : ""}
      <div class="summary-block">${formatSummary(prescription.summary)}</div>
      <ul>
        ${prescription.actions
          .map(
            (action) =>
              `<li><strong>${escapeHtml(action.name)}</strong>：${escapeHtml(action.sets)}组 × ${escapeHtml(action.reps)}次${
                action.note ? `（${escapeHtml(action.note)}）` : ""
              }</li>`
          )
          .join("")}
      </ul>
      ${
        prescription.id && !window.APP_CONFIG.DEMO_MODE
          ? `<div class="history-card-actions">
              <button class="btn btn-secondary btn-small history-export-md" type="button" data-id="${escapeHtml(prescription.id)}">导出 MD</button>
              <button class="btn btn-secondary btn-small history-export-json" type="button" data-id="${escapeHtml(prescription.id)}">导出 JSON</button>
            </div>`
          : ""
      }
    </article>
  `;
}

async function loadPrescriptionHistory() {
  if (!requireLogin()) {
    els.prescriptionHistory.textContent = "请先登录后再查看历史处方。";
    return;
  }

  els.prescriptionHistory.textContent = "正在加载…";
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/prescriptions`,
      { headers: authHeaders() },
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (response.status === 401) {
      logoutSession();
      els.prescriptionHistory.textContent = "登录已过期，请重新登录。";
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data) || data.length === 0) {
      els.prescriptionHistory.textContent = "暂无处方记录。";
      return;
    }
    if (els.historyUserMeta && state.currentUser?.account) {
      els.historyUserMeta.textContent = `${
        state.currentUser.age ? `年龄：${state.currentUser.age} 岁 · ` : ""
      }账号：${state.currentUser.account} · 共 ${data.length} 条处方`;
    }
    els.prescriptionHistory.innerHTML = data.map(renderHistoryCard).join("");
    els.prescriptionHistory.querySelectorAll(".history-export-md").forEach((button) => {
      button.addEventListener("click", async () => {
        const id = Number(button.dataset.id);
        const original = state.prescription;
        if (original?.id === id) {
          await exportPrescription("md");
          return;
        }
        const backup = state.prescription;
        state.prescription = { id };
        await exportPrescription("md");
        state.prescription = backup;
      });
    });
    els.prescriptionHistory.querySelectorAll(".history-export-json").forEach((button) => {
      button.addEventListener("click", async () => {
        const backup = state.prescription;
        state.prescription = { id: Number(button.dataset.id) };
        await exportPrescription("json");
        state.prescription = backup;
      });
    });
  } catch (error) {
    const hint =
      error?.name === "AbortError"
        ? "历史处方请求超时，请确认后端已启动。"
        : "加载失败，请确认后端已启动且已登录。";
    renderLoadError(els.prescriptionHistory, { message: hint, onRetry: loadPrescriptionHistory });
  }
}

async function requestPrescription(formData) {
  if (window.APP_CONFIG.DEMO_MODE) {
    await new Promise((resolve) => window.setTimeout(resolve, 600));
    return { ...window.MockService.buildMockPrescription(formData), source: "mock" };
  }
  if (!requireLogin()) {
    return null;
  }

  const response = await fetchWithTimeout(
    `${window.APP_CONFIG.API_BASE}/generate_prescription`,
    {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        name: formData.name,
        age: formData.age,
        symptoms: formData.symptoms,
        history: formData.history,
        pain_regions: formData.pain_regions,
        mobility_score: formData.mobility_score,
        patient_profile_id: formData.patient_profile_id,
      }),
    },
    window.APP_CONFIG.PRESCRIPTION_TIMEOUT_MS
  );

  if (response.status === 401) {
    logoutSession();
    throw new Error("登录已过期，请重新登录");
  }

  if (!response.ok) {
    const detail = await parseApiErrorDetail(response);
    const message =
      typeof detail === "object" && detail !== null
        ? detail.message || JSON.stringify(detail)
        : detail || `HTTP ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    if (typeof detail === "object" && detail?.code === "red_flag_detected") {
      error.code = detail.code;
      error.redFlags = detail.red_flags || [];
    }
    throw error;
  }

  const data = await response.json();
  return {
    id: data.id,
    patient_profile_id: data.patient_profile_id,
    patient_name: data.patient_name,
    patient_age: data.patient_age,
    summary: data.summary,
    actions: data.actions.map((action) => window.MockService.enrichAction(action)),
    source: "api",
  };
}

function handleActionImageError(img) {
  img.classList.add("is-missing");
  img.removeAttribute("src");
  img.setAttribute("aria-label", "示意图待上传");
}
window.handleActionImageError = handleActionImageError;

function renderActionVideoMarkup(action) {
  if (window.APP_CONFIG.isValidVideoUrl(action.videoUrl)) {
    return `<button class="btn btn-secondary btn-small action-video-btn" type="button" data-video-url="${escapeAdminText(action.videoUrl)}">▶ 观看示范视频</button>`;
  }
  return "";
}

function renderPrescription(prescription) {
  const metaParts = [];
  if (prescription.sequence_no || prescription.id) {
    metaParts.push(`处方编号 ${formatPrescriptionLabel(prescription)}`);
  }
  if (prescription.patient_name) metaParts.push(`患者：${prescription.patient_name}`);
  if (prescription.patient_age) metaParts.push(`年龄：${prescription.patient_age}`);
  if (prescription.source === "mock") metaParts.push("来源：本地 Mock");
  if (prescription.source === "api") metaParts.push("来源：DeepSeek 后端 API");
  els.prescriptionMeta.textContent = metaParts.join(" · ");
  els.prescriptionSummary.innerHTML = formatSummary(prescription.summary);
  els.actionList.innerHTML = "";

  prescription.actions.forEach((action) => {
    const poseSupported = isActionPoseSupported(action);
    const card = document.createElement("article");
    card.className = "action-card card";
    card.innerHTML = `
      <div class="action-image-wrap">
        <img
          src="${window.APP_CONFIG.assetUrl(action.image)}"
          alt="${escapeHtml(action.name)}示意图"
          loading="lazy"
          onerror="handleActionImageError(this)"
        />
        <span class="action-image-placeholder">示意图待上传</span>
      </div>
      <div class="action-card-body">
        <h3>${escapeHtml(action.name)}</h3>
        <div class="action-meta">
          <span class="tag">${escapeHtml(action.sets)} 组</span>
          <span class="tag">${escapeHtml(action.reps)} 次/组</span>
          ${action.frequency ? `<span class="tag tag-frequency">${escapeHtml(action.frequency)}</span>` : ""}
          ${action.difficulty_level ? `<span class="tag tag-difficulty${action.difficulty_level === "中级" ? " mid" : action.difficulty_level === "高级" ? " advanced" : ""}">${escapeHtml(action.difficulty_level)}</span>` : ""}
          <span class="tag ${poseSupported ? "tag-supported" : "tag-pending"}">
            ${poseSupported ? "支持实时纠正" : "暂不支持实时纠正"}
          </span>
        </div>
        <p>${escapeHtml(action.description || "按医嘱缓慢完成动作，注意呼吸节奏。")}</p>
        ${renderActionVideoMarkup(action)}
        ${
          action.note
            ? `<p><strong>注意：</strong>${escapeHtml(action.note)}</p>`
            : ""
        }
        ${
          action.contraindications
            ? `<p class="hint"><strong>禁忌：</strong>${escapeHtml(action.contraindications)}</p>`
            : ""
        }
        ${
          action.progression
            ? `<p class="hint"><strong>进阶：</strong>${escapeHtml(action.progression)}</p>`
            : ""
        }
        ${
          action.regression
            ? `<p class="hint"><strong>降阶：</strong>${escapeHtml(action.regression)}</p>`
            : ""
        }
        <button class="btn btn-primary view-demo" type="button" data-action-id="${escapeHtml(action.id || "")}">
          查看演示${poseSupported ? " / 跟练" : ""}
        </button>
        ${poseSupported ? "" : `<p class="hint support-hint">${escapeHtml(window.APP_CONFIG.getUnsupportedPoseHint())}</p>`}
      </div>
    `;
    els.actionList.appendChild(card);
  });

  updatePrescriptionExportBar();
  updatePrescriptionFeedbackCard();
  renderPrescriptionCollaboration();

  els.actionList.querySelectorAll(".view-demo").forEach((button) => {
    button.addEventListener("click", () => {
      const actionId = button.dataset.actionId;
      const action = prescription.actions.find((item) => item.id === actionId);
      if (!action) {
        showErrorToast("动作信息缺失，请稍后重试");
        return;
      }
      showDemo(action);
    });
  });
}

function updatePoseFeedback(result) {
  const { feedback, score, status, voice_cue: voiceCue } = result;
  if (typeof score === "number") {
    state.trainingLastScore = score;
  }

  els.scoreBadge.textContent = `${score ?? "--"} 分`;
  els.statusText.textContent =
    status === "ok"
      ? "动作标准"
      : status === "warning"
        ? "需要调整"
        : status === "error"
          ? "无法识别"
          : "检测中";

  els.statusDot.className = "status-dot";
  if (status) els.statusDot.classList.add(status);

  els.videoShell.classList.remove("status-ok", "status-warning", "status-error");
  if (status) els.videoShell.classList.add(`status-${status}`);

  els.feedbackList.innerHTML = "";
  (feedback || []).forEach((line, index) => {
    const item = document.createElement("li");
    item.textContent = line;
    if (index === 0) item.classList.add("latest");
    els.feedbackList.appendChild(item);
  });

  if (typeof score === "number" && score < 60 && navigator.vibrate) {
    navigator.vibrate(80);
  }
  countRep(status);
  playVoiceCue(feedback, status, score, voiceCue);
}

async function correctPose(payload) {
  if (window.APP_CONFIG.DEMO_MODE) {
    await new Promise((resolve) => window.setTimeout(resolve, 120));
    return window.MockService.mockCorrectPose(payload);
  }

  const response = await fetchWithTimeout(
    `${window.APP_CONFIG.API_BASE}/correct_pose`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    window.APP_CONFIG.POSE_TIMEOUT_MS
  );

  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  return {
    feedback: data.feedback || ["暂无反馈"],
    score: data.score ?? 0,
    status: data.status || "warning",
    voice_cue: data.voice_cue || null,
  };
}

function averageVisibility(visibility) {
  if (!visibility?.length) return 1;
  return visibility.reduce((sum, value) => sum + value, 0) / visibility.length;
}

function getPoseActionId(action) {
  return action?.backendId || window.APP_CONFIG.getBackendActionId(action?.id) || action?.id;
}

function resolveActionPoseId(action) {
  return action?.id || action?.backendId || null;
}

function isActionPoseSupported(actionOrId) {
  const actionId =
    typeof actionOrId === "string" ? actionOrId : resolveActionPoseId(actionOrId);
  return window.APP_CONFIG.isPoseSupported(actionId);
}

function getPoseMissingVisibilityFeedback(actionId, visibility) {
  const backendActionId = window.APP_CONFIG.getBackendActionId(actionId);
  const required = window.APP_CONFIG.POSE_REQUIRED_KEYPOINTS?.[backendActionId] || [];
  if (!required.length || !Array.isArray(visibility)) return null;

  const missing = required
    .filter((index) => (visibility[index] ?? 0) < window.APP_CONFIG.POSE_VISIBILITY_MIN)
    .map((index) => window.APP_CONFIG.POSE_KEYPOINT_NAMES[index] || `关键点${index}`);
  if (!missing.length) return null;

  if (missing.length === required.length) {
    return {
      feedback: [
        "未识别到该动作的关键关节，请确保目标部位完整入镜并重新采集姿态。",
      ],
      score: 0,
      status: "error",
    };
  }

  const names = missing.length === 1 ? missing[0] : `${missing.slice(0, -1).join("、")}和${missing[missing.length - 1]}`;
  return {
    feedback: [
      `未识别到${names}，请调整摄像头角度或使这些部位更清晰可见。`,
    ],
    score: 35,
    status: "warning",
  };
}

function handlePoseResult(result) {
  if (Array.isArray(result?.feedback) && (result.score !== undefined || result.status)) {
    updatePoseFeedback({
      feedback: result.feedback,
      score: result.score ?? 0,
      status: result.status || "warning",
      voice_cue: result.voice_cue || null,
    });
    return;
  }
  const keypoints = result?.keypoints;
  if (keypoints?.length && typeof keypoints[0] === "object" && !Array.isArray(keypoints[0])) {
    queuePosePayload({
      ...result,
      keypoints: keypoints.map((point) => [point.x, point.y, point.z ?? 0]),
      visibility: result.visibility || keypoints.map(() => 1),
    });
    return;
  }
  queuePosePayload(result);
}

function queuePosePayload(frame) {
  if (!state.currentAction?.id || !state.autoPoseEnabled) return;

  if (!frame?.keypoints?.length || !frame?.visibility?.length) {
    // 不再对用户显示“检测受阻”提示（可能为短暂遮挡或帧丢失），仅记录供调试使用
    console.debug("queuePosePayload: no keypoints/visibility in frame — skipping", {
      keypoints: frame?.keypoints?.length,
      visibility: frame?.visibility?.length,
    });
    return;
  }

  if (frame.keypoints && frame.visibility && (frame.keypoints.length !== 17 || frame.visibility.length !== 17)) {
    if (window.APP_CONFIG.DEV_MODE) {
      console.warn("partial pose frame received", {
        keypoints: frame.keypoints?.length,
        visibility: frame.visibility?.length,
      });
    }
    // 允许继续发送不完整的关键点，让后端决定如何处理
  }

  const avgVisibility = averageVisibility(frame.visibility);
  if (avgVisibility < window.APP_CONFIG.POSE_VISIBILITY_MIN) {
    // 原先这里会阻断并显示提示；现改为仅记录警告并继续发送，由后端决定如何处理
    if (window.APP_CONFIG.DEV_MODE) {
      console.warn("low average visibility", { avgVisibility });
    }
  }

  const now = Date.now();
  const payload = {
    action_id: getPoseActionId(state.currentAction),
    keypoints: frame.keypoints,
    visibility: frame.visibility,
    timestamp: now,
  };

  const missingFeedback = getPoseMissingVisibilityFeedback(payload.action_id, frame.visibility);
  if (missingFeedback) {
    updatePoseFeedback(missingFeedback);
  }

  if (now - state.lastPoseSentAt < window.APP_CONFIG.POSE_SEND_INTERVAL_MS) {
    state.pendingPosePayload = payload;
    return;
  }

  state.pendingPosePayload = payload;
  pumpPoseCorrection();
}

async function pumpPoseCorrection() {
  if (state.poseInFlight || !state.pendingPosePayload) return;

  state.poseInFlight = true;
  const payload = state.pendingPosePayload;
  state.pendingPosePayload = null;
  state.lastPoseSentAt = payload.timestamp;

  try {
    const result = await correctPose(payload);
    updatePoseFeedback(result);
  } catch (error) {
    updatePoseFeedback({
      feedback: ["网络连接不稳定，请检查网络或后端服务"],
      score: 0,
      status: "error",
    });
  } finally {
    state.poseInFlight = false;
    if (state.pendingPosePayload) pumpPoseCorrection();
  }
}

function setCameraLoading(active, text = "正在准备…") {
  if (els.cameraLoading) els.cameraLoading.hidden = !active;
  if (els.cameraLoadingText) els.cameraLoadingText.textContent = text;
  if (els.startCameraButton) els.startCameraButton.disabled = active;
}

function resetStartCameraButton() {
  if (!els.startCameraButton) return;
  els.startCameraButton.disabled = false;
  els.startCameraButton.textContent = "启动摄像头";
}

async function ensurePoseTracker() {
  if (!state.poseTracker) {
    state.poseTracker = new PoseTracker({
      video: els.video,
      canvas: els.overlay,
      onFrame: queuePosePayload,
      onPoseResult: handlePoseResult,
      getActionId: () => getPoseActionId(state.currentAction),
      getAuthHeaders: () => authHeaders(),
    });
    await state.poseTracker.init();
  }
}

function preloadPoseTracker() {
  ensurePoseTracker().catch(() => {
    // 预加载失败时留到用户点击「启动摄像头」再重试
  });
}

function showDemo(action) {
  return showDemoAsync(action);
}

async function showDemoAsync(action) {
  const detail = await fetchActionDetail(action);
  state.currentAction = detail;

  const nameEl = document.getElementById("demo-action-name");
  const imgEl = document.getElementById("demo-action-image");
  const metaEl = document.getElementById("demo-meta");
  const descEl = document.getElementById("demo-action-desc");
  const contraEl = document.getElementById("demo-contraindications");
  const progEl = document.getElementById("demo-progression");
  const videoWrap = document.getElementById("demo-video-wrap");
  const videoLink = document.getElementById("demo-video-link");
  const videoHintEl = document.getElementById("demo-video-hint");
  const startBtn = document.getElementById("demo-start-training");

  if (nameEl) nameEl.textContent = detail.name;

  if (imgEl) {
    imgEl.classList.remove("is-missing");
    imgEl.src = window.APP_CONFIG.assetUrl(detail.image);
    imgEl.alt = `${detail.name}示意图`;
  }

  if (metaEl) {
    metaEl.innerHTML = renderActionMetaTags(detail);
  }

  if (descEl) descEl.textContent = detail.description || "按医嘱缓慢完成动作，注意呼吸节奏。";
  renderActionDetailSections(detail);

  if (contraEl) contraEl.textContent = detail.contraindications || "";
  if (progEl) progEl.textContent = detail.progression || "";

  if (videoWrap && videoLink && videoHintEl) {
    if (window.APP_CONFIG.isValidVideoUrl(detail.videoUrl)) {
      videoLink.href = "#";
      videoLink.dataset.videoUrl = detail.videoUrl;
      videoLink.hidden = false;
      videoHintEl.textContent = "";
      videoHintEl.hidden = true;
      videoWrap.hidden = false;
    } else {
      delete videoLink.dataset.videoUrl;
      videoLink.removeAttribute("href");
      videoLink.hidden = true;
      videoHintEl.hidden = true;
      videoWrap.hidden = true;
    }
  }

  const poseSupported = isActionPoseSupported(detail);
  if (startBtn) {
    startBtn.hidden = !poseSupported;
  }

  goToStep("demo");
}

function startTraining(action) {
  if (!isActionPoseSupported(action)) {
    showWarnToast("该动作暂不支持实时纠正，请选择支持的动作进行跟练。");
    return;
  }
  stopPrescriptionLoading();
  setLoading(false);
  stopCamera();
  setCameraLoading(false);
  resetStartCameraButton();

  state.currentAction = action;
  state.trainingLastScore = null;
  const completeButton = document.getElementById("complete-training");
  if (completeButton) {
    completeButton.disabled = false;
    completeButton.textContent = "完成训练，返回处方";
  }
  if (els.checkinPainBefore) els.checkinPainBefore.value = "";
  if (els.checkinPainAfter) els.checkinPainAfter.value = "";
  if (els.checkinNote) els.checkinNote.value = "";
  els.trainingActionName.textContent = `${action.name} · ${action.sets} 组 × ${action.reps} 次${action.frequency ? ` · ${action.frequency}` : ""}`;
  if (els.feedbackOverlay) els.feedbackOverlay.textContent = "准备就绪后点击启动摄像头";
  els.scoreBadge.textContent = "-- 分";
  els.feedbackList.innerHTML = "";
  els.statusText.textContent = "未开始";
  els.statusDot.className = "status-dot";
  els.videoShell.classList.remove("status-ok", "status-warning", "status-error");
  goToStep("training");
  preloadPoseTracker();
  startTrainingCounter();
  resetVoiceCueState();
  syncVoiceToggleUi();
  setVoiceCueText(
    state.voiceEnabled
      ? "等待动作检测…"
      : "纠错提示将显示于此；点击「开启语音播报」可朗读"
  );
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    showErrorToast("当前浏览器不支持摄像头");
    return;
  }

  try {
    setCameraLoading(true, "正在加载姿态模型…");
    stopCamera();

    await ensurePoseTracker();

    setCameraLoading(true, "正在启动摄像头…");
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    state.cameraStream = stream;
    els.video.srcObject = stream;
    await els.video.play();
    els.videoShell.classList.add("camera-active");

    state.autoPoseEnabled = true;
    state.poseTracker.start();
    if (els.feedbackOverlay) els.feedbackOverlay.textContent = "等待检测…";
    els.statusText.textContent = "实时检测中";
    if (!state.voiceEnabled && "speechSynthesis" in window) {
      state.voiceEnabled = true;
      syncVoiceToggleUi();
      setVoiceCueText("语音播报已开启");
      speakVoicePrompt("语音播报已开启");
    } else {
      setVoiceCueText(state.voiceEnabled ? "正在检测，请做动作…" : "纠错提示将显示于此");
    }
    showToast("摄像头已启动，正在实时分析动作");
  } catch (error) {
    stopCamera();
    showErrorToast("无法访问摄像头或姿态模型加载失败，请检查浏览器权限与网络");
  } finally {
    setCameraLoading(false);
    if (els.startCameraButton && state.cameraStream) {
      els.startCameraButton.textContent = "重新启动摄像头";
    }
  }
}

function stopCamera() {
  state.autoPoseEnabled = false;
  state.pendingPosePayload = null;
  state.poseInFlight = false;
  state.poseTracker?.stop();
  if (state.cameraStream) {
    state.cameraStream.getTracks().forEach((track) => track.stop());
    state.cameraStream = null;
  }
  els.video.srcObject = null;
  els.videoShell.classList.remove("camera-active");
  setCameraLoading(false);
}

function completeTraining() {
  stopTrainingCounter();
  const action = state.currentAction;
  if (!action) return;
  state.currentAction = null;
  const completeButton = document.getElementById("complete-training");
  if (completeButton) {
    completeButton.disabled = true;
    completeButton.textContent = "正在保存…";
  }
  stopCamera();
  const painBefore = els.checkinPainBefore?.value ? Number(els.checkinPainBefore.value) : null;
  const painAfter = els.checkinPainAfter?.value ? Number(els.checkinPainAfter.value) : null;
  const note = els.checkinNote?.value?.trim() || null;

  const finish = (message = "训练已完成，可继续跟练其他动作或返回问诊", toastOptions = {}) => {
    if (completeButton) {
      completeButton.disabled = false;
      completeButton.textContent = "完成训练，返回处方";
    }
    goToStep("prescription");
    showToast(message, toastOptions);
  };

  if (window.APP_CONFIG.DEMO_MODE || !isSessionReady()) {
    finish();
    return;
  }

  submitTrainingCheckin(action, { painBefore, painAfter, note })
    .then(() => {
      finish("训练打卡已保存");
    })
    .catch((error) => {
      finish(
        typeof error.message === "string" ? error.message : "训练打卡保存失败",
        { type: "error" }
      );
    });
}

function setHeaderMenuOpen(open) {
  if (!els.headerActions || !els.headerMenuToggle) return;
  els.headerActions.classList.toggle("open", open);
  els.headerMenuToggle.setAttribute("aria-expanded", open ? "true" : "false");
  els.headerMenuToggle.textContent = open ? "收起" : "更多";
}

function applyDevModeUi() {
  if (window.APP_CONFIG.DEV_MODE) {
    document.body.classList.add("dev-mode");
    return;
  }
  if (els.testDoubaoButton) {
    els.testDoubaoButton.hidden = true;
  }
}

async function testDoubaoConnection() {
  if (window.APP_CONFIG.DEMO_MODE) {
    showWarnToast("请先关闭 Demo 模式再测试 DeepSeek 连接");
    return;
  }

  setLoading(true, "正在测试 DeepSeek API 连接…");
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/test_deepseek`,
      { method: "POST" },
      window.APP_CONFIG.PRESCRIPTION_TIMEOUT_MS
    );
    const data = await response.json();
    if (data.status === "success") {
      showToast("DeepSeek 连接成功，摘要已生成");
      const summaryContent =
        typeof data.summary === "string"
          ? data.summary
          : data.summary?.text || data.summary?.summary || data.summary;
      showDoubaoResult(summaryContent);
    } else {
      showDoubaoResult(data);
      showErrorToast(`DeepSeek 连接失败：${data.detail || "未知错误"}`);
    }
  } catch (error) {
    showDoubaoResult({ error: "DeepSeek 测试请求失败，请检查后端与环境变量" });
    showErrorToast("DeepSeek 测试请求失败，请检查后端与环境变量");
  } finally {
    setLoading(false);
  }
}

function initPainRegions() {
  window.PAIN_REGIONS.forEach((region) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.textContent = region;
    button.addEventListener("click", () => {
      if (state.selectedPainRegions.has(region)) {
        state.selectedPainRegions.delete(region);
        button.classList.remove("selected");
      } else {
        state.selectedPainRegions.add(region);
        button.classList.add("selected");
      }
      if (state.selectedPainRegions.size > 0) {
        els.painRegionsError.textContent = "";
      }
      updateMobilityGuide();
    });
    els.painRegions.appendChild(button);
  });
}

function updateModeBadge() {
  els.modeBadge.textContent = window.APP_CONFIG.DEMO_MODE ? "Demo 模式" : "API 模式";
  els.modeBadge.className = window.APP_CONFIG.DEMO_MODE ? "mode-badge demo" : "mode-badge api";
}

function bindEvents() {
  els.toastClose?.addEventListener("click", hideToast);

  els.authLoginForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitAuth("login");
  });

  els.authRegisterForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitAuth("register");
  });

  els.authTabs().forEach((button) => {
    button.addEventListener("click", () => {
      switchAuthTab(button.dataset.authTab);
    });
  });

  els.mobilityScore.addEventListener("input", (event) => {
    els.mobilityValue.textContent = event.target.value;
    updateMobilityTierDisplay(Number(event.target.value));
  });

  els.intakeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!requireLogin()) return;
    const formData = readFormData();
    if (!validateForm(formData)) return;

    const submitButton = document.getElementById("submit-prescription");
    submitButton.disabled = true;
    submitButton.textContent = "生成中…";
    startPrescriptionLoading();

    try {
      const prescription = await requestPrescription(formData);
      if (!prescription) {
        stopPrescriptionLoading();
        return;
      }
      state.prescription = prescription;
      savePrescriptionToSession(prescription, formData);
      renderPrescription(prescription);
      renderPrescriptionRecap(formData);
      finishPrescriptionLoading();
      goToStep("prescription");
      showToast(
        prescription.source === "api"
          ? "处方已由后端 DeepSeek 服务生成"
          : "已使用本地 Mock 处方"
      );
    } catch (error) {
      stopPrescriptionLoading();
      const isTimeout = error?.name === "AbortError";
      if (error?.code === "red_flag_detected") {
        showRedFlagAlert(error.message, error.redFlags);
        els.symptomsError.textContent = "主诉含红旗症状，请查看屏幕中央预警提示";
        showWarnToast("检测到红旗症状，已暂停生成处方");
      } else if (error?.status === 400) {
        if (error.message.includes("疼痛部位")) {
          els.painRegionsError.textContent = error.message;
        } else {
          els.symptomsError.textContent = error.message;
        }
        showErrorToast(error.message);
      } else {
        showErrorToast(
          isTimeout
            ? "DeepSeek 生成超时，请稍后重试或检查后端配置"
            : "处方服务失败，请检查后端与 DeepSeek_API_KEY"
        );
      }
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "生成康复处方";
      if (prescriptionProgressTimer) {
        window.clearInterval(prescriptionProgressTimer);
        prescriptionProgressTimer = null;
      }
    }
  });

  document.getElementById("back-to-intake").addEventListener("click", () => {
    goToStep("intake");
  });
  document.getElementById("go-history").addEventListener("click", () => {
    goToStep("history");
  });
  document.getElementById("back-to-prescription").addEventListener("click", () => {
    goToStep("prescription");
  });
  document.getElementById("refresh-history").addEventListener("click", () => {
    loadPrescriptionHistory();
    loadTrainingStats();
  });

  document.getElementById("export-prescription-md")?.addEventListener("click", () => exportPrescription("md"));
  document.getElementById("export-prescription-json")?.addEventListener("click", () => exportPrescription("json"));

  els.patientProfileSelect?.addEventListener("change", (event) => {
    const value = event.target.value;
    state.selectedPatientProfileId = value ? Number(value) : null;
    if (state.selectedPatientProfileId) {
      const profile = state.patientProfiles.find((item) => item.id === state.selectedPatientProfileId);
      applyPatientProfileToIntake(profile);
    }
    loadImagingReports();
  });

  document.getElementById("save-patient-profile")?.addEventListener("click", async () => {
    if (!requireLogin()) return;
    const formData = readFormData();
    if (!validateForm(formData)) return;
    try {
      const profile = await createPatientProfileFromIntake(formData);
      if (profile) showToast(`已保存患者档案：${profile.name}`);
      else showErrorToast("患者档案保存失败");
    } catch {
      showErrorToast("患者档案保存失败，请确认后端已启动");
    }
  });

  els.goProgressButton?.addEventListener("click", () => goToStep("progress"));
  els.collaborationEntryButton?.addEventListener("click", () => goToStep("collaboration"));
  document.getElementById("back-from-collaboration")?.addEventListener("click", () => goToStep("prescription"));
  els.doctorEntryButton?.addEventListener("click", () => goToStep("doctor"));
  document.getElementById("back-from-doctor")?.addEventListener("click", () => goToStep("intake"));
  document.querySelectorAll(".report-period-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const period = button.dataset.reportPeriod;
      if (!period || state.progressReportPeriod === period) return;
      state.progressReportPeriod = period;
      document.querySelectorAll(".report-period-btn").forEach((item) => {
        item.classList.toggle("active", item.dataset.reportPeriod === period);
      });
      await loadProgressReport();
    });
  });
  collaborationPage.bindCollaborationEvents();
  els.knowledgeEntryButton?.addEventListener("click", () => goToStep("knowledge"));
  document.getElementById("back-from-knowledge")?.addEventListener("click", () => goToStep("intake"));
  document.getElementById("back-from-progress")?.addEventListener("click", () => goToStep("history"));
  document.getElementById("export-report-md")?.addEventListener("click", exportProgressReport);
  document.getElementById("toggle-voice")?.addEventListener("click", toggleVoice);
  els.adminEntryButton?.addEventListener("click", () => goToStep("admin"));
  els.profilesEntryButton?.addEventListener("click", () => {
    state.profileReturnStep = state.currentStep === "profiles" ? "intake" : state.currentStep;
    goToStep("profiles");
  });
  els.libraryEntryButton?.addEventListener("click", () => goToStep("library"));
  document.getElementById("open-profiles-from-intake")?.addEventListener("click", () => {
    state.profileReturnStep = "intake";
    goToStep("profiles");
  });
  document.getElementById("back-from-profiles")?.addEventListener("click", () => goToStep(state.profileReturnStep || "intake"));
  document.getElementById("back-from-library")?.addEventListener("click", () => goToStep("intake"));
  document.getElementById("profile-create-toggle")?.addEventListener("click", () => {
    resetProfileForm();
    if (els.profileFormCard) els.profileFormCard.hidden = false;
  });
  document.getElementById("profile-form-cancel")?.addEventListener("click", resetProfileForm);
  document.getElementById("refresh-profiles")?.addEventListener("click", loadProfilesPage);
  els.profileForm?.addEventListener("submit", saveProfileForm);
  document.getElementById("upload-imaging-report")?.addEventListener("click", uploadImagingReport);
  document.getElementById("red-flag-dismiss")?.addEventListener("click", hideRedFlagAlert);
  els.redFlagOverlay?.addEventListener("click", (event) => {
    if (event.target === els.redFlagOverlay) hideRedFlagAlert();
  });
  document.getElementById("refresh-library")?.addEventListener("click", loadActionLibrary);
  document.getElementById("library-filter-q")?.addEventListener("input", (event) => {
    state.libraryFilters.q = event.target.value;
    libraryFilterDebounced();
  });
  document.getElementById("library-filter-region")?.addEventListener("change", (event) => {
    state.libraryFilters.bodyRegion = event.target.value;
    renderActionLibraryGrid();
  });
  document.getElementById("library-filter-difficulty")?.addEventListener("change", (event) => {
    state.libraryFilters.difficulty = event.target.value;
    renderActionLibraryGrid();
  });
  bindProfilesPageEvents();
  bindImagingReportEvents();
  bindAdminPanelEvents();
  bindAdminQuickNavEvents();
  bindKnowledgePageEvents();
  bindPrescriptionFeedbackEvents();
  document.getElementById("back-from-admin")?.addEventListener("click", () => goToStep("intake"));

  document.getElementById("demo-start-training")?.addEventListener("click", () => {
    if (state.currentAction) startTraining(state.currentAction);
  });
  document.getElementById("demo-back")?.addEventListener("click", () => goToStep("prescription"));

  document.getElementById("start-camera").addEventListener("click", startCamera);
  els.testDoubaoButton?.addEventListener("click", testDoubaoConnection);
  document.getElementById("clear-doubao-result").addEventListener("click", hideDoubaoResult);
  els.headerMenuToggle?.addEventListener("click", () => {
    const open = !els.headerActions?.classList.contains("open");
    setHeaderMenuOpen(open);
  });
  document.addEventListener("click", (event) => {
    if (!els.headerActions?.classList.contains("open")) return;
    if (event.target.closest(".header-actions") || event.target.closest("#header-menu-toggle")) {
      return;
    }
    setHeaderMenuOpen(false);
  });
  document.getElementById("header-secondary-toggle")?.addEventListener("click", (event) => {
    event.stopPropagation();
    const group = document.getElementById("header-secondary-group");
    setHeaderSecondaryOpen(group?.hidden);
  });
  document.addEventListener("click", (event) => {
    const group = document.getElementById("header-secondary-group");
    if (!group || group.hidden) return;
    if (event.target.closest("#header-secondary-group") || event.target.closest("#header-secondary-toggle")) {
      return;
    }
    setHeaderSecondaryOpen(false);
  });
  document.getElementById("toggle-demo").addEventListener("click", () => {
    window.APP_CONFIG.setDemoMode(!window.APP_CONFIG.DEMO_MODE);
    location.reload();
  });
  document.getElementById("stop-training").addEventListener("click", () => {
    stopCamera();
    stopTrainingCounter();
    resetStartCameraButton();
    goToStep("prescription");
  });
  document.getElementById("complete-training").addEventListener("click", completeTraining);
  els.logoutButton?.addEventListener("click", logoutSession);

  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".action-video-btn, #demo-video-link[data-video-url]");
    if (!btn) return;
    event.preventDefault();
    const url = btn.dataset.videoUrl;
    if (!url) return;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(() => {
        showToast("视频链接已复制，请在浏览器中打开");
      }).catch(() => {
        showToast(`请复制此链接到浏览器打开：${url}`);
      });
    } else {
      showToast(`请复制此链接到浏览器打开：${url}`);
    }
  });
  els.stepButtons().forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) return;
      const step = button.dataset.step;
      if (step !== "login" && !isSessionReady()) return;
      if ((step === "demo" || step === "training") && !state.currentAction) return;
      if (step === "training" && !isActionPoseSupported(state.currentAction)) return;
      if (step === "prescription" && !state.prescription) return;
      goToStep(step);
    });
  });
}

function canRestoreStep(step) {
  const loggedInSteps = new Set([
    "intake",
    "prescription",
    "history",
    "profiles",
    "library",
    "progress",
    "knowledge",
    "collaboration",
    "doctor",
    "admin",
    "demo",
    "training",
  ]);
  if (!loggedInSteps.has(step)) return false;

  if (step === "admin") return state.currentUser?.role === "admin";
  if (step === "doctor") {
    return state.currentUser?.role === "doctor" || state.currentUser?.role === "admin";
  }

  const needsPrescription = new Set(["prescription", "demo", "training", "collaboration"]);
  if (needsPrescription.has(step) && !state.prescription) return false;

  if ((step === "demo" || step === "training") && !state.currentAction) return false;

  return true;
}

function restoreSessionState() {
  if (!isSessionReady()) return false;

  const savedPrescription = loadPrescriptionFromSession();
  const savedStep = sessionStorage.getItem(sessionKey("kj_current_step"));
  const savedFormData = loadFormDataFromSession();

  if (savedPrescription) {
    state.prescription = savedPrescription;
    renderPrescription(savedPrescription);
    renderPrescriptionRecap(savedFormData);
    updatePrescriptionExportBar();
    updatePrescriptionFeedbackCard();
  }

  if (savedStep && canRestoreStep(savedStep)) {
    goToStep(savedStep);
    return true;
  }

  if (state.prescription) {
    goToStep("prescription");
    return true;
  }

  return false;
}

// Register per-step loaders consumed by goToStep (shared/state.js).
registerStepLoader("history", () => {
  loadPrescriptionHistory();
  loadTrainingStats();
});
registerStepLoader("admin", () => loadAdminActions());
registerStepLoader("knowledge", () => loadKnowledgePage());
registerStepLoader("profiles", () => loadProfilesPage());
registerStepLoader("library", () => loadActionLibrary());
registerStepLoader("progress", () => loadProgressPage());
registerStepLoader("collaboration", () => loadCollaborationPage());
registerStepLoader("doctor", () => loadDoctorWorkspace());
registerStepLoader("intake", () => {
  loadPatientProfiles();
  loadImagingReports();
  updateMobilityGuide();
  hideRedFlagAlert();
  if (els.patientProfileSelect?.closest(".field")) {
    els.patientProfileSelect.closest(".field").hidden = window.APP_CONFIG.DEMO_MODE;
  }
});
registerStepLoader("prescription", () => {
  updatePrescriptionExportBar();
  updatePrescriptionFeedbackCard();
  renderPrescriptionCollaboration();
});
setStepNavEl(document.querySelector(".step-nav"));

function init() {
  state.auth = readStoredAuth();
  if (state.auth?.user) {
    syncCurrentUserFromAuth();
  }

  initPainRegions();
  initProfilePainRegions();
  bindEvents();
  applyDevModeUi();
  updateModeBadge();
  updateAuthStatus();
  updateAdminEntry();
  updateMobilityTierDisplay(Number(els.mobilityScore?.value || 5));
  updateMobilitySummary(Number(els.mobilityScore?.value || 5));
  switchAuthTab("login");

  if ("speechSynthesis" in window) {
    window.speechSynthesis.addEventListener("voiceschanged", primeSpeechSynthesis);
    primeSpeechSynthesis();
  }

  if (isSessionReady()) {
    loadPatientProfiles();
    if (!restoreSessionState()) {
      goToStep("intake");
    }
  } else {
    clearPrescriptionSession();
    goToStep("login");
  }
}

init();
