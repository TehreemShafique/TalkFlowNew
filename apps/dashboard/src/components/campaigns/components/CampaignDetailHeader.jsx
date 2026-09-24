"use client";

import { ArrowLeft, Megaphone, Sliders, GitFork, FileCode, ShieldCheck, BarChart3 } from "lucide-react";

export default function CampaignDetailHeader({ campaign, subRoute, onBack, onNavigate, onToggleStatus }) {
  const NAV_CARDS = [
    { id: "overview", label: "Overview", icon: Megaphone, path: campaign.id },
    { id: "dialing", label: "Dialing Settings", icon: Sliders, path: `${campaign.id}/dialing` },
    { id: "routing", label: "Inbound Routing", icon: GitFork, path: `${campaign.id}/routing` },
    { id: "script", label: "Active Script", icon: FileCode, path: `${campaign.id}/script` },
    { id: "transfer", label: "Verifier Transfer", icon: ShieldCheck, path: `${campaign.id}/transfer` },
    { id: "performance", label: "Analytics", icon: BarChart3, path: `${campaign.id}/performance` },
  ];

  const isActive = campaign.status === "active";
  const isPaused = campaign.status === "paused";

  return (
    <>
      {/* Header with Back Button and Campaign Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                {campaign.name}
              </h2>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isActive ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 dark:border-emerald-800/60 bg-emerald-50 dark:bg-emerald-950/70 px-3 py-1 text-xs font-bold text-emerald-700 dark:text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              ACTIVE
            </span>
          ) : isPaused ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-300 dark:border-amber-800/60 bg-amber-50 dark:bg-amber-950/70 px-3 py-1 text-xs font-bold text-amber-700 dark:text-amber-400">
              PAUSED
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-neutral-300 dark:border-neutral-700 bg-neutral-100 dark:bg-neutral-800 px-3 py-1 text-xs font-bold text-neutral-700 dark:text-neutral-300">
              DRAFT
            </span>
          )}

          {onToggleStatus && (
            <button
              type="button"
              onClick={() => onToggleStatus(campaign.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold shadow-xs transition-colors ${
                isActive
                  ? "border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900"
                  : "bg-emerald-600 hover:bg-emerald-700 text-white"
              }`}
            >
              {isActive ? "Pause Campaign" : "Activate Campaign"}
            </button>
          )}
        </div>
      </div>

      {/* Cards Grid for Remaining URLs Navigation */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {NAV_CARDS.map((card) => {
          const Icon = card.icon;
          const isCardActive =
            subRoute === card.id || (subRoute === "overview" && card.id === "overview");

          return (
            <button
              key={card.id}
              type="button"
              onClick={() => onNavigate(card.path)}
              className={`flex flex-col items-center justify-center p-3.5 rounded-xl border text-center transition-all duration-150 gap-2 ${
                isCardActive
                  ? "border-blue-500 bg-blue-50/80 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 font-bold shadow-xs"
                  : "border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] text-neutral-600 dark:text-neutral-400 hover:border-neutral-300 dark:hover:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-[#121215]"
              }`}
            >
              <Icon className="h-5 w-5" />
              <span className="text-xs font-semibold leading-tight">{card.label}</span>
            </button>
          );
        })}
      </div>
    </>
  );
}