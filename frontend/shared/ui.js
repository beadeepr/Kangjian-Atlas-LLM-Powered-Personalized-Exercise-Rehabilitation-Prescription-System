// Shared UI helpers: pure functions with no app-state dependency.
// Extracted from app.js to keep rendering utilities reusable across pages.

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Backwards-compatible alias retained for the legacy render code in app.js.
export const escapeAdminText = escapeHtml;

export function formatShortDate(value) {
  if (!value) return "—";
  return String(value).slice(0, 19).replace("T", " ");
}

// Debounce a function by `wait` ms. Returns a cancelable wrapper.
export function debounce(fn, wait = 300) {
  let timer = null;
  function debounced(...args) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn.apply(this, args);
    }, wait);
  }
  debounced.cancel = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  };
  debounced.flush = (...args) => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    fn.apply(this, args);
  };
  return debounced;
}

// Render a friendly "feature unavailable in Demo mode" notice into `container`.
// `onSwitch` is invoked when the user clicks the switch button; defaulting to
// flipping the demo flag and reloading.
export function renderDemoNotice(container, { featureName = "该功能", onSwitch } = {}) {
  if (!container) return;
  container.innerHTML = `
    <div class="notice-card demo-notice">
      <div class="notice-icon">🧪</div>
      <div class="notice-body">
        <h3>${escapeHtml(featureName)}需要 API 模式</h3>
        <p>当前为 Demo 模式，仅演示本地数据。切换到 API 模式并登录后即可使用真实后端能力。</p>
      </div>
      <button class="btn btn-primary btn-small demo-notice-switch" type="button">切换 API 模式</button>
    </div>
  `;
  const btn = container.querySelector(".demo-notice-switch");
  if (btn) {
    btn.addEventListener("click", () => {
      if (onSwitch) onSwitch();
      else {
        window.APP_CONFIG.setDemoMode(false);
        location.reload();
      }
    });
  }
}

// Render a load-error block with a retry button into `container`.
// `onRetry` is invoked when the user clicks 重试.
export function renderLoadError(container, { message = "加载失败，请确认后端已启动后重试。", onRetry } = {}) {
  if (!container) return;
  container.innerHTML = `
    <div class="notice-card error-notice">
      <div class="notice-icon">⚠️</div>
      <div class="notice-body">
        <p>${escapeHtml(message)}</p>
      </div>
      <button class="btn btn-secondary btn-small error-notice-retry" type="button">重试</button>
    </div>
  `;
  const btn = container.querySelector(".error-notice-retry");
  if (btn && onRetry) btn.addEventListener("click", onRetry);
}
