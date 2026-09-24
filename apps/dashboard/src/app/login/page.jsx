"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Logo } from "@/components/layout/Logo";
import { useAuth } from "@/context";
import { Button, Input, LoadingSpinner } from "@/components/ui";
import {
  validateLoginForm,
  calculatePasswordStrength,
} from "@/lib/validations/auth";
import {
  Lock,
  Mail,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Headphones,
} from "lucide-react";

export default function LoginPage() {
  const { login, isAuthenticated, loading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      if (typeof window !== "undefined") {
        window.location.href = "/";
      }
    }
  }, [authLoading, isAuthenticated]);

  // Login form state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Common form control states
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});

  const passwordStrength = calculatePasswordStrength(password);

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    setSuccessMsg("");
    setFieldErrors({});

    const validation = validateLoginForm({ email, password });
    if (!validation.success) {
      setFieldErrors(validation.errors);
      setErrorMsg("Please fix the validation errors below.");
      return;
    }

    try {
      setIsSubmitting(true);
      const userPayload = await login(email, password);
      setSuccessMsg(
        `Welcome back, ${userPayload.firstName || userPayload.username}! Redirecting...`
      );
      setTimeout(() => {
        if (typeof window !== "undefined") {
          window.location.href = "/";
        }
      }, 600);
    } catch (err) {
      setErrorMsg(err.message || "Invalid credentials. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center bg-neutral-950 text-white">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen w-full flex-col items-center justify-center bg-neutral-950 px-4 py-8 text-neutral-100 font-sans selection:bg-emerald-500 selection:text-white overflow-y-auto">
      {/* Background Decorative Gradients */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.12),transparent_50%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_bottom_left,rgba(59,130,246,0.1),transparent_50%)]" />

      {/* Main Login Card */}
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-neutral-800 bg-[#0d0d0f]/90 p-6 sm:p-8 shadow-2xl backdrop-blur-xl transition-all my-auto">
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-2">
          <Logo theme="dark" className="mb-3" />
          <h1 className="text-xl font-bold tracking-tight text-white">
            TalkFlow Analytics
          </h1>
          <p className="mt-1 text-xs text-neutral-400">
            Sign in to access your BPO workspace
          </p>
        </div>

        {/* Notifications Banners */}
        {errorMsg && (
          <div className="mt-4 flex items-center gap-2.5 rounded-lg border border-rose-900/50 bg-rose-950/40 p-3 text-xs font-medium text-rose-400 animate-in fade-in-0">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mt-4 flex items-center gap-2.5 rounded-lg border border-emerald-900/50 bg-emerald-950/40 p-3 text-xs font-medium text-emerald-400 animate-in fade-in-0">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Sign In Form */}
        <form onSubmit={handleLoginSubmit} className="mt-6 flex flex-col gap-4" noValidate>
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-neutral-300">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-4 w-4 text-neutral-500" />
              <Input
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (fieldErrors.email) setFieldErrors((prev) => ({ ...prev, email: undefined }));
                }}
                className={`pl-9 !bg-[#121215] !text-white caret-emerald-400 placeholder:text-neutral-500 focus:!border-emerald-500 ${
                  fieldErrors.email ? "border-rose-500 focus:border-rose-500" : "border-neutral-800"
                }`}
              />
            </div>
            {fieldErrors.email && (
              <p className="mt-1 text-[11px] font-medium text-rose-400">{fieldErrors.email}</p>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold text-neutral-300">
                Password
              </label>
              <Link
                href="/forgot-password"
                className="text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 hover:underline transition-colors"
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-neutral-500" />
              <Input
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (fieldErrors.password) setFieldErrors((prev) => ({ ...prev, password: undefined }));
                }}
                className={`pl-9 pr-10 !bg-[#121215] !text-white caret-emerald-400 placeholder:text-neutral-500 focus:!border-emerald-500 ${
                  fieldErrors.password ? "border-rose-500 focus:border-rose-500" : "border-neutral-800"
                }`}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-2.5 text-neutral-500 hover:text-neutral-300 transition-colors"
                title={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {fieldErrors.password && (
              <p className="mt-1 text-[11px] font-medium text-rose-400">{fieldErrors.password}</p>
            )}

            {/* Password Strength Indicator */}
            {password.length > 0 && (
              <div className="mt-2.5 flex flex-col gap-1 rounded-lg border border-neutral-800/80 bg-[#141417] p-2.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-neutral-400 font-medium">Password Strength:</span>
                  <span className={`font-bold ${passwordStrength.textColor}`}>
                    {passwordStrength.label}
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-neutral-800 overflow-hidden mt-0.5">
                  <div
                    className={`h-full transition-all duration-300 ${passwordStrength.color}`}
                    style={{ width: `${passwordStrength.percentage}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          <Button
            type="submit"
            variant="primary"
            size="lg"
            disabled={isSubmitting}
            className="mt-2 w-full font-bold shadow-lg shadow-emerald-600/20"
          >
            {isSubmitting ? (
              <>
                <LoadingSpinner size="sm" className="text-white" />
                <span>Authenticating...</span>
              </>
            ) : (
              <>
                <span>Sign In</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </Button>

          {/* Create Account Link */}
          <div className="mt-4 text-center text-xs text-neutral-400">
            Don't have an account?{" "}
            <Link
              href="/signup"
              className="font-bold text-emerald-400 hover:text-emerald-300 hover:underline transition-colors"
            >
              Create Account
            </Link>
          </div>
        </form>
      </div>

      {/* Footer copyright */}
      <p className="mt-6 text-[11px] text-neutral-500">
        TalkFlow BPO System © 2026 SmartBrains IT Ops
      </p>
    </div>
  );
}
