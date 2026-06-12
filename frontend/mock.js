function resolveActionId(action) {
  if (action.id) return action.id;
  return window.ACTION_NAME_TO_ID[action.name] || null;
}

function enrichAction(action) {
  const id = resolveActionId(action);
  const catalog = id ? window.ACTION_CATALOG[id] : null;
  return {
    id,
    name: action.name,
    sets: action.sets ?? catalog?.sets ?? 3,
    reps: action.reps ?? catalog?.reps ?? 10,
    note: action.note ?? "",
    description: catalog?.description ?? "",
    contraindications: catalog?.contraindications ?? "",
    image: catalog?.image ?? "assets/neck_side_bend.svg",
  };
}

function buildMockPrescription(formData) {
  const regions = formData.pain_regions?.length
    ? formData.pain_regions.join("、")
    : "未指定";
  const ids =
    formData.pain_regions?.includes("膝关节") ||
    formData.symptoms.includes("膝")
      ? ["wall_squat", "neck_side_bend"]
      : ["neck_side_bend", "wall_squat"];

  const actions = ids.map((id) => {
    const catalog = window.ACTION_CATALOG[id];
    return enrichAction({
      id,
      name: catalog.name,
      sets: catalog.sets,
      reps: catalog.reps,
      note:
        id === "neck_side_bend"
          ? "温和进行，出现强烈疼痛立即停止"
          : "保持呼吸顺畅，膝盖勿超过脚尖",
    });
  });

  return {
    summary: `基于主诉「${formData.symptoms}」的个性化康复处方。疼痛部位：${regions}；活动度自评：${formData.mobility_score}/10。`,
    actions,
  };
}

function angleBetween(a, b, c) {
  const ab = { x: a[0] - b[0], y: a[1] - b[1] };
  const cb = { x: c[0] - b[0], y: c[1] - b[1] };
  const dot = ab.x * cb.x + ab.y * cb.y;
  const mag =
    Math.hypot(ab.x, ab.y) * Math.hypot(cb.x, cb.y) || 1;
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

  if (!window.ACTION_CATALOG[action_id]) {
    return {
      feedback: ["暂不支持该动作"],
      score: 0,
      status: "error",
    };
  }

  if (action_id === "wall_squat") {
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

  if (action_id === "neck_side_bend") {
    const nose = keypoints[0];
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
};
