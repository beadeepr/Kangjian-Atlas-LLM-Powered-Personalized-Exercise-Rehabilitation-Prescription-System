const state = {
  currentStep: "intake",
  prescription: null,
  currentAction: null,
  cameraStream: null,
  selectedPainRegions: new Set(),
  auth: readStoredAuth(),
};

const els = {
  stepButtons: () => document.querySelectorAll(".step-item"),
  pages: () => document.querySelectorAll(".page"),
  painRegions: document.getElementById("pain-regions"),
  mobilityScore: document.getElementById("mobility-score"),
  mobilityValue: document.getElementById("mobility-value"),
  intakeForm: document.getElementById("intake-form"),
  symptomsError: document.getElementById("symptoms-error"),
  prescriptionSummary: document.getElementById("prescription-summary"),
  actionList: document.getElementById("action-list"),
  prescriptionHistory: document.getElementById("prescription-history"),
  trainingActionName: document.getElementById("training-action-name"),
  videoShell: document.getElementById("video-shell"),
  video: document.getElementById("video"),
  videoPlaceholder: document.getElementById("video-placeholder"),
  feedbackOverlay: document.getElementById("feedback-overlay"),
  scoreBadge: document.getElementById("score-badge"),
  statusDot: document.getElementById("status-dot"),
  statusText: document.getElementById("status-text"),
  feedbackList: document.getElementById("feedback-list"),
  demoHint: document.getElementById("demo-hint"),
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
  }, 2600);
}

function goToStep(step) {
  state.currentStep = step;
  els.pages().forEach((page) => {
    page.classList.toggle("active", page.id === `page-${step}`);
  });
  els.stepButtons().forEach((button) => {
    const isCurrent = button.dataset.step === step;
    button.classList.toggle("active", isCurrent);
    button.disabled = step === "intake" ? button.dataset.step !== "intake" : false;
  });
  if (step === "prescription") {
    loadPrescriptionHistory();
  }
}

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timer = window.setTimeout(
    () => controller.abort(),
    window.APP_CONFIG.FETCH_TIMEOUT_MS
  );
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return response;
  } finally {
    window.clearTimeout(timer);
  }
}

function readFormData() {
  const formData = new FormData(els.intakeForm);
  return {
    name: formData.get("name")?.toString().trim() || null,
    age: formData.get("age") ? Number(formData.get("age")) : null,
    symptoms: formData.get("symptoms")?.toString().trim() || "",
    history: formData.get("history")?.toString().trim() || null,
    pain_regions: Array.from(state.selectedPainRegions),
    mobility_score: Number(formData.get("mobility_score") || 5),
  };
}

