const POSE_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 7], [0, 4], [4, 5], [5, 6], [6, 8],
  [9, 10], [11, 12], [11, 13], [13, 15], [15, 17], [15, 19], [15, 21],
  [17, 19], [12, 14], [14, 16], [16, 18], [16, 20], [16, 22], [18, 20],
  [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [27, 29], [27, 31],
  [24, 26], [26, 28], [28, 30], [28, 32],
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
  }

  async init() {
    const vision = await import(
      "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm"
    );
    const { PoseLandmarker, FilesetResolver } = vision;
    const filesetResolver = await FilesetResolver.forVisionTasks(
      "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
    );
    this.landmarker = await PoseLandmarker.createFromOptions(filesetResolver, {
      baseOptions: {
        modelAssetPath:
          "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
        delegate: "GPU",
      },
      runningMode: "VIDEO",
      numPoses: 1,
    });
  }

  resizeCanvas() {
    const width = this.video.videoWidth || 640;
    const height = this.video.videoHeight || 480;
    this.canvas.width = width;
    this.canvas.height = height;
  }

  drawSkeleton(landmarks, visibilities) {
    const { width, height } = this.canvas;
    this.ctx.clearRect(0, 0, width, height);

    POSE_CONNECTIONS.forEach(([start, end]) => {
      const p1 = landmarks[start];
      const p2 = landmarks[end];
      const v1 = visibilities?.[start] ?? 1;
      const v2 = visibilities?.[end] ?? 1;
      if (!p1 || !p2 || v1 < 0.5 || v2 < 0.5) return;

      this.ctx.beginPath();
      this.ctx.moveTo(p1.x * width, p1.y * height);
      this.ctx.lineTo(p2.x * width, p2.y * height);
      this.ctx.strokeStyle = "rgba(52, 168, 83, 0.9)";
      this.ctx.lineWidth = 3;
      this.ctx.stroke();
    });

    landmarks.forEach((point, index) => {
      const visibility = visibilities?.[index] ?? 1;
      const x = point.x * width;
      const y = point.y * height;
      this.ctx.beginPath();
      this.ctx.arc(x, y, visibility < 0.5 ? 3 : 5, 0, Math.PI * 2);
      this.ctx.fillStyle =
        visibility < 0.5 ? "rgba(150, 150, 150, 0.8)" : "rgba(26, 115, 232, 0.95)";
      this.ctx.fill();
    });
  }

  start() {
    this.running = true;
    const loop = () => {
      if (!this.running) return;
      if (this.video.readyState >= 2 && this.landmarker) {
        if (this.video.currentTime !== this.lastVideoTime) {
          this.lastVideoTime = this.video.currentTime;
          this.resizeCanvas();
          const result = this.landmarker.detectForVideo(this.video, performance.now());
          const landmarks = result.landmarks?.[0];
          if (landmarks?.length === 33) {
            const keypoints = landmarks.map((p) => [p.x, p.y, p.z ?? 0]);
            const visibility = landmarks.map((p) => p.visibility ?? 1);
            this.drawSkeleton(landmarks, visibility);
            this.onFrame?.({ keypoints, visibility });
          } else {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
          }
        }
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  stop() {
    this.running = false;
    this.ctx?.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }
}
