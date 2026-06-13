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
};

const els = {
  stepButtons: () => document.querySelectorAll(".step-item"),
  pages: () => document.querySelectorAll(".page"),
  loginForm: document.getElementById("login-form"),
  loginName: document.getElementById("login-name"),
  loginAge: document.getElementById("login-age"),
  loginNameError: document.getElementById("login-name-error"),
  loginAgeError: document.getElementById("login-age-error"),
  userIdentity: document.getElementById("user-identity"),
  userAvatar: document.getElementById("user-avatar"),
  userDisplayName: document.getElementById("user-display-name"),
  userDisplayAge: document.getElementById("user-display-age"),
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
  trainingActionName: document.getElementById("training-action-name"),
  videoShell: document.getElementById("video-shell"),
  video: document.getElementById("video"),
  overlay: document.getElementById("overlay"),
  videoPlaceholder: document.getElementById("video-placeholder"),
  feedbackOverlay: document.getElementById("feedback-overlay"),
  scoreBadge: document.getElementById("score-badge"),
  statusDot: document.getElementById("status-dot"),
  statusText: document.getElementById("status-text"),
  feedbackList: document.getElementById("feedback-list"),
  demoHint: document.getElementById("demo-hint"),
  modeBadge: document.getElementById("mode-badge"),
  toast: document.getElementById("toast"),
  authForm: document.getElementById("auth-form"),
  authAccount: document.getElementById("auth-account"),
  authPassword: document.getElementById("auth-password"),
  authNickname: document.getElementById("auth-nickname"),
  authGender: document.getElementById("auth-gender"),
  authAge: document.getElementById("auth-age"),
  authStatus: document.getElementById("auth-status"),
  loginButton: document.getElementById("login-button"),
  registerButton: document.getElementById("register-button"),
  logoutButton: document.getElementById("logout-button"),
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
  } else {
    localStorage.removeItem("kj_auth");
  }
  updateAuthStatus();
}

function authHeaders(extra = {}) {
  return state.auth?.token
    ? { ...extra, Authorization: `Bearer ${state.auth.token}` }
    : extra;
}

function requireLogin() {
  if (window.APP_CONFIG.DEMO_MODE || state.auth?.token) {
    return true;
  }
  showToast("请先登录后再使用真实后端服务");
  return false;
}

function updateAuthStatus() {
  if (!els.authStatus) return;
  if (window.APP_CONFIG.DEMO_MODE) {
    els.authStatus.textContent = "Demo 模式";
    els.logoutButton.disabled = true;
    return;
  }
  if (state.auth?.user) {
    els.authStatus.textContent = `已登录：${state.auth.user.nickname}`;
    els.logoutButton.disabled = false;
  } else {
    els.authStatus.textContent = "未登录";
    els.logoutButton.disabled = true;
  }
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.classList.remove("show");
  }, 3200);
}

function setLoading(active, text = "正在处理…") {
  els.loadingOverlay.classList.toggle("active", active);
  els.loadingText.textContent = text;
}

