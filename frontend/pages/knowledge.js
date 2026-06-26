// M7 Knowledge education page.
//
// Extracted from app.js as a self-contained page module. The page relies on
// app-level state, element refs, and API helpers; those are injected via the
// `ctx` object so this module stays free of global coupling.
//
// ctx shape:
//   state              - shared app state object (knowledgeFilters, knowledgeArticles,
//                        knowledgeExpandedId, knowledgeTab, knowledgeQaRegions)
//   els                - element refs (knowledgeArticlesList, knowledgePreventionList,
//                        knowledgeQaResult, knowledgePainRegions)
//   apiGet(path, opts) - GET JSON helper
//   apiSend(method, path, body, opts) - POST/PUT/DELETE JSON helper
//   escapeHtml(value)  - HTML escaper
//   renderLoadError(container, { message, onRetry })
//   showToast(message)
//   parseApiError(response)

export function createKnowledgePage(ctx) {
  const {
    state,
    els,
    apiGet,
    apiSend,
    escapeHtml,
    renderLoadError,
    showToast,
  } = ctx;

  function renderKnowledgePainRegions() {
    if (!els.knowledgePainRegions) return;
    els.knowledgePainRegions.innerHTML = window.PAIN_REGIONS.map(
      (region) =>
        `<button class="chip${state.knowledgeQaRegions.has(region) ? " selected" : ""}" type="button" data-region="${escapeHtml(region)}">${escapeHtml(region)}</button>`
    ).join("");
  }

  function switchKnowledgeTab(tab) {
    state.knowledgeTab = tab;
    document.querySelectorAll(".knowledge-tab").forEach((button) => {
      const active = button.dataset.knowledgeTab === tab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.getElementById("knowledge-articles-panel").hidden = tab !== "articles";
    document.getElementById("knowledge-prevention-panel").hidden = tab !== "prevention";
    document.getElementById("knowledge-qa-panel").hidden = tab !== "qa";
    if (tab === "prevention") renderKnowledgePrevention();
  }

  function renderKnowledgeArticleCard(article) {
    const expanded = state.knowledgeExpandedId === article.id;
    const regions = (article.body_regions || []).join("、");
    const related = (article.related_actions || [])
      .map((a) => `<li>${escapeHtml(a.name || a.id)}${a.sets ? ` · ${a.sets}组×${a.reps}次` : ""}</li>`)
      .join("");
    const tips = (article.prevention_tips || [])
      .map((tip) => `<li>${escapeHtml(tip)}</li>`)
      .join("");
    return `
    <article class="knowledge-article-card${expanded ? " expanded" : ""}" data-article-id="${escapeHtml(article.id)}">
      <button class="knowledge-article-head" type="button" data-toggle-article="${escapeHtml(article.id)}">
        <div>
          <span class="knowledge-category">${escapeHtml(article.category || "康复百科")}</span>
          <h3>${escapeHtml(article.title)}</h3>
          <p class="hint">${escapeHtml(regions)}</p>
        </div>
        <span class="knowledge-expand-icon" aria-hidden="true">${expanded ? "−" : "+"}</span>
      </button>
      <div class="knowledge-article-body"${expanded ? "" : " hidden"}>
        <p>${escapeHtml(article.summary)}</p>
        <p>${escapeHtml(article.content)}</p>
        ${related ? `<h4>相关训练动作</h4><ul>${related}</ul>` : ""}
        ${tips ? `<h4>预防保健建议</h4><ul class="prevention-tips-list">${tips}</ul>` : ""}
      </div>
    </article>`;
  }

  function renderKnowledgeArticles() {
    if (!els.knowledgeArticlesList) return;
    const articles = state.knowledgeArticles;
    if (!articles.length) {
      els.knowledgeArticlesList.innerHTML = "<p class=\"hint\">暂无匹配的康复百科内容。</p>";
      return;
    }
    els.knowledgeArticlesList.innerHTML = articles.map(renderKnowledgeArticleCard).join("");
  }

  function renderKnowledgePrevention() {
    if (!els.knowledgePreventionList) return;
    const articles = state.knowledgeArticles;
    if (!articles.length) {
      els.knowledgePreventionList.innerHTML = "<p class=\"hint\">暂无预防保健内容。</p>";
      return;
    }
    els.knowledgePreventionList.innerHTML = articles
      .map((article) => {
        const tips = (article.prevention_tips || [])
          .map((tip) => `<li>${escapeHtml(tip)}</li>`)
          .join("");
        return `
        <div class="card knowledge-prevention-card">
          <h3>${escapeHtml(article.title)}</h3>
          <p class="hint">${escapeHtml((article.body_regions || []).join("、"))}</p>
          <ul class="prevention-tips-list">${tips || "<li>保持规律活动，避免突然增加训练量。</li>"}</ul>
        </div>`;
      })
      .join("");
  }

  function populateKnowledgeRegionFilter() {
    const select = document.getElementById("knowledge-filter-region");
    if (!select) return;
    const current = select.value;
    select.innerHTML = `<option value="">全部部位</option>${window.PAIN_REGIONS.map(
      (region) =>
        `<option value="${escapeHtml(region)}"${state.knowledgeFilters.bodyRegion === region ? " selected" : ""}>${escapeHtml(region)}</option>`
    ).join("")}`;
    select.value = current || state.knowledgeFilters.bodyRegion;
  }

  async function fetchKnowledgeArticles() {
    const params = new URLSearchParams();
    if (state.knowledgeFilters.q?.trim()) params.set("q", state.knowledgeFilters.q.trim());
    if (state.knowledgeFilters.bodyRegion) params.set("body_region", state.knowledgeFilters.bodyRegion);
    params.set("limit", "10");
    const query = params.toString();
    if (window.APP_CONFIG.DEMO_MODE) {
      return window.MockService.buildMockKnowledgeArticles(
        state.knowledgeFilters.q,
        state.knowledgeFilters.bodyRegion || null,
        10
      );
    }
    const data = await apiGet(`/knowledge/articles${query ? `?${query}` : ""}`);
    return data.items || [];
  }

  async function loadKnowledgePage() {
    if (!els.knowledgeArticlesList) return;
    renderKnowledgePainRegions();
    populateKnowledgeRegionFilter();
    els.knowledgeArticlesList.innerHTML = "<p class=\"hint\">正在加载康复知识…</p>";
    if (els.knowledgePreventionList) {
      els.knowledgePreventionList.innerHTML = "<p class=\"hint\">正在加载…</p>";
    }
    try {
      state.knowledgeArticles = await fetchKnowledgeArticles();
      renderKnowledgeArticles();
      if (state.knowledgeTab === "prevention") renderKnowledgePrevention();
    } catch {
      renderLoadError(els.knowledgeArticlesList, {
        message: "知识库加载失败，请确认后端已启动后重试。",
        onRetry: loadKnowledgePage,
      });
    }
  }

  function renderKnowledgeQaResult(result) {
    if (!els.knowledgeQaResult) return;
    const refs = (result.references || [])
      .slice(0, 3)
      .map((a) => `<li>${escapeHtml(a.title)}</li>`)
      .join("");
    const actions = (result.suggested_actions || [])
      .slice(0, 4)
      .map((a) => `<li>${escapeHtml(a.name || a.id)}</li>`)
      .join("");
    const safety = (result.safety_notes || [])
      .map((note) => `<li>${escapeHtml(note)}</li>`)
      .join("");
    const ragHint = (result.rag_contexts || []).length
      ? `<p class="hint">已检索 ${result.rag_contexts.length} 条知识库上下文。</p>`
      : "";
    els.knowledgeQaResult.hidden = false;
    els.knowledgeQaResult.innerHTML = `
    <div class="knowledge-qa-answer">
      <h3>回答</h3>
      <p>${escapeHtml(result.answer)}</p>
      ${ragHint}
    </div>
    ${refs ? `<div class="knowledge-qa-refs"><h4>参考文章</h4><ul>${refs}</ul></div>` : ""}
    ${actions ? `<div class="knowledge-qa-actions"><h4>推荐动作</h4><ul>${actions}</ul></div>` : ""}
    ${safety ? `<div class="knowledge-qa-safety"><h4>安全提示</h4><ul>${safety}</ul></div>` : ""}
  `;
  }

  async function submitKnowledgeQuestion(event) {
    event.preventDefault();
    const question = document.getElementById("knowledge-question")?.value?.trim();
    if (!question) {
      showToast("请输入您的问题");
      return;
    }
    const painRegions = Array.from(state.knowledgeQaRegions);
    const submitBtn = document.getElementById("knowledge-qa-submit");
    if (submitBtn) submitBtn.disabled = true;
    if (els.knowledgeQaResult) {
      els.knowledgeQaResult.hidden = false;
      els.knowledgeQaResult.innerHTML = "<p class=\"hint\">正在检索知识库并生成回答…</p>";
    }
    try {
      let result;
      if (window.APP_CONFIG.DEMO_MODE) {
        result = window.MockService.answerMockKnowledgeQuestion(question, painRegions);
      } else {
        result = await apiSend(
          "POST",
          "/knowledge/qa",
          { question, pain_regions: painRegions.length ? painRegions : null, limit: 4 },
          { timeoutMs: window.APP_CONFIG.PRESCRIPTION_TIMEOUT_MS }
        );
      }
      renderKnowledgeQaResult(result);
    } catch (error) {
      if (els.knowledgeQaResult) {
        els.knowledgeQaResult.innerHTML = `<p class="hint">${escapeHtml(error.message || "问答请求失败")}</p>`;
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  function bindKnowledgePageEvents(debounceFn) {
    document.querySelectorAll(".knowledge-tab").forEach((button) => {
      button.addEventListener("click", () => switchKnowledgeTab(button.dataset.knowledgeTab));
    });
    document.getElementById("knowledge-qa-form")?.addEventListener("submit", submitKnowledgeQuestion);
    document.getElementById("refresh-knowledge")?.addEventListener("click", loadKnowledgePage);
    document.getElementById("knowledge-filter-q")?.addEventListener("input", (event) => {
      state.knowledgeFilters.q = event.target.value;
      if (debounceFn) debounceFn();
      else loadKnowledgePage();
    });
    document.getElementById("knowledge-filter-region")?.addEventListener("change", (event) => {
      state.knowledgeFilters.bodyRegion = event.target.value;
      loadKnowledgePage();
    });
    els.knowledgeArticlesList?.addEventListener("click", (event) => {
      const toggle = event.target.closest("[data-toggle-article]");
      if (!toggle) return;
      const id = toggle.dataset.toggleArticle;
      state.knowledgeExpandedId = state.knowledgeExpandedId === id ? null : id;
      renderKnowledgeArticles();
    });
    els.knowledgePainRegions?.addEventListener("click", (event) => {
      const chip = event.target.closest(".chip[data-region]");
      if (!chip) return;
      const region = chip.dataset.region;
      if (state.knowledgeQaRegions.has(region)) state.knowledgeQaRegions.delete(region);
      else state.knowledgeQaRegions.add(region);
      renderKnowledgePainRegions();
    });
  }

  return {
    loadKnowledgePage,
    bindKnowledgePageEvents,
    switchKnowledgeTab,
  };
}
