# 后端任务清单：报告上传 LLM 分析

> **面向**：后端开发  
> **前端状态**：报告上传 UI 已完成，并已对接以下字段的展示逻辑（后端尚未全部实现）。  
> **优先级**：P0 替换关键词校验；P1 返回 `summary`；P2 处方生成联动。

---

## 1. 背景

当前 `POST /api/imaging_reports` 流程：

1. 从 txt/md/pdf/docx 提取文字（`extract_text_report_content`）
2. 用 **关键词规则** 校验是否为医学报告（`validate_imaging_report_content`）
3. 用 **正则规则** 检测红旗（`detect_red_flags`）

**问题**：无关 PDF/文本仍可能被误判为「低危医学报告」。产品决策是改为 **DeepSeek LLM 语义分析**，关键词校验仅作兜底或删除。

相关代码位置：

| 模块 | 文件 |
|------|------|
| 上传 API | `backend/app/api.py` → `create_imaging_report_api` |
| 关键词校验 | `backend/app/validators.py` → `validate_imaging_report_content` |
| 红旗正则 | `backend/app/validators.py` → `detect_red_flags` |
| LLM 封装 | `backend/app/doubao.py` → `generate_with_http` / `generate_summary` |
| 数据模型 | `backend/app/models.py` → `ImagingReportModel` |
| 响应 Schema | `backend/app/schema.py` → `ImagingReportResponse` |
| 集成测试 | `backend/run_backend_tests.py` → `imaging_report_flow` |

---

## 2. 前端已对接的期望行为

前端（`frontend/pages/profiles.js`、`frontend/shared/imaging.js`）已实现：

- 上传超时 **35 秒**（`IMAGING_UPLOAD_TIMEOUT_MS`），LLM 分析需在此时间内完成或异步化
- 客户端 **5MB** 大小校验（后端已有同等限制）
- 上传中按钮禁用 + 文案「正在上传并分析报告，请稍候…」
- **400 错误**：展示 `detail` 字符串（期望 LLM 拒绝时返回可读 `reject_reason`）
- 列表卡片展示：
  - `ocr_status` → 中文标签（含 `llm_analyzed`、`pending_llm_review`）
  - `risk_level` → 低/中/高/待确认
  - **`summary` 优先于 `ocr_text`** 作为「分析摘要」
  - `reject_reason` / `analysis_note`（拒绝原因）
  - `red_flags` 列表 + 高危弹窗

---

## 3. 任务清单

### P0 — LLM 分析核心

- [ ] **3.1** 新增 `analyze_imaging_report(text: str, report_type: str | None) -> dict`  
  建议放在 `backend/app/doubao.py` 或新建 `backend/app/imaging_analysis.py`。

- [ ] **3.2** 调用 DeepSeek（复用 `generate_with_http`），要求模型 **只输出 JSON**，字段见 §4。

- [ ] **3.3** 在 `create_imaging_report_api` 中：
  - 有 `ocr_text`（含 pdf/docx 提取结果）时 → 调用 `analyze_imaging_report`
  - `is_medical_report == false` → **HTTP 400**，`detail` 为 `reject_reason`
  - `is_medical_report == true` → 写入 DB，设置 `ocr_status = "llm_analyzed"`

- [ ] **3.4** 移除或大幅弱化 `validate_imaging_report_content` 的关键词拦截；至少不再作为唯一判据。

- [ ] **3.5** LLM 返回的 `red_flags` 与 `risk_level` 优先于纯 `detect_red_flags` 正则结果；可合并两者（取并集，risk 取最高）。

### P1 — 数据模型与 API 字段

- [ ] **3.6** DB 迁移：`imaging_reports` 表增加字段（至少）：
  - `summary` TEXT NULL — LLM 生成的 1–3 句摘要
  - 可选：`analysis_status` VARCHAR(32) — `completed` / `failed` / `pending`
  - 可选：`reject_reason` TEXT — 仅拒绝场景也可只通过 400 返回不落库

- [ ] **3.7** 扩展 `ImagingReportResponse`：
  ```python
  summary: Optional[str] = None
  reject_reason: Optional[str] = None   # 可选，成功响应一般为 null
  analysis_status: Optional[str] = None
  confidence: Optional[float] = None    # 可选，0–1
  ```

- [ ] **3.8** 更新 `imaging_report_response()` 与 `create_imaging_report()` 写入/读出上述字段。

### P1 — 异常与降级

- [ ] **3.9** DeepSeek 超时/报错时的降级策略（二选一，需产品确认）：
  - **方案 A（推荐）**：仍保存文件与 `ocr_text`，`ocr_status = "pending_llm_review"`，`risk_level = "unknown"`，HTTP 201
  - **方案 B**：HTTP 503，提示稍后重试  
  前端已识别 `pending_llm_review` 与 `unknown`。

- [ ] **3.10** 纯图片上传（无 OCR 文字）：保持 `ocr_status = "pending_external_ocr"`，不调用 LLM；或后续接 OCR 再分析。

### P2 — 处方联动（可选）

