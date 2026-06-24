import { PoseTracker } from "./pose.js";

const state = {
  currentStep: "login",
  prescription: null,
  currentAction: null,
  cameraStream: null,
  selectedPainRegions: new Set(),
  poseTracker: null,
  poseInFlight: false,
  pendingPosePayload: null,
  lastPoseSentAt: 0,
  autoPoseEnabled: false,
  currentUser: null,
  auth: null,
  authTab: "login",
  selectedPatientProfileId: null,
  patientProfiles: [],
  trainingLastScore: null,
  adminEditingId: null,
  adminFilters: { q: "", bodyRegion: "" },
  adminPanelData: null,
  adminScrollFocusTimer: null,
};

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
  adminActionsPanel: document.getElementById("admin-actions-panel"),
  adminQuickNav: document.getElementById("admin-quick-nav"),
};

function readStoredAuth() {
  try {
    return JSON.parse(localStorage.getItem("kj_auth") || "null");
  } catch (error) {
    return null;
  }
}

function saveAuth(auth) {
  state.auth = auth;
  if (auth) {
    localStorage.setItem("kj_auth", JSON.stringify(auth));
    syncCurrentUserFromAuth();
  } else {
    localStorage.removeItem("kj_auth");
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
  showToast("请先登录或注册后再继续");
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
      showToast(typeof detail === "string" ? detail : "账号或密码错误");
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
      showToast(`欢迎你，${loginData.user.nickname}`);
      loadPatientProfiles();
      updateAdminEntry();
      goToStep("intake");
      return;
    }

    const data = await response.json();
    saveAuth({ token: data.token, user: data.user });
    showToast(`欢迎你，${data.user.nickname}`);
    loadPatientProfiles();
    updateAdminEntry();
    goToStep("intake");
  } catch (error) {
    const isNetworkError = error instanceof TypeError;
    showToast(
      error?.name === "AbortError"
        ? "登录请求超时，请确认后端已启动"
        : isNetworkError
          ? "无法连接后端，请确认服务运行在 localhost:8000"
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
  goToStep("login");
  showToast("已退出登录");
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.classList.remove("show");
  }, 3200);
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
        { text: "正在调用豆包大模型…", progress: 48 },
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

function goToStep(step) {
  state.currentStep = step;
  setHeaderMenuOpen(false);
  sessionStorage.setItem("kj_current_step", step);
  els.pages().forEach((page) => {
    page.classList.toggle("active", page.id === `page-${step}`);
  });
  els.stepButtons().forEach((button) => {
    const isCurrent = button.dataset.step === step;
    button.classList.toggle("active", isCurrent);
    const targetStep = button.dataset.step;
    if (targetStep === "login") {
      button.disabled = false;
    } else if (!isSessionReady()) {
      button.disabled = true;
    } else if (targetStep === "prescription") {
      button.disabled = !state.prescription;
    } else if (targetStep === "demo") {
      button.disabled = !state.currentAction;
    } else if (targetStep === "training") {
      button.disabled = !state.currentAction || !window.APP_CONFIG.isPoseSupported(state.currentAction?.id);
    } else {
      button.disabled = false;
    }
  });
  updateUserIdentity();
  if (step === "history") {
    loadPrescriptionHistory();
    loadTrainingStats();
  }
  if (step === "admin") {
    loadAdminActions();
  }
  if (step === "intake") {
    loadPatientProfiles();
    if (els.patientProfileSelect?.closest(".field")) {
      els.patientProfileSelect.closest(".field").hidden = window.APP_CONFIG.DEMO_MODE;
    }
  }
  if (step === "prescription") {
    updatePrescriptionExportBar();
  }
}

function savePrescriptionToSession(prescription, formData) {
  try {
    sessionStorage.setItem("kj_prescription", JSON.stringify(prescription));
    if (formData) sessionStorage.setItem("kj_form_data", JSON.stringify(formData));
  } catch { /* quota exceeded or private mode */ }
}

