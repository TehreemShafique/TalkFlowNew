"use client";

import React, { useState, useMemo } from "react";
import {
  PhoneForwarded,
  Search,
  CheckCircle2,
  AlertTriangle,
  Clock,
  RefreshCw,
  Users,
  ShieldAlert,
  ArrowLeft,
  Activity,
  PhoneCall,
  UserCheck,
  Check,
  X,
  RotateCcw,
  Sliders,
  Radio,
  FileText,
  AlertCircle,
  XCircle,
  Send,
} from "lucide-react";
import { LIVE_TRANSFERS, VERIFIER_POOLS, FAILED_TRANSFERS_QUEUE } from "@/data";
import { apiFetch } from "@/lib/api";

export default function TransfersView({ initialAction, onActionChange }) {
  const [liveTransfersList, setLiveTransfersList] = useState(LIVE_TRANSFERS);
  const [verifierPoolsList, setVerifierPoolsList] = useState(VERIFIER_POOLS);
  const [failedQueue, setFailedQueue] = useState(FAILED_TRANSFERS_QUEUE);

  const [searchQuery, setSearchQuery] = useState("");
  const [poolFilter, setPoolFilter] = useState("all");

  const isFailedMode = initialAction === "failed";

  const navigateToAction = (actionStr) => {
    if (onActionChange) {
      onActionChange(actionStr);
    }
  };

  // Failed Queue handlers
  const handleRetryTransfer = async (failedId) => {
    try {
      await apiFetch(`/transfers/${failedId}/retry`, { method: "POST" });
    } catch (err) {
      console.warn("Retry transfer backend call error:", err);
    }
    setFailedQueue((prev) => prev.filter((item) => item.id !== failedId));
  };

  const handleMarkResolved = async (failedId) => {
    try {
      await apiFetch(`/transfers/${failedId}/create-callback`, {
        method: "POST",
        body: JSON.stringify({ notes: "Marked resolved via dashboard" }),
      });
    } catch (err) {
      console.warn("Create callback backend call error:", err);
    }
    setFailedQueue((prev) => prev.filter((item) => item.id !== failedId));
  };

  // Filtered failed items
  const filteredFailedQueue = useMemo(() => {
    return failedQueue.filter((item) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          item.leadName.toLowerCase().includes(q) ||
          item.phone.toLowerCase().includes(q) ||
          item.campaign.toLowerCase().includes(q) ||
          item.failureReason.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [failedQueue, searchQuery]);

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-6 text-neutral-900 dark:text-neutral-100 font-sans min-h-screen bg-neutral-50 dark:bg-[#050505] transition-colors duration-200">
      {/* ========================================================================= */}
      {/* ROUTE 1: /transfers (Transfer Monitor - Agents) */}
      {/* ========================================================================= */}
      {!isFailedMode && (
        <div className="flex flex-col gap-6">
          {/* Header Title & Top Navigation Actions */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-200 dark:border-neutral-800/80 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-neutral-900 dark:text-white tracking-tight">
                  Transfer Monitor
                </h1>
                <span className="flex items-center gap-1.5 rounded-full bg-blue-100 dark:bg-blue-950/80 border border-blue-300 dark:border-blue-800 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 dark:text-blue-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
                  REAL-TIME HANDSHAKE
                </span>
              </div>
              <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
                Monitor live agent transfers, verifier pool availability, queue wait times, and 3-way handshakes.
              </p>
            </div>

            <button
              type="button"
              onClick={() => navigateToAction("failed")}
              className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-rose-700 transition-colors"
            >
              <AlertTriangle className="h-4 w-4" />
              <span>Failed Recovery Queue</span>
              {failedQueue.length > 0 && (
                <span className="ml-1 rounded-full bg-white/20 px-2 py-0.2 text-[10px] font-extrabold">
                  {failedQueue.length} Failed
                </span>
              )}
            </button>
          </div>

          {/* Quick KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs font-medium text-neutral-500">Active Verifiers Online</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-2xl font-extrabold text-neutral-900 dark:text-white">26 Agents</span>
                <span className="text-xs font-bold text-emerald-600">9 Available</span>
              </div>
            </div>

            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs font-medium text-neutral-500">Avg Queue Wait Time</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-2xl font-extrabold text-blue-600">14 Sec</span>
                <span className="text-[10px] font-bold text-neutral-400">Target &lt; 20s</span>
              </div>
            </div>

            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs font-medium text-neutral-500">Live Active Transfers</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-2xl font-extrabold text-emerald-600">
                  {liveTransfersList.length} Active
                </span>
                <span className="text-xs font-bold text-emerald-600 animate-pulse">● Live</span>
              </div>
            </div>

            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs font-medium text-neutral-500">Transfer Success Rate</span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-2xl font-extrabold text-purple-600">94.2%</span>
                <span className="text-xs font-bold text-emerald-600">+1.8%</span>
              </div>
            </div>
          </div>

          {/* Live Active Transfers Section */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-neutral-900 dark:text-white">
                Live Active Agent Transfer Channels
              </h3>
              <span className="text-xs text-neutral-500 font-mono">
                Showing {liveTransfersList.length} active channels
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {liveTransfersList.map((tx) => (
                <div
                  key={tx.id}
                  className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col justify-between gap-4"
                >
                  <div className="flex flex-col gap-3 text-xs">
                    <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
                      <div className="flex items-center gap-2">
                        <PhoneForwarded className="h-4 w-4 text-blue-600 animate-pulse" />
                        <span className="font-mono font-bold text-neutral-900 dark:text-white">
                          {tx.transferId}
                        </span>
                      </div>
                      <span className="font-bold text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                        {tx.status}
                      </span>
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <div className="flex justify-between">
                        <span className="text-neutral-500">Customer:</span>
                        <span className="font-bold">{tx.leadName} ({tx.phone})</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-500">Campaign:</span>
                        <span className="font-semibold">{tx.campaign}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-500">From Agent:</span>
                        <span className="font-semibold text-purple-600">{tx.fromAgent}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-500">Target Pool:</span>
                        <span className="font-bold text-blue-600">{tx.targetPool}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-500">Assigned Verifier:</span>
                        <span className="font-bold text-emerald-600">{tx.assignedVerifier}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-neutral-500">Transfer Type:</span>
                        <span className="font-semibold">{tx.transferType}</span>
                      </div>
                    </div>

                    <div className="bg-blue-50 dark:bg-blue-950/40 p-3 rounded-lg border border-blue-200 dark:border-blue-800 flex flex-col gap-1 text-[11px]">
                      <span className="font-bold text-blue-700 dark:text-blue-300">
                        Data Passed: {tx.dataPassed}
                      </span>
                      <span className="text-neutral-500">Audio Mode: {tx.audioPass}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Verifier Pools Overview Table */}
          <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
            <h3 className="text-base font-bold text-neutral-900 dark:text-white">
              Verifier Agent Pools Status
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                    <th className="py-2.5 px-3">Pool Name</th>
                    <th className="py-2.5 px-3">Campaign</th>
                    <th className="py-2.5 px-3">Total Verifiers</th>
                    <th className="py-2.5 px-3">Available</th>
                    <th className="py-2.5 px-3">In Call</th>
                    <th className="py-2.5 px-3">Avg Wait Time</th>
                    <th className="py-2.5 px-3">Queue Length</th>
                    <th className="py-2.5 px-3">Success Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {verifierPoolsList.map((pool) => (
                    <tr key={pool.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                      <td className="py-3.5 px-3 font-bold text-blue-600">{pool.name}</td>
                      <td className="py-3.5 px-3 font-semibold">{pool.campaign}</td>
                      <td className="py-3.5 px-3 font-mono font-bold">{pool.activeVerifiers}</td>
                      <td className="py-3.5 px-3 font-bold text-emerald-600">{pool.availableVerifiers}</td>
                      <td className="py-3.5 px-3 font-mono text-neutral-700">{pool.inCallVerifiers}</td>
                      <td className="py-3.5 px-3 font-mono">{pool.avgWaitTimeSec}s</td>
                      <td className="py-3.5 px-3 font-mono font-bold text-amber-600">{pool.queueLength}</td>
                      <td className="py-3.5 px-3 font-extrabold text-purple-600">{pool.transferSuccessRate}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 2: /transfers/failed (Failed Transfer Recovery Queue) */}
      {/* ========================================================================= */}
      {isFailedMode && (
        <div className="flex flex-col gap-6">
          {/* Header Title & Back Button */}
          <div className="flex items-center gap-3 border-b border-neutral-200 dark:border-neutral-800/80 pb-4">
            <button
              type="button"
              onClick={() => navigateToAction(null)}
              className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  Failed Transfer Recovery Queue
                </h2>
                <span className="rounded-full bg-rose-100 text-rose-700 px-2.5 py-0.5 text-xs font-bold border border-rose-300">
                  {failedQueue.length} Pending Recovery
                </span>
              </div>
              <p className="text-xs text-neutral-500">
                Recover failed or dropped call transfer attempts, re-assign verifier pools, or schedule immediate callbacks.
              </p>
            </div>
          </div>

          {/* Search Bar */}
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-neutral-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search lead, phone, failure reason..."
              className="w-full rounded-lg border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] py-2 pl-9 pr-3 text-xs outline-none focus:border-blue-500"
            />
          </div>

          {/* Failed Queue Table */}
          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
            {filteredFailedQueue.length === 0 ? (
              <div className="p-8 text-center text-xs font-semibold text-neutral-500">
                No failed transfer items in queue.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[850px] text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                      <th className="py-2.5 px-3">Transfer ID</th>
                      <th className="py-2.5 px-3">Customer / Phone</th>
                      <th className="py-2.5 px-3">Campaign</th>
                      <th className="py-2.5 px-3">Failed At</th>
                      <th className="py-2.5 px-3">Target Pool</th>
                      <th className="py-2.5 px-3">Failure Reason</th>
                      <th className="py-2.5 px-3">SIP Response</th>
                      <th className="py-2.5 px-3">Attempts</th>
                      <th className="py-2.5 px-3 text-right">Recovery Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                    {filteredFailedQueue.map((item) => (
                      <tr key={item.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                        <td className="py-3.5 px-3 font-mono font-bold text-rose-600">{item.transferId}</td>
                        <td className="py-3.5 px-3">
                          <div className="flex flex-col">
                            <span className="font-bold text-neutral-900 dark:text-white">{item.leadName}</span>
                            <span className="font-mono text-[11px] text-neutral-500">{item.phone}</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-3 font-semibold">{item.campaign}</td>
                        <td className="py-3.5 px-3 text-neutral-500">{item.failedAt}</td>
                        <td className="py-3.5 px-3 font-bold text-blue-600">{item.targetPool}</td>
                        <td className="py-3.5 px-3 font-bold text-rose-600">{item.failureReason}</td>
                        <td className="py-3.5 px-3 font-mono text-neutral-600 dark:text-neutral-400">{item.sipCode}</td>
                        <td className="py-3.5 px-3 font-mono font-bold">{item.retryCount}</td>
                        <td className="py-3.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleRetryTransfer(item.id)}
                              className="px-3 py-1 bg-emerald-600 text-white font-bold rounded-md hover:bg-emerald-700"
                            >
                              Retry Transfer
                            </button>
                            <button
                              type="button"
                              onClick={() => handleMarkResolved(item.id)}
                              className="px-3 py-1 bg-neutral-200 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 font-bold rounded-md hover:bg-neutral-300"
                            >
                              Mark Resolved
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
