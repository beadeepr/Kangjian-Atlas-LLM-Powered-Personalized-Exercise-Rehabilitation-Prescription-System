from __future__ import annotations

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
            self.record("处方生成与导出", self.prescription_export_flow)
            self.record("训练打卡与趋势统计", self.training_flow)
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

    def training_flow(self):
        response = self.client.post("/api/training_checkins", headers=self.user_headers, json={
            "prescription_id": self.created_prescription_id,
            "action_name": "骨盆后倾训练",
            "trained_on": "2026-06-18",
            "duration_minutes": 10,
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

    def admin_knowledge_flow(self):
        response = self.client.get("/api/admin/actions", headers=self.user_headers)
        assert response.status_code == 403, response.text

        response = self.client.get("/api/admin/actions/meta", headers=self.admin_headers)
        assert response.status_code == 200, response.text
        assert "body_regions" in response.json()

        action_id = f"tmp_autotest_action_{self.unique}"
        response = self.client.post("/api/admin/actions", headers=self.admin_headers, json={
            "id": action_id,
            "name": "自动测试动作",
            "sets": 2,
            "reps": 8,
            "frequency": "每日1次",
            "description": "自动测试后删除",
            "body_regions": ["腰部"],
            "target_conditions": ["测试"],
        })
        assert response.status_code == 201, response.text

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