function goToStep(step) {
  state.currentStep = step;
  els.pages().forEach((page) => {
    page.classList.toggle("active", page.id === `page-${step}`);
  });
  els.stepButtons().forEach((button) => {
    const isCurrent = button.dataset.step === step;
    button.classList.toggle("active", isCurrent);
    const targetStep = button.dataset.step;
    if (targetStep === "login") {
      button.disabled = false;
    } else if (!state.currentUser) {
      button.disabled = true;
    } else if (targetStep === "prescription") {
      button.disabled = !state.prescription;
    } else if (targetStep === "training") {
      button.disabled = !state.currentAction;
    } else {
      button.disabled = false;
    }
  });
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

function readLoginData() {
  const formData = new FormData(els.loginForm);
  return {
    name: formData.get("login_name")?.toString().trim() || "",
    age: formData.get("login_age") ? Number(formData.get("login_age")) : null,
  };
}

function validateLoginForm(loginData) {
  let valid = true;
  if (!loginData.name) {
    els.loginNameError.textContent = "请输入姓名";
    valid = false;
  } else {
    els.loginNameError.textContent = "";
  }

  if (!loginData.age || loginData.age < 1 || loginData.age > 120) {
    els.loginAgeError.textContent = "请输入有效年龄";
    valid = false;
  } else {
    els.loginAgeError.textContent = "";
  }

  return valid;
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

function persistCurrentUser() {
  if (!state.currentUser) return;
  localStorage.setItem("kj_current_user", JSON.stringify(state.currentUser));
}

function loadPersistedUser() {
  const raw = localStorage.getItem("kj_current_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function updateUserIdentity() {
  if (!state.currentUser) {
    els.userIdentity.hidden = true;
    els.historyUserName.textContent = "当前用户：未登录";
    els.historyUserMeta.textContent = "登录后可查看该用户的历史处方";
    return;
  }

  els.userIdentity.hidden = false;
  els.userDisplayName.textContent = state.currentUser.name;
  els.userDisplayAge.textContent = `${state.currentUser.age} 岁`;
  els.userAvatar.textContent = state.currentUser.name.slice(0, 1);
  els.historyUserName.textContent = `当前用户：${state.currentUser.name}`;
  els.historyUserMeta.textContent = `年龄：${state.currentUser.age} 岁`;
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
  if (window.APP_CONFIG.DEMO_MODE) {
    els.prescriptionHistory.textContent = "Demo 模式下不加载历史处方。";
    return;
  }
  if (!state.currentUser) {
    els.prescriptionHistory.textContent = "请先登录后再查看历史处方。";
    return;
  }

  els.prescriptionHistory.textContent = "正在加载…";
  if (!requireLogin()) {
    els.prescriptionHistory.textContent = "请先登录后查看历史处方。";
    return;
  }
  try {
    const response = await fetchWithTimeout(`${window.APP_CONFIG.API_BASE}/prescriptions`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const filtered = Array.isArray(data)
      ? data.filter((item) => item.patient_name === state.currentUser.name)
      : [];
    if (filtered.length === 0) {
      els.prescriptionHistory.textContent = "暂无处方记录。";
      return;
    }
    els.prescriptionHistory.innerHTML = filtered.map(renderHistoryCard).join("");
  } catch (error) {
    const hint =
      error?.name === "AbortError"
        ? "历史处方请求超时，请确认后端已启动。"
        : "加载失败，请确认后端已启动且 CORS 已配置。";
    els.prescriptionHistory.textContent = hint;
  }
}

async function requestPrescription(formData) {
  if (window.APP_CONFIG.DEMO_MODE) {
    await new Promise((resolve) => window.setTimeout(resolve, 600));
    return { ...window.MockService.buildMockPrescription(formData), source: "mock" };
  }

  const response = await fetchWithTimeout(
    `${window.APP_CONFIG.API_BASE}/generate_prescription`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

function queuePosePayload(frame) {
  if (!state.currentAction?.id || !state.autoPoseEnabled) return;

  const now = Date.now();
  if (now - state.lastPoseSentAt < window.APP_CONFIG.POSE_SEND_INTERVAL_MS) {
    state.pendingPosePayload = {
      action_id: state.currentAction.id,
      keypoints: frame.keypoints,
      visibility: frame.visibility,
      timestamp: now,
    };
    return;
  }

  state.pendingPosePayload = {
    action_id: state.currentAction.id,
    keypoints: frame.keypoints,
    visibility: frame.visibility,
    timestamp: now,
  };
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

function startTraining(action) {
  if (!window.APP_CONFIG.isPoseSupported(action.id)) {
    showToast("该动作暂不支持实时纠正，请选择支持的动作进行跟练。");
    return;
  }
  state.currentAction = action;
  els.trainingActionName.textContent = `${action.name} · ${action.sets} 组 × ${action.reps} 次`;
  els.feedbackOverlay.textContent = "等待检测…";
  els.scoreBadge.textContent = "-- 分";
  els.feedbackList.innerHTML = "";
  els.statusText.textContent = "未开始";
  els.statusDot.className = "status-dot";
  els.videoShell.classList.remove("status-ok", "status-warning", "status-error");
  goToStep("training");
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    showToast("当前浏览器不支持摄像头");
    return;
  }

  try {
    setLoading(true, "正在启动摄像头与姿态模型…");
    stopCamera();

    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    state.cameraStream = stream;
    els.video.srcObject = stream;
    await els.video.play();
    els.videoShell.classList.add("camera-active");

    if (!state.poseTracker) {
      state.poseTracker = new PoseTracker({
        video: els.video,
        canvas: els.overlay,
        onFrame: queuePosePayload,
      });
      await state.poseTracker.init();
    }

    state.autoPoseEnabled = true;
    state.poseTracker.start();
    els.statusText.textContent = "实时检测中";
    showToast("摄像头与 MediaPipe 已启动，正在实时分析动作");
  } catch (error) {
    showToast(error?.message?.includes("MediaPipe")
      ? "姿态模型加载失败，请检查网络后重试"
      : "无法访问摄像头，请检查浏览器权限");
  } finally {
    setLoading(false);
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
}

async function simulatePoseDetection() {
  if (!state.currentAction?.id) {
    showToast("请先选择要跟练的动作");
    return;
  }

  const demo = window.MockService.generateDemoKeypoints(state.currentAction.id);
  try {
    const result = await correctPose({
      action_id: state.currentAction.id,
      keypoints: demo.keypoints,
      visibility: demo.visibility,
      timestamp: Date.now(),
    });
    updatePoseFeedback(result);
  } catch (error) {
    updatePoseFeedback({
      feedback: ["模拟检测失败，请确认后端服务可用"],
      score: 0,
      status: "error",
    });
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
  els.loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const loginData = readLoginData();
    if (!validateLoginForm(loginData)) return;
    state.currentUser = loginData;
    persistCurrentUser();
    updateUserIdentity();
    showToast(`欢迎你，${loginData.name}`);
    goToStep("intake");
  });

  els.mobilityScore.addEventListener("input", (event) => {
    els.mobilityValue.textContent = event.target.value;
  });

  els.intakeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = readFormData();
    if (!validateForm(formData)) return;

    const submitButton = document.getElementById("submit-prescription");
    submitButton.disabled = true;
    submitButton.textContent = "生成中…";
    setLoading(
      true,
      window.APP_CONFIG.DEMO_MODE
        ? "正在生成本地 Mock 处方…"
        : "正在调用豆包生成个性化处方，请稍候…"
    );

    try {
      const prescription = await requestPrescription(formData);
      if (!prescription) {
        return;
      }
      state.prescription = prescription;
      renderPrescription(prescription);
      goToStep("prescription");
      showToast(
        prescription.source === "api"
          ? "处方已由后端豆包服务生成"
          : "已使用本地 Mock 处方"
      );
    } catch (error) {
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
      setLoading(false);
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
  document.getElementById("simulate-pose").addEventListener("click", simulatePoseDetection);
  document.getElementById("test-doubao").addEventListener("click", testDoubaoConnection);
  document.getElementById("clear-doubao-result").addEventListener("click", hideDoubaoResult);
  document.getElementById("toggle-demo").addEventListener("click", () => {
    window.APP_CONFIG.setDemoMode(!window.APP_CONFIG.DEMO_MODE);
    location.reload();
  });
  document.getElementById("stop-training").addEventListener("click", () => {
    stopCamera();
    goToStep("prescription");
  });
  els.loginButton.addEventListener("click", () => submitAuth("login"));
  els.registerButton.addEventListener("click", () => submitAuth("register"));
  els.logoutButton.addEventListener("click", () => {
    saveAuth(null);
    els.prescriptionHistory.textContent = "请先登录后查看历史处方。";
    showToast("已退出登录");
  });

  els.stepButtons().forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) return;
      const step = button.dataset.step;
      if (step !== "login" && !state.currentUser) return;
      if (step === "training" && !state.currentAction) return;
      if (step === "prescription" && !state.prescription) return;
      goToStep(step);
    });
  });
}

function initDemoHint() {
  els.demoHint.textContent = window.APP_CONFIG.DEMO_MODE
    ? "Demo 模式：处方与纠正使用本地 Mock。点击「切换 API 模式」连接豆包后端。"
    : "API 模式：处方走豆包，纠正走后端算法。需要后端运行在 localhost:8000。";
}

function init() {
  state.currentUser = loadPersistedUser();
  initPainRegions();
  bindEvents();
  initDemoHint();
  updateModeBadge();
  updateUserIdentity();
  if (state.currentUser) {
    els.loginName.value = state.currentUser.name;
    els.loginAge.value = state.currentUser.age;
    goToStep("intake");
  } else {
    goToStep("login");
  }
}

init();
