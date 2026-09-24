"use client";

import React, { useState, useMemo } from "react";
import {
  ShieldAlert,
  UploadCloud,
  FileText,
  ArrowLeft,
  Search,
  Trash2,
  ExternalLink,
  ShieldCheck,
  Filter,
} from "lucide-react";

export default function SuppressionListView({
  suppressionList = [],
  suppressionBatches = [],
  selectedSuppressionBatch = null,
  onSelectSuppressionBatch,
  onClearSelectedSuppressionBatch,
  onImportSuppressionFile,
  onDeleteSuppressionBatch,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [filterReason, setFilterReason] = useState("all");

  // Derive suppression lists if suppressionBatches array is empty
  const effectiveBatches = useMemo(() => {
    if (suppressionBatches && suppressionBatches.length > 0) {
      return suppressionBatches;
    }

    // Group items by source
    const groups = {};
    suppressionList.forEach((item) => {
      const src = item.source || item.origin || "Manual Entry";
      if (!groups[src]) {
        groups[src] = {
          id: `supp-batch-${src.toLowerCase().replace(/[^a-z0-9]/g, "-")}`,
          name: src,
          source: src,
          totalCount: 0,
          columns: item.columns || ["phone", "reason", "addedBy", "source", "addedAt", "status"],
          createdAt: item.addedAt || item.added_at || item.createdAt || new Date().toISOString(),
          type: src.includes(".csv") ? "csv" : "auto_extracted",
        };
      }
      groups[src].totalCount += 1;
    });

    return Object.values(groups);
  }, [suppressionBatches, suppressionList]);

  // Filtered records when inspecting a specific list
  const inspectedRecords = useMemo(() => {
    let records = suppressionList;

    if (selectedSuppressionBatch) {
      records = records.filter((r) => {
        const itemSource = r.source || r.origin || "Manual Entry";
        const targetSource = selectedSuppressionBatch.source || selectedSuppressionBatch.name;
        const targetId = selectedSuppressionBatch.id;

        return (
          r.batchId === targetId ||
          itemSource.toLowerCase() === targetSource.toLowerCase() ||
          (r.source && targetSource && targetSource.toLowerCase().includes(r.source.toLowerCase())) ||
          (r.source && selectedSuppressionBatch.name && selectedSuppressionBatch.name.toLowerCase().includes(r.source.toLowerCase()))
        );
      });
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      records = records.filter(
        (r) =>
          (r.phone && String(r.phone).toLowerCase().includes(q)) ||
          (r.reason && String(r.reason).toLowerCase().includes(q)) ||
          (r.source && String(r.source).toLowerCase().includes(q)) ||
          (r.customFields && Object.values(r.customFields).some((v) => String(v).toLowerCase().includes(q)))
      );
    }

    if (filterReason !== "all") {
      records = records.filter(
        (r) => (r.reason || "").toLowerCase() === filterReason.toLowerCase()
      );
    }

    return records;
  }, [suppressionList, selectedSuppressionBatch, searchQuery, filterReason]);

  // Derive dynamic column headers for the selected suppression batch
  const dynamicColumns = useMemo(() => {
    if (selectedSuppressionBatch?.columns && Array.isArray(selectedSuppressionBatch.columns) && selectedSuppressionBatch.columns.length > 0) {
      return selectedSuppressionBatch.columns;
    }
    if (inspectedRecords.length > 0) {
      const keys = new Set();
      inspectedRecords.forEach((rec) => {
        if (rec.customFields) {
          Object.keys(rec.customFields).forEach((k) => keys.add(k));
        }
      });
      if (keys.size > 0) return Array.from(keys);
    }
    return ["phone", "reason", "addedBy", "source", "addedAt", "status"];
  }, [selectedSuppressionBatch, inspectedRecords]);

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white dark:bg-[#0d0d0d] p-4 sm:p-5 rounded-xl border border-neutral-200 dark:border-neutral-800 shadow-xs">
        <div className="flex items-center gap-3">
          {selectedSuppressionBatch && (
            <button
              type="button"
              onClick={onClearSelectedSuppressionBatch}
              className="p-2 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors"
              title="Back to Suppression Lists"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
          )}
          <div>
            <h3 className="text-base font-bold text-neutral-900 dark:text-white flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-rose-600 dark:text-rose-500" />
              <span>
                {selectedSuppressionBatch
                  ? `Suppression List: ${selectedSuppressionBatch.name}`
                  : "DNC & Opt-Out Suppression Registry"}
              </span>
            </h3>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
              {selectedSuppressionBatch
                ? `Showing ${inspectedRecords.length} scrubbed phone numbers with ${dynamicColumns.length} dynamic columns`
                : "Manage bulk CSV suppression files, auto-extracted lead DNC lists, and compliance blocklists"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {selectedSuppressionBatch ? (
            <button
              type="button"
              onClick={onClearSelectedSuppressionBatch}
              className="inline-flex items-center gap-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3.5 py-1.5 text-xs font-bold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>All Suppression Lists</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={onImportSuppressionFile}
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white px-3.5 py-1.5 text-xs font-bold shadow-xs transition-colors"
            >
              <UploadCloud className="h-4 w-4" />
              <span>+ Import Suppression CSV</span>
            </button>
          )}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* VIEW 1: SUPPRESSION LISTS / BATCHES REGISTRY TABLE (When non-selected) */}
      {/* ========================================================================= */}
      {!selectedSuppressionBatch && (
        <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-xs font-bold text-neutral-700 dark:text-neutral-300 uppercase tracking-wider">
              Suppression Lists ({effectiveBatches.length})
            </h4>
            <span className="text-[11px] text-neutral-500 dark:text-neutral-400">
              Total Suppressed Records:{" "}
              <strong className="text-rose-600 dark:text-rose-400 font-mono">
                {suppressionList.length}
              </strong>
            </span>
          </div>

          <div className="w-full overflow-x-auto">
            <table className="w-full min-w-[850px] border-collapse text-xs text-left">
              <thead>
                <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 font-semibold uppercase text-[11px]">
                  <th className="px-4 py-3">Suppression List Name</th>
                  <th className="px-4 py-3">Suppressed Numbers</th>
                  <th className="px-4 py-3">Source / Origin</th>
                  <th className="px-4 py-3">Date Created</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                {effectiveBatches.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-10 text-neutral-500 dark:text-neutral-400">
                      No suppression lists found. Import a lead file or suppression CSV to generate lists.
                    </td>
                  </tr>
                ) : (
                  effectiveBatches.map((batch, idx) => {
                    const rawDate = batch.createdAt || batch.created_at || batch.dateAdded;
                    const dateVal = rawDate ? new Date(rawDate).toLocaleDateString() : "Today";
                    const isAutoExtracted =
                      batch.type === "auto_extracted" ||
                      (batch.name && batch.name.startsWith("DNC -")) ||
                      (batch.source && batch.source.includes("Import"));

                    return (
                      <tr
                        key={`${batch.id || batch.name}-${idx}`}
                        className="transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-900/50 cursor-pointer"
                        onClick={() => onSelectSuppressionBatch && onSelectSuppressionBatch(batch)}
                      >
                        <td className="px-4 py-4 font-bold text-neutral-900 dark:text-white">
                          <div className="flex items-center gap-2">
                            <div
                              className={`p-1.5 rounded-md ${
                                isAutoExtracted
                                  ? "bg-amber-100 text-amber-700 dark:bg-amber-950/80 dark:text-amber-400"
                                  : "bg-rose-100 text-rose-700 dark:bg-rose-950/80 dark:text-rose-400"
                              }`}
                            >
                              <FileText className="h-4 w-4" />
                            </div>
                            <div className="flex flex-col">
                              <span className="hover:underline">{batch.name}</span>
                              {isAutoExtracted && (
                                <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">
                                  Auto-extracted from Lead List
                                </span>
                              )}
                            </div>
                          </div>
                        </td>

                        <td className="px-4 py-4 font-mono font-bold text-rose-600 dark:text-rose-400">
                          {batch.totalCount || batch.importedRows || batch.total_rows || inspectedRecords.length}
                        </td>

                        <td className="px-4 py-4 text-neutral-600 dark:text-neutral-400 font-medium">
                          {batch.source || batch.fileName || "Lead Import"}
                        </td>

                        <td className="px-4 py-4 text-neutral-600 dark:text-neutral-400 font-mono text-[11px]">
                          {dateVal}
                        </td>

                        <td className="px-4 py-4">
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-950/80 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                            <ShieldCheck className="h-3 w-3" />
                            Active Blocklist
                          </span>
                        </td>

                        <td className="px-4 py-4 text-right">
                          <div
                            className="flex items-center justify-end gap-2"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              type="button"
                              onClick={() => onSelectSuppressionBatch && onSelectSuppressionBatch(batch)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-700 dark:text-neutral-300 hover:text-blue-600 dark:hover:text-blue-400 font-semibold transition-colors"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                              <span>View Numbers</span>
                            </button>

                            {onDeleteSuppressionBatch && (
                              <button
                                type="button"
                                onClick={() => onDeleteSuppressionBatch(batch.id)}
                                className="p-1.5 rounded-md text-neutral-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 transition-colors"
                                title="Delete Suppression List"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* VIEW 2: SUPPRESSION LIST RECORDS DRILL-DOWN TABLE WITH DYNAMIC COLUMNS */}
      {/* ========================================================================= */}
      {selectedSuppressionBatch && (
        <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
          {/* Controls Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-neutral-400" />
              <input
                type="text"
                placeholder="Search by phone or record data..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 pl-9 pr-3 py-1.5 text-xs text-neutral-900 dark:text-white placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-rose-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-neutral-500" />
              <select
                value={filterReason}
                onChange={(e) => setFilterReason(e.target.value)}
                className="rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-1.5 text-xs font-medium text-neutral-700 dark:text-neutral-300 focus:outline-none focus:ring-2 focus:ring-rose-500"
              >
                <option value="all">All Reasons</option>
                <option value="dnc">Do Not Call (DNC)</option>
                <option value="opt_out">Opt-Out Request</option>
                <option value="tcpa_litigant">TCPA Litigant</option>
                <option value="invalid">Invalid Phone</option>
              </select>
            </div>
          </div>

          {/* Dynamic Columns Table */}
          <div className="w-full overflow-x-auto">
            <table className="w-full min-w-[800px] border-collapse text-xs text-left">
              <thead>
                <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 font-semibold uppercase text-[11px]">
                  {dynamicColumns.map((colName) => (
                    <th key={colName} className="px-4 py-3 font-mono">
                      {colName.replace(/_/g, " ")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                {inspectedRecords.length === 0 ? (
                  <tr>
                    <td colSpan={dynamicColumns.length} className="text-center py-8 text-neutral-500 dark:text-neutral-400">
                      No suppressed records found in this list matching your criteria.
                    </td>
                  </tr>
                ) : (
                  inspectedRecords.map((dnc, idx) => {
                    return (
                      <tr
                        key={`${dnc.id || dnc.phone || "dnc"}-${idx}`}
                        className="transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-900/50"
                      >
                        {dynamicColumns.map((colName) => {
                          const isPhoneCol = /phone|mobile|cell|contact|tele|number|num/i.test(colName);
                          const isReasonCol = /reason|status/i.test(colName);

                          let rawVal = dnc.customFields?.[colName];
                          if (rawVal === undefined || rawVal === null || rawVal === "") {
                            if (isPhoneCol) rawVal = dnc.phone;
                            else if (colName.toLowerCase().includes("reason")) rawVal = dnc.reason;
                            else if (colName.toLowerCase().includes("source")) rawVal = dnc.source || selectedSuppressionBatch?.name;
                            else if (colName.toLowerCase().includes("added") || colName.toLowerCase().includes("date")) rawVal = dnc.addedAt ? new Date(dnc.addedAt).toLocaleDateString() : "Today";
                            else if (colName.toLowerCase() === "status") rawVal = dnc.status || "Suppressed";
                            else rawVal = dnc[colName];
                          }

                          if (rawVal === undefined || rawVal === null || rawVal === "") rawVal = "—";

                          return (
                            <td
                              key={colName}
                              className={`px-4 py-4 ${
                                isPhoneCol
                                  ? "font-mono font-bold text-rose-600 dark:text-rose-400"
                                  : "text-neutral-800 dark:text-neutral-200 font-medium"
                              }`}
                            >
                              {isReasonCol ? (
                                <span className="inline-flex items-center gap-1 rounded bg-rose-50 dark:bg-rose-950/80 px-2 py-0.5 text-xs font-bold text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-800">
                                  <ShieldAlert className="h-3 w-3" />
                                  {String(rawVal)}
                                </span>
                              ) : (
                                String(rawVal)
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}