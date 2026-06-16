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
  trainingPoseHint: document.getElementById("training-pose-hint"),
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
  };
  updateUserIdentity();
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
      goToStep("intake");
      return;
    }

    const data = await response.json();
    saveAuth({ token: data.token, user: data.user });
    showToast(`欢迎你，${data.user.nickname}`);
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
    } else if (targetStep === "training") {
      button.disabled = !state.currentAction;
    } else {
      button.disabled = false;
    }
  });
  updateUserIdentity();
  if (step === "history") {
    loadPrescriptionHistory();
  }
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
  return {
    name: state.currentUser?.name || null,
    age: state.currentUser?.age || null,
    symptoms: formData.get("symptoms")?.toString().trim() || "",
    history: formData.get("history")?.toString().trim() || null,
    pain_regions: Array.from(state.selectedPainRegions),
    mobility_score: Number(formData.get("mobility_score") || 5),
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
  return summary
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => `<p>${line}</p>`)
    .join("");
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
    patient_name: data.patient_name,
    patient_age: data.patient_age,
    summary: data.summary,
    actions: data.actions.map((action) => window.MockService.enrichAction(action)),
    source: "api",
  };
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
      <img src="${window.APP_CONFIG.assetUrl(action.image)}" alt="${action.name}示意图" />
      <div class="action-card-body">
        <h3>${action.name}</h3>
        <div class="action-meta">
          <span class="tag">${action.sets} 组</span>
          <span class="tag">${action.reps} 次/组</span>
          <span class="tag ${poseSupported ? "tag-supported" : "tag-pending"}">
            ${poseSupported ? "支持实时纠正" : "暂不支持实时纠正"}
          </span>
        </div>
        <p>${action.description || "按医嘱缓慢完成动作，注意呼吸节奏。"}</p>
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
          poseSupported
            ? `<button class="btn btn-primary start-training" type="button" data-action-id="${action.id || ""}">
          开始跟练
        </button>`
            : `<button class="btn btn-secondary unsupported-training" type="button" data-action-id="${action.id || ""}">
          仅查看处方
        </button>
        <p class="hint support-hint">当前版本实时纠正仅支持“靠墙静蹲”和“颈部侧屈拉伸”。</p>`
        }
      </div>
    `;
    els.actionList.appendChild(card);
  });

  els.actionList.querySelectorAll(".start-training").forEach((button) => {
    button.addEventListener("click", () => {
      const actionId = button.dataset.actionId;
      const action = prescription.actions.find((item) => item.id === actionId);
      if (!action) {
        showToast("动作信息缺失，请稍后重试");
        return;
      }
      startTraining(action);
    });
  });

  els.actionList.querySelectorAll(".unsupported-training").forEach((button) => {
    button.addEventListener("click", () => {
      showToast("该动作暂不支持实时纠正，可先参考处方说明完成训练。");
    });
  });
}

function updatePoseFeedback(result) {
  const { feedback, score, status } = result;
  const latest = feedback?.[0] || "暂无反馈";

  els.feedbackOverlay.textContent = latest;
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

function updateTrainingPoseHint(actionId) {
  if (!els.trainingPoseHint) return;
  const catalogId = window.APP_CONFIG.normalizeCatalogActionId(actionId);
  if (catalogId === "wall_squat") {
    els.trainingPoseHint.textContent = "侧对镜头，便于观察膝部弯曲角度";
    return;
  }
  if (catalogId === "neck_side_bend") {
    els.trainingPoseHint.textContent = "侧对镜头，便于捕捉头颈侧屈幅度";
    return;
  }
  els.trainingPoseHint.textContent = "保持全身入镜，动作缓慢可控";
}

function queuePosePayload(frame) {
  if (!state.currentAction?.id || !state.autoPoseEnabled) return;

  const avgVisibility = averageVisibility(frame.visibility);
  if (avgVisibility < window.APP_CONFIG.POSE_VISIBILITY_MIN) {
    state.pendingPosePayload = null;
    updatePoseFeedback({
      feedback: ["请调整站位，确保全身入镜且光线充足"],
      score: null,
      status: "warning",
    });
    els.statusText.textContent = "检测受阻";
    return;
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
  els.trainingActionName.textContent = `${action.name} · ${action.sets} 组 × ${action.reps} 次`;
  updateTrainingPoseHint(action.id);
  els.feedbackOverlay.textContent = "请先阅读拍摄建议，再启动摄像头";
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
    els.feedbackOverlay.textContent = "等待检测…";
    els.statusText.textContent = "实时检测中";
    showToast("摄像头已启动，正在实时分析动作");
  } catch (error) {
    stopCamera();
    showToast(error?.message?.includes("MediaPipe")
      ? "姿态模型加载失败，请检查网络后重试"
      : "无法访问摄像头，请检查浏览器权限");
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
  stopCamera();
  state.currentAction = null;
  goToStep("prescription");
  showToast("训练已完成，可继续跟练其他动作或返回问诊");
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
      renderPrescription(prescription);
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
  });

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

  els.stepButtons().forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) return;
      const step = button.dataset.step;
      if (step !== "login" && !isSessionReady()) return;
      if (step === "training" && !state.currentAction) return;
      if (step === "prescription" && !state.prescription) return;
      goToStep(step);
    });
  });
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
  switchAuthTab("login");

  if (isSessionReady()) {
    goToStep("intake");
  } else {
    goToStep("login");
  }
}

init();
