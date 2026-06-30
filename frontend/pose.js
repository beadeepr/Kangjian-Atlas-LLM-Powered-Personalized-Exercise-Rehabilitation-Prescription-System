// =========================================================================
// MediaPipe PoseLandmarker (browser-side pose estimation — Plan A)
// 本地化文件，无需境外 CDN
// =========================================================================
import { PoseLandmarker, FilesetResolver } from "./mediapipe/vision_bundle.mjs";

const MP_WASM_BASE = "./mediapipe/";
const MP_MODEL_URL = "./models/pose_landmarker_lite.task";

let _mpVision = null;
let _mpPoseLandmarker = null;

async function _ensureMediaPipe() {
  if (_mpPoseLandmarker) return _mpPoseLandmarker;
  if (!_mpVision) {
    _mpVision = await FilesetResolver.forVisionTasks(MP_WASM_BASE);
  }
  _mpPoseLandmarker = await PoseLandmarker.createFromOptions(_mpVision, {
    baseOptions: {
      modelAssetPath: MP_MODEL_URL,
      delegate: "GPU",
    },
    runningMode: "VIDEO",
    numPoses: 1,
    minPoseDetectionConfidence: 0.5,
    minPosePresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });
  return _mpPoseLandmarker;
}

// COCO-17 keypoint connections (suitable for backend 17-point model)
const POSE_CONNECTIONS = [
  [0, 1], [0, 2], [1, 3], [2, 4], // head
  [0, 5], [0, 6], [5, 7], [7, 9], [6, 8], [8, 10], // shoulders->arms
  [5, 6], [11, 12], [5, 11], [6, 12], // torso
  [11, 13], [13, 15], [12, 14], [14, 16], // legs
];

const COCO17_TO_MP33 = {
  0: 0,
  1: 2,
  2: 5,
  3: 7,
  4: 8,
  5: 11,
  6: 12,
  7: 13,
  8: 14,
  9: 15,
  10: 16,
  11: 23,
  12: 24,
  13: 25,
  14: 26,
  15: 27,
  16: 28,
};

function normalizeToCoco17(rawKeypoints, rawVisibility) {
  if (!rawKeypoints?.length) return null;
  const toPoint = (kp) => ({
    x: kp[0] ?? kp.x ?? 0,
    y: kp[1] ?? kp.y ?? 0,
    z: kp[2] ?? kp.z ?? 0,
  });
  const toScore = (kp, index) => {
    if (Array.isArray(rawVisibility) && rawVisibility[index] != null) {
      return Number(rawVisibility[index]);
    }
    if (Array.isArray(kp) && kp[3] != null) return Number(kp[3]);
    return 1;
  };

  if (rawKeypoints.length === 17) {
    return {
      keypoints: rawKeypoints.map(toPoint),
      visibility: rawKeypoints.map((kp, index) => toScore(kp, index)),
    };
  }

  if (rawKeypoints.length >= 33) {
    const keypoints = [];
    const visibility = [];
    for (let coco = 0; coco < 17; coco += 1) {
      const mp = COCO17_TO_MP33[coco];
      const kp = rawKeypoints[mp] ?? [0, 0, 0];
      keypoints.push(toPoint(kp));
      visibility.push(toScore(kp, mp));
    }
    return { keypoints, visibility };
  }

  return null;
}

export class PoseTracker {
  constructor({ video, canvas, onFrame, onPoseResult, getActionId, getAuthHeaders }) {
    this.video = video;
    this.canvas = canvas;
    this.onFrame = onFrame;
    this.onPoseResult = onPoseResult;
    this.getActionId = getActionId;
    this.getAuthHeaders = getAuthHeaders;
    this.landmarker = null;
    this.running = false;
    this.lastVideoTime = -1;
    this.ctx = canvas.getContext("2d");
    this.lastValidKeypoints = null;
    this.lastValidVisibility = null;
    this.lastValidVelocities = null;
    this.lastValidTimestamp = 0;
    this.lastArOverlay = null;
    this.currentCanvasSize = { width: 0, height: 0 };
    this.currentOffscreenSize = { width: 0, height: 0 };
    this._cachedScaleX = 1;
    this._cachedScaleXTs = 0;
    this.displayKeypoints = null;
    this.displayVisibility = null;
    this._animRequest = null;
    this._animStartTs = 0;
    this._animDuration = 120;
    this._renderRequest = null;
    this._lastRenderTs = 0;
    this._smoothing = 28;
    this._predictionTime = 0.08;
    this._maxPredictionTime = 0.16;

    // ---------- 自适应 EMA 抗抖动 ----------
    // 原始 33 点平滑状态（对 MediaPipe 输出做低通滤波）
    this._smooth33Raw = null;
    this._smoothAlphaMin = 0.10;       // 静止时极强平滑
    this._smoothAlphaMax = 0.60;       // 快速运动时灵敏跟踪
    this._smoothSpeedThreshold = 0.015; // 归一化坐标的速度阈值
  }

