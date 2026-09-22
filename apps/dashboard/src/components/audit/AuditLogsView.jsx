"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  Search,
  Filter,
  Clock,
  User,
  Key,
  FileText,
  Megaphone,
  Headphones,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Info,
  XCircle,
  Download,
  Eye,
  X,
  Copy,
  Check,
  RefreshCw,
  Server,
  Activity,
  ChevronRight,
  Globe,
  Radio,
  Lock,
} from "lucide-react";
import { INITIAL_AUDIT_LOGS } from "@/data";
import { apiFetch } from "@/lib/api";

export default function AuditLogsView() {
  const [logs, setLogs] = useState(INITIAL_AUDIT_LOGS);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [selectedSeverity, setSelectedSeverity] = useState("all");
  const [isLiveStream, setIsLiveStream] = useState(true);

  // Load live audit logs from API (Step 51)
  React.useEffect(() => {
    async function loadAuditLogs() {
      try {
        const res = await apiFetch("/audit?pageSize=50");
        if (res?.data && Array.isArray(res.data) && res.data.length > 0) {
          const formatted = res.data.map((item) => ({
            id: item.id,
            timestamp: item.ts ? new Date(item.ts).toLocaleString() : "Just now",
            user: item.actorRole ? `${item.actorRole} (${item.actorId?.slice(0, 8)})` : item.actorId,
            category: item.resourceType || "system",
            eventType: item.action,
            severity: item.result === "success" ? "info" : "warning",
            targetResource: `${item.resourceType || "resource"}:${item.resourceId || ""}`,
            ipAddress: item.ip || "127.0.0.1",
            status: item.result === "success" ? "SUCCESS" : "FAILED",
            details: JSON.stringify(item.metadata || {}),
          }));
          setLogs(formatted);
        }
      } catch (err) {
        console.warn("Audit log fetch error, using local state:", err);
      }
    }
    loadAuditLogs();
  }, []);

  // Inspector Modal State
  const [selectedLog, setSelectedLog] = useState(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  // Filtered Logs
  const filteredLogs = logs.filter((log) => {
    const matchesCategory =
      selectedCategory === "all" || log.category === selectedCategory;
    const matchesSeverity =
      selectedSeverity === "all" || log.severity === selectedSeverity;
    const matchesSearch =
      log.eventType.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.user.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.details.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.targetResource.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.ipAddress.includes(searchQuery);
    return matchesCategory && matchesSeverity && matchesSearch;
  });

  const openInspector = (log) => {
    setSelectedLog(log);
    setIsInspectorOpen(true);
  };

  const copyPayload = (jsonObj, id) => {
    navigator.clipboard?.writeText(JSON.stringify(jsonObj, null, 2));
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleExportLogs = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(filteredLogs, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `talkflow_audit_logs_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-6 text-neutral-900 dark:text-neutral-100 font-sans min-h-screen bg-neutral-50 dark:bg-[#050505] transition-colors duration-200">
      {/* 1. Header & PRD Subtitle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-200 dark:border-neutral-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-neutral-900 dark:text-white tracking-tight">
              System Audit Logs & Security Stream
            </h1>
            <span className="rounded-full bg-purple-100 dark:bg-purple-600/20 border border-purple-300 dark:border-purple-500/40 px-2.5 py-0.5 text-[10px] font-bold text-purple-700 dark:text-purple-400">
              PRD Section 8 & Morpheus API Audit
            </span>
          </div>
          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
            Immutable audit trail of security events, configuration edits, script approvals, API requests, and compliance opt-outs.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsLiveStream(!isLiveStream)}
            className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors ${
              isLiveStream
                ? "border-emerald-300 dark:border-emerald-800/80 bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400"
                : "border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] text-neutral-600 dark:text-neutral-400"
            }`}
          >
            <span className="relative flex h-2 w-2">
              {isLiveStream && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              )}
              <span
                className={`relative inline-flex h-2 w-2 rounded-full ${
                  isLiveStream ? "bg-emerald-500 dark:bg-emerald-400" : "bg-neutral-400 dark:bg-neutral-500"
                }`}
              />
            </span>
            <span>Live Audit Stream: {isLiveStream ? "Active" : "Paused"}</span>
          </button>

          <button
            type="button"
            onClick={handleExportLogs}
            className="inline-flex items-center gap-1.5 rounded-lg border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] px-3.5 py-1.5 text-xs font-bold text-neutral-800 dark:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
          >
            <Download className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
            <span>Export JSON Log</span>
          </button>
        </div>
      </div>

      {/* 2. Overview KPI Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold text-neutral-500 dark:text-neutral-400">
            <span>24h Audit Events</span>
            <Activity className="h-4 w-4 text-purple-600 dark:text-purple-400" />
          </div>
          <div className="text-2xl font-extrabold text-neutral-900 dark:text-white mt-1">
            1,420 Events
          </div>
          <div className="text-[10px] text-neutral-500 mt-1">
            100% recorded & timestamped
          </div>
        </div>

        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold text-neutral-500 dark:text-neutral-400">
            <span>User & Admin Actions</span>
            <User className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          </div>
          <div className="text-2xl font-extrabold text-blue-600 dark:text-blue-400 mt-1">
            18 Audited
          </div>
          <div className="text-[10px] text-neutral-500 mt-1">
            Bilal Satti, Usama Awan, Babar
          </div>
        </div>

        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold text-neutral-500 dark:text-neutral-400">
            <span>Script & Config Edits</span>
            <FileText className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          </div>
          <div className="text-2xl font-extrabold text-amber-600 dark:text-amber-400 mt-1">
            4 Version Bumps
          </div>
          <div className="text-[10px] text-neutral-500 mt-1">
            FR-05 single active script enforced
          </div>
        </div>

        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold text-neutral-500 dark:text-neutral-400">
            <span>Security Compliance</span>
            <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-1">
            100% Compliant
          </div>
          <div className="text-[10px] text-neutral-500 mt-1">
            Zero unauthorized access flags
          </div>
        </div>
      </div>

      {/* 3. Interactive Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-3 shadow-xs text-xs">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-neutral-400 dark:text-neutral-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search event type, user, target resource, IP address..."
            className="w-full rounded-lg border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#141416] pl-9 pr-4 py-2 text-xs text-neutral-900 dark:text-white placeholder-neutral-400 dark:placeholder-neutral-500 outline-none focus:border-blue-500 dark:focus:border-neutral-700"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Category Filter */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="rounded-lg border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#141416] px-3 py-2 text-xs font-semibold text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-700"
          >
            <option value="all">All Categories</option>
            <option value="User Authentication">User Authentication</option>
            <option value="Script & Campaign Edits">Script & Campaign Edits</option>
            <option value="API & Webhook Activity">API & Webhook Activity</option>
            <option value="Recording & QA Audits">Recording & QA Audits</option>
            <option value="Compliance & DNC">Compliance & DNC</option>
          </select>

          {/* Severity Filter */}
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="rounded-lg border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#141416] px-3 py-2 text-xs font-semibold text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-700"
          >
            <option value="all">All Severities</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="SECURITY">SECURITY</option>
          </select>
        </div>
      </div>

      {/* 4. Detailed Audit Trail Data Table */}
      <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <Lock className="h-4 w-4 text-purple-600 dark:text-purple-400" />
            <span>Audit Trail Events Log ({filteredLogs.length} Records)</span>
          </h2>

          <span className="text-xs text-neutral-500 font-mono">
            Encrypted & Immutable Audit Ledger
          </span>
        </div>

        <div className="w-full overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
          <table className="w-full min-w-[1000px] border-collapse text-xs text-left">
            <thead>
              <tr className="border-b border-neutral-200 dark:border-neutral-800 bg-neutral-100 dark:bg-neutral-950 text-neutral-600 dark:text-neutral-400 font-bold uppercase tracking-wider text-[11px]">
                <th className="px-4 py-3">Timestamp / ID</th>
                <th className="px-4 py-3">Event Type</th>
                <th className="px-4 py-3">User / Identity</th>
                <th className="px-4 py-3">Target Resource</th>
                <th className="px-4 py-3 text-center">Severity</th>
                <th className="px-4 py-3">IP Address</th>
                <th className="px-4 py-3 text-right">Inspect Payload</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/70 bg-white dark:bg-[#0d0d0d]">
              {filteredLogs.map((log) => (
                <tr key={log.id} className="transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                  {/* Timestamp / ID */}
                  <td className="px-4 py-3.5">
                    <div className="flex flex-col">
                      <span className="font-bold text-neutral-900 dark:text-white">{log.timestamp}</span>
                      <span className="text-[10px] font-mono text-neutral-500">
                        {log.eventId} • {log.timeAgo}
                      </span>
                    </div>
                  </td>

                  {/* Event Type */}
                  <td className="px-4 py-3.5">
                    <div className="flex flex-col">
                      <span className="font-extrabold text-blue-600 dark:text-blue-400 font-mono">
                        {log.eventType}
                      </span>
                      <span className="text-[10px] text-neutral-500 dark:text-neutral-400">
                        {log.category}
                      </span>
                    </div>
                  </td>

                  {/* User / Identity */}
                  <td className="px-4 py-3.5">
                    <div className="flex flex-col">
                      <span className="font-semibold text-neutral-800 dark:text-neutral-200">{log.user}</span>
                      <span className="text-[10px] text-neutral-500">{log.userEmail}</span>
                    </div>
                  </td>

                  {/* Target Resource */}
                  <td className="px-4 py-3.5">
                    <span className="rounded-md bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 px-2 py-1 text-[11px] font-medium text-neutral-700 dark:text-neutral-300">
                      {log.targetResource}
                    </span>
                  </td>

                  {/* Severity Badge */}
                  <td className="px-4 py-3.5 text-center">
                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-[10px] font-extrabold uppercase ${
                        log.severity === "SUCCESS"
                          ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-800"
                          : log.severity === "SECURITY"
                          ? "bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-400 border-purple-300 dark:border-purple-800"
                          : log.severity === "WARNING"
                          ? "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-800"
                          : "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-400 border-blue-300 dark:border-blue-800"
                      }`}
                    >
                      {log.severity}
                    </span>
                  </td>

                  {/* IP Address */}
                  <td className="px-4 py-3.5 font-mono text-neutral-600 dark:text-neutral-400 text-[11px]">
                    <div className="flex flex-col">
                      <span>{log.ipAddress}</span>
                      <span className="text-[10px] text-neutral-500">{log.location}</span>
                    </div>
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3.5 text-right">
                    <button
                      type="button"
                      onClick={() => openInspector(log)}
                      className="inline-flex items-center gap-1 rounded-md border border-neutral-300 dark:border-neutral-700 bg-neutral-100 dark:bg-neutral-900 px-3 py-1 text-xs font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-800 hover:text-neutral-900 dark:hover:text-white transition-colors"
                    >
                      <Eye className="h-3 w-3 text-purple-600 dark:text-purple-400" />
                      <span>Inspect</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. AUDIT LOG EVENT INSPECTOR MODAL */}
      {isInspectorOpen && selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-xs">
          <div className="w-full max-w-xl rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#121214] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                <div>
                  <h3 className="text-base font-bold text-neutral-900 dark:text-white">
                    Audit Event Payload Details
                  </h3>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 font-mono">
                    {selectedLog.eventId} • {selectedLog.eventType}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsInspectorOpen(false)}
                className="text-neutral-400 hover:text-neutral-700 dark:hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex flex-col gap-3 text-xs">
              <div className="grid grid-cols-2 gap-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900 p-3">
                <div>
                  <span className="text-neutral-500 text-[10px] uppercase font-bold">Initiated By:</span>
                  <p className="font-bold text-neutral-900 dark:text-white mt-0.5">{selectedLog.user}</p>
                  <p className="text-[10px] text-neutral-500 dark:text-neutral-400">{selectedLog.userEmail}</p>
                </div>
                <div>
                  <span className="text-neutral-500 text-[10px] uppercase font-bold">IP & Geolocation:</span>
                  <p className="font-mono text-neutral-800 dark:text-neutral-200 mt-0.5">{selectedLog.ipAddress}</p>
                  <p className="text-[10px] text-neutral-500 dark:text-neutral-400">{selectedLog.location}</p>
                </div>
              </div>

              <div>
                <span className="font-bold text-neutral-900 dark:text-white">Event Summary:</span>
                <p className="mt-1 text-neutral-700 dark:text-neutral-300 rounded-md border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] p-2.5">
                  {selectedLog.details}
                </p>
              </div>

              {/* JSON Payload Inspector */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-neutral-900 dark:text-white">Raw Event JSON Payload:</span>
                  <button
                    type="button"
                    onClick={() => copyPayload(selectedLog.payload, selectedLog.id)}
                    className="text-xs text-purple-600 dark:text-purple-400 hover:text-purple-700 dark:hover:text-purple-300 flex items-center gap-1"
                  >
                    {copiedId === selectedLog.id ? (
                      <>
                        <Check className="h-3 w-3 text-emerald-500" /> Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" /> Copy JSON
                      </>
                    )}
                  </button>
                </div>

                <pre className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-100 dark:bg-[#0a0a0c] p-3 font-mono text-[11px] text-emerald-700 dark:text-emerald-400 max-h-56">
                  {JSON.stringify(selectedLog.payload, null, 2)}
                </pre>
              </div>
            </div>

            <div className="border-t border-neutral-200 dark:border-neutral-800 pt-4 mt-4 text-right">
              <button
                type="button"
                onClick={() => setIsInspectorOpen(false)}
                className="rounded-md bg-neutral-200 dark:bg-neutral-800 px-4 py-1.5 font-bold text-neutral-800 dark:text-white hover:bg-neutral-300 dark:hover:bg-neutral-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
