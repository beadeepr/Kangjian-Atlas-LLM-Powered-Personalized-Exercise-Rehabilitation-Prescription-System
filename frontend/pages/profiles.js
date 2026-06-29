// Patient profiles + imaging reports page module.
//
// Extracted from app.js. Owns: profile form, profile list, profile select
// (used by intake), imaging report upload/list/delete, and page event
// binding. App-level helpers injected via `ctx`.
//
// ctx shape:
//   state, els,
//   fetchWithTimeout(url, opts, timeoutMs), authHeaders(extra),
//   parseApiError(response),
//   escapeAdminText,
//   isSessionReady, requireLogin, requireApi, apiEnabled,
//   showToast, showErrorToast, renderDemoNotice, renderLoadError,
//   setLoading(active, text),
//   showRedFlagAlert(message, redFlags),
//   updateMobilityGuide(),
//   goToStep(step)

export function createProfilesPage(ctx) {
  const {
    state,
    els,
    fetchWithTimeout,
    authHeaders,
    parseApiError,
    escapeAdminText,
    isSessionReady,
    requireLogin,
    requireApi,
    apiEnabled,
    showToast,
    showErrorToast,
    renderDemoNotice,
    renderLoadError,
    setLoading,
    showRedFlagAlert,
    updateMobilityGuide,
    goToStep,
  } = ctx;

  function applyPatientProfileToIntake(profile) {
    if (!profile) return;
    const historyField = document.getElementById("history");
    if (historyField && profile.history) historyField.value = profile.history;
    state.selectedPainRegions.clear();
    (profile.pain_regions || []).forEach((region) => state.selectedPainRegions.add(region));
    els.painRegions?.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("selected", state.selectedPainRegions.has(chip.textContent));
    });
    updateMobilityGuide();
  }

  function readProfileFormPayload() {
    return {
      name: document.getElementById("profile-name")?.value.trim() || "",
      gender: document.getElementById("profile-gender")?.value || null,
      age: document.getElementById("profile-age")?.value ? Number(document.getElementById("profile-age").value) : null,
      phone: document.getElementById("profile-phone")?.value.trim() || null,
      height_cm: document.getElementById("profile-height")?.value ? Number(document.getElementById("profile-height").value) : null,
      weight_kg: document.getElementById("profile-weight")?.value ? Number(document.getElementById("profile-weight").value) : null,
      pain_regions: Array.from(state.profileFormRegions),
      history: document.getElementById("profile-history")?.value.trim() || null,
      surgery_history: document.getElementById("profile-surgery")?.value.trim() || null,
      allergy_history: document.getElementById("profile-allergy")?.value.trim() || null,
      rehab_goal: document.getElementById("profile-goal")?.value.trim() || null,
      note: document.getElementById("profile-note")?.value.trim() || null,
    };
  }

  function resetProfileForm() {
    state.profileFormRegions.clear();
    document.getElementById("profile-edit-id").value = "";
    document.getElementById("profile-form-title").textContent = "新建健康档案";
    els.profileForm?.reset();
    els.profilePainRegions?.querySelectorAll(".chip").forEach((chip) => chip.classList.remove("selected"));
    if (els.profileFormCard) els.profileFormCard.hidden = true;
  }

  function fillProfileForm(profile) {
    document.getElementById("profile-edit-id").value = profile.id;
    document.getElementById("profile-form-title").textContent = `编辑档案：${profile.name}`;
    document.getElementById("profile-name").value = profile.name || "";
    document.getElementById("profile-gender").value = profile.gender || "";
    document.getElementById("profile-age").value = profile.age ?? "";
    document.getElementById("profile-phone").value = profile.phone || "";
    document.getElementById("profile-height").value = profile.height_cm ?? "";
    document.getElementById("profile-weight").value = profile.weight_kg ?? "";
    document.getElementById("profile-history").value = profile.history || "";
    document.getElementById("profile-surgery").value = profile.surgery_history || "";
    document.getElementById("profile-allergy").value = profile.allergy_history || "";
    document.getElementById("profile-goal").value = profile.rehab_goal || "";
    document.getElementById("profile-note").value = profile.note || "";
    state.profileFormRegions = new Set(profile.pain_regions || []);
    els.profilePainRegions?.querySelectorAll(".chip").forEach((chip) => {
      chip.classList.toggle("selected", state.profileFormRegions.has(chip.textContent));
    });
    if (els.profileFormCard) els.profileFormCard.hidden = false;
  }

  function renderProfileCard(profile) {
    const regions = (profile.pain_regions || []).join("、") || "未填写";
    return `
      <article class="profile-card" data-profile-id="${profile.id}">
        <div class="profile-card-head">
          <div>
            <h3>${escapeAdminText(profile.name)}${profile.age ? ` · ${profile.age}岁` : ""}</h3>
            <p class="hint">${escapeAdminText(profile.gender || "性别未填")}${profile.phone ? ` · ${escapeAdminText(profile.phone)}` : ""}</p>
          </div>
          <div class="profile-card-actions">
            <button class="btn btn-secondary btn-small profile-use-btn" type="button" data-profile-id="${profile.id}">用于问诊</button>
            <button class="btn btn-secondary btn-small profile-edit-btn" type="button" data-profile-id="${profile.id}">编辑</button>
            <button class="btn btn-secondary btn-small profile-delete-btn" type="button" data-profile-id="${profile.id}">删除</button>
          </div>
        </div>
        <div class="profile-meta-grid">
          <span>疼痛部位：${escapeAdminText(regions)}</span>
          <span>伤病史：${escapeAdminText(profile.history || "无")}</span>
          <span>手术史：${escapeAdminText(profile.surgery_history || "无")}</span>
          <span>过敏史：${escapeAdminText(profile.allergy_history || "无")}</span>
        </div>
        ${profile.rehab_goal ? `<p class="hint" style="margin-top:8px">康复目标：${escapeAdminText(profile.rehab_goal)}</p>` : ""}
      </article>`;
  }

  async function loadProfilesPage() {
    if (!els.profilesList) return;
    if (window.APP_CONFIG.DEMO_MODE) {
      renderDemoNotice(els.profilesList, { featureName: "健康档案" });
      return;
    }
    if (!isSessionReady()) {
      els.profilesList.innerHTML = "<p class=\"hint\">请先登录后查看健康档案。</p>";
      return;
    }
    els.profilesList.innerHTML = "<p class=\"hint\">正在加载…</p>";
    try {
      const response = await fetchWithTimeout(
        `${window.APP_CONFIG.API_BASE}/patient_profiles`,
        { headers: authHeaders() },
        window.APP_CONFIG.LIST_TIMEOUT_MS
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.patientProfiles = await response.json();
      renderPatientProfileSelect();
      if (!state.patientProfiles.length) {
        els.profilesList.innerHTML = "<p class=\"hint\">暂无健康档案，可点击「新建档案」添加。</p>";
        return;
      }
      els.profilesList.innerHTML = state.patientProfiles.map(renderProfileCard).join("");
    } catch {
      renderLoadError(els.profilesList, {
        message: "健康档案加载失败，请确认后端已启动后重试。",
        onRetry: loadProfilesPage,
      });
    }
  }

  async function saveProfileForm(event) {
    event.preventDefault();
    if (!requireLogin()) return;
    const payload = readProfileFormPayload();
    if (!payload.name) {
      showToast("请填写姓名");
      return;
    }
    const editId = document.getElementById("profile-edit-id")?.value;
    const url = editId
      ? `${window.APP_CONFIG.API_BASE}/patient_profiles/${editId}`
      : `${window.APP_CONFIG.API_BASE}/patient_profiles`;
    const response = await fetchWithTimeout(
      url,
      {
        method: editId ? "PUT" : "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      },
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (!response.ok) {
      showErrorToast("档案保存失败");
      return;
    }
    const profile = await response.json();
    showToast(editId ? "档案已更新" : "档案已创建");
    resetProfileForm();
    await loadPatientProfiles();
    await loadProfilesPage();
    if (!editId) {
      state.selectedPatientProfileId = profile.id;
      renderPatientProfileSelect();
    }
  }

  async function deleteProfile(profileId) {
    if (!window.confirm("确定删除该健康档案？")) return;
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/patient_profiles/${profileId}`,
      { method: "DELETE", headers: authHeaders() },
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (!response.ok) {
      showErrorToast("删除失败");
      return;
    }
    if (state.selectedPatientProfileId === profileId) state.selectedPatientProfileId = null;
    showToast("档案已删除");
    await loadPatientProfiles();
    await loadProfilesPage();
  }

  function renderImagingReportCard(report) {
    const riskClass = report.risk_level === "high" ? "risk-high" : "";
    const ocrText = report.ocr_text || "";
    const uniqueFlags = (report.red_flags || []).filter((item, index, list) => {
      const label = item.label || "";
      if (!label) return false;
      if (ocrText.includes(label)) return false;
      return list.findIndex((other) => other.label === label) === index;
    });
    const flags = uniqueFlags
      .map((item) => `<li>${escapeAdminText(item.label || item.code)}</li>`)
      .join("");
    const createdAt = report.created_at
      ? escapeAdminText(String(report.created_at).slice(0, 19).replace("T", " "))
      : "";
    return `
      <article class="imaging-report-card ${riskClass}" data-report-id="${report.id}">
        <div class="imaging-report-head">
          <div>
            <strong>${escapeAdminText(report.report_type || "影像报告")}</strong>
            ${report.file_name ? ` · ${escapeAdminText(report.file_name)}` : ""}
            ${createdAt ? `<span class="hint"> · ${createdAt}</span>` : ""}
          </div>
          <button class="btn btn-secondary btn-small imaging-delete-btn" type="button" data-report-id="${report.id}">删除</button>
        </div>
        <p class="hint">OCR：${escapeAdminText(report.ocr_status)} · 风险：${escapeAdminText(report.risk_level)}</p>
        ${ocrText ? `<p class="imaging-ocr-text">${escapeAdminText(ocrText.slice(0, 220))}${ocrText.length > 220 ? "…" : ""}</p>` : ""}
        ${flags ? `<ul class="red-flag-list imaging-flag-list">${flags}</ul>` : ""}
      </article>`;
  }

  async function deleteImagingReport(reportId) {
    if (!requireApi()) return;
    if (!window.confirm("确定删除该影像报告记录？")) return;
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/imaging_reports/${reportId}`,
      { method: "DELETE", headers: authHeaders() },
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (!response.ok) {
      showErrorToast("删除失败");
      return;
    }
    showToast("影像报告已删除");
    await loadImagingReports();
  }

  function bindImagingReportEvents() {
    if (els.imagingReportsList?.dataset.bound === "true") return;
    if (els.imagingReportsList) els.imagingReportsList.dataset.bound = "true";
    els.imagingReportsList?.addEventListener("click", async (event) => {
      const button = event.target.closest(".imaging-delete-btn");
      if (!button) return;
      await deleteImagingReport(Number(button.dataset.reportId));
    });
  }

  async function loadImagingReports() {
    if (!els.imagingReportsList || !isSessionReady() || window.APP_CONFIG.DEMO_MODE) return;
    try {
      const params = state.selectedPatientProfileId
        ? `?patient_profile_id=${state.selectedPatientProfileId}`
        : "";
      const response = await fetchWithTimeout(
        `${window.APP_CONFIG.API_BASE}/imaging_reports${params}`,
        { headers: authHeaders() },
        window.APP_CONFIG.LIST_TIMEOUT_MS
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const reports = await response.json();
      const seen = new Set();
      state.imagingReports = reports.filter((report) => {
        if (seen.has(report.id)) return false;
        seen.add(report.id);
        return true;
      });
      if (!state.imagingReports.length) {
        els.imagingReportsList.innerHTML = "<p class=\"hint\">暂无影像报告记录。</p>";
        return;
      }
      els.imagingReportsList.innerHTML = state.imagingReports.map(renderImagingReportCard).join("");
    } catch {
      renderLoadError(els.imagingReportsList, {
        message: "影像报告加载失败，请确认后端已启动后重试。",
        onRetry: loadImagingReports,
      });
    }
  }

  async function uploadImagingReport() {
    if (!requireApi()) return;
    const fileInput = document.getElementById("imaging-file");
    const ocrText = document.getElementById("imaging-ocr-text")?.value.trim();
    const note = document.getElementById("imaging-note")?.value.trim();
    const reportType = document.getElementById("imaging-report-type")?.value || "影像报告";
    const file = fileInput?.files?.[0];

    if (!file && !ocrText) {
      showToast("请上传文本报告或粘贴报告内容");
      return;
    }

    const payload = {
      patient_profile_id: state.selectedPatientProfileId,
      report_type: reportType,
      note: note || null,
      ocr_text: ocrText || null,
    };

    if (file) {
      const buffer = await file.arrayBuffer();
      const bytes = new Uint8Array(buffer);
      let binary = "";
      bytes.forEach((byte) => {
        binary += String.fromCharCode(byte);
      });
      payload.file_name = file.name;
      payload.file_content_base64 = btoa(binary);
      if (!ocrText && /\.(txt|md)$/i.test(file.name)) {
        payload.ocr_text = await file.text();
      }
    }

    setLoading(true, "正在上传并分析影像报告…");
    try {
      const response = await fetchWithTimeout(
        `${window.APP_CONFIG.API_BASE}/imaging_reports`,
        {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(payload),
        },
        window.APP_CONFIG.LIST_TIMEOUT_MS
      );
      if (!response.ok) {
        const detail = await parseApiError(response);
        showErrorToast(detail || "上传失败");
        return;
      }
      const report = await response.json();
      if (report.red_flags?.length) {
        showRedFlagAlert("影像报告检测到红旗症状，建议尽快就医评估。", report.red_flags);
      }
      showToast("影像报告已上传");
      if (fileInput) fileInput.value = "";
      document.getElementById("imaging-ocr-text").value = "";
      document.getElementById("imaging-note").value = "";
      await loadImagingReports();
    } catch {
      showErrorToast("影像报告上传失败");
    } finally {
      setLoading(false);
    }
  }

  function initProfilePainRegions() {
    if (!els.profilePainRegions) return;
    window.PAIN_REGIONS.forEach((region) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chip";
      button.textContent = region;
      button.addEventListener("click", () => {
        if (state.profileFormRegions.has(region)) {
          state.profileFormRegions.delete(region);
          button.classList.remove("selected");
        } else {
          state.profileFormRegions.add(region);
          button.classList.add("selected");
        }
      });
      els.profilePainRegions.appendChild(button);
    });
  }

  function bindProfilesPageEvents() {
    if (els.profilesList?.dataset.bound === "true") return;
    if (els.profilesList) els.profilesList.dataset.bound = "true";

    els.profilesList?.addEventListener("click", async (event) => {
      const useBtn = event.target.closest(".profile-use-btn");
      if (useBtn) {
        const profile = state.patientProfiles.find((item) => item.id === Number(useBtn.dataset.profileId));
        if (profile) {
          state.selectedPatientProfileId = profile.id;
          renderPatientProfileSelect();
          applyPatientProfileToIntake(profile);
          goToStep("intake");
          showToast(`已关联档案：${profile.name}`);
        }
        return;
      }
      const editBtn = event.target.closest(".profile-edit-btn");
      if (editBtn) {
        const profile = state.patientProfiles.find((item) => item.id === Number(editBtn.dataset.profileId));
        if (profile) fillProfileForm(profile);
        return;
      }
      const deleteBtn = event.target.closest(".profile-delete-btn");
      if (deleteBtn) {
        await deleteProfile(Number(deleteBtn.dataset.profileId));
      }
    });
  }

  async function loadPatientProfiles() {
    if (!apiEnabled() || !els.patientProfileSelect) return;
    try {
      const response = await fetchWithTimeout(
        `${window.APP_CONFIG.API_BASE}/patient_profiles`,
        { headers: authHeaders() },
        window.APP_CONFIG.LIST_TIMEOUT_MS
      );
      if (!response.ok) return;
      state.patientProfiles = await response.json();
      renderPatientProfileSelect();
    } catch {
      // 患者档案为可选能力，加载失败不阻断问诊
    }
  }

  function renderPatientProfileSelect() {
    if (!els.patientProfileSelect) return;
    const options = [
      `<option value="">不关联患者档案（使用当前账号信息）</option>`,
      ...state.patientProfiles.map(
        (profile) =>
          `<option value="${profile.id}"${state.selectedPatientProfileId === profile.id ? " selected" : ""}>${profile.name}${profile.age ? ` · ${profile.age}岁` : ""}</option>`
      ),
    ];
    els.patientProfileSelect.innerHTML = options.join("");
  }

  async function createPatientProfileFromIntake(formData) {
    if (!apiEnabled()) return null;
    const response = await fetchWithTimeout(
      `${window.APP_CONFIG.API_BASE}/patient_profiles`,
      {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          name: formData.name || state.currentUser?.name || "未命名患者",
          age: formData.age ?? state.currentUser?.age ?? null,
          gender: state.currentUser?.gender ?? null,
          pain_regions: formData.pain_regions,
          history: formData.history,
        }),
      },
      window.APP_CONFIG.LIST_TIMEOUT_MS
    );
    if (!response.ok) return null;
    const profile = await response.json();
    state.patientProfiles.push(profile);
    state.selectedPatientProfileId = profile.id;
    renderPatientProfileSelect();
    return profile;
  }

  return {
    loadProfilesPage,
    loadPatientProfiles,
    renderPatientProfileSelect,
    createPatientProfileFromIntake,
    saveProfileForm,
    deleteProfile,
    resetProfileForm,
    fillProfileForm,
    initProfilePainRegions,
    bindProfilesPageEvents,
    loadImagingReports,
    uploadImagingReport,
    bindImagingReportEvents,
    applyPatientProfileToIntake,
  };
}