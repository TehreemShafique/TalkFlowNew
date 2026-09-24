"use client";

const USER_KEY = "app_user_data";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

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

// Global HTTP Interceptor wrapper for fetch API
export async function apiFetch(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(apiUrl(endpoint), {
      ...options,
      headers,
      credentials: "include",
    });

    return response;
  } catch (error) {
    return {
      ok: false,
      status: 0,
      json: async () => ({ data: [], items: [] }),
    };
  }
}
