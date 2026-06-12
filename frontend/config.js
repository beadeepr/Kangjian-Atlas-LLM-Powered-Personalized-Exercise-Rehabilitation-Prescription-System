function readDemoMode() {
  if (window.DEMO_MODE !== undefined) {
    return Boolean(window.DEMO_MODE);
  }
  const query = new URLSearchParams(window.location.search);
  if (query.has("demo")) {
    return query.get("demo") !== "false" && query.get("demo") !== "0";
  }
  const stored = localStorage.getItem("kj_demo_mode");
  if (stored !== null) {
    return stored === "true";
  }
  return true;
}

window.APP_CONFIG = {
  API_BASE: window.API_BASE || "http://localhost:8000/api",
  DEMO_MODE: readDemoMode(),
  FETCH_TIMEOUT_MS: 2000,
  POSE_SEND_INTERVAL_MS: 100,
  assetUrl(path) {
    return new URL(path, window.location.href).href;
  },
  setDemoMode(enabled) {
    localStorage.setItem("kj_demo_mode", enabled ? "true" : "false");
    this.DEMO_MODE = enabled;
  },
};

window.ACTION_CATALOG = {
  neck_side_bend: {
    id: "neck_side_bend",
    name: "颈部侧屈拉伸",
    description: "坐姿或站姿，缓慢将头向一侧倾斜，停留20秒，重复3次",
    contraindications: "颈椎不稳、急性炎症期禁忌",
    image: "assets/neck_side_bend.svg",
    sets: 3,
    reps: 1,
  },
  wall_squat: {
    id: "wall_squat",
    name: "靠墙静蹲",
    description: "背靠墙，下蹲保持膝盖不超过脚尖，停留30秒，重复3次",
    contraindications: "急性膝关节疼痛、严重膝关节炎患者谨慎",
    image: "assets/wall_squat.svg",
    sets: 3,
    reps: 1,
  },
};

window.ACTION_NAME_TO_ID = Object.fromEntries(
  Object.values(window.ACTION_CATALOG).map((action) => [action.name, action.id])
);

window.PAIN_REGIONS = ["颈部", "肩部", "腰部", "膝关节", "踝关节"];
