"use client";

import React, { useState } from "react";
import {
  User,
  Mail,
  Phone,
  Building2,
  BadgeCheck,
  LogOut,
  CheckCircle2,
  ShieldCheck,
  Globe,
  Save,
} from "lucide-react";
import { useAuth } from "@/context";
import { apiFetch } from "@/lib/api";

export default function ProfileView() {
  const { user, role, logout, refreshUser } = useAuth();

  // Profile Form State
  const [formData, setFormData] = useState({
    firstName: user?.firstName || "",
    lastName: user?.lastName || "",
    username: user?.username || "",
    email: user?.email || "",
    extension: user?.extension || "",
    department: "SmartBrains BPO Operations",
    timezone: "America/New_York (UTC-5)",
    language: "English (US)",
    defaultLanding: "dashboard",
  });

  const [savedSuccess, setSavedSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMsg("");
    setSavedSuccess(false);
    try {
      const response = await apiFetch("/auth/me", {
        method: "PATCH",
        body: JSON.stringify({
          first_name: formData.firstName,
          last_name: formData.lastName,
          username: formData.username,
          email: formData.email,
          extension: formData.extension,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || "Failed to update profile. Please try again.");
      }

      await refreshUser();
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      setErrorMsg(err.message || "Failed to update profile. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  const userRoleTitle = user?.type || user?.role || role || "Master Admin";

  return (
    <div className="flex-1 space-y-6 p-6 pb-12 max-w-7xl mx-auto w-full">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-xl border border-neutral-200 bg-white p-6 dark:border-[#1a1a1a] dark:bg-[#09090b] shadow-xs">
        <div className="absolute top-0 right-0 h-32 w-32 translate-x-8 -translate-y-8 rounded-full bg-blue-500/10 blur-2xl dark:bg-blue-500/15" />
        <div className="relative flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            {/* User Avatar with Initials */}
            <div className="relative flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 text-2xl font-bold text-white shadow-md">
              {user?.firstName?.[0] || "?"}
              {user?.lastName?.[0] || ""}
              <span className="absolute bottom-1 right-1 h-4 w-4 rounded-full border-2 border-white bg-emerald-500 dark:border-[#09090b]" title="Account Active" />
            </div>

            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-neutral-900 dark:text-white">
                  {user?.firstName || user?.username || "User"} {user?.lastName || ""}
                </h1>
                <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 dark:border-blue-900/40 dark:bg-blue-950/40 dark:text-blue-400">
                  <BadgeCheck className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
                  {userRoleTitle}
                </span>
              </div>
              <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400 flex items-center gap-4 flex-wrap">
                <span className="flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5 text-neutral-400" />
                  {user?.email || "—"}
                </span>
                <span className="flex items-center gap-1.5">
                  <Phone className="h-3.5 w-3.5 text-neutral-400" />
                  Ext: {user?.extension || "Not assigned"}
                </span>
                <span className="flex items-center gap-1.5">
                  <Building2 className="h-3.5 w-3.5 text-neutral-400" />
                  SmartBrains BPO
                </span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 self-end md:self-center">
            <button
              type="button"
              onClick={logout}
              className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-100 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-400 dark:hover:bg-rose-900/50 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Sign Out
            </button>
          </div>
        </div>

        {/* Quick Account Highlights */}
        <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3 border-t border-neutral-100 pt-4 dark:border-neutral-800">
          <div className="flex flex-col">
            <span className="text-xs text-neutral-500 dark:text-neutral-400">Account ID</span>
            <span className="font-mono text-xs font-bold text-neutral-900 dark:text-white">
              {user?.id || "—"}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-neutral-500 dark:text-neutral-400">Account Status</span>
            <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" /> Active & Verified
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-neutral-500 dark:text-neutral-400">2FA Security</span>
            <span className="text-xs font-bold text-blue-600 dark:text-blue-400 flex items-center gap-1">
              <ShieldCheck className="h-3 w-3" /> Enabled (TOTP)
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-neutral-500 dark:text-neutral-400">Last Active</span>
            <span className="text-xs font-bold text-neutral-900 dark:text-white">
              {user?.lastLogin || "—"}
            </span>
          </div>
        </div>
      </div>

      {/* Account Profile Form */}
      <form onSubmit={handleSaveProfile} className="space-y-6">
        {savedSuccess && (
          <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-xs font-semibold text-emerald-800 dark:border-emerald-900/40 dark:bg-emerald-950/40 dark:text-emerald-300">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            <span>Profile details updated successfully!</span>
          </div>
        )}

        {errorMsg && (
          <div className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800 dark:border-rose-900/40 dark:bg-rose-950/40 dark:text-rose-300">
            <CheckCircle2 className="h-4 w-4 text-rose-600 dark:text-rose-400" />
            <span>{errorMsg}</span>
          </div>
        )}

        <div className="rounded-xl border border-neutral-200 bg-white p-6 dark:border-[#1a1a1a] dark:bg-[#09090b] space-y-4">
          <h2 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <User className="h-4 w-4 text-blue-600" /> Personal & Work Identity
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                First Name
              </label>
              <input
                type="text"
                value={formData.firstName}
                onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
                className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-900 dark:border-neutral-800 dark:bg-[#121215] dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                Last Name
              </label>
              <input
                type="text"
                value={formData.lastName}
                onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-900 dark:border-neutral-800 dark:bg-[#121215] dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                Username
              </label>
              <input
                type="text"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-900 dark:border-neutral-800 dark:bg-[#121215] dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                Work Email Address
              </label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-900 dark:border-neutral-800 dark:bg-[#121215] dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                Telephony Extension Number
              </label>
              <input
                type="text"
                value={formData.extension}
                onChange={(e) => setFormData({ ...formData, extension: e.target.value })}
                className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-xs font-mono font-medium text-neutral-900 dark:border-neutral-800 dark:bg-[#121215] dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                Department / Unit
              </label>
              <input
                type="text"
                value={formData.department}
                onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-900 dark:border-neutral-800 dark:bg-[#121215] dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-neutral-200 bg-white p-6 dark:border-[#1a1a1a] dark:bg-[#09090b] space-y-4">
          <h2 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <Globe className="h-4 w-4 text-blue-600" /> Regional & Display Preferences
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                Platform Timezone
              </label>
              <select
                value={formData.timezone}
                onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
                className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-900 dark:border-neutral-800 dark:bg-[#121215] dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="America/New_York (UTC-5)">America/New_York (EST / UTC-5)</option>
                <option value="America/Chicago (UTC-6)">America/Chicago (CST / UTC-6)</option>
                <option value="America/Los_Angeles (UTC-8)">America/Los_Angeles (PST / UTC-8)</option>
                <option value="UTC">UTC (Coordinated Universal Time)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-neutral-700 dark:text-neutral-300 mb-1">
                Default Landing Route
              </label>
              <select
                value={formData.defaultLanding}
                onChange={(e) => setFormData({ ...formData, defaultLanding: e.target.value })}
                className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-900 dark:border-neutral-800 dark:bg-[#121215] dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="dashboard">/dashboard (Role-aware Overview)</option>
                <option value="campaigns">/campaigns (Campaign Manager View)</option>
                <option value="verifier">/verifier (Verifier Workspace)</option>
                <option value="qa">/qa (QA Review Queue)</option>
                <option value="analytics">/analytics (Business Reports)</option>
                <option value="system">/system (Service Health)</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={isSaving}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-semibold text-white hover:bg-blue-700 transition-colors shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Save className="h-4 w-4" /> {isSaving ? "Saving..." : "Save Profile Changes"}
          </button>
        </div>
      </form>
    </div>
  );
}