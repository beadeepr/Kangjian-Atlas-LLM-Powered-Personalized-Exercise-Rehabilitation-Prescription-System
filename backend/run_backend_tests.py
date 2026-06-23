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
            self.record("用户注册与登录", self.auth_flow)
            self.record("患者档案 CRUD", self.patient_profile_flow)
            self.record("红旗症状处方拦截", self.red_flag_prescription_block)
            self.record("处方生成与导出", self.prescription_export_flow)
            self.record("训练打卡与趋势统计", self.training_flow)
            self.record("实时动作纠正接口", self.pose_correction_flow)
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
