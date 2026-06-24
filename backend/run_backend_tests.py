from __future__ import annotations

import base64
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import traceback

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = Path(__file__).resolve().parent
REPORT_DB = BACKEND_DIR / "reports" / "backend_test.db"
REPORT_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{REPORT_DB}")

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.test_reports import write_report  # noqa: E402


class BackendSmokeSuite:
    def __init__(self):
        self.client = TestClient(app)
        self.cases: list[dict] = []
        self.unique = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        self.user_account = f"autotest_user_{self.unique}"
        self.admin_account = "admin"
        self.user_headers: dict[str, str] = {}
        self.admin_headers: dict[str, str] = {}
        self.doctor_headers: dict[str, str] = {}
        self.doctor_account = f"doctor_{self.unique}"
        self.created_profile_id: int | None = None
        self.created_prescription_id: int | None = None
        self.created_checkin_id: int | None = None
        self.created_feedback_id: int | None = None
        self.actions_path = ROOT_DIR / "knowledge" / "actions.json"
        self.original_actions = self.actions_path.read_text(encoding="utf-8")

    def record(self, name: str, fn):
        try:
            detail = fn() or "通过"
            self.cases.append({"name": name, "status": "passed", "detail": detail})
        except Exception as exc:
            self.cases.append({
                "name": name,
                "status": "failed",
                "detail": f"{exc}\n{traceback.format_exc(limit=2)}",
            })

    def run(self):
        init_db()
        try:
            self.record("健康检查", self.health)
            self.record("生产存储栈配置", self.production_storage_config_flow)
            self.record("用户注册与登录", self.auth_flow)
            self.record("患者档案 CRUD", self.patient_profile_flow)
            self.record("红旗症状处方拦截", self.red_flag_prescription_block)
            self.record("处方生成与导出", self.prescription_export_flow)
            self.record("训练打卡与趋势统计", self.training_flow)
            self.record("实时动作纠正接口", self.pose_correction_flow)
            self.record("RTMPose流式推理接口", self.pose_streaming_flow)
            self.record("3D骨骼与AR叠加服务", self.visual_overlay_flow)
            self.record("语音纠错与疲劳监测", self.voice_and_fatigue_flow)
            self.record("医生协同与处方动态调整闭环", self.doctor_collaboration_flow)
            self.record("康复进度报告", self.progress_report_flow)
            self.record("知识科普与问答", self.knowledge_education_flow)
            self.record("后台管理统计与反馈", self.admin_management_flow)
            self.record("管理员知识库权限与维护", self.admin_knowledge_flow)
        finally:
            self.cleanup()
        return self.build_report()

    def build_report(self):
        total = len(self.cases)
        failed = len([case for case in self.cases if case["status"] != "passed"])
        passed = total - failed
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": total,
            "passed": passed,
            "failed": failed,
            "status": "passed" if failed == 0 else "failed",
            "cases": self.cases,
            "note": "覆盖健康检查、认证、患者档案、处方导出、训练打卡、管理员知识库维护等后端主流程。",
        }

    def health(self):
        response = self.client.get("/health")
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "ok"

        response = self.client.get("/ready")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["database"] == "ok"
        assert data["redis"]["status"] in ("disabled", "ok", "error")
        assert data["object_storage"]["status"] == "ok"

    def production_storage_config_flow(self):
        response = self.client.get("/api/deployment/info")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["database"] == "ok"
        assert "driver" in data["database_backend"]
        assert data["redis"]["status"] in ("disabled", "ok", "error")
        assert data["object_storage"]["backend"] in ("local", "minio")
        assert data["object_storage"]["status"] == "ok"

    def auth_flow(self):
        response = self.client.post("/api/register", json={
            "account": self.user_account,
            "password": "123456",
            "nickname": "自动测试用户",
        })
        assert response.status_code in (201, 409), response.text

        response = self.client.post("/api/register", json={
            "account": self.admin_account,
            "password": "123456",
            "nickname": "管理员",
        })
        assert response.status_code in (201, 409), response.text

        login = self.client.post("/api/login", json={
            "account": self.user_account,
            "password": "123456",
        })
        assert login.status_code == 200, login.text
        self.user_headers = {"Authorization": "Bearer " + login.json()["token"]}

        admin_login = self.client.post("/api/login", json={
            "account": self.admin_account,
            "password": "123456",
        })
        assert admin_login.status_code == 200, admin_login.text
        assert admin_login.json()["user"]["role"] == "admin"
        self.admin_headers = {"Authorization": "Bearer " + admin_login.json()["token"]}

        os.environ["DOCTOR_ACCOUNTS"] = self.doctor_account
        response = self.client.post("/api/register", json={
            "account": self.doctor_account,
            "password": "123456",
            "nickname": "协同医生",
        })
        assert response.status_code == 201, response.text
        assert response.json()["role"] == "doctor"
        doctor_login = self.client.post("/api/login", json={
            "account": self.doctor_account,
            "password": "123456",
        })
        assert doctor_login.status_code == 200, doctor_login.text
        self.doctor_headers = {"Authorization": "Bearer " + doctor_login.json()["token"]}

    def patient_profile_flow(self):
        response = self.client.post("/api/patient_profiles", headers=self.user_headers, json={
            "name": "自动测试患者",
            "age": 31,
            "pain_regions": ["腰部"],
            "history": "久坐后腰部酸痛",
        })
        assert response.status_code == 201, response.text
        self.created_profile_id = response.json()["id"]

        response = self.client.put(
            f"/api/patient_profiles/{self.created_profile_id}",
            headers=self.user_headers,
            json={"rehab_goal": "缓解疼痛并恢复日常活动"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["rehab_goal"] == "缓解疼痛并恢复日常活动"

    def prescription_export_flow(self):
        response = self.client.post("/api/generate_prescription", headers=self.user_headers, json={
            "patient_profile_id": self.created_profile_id,
            "symptoms": "腰部酸痛一月，久坐后加重",
            "mobility_score": 5,
        })
        assert response.status_code == 200, response.text
        self.created_prescription_id = response.json()["id"]

        for export_format in ("md", "txt", "json"):
            response = self.client.get(
                f"/api/prescriptions/{self.created_prescription_id}/export?format={export_format}",
                headers=self.user_headers,
            )
            assert response.status_code == 200, response.text
            assert "attachment" in response.headers.get("content-disposition", "")
        self.prescription_safety_flow()

    def prescription_safety_flow(self):
        response = self.client.post("/api/generate_prescription", headers=self.user_headers, json={
            "name": "安全校验测试",
            "age": 66,
            "symptoms": "膝关节疼痛伴明显肿胀，上下楼困难",
            "history": "严重关节炎，近期肿胀明显",
            "pain_regions": ["膝关节"],
            "mobility_score": 3,
        })
        assert response.status_code == 200, response.text
        data = response.json()
        safety = data["raw_response"]["safety"]
        assert safety["risk_level"] in ("medium", "high")
        assert safety["filtered_actions"], data
        assert any("明显肿胀" in (item.get("contraindications") or "") for item in safety["filtered_actions"])
        assert all((action["sets"] or 0) <= 2 for action in data["actions"])

    def imaging_report_flow(self):
        report_text = "MRI报告提示腰椎间盘突出，患者描述下肢麻木无力，建议结合临床就医评估。"
        encoded = base64.b64encode(report_text.encode("utf-8")).decode("ascii")
        response = self.client.post("/api/imaging_reports", headers=self.user_headers, json={
            "patient_profile_id": self.created_profile_id,
            "report_type": "MRI",
            "file_name": "lumbar_mri.txt",
            "file_content_base64": encoded,
            "note": "自动化测试报告",
        })
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["patient_profile_id"] == self.created_profile_id
        assert data["file_path"]
        assert data["ocr_status"] == "text_file_extracted"
        assert data["risk_level"] == "high"
        assert any(item["code"] == "numbness_or_weakness" for item in data["red_flags"])

        response = self.client.get(
            f"/api/imaging_reports?patient_profile_id={self.created_profile_id}",
            headers=self.user_headers,
        )
        assert response.status_code == 200, response.text
        assert any(item["id"] == data["id"] for item in response.json())

        response = self.client.get(f"/api/imaging_reports/{data['id']}", headers=self.user_headers)
        assert response.status_code == 200, response.text
        assert response.json()["id"] == data["id"]

    def red_flag_prescription_block(self):
        self.imaging_report_flow()
        response = self.client.post("/api/generate_prescription", headers=self.user_headers, json={
            "patient_profile_id": self.created_profile_id,
            "symptoms": "腰痛突然加重，伴下肢麻木无力和大小便异常",
            "mobility_score": 3,
        })
        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
        assert detail["code"] == "red_flag_detected"
        labels = {item["label"] for item in detail["red_flags"]}
        assert "麻木或无力" in labels
        assert "大小便异常" in labels

    def training_flow(self):
        response = self.client.post("/api/training_checkins", headers=self.user_headers, json={
            "prescription_id": self.created_prescription_id,
            "action_name": "骨盆后倾训练",
            "trained_on": "2026-06-18",
            "pain_before": 4,
            "pain_after": 2,
            "score": 88,
        })
        assert response.status_code == 201, response.text
        self.created_checkin_id = response.json()["id"]
        assert response.json()["patient_profile_id"] == self.created_profile_id

        response = self.client.get("/api/training_checkins/trends?days=7", headers=self.user_headers)
        assert response.status_code == 200, response.text
        assert len(response.json()["points"]) == 7

        response = self.client.get("/api/training_checkins/visualization?days=7", headers=self.user_headers)
        assert response.status_code == 200, response.text
        assert response.json()["total_checkins"] >= 1

    def pose_correction_flow(self):
        keypoints, visibility = self.sample_pose_keypoints()
        for action_id in ("calf_stretch", "ankle_pump", "neck_chin_tuck"):
            response = self.client.post("/api/correct_pose", json={
                "action_id": action_id,
                "keypoints": keypoints,
                "visibility": visibility,
                "timestamp": 1,
            })
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["status"] in ("ok", "warning")
            assert isinstance(data["score"], int)
            assert data["feedback"]
            assert data["voice_cue"]["text"]

    def sample_pose_keypoints(self):
        keypoints = [[0.5, 0.5, 0.0] for _ in range(33)]
        keypoints[0] = [0.50, 0.10, 0.0]
        keypoints[7] = [0.44, 0.14, 0.0]
        keypoints[8] = [0.56, 0.14, 0.0]
        keypoints[11] = [0.42, 0.25, 0.0]
        keypoints[12] = [0.58, 0.25, 0.0]
        keypoints[13] = [0.40, 0.38, 0.0]
        keypoints[14] = [0.60, 0.38, 0.0]
        keypoints[15] = [0.38, 0.52, 0.0]
        keypoints[16] = [0.62, 0.52, 0.0]
        keypoints[23] = [0.44, 0.52, 0.0]
        keypoints[24] = [0.56, 0.52, 0.0]
        keypoints[25] = [0.44, 0.74, 0.0]
        keypoints[26] = [0.56, 0.74, 0.0]
        keypoints[27] = [0.44, 0.94, 0.0]
        keypoints[28] = [0.56, 0.94, 0.0]
        keypoints[29] = [0.43, 0.96, 0.0]
        keypoints[30] = [0.57, 0.96, 0.0]
        keypoints[31] = [0.42, 0.86, 0.0]
        keypoints[32] = [0.58, 0.86, 0.0]
        visibility = [1.0 for _ in range(33)]
        return keypoints, visibility

    def pose_streaming_flow(self):
        keypoints, visibility = self.sample_pose_keypoints()
        response = self.client.get("/api/pose/status", headers=self.user_headers)
        assert response.status_code == 200, response.text
        assert response.json()["mode"] in ("onnx", "keypoint_passthrough")

        response = self.client.post("/api/pose/infer_frame", headers=self.user_headers, json={
            "action_id": "neck_chin_tuck",
            "frame_id": "frame-1",
            "keypoints": keypoints,
            "visibility": visibility,
            "timestamp": 1,
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["frame_id"] == "frame-1"
        assert data["provider"] == "keypoint_passthrough"
        assert data["feedback"]
        assert data["skeleton_3d"]["format"] == "kangjian_skeleton_v1"
        assert data["ar_overlay"]["format"] == "kangjian_ar_overlay_v1"

        response = self.client.post("/api/pose/infer_batch", headers=self.user_headers, json={
            "frames": [
                {
                    "action_id": "neck_chin_tuck",
                    "frame_id": "batch-1",
                    "keypoints": keypoints,
                    "visibility": visibility,
                },
                {
                    "action_id": "calf_stretch",
                    "frame_id": "batch-2",
                    "keypoints": keypoints,
                    "visibility": visibility,
                },
            ]
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["batch_size"] == 2
        assert len(data["results"]) == 2
        assert data["session_id"]

        with self.client.websocket_connect("/api/pose/ws") as websocket:
            session = websocket.receive_json()
            assert session["type"] == "session"
            websocket.send_json({
                "action_id": "neck_chin_tuck",
                "frame_id": "ws-1",
                "keypoints": keypoints,
                "visibility": visibility,
            })
            message = websocket.receive_json()
            assert message["type"] == "feedback"
            assert message["frame_id"] == "ws-1"
            assert message["voice_cue"]["text"]
            assert message["skeleton_3d"]["joints"]
            assert message["ar_overlay"]["items"]
            websocket.send_json({"type": "close"})
            assert websocket.receive_json()["type"] == "closed"

    def visual_overlay_flow(self):
        keypoints, visibility = self.sample_pose_keypoints()
        response = self.client.get("/api/visual/skeleton/spec", headers=self.user_headers)
        assert response.status_code == 200, response.text
        spec = response.json()
        assert spec["landmark_format"] == "mediapipe_pose_33"
        assert len(spec["landmarks"]) == 33
        assert spec["bones"]

        response = self.client.post("/api/visual/skeleton/frame", headers=self.user_headers, json={
            "action_id": "neck_chin_tuck",
            "keypoints": keypoints,
            "visibility": visibility,
        })
        assert response.status_code == 200, response.text
        skeleton = response.json()["skeleton_3d"]
        assert skeleton["format"] == "kangjian_skeleton_v1"
        assert len(skeleton["joints"]) == 33
        assert skeleton["bones"]

        response = self.client.post("/api/visual/ar/overlay", headers=self.user_headers, json={
            "action_id": "neck_chin_tuck",
            "keypoints": keypoints,
            "visibility": visibility,
            "feedback": ["下巴回收还不够，请缓慢向后收。"],
            "status": "warning",
            "score": 72,
            "viewport_width": 720,
            "viewport_height": 1280,
            "mirror": True,
        })
        assert response.status_code == 200, response.text
        overlay = response.json()["ar_overlay"]
        assert overlay["format"] == "kangjian_ar_overlay_v1"
        assert overlay["viewport"]["mirror"] is True
        assert overlay["items"]

    def voice_and_fatigue_flow(self):
        response = self.client.post("/api/voice/cue", headers=self.user_headers, json={
            "feedback": ["动作幅度还不够，请缓慢抬高一点。"],
            "status": "warning",
            "score": 72,
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["enabled"] is True
        assert data["text"]
        assert data["ssml"]
        assert data["priority"] == "medium"

        response = self.client.post("/api/wearables/metrics", headers=self.user_headers, json={
            "patient_profile_id": self.created_profile_id,
            "training_checkin_id": self.created_checkin_id,
            "device_type": "test_band",
            "heart_rate": 156,
            "resting_heart_rate": 72,
            "hrv_ms": 22,
            "spo2": 96,
            "perceived_exertion": 8,
            "duration_minutes": 45,
        })
        assert response.status_code == 201, response.text
        metric = response.json()
        assert metric["fatigue_score"] >= 45
        assert metric["risk_level"] in ("medium", "high")
        assert metric["recommendation"]

        response = self.client.get("/api/wearables/fatigue/status", headers=self.user_headers)
        assert response.status_code == 200, response.text
        status = response.json()
        assert status["sample_count"] >= 1
        assert status["fatigue_score"] >= 0
        assert status["recommendation"]

        response = self.client.get("/api/wearables/metrics", headers=self.user_headers)
        assert response.status_code == 200, response.text
        assert any(item["id"] == metric["id"] for item in response.json())

    def doctor_collaboration_flow(self):
        response = self.client.post("/api/doctor_links", headers=self.user_headers, json={
            "doctor_account": self.doctor_account,
            "patient_profile_id": self.created_profile_id,
            "patient_note": "希望医生帮忙审核腰痛处方。",
        })
        assert response.status_code == 201, response.text
        link = response.json()
        assert link["status"] == "active"

        response = self.client.get("/api/doctor/patients", headers=self.doctor_headers)
        assert response.status_code == 200, response.text
        assert any(item["id"] == link["id"] for item in response.json())

        response = self.client.post(
            f"/api/prescriptions/{self.created_prescription_id}/reviews/share",
            headers=self.user_headers,
            json={"doctor_account": self.doctor_account, "patient_note": "训练后腰部偶有酸胀。"},
        )
        assert response.status_code == 201, response.text
        review = response.json()
        assert review["status"] == "pending"

        response = self.client.get("/api/doctor/reviews?status=pending", headers=self.doctor_headers)
        assert response.status_code == 200, response.text
        assert any(item["id"] == review["id"] for item in response.json())

        response = self.client.put(
            f"/api/doctor/reviews/{review['id']}",
            headers=self.doctor_headers,
            json={"status": "changes_requested", "doctor_note": "建议先降低训练量。", "risk_level": "medium"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "changes_requested"

        response = self.client.post(
            f"/api/doctor/reviews/{review['id']}/adjustments",
            headers=self.doctor_headers,
            json={
                "reason": "医生建议降低训练负荷并观察疼痛变化。",
                "summary": "医生调整版：降低前两项动作组数，保持无痛范围。",
                "action_changes": [
                    {"operation": "update", "name": "骨盆后倾训练", "sets": 2, "reps": 8, "note": "医生建议低强度执行。"}
                ],
            },
        )
        assert response.status_code == 201, response.text
        adjustment = response.json()
        assert adjustment["source"] == "doctor"
        assert adjustment["status"] == "proposed"

        response = self.client.post(
            f"/api/prescription_adjustments/{adjustment['id']}/decision",
            headers=self.user_headers,
            json={"decision": "apply"},
        )
        assert response.status_code == 200, response.text
        decided = response.json()
        assert decided["status"] == "applied"
        assert decided["created_prescription_id"]

        response = self.client.post(
            f"/api/prescriptions/{self.created_prescription_id}/adjustments/auto",
            headers=self.user_headers,
        )
        assert response.status_code == 201, response.text
        auto_adjustment = response.json()
        assert auto_adjustment["source"] == "system"
        assert auto_adjustment["adjusted_actions"]

    def progress_report_flow(self):
        response = self.client.get("/api/training_checkins/report?period=weekly", headers=self.user_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["period"] == "weekly"
        assert data["total_checkins"] >= 1
        assert data["completion_rate"] >= 0
        assert data["vas_summary"]
        assert data["recommendations"]
        assert data["trend"]["points"]

        response = self.client.get("/api/training_checkins/report/export?period=weekly&format=md", headers=self.user_headers)
        assert response.status_code == 200, response.text
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "康复进度报告" in response.text

    def knowledge_education_flow(self):
        response = self.client.get("/api/knowledge/rag/status", headers=self.user_headers)
        assert response.status_code == 200, response.text
        assert response.json()["provider"] in ("local", "chroma", "qdrant")

        response = self.client.post("/api/knowledge/rag/search", headers=self.user_headers, json={
            "query": "腰痛核心稳定训练",
            "body_regions": ["腰部"],
            "limit": 3,
        })
        assert response.status_code == 200, response.text
        assert response.json()["results"]

        response = self.client.get("/api/knowledge/articles?body_region=腰部", headers=self.user_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["items"]
        assert data["items"][0]["prevention_tips"]

        response = self.client.post("/api/knowledge/qa", headers=self.user_headers, json={
            "question": "腰痛久坐后加重应该做什么康复训练？",
            "pain_regions": ["腰部"],
            "limit": 3,
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert "腰部" in data["answer"]
        assert data["references"]
        assert data["rag_contexts"]
        assert data["suggested_actions"]
        assert data["safety_notes"]

    def admin_management_flow(self):
        response = self.client.get("/api/admin/dashboard", headers=self.user_headers)
        assert response.status_code == 403, response.text

        response = self.client.post("/api/feedback", headers=self.user_headers, json={
            "category": "功能建议",
            "rating": 5,
            "content": "希望后台可以查看用户统计和处理反馈。",
            "source": "backend_smoke_test",
        })
        assert response.status_code == 201, response.text
        self.created_feedback_id = response.json()["id"]
        assert response.json()["status"] == "open"

        response = self.client.get("/api/admin/dashboard", headers=self.admin_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["totals"]["users"] >= 1
        assert data["totals"]["actions"] >= 1
        assert data["feedback_summary"]["open_count"] >= 1

        response = self.client.get("/api/admin/users", headers=self.admin_headers)
        assert response.status_code == 200, response.text
        assert any(item["account"] == self.user_account for item in response.json())

        response = self.client.get("/api/admin/feedback?status=open", headers=self.admin_headers)
        assert response.status_code == 200, response.text
        assert any(item["id"] == self.created_feedback_id for item in response.json())

        response = self.client.put(
            f"/api/admin/feedback/{self.created_feedback_id}",
            headers=self.admin_headers,
            json={"status": "resolved", "admin_note": "已记录"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "resolved"
        assert response.json()["admin_note"] == "已记录"

    def admin_knowledge_flow(self):
        response = self.client.get("/api/admin/actions", headers=self.user_headers)
        assert response.status_code == 403, response.text

        response = self.client.post("/api/knowledge/rag/reindex", headers=self.user_headers)
        assert response.status_code == 403, response.text

        response = self.client.post("/api/knowledge/rag/reindex", headers=self.admin_headers)
        assert response.status_code == 200, response.text
        assert response.json()["indexed_documents"] >= 1

        response = self.client.get("/api/admin/actions/meta", headers=self.admin_headers)
        assert response.status_code == 200, response.text
        meta = response.json()
        assert "body_regions" in meta
        assert "categories" in meta
        assert "difficulty_levels" in meta

        response = self.client.get("/api/actions")
        assert response.status_code == 200, response.text
        first_action = response.json()[0]
        assert first_action["category"]
        assert first_action["difficulty_level"] in ("初级", "中级", "高级")
        assert first_action["demo_media"]["image"]
        assert first_action["steps"]
        assert first_action["common_mistakes"]

        action_id = f"tmp_autotest_action_{self.unique}"
        response = self.client.post("/api/admin/actions", headers=self.admin_headers, json={
            "id": action_id,
            "name": "自动测试动作",
            "sets": 2,
            "reps": 8,
            "category": "活动度训练",
            "difficulty_level": "初级",
            "stage": "活动度恢复期",
            "target_muscles": ["腹横肌"],
            "equipment": ["徒手"],
            "steps": ["准备姿势", "缓慢完成动作", "回到起始位置"],
            "common_mistakes": ["速度过快"],
            "correct_cues": ["保持呼吸"],
            "risk_level": "低",
            "demo_media": {"image": "assets/actions/exercise_generic.svg", "video": ""},
            "frequency": "每日1次",
            "description": "自动测试后删除",
            "body_regions": ["腰部"],
            "target_conditions": ["测试"],
        })
        assert response.status_code == 201, response.text
        assert response.json()["category"] == "活动度训练"
        assert response.json()["demo_media"]["image"] == "assets/actions/exercise_generic.svg"

        response = self.client.put(f"/api/admin/actions/{action_id}", headers=self.admin_headers, json={"reps": 10})
        assert response.status_code == 200, response.text
        assert response.json()["reps"] == 10

        response = self.client.delete(f"/api/admin/actions/{action_id}", headers=self.admin_headers)
        assert response.status_code == 200, response.text

    def cleanup(self):
        if self.created_checkin_id:
            self.client.delete(f"/api/training_checkins/{self.created_checkin_id}", headers=self.user_headers)
        if self.created_profile_id:
            self.client.delete(f"/api/patient_profiles/{self.created_profile_id}", headers=self.user_headers)
        self.actions_path.write_text(self.original_actions, encoding="utf-8")


def main():
    suite = BackendSmokeSuite()
    report = suite.run()
    write_report(report)
    print(f"backend tests {report['status']}: {report['passed']}/{report['total']} passed")
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
