"use client";

const USER_KEY = "app_user_data";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function apiUrl(path) {
  return path.startsWith("http") ? path : `${API_BASE_URL}${path}`;
}

export function clearAuthToken() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem("talkflow_auth_token");
    localStorage.removeItem("app_access_token");
  }
}

export function getStoredUser() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    console.warn("Failed to parse stored user profile:", error);
    return null;
  }
}

export function setStoredUser(user) {
  if (typeof window !== "undefined") {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_KEY);
    }
  }
}

// Endpoints that establish or tear down the session. A 401 from these is a
// final answer, so they must not trigger the refresh-and-retry path.
const AUTH_ENDPOINTS = ["/auth/login", "/auth/refresh", "/auth/logout"];

function isAuthEndpoint(endpoint) {
  return AUTH_ENDPOINTS.some((path) => endpoint.startsWith(path));
}

// Deduplicates concurrent 401s: several views can mount at once and all of them
// would otherwise fire their own refresh, and rotation invalidates the losers.
let refreshInFlight = null;

async function refreshAccessToken() {
  if (!refreshInFlight) {
    refreshInFlight = fetch(apiUrl("/auth/refresh"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    })
      .then((response) => response.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

function redirectToLogin() {
  clearAuthToken();
  if (typeof window === "undefined") return;
  // A hard navigation (not router.push) is deliberate: the session is gone, so
  // every in-memory view must be torn down rather than SPA-cached. ``replace``
  // also stops the back button from returning to a stale authenticated page.
  if (window.location.pathname !== "/login") {
    window.location.replace(`${window.location.origin}/login`);
  }
}

// Global HTTP Interceptor wrapper for fetch API.
//
// The access token is a short-lived HttpOnly cookie (blueprint 11.4), so it can
// expire while the tab is open. On a 401 we spend the rotating refresh cookie
// once and replay the original request; if that fails the session is genuinely
// over and the user is sent back to the login screen.
export async function apiFetch(endpoint, options = {}) {
  // A FormData body must be sent without an explicit Content-Type: the browser
  // has to append the multipart boundary itself, and naming the header
  // "application/json" corrupts the upload.  Callers uploading files therefore
  // pass FormData as `body` and get the right header for free.
  const isMultipart = typeof FormData !== "undefined" && options.body instanceof FormData;

  const headers = {
    ...(isMultipart ? {} : { "Content-Type": "application/json" }),
    ...(options.headers || {}),
  };

  const send = () =>
    fetch(apiUrl(endpoint), {
      ...options,
      headers,
      credentials: "include",
    });

  try {
    const response = await send();

    if (response.status === 401 && !isAuthEndpoint(endpoint)) {
      if (await refreshAccessToken()) {
        return send();
      }
      redirectToLogin();
    }

    return response;
  } catch (error) {
    // Callers rely on apiFetch never rejecting, so a transport failure is still
    // returned as a response-shaped object. It is explicitly `ok: false` and
    // carries the cause, but it no longer fabricates `data: []`/`items: []` -
    // an unreachable backend must not look like an empty database.
    console.error("apiFetch transport failure:", endpoint, error);
    return {
      ok: false,
      status: 0,
      error,
      json: async () => ({}),
    };
  }
}
