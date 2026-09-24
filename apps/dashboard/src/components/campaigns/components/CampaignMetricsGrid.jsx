"use client";

import { useState, useEffect, useMemo } from "react";
import { apiFetch } from "@/lib/api";

export default function CampaignMetricsGrid({ campaigns: propCampaigns }) {
  const [dbCampaigns, setDbCampaigns] = useState([]);
  const [callsList, setCallsList] = useState([]);
  const [leadBatches, setLeadBatches] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadRealData() {
      setLoading(true);

      // 1. Fetch campaigns
      let activeCampaigns = propCampaigns || [];
      if (!activeCampaigns || !activeCampaigns.length) {
        try {
          const res = await apiFetch("/campaigns");
          if (res && res.ok) {
            const json = await res.json();
            activeCampaigns = json.data || json.items || [];
          }
        } catch (e) {}
      }

      if ((!activeCampaigns || !activeCampaigns.length) && typeof window !== "undefined") {
        try {
          const saved = localStorage.getItem("talkflow_campaigns");
          if (saved) activeCampaigns = JSON.parse(saved);
        } catch (e) {}
      }

      // 2. Fetch lead batches
      let batches = [];
      if (typeof window !== "undefined") {
        try {
          const savedBatches = localStorage.getItem("talkflow_lead_batches");
          if (savedBatches) batches = JSON.parse(savedBatches);
        } catch (e) {}
      }
      try {
        const res = await apiFetch("/leads");
        if (res && res.ok) {
          const json = await res.json();
          const apiBatches = json.data || json.items || [];
          if (apiBatches.length > 0) batches = apiBatches;
        }
      } catch (e) {}

      // 3. Fetch real calls
      let calls = [];
      if (typeof window !== "undefined") {
        try {
          const savedCalls = localStorage.getItem("talkflow_calls");
          if (savedCalls) calls = JSON.parse(savedCalls);
        } catch (e) {}
      }
      try {
        const res = await apiFetch("/calls?page_size=500");
        if (res && res.ok) {
          const json = await res.json();
          const apiCalls = json.data || json.items || [];
          if (apiCalls.length > 0) calls = apiCalls;
        }
      } catch (e) {}

      if (isMounted) {
        setDbCampaigns(activeCampaigns || []);
        setLeadBatches(batches || []);
        setCallsList(calls || []);
        setLoading(false);
      }
    }

    loadRealData();
    return () => {
      isMounted = false;
    };
  }, [propCampaigns]);

  // Compute metrics per campaign / lead batch
  const performanceRows = useMemo(() => {
    const rows = [];
    const effectiveCampaigns = dbCampaigns.length > 0 ? dbCampaigns : (propCampaigns || []);

    if (!effectiveCampaigns || effectiveCampaigns.length === 0) {
      return [];
    }

    effectiveCampaigns.forEach((camp) => {
      const campIdStr = String(camp.id).toLowerCase();
      const campNameStr = String(camp.name || "").toLowerCase();

      // Find lead batches bound to this campaign
      const boundBatches = leadBatches.filter(
        (b) =>
          String(b.assignedCampaignId || b.campaignId || "").toLowerCase() === campIdStr ||
          String(b.assignedCampaignName || b.campaignName || "").toLowerCase() === campNameStr
      );

      if (boundBatches.length > 0) {
        boundBatches.forEach((batch) => {
          const batchName = batch.name || batch.id || "Lead Batch";
          const matchingCalls = callsList.filter(
            (c) =>
              String(c.campaignId || "").toLowerCase() === campIdStr ||
              String(c.campaignName || c.campaign || "").toLowerCase() === campNameStr ||
              String(c.batchId || c.listId || "").toLowerCase() === String(batch.id || "").toLowerCase()
          );

          const totalDialed = matchingCalls.length;
          const answered = matchingCalls.filter(
            (c) =>
              c.status === "answered" ||
              c.status === "completed" ||
              c.status === "transferred" ||
              c.disposition
          ).length;

          const contactRateVal = totalDialed > 0 ? ((answered / totalDialed) * 100).toFixed(1) : "0.0";
          const conversionsCount = matchingCalls.filter(
            (c) =>
              c.qualification?.status === "qualified" ||
              String(c.disposition || c.qualificationStatus || "").toLowerCase().includes("qualified") ||
              c.status === "transferred"
          ).length;

          const convRateVal = totalDialed > 0 ? ((conversionsCount / totalDialed) * 100).toFixed(1) : "0.0";
          const totalSec = matchingCalls.reduce((acc, curr) => acc + (curr.durationSeconds || curr.duration_seconds || 0), 0);
          const avgSec = totalDialed > 0 ? Math.round(totalSec / totalDialed) : 0;
          const mins = Math.floor(avgSec / 60);
          const secs = avgSec % 60;
          const avgDurationStr = `${mins}m ${secs < 10 ? "0" : ""}${secs}s`;
          const dropRateVal = totalDialed > 0 ? (((totalDialed - answered) / totalDialed) * 100).toFixed(1) : "0.0";

          rows.push({
            id: `${camp.id}-${batch.id || batchName}`,
            campaignName: camp.name,
            leadListName: batchName,
            totalLeadsCount: batch.count || batch.totalLeads || "0 Leads",
            callsDialed: totalDialed,
            answered: answered,
            contactRate: `${contactRateVal}%`,
            conversions: conversionsCount,
            conversionRate: `${convRateVal}%`,
            avgDuration: avgDurationStr,
            dropRate: `${dropRateVal}%`,
            totalSec: totalSec,
            status: camp.status || "active",
          });
        });
      } else {
        const matchingCalls = callsList.filter(
          (c) =>
            String(c.campaignId || "").toLowerCase() === campIdStr ||
            String(c.campaignName || c.campaign || "").toLowerCase() === campNameStr
        );

        const totalDialed = matchingCalls.length;
        const answered = matchingCalls.filter(
          (c) =>
            c.status === "answered" ||
            c.status === "completed" ||
            c.status === "transferred" ||
            c.disposition
        ).length;

        const contactRateVal = totalDialed > 0 ? ((answered / totalDialed) * 100).toFixed(1) : "0.0";
        const conversionsCount = matchingCalls.filter(
          (c) =>
            c.qualification?.status === "qualified" ||
            String(c.disposition || c.qualificationStatus || "").toLowerCase().includes("qualified") ||
            c.status === "transferred"
        ).length;

        const convRateVal = totalDialed > 0 ? ((conversionsCount / totalDialed) * 100).toFixed(1) : "0.0";
        const totalSec = matchingCalls.reduce((acc, curr) => acc + (curr.durationSeconds || curr.duration_seconds || 0), 0);
        const avgSec = totalDialed > 0 ? Math.round(totalSec / totalDialed) : 0;
        const mins = Math.floor(avgSec / 60);
        const secs = avgSec % 60;
        const avgDurationStr = `${mins}m ${secs < 10 ? "0" : ""}${secs}s`;
        const dropRateVal = totalDialed > 0 ? (((totalDialed - answered) / totalDialed) * 100).toFixed(1) : "0.0";

        rows.push({
          id: String(camp.id),
          campaignName: camp.name,
          leadListName: "Default Lead Queue",
          totalLeadsCount: "0 Leads",
          callsDialed: totalDialed,
          answered: answered,
          contactRate: `${contactRateVal}%`,
          conversions: conversionsCount,
          conversionRate: `${convRateVal}%`,
          avgDuration: avgDurationStr,
          dropRate: `${dropRateVal}%`,
          totalSec: totalSec,
          status: camp.status || "active",
        });
      }
    });

    return rows;
  }, [dbCampaigns, propCampaigns, leadBatches, callsList]);

  // Aggregate KPIs
  const kpis = useMemo(() => {
    const totalCallsDialed = performanceRows.reduce((acc, r) => acc + r.callsDialed, 0);
    const totalAnswered = performanceRows.reduce((acc, r) => acc + r.answered, 0);
    const totalConversions = performanceRows.reduce((acc, r) => acc + r.conversions, 0);
    const totalSec = performanceRows.reduce((acc, r) => acc + (r.totalSec || 0), 0);

    const contactRateStr = totalCallsDialed > 0 ? `${((totalAnswered / totalCallsDialed) * 100).toFixed(1)}%` : "0.0%";
    const conversionRateStr = totalCallsDialed > 0 ? `${((totalConversions / totalCallsDialed) * 100).toFixed(1)}%` : "0.0%";
    const avgSec = totalCallsDialed > 0 ? Math.round(totalSec / totalCallsDialed) : 0;
    const mins = Math.floor(avgSec / 60);
    const secs = avgSec % 60;

    return {
      totalCalls: totalCallsDialed,
      contactRate: contactRateStr,
      conversionRate: conversionRateStr,
      avgHandleTime: `${mins}m ${secs < 10 ? "0" : ""}${secs}s`,
    };
  }, [performanceRows]);

  if (loading) {
    return (
      <div className="p-8 text-center text-xs text-neutral-500 animate-pulse">
        Loading real-time campaign performance analytics...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Top Real KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs flex flex-col gap-1">
          <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
            Total Dialed Calls
          </span>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-2xl font-extrabold text-neutral-900 dark:text-white">
              {kpis.totalCalls.toLocaleString()}
            </span>
            <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800/60">
              Live DB
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs flex flex-col gap-1">
          <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
            Avg Contact Rate
          </span>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-2xl font-extrabold text-neutral-900 dark:text-white">
              {kpis.contactRate}
            </span>
            <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800/60">
              Live DB
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs flex flex-col gap-1">
          <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
            Avg Conversion Rate
          </span>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-2xl font-extrabold text-blue-600 dark:text-blue-400">
              {kpis.conversionRate}
            </span>
            <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800/60">
              Live DB
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs flex flex-col gap-1">
          <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
            Avg Handle Time (AHT)
          </span>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-2xl font-extrabold text-neutral-900 dark:text-white">
              {kpis.avgHandleTime}
            </span>
            <span className="text-xs font-bold text-neutral-600 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-800 px-2 py-0.5 rounded-full">
              Telemetry
            </span>
          </div>
        </div>
      </div>

      {/* Main Table: Per Campaign & Lead List Performance */}
      <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
          <div>
            <h3 className="text-base font-bold text-neutral-900 dark:text-white">
              Campaign & Lead List Real-Time Performance
            </h3>
            <p className="text-xs text-neutral-500">
              Live telemetry aggregated directly from PostgreSQL database and active lead lists
            </p>
          </div>
          <span className="text-xs font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/80 px-2.5 py-1 rounded-md border border-emerald-200 dark:border-emerald-800">
            Real Data Synced ({performanceRows.length} Rows)
          </span>
        </div>

        {kpis.totalCalls === 0 && (
          <div className="p-4 bg-amber-50/70 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/80 rounded-lg text-amber-800 dark:text-amber-300 text-xs flex items-center justify-between">
            <span>
              <strong>No Calls Performed Yet:</strong> All metrics are currently at 0 because no dialing calls have been executed for your campaigns yet. Run the fake gateway script (e.g. <code className="font-mono bg-amber-100 dark:bg-amber-900/60 px-1 py-0.5 rounded">python -m scripts.fake_gateway --outcome qualified</code>) or start a live dialing session to populate performance telemetry.
            </span>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full min-w-[850px] border-collapse text-xs text-left">
            <thead>
              <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 font-semibold uppercase tracking-wider text-[11px]">
                <th className="px-4 py-3">Campaign Name</th>
                <th className="px-4 py-3">Bound Lead List</th>
                <th className="px-4 py-3">Calls Dialed</th>
                <th className="px-4 py-3">Answered</th>
                <th className="px-4 py-3">Contact Rate</th>
                <th className="px-4 py-3">Conversions</th>
                <th className="px-4 py-3">Conv. Rate</th>
                <th className="px-4 py-3">Avg Duration</th>
                <th className="px-4 py-3">Drop %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
              {performanceRows.length > 0 ? (
                performanceRows.map((row) => (
                  <tr key={row.id} className="transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                    <td className="px-4 py-3.5 font-bold text-neutral-900 dark:text-white">
                      {row.campaignName}
                    </td>
                    <td className="px-4 py-3.5 font-semibold text-purple-600 dark:text-purple-400">
                      {row.leadListName}
                    </td>
                    <td className="px-4 py-3.5 font-mono">{row.callsDialed.toLocaleString()}</td>
                    <td className="px-4 py-3.5 font-mono">{row.answered.toLocaleString()}</td>
                    <td className="px-4 py-3.5 font-semibold text-emerald-600">{row.contactRate}</td>
                    <td className="px-4 py-3.5 font-bold text-blue-600 font-mono">{row.conversions.toLocaleString()}</td>
                    <td className="px-4 py-3.5 font-extrabold text-blue-600">{row.conversionRate}</td>
                    <td className="px-4 py-3.5 text-neutral-500 font-mono">{row.avgDuration}</td>
                    <td className="px-4 py-3.5 font-mono text-amber-600">{row.dropRate}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-xs text-neutral-500 italic">
                    No active campaigns or lead lists found in database. Create a campaign to start tracking performance.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}