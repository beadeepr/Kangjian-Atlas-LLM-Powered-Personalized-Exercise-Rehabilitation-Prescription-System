function resolveRawActionId(action) {
  if (action.id) return action.id;
  return window.ACTION_NAME_TO_ID[action.name] || null;
}

function resolveActionId(action) {
  const rawId = resolveRawActionId(action);
  return rawId ? window.APP_CONFIG.normalizeCatalogActionId(rawId) : null;
}

function enrichAction(action) {
  const rawId = resolveRawActionId(action);
  const catalog = rawId ? window.ACTION_CATALOG[rawId] : null;
  const catalogId = catalog?.id || rawId;
  return {
    id: catalogId,
    backendId: rawId ? window.APP_CONFIG.getBackendActionId(rawId) : null,
    name: action.name || catalog?.name || "康复动作",
    sets: action.sets ?? catalog?.sets ?? 3,
    reps: action.reps ?? catalog?.reps ?? 10,
    frequency: action.frequency ?? catalog?.frequency ?? "",
    note: action.note ?? "",
    description: action.description ?? catalog?.description ?? action.note ?? "",
    contraindications: action.contraindications ?? catalog?.contraindications ?? "",
    progression: action.progression ?? catalog?.progression ?? "",
    regression: action.regression ?? catalog?.regression ?? "",
    category: action.category ?? "",
    difficulty_level: action.difficulty_level ?? "初级",
    stage: action.stage ?? "",
    target_muscles: action.target_muscles ?? [],
    equipment: action.equipment ?? [],
    body_regions: action.body_regions ?? catalog?.target_regions ?? [],
    steps: action.steps ?? [],
    common_mistakes: action.common_mistakes ?? [],
    correct_cues: action.correct_cues ?? [],
    error_comparisons: action.error_comparisons ?? [],
    difficulty_profiles: action.difficulty_profiles ?? [],
    risk_level: action.risk_level ?? "",
    image: action.image || catalog?.image || (rawId ? window.APP_CONFIG.actionImage(rawId) : ""),
    videoUrl: action.video_url || action.videoUrl || catalog?.videoUrl || "",
    videoHint: action.video_hint || action.videoHint || catalog?.videoHint || "",
  };
}

function scoreAction(action, symptoms, painRegions, history) {
  const text = `${symptoms} ${history || ""}`;
  let score = 0;

  (painRegions || []).forEach((region) => {
    if (action.target_regions?.includes(region)) score += 4;
    (window.REGION_HINTS[region] || []).forEach((hint) => {
      if (text.includes(hint)) score += 1;
    });
  });

  (action.keywords || []).forEach((keyword) => {
    if (text.includes(keyword)) score += 3;
  });

  return score;
}

const SIMILAR_ACTION_GROUPS = [
  ["neck_chin_tuck", "chin_tuck"],
  ["bird_dog", "dead_bug"],
];

function dedupeSimilarActions(actions) {
  const kept = [];
  const usedGroups = new Set();
  for (const action of actions) {
    const group = SIMILAR_ACTION_GROUPS.find((ids) => ids.includes(action.id));
    if (group) {
      const key = group.join("|");
      if (usedGroups.has(key)) continue;
      usedGroups.add(key);
    }
    kept.push(action);
  }
  return kept;
}

function selectActionsForPrescription(formData) {
  const catalog = Object.values(window.ACTION_CATALOG);
  const scored = catalog
    .map((action) => ({
      action,
      score: scoreAction(action, formData.symptoms, formData.pain_regions, formData.history),
    }))
    .sort((a, b) => b.score - a.score);

  let selected = scored.filter((item) => item.score > 0).map((item) => item.action).slice(0, 4);

  if (selected.length < 2) {
    const regionDefaults = {
      颈部: ["neck_chin_tuck", "neck_side_bend"],
      肩部: ["scapular_retraction", "neck_side_bend"],
      腰部: ["cat_cow", "pelvic_tilt"],
      膝关节: ["wall_squat", "straight_leg_raise"],
      踝关节: ["ankle_pump", "calf_stretch"],
    };
    const fallbackIds = [];
    (formData.pain_regions || []).forEach((region) => {
      fallbackIds.push(...(regionDefaults[region] || []));
    });
    if (!fallbackIds.length) {
      fallbackIds.push("neck_side_bend", "cat_cow", "wall_squat");
    }
    fallbackIds.forEach((id) => {
      if (selected.length >= 2) return;
      const candidate = window.ACTION_CATALOG[id];
      if (candidate && !selected.find((item) => item.id === id)) {
        selected.push(candidate);
      }
    });
  }

  if (formData.mobility_score <= 4) {
    selected = selected.map((action) => ({
      ...action,
      sets: Math.max(2, action.sets - 1),
      reps: Math.max(1, action.reps),
    }));
  }

  return dedupeSimilarActions(selected.slice(0, 4)).map((action) =>
    enrichAction({
      id: action.id,
      name: action.name,
      sets: action.sets,
      reps: action.reps,
      note: action.description,
    })
  );
}

