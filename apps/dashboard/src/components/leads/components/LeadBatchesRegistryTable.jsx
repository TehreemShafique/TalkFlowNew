"use client";

import { FileSpreadsheet, Calendar, Trash2, ChevronRight } from "lucide-react";

export default function LeadBatchesRegistryTable({
  batches,
  activeCampaigns,
  onSelectBatch,
  onAssignCampaign,
  onDeleteBatch,
}) {
  return (
    <div className="flex flex-col gap-5">
      <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
        <div className="flex items-center justify-between pb-4 border-b border-neutral-200 dark:border-neutral-800">
          <div>
            <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-2">
              <FileSpreadsheet className="h-4 w-4 text-blue-600 dark:text-blue-400" />
              <span>Imported Lead Files Registry</span>
            </h3>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
              Click any lead file row to view its records or assign real-time active campaigns
            </p>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800/60">
            {batches.length} {batches.length === 1 ? "File Batch" : "File Batches"} Registered
          </span>
        </div>

        <div className="w-full overflow-x-auto mt-4">
          <table className="w-full min-w-[750px] border-collapse text-xs text-left">
            <thead>
              <tr className="border-b border-neutral-200 dark:border-neutral-800/80 text-neutral-600 dark:text-neutral-400 font-semibold uppercase tracking-wider text-[11px]">
                <th className="px-4 py-3">Batch ID</th>
                <th className="px-4 py-3">File / List Name</th>
                <th className="px-4 py-3">Total Leads</th>
                <th className="px-4 py-3">Assigned Campaign</th>
                <th className="px-4 py-3">Date Uploaded</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
              {batches.length > 0 ? (
                batches.map((batch) => (
                  <tr
                    key={batch.id}
                    onClick={() => onSelectBatch(batch)}
                    className="hover:bg-blue-50/40 dark:hover:bg-neutral-900/60 transition-colors cursor-pointer group"
                  >
                    <td className="px-4 py-4 font-mono font-bold text-blue-600 dark:text-blue-400 group-hover:underline">
                      {String(batch.id).slice(0, 8)}...
                    </td>

                    <td className="px-4 py-4 font-bold text-neutral-900 dark:text-white">
                      <div className="flex items-center gap-2">
                        <FileSpreadsheet className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                        <span className="group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                          {batch.fileName || batch.file_name || "lead_batch.csv"}
                        </span>
                      </div>
                    </td>

                    <td className="px-4 py-4 font-semibold text-neutral-800 dark:text-neutral-200">
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-neutral-100 dark:bg-neutral-800 font-mono font-bold">
                        {(batch.importedRows || batch.totalRows || batch.total_rows || 0).toLocaleString()} Leads
                      </span>
                    </td>

                    <td className="px-4 py-4" onClick={(e) => e.stopPropagation()}>
                      <select
                        value={batch.campaignId || batch.campaign_id || ""}
                        onChange={(e) => onAssignCampaign(batch.id, e.target.value || null)}
                        className="rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-[#121215] py-1.5 px-2.5 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500 transition-colors cursor-pointer"
                      >
                        <option value="">-- Assign Active Campaign --</option>
                        {activeCampaigns.map((camp) => (
                          <option key={camp.id} value={camp.id}>
                            {camp.name} ({camp.status})
                          </option>
                        ))}
                      </select>
                    </td>

                    <td className="px-4 py-4 text-neutral-500 dark:text-neutral-400 text-[11px]">
                      <div className="flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 opacity-60" />
                        <span>{batch.createdAt ? new Date(batch.createdAt).toLocaleDateString() : "Recently"}</span>
                      </div>
                    </td>

                    <td className="px-4 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => onSelectBatch(batch)}
                          className="inline-flex items-center gap-1 rounded-md bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 hover:bg-blue-600 hover:text-white dark:hover:bg-blue-600 px-2.5 py-1 text-xs font-bold transition-all"
                          title="View Lead List"
                        >
                          <span>View List</span>
                          <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (onDeleteBatch) onDeleteBatch(batch.id);
                          }}
                          className="p-1.5 rounded-md text-neutral-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
                          title="Delete Lead List Batch"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-neutral-500 dark:text-neutral-400">
                    No lead file batches registered yet. Upload a CSV list using the Import Wizard.
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