function loadPrescriptionFromSession() {
  try {
    const raw = sessionStorage.getItem("kj_prescription");
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function loadFormDataFromSession() {
  try {
    const raw = sessionStorage.getItem("kj_form_data");
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function clearPrescriptionSession() {
  sessionStorage.removeItem("kj_prescription");
  sessionStorage.removeItem("kj_form_data");
  sessionStorage.removeItem("kj_current_step");
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
      <dt>疼痛部位</dt><dd>${regions}</dd>
      <dt>主诉</dt><dd>${formData.symptoms || "未填写"}</dd>
      <dt>伤病史</dt><dd>${formData.history || "无"}</dd>
      <dt>活动度自评</dt><dd><span class="recap-mobility recap-mobility-${mobility.tier}">${formData.mobility_score ?? "—"}/10 · ${mobility.label}</span></dd>
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

  return !painRegionError && !symptomError;
}

async function parseApiError(response) {
  const raw = await response.text();
  try {
    const data = JSON.parse(raw);
    return data.detail || raw;
  } catch {
    return raw || `HTTP ${response.status}`;
  }
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
  const isAdmin = state.currentUser?.role === "admin";
  if (els.adminEntryButton) {
    els.adminEntryButton.hidden = !isAdmin || window.APP_CONFIG.DEMO_MODE;
  }
  if (els.adminQuickNav) {
    els.adminQuickNav.hidden = !isAdmin || window.APP_CONFIG.DEMO_MODE;
  }
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

async function loadPatientProfiles() {
  if (!isSessionReady() || window.APP_CONFIG.DEMO_MODE || !els.patientProfileSelect) return;
  try {
    const response = await fetchWithTimeout(`${window.APP_CONFIG.API_BASE}/patient_profiles`, {
      headers: authHeaders(),
    });
    if (!response.ok) return;
    state.patientProfiles = await response.json();
    renderPatientProfileSelect();
  } catch {
    // 患者档案为可选能力，加载失败不阻断问诊
  }
}

function renderPatientProfileSelect() {
  if (!els.patientProfileSelect) return;
  const options = [
    `<option value="">不关联患者档案（使用当前账号信息）</option>`,
    ...state.patientProfiles.map(
      (profile) =>
        `<option value="${profile.id}"${state.selectedPatientProfileId === profile.id ? " selected" : ""}>${profile.name}${profile.age ? ` · ${profile.age}岁` : ""}</option>`
    ),
  ];
  els.patientProfileSelect.innerHTML = options.join("");
}

async function createPatientProfileFromIntake(formData) {
  if (!isSessionReady() || window.APP_CONFIG.DEMO_MODE) return null;
  const response = await fetchWithTimeout(
    `${window.APP_CONFIG.API_BASE}/patient_profiles`,
    {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        name: formData.name || state.currentUser?.name || "未命名患者",
        age: formData.age ?? state.currentUser?.age ?? null,
        gender: state.currentUser?.gender ?? null,
        pain_regions: formData.pain_regions,
        history: formData.history,
      }),
    }
  );
  if (!response.ok) return null;
  const profile = await response.json();
  state.patientProfiles.push(profile);
  state.selectedPatientProfileId = profile.id;
  renderPatientProfileSelect();
  return profile;
}

async function exportPrescription(format) {
  const prescriptionId = state.prescription?.id;
  if (!prescriptionId || window.APP_CONFIG.DEMO_MODE) {
    showToast("请先登录并在 API 模式下生成可导出的处方");
    return;
  }
  if (!requireLogin()) return;
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/prescriptions/${prescriptionId}/export?format=${format}`,
      { headers: authHeaders() }
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
    showToast("处方导出失败，请确认已登录且后端可用");
  }
}

async function submitTrainingCheckin(action, options = {}) {
  if (!isSessionReady() || window.APP_CONFIG.DEMO_MODE) return null;
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
  if (!isSessionReady() || window.APP_CONFIG.DEMO_MODE) {
    els.trainingStatsPanel.hidden = true;
    return;
  }
  els.trainingStatsPanel.hidden = false;
  els.trainingStatsPanel.innerHTML = `<p class="hint">正在加载训练统计…</p>`;
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/training_checkins/visualization?days=30`,
      { headers: authHeaders() }
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const trend = data.trend?.points || [];
    const recent = trend.slice(-7);
    els.trainingStatsPanel.innerHTML = `
      <h3>训练统计（近 30 天）</h3>
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
    els.trainingStatsPanel.innerHTML = `<p class="hint">训练统计加载失败，请确认后端已启动。</p>`;
  }
}

function getApiDocsUrl() {
  const apiBase = window.APP_CONFIG.API_BASE || "";
  if (apiBase.endsWith("/api")) {
    return `${apiBase.slice(0, -4)}/docs`;
  }
  return `${window.location.protocol}//${window.location.hostname}:8000/docs`;
}

function escapeAdminText(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
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

function renderAdminPanel({ actions, meta, deploy, testReport }) {
  const regionOptions = (meta?.body_regions || [])
    .map(
      (region) =>
        `<option value="${escapeAdminText(region)}"${state.adminFilters.bodyRegion === region ? " selected" : ""}>${escapeAdminText(region)}</option>`
    )
    .join("");

  return `
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

async function loadAdminActions(options = {}) {
  if (!els.adminActionsPanel || state.currentUser?.role !== "admin") return;
  const { silent = false } = options;
  const scrollY = window.scrollY;

  if (!silent) {
    els.adminActionsPanel.innerHTML = `<p class="hint">正在加载管理后台…</p>`;
  }

  try {
    const [actionsRes, metaRes, deployRes, testReport] = await Promise.all([
      fetchWithTimeout(buildAdminActionsUrl(), { headers: authHeaders() }),
      fetchWithTimeout(`${window.APP_CONFIG.API_BASE}/admin/actions/meta`, { headers: authHeaders() }),
      fetchWithTimeout(`${window.APP_CONFIG.API_BASE}/deployment/info`),
      fetchAdminTestReport(),
    ]);
    if (!actionsRes.ok) throw new Error("admin actions unavailable");
    const actions = await actionsRes.json();
    const meta = metaRes.ok ? await metaRes.json() : null;
    const deploy = deployRes.ok ? await deployRes.json() : null;
    renderAdminPanelToDom({ actions, meta, deploy, testReport });
    if (silent) {
      window.scrollTo(0, scrollY);
    }
  } catch {
    els.adminActionsPanel.innerHTML = `<p class="hint">管理员面板加载失败，请确认账号具备 admin 权限且后端已启动。</p>`;
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
        showToast(error.message || "删除失败");
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
  });

  els.adminActionsPanel.addEventListener("input", (event) => {
    if (state.currentUser?.role !== "admin") return;
    if (event.target.id !== "admin-filter-q") return;
    state.adminFilters.q = event.target.value;
    clearTimeout(window.adminFilterTimer);
    window.adminFilterTimer = window.setTimeout(() => {
      loadAdminActions({ silent: true });
    }, 300);
  });

  els.adminActionsPanel.addEventListener("submit", async (event) => {
    if (state.currentUser?.role !== "admin") return;
    const createForm = event.target.closest("#admin-create-form");
    if (createForm) {
      event.preventDefault();
      try {
        await submitAdminCreate(createForm);
      } catch (error) {
        showToast(error.message || "新增动作失败");
      }
      return;
    }

    const editForm = event.target.closest(".admin-edit-form");
    if (editForm) {
      event.preventDefault();
      try {
        await submitAdminEdit(editForm.dataset.actionId, editForm);
      } catch (error) {
        showToast(error.message || "保存失败");
      }
    }
  });
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
  els.userDisplayName.textContent = state.currentUser.name;
  els.userAvatar.textContent = state.currentUser.name.slice(0, 1);
  els.historyUserName.textContent = `当前用户：${state.currentUser.name}`;
  els.historyUserMeta.textContent = state.currentUser.age
    ? `年龄：${state.currentUser.age} 岁`
    : "年龄未填写";
}

function renderHistoryCard(prescription) {
  const header = [
    prescription.patient_name ? `患者：${prescription.patient_name}` : "",
    prescription.patient_age ? `年龄：${prescription.patient_age}` : "",
  ]
    .filter(Boolean)
    .join(" | ");

  return `
    <article class="history-card">
      <h4>处方 #${prescription.id || "N/A"}</h4>
      ${header ? `<div class="meta">${header}</div>` : ""}
      <div class="summary-block">${formatSummary(prescription.summary)}</div>
      <ul>
        ${prescription.actions
          .map(
            (action) =>
              `<li><strong>${action.name}</strong>：${action.sets}组 × ${action.reps}次${
                action.note ? `（${action.note}）` : ""
              }</li>`
          )
          .join("")}
      </ul>
      ${
        prescription.id && !window.APP_CONFIG.DEMO_MODE
          ? `<div class="history-card-actions">
              <button class="btn btn-secondary btn-small history-export-md" type="button" data-id="${prescription.id}">导出 MD</button>
              <button class="btn btn-secondary btn-small history-export-json" type="button" data-id="${prescription.id}">导出 JSON</button>
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
    const response = await fetchWithTimeout(`${window.APP_CONFIG.API_BASE}/prescriptions`, {
      headers: authHeaders(),
    });
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
    els.prescriptionHistory.textContent = hint;
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
    const detail = await parseApiError(response);
    const error = new Error(detail || `HTTP ${response.status}`);
    error.status = response.status;
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

function isValidVideoUrl(url) {
  return typeof url === "string" && url.startsWith("http");
}

function renderActionVideoMarkup(action) {
  if (isValidVideoUrl(action.videoUrl)) {
    return `<button class="btn btn-secondary btn-small action-video-btn" type="button" data-video-url="${escapeAdminText(action.videoUrl)}">▶ 观看示范视频</button>`;
  }
  return "";
}

function renderPrescription(prescription) {
  const metaParts = [];
  if (prescription.id) metaParts.push(`处方编号 #${prescription.id}`);
  if (prescription.patient_name) metaParts.push(`患者：${prescription.patient_name}`);
  if (prescription.patient_age) metaParts.push(`年龄：${prescription.patient_age}`);
  if (prescription.source === "mock") metaParts.push("来源：本地 Mock");
  if (prescription.source === "api") metaParts.push("来源：豆包后端 API");
  els.prescriptionMeta.textContent = metaParts.join(" · ");
  els.prescriptionSummary.innerHTML = formatSummary(prescription.summary);
  els.actionList.innerHTML = "";

  prescription.actions.forEach((action) => {
    const poseSupported = window.APP_CONFIG.isPoseSupported(action.id);
    const card = document.createElement("article");
    card.className = "action-card card";
    card.innerHTML = `
      <div class="action-image-wrap">
        <img
          src="${window.APP_CONFIG.assetUrl(action.image)}"
          alt="${action.name}示意图"
          loading="lazy"
          onerror="handleActionImageError(this)"
        />
        <span class="action-image-placeholder">示意图待上传</span>
      </div>
      <div class="action-card-body">
        <h3>${action.name}</h3>
        <div class="action-meta">
          <span class="tag">${action.sets} 组</span>
          <span class="tag">${action.reps} 次/组</span>
          ${action.frequency ? `<span class="tag tag-frequency">${action.frequency}</span>` : ""}
          <span class="tag ${poseSupported ? "tag-supported" : "tag-pending"}">
            ${poseSupported ? "支持实时纠正" : "暂不支持实时纠正"}
          </span>
        </div>
        <p>${action.description || "按医嘱缓慢完成动作，注意呼吸节奏。"}</p>
        ${renderActionVideoMarkup(action)}
        ${
          action.note
            ? `<p><strong>注意：</strong>${action.note}</p>`
            : ""
        }
        ${
          action.contraindications
            ? `<p class="hint"><strong>禁忌：</strong>${action.contraindications}</p>`
            : ""
        }
        ${
          action.progression
            ? `<p class="hint"><strong>进阶：</strong>${action.progression}</p>`
            : ""
        }
        ${
          action.regression
            ? `<p class="hint"><strong>降阶：</strong>${action.regression}</p>`
            : ""
        }
        <button class="btn btn-primary view-demo" type="button" data-action-id="${action.id || ""}">
          查看演示${poseSupported ? " / 跟练" : ""}
        </button>
        ${poseSupported ? "" : `<p class="hint support-hint">${window.APP_CONFIG.getUnsupportedPoseHint()}</p>`}
      </div>
    `;
    els.actionList.appendChild(card);
  });

  updatePrescriptionExportBar();

  els.actionList.querySelectorAll(".view-demo").forEach((button) => {
    button.addEventListener("click", () => {
      const actionId = button.dataset.actionId;
      const action = prescription.actions.find((item) => item.id === actionId);
      if (!action) {
        showToast("动作信息缺失，请稍后重试");
        return;
      }
      showDemo(action);
    });
  });
}

function updatePoseFeedback(result) {
  const { feedback, score, status } = result;
  if (typeof score === "number") {
    state.trainingLastScore = score;
  }
  const latest = feedback?.[0] || "暂无反馈";

  if (els.feedbackOverlay) els.feedbackOverlay.textContent = latest;
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
  };
}

function averageVisibility(visibility) {
  if (!visibility?.length) return 1;
  return visibility.reduce((sum, value) => sum + value, 0) / visibility.length;
}

function getPoseActionId(action) {
  return action?.backendId || window.APP_CONFIG.getBackendActionId(action?.id) || action?.id;
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
    console.warn("partial pose frame received", {
      keypoints: frame.keypoints?.length,
      visibility: frame.visibility?.length,
    });
    // 允许继续发送不完整的关键点，让后端决定如何处理
  }

  const avgVisibility = averageVisibility(frame.visibility);
  if (avgVisibility < window.APP_CONFIG.POSE_VISIBILITY_MIN) {
    // 原先这里会阻断并显示提示；现改为仅记录警告并继续发送，由后端决定如何处理
    console.warn("low average visibility", { avgVisibility });
  }

  const now = Date.now();
  const payload = {
    action_id: getPoseActionId(state.currentAction),
    keypoints: frame.keypoints,
    visibility: frame.visibility,
    timestamp: now,
  };

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
  state.currentAction = action;

  const nameEl = document.getElementById("demo-action-name");
  const imgEl = document.getElementById("demo-action-image");
  const metaEl = document.getElementById("demo-meta");
  const descEl = document.getElementById("demo-action-desc");
  const contraSec = document.getElementById("demo-contraindications-section");
  const contraEl = document.getElementById("demo-contraindications");
  const progSec = document.getElementById("demo-progression-section");
  const progEl = document.getElementById("demo-progression");
  const videoWrap = document.getElementById("demo-video-wrap");
  const videoLink = document.getElementById("demo-video-link");
  const videoHintEl = document.getElementById("demo-video-hint");
  const startBtn = document.getElementById("demo-start-training");

  if (nameEl) nameEl.textContent = action.name;

  if (imgEl) {
    imgEl.classList.remove("is-missing");
    imgEl.src = window.APP_CONFIG.assetUrl(action.image);
    imgEl.alt = `${action.name}示意图`;
  }

  if (metaEl) {
    const parts = [];
    if (action.sets) parts.push(`${action.sets} 组`);
    if (action.reps) parts.push(`${action.reps} 次/组`);
    if (action.frequency) parts.push(action.frequency);
    metaEl.innerHTML = parts.map((p) => `<span class="tag">${p}</span>`).join("");
  }

  if (descEl) descEl.textContent = action.description || "按医嘱缓慢完成动作，注意呼吸节奏。";

  if (contraSec && contraEl) {
    contraSec.hidden = !action.contraindications;
    contraEl.textContent = action.contraindications || "";
  }

  if (progSec && progEl) {
    progSec.hidden = !action.progression;
    progEl.textContent = action.progression || "";
  }

  if (videoWrap && videoLink && videoHintEl) {
    if (isValidVideoUrl(action.videoUrl)) {
      videoLink.href = "#";
      videoLink.dataset.videoUrl = action.videoUrl;
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

  const poseSupported = window.APP_CONFIG.isPoseSupported(action.id);
  if (startBtn) {
    startBtn.hidden = !poseSupported;
  }

  goToStep("demo");
}

function startTraining(action) {
  if (!window.APP_CONFIG.isPoseSupported(action.id)) {
    showToast("该动作暂不支持实时纠正，请选择支持的动作进行跟练。");
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
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    showToast("当前浏览器不支持摄像头");
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
    showToast("摄像头已启动，正在实时分析动作");
  } catch (error) {
    stopCamera();
    showToast("无法访问摄像头或姿态模型加载失败，请检查浏览器权限与网络");
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

  const finish = (message = "训练已完成，可继续跟练其他动作或返回问诊") => {
    if (completeButton) {
      completeButton.disabled = false;
      completeButton.textContent = "完成训练，返回处方";
    }
    goToStep("prescription");
    showToast(message);
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
      finish(typeof error.message === "string" ? error.message : "训练打卡保存失败");
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
    showToast("请先关闭 Demo 模式再测试豆包连接");
    return;
  }

  setLoading(true, "正在测试豆包 API 连接…");
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/test_doubao`,
      { method: "POST" },
      window.APP_CONFIG.PRESCRIPTION_TIMEOUT_MS
    );
    const data = await response.json();
    if (data.status === "success") {
      showToast("豆包连接成功，摘要已生成");
      const summaryContent =
        typeof data.summary === "string"
          ? data.summary
          : data.summary?.text || data.summary?.summary || data.summary;
      showDoubaoResult(summaryContent);
    } else {
      showDoubaoResult(data);
      showToast(`豆包连接失败：${data.detail || "未知错误"}`);
    }
  } catch (error) {
    showDoubaoResult({ error: "豆包测试请求失败，请检查后端与环境变量" });
    showToast("豆包测试请求失败，请检查后端与环境变量");
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
    });
    els.painRegions.appendChild(button);
  });
}

function updateModeBadge() {
  els.modeBadge.textContent = window.APP_CONFIG.DEMO_MODE ? "Demo 模式" : "API 模式";
  els.modeBadge.className = window.APP_CONFIG.DEMO_MODE ? "mode-badge demo" : "mode-badge api";
}

function bindEvents() {
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
          ? "处方已由后端豆包服务生成"
          : "已使用本地 Mock 处方"
      );
    } catch (error) {
      stopPrescriptionLoading();
      const isTimeout = error?.name === "AbortError";
      if (error?.status === 400) {
        if (error.message.includes("疼痛部位")) {
          els.painRegionsError.textContent = error.message;
        } else {
          els.symptomsError.textContent = error.message;
        }
        showToast(error.message);
      } else {
        showToast(
          isTimeout
            ? "豆包生成超时，请稍后重试或检查后端配置"
            : "处方服务失败，请检查后端与 DOUBAO_API_KEY"
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
  });

  document.getElementById("save-patient-profile")?.addEventListener("click", async () => {
    if (!requireLogin()) return;
    const formData = readFormData();
    if (!validateForm(formData)) return;
    try {
      const profile = await createPatientProfileFromIntake(formData);
      if (profile) showToast(`已保存患者档案：${profile.name}`);
      else showToast("患者档案保存失败");
    } catch {
      showToast("患者档案保存失败，请确认后端已启动");
    }
  });

  els.adminEntryButton?.addEventListener("click", () => goToStep("admin"));
  bindAdminPanelEvents();
  bindAdminQuickNavEvents();
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
  document.getElementById("toggle-demo").addEventListener("click", () => {
    window.APP_CONFIG.setDemoMode(!window.APP_CONFIG.DEMO_MODE);
    location.reload();
  });
  document.getElementById("stop-training").addEventListener("click", () => {
    stopCamera();
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
      if (step === "training" && !window.APP_CONFIG.isPoseSupported(state.currentAction?.id)) return;
      if (step === "prescription" && !state.prescription) return;
      goToStep(step);
    });
  });
}

function restoreSessionState() {
  if (!isSessionReady()) return false;

  const savedPrescription = loadPrescriptionFromSession();
  const savedStep = sessionStorage.getItem("kj_current_step");
  const savedFormData = loadFormDataFromSession();

  if (savedPrescription && savedStep) {
    state.prescription = savedPrescription;
    renderPrescription(savedPrescription);
    renderPrescriptionRecap(savedFormData);
    updatePrescriptionExportBar();

    const validSteps = ["prescription", "history", "intake"];
    const targetStep = validSteps.includes(savedStep) ? savedStep : "prescription";
    goToStep(targetStep);
    return true;
  }
  return false;
}

function init() {
  state.auth = readStoredAuth();
  if (state.auth?.user) {
    syncCurrentUserFromAuth();
  }

  initPainRegions();
bindEvents();
applyDevModeUi();
updateModeBadge();
updateAuthStatus();
updateAdminEntry();
switchAuthTab("login");

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