function buildMockPrescription(formData) {
  const regions = formData.pain_regions?.length
    ? formData.pain_regions.join("、")
    : "未指定";
  const actions = selectActionsForPrescription(formData);

  return {
    summary:
      `基于主诉「${formData.symptoms}」的个性化康复处方。\n` +
      `疼痛部位：${regions}；活动度自评：${formData.mobility_score}/10。\n` +
      `训练原则：循序渐进，以不诱发剧烈疼痛为度；如出现麻木、刺痛或症状加重，请立即停止并就医。`,
    actions,
  };
}

function angleBetween(a, b, c) {
  const ab = { x: a[0] - b[0], y: a[1] - b[1] };
  const cb = { x: c[0] - b[0], y: c[1] - b[1] };
  const dot = ab.x * cb.x + ab.y * cb.y;
  const mag = Math.hypot(ab.x, ab.y) * Math.hypot(cb.x, cb.y) || 1;
  const cos = Math.max(-1, Math.min(1, dot / mag));
  return (Math.acos(cos) * 180) / Math.PI;
}

function mockCorrectPose(payload) {
  const { action_id, keypoints, visibility } = payload;

  if (!keypoints || keypoints.length < 33) {
    return {
      feedback: ["请全身入镜，确保摄像头能拍到完整身体"],
      score: 0,
      status: "error",
    };
  }

  const avgVisibility =
    visibility?.length === 33
      ? visibility.reduce((sum, value) => sum + value, 0) / 33
      : 1;

  if (avgVisibility < 0.3) {
    return {
      feedback: ["光线不足或遮挡严重，请调整位置"],
      score: 50,
      status: "warning",
    };
  }

  const catalogId = window.APP_CONFIG.normalizeCatalogActionId(action_id);
  if (!window.APP_CONFIG.isPoseSupported(catalogId)) {
    return {
      feedback: ["暂不支持该动作"],
      score: 0,
      status: "error",
    };
  }

  if (catalogId === "wall_squat") {
    const hip = keypoints[23];
    const knee = keypoints[25];
    const ankle = keypoints[27];
    const kneeAngle = angleBetween(hip, knee, ankle);

    if (kneeAngle < 80) {
      return {
        feedback: ["膝关节角度过小，请稍微站高一点"],
        score: 58,
        status: "warning",
      };
    }
    if (kneeAngle > 130) {
      return {
        feedback: ["膝关节角度过小，请再蹲深一点"],
        score: 62,
        status: "warning",
      };
    }
    return {
      feedback: ["膝盖角度合适，背部贴墙，继续保持"],
      score: 88,
      status: "ok",
    };
  }

  if (catalogId === "neck_side_bend") {
    const leftEar = keypoints[7];
    const rightEar = keypoints[8];
    const leftShoulder = keypoints[11];
    const rightShoulder = keypoints[12];
    const leftTilt = Math.abs(leftEar[1] - leftShoulder[1]);
    const rightTilt = Math.abs(rightEar[1] - rightShoulder[1]);

    if (leftTilt > 0.08 || rightTilt > 0.08) {
      return {
        feedback: ["头部倾斜幅度良好，保持停留20秒"],
        score: 86,
        status: "ok",
      };
    }
    return {
      feedback: ["请再向一侧缓慢侧屈，感受对侧拉伸"],
      score: 64,
      status: "warning",
    };
  }

  return {
    feedback: ["动作检测中，请保持稳定"],
    score: 70,
    status: "warning",
  };
}

function generateDemoKeypoints(actionId) {
  const points = Array.from({ length: 33 }, () => [0.5, 0.5, 0]);
  const visibility = Array.from({ length: 33 }, () => 0.95);

  if (actionId === "wall_squat") {
    points[23] = [0.45, 0.55, 0];
    points[25] = [0.45, 0.72, 0];
    points[27] = [0.45, 0.9, 0];
    points[24] = [0.55, 0.55, 0];
    points[26] = [0.55, 0.72, 0];
    points[28] = [0.55, 0.9, 0];
  } else {
    points[0] = [0.52, 0.2, 0];
    points[7] = [0.46, 0.22, 0];
    points[8] = [0.58, 0.24, 0];
    points[11] = [0.42, 0.38, 0];
    points[12] = [0.62, 0.38, 0];
  }

  return { keypoints: points, visibility };
}

window.MockService = {
  buildMockPrescription,
  enrichAction,
  resolveActionId,
  mockCorrectPose,
  generateDemoKeypoints,
  selectActionsForPrescription,
};
