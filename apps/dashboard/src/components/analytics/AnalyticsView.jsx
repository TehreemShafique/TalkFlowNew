"use client";

import React, { useState, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import {
  BarChart3,
  Target,
  FileText,
  ListFilter,
  Bot,
  ShieldCheck,
  Activity,
  Download,
  ArrowLeft,
  Search,
  Calendar,
  Clock,
  TrendingUp,
  Zap,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Sparkles,
  Users,
  DollarSign,
  Plus,
  X,
  RefreshCw,
  FileSpreadsheet,
  Cpu,
  Radio,
  PhoneCall,
} from "lucide-react";

// Mock Data Definitions for Analytics Sub-Modules
const MOCK_CAMPAIGN_SUMMARY = [
  { date: "2026-09-12", campaign: "Med Fronter", dialed: 12450, answerRate: "72.4%", qualified: 4120, transferRate: "33.1%", dropRate: "1.2%", revenue: "$370,800" },
  { date: "2026-09-12", campaign: "Solar Outreach East", dialed: 8900, answerRate: "68.1%", qualified: 2150, transferRate: "24.1%", dropRate: "1.8%", revenue: "$193,500" },
  { date: "2026-09-12", campaign: "Insurance Renewals", dialed: 5400, answerRate: "81.0%", qualified: 2430, transferRate: "45.0%", dropRate: "0.8%", revenue: "$218,700" },
  { date: "2026-09-11", campaign: "Med Fronter", dialed: 11800, answerRate: "71.5%", qualified: 3890, transferRate: "32.9%", dropRate: "1.4%", revenue: "$350,100" },
  { date: "2026-09-11", campaign: "Solar Outreach East", dialed: 8600, answerRate: "67.0%", qualified: 2010, transferRate: "23.3%", dropRate: "2.0%", revenue: "$180,900" },
];

const MOCK_SCRIPT_PERFORMANCE = [
  { scriptName: "Medicare Advantage Qualification", version: "v3.2.0", status: "ACTIVE", executions: 18450, consentRate: "99.4%", qualRate: "34.2%", dropNode: "Part B Check (Node 3)", avgDuration: "02:15" },
  { scriptName: "Medicare Advantage Qualification", version: "v3.1.0", status: "APPROVED", executions: 12100, consentRate: "98.9%", qualRate: "31.8%", dropNode: "Greeting Consent", avgDuration: "02:30" },
  { scriptName: "Solar Homeowner Screening", version: "v1.4.0", status: "ACTIVE", executions: 14200, consentRate: "96.5%", qualRate: "25.1%", dropNode: "Roof Shading Check", avgDuration: "01:55" },
  { scriptName: "Inbound Insurance Verification", version: "v2.0.0", status: "ACTIVE", executions: 8900, consentRate: "99.8%", qualRate: "48.5%", dropNode: "Policy ID Verification", avgDuration: "03:10" },
];

const MOCK_LEAD_SOURCES = [
  { source: "HealthcareLeads Direct API", vendor: "HealthcareLeads Inc", ingested: 25000, contactRate: "74.5%", qualYield: "35.8%", dncRate: "0.4%", cpa: "$14.50", roiRating: "EXCELLENT" },
  { source: "Digital Web Inbound Form", vendor: "SmartBrains Digital", ingested: 18400, contactRate: "82.1%", qualYield: "42.0%", dncRate: "0.2%", cpa: "$11.20", roiRating: "OPTIMAL" },
  { source: "CSV Batch Import #109", vendor: "BPO Data Vendors", ingested: 12000, contactRate: "58.2%", qualYield: "19.4%", dncRate: "1.5%", cpa: "$22.80", roiRating: "MODERATE" },
  { source: "Organic Search DID Inbound", vendor: "Organic Campaign", ingested: 9500, contactRate: "91.0%", qualYield: "52.4%", dncRate: "0.1%", cpa: "$8.40", roiRating: "EXCELLENT" },
];

const MOCK_BOT_PERFORMANCE = [
  { metric: "STT Word Error Rate (WER)", value: "1.2%", benchmark: "< 2.5%", status: "OPTIMAL" },
  { metric: "Silero VAD Interruption Rate", value: "2.1%", benchmark: "< 3.0%", status: "HEALTHY" },
  { metric: "Intent Recognition Accuracy", value: "98.6%", benchmark: "> 95.0%", status: "EXCELLENT" },
  { metric: "LLM Out-of-Script Fallback Rate", value: "0.4%", benchmark: "< 1.0%", status: "OPTIMAL" },
  { metric: "Average Bot Conversational Turn", value: "1.8s", benchmark: "< 2.5s", status: "HEALTHY" },
];

const MOCK_COMPLIANCE_LOGS = [
  { id: "cmp-901", rule: "TCPA Recorded Consent Disclosure", checkType: "Verbal Audio Consent", complianceRate: "99.8%", violationsCount: 2, status: "PASSED" },
  { id: "cmp-902", rule: "DNC / Suppression List Verification", checkType: "Real-time DB Lookup", complianceRate: "100.0%", violationsCount: 0, status: "PASSED" },
  { id: "cmp-903", rule: "Calling Hours Window Enforcer", checkType: "Timezone Boundary Check", complianceRate: "100.0%", violationsCount: 0, status: "PASSED" },
  { id: "cmp-904", rule: "Licensed Verifier Handoff Disclosure", checkType: "Script Transfer Node", complianceRate: "99.5%", violationsCount: 4, status: "AUDITED" },
];

const MOCK_LATENCY_METRICS = [
  { component: "AudioSocket RTP Inbound Stream", latencyMs: "12ms", targetMs: "< 20ms", status: "EXCELLENT" },
  { component: "Silero VAD Voice Activity Detection", latencyMs: "25ms", targetMs: "< 40ms", status: "EXCELLENT" },
  { component: "STT Engine (Whisper / Parakeet)", latencyMs: "82ms", targetMs: "< 120ms", status: "HEALTHY" },
  { component: "Script Engine / Rule Evaluator", latencyMs: "18ms", targetMs: "< 30ms", status: "EXCELLENT" },
  { component: "LLM Time-to-First-Token (TTFT)", latencyMs: "138ms", targetMs: "< 200ms", status: "HEALTHY" },
  { component: "TTS Audio Synthesis (Chatterbox)", latencyMs: "65ms", targetMs: "< 100ms", status: "HEALTHY" },
  { component: "Total End-to-End Latency", latencyMs: "340ms", targetMs: "< 500ms", status: "PASS" },
];

const MOCK_EXPORTS = [
  { id: "exp-101", title: "Daily Campaign Conversion Summary CSV", format: "CSV", size: "2.4 MB", dateGenerated: "2026-09-12 01:00", frequency: "Daily Automated", status: "READY" },
  { id: "exp-102", title: "Monthly TCPA Compliance Audit Log", format: "PDF", size: "8.1 MB", dateGenerated: "2026-09-10 18:30", frequency: "Monthly Automated", status: "READY" },
  { id: "exp-103", title: "Lead Source Quality & ROI Breakdown", format: "XLSX", size: "4.5 MB", dateGenerated: "2026-09-08 09:15", frequency: "Weekly Manual", status: "READY" },
  { id: "exp-104", title: "AI Latency & STT Engineering Telemetry", format: "JSON", size: "12.8 MB", dateGenerated: "2026-09-05 12:00", frequency: "Ad-hoc Export", status: "READY" },
];

export default function AnalyticsView({ initialAction, onActionChange }) {
  const [exportsList, setExportsList] = useState(MOCK_EXPORTS);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [newExportTitle, setNewExportTitle] = useState("");
  const [newExportFormat, setNewExportFormat] = useState("CSV");

  // Load server exports & rollups on mount (Step 40)
  React.useEffect(() => {
    async function loadAnalyticsData() {
      try {
        const expRes = await apiFetch("/exports?pageSize=50");
        if (expRes?.data && Array.isArray(expRes.data) && expRes.data.length > 0) {
          const formatted = expRes.data.map((job) => ({
            id: job.id,
            title: `${job.report.toUpperCase()} Report (${job.format.toUpperCase()})`,
            format: job.format.toUpperCase(),
            size: `${job.rowCount || 0} rows`,
            dateGenerated: new Date(job.createdAt).toISOString().slice(0, 16).replace("T", " "),
            frequency: "Server Report Export",
            status: job.status.toUpperCase(),
            downloadUrl: job.downloadUrl,
          }));
          setExportsList(formatted);
        }
      } catch (err) {
        console.warn("Server exports fetch error, using local state:", err);
      }
    }
    loadAnalyticsData();
  }, []);

  // Determine active sub-route from initialAction (e.g. /analytics/campaigns -> 'campaigns')
  const routeInfo = useMemo(() => {
    if (!initialAction || initialAction === "all" || initialAction === "overview") {
      return { mode: "overview" };
    }
    const mode = initialAction.split("/")[0];
    return { mode };
  }, [initialAction]);

  const navigateToAction = (actionStr) => {
    if (onActionChange) {
      onActionChange(actionStr);
    }
  };

  const handleCreateExport = async (e) => {
    e.preventDefault();
    if (!newExportTitle.trim()) return;

    try {
      const res = await apiFetch("/exports", {
        method: "POST",
        body: JSON.stringify({
          report: "calls",
          format: newExportFormat.toLowerCase(),
        }),
      });
      if (res?.data) {
        const job = res.data;
        const newExp = {
          id: job.id,
          title: newExportTitle.trim(),
          format: (job.format || newExportFormat).toUpperCase(),
          size: `${job.rowCount || 0} rows`,
          dateGenerated: new Date().toISOString().slice(0, 16).replace("T", " "),
          frequency: "Ad-hoc Manual Export",
          status: (job.status || "READY").toUpperCase(),
          downloadUrl: job.downloadUrl,
        };
        setExportsList((prev) => [newExp, ...prev]);
      }
    } catch (err) {
      console.warn("Create export API error, local fallback:", err);
      const newExp = {
        id: `exp-${Date.now()}`,
        title: newExportTitle.trim(),
        format: newExportFormat,
        size: "1.2 MB",
        dateGenerated: new Date().toISOString().slice(0, 16).replace("T", " "),
        frequency: "Ad-hoc Manual Export",
        status: "READY",
      };
      setExportsList((prev) => [newExp, ...prev]);
    }

    setIsExportModalOpen(false);
    setNewExportTitle("");
  };

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-6 text-neutral-900 dark:text-neutral-100 font-sans min-h-screen bg-neutral-50 dark:bg-[#050505] transition-colors duration-200">
      {/* ========================================================================= */}
      {/* ROUTE 1: /analytics (Business Overview Main Dashboard) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "overview" && (
        <div className="flex flex-col gap-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-200 dark:border-neutral-800 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-neutral-900 dark:text-white tracking-tight">
                  Analytics & Business Overview
                </h1>
                <span className="rounded-full bg-blue-100 dark:bg-blue-600/20 border border-blue-300 dark:border-blue-500/40 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 dark:text-blue-400">
                  Live Control Plane
                </span>
              </div>
              <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
                High-level campaign performance, transfer conversion rates, revenue tracking, and qualification metrics.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => navigateToAction("exports")}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold text-neutral-800 dark:text-white bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-lg shadow-xs hover:bg-neutral-100 dark:hover:bg-neutral-800"
              >
                <Download className="h-4 w-4 text-blue-500" />
                <span>Export Reports</span>
              </button>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-2">
              <div className="flex items-center justify-between text-neutral-500">
                <span className="text-xs font-semibold">Total Calls Dialed</span>
                <PhoneCall className="h-4 w-4 text-blue-500" />
              </div>
              <span className="text-2xl font-extrabold text-neutral-900 dark:text-white">45,210</span>
              <span className="text-[11px] text-emerald-600 font-bold flex items-center gap-1">
                <TrendingUp className="h-3 w-3" /> +12.4% vs last week
              </span>
            </div>

            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-2">
              <div className="flex items-center justify-between text-neutral-500">
                <span className="text-xs font-semibold">Qualified Transfers</span>
                <Target className="h-4 w-4 text-emerald-500" />
              </div>
              <span className="text-2xl font-extrabold text-emerald-600">14,890</span>
              <span className="text-[11px] text-neutral-500 font-semibold">32.9% Transfer Yield Rate</span>
            </div>

            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-2">
              <div className="flex items-center justify-between text-neutral-500">
                <span className="text-xs font-semibold">Total Sales Revenue</span>
                <DollarSign className="h-4 w-4 text-purple-500" />
              </div>
              <span className="text-2xl font-extrabold text-purple-600">$1,248,500</span>
              <span className="text-[11px] text-emerald-600 font-bold flex items-center gap-1">
                <TrendingUp className="h-3 w-3" /> +8.6% MTD
              </span>
            </div>

            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-2">
              <div className="flex items-center justify-between text-neutral-500">
                <span className="text-xs font-semibold">Bot Resolution Rate</span>
                <Bot className="h-4 w-4 text-blue-500" />
              </div>
              <span className="text-2xl font-extrabold text-blue-600">94.2%</span>
              <span className="text-[11px] text-neutral-500 font-semibold">Zero-Human Bot Handling</span>
            </div>
          </div>

          {/* Quick Sub-Analytics Section Grid */}
          <div className="flex flex-col gap-3">
            <h2 className="text-base font-bold text-neutral-900 dark:text-white">
              Analytics Modules & Reports
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div
                onClick={() => navigateToAction("campaigns")}
                className="cursor-pointer rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs hover:border-blue-500 transition-all flex flex-col justify-between"
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <Target className="h-5 w-5 text-blue-600" />
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-200">
                      /analytics/campaigns
                    </span>
                  </div>
                  <h3 className="text-sm font-bold">Daily Campaign Summary</h3>
                  <p className="text-xs text-neutral-500">Day-by-day metrics across active Medicare & Solar campaigns.</p>
                </div>
                <span className="mt-4 text-xs font-bold text-blue-600 hover:underline">Open Report →</span>
              </div>

              <div
                onClick={() => navigateToAction("scripts")}
                className="cursor-pointer rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs hover:border-blue-500 transition-all flex flex-col justify-between"
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <FileText className="h-5 w-5 text-purple-600" />
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-purple-50 text-purple-600 border border-purple-200">
                      /analytics/scripts
                    </span>
                  </div>
                  <h3 className="text-sm font-bold">Script Performance by Version</h3>
                  <p className="text-xs text-neutral-500">Qualification rates, consent capture, and drop-off nodes per version.</p>
                </div>
                <span className="mt-4 text-xs font-bold text-purple-600 hover:underline">Open Report →</span>
              </div>

              <div
                onClick={() => navigateToAction("sources")}
                className="cursor-pointer rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs hover:border-blue-500 transition-all flex flex-col justify-between"
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <ListFilter className="h-5 w-5 text-emerald-600" />
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-600 border border-emerald-200">
                      /analytics/sources
                    </span>
                  </div>
                  <h3 className="text-sm font-bold">Lead Source Quality</h3>
                  <p className="text-xs text-neutral-500">Vendor quality, contact rates, DNC suppression rates, and ROI yield.</p>
                </div>
                <span className="mt-4 text-xs font-bold text-emerald-600 hover:underline">Open Report →</span>
              </div>

              <div
                onClick={() => navigateToAction("bot")}
                className="cursor-pointer rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs hover:border-blue-500 transition-all flex flex-col justify-between"
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <Bot className="h-5 w-5 text-blue-600" />
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-200">
                      /analytics/bot
                    </span>
                  </div>
                  <h3 className="text-sm font-bold">Bot Performance</h3>
                  <p className="text-xs text-neutral-500">STT accuracy, VAD interruption handling, and turn latency.</p>
                </div>
                <span className="mt-4 text-xs font-bold text-blue-600 hover:underline">Open Report →</span>
              </div>

              <div
                onClick={() => navigateToAction("compliance")}
                className="cursor-pointer rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs hover:border-blue-500 transition-all flex flex-col justify-between"
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <ShieldCheck className="h-5 w-5 text-amber-600" />
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200">
                      /analytics/compliance
                    </span>
                  </div>
                  <h3 className="text-sm font-bold">Compliance Review</h3>
                  <p className="text-xs text-neutral-500">TCPA consent disclosures, opt-outs, and recording policy audits.</p>
                </div>
                <span className="mt-4 text-xs font-bold text-amber-600 hover:underline">Open Report →</span>
              </div>

              <div
                onClick={() => navigateToAction("performance")}
                className="cursor-pointer rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs hover:border-blue-500 transition-all flex flex-col justify-between"
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <Activity className="h-5 w-5 text-rose-600" />
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-50 text-rose-600 border border-rose-200">
                      /analytics/performance
                    </span>
                  </div>
                  <h3 className="text-sm font-bold">AI Latency & Telemetry</h3>
                  <p className="text-xs text-neutral-500">End-to-end timing across STT, Silero VAD, LLM TTFT, and Chatterbox TTS.</p>
                </div>
                <span className="mt-4 text-xs font-bold text-rose-600 hover:underline">Open Report →</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 2: /analytics/campaigns (Daily Campaign Summary) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "campaigns" && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  Daily Campaign Summary
                </h2>
                <p className="text-xs text-neutral-500">
                  Granular day-by-day metrics across active campaigns.
                </p>
              </div>
            </div>
          </div>

          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                    <th className="py-2.5 px-3">Date</th>
                    <th className="py-2.5 px-3">Campaign</th>
                    <th className="py-2.5 px-3">Leads Dialed</th>
                    <th className="py-2.5 px-3">Answer Rate</th>
                    <th className="py-2.5 px-3">Qualified</th>
                    <th className="py-2.5 px-3">Transfer Yield</th>
                    <th className="py-2.5 px-3">Drop Rate</th>
                    <th className="py-2.5 px-3 text-right">Revenue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {MOCK_CAMPAIGN_SUMMARY.map((row, idx) => (
                    <tr key={idx} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                      <td className="py-3 px-3 font-mono text-neutral-500">{row.date}</td>
                      <td className="py-3 px-3 font-bold text-neutral-900 dark:text-white">{row.campaign}</td>
                      <td className="py-3 px-3 font-mono">{row.dialed.toLocaleString()}</td>
                      <td className="py-3 px-3 font-semibold text-blue-600">{row.answerRate}</td>
                      <td className="py-3 px-3 font-bold text-emerald-600">{row.qualified.toLocaleString()}</td>
                      <td className="py-3 px-3 font-bold text-purple-600">{row.transferRate}</td>
                      <td className="py-3 px-3 text-rose-500 font-semibold">{row.dropRate}</td>
                      <td className="py-3 px-3 text-right font-bold text-emerald-600">{row.revenue}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 3: /analytics/scripts (Script Performance by Version) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "scripts" && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  Script Performance by Version
                </h2>
                <p className="text-xs text-neutral-500">
                  Evaluate qualification rates, drop-off nodes, and conversion metrics across script iterations.
                </p>
              </div>
            </div>
          </div>

          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                    <th className="py-2.5 px-3">Script Name</th>
                    <th className="py-2.5 px-3">Version</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Executions</th>
                    <th className="py-2.5 px-3">Consent Capture</th>
                    <th className="py-2.5 px-3">Qual Rate</th>
                    <th className="py-2.5 px-3">Primary Drop Node</th>
                    <th className="py-2.5 px-3 text-right">Avg Handle Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {MOCK_SCRIPT_PERFORMANCE.map((row, idx) => (
                    <tr key={idx} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                      <td className="py-3 px-3 font-bold text-neutral-900 dark:text-white">{row.scriptName}</td>
                      <td className="py-3 px-3 font-mono font-bold text-blue-600">{row.version}</td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700">
                          {row.status}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono">{row.executions.toLocaleString()}</td>
                      <td className="py-3 px-3 font-semibold text-emerald-600">{row.consentRate}</td>
                      <td className="py-3 px-3 font-bold text-purple-600">{row.qualRate}</td>
                      <td className="py-3 px-3 text-rose-500">{row.dropNode}</td>
                      <td className="py-3 px-3 text-right font-mono text-neutral-500">{row.avgDuration}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 4: /analytics/sources (Lead Source Quality) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "sources" && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  Lead Source Quality & ROI
                </h2>
                <p className="text-xs text-neutral-500">
                  Track lead vendors, contact rates, DNC suppression rates, and qualification yields per source.
                </p>
              </div>
            </div>
          </div>

          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                    <th className="py-2.5 px-3">Lead Source Name</th>
                    <th className="py-2.5 px-3">Vendor</th>
                    <th className="py-2.5 px-3">Ingested Leads</th>
                    <th className="py-2.5 px-3">Contact Rate</th>
                    <th className="py-2.5 px-3">Qual Yield</th>
                    <th className="py-2.5 px-3">DNC Rate</th>
                    <th className="py-2.5 px-3">CPA</th>
                    <th className="py-2.5 px-3 text-right">ROI Rating</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {MOCK_LEAD_SOURCES.map((row, idx) => (
                    <tr key={idx} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                      <td className="py-3 px-3 font-bold text-neutral-900 dark:text-white">{row.source}</td>
                      <td className="py-3 px-3 text-neutral-500">{row.vendor}</td>
                      <td className="py-3 px-3 font-mono">{row.ingested.toLocaleString()}</td>
                      <td className="py-3 px-3 font-semibold text-blue-600">{row.contactRate}</td>
                      <td className="py-3 px-3 font-bold text-emerald-600">{row.qualYield}</td>
                      <td className="py-3 px-3 font-mono text-amber-600">{row.dncRate}</td>
                      <td className="py-3 px-3 font-bold text-purple-600">{row.cpa}</td>
                      <td className="py-3 px-3 text-right">
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700">
                          {row.roiRating}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 5: /analytics/bot (Bot Performance) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "bot" && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  Bot Performance & Conversational Metrics
                </h2>
                <p className="text-xs text-neutral-500">
                  STT accuracy, VAD interruption handling, barge-in rates, and LLM response turns.
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {MOCK_BOT_PERFORMANCE.map((item, idx) => (
              <div key={idx} className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex items-center justify-between">
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-bold text-neutral-900 dark:text-white">{item.metric}</span>
                  <span className="text-xs text-neutral-500">Target Benchmark: {item.benchmark}</span>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className="text-xl font-extrabold text-blue-600">{item.value}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700">
                    {item.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 6: /analytics/compliance (Compliance Review) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "compliance" && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  Compliance Review & TCPA Audit
                </h2>
                <p className="text-xs text-neutral-500">
                  TCPA disclaimer verification rate, opt-out processing, recording retention compliance, and violation flags.
                </p>
              </div>
            </div>
          </div>

          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                    <th className="py-2.5 px-3">Compliance Rule</th>
                    <th className="py-2.5 px-3">Check Method</th>
                    <th className="py-2.5 px-3">Compliance Rate</th>
                    <th className="py-2.5 px-3">Violations Count</th>
                    <th className="py-2.5 px-3 text-right">Audit Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {MOCK_COMPLIANCE_LOGS.map((row) => (
                    <tr key={row.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                      <td className="py-3.5 px-3 font-bold text-neutral-900 dark:text-white">{row.rule}</td>
                      <td className="py-3.5 px-3 text-neutral-500">{row.checkType}</td>
                      <td className="py-3.5 px-3 font-bold text-emerald-600">{row.complianceRate}</td>
                      <td className="py-3.5 px-3 font-mono font-bold text-amber-600">{row.violationsCount}</td>
                      <td className="py-3.5 px-3 text-right">
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700">
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 7: /analytics/performance (AI Latency & Engineering Metrics) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "performance" && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  AI Latency & Engineering Telemetry
                </h2>
                <p className="text-xs text-neutral-500">
                  AudioSocket streaming latency, Silero VAD timing, STT latency, LLM time-to-first-token, and TTS synthesis speed.
                </p>
              </div>
            </div>
          </div>

          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                    <th className="py-2.5 px-3">System Subsystem Component</th>
                    <th className="py-2.5 px-3">Measured Latency</th>
                    <th className="py-2.5 px-3">Target Benchmark</th>
                    <th className="py-2.5 px-3 text-right">Telemetry Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {MOCK_LATENCY_METRICS.map((row, idx) => (
                    <tr key={idx} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                      <td className="py-3.5 px-3 font-bold text-neutral-900 dark:text-white">{row.component}</td>
                      <td className="py-3.5 px-3 font-mono font-extrabold text-blue-600">{row.latencyMs}</td>
                      <td className="py-3.5 px-3 font-mono text-neutral-500">{row.targetMs}</td>
                      <td className="py-3.5 px-3 text-right">
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700">
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 8: /analytics/exports (Export History & Scheduled Exports) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "exports" && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  Export History & Scheduled Reports
                </h2>
                <p className="text-xs text-neutral-500">
                  Download historical CSV/JSON analytics reports, configure automated daily/weekly email exports.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setIsExportModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-blue-600 rounded-lg shadow-xs hover:bg-blue-700 transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>Schedule New Export</span>
            </button>
          </div>

          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                    <th className="py-2.5 px-3">Export Job Title</th>
                    <th className="py-2.5 px-3">Format</th>
                    <th className="py-2.5 px-3">File Size</th>
                    <th className="py-2.5 px-3">Date Generated</th>
                    <th className="py-2.5 px-3">Frequency</th>
                    <th className="py-2.5 px-3 text-right">Download</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {exportsList.map((row) => (
                    <tr key={row.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                      <td className="py-3.5 px-3 font-bold text-neutral-900 dark:text-white">{row.title}</td>
                      <td className="py-3.5 px-3 font-mono font-bold text-purple-600">{row.format}</td>
                      <td className="py-3.5 px-3 font-mono text-neutral-500">{row.size}</td>
                      <td className="py-3.5 px-3 text-neutral-500">{row.dateGenerated}</td>
                      <td className="py-3.5 px-3 font-semibold text-blue-600">{row.frequency}</td>
                      <td className="py-3.5 px-3 text-right">
                        <button
                          type="button"
                          onClick={() => alert(`Downloading export: ${row.title}`)}
                          className="inline-flex items-center gap-1 px-3 py-1 text-xs font-bold text-blue-600 bg-blue-50 dark:bg-blue-950/40 rounded border border-blue-200 dark:border-blue-800 hover:bg-blue-100"
                        >
                          <Download className="h-3.5 w-3.5" />
                          <span>Download</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Modal: Schedule Export */}
          {isExportModalOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
              <div className="w-full max-w-md rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-2xl flex flex-col gap-4 text-xs">
                <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3">
                  <h3 className="text-base font-bold text-neutral-900 dark:text-white">
                    Schedule Automated Analytics Export
                  </h3>
                  <button
                    type="button"
                    onClick={() => setIsExportModalOpen(false)}
                    className="p-1 text-neutral-400 hover:text-neutral-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <form onSubmit={handleCreateExport} className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label className="font-bold text-neutral-800 dark:text-neutral-200">
                      Report Title
                    </label>
                    <input
                      type="text"
                      required
                      value={newExportTitle}
                      onChange={(e) => setNewExportTitle(e.target.value)}
                      placeholder="e.g. Weekly Executive Performance Summary"
                      className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none focus:border-blue-500"
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="font-bold text-neutral-800 dark:text-neutral-200">
                      Target Export Format
                    </label>
                    <select
                      value={newExportFormat}
                      onChange={(e) => setNewExportFormat(e.target.value)}
                      className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none"
                    >
                      <option value="CSV">CSV (Comma Separated)</option>
                      <option value="XLSX">Excel Spreadsheet (.xlsx)</option>
                      <option value="JSON">JSON Telemetry Dump</option>
                      <option value="PDF">PDF Report Summary</option>
                    </select>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-200 dark:border-neutral-800">
                    <button
                      type="button"
                      onClick={() => setIsExportModalOpen(false)}
                      className="px-4 py-2 font-semibold text-neutral-600 dark:text-neutral-400 hover:text-neutral-900"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-5 py-2 font-bold text-white bg-blue-600 rounded-md hover:bg-blue-700 shadow-xs"
                    >
                      Generate & Save
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
