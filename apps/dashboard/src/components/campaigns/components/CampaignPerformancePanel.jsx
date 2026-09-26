"use client";

import { useState, useEffect, useMemo } from "react";
import { apiFetch } from "@/lib/api";

export default function CampaignPerformancePanel({ campaign }) {
  const [callsList, setCallsList] = useState([]);

  useEffect(() => {
    let isMounted = true;
    async function loadCalls() {
      let calls = [];
      if (typeof window !== "undefined") {
        try {
          const saved = localStorage.getItem("talkflow_calls");
          if (saved) calls = JSON.parse(saved);
        } catch (err) {}
      }
      try {
        // `pageSize` (camelCase) is the registered query key; `page_size` was
        // silently dropped and returned the default 20-row page. The server
        // caps page size at 200, so requesting 500 is a 422 - these stats are
        // computed over the most recent 200 calls.
        const res = await apiFetch("/calls?pageSize=200");
        if (res && res.ok) {
          const json = await res.json();
          const apiCalls = json.data || json.items || [];
          if (apiCalls.length > 0) calls = apiCalls;
        }
      } catch (err) {}

      if (isMounted) {
        setCallsList(calls);
      }
    }

    loadCalls();
    return () => {
      isMounted = false;
    };
  }, []);

  const stats = useMemo(() => {
    if (!campaign) return { callsDialed: "0", contactRate: "0.0%", conversions: "0", conversionRate: "0.0%", avgDuration: "0m 00s" };

    const campIdStr = String(campaign.id).toLowerCase();
    const campNameStr = String(campaign.name || "").toLowerCase();

    // Filter calls for this campaign if campaignId / name matches
    const campaignCalls = callsList.filter(
      (c) =>
        String(c.campaignId || "").toLowerCase() === campIdStr ||
        String(c.campaignName || c.campaign || "").toLowerCase() === campNameStr
    );

    const totalDialed = campaignCalls.length;
    const answeredCalls = campaignCalls.filter(
      (c) => c.status === "answered" || c.status === "in_progress" || c.status === "transferred" || c.status === "completed" || c.disposition
    ).length;
    const contactRateVal = totalDialed > 0 ? ((answeredCalls / totalDialed) * 100).toFixed(1) + "%" : "0.0%";

    const conversionsCount = campaignCalls.filter(
      (c) =>
        c.qualification?.status === "qualified" ||
        String(c.disposition || c.qualificationStatus || "").toLowerCase().includes("qualified") ||
        c.status === "transferred"
    ).length;
    const conversionRateVal = totalDialed > 0 ? ((conversionsCount / totalDialed) * 100).toFixed(1) + "%" : "0.0%";

    const totalSeconds = campaignCalls.reduce((acc, curr) => acc + (curr.durationSeconds || curr.duration_seconds || 0), 0);
    const avgSec = totalDialed > 0 ? Math.round(totalSeconds / totalDialed) : 0;
    const mins = Math.floor(avgSec / 60);
    const secs = avgSec % 60;
    const avgDurationStr = `${mins}m ${secs < 10 ? "0" : ""}${secs}s`;

    return {
      callsDialed: String(totalDialed),
      contactRate: contactRateVal,
      conversions: String(conversionsCount),
      conversionRate: conversionRateVal,
      avgDuration: avgDurationStr,
    };
  }, [campaign, callsList]);

  return (
    <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-6">
      <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
        <div>
          <h3 className="text-base font-bold text-neutral-900 dark:text-white">
            Campaign Real-Time Analytics
          </h3>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            Live telemetry computed from call detail records (CDR) and dialer engine
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 border border-blue-200">
          <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
          Live Telemetry
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
        <div className="flex flex-col gap-1 bg-neutral-50 dark:bg-[#151518] p-4 rounded-lg border border-neutral-200 dark:border-neutral-800">
          <span className="text-neutral-500 font-medium">Total Dialed Calls</span>
          <span className="text-xl font-extrabold text-neutral-900 dark:text-white">
            {stats.callsDialed}
          </span>
        </div>
        <div className="flex flex-col gap-1 bg-neutral-50 dark:bg-[#151518] p-4 rounded-lg border border-neutral-200 dark:border-neutral-800">
          <span className="text-neutral-500 font-medium">Contact Rate</span>
          <span className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400">
            {stats.contactRate}
          </span>
        </div>
        <div className="flex flex-col gap-1 bg-neutral-50 dark:bg-[#151518] p-4 rounded-lg border border-neutral-200 dark:border-neutral-800">
          <span className="text-neutral-500 font-medium">Verified Conversions</span>
          <span className="text-xl font-extrabold text-blue-600 dark:text-blue-400">
            {stats.conversions} ({stats.conversionRate})
          </span>
        </div>
        <div className="flex flex-col gap-1 bg-neutral-50 dark:bg-[#151518] p-4 rounded-lg border border-neutral-200 dark:border-neutral-800">
          <span className="text-neutral-500 font-medium">Avg Handle Time</span>
          <span className="text-xl font-extrabold text-neutral-900 dark:text-white">
            {stats.avgDuration}
          </span>
        </div>
      </div>
    </div>
  );
}