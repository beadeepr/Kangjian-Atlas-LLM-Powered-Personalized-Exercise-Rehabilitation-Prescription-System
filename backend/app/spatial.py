from __future__ import annotations

from typing import Any


LANDMARK_NAMES = [
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
]

SKELETON_BONES = [
    ("left_shoulder", "right_shoulder", "shoulders"),
    ("left_hip", "right_hip", "pelvis"),
    ("left_shoulder", "left_elbow", "left_upper_arm"),
    ("left_elbow", "left_wrist", "left_forearm"),
    ("right_shoulder", "right_elbow", "right_upper_arm"),
    ("right_elbow", "right_wrist", "right_forearm"),
    ("left_shoulder", "left_hip", "left_trunk"),
    ("right_shoulder", "right_hip", "right_trunk"),
    ("left_hip", "left_knee", "left_thigh"),
    ("left_knee", "left_ankle", "left_shank"),
    ("right_hip", "right_knee", "right_thigh"),
    ("right_knee", "right_ankle", "right_shank"),
    ("left_ankle", "left_heel", "left_heel_line"),
    ("left_heel", "left_foot_index", "left_foot"),
    ("right_ankle", "right_heel", "right_heel_line"),
    ("right_heel", "right_foot_index", "right_foot"),
    ("nose", "left_ear", "left_head"),
    ("nose", "right_ear", "right_head"),
]