- [ ] **3.11** 在 `POST /api/generate_prescription` 中读取该患者 **最新一份** `llm_analyzed` 报告：
  - `risk_level == "high"` → 与主诉红旗类似，返回 400 + `red_flag_detected`（或新 code `imaging_risk_high`）
  - 或将 `summary` 注入 LLM 处方 prompt 作为补充上下文（不阻断）

### P3 — 测试

- [ ] **3.12** 更新 `run_backend_tests.py` → `imaging_report_flow`：
  - 断言 `summary` 非空（或 mock LLM）
  - 断言 `ocr_status == "llm_analyzed"`
- [ ] **3.13** 新增 **拒绝样例**（中性内容，勿用敏感政治文本）：
  - 食谱 / 新闻摘要类 txt → 期望 400 + 明确 reject 文案
- [ ] **3.14** 保留现有 MRI 样例：`lumbar_mri.txt` 仍应 `risk_level == "high"` 且含麻木类红旗

---

## 4. LLM 输出 JSON 契约

Prompt 应明确要求模型返回如下结构（字段名固定，便于 `_extract_json_object` 解析）：

```json
{
  "is_medical_report": true,
  "summary": "MRI 提示 L4-L5 椎间盘膨出，伴轻度神经根受压。",
  "red_flags": [
    { "code": "numbness_or_weakness", "label": "下肢麻木或无力", "evidence": "原文片段" }
  ],
  "risk_level": "high",
  "reject_reason": null,
  "confidence": 0.92
}
```

拒绝非医学内容示例：

```json
{
  "is_medical_report": false,
  "summary": null,
  "red_flags": [],
  "risk_level": "unknown",
  "reject_reason": "内容不符合医学检查报告特征，请上传 MRI/X光/CT 报告或粘贴诊断结论。",
  "confidence": 0.88
}
```

**`risk_level` 枚举**：`low` | `medium` | `high` | `unknown`（与前端 `IMAGING_RISK_LABELS` 一致）

**`ocr_status` 枚举**（前端已映射）：

| 值 | 含义 |
|----|------|
| `provided` | 用户手动粘贴 |
| `text_file_extracted` | 仅文件提取、尚未 LLM（过渡态，LLM 上线后应少见） |
| `llm_analyzed` | LLM 分析完成 |
| `pending_llm_review` | LLM 失败，待人工/重试 |
| `pending_external_ocr` | 图片存档，无文字 |
| `rejected` | 可选，用于历史记录 |

---

## 5. 建议实现步骤

```
1. 编写 analyze_imaging_report + 单元测试（mock DeepSeek）
2. 数据库 migration 增加 summary 等字段
3. 改 create_imaging_report_api 流程
4. 调整 imaging_report_flow 集成测试
5. （可选）generate_prescription 读取最新报告
```

### 5.1 Prompt 要点

- 角色：医学影像/检查报告解读助手，**保守、安全优先**
- 输入：`report_type` + 截断后的报告正文（建议 ≤ 8000 字符）
- 输出：仅 JSON，不要 markdown 包裹（或确保 `_extract_json_object` 可解析）
- 红旗定义与现有 `_RED_FLAG_RULES` 对齐，便于 code 统一
- 非医学内容：明确 `is_medical_report: false`，给出用户可操作的 `reject_reason`

### 5.2 性能

- 前端超时 35s；`generate_with_http(..., timeout=28)` 留余量
- 若经常超时，考虑：异步任务 + 轮询，或上传先 201 再后台分析（需新增 PATCH/GET 状态接口）

---

## 6. 现有 API 不变部分

**请求** `POST /api/imaging_reports`（`ImagingReportCreateRequest`）：

```json
{
  "patient_profile_id": 1,
  "report_type": "MRI报告",
  "file_name": "report.pdf",
  "file_content_base64": "...",
  "ocr_text": "可选，优先于文件提取",
  "note": "可选备注"
}
```

**成功响应** 仍为 `ImagingReportResponse`，在现有字段基础上 **增加** `summary` 等，勿破坏已有字段。

---

## 7. 环境依赖

`.env` 中需配置（已有处方 LLM 同款）：

```
DeepSeek_API_KEY=...
DeepSeek_MODEL_ID=...
DeepSeek_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

文件解析依赖（已加入 `requirements.txt`）：`pypdf`、`python-docx`

---

## 8. 验收标准

1. 上传真实 MRI 文字报告 → 201，`summary` 有内容，`ocr_status=llm_analyzed`，红旗与风险合理  
2. 上传明显非医学 txt（如食谱）→ 400，前端展示 reject 文案  
3. 上传 png 无文字 → 201，`pending_external_ocr`，不误报低危  
4. DeepSeek 不可用时 → 按 §3.9 降级策略行为一致  
5. `python run_backend_tests.py` 全部通过  

---

## 9. 联系人 / 备注

- 前端配置：`frontend/config.js`（超时、文件类型）  
- 前端展示逻辑：`frontend/shared/imaging.js`  
- **请勿在测试数据中使用敏感政治内容**  
- 关键词校验文件 `validators.py` 中 `_NON_MEDICAL_REPORT_HINTS` 可在 LLM 稳定后删除
