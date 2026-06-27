// COCO-17 keypoint connections (suitable for backend 17-point model)
const POSE_CONNECTIONS = [
  [0, 1], [0, 2], [1, 3], [2, 4], // head
  [0, 5], [0, 6], [5, 7], [7, 9], [6, 8], [8, 10], // shoulders->arms
  [5, 6], [11, 12], [5, 11], [6, 12], // torso
  [11, 13], [13, 15], [12, 14], [14, 16], // legs
];

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

  _applyKeypoints(rawKeypoints, rawVisibility) {
    const keypoints = (rawKeypoints || []).map((kp) => ({
      x: kp[0] ?? kp.x,
      y: kp[1] ?? kp.y,
      z: kp[2] ?? kp.z ?? 0,
    }));
    const visibility = rawVisibility || keypoints.map(() => 1);
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
              this.lastArOverlay = json.ar_overlay || null;
            }

            if (json && this._applyKeypoints(json.keypoints, json.visibility)) {
              this._emitPoseResult(json, json.keypoints, json.visibility);
            } else if (this.displayKeypoints && this.displayVisibility) {
              this._drawFrame();
            } else if (this.lastValidKeypoints && this.lastValidVisibility) {
              this.displayKeypoints = this.lastValidKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
              this.displayVisibility = this.lastValidVisibility.slice();
              this._drawFrame();
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
