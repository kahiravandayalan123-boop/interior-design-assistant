// Thin wrapper around the backend REST API.
// In dev, BASE is "" and the Vite proxy forwards /api to http://127.0.0.1:8000.
// In production (Vercel) it's the deployed backend's URL, e.g.
// https://my-backend.up.railway.app — a trailing slash is tolerated.
const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

// Thrown on any non-2xx response. Carries the HTTP status so callers can
// special-case things like "session expired" (404) vs. everything else.
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function jsonOrThrow(res) {
  let body = null;
  try {
    body = await res.json();
  } catch {
    // Non-JSON response (proxy error page, dropped connection, etc).
  }
  if (!res.ok) {
    const detail = body?.detail || body?.message;
    const message =
      typeof detail === "string" && detail
        ? detail
        : body
          ? JSON.stringify(detail ?? body)
          : `Request failed (${res.status} ${res.statusText || ""}).`.trim();
    throw new ApiError(message, res.status);
  }
  return body;
}

// Client-side backstops, a little above the backend's own provider timeouts
// (backend/app/config.py) so a hung connection can never spin forever.
const TIMEOUT_MS = {
  default: 30_000,
  analyze: 200_000, // Claude vision + questions
  generate: 330_000, // Claude prompt + image render (+ analysis, for /modify)
};

// Status 0 = never got an HTTP response; 408 = gave up waiting.
async function request(path, options = {}, timeoutMs = TIMEOUT_MS.default) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { ...options, signal: controller.signal });
  } catch (e) {
    if (e?.name === "AbortError") {
      throw new ApiError(
        "The server took too long to respond. Please try again.",
        408
      );
    }
    // fetch() itself throws on network failure / server unreachable / CORS.
    throw new ApiError(
      "Can't reach the server. It may be starting up — wait a few seconds, then try again.",
      0
    );
  } finally {
    clearTimeout(timer);
  }
  return jsonOrThrow(res);
}

export function mediaUrl(path) {
  if (!path) return "";
  if (/^https?:|^data:/.test(path)) return path;
  return `${BASE}${path}`;
}

export async function getConfig() {
  return request("/api/config");
}

export async function uploadRoom({ style, file }) {
  const form = new FormData();
  form.append("style", style);
  form.append("image", file);
  return request("/api/upload", { method: "POST", body: form }, TIMEOUT_MS.analyze);
}

// `message` is the optional free-text change request ("" clears it).
export async function sendAnswers({ sessionId, answers, message }) {
  return request("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, answers, message }),
  });
}

export async function generateRedesign({ sessionId }) {
  return request(
    "/api/generate",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    },
    TIMEOUT_MS.generate
  );
}

// Loads a bundled sample room photo (frontend/public/samples) as a File, so
// the demo can skip a live upload from disk.
export async function loadSample(src, name) {
  const res = await fetch(src);
  if (!res.ok) throw new ApiError("Couldn't load the sample photo.", res.status);
  const blob = await res.blob();
  return new File([blob], name, { type: blob.type || "image/jpeg" });
}

// "Modify Existing Room" flow: one call — photo + free-text instruction +
// budget in, a finished redesign (image + shopping list) out.
export async function modifyRoom({ file, instruction, budget }) {
  const form = new FormData();
  form.append("image", file);
  form.append("instruction", instruction);
  form.append("budget", budget);
  return request("/api/modify", { method: "POST", body: form }, TIMEOUT_MS.generate);
}

// Fetches the image at `url` (same-origin, served by our backend) and saves
// it via a temporary object URL — works for both the mock placeholder and a
// real DALL-E render, and avoids the cross-origin limits of a plain
// `<a download>` pointed at a provider's own CDN.
export async function downloadImage(url, filename) {
  const res = await fetch(url);
  if (!res.ok) throw new ApiError("Couldn't download the image.", res.status);
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}
