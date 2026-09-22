"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import {
  clearAuthToken,
  getStoredUser,
  setStoredUser,
  apiFetch,
} from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const storedUser = getStoredUser();
      if (storedUser) setUser(storedUser);

      try {
        const response = await apiFetch("/auth/me");
        if (response.ok) {
          const freshUser = await response.json();
          setUser(freshUser);
          setStoredUser(freshUser);
        } else {
          clearAuthToken();
          setUser(null);
        }
      } catch {
        // Offline-tolerant: keep stored profile if network transiently drops
      }
      setLoading(false);
    })();
  }, []);

  const refreshUser = async () => {
    try {
      const response = await apiFetch("/auth/me");
      if (response.ok) {
        const freshUser = await response.json();
        setUser(freshUser);
        setStoredUser(freshUser);
        return freshUser;
      }
    } catch {
      // Keep existing user on transient failures.
    }
    return null;
  };

  const login = async (email, password) => {
    setLoading(true);
    try {
      const response = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Invalid credentials. Please try again.");
      }

      const data = await response.json();
      setStoredUser(data.user);
      setUser(data.user);
      return data.user;
    } finally {
      setLoading(false);
    }
  };

  const signup = async ({ email, password, username, firstName, lastName }) => {
    setLoading(true);
    try {
      const response = await apiFetch("/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          username,
          first_name: firstName,
          last_name: lastName,
        }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Account creation failed. Please try again.");
      }

      const data = await response.json();
      return data;
    } finally {
      setLoading(false);
    }
  };

  const register = async ({ username, email, firstName, lastName, type, password }) => {
    setLoading(true);
    try {
      const response = await apiFetch("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          username,
          first_name: firstName,
          last_name: lastName,
          type,
        }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Account creation failed. Please try again.");
      }

      const data = await response.json();
      setStoredUser(data.user);
      setUser(data.user);
      return data.user;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // Best-effort: revoke server-side cookie, then clear local state.
    }
    clearAuthToken();
    setUser(null);
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  };

  const status = user?.account_status || "APPROVED";
  const roles = user?.roles || [];
  const isPending = status === "PENDING";
  const isApproved = status === "APPROVED";
  const isRejected = status === "REJECTED";

  const is_admin = Boolean(
    user &&
      (user.is_admin ||
        roles.includes("MASTER_ADMIN") ||
        roles.includes("DEVOPS_IT"))
  );

  const role = user?.role || user?.type || (roles.length > 0 ? roles[0] : "VIEWER");

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: Boolean(user),
        status,
        roles,
        isPending,
        isApproved,
        isRejected,
        is_admin,
        role,
        login,
        signup,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
