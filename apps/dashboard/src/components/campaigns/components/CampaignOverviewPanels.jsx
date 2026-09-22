"use client";

export default function CampaignOverviewPanels({ campaign }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
            <span className="text-neutral-500">AMD Machine Detection:</span>
            <span className="font-bold text-emerald-600">{campaign.amd}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-500">AMD Action:</span>
            <span className="font-semibold">{campaign.amdSub || "Standard"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-500">Call Recording:</span>
            <span className="font-bold text-emerald-600">{campaign.recording}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-500">Allocated User Groups:</span>
            <span className="font-semibold">{campaign.userGroups}</span>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
        <h3 className="text-sm font-bold text-neutral-900 dark:text-white border-b border-neutral-100 dark:border-neutral-800 pb-3">
          Active SIP Trunks
        </h3>

        <div className="flex flex-col gap-3 text-xs">
          <div className="flex flex-col gap-0.5 bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <span className="text-[11px] text-neutral-400 font-medium">Manual Outbound Trunk</span>
            <span className="font-mono font-bold text-blue-600">{campaign.trunks.manual}</span>
          </div>
          <div className="flex flex-col gap-0.5 bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <span className="text-[11px] text-neutral-400 font-medium">Auto Dialer Trunk</span>
            <span className="font-mono font-bold text-blue-600">{campaign.trunks.auto}</span>
          </div>
          <div className="flex flex-col gap-0.5 bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <span className="text-[11px] text-neutral-400 font-medium">3-Way Transfer Trunk</span>
            <span className="font-mono font-bold text-blue-600">{campaign.trunks.threeWay}</span>
          </div>
        </div>
      </div>
    </div>
  );
}