function validateForm(formData) {
  if (!formData.symptoms) {
    els.symptomsError.textContent = "请填写主诉信息";
    return false;
  }
  els.symptomsError.textContent = "";
  return true;
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
      <p>${prescription.summary}</p>
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

  els.prescriptionHistory.textContent = "正在加载…";
  if (!requireLogin()) {
    els.prescriptionHistory.textContent = "请先登录后查看历史处方。";
    return;
  }
  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/prescriptions`,
      {
        headers: authHeaders(),
      }
    );
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    if (!Array.isArray(data) || data.length === 0) {
      els.prescriptionHistory.textContent = "暂无处方记录。";
      return;
    }
    els.prescriptionHistory.innerHTML = data.map(renderHistoryCard).join("");
  } catch (error) {
    const hint =
      error?.name === "AbortError"
        ? "请求超时，请确认后端已启动（uvicorn app.main:app --port 8000）。"
        : "加载失败，请确认：① 后端已启动 ② 地址为 http://localhost:8000 ③ 已配置 CORS。";
    els.prescriptionHistory.textContent = hint;
  }
}

async function requestPrescription(formData) {
  if (window.APP_CONFIG.DEMO_MODE) {
    return window.MockService.buildMockPrescription(formData);
  }
  if (!requireLogin()) {
    return null;
  }

  try {
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
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return {
      summary: data.summary,
      actions: data.actions.map((action) => window.MockService.enrichAction(action)),
    };
  } catch (error) {
    showToast("处方服务暂不可用，已切换为本地 Mock 数据");
    return window.MockService.buildMockPrescription(formData);
  }
}

function readAuthForm() {
  return {
    account: els.authAccount.value.trim(),
    password: els.authPassword.value.trim(),
    nickname: els.authNickname.value.trim(),
    gender: els.authGender.value || null,
    age: els.authAge.value ? Number(els.authAge.value) : null,
  };
}

async function submitAuth(mode) {
  if (window.APP_CONFIG.DEMO_MODE) {
    showToast("Demo 模式无需登录");
    return;
  }
  const form = readAuthForm();
  if (!form.account || !form.password) {
    showToast("请填写账号和密码");
    return;
  }
  if (mode === "register" && !form.nickname) {
    showToast("注册时请填写昵称");
    return;
  }

  const url = `${window.APP_CONFIG.API_BASE}/${mode === "register" ? "register" : "login"}`;
  const body =
    mode === "register"
      ? form
      : { account: form.account, password: form.password };

  try {
    const response = await fetchWithTimeout(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }
    if (mode === "register") {
      showToast("注册成功，请登录");
      els.authNickname.value = data.nickname || form.nickname;
      return;
    }
    saveAuth({ token: data.token, user: data.user });
    showToast("登录成功");
    loadPrescriptionHistory();
  } catch (error) {
    showToast(error.message || "账号服务暂不可用");
  }
}

function renderPrescription(prescription) {
  els.prescriptionSummary.textContent = prescription.summary;
  els.actionList.innerHTML = "";

  prescription.actions.forEach((action) => {
    const card = document.createElement("article");
    card.className = "action-card card";
    card.innerHTML = `
      <img src="${window.APP_CONFIG.assetUrl(action.image)}" alt="${action.name}示意图" />
      <div class="action-card-body">
        <h3>${action.name}</h3>
        <div class="action-meta">
          <span class="tag">${action.sets} 组</span>
          <span class="tag">${action.reps} 次/组</span>
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
        <button class="btn btn-primary start-training" type="button" data-action-id="${action.id || ""}">
          开始跟练
        </button>
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
  if (status) {
    els.statusDot.classList.add(status);
  }

  els.videoShell.classList.remove("status-ok", "status-warning", "status-error");
  if (status) {
    els.videoShell.classList.add(`status-${status}`);
  }

  els.feedbackList.innerHTML = "";
  (feedback || []).forEach((line, index) => {
    const item = document.createElement("li");
    item.textContent = line;
    if (index === 0) {
      item.classList.add("latest");
    }
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

  try {
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/correct_pose`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return {
      feedback: data.feedback || ["暂无反馈"],
      score: data.score ?? 0,
      status: data.status || "warning",
    };
  } catch (error) {
    return {
      feedback: ["网络连接不稳定，请检查网络"],
      score: 0,
      status: "error",
    };
  }
}

function startTraining(action) {
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
    if (state.cameraStream) {
      state.cameraStream.getTracks().forEach((track) => track.stop());
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    state.cameraStream = stream;
    els.video.srcObject = stream;
    els.videoShell.classList.add("camera-active");
    els.statusText.textContent = "摄像头已开启";
    showToast("摄像头已启动，可点击模拟检测查看反馈样式");
  } catch (error) {
    showToast("无法访问摄像头，请检查浏览器权限");
  }
}

function stopCamera() {
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
  const result = await correctPose({
    action_id: state.currentAction.id,
    keypoints: demo.keypoints,
    visibility: demo.visibility,
    timestamp: Date.now(),
  });
  updatePoseFeedback(result);
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
    });
    els.painRegions.appendChild(button);
  });
}

function bindEvents() {
  els.mobilityScore.addEventListener("input", (event) => {
    els.mobilityValue.textContent = event.target.value;
  });

  els.intakeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = readFormData();
    if (!validateForm(formData)) {
      return;
    }

    const submitButton = document.getElementById("submit-prescription");
    submitButton.disabled = true;
    submitButton.textContent = "生成中…";

    try {
      const prescription = await requestPrescription(formData);
      if (!prescription) {
        return;
      }
      state.prescription = prescription;
      renderPrescription(prescription);
      goToStep("prescription");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "生成康复处方";
    }
  });

  document.getElementById("back-to-intake").addEventListener("click", () => {
    goToStep("intake");
  });

  document.getElementById("start-camera").addEventListener("click", startCamera);
  document.getElementById("simulate-pose").addEventListener("click", simulatePoseDetection);
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
      if (step === "training" && !state.currentAction) return;
      if (step === "prescription" && !state.prescription) return;
      goToStep(step);
    });
  });
}

function initDemoHint() {
  els.demoHint.textContent = window.APP_CONFIG.DEMO_MODE
    ? "当前为 Demo 模式。接后端请在 Console 执行：APP_CONFIG.setDemoMode(false); location.reload();"
    : "已连接后端 API。切回 Mock：APP_CONFIG.setDemoMode(true); location.reload();";
}

function init() {
  initPainRegions();
  bindEvents();
  initDemoHint();
  updateAuthStatus();
  goToStep("intake");
}

init();
