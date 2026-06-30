export const IMAGING_OCR_STATUS_LABELS = {
  provided: "手动粘贴",
  text_file_extracted: "文件文字已提取",
  pending_external_ocr: "图片已存档，待识别",
  llm_analyzed: "模型已分析",
  pending_llm_review: "待模型分析",
  rejected: "未通过校验",
};

export const IMAGING_RISK_LABELS = {
  low: "低",
  medium: "中",
  high: "高",
  unknown: "待确认",
};

export function formatImagingOcrStatus(status) {
  return IMAGING_OCR_STATUS_LABELS[status] || status || "—";
}

export function formatImagingRiskLevel(level) {
  return IMAGING_RISK_LABELS[level] || level || "—";
}

export function imagingReportPreview(report) {
  const summary = String(report?.summary || "").trim();
  if (summary) return summary;
  return String(report?.ocr_text || "").trim();
}

export function imagingRiskClass(level) {
  if (level === "high") return "risk-high";
  if (level === "unknown") return "risk-unknown";
  if (level === "medium") return "risk-medium";
  return "";
}

export function imagingUploadSuccessMessage(report) {
  if (report?.risk_level === "high") {
    return "报告已上传，检测到需关注的风险信号";
  }
  if (report?.ocr_status === "pending_external_ocr" || report?.ocr_status === "pending_llm_review") {
    return "报告已存档，待进一步分析";
  }
  if (report?.summary) {
    return "报告已上传并完成分析";
  }
  return "报告已上传";
}
