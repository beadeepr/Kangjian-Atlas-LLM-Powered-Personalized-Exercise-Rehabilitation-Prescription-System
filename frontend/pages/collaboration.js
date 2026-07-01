// Patient–doctor collaboration: binding, review sharing, adjustments, doctor workspace.



export function createCollaborationPage(ctx) {

  const {

    state,

    els,

    apiGet,

    apiSend,

    escapeHtml,

    formatShortDate,

    showToast,

    showErrorToast,

    renderDemoNotice,

    renderLoadError,

    requireApi,

    showWarnToast,

  } = ctx;



  let doctorPickerOutsideHandler = null;



  function isDoctorRole() {

    const role = state.currentUser?.role;

    return role === "doctor" || role === "admin";

  }



  function renderAdjustmentCard(adjustment) {

    const statusLabel =

      adjustment.status === "proposed"

        ? "待处理"

        : adjustment.status === "applied"

          ? "已采纳"

          : adjustment.status === "rejected"

            ? "已拒绝"

            : adjustment.status;

    const sourceLabel = adjustment.source === "system" ? "系统自动" : "医生建议";

    const actions = (adjustment.adjusted_actions || [])

      .map((action) => `${action.name || action.id} · ${action.sets || 1}组×${action.reps || 1}次`)

      .join("；");

    const pending = adjustment.status === "proposed";

    return `

      <article class="adjustment-card" data-adjustment-id="${adjustment.id}">

        <div class="adjustment-head">

          <strong>${escapeHtml(sourceLabel)}</strong>

          <span class="adjustment-status status-${escapeHtml(adjustment.status)}">${escapeHtml(statusLabel)}</span>

        </div>

        <p>${escapeHtml(adjustment.summary || adjustment.reason || "处方调整建议")}</p>

        ${adjustment.reason ? `<p class="hint">${escapeHtml(adjustment.reason)}</p>` : ""}

        ${actions ? `<p class="hint"><strong>调整后动作：</strong>${escapeHtml(actions)}</p>` : ""}

        <p class="hint">处方 #${adjustment.prescription_id} · ${formatShortDate(adjustment.created_at)}</p>

        ${

          pending

            ? `<div class="adjustment-actions">

                <button class="btn btn-primary btn-small adjustment-apply-btn" type="button" data-id="${adjustment.id}">采纳调整</button>

                <button class="btn btn-secondary btn-small adjustment-reject-btn" type="button" data-id="${adjustment.id}">拒绝</button>

              </div>`

            : adjustment.created_prescription_id

              ? `<p class="hint">已生成新处方 #${adjustment.created_prescription_id}</p>`

              : ""

        }

      </article>`;

  }



  async function loadAdjustments() {

    const container = els.progressAdjustments;

    if (!container) return;

    if (!requireApi()) {

      renderDemoNotice(container, { featureName: "处方调整建议" });

      return;

    }

    container.innerHTML = '<p class="hint">正在加载…</p>';

    try {

      const adjustments = await apiGet("/prescription_adjustments?status=proposed");

      state.pendingAdjustments = adjustments;

      if (!adjustments.length) {

        container.innerHTML = '<p class="hint">暂无待处理的处方调整建议。</p>';

        return;

      }

      container.innerHTML = adjustments.map(renderAdjustmentCard).join("");

    } catch {

      renderLoadError(container, { message: "调整建议加载失败。", onRetry: loadAdjustments });

    }

  }



  async function decideAdjustment(adjustmentId, decision) {

    try {

      await apiSend("POST", `/prescription_adjustments/${adjustmentId}/decision`, { decision });

      showToast(decision === "apply" ? "已采纳调整并生成新处方" : "已拒绝该调整建议");

      await loadAdjustments();

    } catch (error) {

      showErrorToast(error.message || "操作失败");

    }

  }



  async function requestAutoAdjustment() {

    const prescriptionId = state.prescription?.id;

    if (!prescriptionId) {

      showWarnToast("请先生成或选择一份处方");

      return;

    }

    if (!requireApi()) return;

    try {

      await apiSend("POST", `/prescriptions/${prescriptionId}/adjustments/auto`, null);

      showToast("已生成系统自动调整建议");

      await loadAdjustments();

    } catch (error) {

      showErrorToast(error.message || "生成调整建议失败，请确认有足够训练打卡数据");

    }

  }



  function renderPrescriptionCollaboration() {

    const card = els.prescriptionCollaborationCard;

    if (!card || !state.prescription?.id) {

      if (card) card.hidden = true;

      return;

    }

    if (!requireApi()) {

      card.hidden = true;

      return;

    }

    card.hidden = false;

    card.innerHTML = `

      <h3>提交医生审核</h3>

      <p class="hint">填写留言后点击提交，从已绑定医生中快速选择接收人。</p>

      <form id="prescription-review-form" class="collab-form collab-form-first" novalidate>

        <label class="field field-full">患者留言（可选）

          <textarea id="review-patient-note" rows="2" placeholder="请医生重点关注的问题…"></textarea>

        </label>

        <div class="review-submit-wrap">

          <button class="btn btn-primary btn-small" id="review-submit-btn" type="button">提交处方审核</button>

          <div id="doctor-picker-popover" class="doctor-picker-popover" hidden>

            <p class="doctor-picker-title">选择已绑定的医生</p>

            <div id="doctor-picker-list" class="doctor-picker-list"><p class="hint">正在加载…</p></div>

            <p class="hint doctor-picker-foot">尚未绑定医生？请前往「更多 → 医患协同」</p>

          </div>

        </div>

      </form>

    `;

    hideDoctorPicker();

  }



  function renderBoundDoctorCard(link) {

    const label = link.doctor_name || link.doctor_account || `医生 #${link.doctor_id}`;

    return `

      <article class="bound-doctor-card" data-link-id="${link.id}">

        <div class="bound-doctor-head">

          <strong>${escapeHtml(label)}</strong>

          <button class="btn btn-secondary btn-small unlink-doctor-btn" type="button" data-link-id="${link.id}">解绑</button>

        </div>

        <p class="hint">账号：${escapeHtml(link.doctor_account || "—")} · 绑定于 ${formatShortDate(link.created_at)}</p>

      </article>`;

  }



  async function loadPatientDoctorLinks(listId = "collab-bound-doctors-list") {

    const listEl = document.getElementById(listId);

    if (!listEl) return;

    try {

      const links = await apiGet("/doctor_links");

      if (!links.length) {

        listEl.innerHTML = '<p class="hint">暂无绑定医生，可在下方填写医生账号进行绑定。</p>';

        return links;

      }

      listEl.innerHTML = links.map(renderBoundDoctorCard).join("");

      return links;

    } catch {

      listEl.innerHTML = '<p class="hint">绑定医生列表加载失败。</p>';

      return [];

    }

  }



  async function loadCollaborationPage() {

    const panel = els.collaborationPanel;

    if (!panel) return;

    if (!requireApi()) {

      renderDemoNotice(panel, { featureName: "医患协同" });

      return;

    }

    if (isDoctorRole()) {

      panel.innerHTML = '<p class="hint">医生账号请使用「医生工作台」管理患者。</p>';

      return;

    }

    panel.innerHTML = `

      <section class="collab-bound-section">

        <h3>已绑定医生</h3>

        <div id="collab-bound-doctors-list" class="bound-doctors-list"><p class="hint">正在加载…</p></div>

      </section>

      <form id="doctor-link-form" class="collab-form" novalidate>

        <h3>绑定新医生</h3>

        <label class="field field-full">医生账号

          <input id="doctor-link-account" type="text" placeholder="例如：doctor" required />

        </label>

        <label class="field field-full">备注（可选）

          <input id="doctor-link-note" type="text" placeholder="简要说明咨询目的" />

        </label>

        <button class="btn btn-secondary btn-small" type="submit">绑定医生</button>

      </form>

    `;

    await loadPatientDoctorLinks("collab-bound-doctors-list");

  }



  function hideDoctorPicker() {

    const popover = document.getElementById("doctor-picker-popover");

    if (popover) popover.hidden = true;

    document.getElementById("prescription-collaboration-card")?.classList.remove("doctor-picker-open");

    if (doctorPickerOutsideHandler) {

      document.removeEventListener("click", doctorPickerOutsideHandler);

      doctorPickerOutsideHandler = null;

    }

  }



  async function toggleDoctorPicker() {

    const popover = document.getElementById("doctor-picker-popover");

    const wrap = document.querySelector(".review-submit-wrap");

    if (!popover) return;



    if (!popover.hidden) {

      hideDoctorPicker();

      return;

    }



    popover.hidden = false;

    document.getElementById("prescription-collaboration-card")?.classList.add("doctor-picker-open");

    const listEl = document.getElementById("doctor-picker-list");

    if (listEl) listEl.innerHTML = '<p class="hint">正在加载…</p>';



    await loadDoctorPickerList();



    if (doctorPickerOutsideHandler) {

      document.removeEventListener("click", doctorPickerOutsideHandler);

    }

    doctorPickerOutsideHandler = (event) => {

      if (wrap?.contains(event.target)) return;

      hideDoctorPicker();

    };

    setTimeout(() => document.addEventListener("click", doctorPickerOutsideHandler), 0);

  }



  async function loadDoctorPickerList() {

    const listEl = document.getElementById("doctor-picker-list");

    if (!listEl) return [];

    try {

      const links = await apiGet("/doctor_links");

      if (!links.length) {

        listEl.innerHTML = '<p class="hint">暂无绑定医生，请先前往「更多 → 医患协同」绑定。</p>';

        return [];

      }

      listEl.innerHTML = links

        .map((link) => {

          const label = link.doctor_name || link.doctor_account || `医生 #${link.doctor_id}`;

          return `

            <button class="doctor-picker-item" type="button" data-account="${escapeHtml(link.doctor_account || "")}">

              <strong>${escapeHtml(label)}</strong>

              <span class="hint">${escapeHtml(link.doctor_account || "")}</span>

            </button>`;

        })

        .join("");

      return links;

    } catch {

      listEl.innerHTML = '<p class="hint">医生列表加载失败。</p>';

      return [];

    }

  }



  async function revokeDoctorLink(linkId, onSuccess) {

    if (!window.confirm("确定解除与该医生的绑定吗？")) return;

    try {

      await apiSend("DELETE", `/doctor_links/${linkId}`);

      showToast("已解除绑定");

      if (typeof onSuccess === "function") {

        await onSuccess();

      }

    } catch (error) {

      showErrorToast(error.message || "解绑失败");

    }

  }



  async function bindDoctor(event) {

    event.preventDefault();

    if (!requireApi()) return;

    const account = document.getElementById("doctor-link-account")?.value.trim();

    if (!account) return;

    const patientNote = document.getElementById("doctor-link-note")?.value.trim() || null;

    const payload = {

      doctor_account: account,

      patient_profile_id: state.prescription?.patient_profile_id || state.selectedPatientProfileId || null,

      patient_note: patientNote,

    };

    try {

      await apiSend("POST", "/doctor_links", payload);

      showToast(`已绑定医生：${account}`);

      document.getElementById("doctor-link-account").value = "";

      document.getElementById("doctor-link-note").value = "";

      await loadPatientDoctorLinks("collab-bound-doctors-list");

    } catch (error) {

      showErrorToast(error.message || "绑定失败，请确认医生账号存在");

    }

  }



  async function sharePrescriptionReview(doctorAccount, patientNote) {

    if (!requireApi()) return;

    const prescriptionId = state.prescription?.id;

    if (!prescriptionId || !doctorAccount) return;

    try {

      await apiSend("POST", `/prescriptions/${prescriptionId}/reviews/share`, {

        doctor_account: doctorAccount,

        patient_note: patientNote,

      });

      showToast("处方已提交医生审核");

      hideDoctorPicker();

    } catch (error) {

      showErrorToast(error.message || "提交审核失败，请先绑定该医生");

    }

  }



  function formatPatientLabel(link) {

    const name = link.patient_name || "未命名患者";

    const ageText = link.patient_age != null ? `${link.patient_age} 岁` : "年龄未填";

    return `${name} · ${ageText}`;

  }



  function formatPatientMeta(link) {

    if (link.patient_profile_id) {

      return `健康档案 #${link.patient_profile_id}`;

    }

    return "未关联健康档案（展示账号信息）";

  }



  function renderReviewCard(review) {

    const patientLabel = review.patient_name

      ? `${review.patient_name}${review.patient_age != null ? ` · ${review.patient_age} 岁` : ""}`

      : `患者 #${review.user_id}`;

    return `

      <article class="doctor-review-card" data-review-id="${review.id}">

        <div class="doctor-review-head">

          <div>

            <strong>${escapeHtml(patientLabel)}</strong>

            <p class="hint">处方 #${review.prescription_id} · 风险 ${escapeHtml(review.risk_level || "unknown")}</p>

          </div>

          <span class="review-status">${escapeHtml(review.status)}</span>

        </div>

        <p class="hint">提交时间：${formatShortDate(review.created_at)}</p>

        ${review.patient_note ? `<p class="doctor-patient-note">${escapeHtml(review.patient_note)}</p>` : ""}

        <section class="doctor-review-section">

          <div class="doctor-section-head">

            <h4>审核记录</h4>

          </div>

          <form class="doctor-review-form" data-review-id="${review.id}">

            <label class="field field-full">审核意见

              <textarea name="doctor_note" rows="2" placeholder="审核说明…">${escapeHtml(review.doctor_note || "")}</textarea>

            </label>

            <label class="field">风险等级

              <select name="risk_level">

                ${["low", "medium", "high", "unknown"]

                  .map(

                    (level) =>

                      `<option value="${level}"${review.risk_level === level ? " selected" : ""}>${level}</option>`

                  )

                  .join("")}

              </select>

            </label>

            <label class="field">审核结果

              <select name="status">

                <option value="approved">批准</option>

                <option value="reviewed">已阅</option>

                <option value="changes_requested">需调整</option>

              </select>

            </label>

          </form>

        </section>

        <section class="doctor-adjustment-section">

          <div class="doctor-section-head">

            <h4>提出调整建议</h4>

            <span class="hint">发送后患者可在康复进度页采纳</span>

          </div>

          <form class="doctor-adjustment-form" data-review-id="${review.id}" data-prescription-id="${review.prescription_id}">

            <label class="field field-full">调整摘要

              <input name="summary" type="text" placeholder="例如：降低训练强度" required />

            </label>

            <label class="field field-full">调整原因

              <textarea name="reason" rows="2" placeholder="基于审核的调整理由…"></textarea>

            </label>

            <label class="field field-full">动作变更（JSON，可选）

              <textarea name="action_changes" rows="3" placeholder='[{"operation":"update","name":"麦肯基俯卧撑","sets":2}]'></textarea>

            </label>

          </form>

        </section>

        <div class="doctor-review-footer">

          <button class="btn btn-secondary btn-small doctor-save-review-btn" type="button" data-review-id="${review.id}">保存审核</button>

          <button class="btn btn-primary btn-small doctor-submit-adjustment-btn" type="button" data-review-id="${review.id}">提交调整建议</button>

        </div>

      </article>`;

  }



  function renderPatientLinkCard(link) {

    return `

      <article class="doctor-patient-card" data-link-id="${link.id}">

        <div class="bound-doctor-head">

          <strong>${escapeHtml(formatPatientLabel(link))}</strong>

          <button class="btn btn-secondary btn-small unlink-patient-btn" type="button" data-link-id="${link.id}">解除绑定</button>

        </div>

        <p class="hint">${escapeHtml(formatPatientMeta(link))} · 绑定于 ${formatShortDate(link.created_at)}</p>

        ${link.patient_note ? `<p>${escapeHtml(link.patient_note)}</p>` : ""}

      </article>`;

  }



  async function loadDoctorWorkspace() {

    const panel = els.doctorWorkspace;

    if (!panel) return;

    if (!requireApi()) {

      renderDemoNotice(panel, { featureName: "医生工作台" });

      return;

    }

    if (!isDoctorRole()) {

      panel.innerHTML = '<p class="hint">当前账号无医生权限。</p>';

      return;

    }

    panel.innerHTML = '<p class="hint">正在加载…</p>';

    try {

      const [patients, reviews] = await Promise.all([

        apiGet("/doctor/patients"),

        apiGet("/doctor/reviews"),

      ]);

      const pendingReviews = reviews.filter((item) => item.status === "pending" || item.status === "changes_requested");

      panel.innerHTML = `

        <section class="doctor-section">

          <h3>我的患者（${patients.length}）</h3>

          <div class="doctor-patient-list">

            ${patients.length ? patients.map(renderPatientLinkCard).join("") : '<p class="hint">暂无绑定患者。</p>'}

          </div>

        </section>

        <section class="doctor-section">

          <h3>处方审核（${pendingReviews.length} 待处理）</h3>

          <div class="doctor-review-list">

            ${pendingReviews.length ? pendingReviews.map(renderReviewCard).join("") : '<p class="hint">暂无待审核处方。</p>'}

          </div>

        </section>

      `;

    } catch {

      renderLoadError(panel, { message: "医生工作台加载失败。", onRetry: loadDoctorWorkspace });

    }

  }



  async function submitDoctorReview(form) {

    const reviewId = form.dataset.reviewId;

    const formData = new FormData(form);

    try {

      await apiSend("PUT", `/doctor/reviews/${reviewId}`, {

        status: formData.get("status"),

        doctor_note: formData.get("doctor_note")?.toString().trim() || null,

        risk_level: formData.get("risk_level")?.toString() || null,

      });

      showToast("审核已保存");

      await loadDoctorWorkspace();

    } catch (error) {

      showErrorToast(error.message || "保存审核失败");

    }

  }



  async function submitDoctorAdjustment(form) {

    const reviewId = form.dataset.reviewId;

    const formData = new FormData(form);

    let actionChanges = [];

    const rawChanges = formData.get("action_changes")?.toString().trim();

    if (rawChanges) {

      try {

        actionChanges = JSON.parse(rawChanges);

      } catch {

        showErrorToast("动作变更 JSON 格式不正确");

        return;

      }

    }

    try {

      await apiSend("POST", `/doctor/reviews/${reviewId}/adjustments`, {

        summary: formData.get("summary")?.toString().trim() || null,

        reason: formData.get("reason")?.toString().trim() || null,

        action_changes: actionChanges,

      });

      showToast("调整建议已发送给患者");

      await loadDoctorWorkspace();

    } catch (error) {

      showErrorToast(error.message || "提交调整建议失败");

    }

  }



  function bindCollaborationEvents() {

    els.progressAdjustments?.addEventListener("click", async (event) => {

      const applyBtn = event.target.closest(".adjustment-apply-btn");

      const rejectBtn = event.target.closest(".adjustment-reject-btn");

      if (applyBtn) {

        await decideAdjustment(Number(applyBtn.dataset.id), "apply");

      }

      if (rejectBtn) {

        await decideAdjustment(Number(rejectBtn.dataset.id), "reject");

      }

    });



    els.collaborationPanel?.addEventListener("click", async (event) => {

      const button = event.target.closest(".unlink-doctor-btn");

      if (!button) return;

      await revokeDoctorLink(Number(button.dataset.linkId), () =>

        loadPatientDoctorLinks("collab-bound-doctors-list")

      );

    });



    els.collaborationPanel?.addEventListener("submit", async (event) => {

      if (event.target.id === "doctor-link-form") {

        event.preventDefault();

        await bindDoctor(event);

      }

    });



    els.prescriptionCollaborationCard?.addEventListener("click", async (event) => {

      if (event.target.closest("#review-submit-btn")) {

        event.stopPropagation();

        await toggleDoctorPicker();

        return;

      }

      const pickBtn = event.target.closest(".doctor-picker-item");

      if (pickBtn) {

        event.stopPropagation();

        const account = pickBtn.dataset.account?.trim();

        if (!account) return;

        const patientNote = document.getElementById("review-patient-note")?.value.trim() || null;

        await sharePrescriptionReview(account, patientNote);

      }

    });



    els.doctorWorkspace?.addEventListener("click", async (event) => {

      const unlinkBtn = event.target.closest(".unlink-patient-btn");

      if (unlinkBtn) {

        await revokeDoctorLink(Number(unlinkBtn.dataset.linkId), loadDoctorWorkspace);

        return;

      }

      const saveBtn = event.target.closest(".doctor-save-review-btn");

      if (saveBtn) {

        const card = saveBtn.closest(".doctor-review-card");

        const form = card?.querySelector(".doctor-review-form");

        if (form) await submitDoctorReview(form);

        return;

      }

      const adjBtn = event.target.closest(".doctor-submit-adjustment-btn");

      if (adjBtn) {

        const card = adjBtn.closest(".doctor-review-card");

        const form = card?.querySelector(".doctor-adjustment-form");

        if (form) await submitDoctorAdjustment(form);

      }

    });



    document.getElementById("request-auto-adjustment")?.addEventListener("click", requestAutoAdjustment);

  }



  function updateCollaborationEntryVisibility() {

    const loggedIn = Boolean(state.auth?.token);

    const isDoctor = isDoctorRole();

    if (els.collaborationEntryButton) {

      els.collaborationEntryButton.hidden = !loggedIn || isDoctor || window.APP_CONFIG.DEMO_MODE;

    }

    if (els.doctorEntryButton) {

      els.doctorEntryButton.hidden = !loggedIn || !isDoctor || window.APP_CONFIG.DEMO_MODE;

    }

  }



  return {

    loadAdjustments,

    loadCollaborationPage,

    loadDoctorWorkspace,

    renderPrescriptionCollaboration,

    bindCollaborationEvents,

    updateCollaborationEntryVisibility,

    isDoctorRole,

  };

}

