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

// 开发默认连本机后端。答辩/录屏请用 http://localhost:端口 打开前端，避免地址栏出现内网 IP。
// 跨设备局域网演示时，可在 index.html 前面临时设置 window.API_BASE = "http://<主机IP>:8000/api"。
function readApiBase() {
  if (window.API_BASE) {
    return window.API_BASE;
  }
  const { protocol, hostname, port } = window.location;
  if (port === "8000") {
    return "/api";
  }
  const host = hostname === "localhost" ? "127.0.0.1" : hostname;
  return `${protocol}//${host}:8000/api`;
}

window.APP_CONFIG = {
  API_BASE: readApiBase(),
  DEMO_MODE: readDemoMode(),
  DEV_MODE: readDevMode(),
  FETCH_TIMEOUT_MS: 5000,
  LIST_TIMEOUT_MS: 8000,
  AUTH_TIMEOUT_MS: 10000,
  PRESCRIPTION_TIMEOUT_MS: 45000,
  POSE_TIMEOUT_MS: 2000,
  POSE_SEND_INTERVAL_MS: 50,
  POSE_USE_BACKEND: true,
  POSE_VISIBILITY_MIN: 0.5,
  POSE_KEYPOINT_NAMES: {
    0: "鼻子",
    1: "左眼",
    2: "右眼",
    3: "左耳",
    4: "右耳",
    5: "左肩",
    6: "右肩",
    7: "左肘",
    8: "右肘",
    9: "左腕",
    10: "右腕",
    11: "左髋",
    12: "右髋",
    13: "左膝",
    14: "右膝",
    15: "左踝",
    16: "右踝",
  },
  POSE_REQUIRED_KEYPOINTS: {
    neck_chin_tuck: [0, 3, 4, 5, 6],
    chin_tuck: [0, 3, 4, 5, 6],
    neck_side_bend: [0, 3, 4, 5, 6],
    scapular_retraction: [3, 4, 5, 6],
    thoracic_extension: [5, 6, 11, 12],
    mckenzie_press_up: [5, 6, 7, 8, 9, 10, 11, 12],
    pelvic_tilt: [5, 6, 11, 12],
    bird_dog: [5, 6, 11, 12, 7, 8, 13, 14],
    dead_bug: [5, 6, 11, 12, 9, 10],
    glute_bridge: [5, 6, 11, 12, 13, 14],
    wall_squat: [11, 12, 13, 14, 15, 16],
    straight_leg_raise: [11, 12, 13, 14, 15, 16],
    quad_set: [11, 12, 13, 14],
    calf_stretch: [13, 14, 15, 16],
    ankle_pump: [13, 14, 15, 16],
    shoulder_pendulum: [5, 6, 7, 8, 9, 10],
    shoulder_external_rotation: [5, 6, 7, 8, 11, 12],
  },
  SUPPORTED_POSE_ACTION_IDS: [
    "neck_side_bend",
    "neck_chin_tuck",
    "scapular_retraction",
    "thoracic_extension",
    "mckenzie_press_up",
    "glute_bridge",
    "wall_squat",
    "straight_leg_raise",
    "shoulder_external_rotation",
  ],
  ACTION_ID_ALIASES: {},
  CATALOG_TO_BACKEND_ACTION_ID: {
    chin_tuck: "neck_chin_tuck",
  },
  actionImage(actionId) {
    return `assets/actions/${actionId}.png`;
  },
  POSE_CAMERA_HINTS: {
    neck_side_bend: "侧对镜头，便于捕捉头颈侧屈幅度",
    neck_chin_tuck: "正面对镜头，保持头颈与肩部清晰入镜",
    scapular_retraction: "正面对镜头，确保双肩完整入镜",
    thoracic_extension: "正面对镜头或微侧身，便于观察上背伸展",
    mckenzie_press_up: "侧对镜头，便于观察躯干伸展与骨盆位置",
    glute_bridge: "侧对镜头，确保肩、髋、膝连线清晰可见",
    wall_squat: "侧对镜头，便于观察膝部弯曲角度",
    straight_leg_raise: "侧躺对镜头，便于观察抬腿高度与膝部角度",
    shoulder_external_rotation: "正面对镜头，确保肘部贴紧身体且肩部入镜",
  },
  isSafeMediaUrl(path) {
    if (!path || typeof path !== "string") return false;
    const trimmed = path.trim();
    if (!trimmed || trimmed.includes("\0")) return false;
    if (trimmed.startsWith("//")) return false;
    if (/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(trimmed)) {
      try {
        const protocol = new URL(trimmed).protocol;
        return protocol === "http:" || protocol === "https:";
      } catch {
        return false;
      }
    }
    return true;
  },
  assetUrl(path) {
    if (!this.isSafeMediaUrl(path)) return "";
    return new URL(path, window.location.href).href;
  },
  isValidVideoUrl(url) {
    return this.isSafeMediaUrl(url);
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
  getPoseCameraHint(actionId) {
    const catalogId = this.normalizeCatalogActionId(actionId);
    return this.POSE_CAMERA_HINTS[catalogId] || "保持全身入镜，动作缓慢可控";
  },
  getSupportedPoseActionNames() {
    return this.SUPPORTED_POSE_ACTION_IDS.map(
      (id) => window.ACTION_CATALOG[id]?.name || id
    );
  },
  getUnsupportedPoseHint() {
    return "该动作暂不支持实时纠正，可先按处方说明与示范视频完成训练。";
  },
  MOBILITY_GUIDES: {
    颈部: {
      icon: "🔄",
      title: "颈部旋转测试",
      instruction: "坐姿缓慢左右转头，观察是否出现疼痛、麻木或明显受限。",
    },
    肩部: {
      icon: "🙆",
      title: "扶墙滑臂测试",
      instruction: "面对墙面，示指沿墙向上滑动，比较两侧抬臂高度与是否诱发肩痛。",
    },
    腰部: {
      icon: "🧍",
      title: "前屈触趾测试",
      instruction: "站立缓慢前屈，评估腰部是否僵硬、疼痛或无法继续弯曲。",
    },
    膝关节: {
      icon: "🦵",
      title: "半蹲测试",
      instruction: "扶椅背缓慢半蹲，观察膝部是否疼痛、弹响或无法完成。",
    },
    踝关节: {
      icon: "👣",
      title: "勾脚背屈测试",
      instruction: "坐位勾脚背，比较两侧背屈幅度与跟腱/小腿是否牵拉痛。",
    },
  },
  DEFAULT_MOBILITY_GUIDE: {
    icon: "📋",
    title: "日常活动自评",
    instruction: "回忆近期弯腰、下蹲、转身、抬手等动作是否因疼痛明显受限。",
  },
};

window.APP_CONFIG.isPoseSupported = function isPoseSupported(actionId) {
  const catalogId = this.normalizeCatalogActionId(actionId);
  return this.SUPPORTED_POSE_ACTION_IDS.includes(catalogId);
};

window.ACTION_CATALOG = {
  neck_chin_tuck: {
    id: "neck_chin_tuck",
    name: "下巴回收训练",
    description:
      "坐姿或站姿保持躯干直立，缓慢将下巴向后回收，感受颈后轻微拉伸，保持3-5秒后放松。",
    contraindications: "急性颈部外伤、明显眩晕、上肢麻木加重时暂停。",
    frequency: "每日1-2次",
    sets: 3,
    reps: 10,
    target_regions: ["颈部", "肩部"],
    keywords: ["颈", "颈椎", "下巴", "前倾", "伏案", "姿势"],
    image: "assets/actions/neck_chin_tuck.png",
    videoUrl: "https://www.bilibili.com/video/BV1E741117d1/",
    videoHint: "",
    imageHint: "建议：正侧面示意图，标出下巴水平后移与耳肩对齐",
  },
  neck_side_bend: {
    id: "neck_side_bend",
    name: "颈部侧屈拉伸",
    description: "坐姿或站姿，缓慢将头向一侧倾斜，停留20秒，左右交替完成。",
    contraindications: "颈椎不稳、急性炎症期、牵拉时放射痛明显者禁忌。",
    frequency: "每日1次",
    sets: 3,
    reps: 1,
    target_regions: ["颈部"],
    keywords: ["颈", "颈椎", "侧屈", "拉伸", "落枕"],
    image: "assets/actions/neck_side_bend.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：正面或侧面示意图，标出耳朵向肩膀靠近的拉伸方向",
  },
  scapular_retraction: {
    id: "scapular_retraction",
    name: "肩胛后缩训练",
    description:
      "双臂自然下垂或屈肘，缓慢将两侧肩胛骨向后向下夹紧，保持5秒后放松。",
    contraindications: "肩关节急性损伤、明显肿胀或夜间痛明显时谨慎。",
    frequency: "每周4-5次",
    sets: 3,
    reps: 12,
    target_regions: ["肩部", "颈部"],
    keywords: ["肩", "肩胛", "圆肩", "驼背", "姿势"],
    image: "assets/actions/scapular_retraction.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：背面示意图，用箭头标出肩胛骨向脊柱方向夹紧",
  },
  thoracic_extension: {
    id: "thoracic_extension",
    name: "胸椎伸展训练",
    description:
      "坐姿双手抱头，上背部轻靠椅背，缓慢向后伸展胸椎，避免腰部过度代偿。",
    contraindications: "骨质疏松压缩骨折、胸背部急性疼痛时禁忌。",
    frequency: "每日1次",
    sets: 2,
    reps: 10,
    target_regions: ["肩部", "颈部"],
    keywords: ["胸椎", "驼背", "圆肩", "伏案", "伸展"],
    image: "assets/actions/thoracic_extension.png",
    videoUrl: "https://www.bilibili.com/video/BV1XMAyziE2J/",
    videoHint: "",
    imageHint: "建议：坐姿侧面图，标出胸椎后伸而非腰椎过伸",
  },
  cat_cow: {
    id: "cat_cow",
    name: "猫牛式脊柱松动",
    description:
      "四点跪位，交替做脊柱屈曲与伸展，动作缓慢可控，用于改善腰椎活动度与核心控制。",
    contraindications: "腰椎间盘突出急性期疼痛明显时减量或暂停。",
    frequency: "每日1次",
    sets: 2,
    reps: 8,
    target_regions: ["腰部"],
    keywords: ["腰", "腰椎", "猫牛", "脊柱", "久坐"],
    image: "assets/actions/cat_cow.png",
    videoUrl: "https://www.bilibili.com/video/BV1nA411i766/",
    videoHint: "",
    imageHint: "建议：四点跪位侧面连续两帧，分别示「拱背」与「塌腰」",
  },
  pelvic_tilt: {
    id: "pelvic_tilt",
    name: "骨盆后倾训练",
    description: "仰卧屈膝，收紧腹部使腰背轻贴床面，保持5秒后放松。",
    contraindications: "急性腹部术后、动作诱发明显疼痛时暂停。",
    frequency: "每日1次",
    sets: 3,
    reps: 12,
    target_regions: ["腰部"],
    keywords: ["腰", "骨盆", "后倾", "核心", "仰卧"],
    image: "assets/actions/pelvic_tilt.png",
    videoUrl: "https://www.bilibili.com/video/BV1xmAfzKEqU/",
    videoHint: "",
    imageHint: "建议：仰卧侧面图，标出腰椎贴地与骨盆后倾角度",
  },
  bird_dog: {
    id: "bird_dog",
    name: "鸟狗式核心训练",
    description:
      "四点跪姿，保持腰背稳定，缓慢伸出对侧手臂和腿，保持3秒后还原。",
    contraindications: "跪姿膝痛明显、动作中腰痛加重时谨慎。",
    frequency: "每周3-4次",
    sets: 3,
    reps: 8,
    target_regions: ["腰部"],
    keywords: ["腰", "核心", "鸟狗", "稳定", "四点跪"],
    image: "assets/actions/bird_dog.png",
    videoUrl: "https://www.bilibili.com/video/BV1bKKVzEEHP",
    videoHint: "",
    imageHint: "建议：俯视角或侧面图，标出对侧手脚伸展与躯干稳定",
  },
  dead_bug: {
    id: "dead_bug",
    name: "死虫式核心训练",
    description:
      "仰卧抬起双腿和双臂，保持腰背贴近地面，缓慢放下对侧手脚后还原。",
    contraindications: "无法控制腰椎中立位或动作诱发腰痛时暂停。",
    frequency: "每周3-4次",
    sets: 3,
    reps: 8,
    target_regions: ["腰部"],
    keywords: ["腰", "核心", "死虫", "仰卧", "稳定"],
    image: "assets/actions/dead_bug.png",
    videoUrl: "https://www.bilibili.com/video/BV1zYL8zTEcV",
    videoHint: "",
    imageHint: "建议：仰卧示意图，标出对侧手脚下放时腰椎不离地",
  },
  glute_bridge: {
    id: "glute_bridge",
    name: "臀桥训练",
    description:
      "仰卧屈膝，收紧臀部将骨盆抬起至肩髋膝接近一条直线，保持2秒后缓慢放下。",
    contraindications: "腰部代偿明显、髋部急性疼痛时谨慎。",
    frequency: "每周3-5次",
    sets: 3,
    reps: 12,
    target_regions: ["腰部"],
    keywords: ["腰", "臀", "桥式", "无力", "骨盆"],
    image: "assets/actions/glute_bridge.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：侧面图，标出肩-髋-膝一线与臀部发力",
  },
  wall_squat: {
    id: "wall_squat",
    name: "靠墙静蹲",
    description:
      "背靠墙，下蹲至可耐受角度，膝盖方向与脚尖一致，保持20-30秒。",
    contraindications: "急性膝关节疼痛、严重膝关节炎、明显肿胀时谨慎。",
    frequency: "每周3-4次",
    sets: 3,
    reps: 1,
    target_regions: ["膝关节"],
    keywords: ["膝", "蹲", "股四头肌", "髌骨", "下楼"],
    image: "assets/actions/wall_squat.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：侧面图，标出膝不超过脚尖、背靠墙角度",
  },
  straight_leg_raise: {
    id: "straight_leg_raise",
    name: "直腿抬高训练",
    description: "仰卧，一侧膝关节伸直，缓慢抬高至约30度，保持2秒后放下。",
    contraindications: "腰痛明显加重或髋部疼痛时谨慎。",
    frequency: "每日1次",
    sets: 3,
    reps: 10,
    target_regions: ["膝关节"],
    keywords: ["膝", "直腿抬高", "股四头肌", "术后", "无力"],
    image: "assets/actions/straight_leg_raise.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：仰卧侧面图，标出抬腿约30°与膝伸直",
  },
  quad_set: {
    id: "quad_set",
    name: "股四头肌等长收缩",
    description:
      "仰卧或坐位，膝下垫毛巾，绷紧大腿前侧肌肉并向下压毛巾，保持5秒。",
    contraindications: "医生限制主动收缩或急性损伤未评估时谨慎。",
    frequency: "每日1-2次",
    sets: 3,
    reps: 12,
    target_regions: ["膝关节"],
    keywords: ["膝", "股四头肌", "等长", "术后", "毛巾"],
    image: "assets/actions/quad_set.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：特写膝部与毛巾，标出大腿前侧绷紧下压",
  },
  calf_stretch: {
    id: "calf_stretch",
    name: "小腿后侧拉伸",
    description:
      "面对墙一步距离，后腿伸直脚跟贴地，身体前倾至小腿后侧有牵拉感，停留20秒。",
    contraindications: "跟腱急性断裂、踝部急性扭伤48小时内不宜。",
    frequency: "每日1次",
    sets: 3,
    reps: 2,
    target_regions: ["踝关节"],
    keywords: ["踝", "小腿", "跟腱", "拉伸", "脚跟"],
    image: "assets/actions/calf_stretch.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：弓步拉墙侧面图，标出后脚跟着地与牵拉方向",
  },
  ankle_pump: {
    id: "ankle_pump",
    name: "踝泵运动",
    description:
      "坐位或卧位，脚尖尽力背伸与跖屈，节律进行，促进下肢静脉回流与踝活动。",
    contraindications: "踝部骨折未固定、深静脉血栓未评估前慎用。",
    frequency: "每日2次",
    sets: 3,
    reps: 20,
    target_regions: ["踝关节"],
    keywords: ["踝", "踝泵", "肿胀", "术后", "久卧"],
    image: "assets/actions/ankle_pump.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：足部背伸/跖屈两帧对比示意图",
  },
  shoulder_pendulum: {
    id: "shoulder_pendulum",
    name: "肩关节钟摆运动",
    description:
      "身体前倾，患侧手臂自然下垂，利用身体轻微摆动带动手臂做小幅前后、左右或画圈。",
    contraindications: "肩关节脱位未复位、急性骨折或剧烈疼痛时禁忌。",
    frequency: "每日1次",
    sets: 2,
    reps: 15,
    target_regions: ["肩部"],
    keywords: ["肩", "钟摆", "冻结肩", "活动度", "摆动"],
    image: "assets/actions/shoulder_pendulum.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：体前屈侧面图，标出手臂自然下垂与摆动轨迹",
  },
  shoulder_external_rotation: {
    id: "shoulder_external_rotation",
    name: "肩外旋弹力带训练",
    description:
      "肘关节屈曲90度夹近身体，手持弹力带向外旋转肩关节，缓慢还原。",
    contraindications: "急性肩袖撕裂、外旋时锐痛明显者禁忌。",
    frequency: "每周3次",
    sets: 3,
    reps: 10,
    target_regions: ["肩部"],
    keywords: ["肩", "外旋", "肩袖", "弹力带", "旋转"],
    image: "assets/actions/shoulder_external_rotation.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：正面图，标出肘贴身体与外旋角度",
  },
  lifting_of_arms: {
    id: "lifting_of_arms",
    name: "抬臂",
    description:
      "坐位或站位，缓慢将双臂抬至肩水平或舒适高度，保持2-3秒后放下，用于肩肘协调活动度训练。",
    contraindications: "肩关节脱位未复位、抬臂时锐痛或放射痛明显时暂停。",
    frequency: "每日1-2次",
    sets: 3,
    reps: 10,
    target_regions: ["肩部"],
    keywords: ["肩", "肘", "抬臂", "活动度", "KIMORE", "上肢"],
    image: "assets/actions/lifting_of_arms.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：正面图，标出双臂抬至肩水平的终末位置",
  },
  shoulder_abduction_left: {
    id: "shoulder_abduction_left",
    name: "左肩外展",
    description:
      "站位或坐位，左侧手臂沿身体侧面向外抬起至肩水平或舒适高度，缓慢还原，避免耸肩代偿。",
    contraindications: "左肩急性损伤、外展时剧烈疼痛或冻结肩急性期慎做。",
    frequency: "每日1-2次",
    sets: 3,
    reps: 10,
    target_regions: ["肩部"],
    keywords: ["肩", "外展", "左肩", "活动度", "IRDS"],
    image: "assets/actions/shoulder_abduction_left.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：正面图，标出左臂侧向抬起轨迹",
  },
  shoulder_abduction_right: {
    id: "shoulder_abduction_right",
    name: "右肩外展",
    description:
      "站位或坐位，右侧手臂沿身体侧面向外抬起至肩水平或舒适高度，缓慢还原，避免耸肩代偿。",
    contraindications: "右肩急性损伤、外展时剧烈疼痛或冻结肩急性期慎做。",
    frequency: "每日1-2次",
    sets: 3,
    reps: 10,
    target_regions: ["肩部"],
    keywords: ["肩", "外展", "右肩", "活动度", "IRDS"],
    image: "assets/actions/shoulder_abduction_right.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：正面图，标出右臂侧向抬起轨迹",
  },
  shoulder_flexion_left: {
    id: "shoulder_flexion_left",
    name: "左肩屈曲",
    description:
      "站位或坐位，左侧手臂沿身体前面向前上方抬起至肩水平或舒适高度，缓慢还原，保持躯干稳定。",
    contraindications: "左肩急性损伤、屈曲时锐痛或代偿明显时暂停。",
    frequency: "每日1-2次",
    sets: 3,
    reps: 10,
    target_regions: ["肩部"],
    keywords: ["肩", "屈曲", "左肩", "前屈", "IRDS"],
    image: "assets/actions/shoulder_flexion_left.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：侧面图，标出左臂前屈抬起角度",
  },
  shoulder_flexion_right: {
    id: "shoulder_flexion_right",
    name: "右肩屈曲",
    description:
      "站位或坐位，右侧手臂沿身体前面向前上方抬起至肩水平或舒适高度，缓慢还原，保持躯干稳定。",
    contraindications: "右肩急性损伤、屈曲时锐痛或代偿明显时暂停。",
    frequency: "每日1-2次",
    sets: 3,
    reps: 10,
    target_regions: ["肩部"],
    keywords: ["肩", "屈曲", "右肩", "前屈", "IRDS"],
    image: "assets/actions/shoulder_flexion_right.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：侧面图，标出右臂前屈抬起角度",
  },
  shoulder_forward_elevation: {
    id: "shoulder_forward_elevation",
    name: "肩前屈",
    description:
      "站位或坐位，双臂或单臂沿身体前面向前上方抬起，至肩水平或舒适高度后缓慢放下，动作连贯可控。",
    contraindications: "肩关节急性损伤、前屈诱发明显疼痛或腰椎代偿时暂停。",
    frequency: "每日1-2次",
    sets: 3,
    reps: 10,
    target_regions: ["肩部"],
    keywords: ["肩", "前屈", "抬手", "活动度", "IRDS"],
    image: "assets/actions/shoulder_forward_elevation.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：侧面图，标出肩前屈终末位与躯干稳定",
  },
  elbow_flexion_left: {
    id: "elbow_flexion_left",
    name: "左肘屈曲",
    description:
      "坐位或站位，左侧前臂缓慢屈曲，使手靠近肩部，在无痛范围内充分弯曲后缓慢伸直。",
    contraindications: "左肘骨折未愈合、屈曲时剧烈疼痛或肿胀明显时暂停。",
    frequency: "每日1-2次",
    sets: 3,
    reps: 12,
    target_regions: ["肩部"],
    keywords: ["肘", "屈曲", "左肘", "活动度", "IRDS"],
    image: "assets/actions/elbow_flexion_left.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：侧面图，标出左肘屈曲角度",
  },
  elbow_flexion_right: {
    id: "elbow_flexion_right",
    name: "右肘屈曲",
    description:
      "坐位或站位，右侧前臂缓慢屈曲，使手靠近肩部，在无痛范围内充分弯曲后缓慢伸直。",
    contraindications: "右肘骨折未愈合、屈曲时剧烈疼痛或肿胀明显时暂停。",
    frequency: "每日1-2次",
    sets: 3,
    reps: 12,
    target_regions: ["肩部"],
    keywords: ["肘", "屈曲", "右肘", "活动度", "IRDS"],
    image: "assets/actions/elbow_flexion_right.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：侧面图，标出右肘屈曲角度",
  },
  mckenzie_press_up: {
    id: "mckenzie_press_up",
    name: "麦肯基俯卧撑",
    description:
      "俯卧位，双手撑地缓慢撑起上半身，骨盆保持贴地，用于腰椎后伸松动（后端算法扩展动作）。",
    contraindications: "腰椎管狭窄急性期、动作诱发下肢放射痛时暂停。",
    frequency: "每日1次",
    sets: 3,
    reps: 10,
    target_regions: ["腰部"],
    keywords: ["腰", "麦肯基", "腰椎", "后伸", "突出"],
    image: "assets/actions/mckenzie_press_up.png",
    videoUrl: "",
    videoHint: "",
    imageHint: "建议：侧面俯卧图，标出骨盆贴地与上半身撑起",
  },
};

window.ACTION_NAME_TO_ID = Object.fromEntries(
  Object.values(window.ACTION_CATALOG).map((action) => [action.name, action.id])
);
window.ACTION_NAME_TO_ID["收下巴训练"] = "neck_chin_tuck";

window.PAIN_REGIONS = ["颈部", "肩部", "腰部", "膝关节", "踝关节"];

window.REGION_HINTS = {
  颈部: ["颈", "颈椎", "脖子", "转头", "落枕", "低头"],
  肩部: ["肩", "肩胛", "圆肩", "抬手", "冻结"],
  腰部: ["腰", "腰椎", "久坐", "弯腰", "突出", "劳损"],
  膝关节: ["膝", "髌骨", "蹲", "下楼", "跑步"],
  踝关节: ["踝", "脚跟", "小腿", "跟腱", "肿胀"],
};