  _startRenderLoop() {
    if (this._renderRequest) return;
    this._lastRenderTs = performance.now();
    const step = () => {
      const dt = Math.max(0, performance.now() - this._lastRenderTs);
      this._lastRenderTs = performance.now();

      if (!this.lastValidKeypoints) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this._renderRequest = requestAnimationFrame(step);
        return;
      }

      if (!this.displayKeypoints) {
        this.displayKeypoints = this.lastValidKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
        this.displayVisibility = this.lastValidVisibility
          ? this.lastValidVisibility.slice()
          : this.displayKeypoints.map(() => 1);
      } else {
        const predictAhead = Math.min(this._maxPredictionTime, Math.max(this._predictionTime, dt / 1000));
        const predicted = this._predictKeypoints(predictAhead) || this.lastValidKeypoints;
        const baseAlpha = 1 - Math.exp(-this._smoothing * (dt / 1000));
        for (let i = 0; i < 17; i++) {
          const target = predicted[i] || this.lastValidKeypoints[i] || this.displayKeypoints[i];
          const cur = this.displayKeypoints[i];
          const dx = target.x - cur.x;
          const dy = target.y - cur.y;
          const distance = Math.sqrt(dx * dx + dy * dy);
          let alpha = baseAlpha + Math.min(0.28, distance * 3);
          if (distance > 0.12) alpha = Math.max(alpha, 0.9);
          alpha = Math.min(alpha, 1);
          cur.x += dx * alpha;
          cur.y += dy * alpha;
          cur.z += (target.z - cur.z) * alpha;
          const sv = this.displayVisibility?.[i] ?? 1;
          const ev = this.lastValidVisibility?.[i] ?? 1;
          if (!this.displayVisibility) this.displayVisibility = [];
          this.displayVisibility[i] = sv + (ev - sv) * alpha;
        }
      }

      this._drawFrame();
      this._renderRequest = requestAnimationFrame(step);
    };
    this._renderRequest = requestAnimationFrame(step);
  }

  _stopRenderLoop() {
    if (this._renderRequest) cancelAnimationFrame(this._renderRequest);
    this._renderRequest = null;
  }

  _getVideoScaleX() {
    try {
      const now = Date.now();
      if (this._cachedScaleXTs && now - this._cachedScaleXTs < 1000) return this._cachedScaleX;
      const cs = window.getComputedStyle(this.video);
      const tf = cs?.transform || cs?.webkitTransform;
      let sx = 1;
      if (tf && tf !== "none") {
        if (tf.startsWith("matrix3d(")) {
          const vals = tf.slice(9, -1).split(",").map((v) => Number(v.trim()));
          sx = vals[0] || 1;
        } else if (tf.startsWith("matrix(")) {
          const vals = tf.slice(7, -1).split(",").map((v) => Number(v.trim()));
          sx = vals[0] || 1;
        }
      }
      this._cachedScaleX = sx;
      this._cachedScaleXTs = now;
      return sx;
    } catch (e) {
      return 1;
    }
  }

  _predictKeypoints(secondsAhead) {
    if (!this.lastValidKeypoints) return null;
    const time = Math.min(this._maxPredictionTime, secondsAhead);
    if (!this.lastValidVelocities) {
      return this.lastValidKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
    }
    return this.lastValidKeypoints.map((kp, index) => {
      const vel = this.lastValidVelocities[index] || { x: 0, y: 0, z: 0 };
      return {
        x: kp.x + vel.x * time,
        y: kp.y + vel.y * time,
        z: kp.z + vel.z * time,
      };
    });
  }

  _estimateVelocities(newKeypoints, oldKeypoints, dtSeconds) {
    if (
      !Array.isArray(newKeypoints) ||
      !Array.isArray(oldKeypoints) ||
      newKeypoints.length !== 17 ||
      oldKeypoints.length !== 17 ||
      dtSeconds <= 0
    ) {
      return null;
    }
    return newKeypoints.map((kp, index) => {
      const old = oldKeypoints[index] || { x: kp.x, y: kp.y, z: kp.z };
      let vx = (kp.x - old.x) / dtSeconds;
      let vy = (kp.y - old.y) / dtSeconds;
      let vz = (kp.z - old.z) / dtSeconds;
      const speed = Math.sqrt(vx * vx + vy * vy);
      const maxSpeed = 3.5;
      if (speed > maxSpeed) {
        const scale = maxSpeed / speed;
        vx *= scale;
        vy *= scale;
        vz *= scale;
      }
      return { x: vx, y: vy, z: vz };
    });
  }

  async init() {
    this.backendMode = true;
    this.offscreen = document.createElement("canvas");
    // 预加载 MediaPipe（后台异步，不阻塞页面渲染）
    this._mpReady = _ensureMediaPipe().catch((err) => {
      console.warn("MediaPipe 初始化失败，将回退到服务端 ONNX 推理:", err);
      this._mpError = err;
    });
  }

  resizeCanvas() {
    const width = this.video.videoWidth || 640;
    const height = this.video.videoHeight || 480;
    if (this.currentCanvasSize.width === width && this.currentCanvasSize.height === height) {
      return;
    }
    this.canvas.width = width;
    this.canvas.height = height;
    this.currentCanvasSize.width = width;
    this.currentCanvasSize.height = height;
  }

  _overlayScale(overlay) {
    const viewport = overlay?.viewport || {};
    const vpW = viewport.width || this.canvas.width || 1;
    const vpH = viewport.height || this.canvas.height || 1;
    return {
      sx: this.canvas.width / vpW,
      sy: this.canvas.height / vpH,
    };
  }

  drawArOverlay(overlay) {
    if (!overlay?.items?.length) return false;
    const { sx, sy } = this._overlayScale(overlay);

    overlay.items.forEach((item) => {
      if (item.type === "bone_line") {
        this.ctx.save();
        this.ctx.globalAlpha = item.opacity ?? 0.72;
        this.ctx.strokeStyle = item.color || "#22c55e";
        this.ctx.lineWidth = item.width || 5;
        this.ctx.lineCap = "round";
        this.ctx.beginPath();
        this.ctx.moveTo(item.x1 * sx, item.y1 * sy);
        this.ctx.lineTo(item.x2 * sx, item.y2 * sy);
        this.ctx.stroke();
        this.ctx.restore();
        return;
      }
      if (item.type === "joint_marker") {
        this.ctx.save();
        this.ctx.globalAlpha = item.opacity ?? 0.88;
        this.ctx.fillStyle = item.color || "#38bdf8";
        this.ctx.beginPath();
        this.ctx.arc(item.x * sx, item.y * sy, item.radius || 10, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.restore();
        return;
      }
      if (item.type === "coach_text" && item.text) {
        this.ctx.save();
        const x = item.x * sx;
        const y = item.y * sy;
        const padding = 10;
        this.ctx.font = "600 15px system-ui, sans-serif";
        const metrics = this.ctx.measureText(item.text);
        const boxW = metrics.width + padding * 2;
        const boxH = 28;
        const boxX = x - boxW / 2;
        const boxY = y;
        this.ctx.fillStyle = item.background || "rgba(15, 23, 42, 0.72)";
        if (typeof this.ctx.roundRect === "function") {
          this.ctx.beginPath();
          this.ctx.roundRect(boxX, boxY, boxW, boxH, 8);
          this.ctx.fill();
        } else {
          this.ctx.fillRect(boxX, boxY, boxW, boxH);
        }
        this.ctx.fillStyle = item.color || "#f8fafc";
        this.ctx.textAlign = "center";
        this.ctx.textBaseline = "middle";
        this.ctx.fillText(item.text, x, boxY + boxH / 2);
        this.ctx.restore();
      }
    });
    return true;
  }

  drawSkeleton(landmarks, visibilities) {
    const { width, height } = this.canvas;
    this.ctx.clearRect(0, 0, width, height);
    const videoScaleX = this._getVideoScaleX();
    const mirrored = videoScaleX < 0;

    POSE_CONNECTIONS.forEach(([start, end]) => {
      const p1 = landmarks[start];
      const p2 = landmarks[end];
      const v1 = visibilities?.[start] ?? 1;
      const v2 = visibilities?.[end] ?? 1;
      if (!p1 || !p2 || v1 < 0.5 || v2 < 0.5) return;

      const x1 = (mirrored ? 1 - p1.x : p1.x) * width;
      const y1 = p1.y * height;
      const x2 = (mirrored ? 1 - p2.x : p2.x) * width;
      const y2 = p2.y * height;

      this.ctx.beginPath();
      this.ctx.moveTo(x1, y1);
      this.ctx.lineTo(x2, y2);
      this.ctx.strokeStyle = "rgba(52, 168, 83, 0.9)";
      this.ctx.lineWidth = 3;
      this.ctx.stroke();
    });

    landmarks.forEach((point, index) => {
      const visibility = visibilities?.[index] ?? 1;
      const x = (mirrored ? 1 - point.x : point.x) * width;
      const y = point.y * height;
      this.ctx.beginPath();
      this.ctx.arc(x, y, visibility < 0.5 ? 3 : 5, 0, Math.PI * 2);
      this.ctx.fillStyle =
        visibility < 0.5 ? "rgba(150, 150, 150, 0.8)" : "rgba(26, 115, 232, 0.95)";
      this.ctx.fill();
    });
  }

  _drawFrame() {
    if (this.lastArOverlay && this.drawArOverlay(this.lastArOverlay)) {
      return;
    }
    if (this.displayKeypoints && this.displayVisibility) {
      this.drawSkeleton(this.displayKeypoints, this.displayVisibility);
    }
  }

  /** 对 33 点关键点做自适应 EMA 低通滤波，消除静止时的微小抖动。
   *
   *  自适应 alpha：静止时 alpha → _smoothAlphaMin（强平滑），
   *  快速运动时 alpha → _smoothAlphaMax（灵敏跟踪）。
   */
  _smoothKeypoints33(rawKeypoints33) {
    if (!this._smooth33Raw || this._smooth33Raw.length !== 33) {
      this._smooth33Raw = rawKeypoints33.map((p) => ({
        x: p[0] ?? p.x ?? 0,
        y: p[1] ?? p.y ?? 0,
        z: p[2] ?? p.z ?? 0,
      }));
      return this._smooth33Raw.map((p) => [p.x, p.y, p.z]);
    }

    // 计算关键点集合的最大位移，用于自适应 alpha
    let maxDist = 0;
    for (let i = 0; i < 33; i++) {
      const kp = rawKeypoints33[i] || [0, 0, 0];
      const rx = kp[0] ?? kp.x ?? 0;
      const ry = kp[1] ?? kp.y ?? 0;
      const dx = rx - this._smooth33Raw[i].x;
      const dy = ry - this._smooth33Raw[i].y;
      const d = Math.sqrt(dx * dx + dy * dy);
      if (d > maxDist) maxDist = d;
    }

    const alpha =
      this._smoothAlphaMin +
      (this._smoothAlphaMax - this._smoothAlphaMin) *
        Math.min(1, maxDist / this._smoothSpeedThreshold);

    const result = [];
    for (let i = 0; i < 33; i++) {
      const kp = rawKeypoints33[i] || [0, 0, 0];
      const rx = kp[0] ?? kp.x ?? 0;
      const ry = kp[1] ?? kp.y ?? 0;
      const rz = kp[2] ?? kp.z ?? 0;
      this._smooth33Raw[i].x += alpha * (rx - this._smooth33Raw[i].x);
      this._smooth33Raw[i].y += alpha * (ry - this._smooth33Raw[i].y);
      this._smooth33Raw[i].z += alpha * (rz - this._smooth33Raw[i].z);
      result.push([this._smooth33Raw[i].x, this._smooth33Raw[i].y, this._smooth33Raw[i].z]);
    }
    return result;
  }

  _applyKeypoints(rawKeypoints, rawVisibility) {
    const normalized = normalizeToCoco17(rawKeypoints, rawVisibility);
    if (!normalized) return false;
    const { keypoints, visibility } = normalized;
    if (keypoints.length !== 17 || visibility.length !== 17) return false;

    const nowTs = performance.now() / 1000;
    if (this.lastValidKeypoints && this.lastValidTimestamp) {
      const dt = Math.max(0.001, nowTs - this.lastValidTimestamp);
      const velocities = this._estimateVelocities(keypoints, this.lastValidKeypoints, dt);
      if (velocities) this.lastValidVelocities = velocities;
    }
    this.lastValidTimestamp = nowTs;
    this.lastValidKeypoints = keypoints;
    this.lastValidVisibility = visibility;
    if (!this.displayKeypoints) {
      this.displayKeypoints = keypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
      this.displayVisibility = visibility.slice();
    }
    return true;
  }

  _canUseInferFrame() {
    const actionId = this.getActionId?.();
    const headers = this.getAuthHeaders?.() || {};
    return Boolean(actionId && headers.Authorization);
  }

  async _postInferFrame(dataUrl, offWidth, offHeight, mirrored) {
    const apiBase = window.APP_CONFIG?.API_BASE || "";
    const headers = {
      "Content-Type": "application/json",
      ...(this.getAuthHeaders?.() || {}),
    };
    const response = await fetch(`${apiBase}/pose/infer_frame`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        action_id: this.getActionId(),
        image_base64: dataUrl,
        viewport_width: offWidth,
        viewport_height: offHeight,
        mirror: mirrored,
      }),
    });
    if (!response.ok) return null;
    return response.json();
  }

  async _postInferPose(dataUrl) {
    const apiBase = window.APP_CONFIG?.API_BASE || "";
    const response = await fetch(`${apiBase}/infer_pose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_base64: dataUrl }),
    });
    if (!response.ok) return null;
    return response.json();
  }

  async _postInferFrameKeypoints(keypoints, visibility) {
    const apiBase = window.APP_CONFIG?.API_BASE || "";
    const headers = {
      "Content-Type": "application/json",
      ...(this.getAuthHeaders?.() || {}),
    };
    const response = await fetch(`${apiBase}/pose/infer_frame`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        action_id: this.getActionId(),
        keypoints: keypoints,
        visibility: visibility,
      }),
    });
    if (!response.ok) return null;
    return response.json();
  }

  _emitPoseResult(json, rawKeypoints, rawVisibility) {
    if (this.onPoseResult) {
      this.onPoseResult({
        keypoints: rawKeypoints,
        visibility: rawVisibility,
        feedback: json.feedback,
        score: json.score,
        status: json.status,
        voice_cue: json.voice_cue,
        ar_overlay: json.ar_overlay,
        skeleton_3d: json.skeleton_3d,
      });
      return;
    }
    this.onFrame?.({ keypoints: rawKeypoints, visibility: rawVisibility });
  }

  start() {
    this.running = true;
    this._startRenderLoop();
    if (!this.backendMode) return;

    // 等待 MediaPipe 就绪后启动前端姿态估计
    this._startMediaPipeLoop();
  }

  async _startMediaPipeLoop() {
    try {
      await this._mpReady;
    } catch (err) {
      // MediaPipe 不可用，回退到旧的 Base64 → 服务端 ONNX 路径
      console.warn("MediaPipe 不可用，使用服务端 ONNX 回退方案");
      this._startServerOnnxLoop();
      return;
    }

    const sendIntervalMs = (window.APP_CONFIG && window.APP_CONFIG.POSE_SEND_INTERVAL_MS) || 100;
    let lastSendTs = 0;
    let lastVideoTime = -1;

    const detectLoop = () => {
      if (!this.running) return;

      try {
        if (this.video.readyState >= 2) {
          // 仅在视频帧时间戳变化时才执行检测（避免重复处理同一帧）
          const videoTime = this.video.currentTime;
          if (videoTime !== lastVideoTime) {
            lastVideoTime = videoTime;
            this.resizeCanvas();

            // ---------- 前端 MediaPipe 姿态估计 ----------
            // 使用 performance.now() 作为时间戳（MediaPipe 官方推荐）
            const nowMs = performance.now();
            const result = _mpPoseLandmarker.detectForVideo(this.video, nowMs);
            const landmarks = result?.landmarks?.[0];

            if (landmarks && landmarks.length >= 33) {
              // MediaPipe 返回 33 个归一化关键点 [x, y, z, visibility]
              const keypoints = [];
              const visibility = [];
              for (let i = 0; i < 33; i++) {
                const lm = landmarks[i];
                keypoints.push([lm.x, lm.y, lm.z ?? 0]);
                visibility.push(lm.visibility ?? 1);
              }

              // ---------- 自适应 EMA 抗抖动 ----------
              const smoothed33 = this._smoothKeypoints33(keypoints);

              // 本地渲染骨架（使用平滑后的关键点）
              this._applyKeypoints(smoothed33, visibility);

              // ---------- 发送关键点到后端获取反馈/评分 ----------
              if (nowMs - lastSendTs >= sendIntervalMs) {
                lastSendTs = nowMs;
                this._sendKeypointsToBackend(smoothed33, visibility, nowMs);
              }
            } else {
              // 无人检测到时重置平滑状态，避免下次出现时漂移
              this._smooth33Raw = null;
            }
          }
        }
      } catch (err) {
        // MediaPipe 运行时出错不中断循环
        console.warn("MediaPipe detect 出错:", err);
      }

      // requestAnimationFrame 比 requestVideoFrameCallback 更稳定
      // rVFC 在某些浏览器/场景下可能不触发（如 video 被遮挡或暂停）
      requestAnimationFrame(detectLoop);
    };

    detectLoop();
  }

  async _sendKeypointsToBackend(keypoints, visibility, now) {
    try {
      const json = await this._postInferFrameKeypoints(keypoints, visibility);
      if (json) {
        // 摄像头画面仅显示骨架，不绘制 AR 文字叠层
        this.lastArOverlay = null;
        // 更新反馈/评分（骨架已在 MediaPipe 回调中渲染）
        if (this.onPoseResult) {
          this.onPoseResult({
            keypoints,
            visibility,
            feedback: json.feedback,
            score: json.score,
            status: json.status,
            voice_cue: json.voice_cue,
            ar_overlay: json.ar_overlay,
            skeleton_3d: json.skeleton_3d,
          });
        }
      }
    } catch (err) {
      // 后端请求失败不影响本地渲染
    }
  }

  /** 旧版回退：Base64 图片 → 服务端 ONNX 推理 */
  _startServerOnnxLoop() {
    const sendInterval = (window.APP_CONFIG && window.APP_CONFIG.POSE_SEND_INTERVAL_MS) || 100;
    const loopBackend = async () => {
      if (!this.running) return;
      try {
        if (this.video.readyState >= 2) {
          this.resizeCanvas();
          const offWidth = this.video.videoWidth || 640;
          const offHeight = this.video.videoHeight || 480;
          if (
            this.currentOffscreenSize.width !== offWidth ||
            this.currentOffscreenSize.height !== offHeight
          ) {
            this.offscreen.width = offWidth;
            this.offscreen.height = offHeight;
            this.currentOffscreenSize.width = offWidth;
            this.currentOffscreenSize.height = offHeight;
          }
          const offCtx = this.offscreen.getContext("2d");
          offCtx.drawImage(this.video, 0, 0, this.offscreen.width, this.offscreen.height);
          const dataUrl = this.offscreen.toDataURL("image/jpeg", 0.7);
          const mirrored = this._getVideoScaleX() < 0;

          try {
            let json = null;
            if (this._canUseInferFrame()) {
              json = await this._postInferFrame(dataUrl, offWidth, offHeight, mirrored);
            }
            if (!json) {
              json = await this._postInferPose(dataUrl);
              if (json) this.lastArOverlay = null;
            } else {
              this.lastArOverlay = null;
            }

            if (json) {
              const normalized = normalizeToCoco17(json.keypoints, json.visibility);
              const keypoints = normalized?.keypoints;
              const visibility = normalized?.visibility;
              const hasFeedback = Array.isArray(json.feedback) && json.feedback.length > 0;

              if (keypoints && this._applyKeypoints(keypoints, visibility)) {
                this._emitPoseResult(json, keypoints, visibility);
              } else if (hasFeedback) {
                this._emitPoseResult(
                  json,
                  keypoints || json.keypoints,
                  visibility || json.visibility
                );
              } else if (this.displayKeypoints && this.displayVisibility) {
                this._drawFrame();
              } else if (this.lastValidKeypoints && this.lastValidVisibility) {
                this.displayKeypoints = this.lastValidKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
                this.displayVisibility = this.lastValidVisibility.slice();
                this._drawFrame();
              }
            }
          } catch (err) {
            if (this.displayKeypoints && this.displayVisibility) {
              this._drawFrame();
            }
          }
        }
      } finally {
        setTimeout(loopBackend, sendInterval);
      }
    };
    loopBackend();
  }

  stop() {
    this.running = false;
    this._stopRenderLoop();
    if (this._animRequest) cancelAnimationFrame(this._animRequest);
    this.lastArOverlay = null;
    this.ctx?.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }
}
