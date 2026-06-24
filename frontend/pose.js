// COCO-17 keypoint connections (suitable for backend 17-point model)
const POSE_CONNECTIONS = [
  [0, 1], [0, 2], [1, 3], [2, 4], // head
  [0, 5], [0, 6], [5, 7], [7, 9], [6, 8], [8, 10], // shoulders->arms
  [5, 6], [11, 12], [5, 11], [6, 12], // torso
  [11, 13], [13, 15], [12, 14], [14, 16], // legs
];

export class PoseTracker {
  constructor({ video, canvas, onFrame }) {
    this.video = video;
    this.canvas = canvas;
    this.onFrame = onFrame;
    this.landmarker = null;
    this.running = false;
    this.lastVideoTime = -1;
    this.ctx = canvas.getContext("2d");
    this.lastValidKeypoints = null;
    this.lastValidVisibility = null;
    this.lastValidVelocities = null;
    this.lastValidTimestamp = 0;
    this.currentCanvasSize = { width: 0, height: 0 };
    this.currentOffscreenSize = { width: 0, height: 0 };
    this._cachedScaleX = 1;
    this._cachedScaleXTs = 0;
    this.displayKeypoints = null; // currently rendered keypoints (for animation)
    this.displayVisibility = null;
    this._animRequest = null;
    this._animStartTs = 0;
    this._animDuration = 120; // ms
    this._renderRequest = null;
    this._lastRenderTs = 0;
    this._smoothing = 28; // smoothing rate (per second) for follow
    this._predictionTime = 0.08; // seconds ahead for prediction compensation
    this._maxPredictionTime = 0.16;
  }

