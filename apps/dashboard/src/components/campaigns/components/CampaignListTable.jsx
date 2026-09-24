"use client";

import { Search, X, ArrowUpDown, Edit3, Trash2 } from "lucide-react";

export default function CampaignListTable({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  filteredCampaigns,
  totalCampaigns,
  onSort,
  onOpenCampaign,
  onDeleteCampaign,
}) {
  return (
    <div className="flex flex-col gap-5">
      {/* Search & Status Filter Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-neutral-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search campaigns..."
            className="w-full rounded-lg border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] py-1.5 pl-9 pr-3 text-xs text-neutral-900 dark:text-white placeholder-neutral-400 dark:placeholder-neutral-500 outline-none transition-colors focus:border-blue-500 dark:focus:border-neutral-600"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange("")}
              className="absolute right-2.5 top-2.5 text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center rounded-lg border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-1 text-xs shadow-xs">
          <button
            type="button"
            onClick={() => onStatusFilterChange("all")}
            className={`rounded-md px-3 py-1 font-semibold transition-colors ${
              statusFilter === "all"
                ? "bg-blue-600 dark:bg-[#253246] text-white shadow-xs"
                : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
            }`}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => onStatusFilterChange("active")}
            className={`rounded-md px-3 py-1 font-semibold transition-colors ${
              statusFilter === "active"
                ? "bg-blue-600 dark:bg-[#253246] text-white shadow-xs"
                : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
            }`}
          >
            Active
          </button>
          <button
            type="button"
            onClick={() => onStatusFilterChange("inactive")}
            className={`rounded-md px-3 py-1 font-semibold transition-colors ${
              statusFilter === "inactive"
                ? "bg-blue-600 dark:bg-[#253246] text-white shadow-xs"
                : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
            }`}
          >
            Inactive
          </button>
        </div>
      </div>

      {/* Main Table Card - Clicking Row redirects to /campaigns/[campaignId] */}
      <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
        <div className="w-full overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-xs text-left">
            <thead>
              <tr className="border-b border-neutral-200 dark:border-neutral-800/80 text-neutral-600 dark:text-neutral-400 font-semibold uppercase tracking-wider text-[11px]">
                <th
                  onClick={() => onSort("name")}
                  className="px-4 py-3 cursor-pointer select-none hover:text-neutral-900 dark:hover:text-white"
                >
                  <div className="flex items-center gap-1">
                    <span>Campaign Name</span>
                    <ArrowUpDown className="h-3 w-3 opacity-60" />
                  </div>
                </th>
                <th
                  onClick={() => onSort("dialMode")}
                  className="px-4 py-3 cursor-pointer select-none hover:text-neutral-900 dark:hover:text-white"
                >
                  <div className="flex items-center gap-1">
                    <span>Dial Mode</span>
                    <ArrowUpDown className="h-3 w-3 opacity-60" />
                  </div>
                </th>
                <th
                  onClick={() => onSort("status")}
                  className="px-4 py-3 cursor-pointer select-none hover:text-neutral-900 dark:hover:text-white"
                >
                  <div className="flex items-center gap-1">
                    <span>Status</span>
                    <ArrowUpDown className="h-3 w-3 opacity-60" />
                  </div>
                </th>
                <th
                  onClick={() => onSort("dialLevel")}
                  className="px-4 py-3 cursor-pointer select-none hover:text-neutral-900 dark:hover:text-white"
                >
                  <div className="flex items-center gap-1">
                    <span>Dial Level</span>
                    <ArrowUpDown className="h-3 w-3 opacity-60" />
                  </div>
                </th>
                <th className="px-4 py-3">Trunks</th>
                <th className="px-4 py-3">Recording</th>
                <th className="px-4 py-3">User Groups</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
              {filteredCampaigns.map((camp) => (
                <tr
                  key={camp.id}
                  onClick={() => onOpenCampaign(camp.id)}
                  className="cursor-pointer transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-900/50"
                >
                  <td className="px-4 py-4 font-bold text-blue-600 dark:text-blue-400 hover:underline max-w-[180px] break-words">
                    {camp.name}
                  </td>
                  <td className="px-4 py-4">
                    <span className="inline-flex items-center rounded-full border border-neutral-300 dark:border-neutral-700/80 bg-neutral-100 dark:bg-neutral-800/80 px-2.5 py-0.5 text-xs text-neutral-700 dark:text-neutral-300 font-medium">
                      {camp.dialMode}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    {camp.status === "active" && (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 dark:border-emerald-800/60 bg-emerald-50 dark:bg-emerald-950/70 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        active
                      </span>
                    )}
                    {camp.status === "paused" && (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-300 dark:border-amber-800/60 bg-amber-50 dark:bg-amber-950/70 px-2.5 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-400">
                        paused
                      </span>
                    )}
                    {camp.status === "draft" && (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-neutral-300 dark:border-neutral-700 bg-neutral-100 dark:bg-neutral-800/90 px-2.5 py-0.5 text-xs font-semibold text-neutral-700 dark:text-neutral-300">
                        draft
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-4 font-semibold text-neutral-900 dark:text-white">
                    {camp.dialLevel}
                  </td>
                  <td className="px-4 py-4 font-mono text-[11px] text-neutral-700 dark:text-neutral-300">
                    {camp.trunks.manual}
                  </td>
                  <td className="px-4 py-4">
                    <span className="inline-flex items-center rounded-full border border-emerald-200 dark:border-emerald-800/60 bg-emerald-50 dark:bg-emerald-950/60 px-2.5 py-0.5 text-xs font-bold text-emerald-700 dark:text-emerald-400">
                      {camp.recording}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-neutral-500 dark:text-neutral-400">
                    {camp.userGroups}
                  </td>
                  <td className="px-4 py-4 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenCampaign(camp.id);
                        }}
                        className="inline-flex items-center gap-1 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-2.5 py-1 text-xs font-semibold text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
                        title="Edit & View Campaign"
                      >
                        <Edit3 className="h-3 w-3 text-blue-500" />
                        <span>Edit / View</span>
                      </button>

                      {onDeleteCampaign && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteCampaign(camp.id);
                          }}
                          className="inline-flex items-center gap-1 rounded-md border border-red-200 dark:border-red-900/60 bg-red-50 dark:bg-red-950/50 px-2 py-1 text-xs font-semibold text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/80 transition-colors"
                          title="Delete Campaign"
                        >
                          <Trash2 className="h-3 w-3" />
                          <span>Delete</span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-800/60 text-center text-xs font-medium text-neutral-500 dark:text-neutral-400">
          Showing {filteredCampaigns.length} of {totalCampaigns} campaigns
        </div>
      </div>
    </div>
  );
}