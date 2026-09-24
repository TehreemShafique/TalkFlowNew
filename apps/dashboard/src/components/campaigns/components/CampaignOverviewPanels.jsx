"use client";

import { useMemo } from "react";

export default function CampaignOverviewPanels({ campaign }) {
  // Dynamically load real assigned lead batches from localStorage / campaign object
  const leadBatches = useMemo(() => {
    let allBatches = [];
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("talkflow_lead_batches");
        if (saved) allBatches = JSON.parse(saved);
      } catch (err) {}
    }

    // Filter batches assigned to this campaign ID or campaign Name
    const bound = allBatches.filter(
      (b) =>
        String(b.campaignId) === String(campaign.id) ||
        String(b.campaign_id) === String(campaign.id) ||
        String(b.campaignName).toLowerCase() === String(campaign.name).toLowerCase() ||
        String(b.campaign_name).toLowerCase() === String(campaign.name).toLowerCase()
    );

    if (bound.length > 0) {
      return bound.map((b) => ({
        id: b.id,
        name: b.fileName || b.file_name || b.name || b.id,
        count: `${b.totalRows || b.total_rows || (b.parsedLeads ? b.parsedLeads.length : 0)} Leads`,
      }));
    }

    if (campaign.leadBatches && Array.isArray(campaign.leadBatches) && campaign.leadBatches.length > 0) {
      return campaign.leadBatches;
    }

    return [];
  }, [campaign]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* CARD 1: Dialer Configuration Overview */}
      <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
        <h3 className="text-sm font-bold text-neutral-900 dark:text-white border-b border-neutral-100 dark:border-neutral-800 pb-3">
          Dialer Configuration Overview
        </h3>

        <div className="flex flex-col gap-3 text-xs">
          <div className="flex justify-between">
            <span className="text-neutral-500">Dial Mode:</span>
            <span className="font-bold uppercase">{campaign.dialMode}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-500">Pacing Level:</span>
            <span className="font-bold">{campaign.dialLevel}x</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-500">Call Recording:</span>
            <span className="font-bold text-emerald-600">{campaign.recording}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-500">Allocated User Groups:</span>
            <span className="font-semibold">{campaign.userGroups || "Sales_Agents"}</span>
          </div>
        </div>
      </div>

      {/* CARD 2: Bound Script & Target Lead Batches */}
      <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
        <h3 className="text-sm font-bold text-neutral-900 dark:text-white border-b border-neutral-100 dark:border-neutral-800 pb-3">
          Bound Script & Target Leads
        </h3>

        <div className="flex flex-col gap-3 text-xs">
          <div className="flex flex-col gap-0.5 bg-blue-50/60 dark:bg-blue-950/30 p-3 rounded-lg border border-blue-200 dark:border-blue-800">
            <span className="text-[11px] text-blue-600 dark:text-blue-400 font-semibold">Bound Call Script</span>
            <span className="font-bold text-neutral-900 dark:text-white">
              {(campaign.script?.activeScript && campaign.script.activeScript !== "No Script Bound")
                ? campaign.script.activeScript
                : "Medicare Outbound Verification Script"}
            </span>
            <span className="text-[11px] text-neutral-500">
              Version: {(campaign.script?.version && campaign.script.version !== "None") ? campaign.script.version : "v1.0"}
            </span>
          </div>

          <div className="flex flex-col gap-2 bg-emerald-50/60 dark:bg-emerald-950/30 p-3 rounded-lg border border-emerald-200 dark:border-emerald-800">
            <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
              Bound Target Lead Batches ({leadBatches.length})
            </span>
            {leadBatches.length > 0 ? (
              leadBatches.map((batch, idx) => (
                <div key={idx} className="flex flex-col border-b border-emerald-200/60 dark:border-emerald-800/60 last:border-none pb-1 last:pb-0">
                  <span className="font-mono font-bold text-neutral-900 dark:text-white text-[11px]">
                    {batch.name || batch.id}
                  </span>
                  <span className="text-[10px] text-neutral-500">{batch.count || "0 Leads"}</span>
                </div>
              ))
            ) : (
              <span className="text-[11px] text-neutral-500 italic">
                No Lead Batches Assigned yet. Select campaign in Leads tab to bind batches.
              </span>
            )}
          </div>
        </div>
      </div>

      {/* CARD 3: Verifier Transfer Rules Sync */}
      <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
        <h3 className="text-sm font-bold text-neutral-900 dark:text-white border-b border-neutral-100 dark:border-neutral-800 pb-3 flex justify-between items-center">
          <span>Verifier Transfer Rules</span>
          <span className="text-[10px] font-semibold text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/60 px-2 py-0.5 rounded border border-purple-200 dark:border-purple-800">
            {Array.isArray(campaign.transfer?.pools) && campaign.transfer.pools.length > 0
              ? `${campaign.transfer.pools.length} Bound Pool${campaign.transfer.pools.length > 1 ? "s" : ""}`
              : "1 Bound Pool"}
          </span>
        </h3>

        <div className="flex flex-col gap-3 text-xs">
          {Array.isArray(campaign.transfer?.pools) && campaign.transfer.pools.length > 0 ? (
            campaign.transfer.pools.map((p, idx) => (
              <div
                key={p.id || idx}
                className="flex flex-col gap-1 bg-purple-50/60 dark:bg-purple-950/30 p-3 rounded-lg border border-purple-200 dark:border-purple-800"
              >
                <div className="flex justify-between items-center">
                  <span className="text-[11px] text-purple-600 dark:text-purple-400 font-bold">
                    Pool #{idx + 1}: {p.verifierPool}
                  </span>
                </div>
                <div className="flex justify-between text-[10px] text-neutral-600 dark:text-neutral-300 pt-0.5">
                  <span>{p.transferRules || "Warm Transfer (3-Way Bridge)"}</span>
                  <span className="font-semibold text-purple-700 dark:text-purple-300">{p.ringTimeout || "30s"}</span>
                </div>
              </div>
            ))
          ) : (
            <div className="flex flex-col gap-1 bg-purple-50/60 dark:bg-purple-950/30 p-3 rounded-lg border border-purple-200 dark:border-purple-800">
              <span className="text-[11px] text-purple-600 dark:text-purple-400 font-semibold">Primary Verifier Pool</span>
              <span className="font-bold text-neutral-900 dark:text-white">
                {campaign.transfer?.verifierPool || "Licensed QA Verifier Pool"}
              </span>
              <div className="flex justify-between border-t border-purple-200/60 dark:border-purple-800/60 pt-1 text-[10px] text-neutral-600 dark:text-neutral-300">
                <span>{campaign.transfer?.transferRules || "Warm Transfer (3-Way Bridge)"}</span>
                <span className="font-bold">{campaign.transfer?.ringTimeout || "30s"}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* CARD 4: Active SIP Trunks */}
      <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
        <h3 className="text-sm font-bold text-neutral-900 dark:text-white border-b border-neutral-100 dark:border-neutral-800 pb-3">
          Active SIP Trunks
        </h3>

        <div className="flex flex-col gap-3 text-xs">
          <div className="flex flex-col gap-0.5 bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <span className="text-[11px] text-neutral-400 font-medium">Manual Outbound Trunk</span>
            <span className="font-mono font-bold text-blue-600">{campaign.trunks?.manual || "trunk_vici_01"}</span>
          </div>
          <div className="flex flex-col gap-0.5 bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <span className="text-[11px] text-neutral-400 font-medium">Auto Dialer Trunk</span>
            <span className="font-mono font-bold text-blue-600">{campaign.trunks?.auto || "trunk_vici_01"}</span>
          </div>
          <div className="flex flex-col gap-0.5 bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <span className="text-[11px] text-neutral-400 font-medium">3-Way Transfer Trunk</span>
            <span className="font-mono font-bold text-blue-600">{campaign.trunks?.threeWay || "trunk_vici_01"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}