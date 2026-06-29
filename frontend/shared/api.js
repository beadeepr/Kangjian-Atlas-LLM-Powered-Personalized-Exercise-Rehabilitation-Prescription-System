// Shared API helpers: pure utilities with no app-state dependency.
//
// The auth-aware wrappers (apiGet / apiSend) live in app.js because they need
// access to the live auth token; this module exports the parts that don't.

// Error subclass carrying the failing response for callers that want to
// render a retry button.
export class ApiError extends Error {
  constructor(message, response) {
    super(message);
    this.name = "ApiError";
    this.response = response;
  }
}

// Parse a fetch error response into a human-readable detail string.
export async function parseApiError(response) {
  const raw = await response.text();
  try {
    const data = JSON.parse(raw);
    const detail = data.detail;
    if (typeof detail === "object" && detail !== null) {
      return detail.message || detail.msg || JSON.stringify(detail);
    }
    return detail || raw;
  } catch {
    return raw || `HTTP ${response.status}`;
  }
}

// Variant that returns the raw `detail` field without message extraction.
export async function parseApiErrorDetail(response) {
  const raw = await response.text();
  try {
    const data = JSON.parse(raw);
    return data.detail ?? raw;
  } catch {
    return raw;
  }
}

// fetch with an AbortController-based timeout. Pure: takes the URL and options
// (including any auth headers) the caller already prepared.
export async function fetchWithTimeout(url, options = {}, timeoutMs = 5000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}
