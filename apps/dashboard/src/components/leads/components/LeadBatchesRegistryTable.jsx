"use client";

import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  ChevronRight,
  FileSpreadsheet,
  Loader2,
  Trash2,
  XCircle,
} from "lucide-react";

// One badge per execution state. The icon carries the state so the row is
// readable without relying on colour alone.
const VICIDIAL_STATE_META = {
  completed: {
    label: "Completed",
    icon: CheckCircle2,
    className:
      "bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/60",
  },
  running: {
    label: "Running",
    icon: Loader2,
    className:
      "bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800/60",
    spin: true,
  },
  interrupted: {
    label: "Interrupted",
    icon: XCircle,
    className:
      "bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800/60",
  },
  idle: {
    label: "Idle",
    icon: AlertTriangle,
    className:
      "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300 border-neutral-200 dark:border-neutral-700",
  },
};

function VicidialStateBadge({ status }) {
  const meta = VICIDIAL_STATE_META[status] || VICIDIAL_STATE_META.idle;
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-bold ${meta.className}`}
    >
      <Icon className={`h-3.5 w-3.5 ${meta.spin ? "animate-spin" : ""}`} />
      {meta.label}
    </span>
  );
}

function VicidialRunToggle({ batch, busy, onToggle }) {
  const isActive = Boolean(batch.isActiveForVicidial);
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isActive}
      aria-label={`Run ${batch.fileName || batch.file_name || "lead list"} in VICIdial`}
      disabled={busy}
      onClick={(e) => {
        e.stopPropagation();
        onToggle(batch.id, !isActive);
      }}
      className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
        isActive
          ? "bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/60"
          : "bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400 border-neutral-200 dark:border-neutral-700 hover:border-blue-400"
      }`}
    >
      <span
        className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors ${
          isActive ? "bg-emerald-500" : "bg-neutral-300 dark:bg-neutral-600"
        }`}
      >
        <span
          className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
            isActive ? "translate-x-3.5" : "translate-x-0.5"
          }`}
        />
      </span>
      {busy ? "Syncing" : isActive ? "Yes" : "No"}
    </button>
  );
}

export default function LeadBatchesRegistryTable({
  batches,
  activeCampaigns,
  onSelectBatch,
  onAssignCampaign,
  onDeleteBatch,
  onToggleVicidialRun,
  vicidialBusyBatchId,
  vicidialError,
  batchError,
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

        {batchError && (
          <div
            role="alert"
            className="mt-4 flex items-start gap-2 rounded-lg border border-rose-200 dark:border-rose-800/60 bg-rose-50 dark:bg-rose-950/40 px-3 py-2 text-xs font-semibold text-rose-700 dark:text-rose-300"
          >
            <AlertTriangle className="h-4 w-4 shrink-0 mt-px" />
            <span>{batchError}</span>
          </div>
        )}

        {vicidialError && (
          <div
            role="alert"
            className="mt-4 flex items-start gap-2 rounded-lg border border-rose-200 dark:border-rose-800/60 bg-rose-50 dark:bg-rose-950/40 px-3 py-2 text-xs font-semibold text-rose-700 dark:text-rose-300"
          >
            <AlertTriangle className="h-4 w-4 shrink-0 mt-px" />
            <span>{vicidialError}</span>
          </div>
        )}

        <div className="w-full overflow-x-auto mt-4">
          <table className="w-full min-w-[1180px] border-collapse text-xs text-left">
            <thead>
              <tr className="border-b border-neutral-200 dark:border-neutral-800/80 text-neutral-600 dark:text-neutral-400 font-semibold uppercase tracking-wider text-[11px]">
                <th className="px-4 py-3">Batch ID</th>
                <th className="px-4 py-3">File / List Name</th>
                <th className="px-4 py-3">Total Leads</th>
                <th className="px-4 py-3">VICIdial List ID</th>
                <th className="px-4 py-3">Run Count</th>
                <th className="px-4 py-3">VICIdial State</th>
                <th className="px-4 py-3">Run in VICIdial</th>
                <th className="px-4 py-3">Assigned Campaign</th>
                <th className="px-4 py-3">Date Uploaded</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
              {batches.length > 0 ? (
                batches.map((batch) => {
                  const runCount = Number(batch.runCount) || 0;
                  const isBusy = String(vicidialBusyBatchId) === String(batch.id);
                  return (
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
                        {batch.vicidialListId ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 dark:bg-violet-950/60 px-2.5 py-0.5 font-mono font-bold text-violet-700 dark:text-violet-300 border border-violet-200 dark:border-violet-800/60">
                            List {batch.vicidialListId}
                          </span>
                        ) : (
                          <span className="text-neutral-400 dark:text-neutral-500">Not assigned</span>
                        )}
                      </td>

                      <td className="px-4 py-4" onClick={(e) => e.stopPropagation()}>
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 font-mono font-bold border ${
                            runCount > 0
                              ? "bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800/60"
                              : "bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400 border-neutral-200 dark:border-neutral-700"
                          }`}
                        >
                          {runCount} {runCount === 1 ? "Run" : "Runs"}
                        </span>
                      </td>

                      <td className="px-4 py-4">
                        <VicidialStateBadge status={batch.vicidialStatus} />
                      </td>

                      <td className="px-4 py-4" onClick={(e) => e.stopPropagation()}>
                        {onToggleVicidialRun ? (
                          <VicidialRunToggle
                            batch={batch}
                            busy={isBusy}
                            onToggle={onToggleVicidialRun}
                          />
                        ) : (
                          <span className="text-neutral-400">—</span>
                        )}
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
                  );
                })
              ) : (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-neutral-500 dark:text-neutral-400">
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