  _startRenderLoop() {
    if (this._renderRequest) return;
    this._lastRenderTs = performance.now();
    const step = (ts) => {
      const dt = Math.max(0, ts - this._lastRenderTs);
      this._lastRenderTs = ts;

      if (!this.lastValidKeypoints) {
        // nothing to show
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this._renderRequest = requestAnimationFrame(step);
        return;
      }

      if (!this.displayKeypoints) {
        this.displayKeypoints = this.lastValidKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
        this.displayVisibility = this.lastValidVisibility ? this.lastValidVisibility.slice() : this.displayKeypoints.map(()=>1);
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
          const nv = sv + (ev - sv) * alpha;
          if (!this.displayVisibility) this.displayVisibility = [];
          this.displayVisibility[i] = nv;
        }
      }

      this.drawSkeleton(this.displayKeypoints, this.displayVisibility);
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
    if (!this.lastValidKeypoints) {
      return null;
    }
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
    if (!Array.isArray(newKeypoints) || !Array.isArray(oldKeypoints) || newKeypoints.length !== 17 || oldKeypoints.length !== 17 || dtSeconds <= 0) {
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
    // Use backend by default: prepare offscreen canvas for capture
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

  // Animate displayKeypoints -> targetKeypoints over _animDuration ms
  _animateTo(targetKeypoints, targetVisibility) {
    if (!Array.isArray(targetKeypoints) || targetKeypoints.length !== 17) return;
    if (!this.displayKeypoints) {
      // first-time: jump to target
      this.displayKeypoints = targetKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
      this.displayVisibility = targetVisibility.slice();
      this.drawSkeleton(this.displayKeypoints, this.displayVisibility);
      return;
    }

    const startKeypoints = this.displayKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
    const startVis = this.displayVisibility ? this.displayVisibility.slice() : startKeypoints.map(() => 1);
    const dur = this._animDuration;
    const startTs = performance.now();
    if (this._animRequest) cancelAnimationFrame(this._animRequest);

    const step = (ts) => {
      const t = Math.min(1, (ts - startTs) / dur);
      const interpolated = [];
      const interpVis = [];
      for (let i = 0; i < 17; i++) {
        const s = startKeypoints[i] || { x: 0.5, y: 0.5, z: 0 };
        const e = targetKeypoints[i] || { x: s.x, y: s.y, z: s.z };
        interpolated.push({ x: s.x + (e.x - s.x) * t, y: s.y + (e.y - s.y) * t, z: s.z + (e.z - s.z) * t });
        const sv = startVis[i] ?? 1;
        const ev = targetVisibility[i] ?? 1;
        interpVis.push(sv + (ev - sv) * t);
      }

      this.displayKeypoints = interpolated;
      this.displayVisibility = interpVis;
      this.drawSkeleton(this.displayKeypoints, this.displayVisibility);

      if (t < 1) {
        this._animRequest = requestAnimationFrame(step);
      } else {
        this._animRequest = null;
        this.displayKeypoints = targetKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
        this.displayVisibility = targetVisibility.slice();
      }
    };

    this._animRequest = requestAnimationFrame(step);
  }

  start() {
    this.running = true;
    this._startRenderLoop();
    if (this.backendMode) {
      // Backend loop: capture frames and POST to /infer_pose
      const sendInterval = (window.APP_CONFIG && window.APP_CONFIG.POSE_SEND_INTERVAL_MS) || 100;
      const loopBackend = async () => {
        if (!this.running) return;
        try {
          if (this.video.readyState >= 2) {
            this.resizeCanvas();
            // draw video to offscreen canvas
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
            // call backend
            try {
              const res = await fetch(`${window.APP_CONFIG.API_BASE}/infer_pose`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image_base64: dataUrl }),
              });
              if (res.ok) {
                const json = await res.json();
                const keypoints = (json.keypoints || []).map((kp) => ({ x: kp[0], y: kp[1], z: kp[2] || 0 }));
                const visibility = json.visibility || keypoints.map(() => 1);
                if (keypoints.length === 17 && visibility.length === 17) {
                  const nowTs = performance.now() / 1000;
                  if (this.lastValidKeypoints && this.lastValidTimestamp) {
                    const dt = Math.max(0.001, nowTs - this.lastValidTimestamp);
                    const velocities = this._estimateVelocities(keypoints, this.lastValidKeypoints, dt);
                    if (velocities) {
                      this.lastValidVelocities = velocities;
                    }
                  }
                  this.lastValidTimestamp = performance.now() / 1000;
                  this.lastValidKeypoints = keypoints;
                  this.lastValidVisibility = visibility;
                  // ensure display initialized; render loop will smooth toward lastValid
                  if (!this.displayKeypoints) {
                    this.displayKeypoints = this.lastValidKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
                    this.displayVisibility = this.lastValidVisibility.slice();
                  }
                  this.onFrame?.({ keypoints: json.keypoints, visibility });
                } else {
                  if (json.keypoints?.length || json.visibility?.length) {
                    console.warn("infer_pose returned incomplete pose data", {
                      keypoints: json.keypoints?.length,
                      visibility: json.visibility?.length,
                    });
                  }
                  if (this.displayKeypoints && this.displayVisibility) {
                    // keep showing interpolated display
                    this.drawSkeleton(this.displayKeypoints, this.displayVisibility);
                  } else if (this.lastValidKeypoints && this.lastValidVisibility) {
                    // fallback to last valid pose instantly
                    this.displayKeypoints = this.lastValidKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
                    this.displayVisibility = this.lastValidVisibility.slice();
                    this.drawSkeleton(this.displayKeypoints, this.displayVisibility);
                  }
                }
              } else {
                if (this.displayKeypoints && this.displayVisibility) {
                  this.drawSkeleton(this.displayKeypoints, this.displayVisibility);
                } else if (this.lastValidKeypoints && this.lastValidVisibility) {
                  this.displayKeypoints = this.lastValidKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
                  this.displayVisibility = this.lastValidVisibility.slice();
                  this.drawSkeleton(this.displayKeypoints, this.displayVisibility);
                } else {
                  this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                }
              }
            } catch (err) {
              // network or parse error: keep current display if present
              if (this.displayKeypoints && this.displayVisibility) {
                this.drawSkeleton(this.displayKeypoints, this.displayVisibility);
              } else if (this.lastValidKeypoints && this.lastValidVisibility) {
                this.displayKeypoints = this.lastValidKeypoints.map((p) => ({ x: p.x, y: p.y, z: p.z }));
                this.displayVisibility = this.lastValidVisibility.slice();
                this.drawSkeleton(this.displayKeypoints, this.displayVisibility);
              }
            }
          }
        } finally {
          setTimeout(loopBackend, sendInterval);
        }
      };
      loopBackend();
      return;
    }
  }

  stop() {
    this.running = false;
    this._stopRenderLoop();
    if (this._animRequest) cancelAnimationFrame(this._animRequest);
    this.ctx?.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }
}
