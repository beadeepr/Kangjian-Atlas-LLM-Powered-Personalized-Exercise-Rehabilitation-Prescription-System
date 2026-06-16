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
  return false;
}

function readDevMode() {
  const query = new URLSearchParams(window.location.search);
  return query.get("dev") === "true" || query.get("dev") === "1";
}

window.APP_CONFIG = {
  API_BASE: window.API_BASE || "http://localhost:8000/api",
  DEMO_MODE: readDemoMode(),
  DEV_MODE: readDevMode(),
  FETCH_TIMEOUT_MS: 2000,
  AUTH_TIMEOUT_MS: 10000,
  PRESCRIPTION_TIMEOUT_MS: 45000,
  POSE_TIMEOUT_MS: 2000,
  POSE_SEND_INTERVAL_MS: 100,
  POSE_VISIBILITY_MIN: 0.5,
  SUPPORTED_POSE_ACTION_IDS: ["wall_squat", "neck_side_bend"],
  ACTION_ID_ALIASES: {
    neck_chin_tuck: "chin_tuck",
    scapular_retraction: "shoulder_roll",
  },
  CATALOG_TO_BACKEND_ACTION_ID: {
    chin_tuck: "neck_chin_tuck",
    shoulder_roll: "scapular_retraction",
  },
  assetUrl(path) {
    return new URL(path, window.location.href).href;
  },
  setDemoMode(enabled) {
    localStorage.setItem("kj_demo_mode", enabled ? "true" : "false");
    this.DEMO_MODE = enabled;
  },
  normalizeCatalogActionId(actionId) {
    if (!actionId) return null;
    return this.ACTION_ID_ALIASES[actionId] || actionId;
  },
  getBackendActionId(actionId) {
    if (!actionId) return null;
    const catalogId = this.normalizeCatalogActionId(actionId);
    return this.CATALOG_TO_BACKEND_ACTION_ID[catalogId] || actionId;
  },
};

window.APP_CONFIG.isPoseSupported = function isPoseSupported(actionId) {
  const catalogId = this.normalizeCatalogActionId(actionId);
  return this.SUPPORTED_POSE_ACTION_IDS.includes(catalogId);
};

window.ACTION_CATALOG = {
  neck_side_bend: {
    id: "neck_side_bend",
    name: "颈部侧屈拉伸",
    description: "坐位或站位，头缓慢向一侧侧屈至轻度拉伸感，停留15–20秒，双侧交替。",
    contraindications: "颈椎不稳、急性神经根压迫症状加重期禁用",
    image: "assets/neck_side_bend.svg",
    sets: 3,
    reps: 2,
    target_regions: ["颈部"],
    keywords: ["颈", "颈椎", "脖子", "转头", "落枕"],
  },
  chin_tuck: {
    id: "chin_tuck",
    name: "收下巴训练",
    description: "坐位，下颌微收使后脑勺与衣领贴近，停留5–8秒后放松，强化颈深屈肌。",
    contraindications: "急性颈椎骨折、严重眩晕发作期暂停",
    image: "assets/exercise_generic.svg",
    sets: 3,
    reps: 10,
    target_regions: ["颈部"],
    keywords: ["颈", "低头", "前倾", "伏案", "富贵包"],
  },
  shoulder_roll: {
    id: "shoulder_roll",
    name: "肩胛绕环训练",
    description: "站立，双肩向后下方绕环，幅度以不诱发疼痛为限，改善圆肩与上背僵硬。",
    contraindications: "肩关节急性脱位、肩袖急性撕裂期禁用",
    image: "assets/exercise_generic.svg",
    sets: 2,
    reps: 10,
    target_regions: ["肩部"],
    keywords: ["肩", "肩胛", "圆肩", "抬手", "冻结"],
  },
  cat_cow: {
    id: "cat_cow",
    name: "猫牛式脊柱松动",
    description: "四点跪位，交替做脊柱屈曲与伸展，动作缓慢可控，改善腰椎活动度。",
    contraindications: "腰椎间盘突出急性期疼痛明显时减量或暂停",
    image: "assets/exercise_generic.svg",
    sets: 2,
    reps: 8,
    target_regions: ["腰部"],
    keywords: ["腰", "腰椎", "久坐", "弯腰", "僵硬"],
  },
  pelvic_tilt: {
    id: "pelvic_tilt",
    name: "骨盆后倾训练",
    description: "仰卧屈膝，收紧腹部使腰椎贴紧床面，停留5秒后放松，减轻腰椎前凸负荷。",
    contraindications: "妊娠晚期、急性腰肌痉挛剧痛时谨慎进行",
    image: "assets/exercise_generic.svg",
    sets: 3,
    reps: 10,
    target_regions: ["腰部"],
    keywords: ["腰", "骨盆", "突出", "劳损", "久站"],
  },
  wall_squat: {
    id: "wall_squat",
    name: "靠墙静蹲",
    description: "背靠墙缓慢下蹲至大腿近似平行，膝尖不超过脚尖，保持30秒，增强膝周稳定性。",
    contraindications: "急性膝关节炎肿胀期、髌股关节疼痛明显时减量",
    image: "assets/wall_squat.svg",
    sets: 3,
    reps: 1,
    target_regions: ["膝关节"],
    keywords: ["膝", "髌骨", "蹲", "下楼", "跑步"],
  },
  calf_stretch: {
    id: "calf_stretch",
    name: "小腿后侧拉伸",
    description: "面对墙一步距离，后腿伸直脚跟贴地，身体前倾至小腿后侧有牵拉感，停留20秒。",
    contraindications: "跟腱急性断裂、踝部急性扭伤48小时内不宜",
    image: "assets/exercise_generic.svg",
    sets: 3,
    reps: 2,
    target_regions: ["踝关节"],
    keywords: ["踝", "跟腱", "小腿", "脚跟", "足底"],
  },
  ankle_pump: {
    id: "ankle_pump",
    name: "踝泵运动",
    description: "坐位或卧位，脚尖尽力背伸与跖屈，节律进行，促进踝活动与静脉回流。",
    contraindications: "踝部骨折未固定、深静脉血栓未评估前慎用",
    image: "assets/exercise_generic.svg",
    sets: 3,
    reps: 20,
    target_regions: ["踝关节"],
    keywords: ["踝", "肿胀", "术后", "血栓", "久卧"],
  },
};

window.ACTION_NAME_TO_ID = Object.fromEntries(
  Object.values(window.ACTION_CATALOG).map((action) => [action.name, action.id])
);

window.PAIN_REGIONS = ["颈部", "肩部", "腰部", "膝关节", "踝关节"];

window.REGION_HINTS = {
  颈部: ["颈", "颈椎", "脖子", "转头", "落枕", "低头"],
  肩部: ["肩", "肩胛", "圆肩", "抬手", "冻结"],
  腰部: ["腰", "腰椎", "久坐", "弯腰", "突出", "劳损"],
  膝关节: ["膝", "髌骨", "蹲", "下楼", "跑步"],
  踝关节: ["踝", "脚跟", "小腿", "跟腱", "肿胀"],
};