HIGHLIGHT_RULES = {
    "neck_chin_tuck": ["nose", "left_ear", "right_ear", "left_shoulder", "right_shoulder"],
    "chin_tuck": ["nose", "left_ear", "right_ear", "left_shoulder", "right_shoulder"],
    "neck_side_bend": ["nose", "left_ear", "right_ear", "left_shoulder", "right_shoulder"],
    "scapular_retraction": ["left_shoulder", "right_shoulder", "left_elbow", "right_elbow"],
    "thoracic_extension": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    "mckenzie_press_up": ["left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_hip", "right_hip"],
    "pelvic_tilt": ["left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "right_knee"],
    "bird_dog": ["left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_wrist", "right_wrist", "left_ankle", "right_ankle"],
    "dead_bug": ["left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "right_knee"],
    "glute_bridge": ["left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "right_knee"],
    "wall_squat": ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"],
    "straight_leg_raise": ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"],
    "quad_set": ["left_hip", "left_knee", "left_ankle"],
    "calf_stretch": ["left_knee", "right_knee", "left_ankle", "right_ankle", "left_heel", "right_heel"],
    "ankle_pump": ["left_knee", "right_knee", "left_ankle", "right_ankle", "left_foot_index", "right_foot_index"],
    "shoulder_pendulum": ["left_shoulder", "right_shoulder", "left_wrist", "right_wrist"],
    "shoulder_external_rotation": ["left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist"],
}


def skeleton_spec() -> dict[str, Any]:
    return {
        "landmark_format": "mediapipe_pose_33",
        "coordinate_space": "normalized_user_centered_3d",
        "landmarks": [{"index": index, "name": name} for index, name in enumerate(LANDMARK_NAMES)],
        "bones": [
            {
                "from": start,
                "to": end,
                "name": name,
                "from_index": LANDMARK_NAMES.index(start),
                "to_index": LANDMARK_NAMES.index(end),
            }
            for start, end, name in SKELETON_BONES
        ],
        "render_hints": {
            "default_joint_radius": 0.018,
            "default_bone_width": 0.01,
            "left_color": "#38bdf8",
            "right_color": "#f97316",
            "trunk_color": "#22c55e",
            "warning_color": "#facc15",
            "error_color": "#ef4444",
        },
    }


def build_skeleton_frame(
    keypoints: list[list[float]],
    visibility: list[float] | None = None,
    action_id: str | None = None,
) -> dict[str, Any]:
    visibility = visibility or [1.0] * len(keypoints)
    points = _normalized_points(keypoints, visibility)
    point_by_name = {point["name"]: point for point in points}
    bones = []
    for start, end, name in SKELETON_BONES:
        start_point = point_by_name.get(start)
        end_point = point_by_name.get(end)
        if not start_point or not end_point:
            continue
        bones.append(
            {
                "name": name,
                "from": start,
                "to": end,
                "visible": start_point["visibility"] >= 0.5 and end_point["visibility"] >= 0.5,
                "length": _distance(start_point["position"], end_point["position"]),
            }
        )

    return {
        "format": "kangjian_skeleton_v1",
        "action_id": action_id,
        "coordinate_space": "normalized_user_centered_3d",
        "joints": points,
        "bones": bones,
        "highlight_joints": HIGHLIGHT_RULES.get(action_id or "", []),
        "center": _center_point(keypoints),
        "scale": _body_scale(keypoints),
    }


def build_ar_overlay(
    action_id: str,
    keypoints: list[list[float]],
    visibility: list[float] | None = None,
    feedback: list[str] | None = None,
    status: str | None = None,
    score: int | None = None,
    viewport_width: int | None = None,
    viewport_height: int | None = None,
    mirror: bool = False,
) -> dict[str, Any]:
    skeleton = build_skeleton_frame(keypoints, visibility, action_id=action_id)
    viewport = {
        "width": viewport_width or 720,
        "height": viewport_height or 1280,
        "mirror": mirror,
    }
    severity = _severity(status, score)
    highlight_names = set(skeleton.get("highlight_joints") or [])
    overlay_items = []
    for joint in skeleton["joints"]:
        if joint["name"] not in highlight_names or joint["visibility"] < 0.5:
            continue
        x, y = _screen_point(joint["source"], viewport)
        overlay_items.append(
            {
                "type": "joint_marker",
                "joint": joint["name"],
                "x": x,
                "y": y,
                "radius": 10 if severity == "ok" else 14,
                "color": _severity_color(severity),
                "opacity": 0.88,
            }
        )

    for bone in skeleton["bones"]:
        if not bone["visible"] or (bone["from"] not in highlight_names and bone["to"] not in highlight_names):
            continue
        start = next(point for point in skeleton["joints"] if point["name"] == bone["from"])
        end = next(point for point in skeleton["joints"] if point["name"] == bone["to"])
        x1, y1 = _screen_point(start["source"], viewport)
        x2, y2 = _screen_point(end["source"], viewport)
        overlay_items.append(
            {
                "type": "bone_line",
                "bone": bone["name"],
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "width": 5,
                "color": _severity_color(severity),
                "opacity": 0.72,
            }
        )

    if feedback:
        overlay_items.append(
            {
                "type": "coach_text",
                "text": "；".join(feedback[:2]),
                "x": int(viewport["width"] * 0.5),
                "y": int(viewport["height"] * 0.12),
                "anchor": "top-center",
                "color": _severity_color(severity),
                "background": "rgba(15, 23, 42, 0.72)",
            }
        )

    return {
        "format": "kangjian_ar_overlay_v1",
        "action_id": action_id,
        "viewport": viewport,
        "severity": severity,
        "score": score,
        "items": overlay_items,
        "skeleton": skeleton,
        "render_hints": {
            "target": "camera_overlay",
            "coordinate_space": "screen_pixels",
            "z_order": ["bone_line", "joint_marker", "coach_text"],
        },
    }


def _normalized_points(keypoints: list[list[float]], visibility: list[float]) -> list[dict[str, Any]]:
    center_x, center_y, center_z = _center_point(keypoints)
    scale = _body_scale(keypoints)
    points = []
    for index, name in enumerate(LANDMARK_NAMES):
        if index >= len(keypoints):
            raw = [0.0, 0.0, 0.0]
            visible = 0.0
        else:
            raw = keypoints[index]
            visible = visibility[index] if index < len(visibility) else 1.0
        x = ((raw[0] if len(raw) > 0 else 0.0) - center_x) / scale
        y = (center_y - (raw[1] if len(raw) > 1 else 0.0)) / scale
        z = ((raw[2] if len(raw) > 2 else 0.0) - center_z) / scale
        points.append(
            {
                "index": index,
                "name": name,
                "position": [round(x, 4), round(y, 4), round(z, 4)],
                "source": [
                    round(raw[0] if len(raw) > 0 else 0.0, 4),
                    round(raw[1] if len(raw) > 1 else 0.0, 4),
                    round(raw[2] if len(raw) > 2 else 0.0, 4),
                ],
                "visibility": round(float(visible), 4),
            }
        )
    return points


def _center_point(keypoints: list[list[float]]) -> list[float]:
    candidates = [index for index in (23, 24, 11, 12) if index < len(keypoints)]
    if not candidates:
        return [0.5, 0.5, 0.0]
    return [
        sum(keypoints[index][axis] if len(keypoints[index]) > axis else 0.0 for index in candidates) / len(candidates)
        for axis in range(3)
    ]


def _body_scale(keypoints: list[list[float]]) -> float:
    pairs = [(11, 12), (23, 24), (11, 23), (12, 24)]
    lengths = []
    for start, end in pairs:
        if start < len(keypoints) and end < len(keypoints):
            lengths.append(_distance(keypoints[start][:3], keypoints[end][:3]))
    scale = max(lengths) if lengths else 0.25
    return max(scale, 0.1)


def _distance(a: list[float], b: list[float]) -> float:
    ax, ay, az = (a + [0.0, 0.0, 0.0])[:3]
    bx, by, bz = (b + [0.0, 0.0, 0.0])[:3]
    return round(((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2) ** 0.5, 4)


def _screen_point(source: list[float], viewport: dict[str, Any]) -> tuple[int, int]:
    x = source[0]
    y = source[1]
    if viewport.get("mirror"):
        x = 1 - x
    return int(x * viewport["width"]), int(y * viewport["height"])


def _severity(status: str | None, score: int | None) -> str:
    if status == "error" or (score is not None and score < 45):
        return "error"
    if status == "warning" or (score is not None and score < 80):
        return "warning"
    return "ok"


def _severity_color(severity: str) -> str:
    return {
        "ok": "#22c55e",
        "warning": "#facc15",
        "error": "#ef4444",
    }.get(severity, "#38bdf8")

