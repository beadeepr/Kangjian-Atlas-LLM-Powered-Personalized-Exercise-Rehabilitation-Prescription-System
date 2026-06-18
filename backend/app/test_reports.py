import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = BASE_DIR / "reports"
REPORT_JSON = REPORT_DIR / "backend_test_report.json"
REPORT_MD = REPORT_DIR / "backend_test_report.md"


def load_latest_report() -> dict[str, Any] | None:
    if not REPORT_JSON.exists():
        return None
    try:
        return json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_report(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(render_markdown_report(report), encoding="utf-8")


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# 后端自动化测试报告",
        "",
        f"- 测试时间：{report.get('generated_at')}",
        f"- 总用例数：{report.get('total')}",
        f"- 通过：{report.get('passed')}",
        f"- 失败：{report.get('failed')}",
        f"- 状态：{report.get('status')}",
        "",
        "## 用例明细",
        "",
        "| 用例 | 状态 | 说明 |",
        "|------|------|------|",
    ]
    for item in report.get("cases", []):
        lines.append(f"| {item.get('name')} | {item.get('status')} | {item.get('detail', '')} |")
    lines.extend([
        "",
        "## 备注",
        "",
        report.get("note") or "本报告由后端自动化测试脚本生成。",
        "",
    ])
    return "\n".join(lines)
