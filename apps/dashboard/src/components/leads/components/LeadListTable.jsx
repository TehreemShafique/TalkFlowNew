"use client";

import React, { useMemo } from "react";
import { Search, X, ArrowUpDown, Phone, Mail, CheckCircle, ShieldAlert, ChevronLeft, ChevronRight, FileSpreadsheet } from "lucide-react";

export default function LeadListTable({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  onSort,
  filteredLeads,
  leads,
  onSelectLead,
  page = 1,
  pageSize = 10,
  totalLeads = 0,
  totalPages = 1,
  onNextPage,
  onPrevPage,
  onPageSizeChange,
  selectedBatch,
  batchColumns = [],
}) {
  const startCount = totalLeads === 0 ? 0 : (page - 1) * pageSize + 1;
  const endCount = Math.min(page * pageSize, totalLeads);

  // Auto-detect dynamic headers based strictly on uploaded CSV file's header schema
  const effectiveColumns = useMemo(() => {
    if (batchColumns && batchColumns.length > 0) {
      return batchColumns;
    }
    if (leads && leads.length > 0) {
      const keys = new Set();
      leads.forEach((l) => {
        if (l.customFields) {
          Object.keys(l.customFields).forEach((k) => keys.add(k));
        }
      });
      if (keys.size > 0) {
        return ["Phone", "First Name", "Last Name", "State", "DOB", "Status", ...Array.from(keys)];
      }
    }
    return ["Phone", "First Name", "Last Name", "State", "DOB", "Status"];
  }, [batchColumns, leads]);

  return (
    <div className="flex flex-col gap-5">
      {selectedBatch && (
        <div className="flex items-center justify-between p-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/60 text-xs">
          <div className="flex items-center gap-2 text-blue-700 dark:text-blue-300 font-semibold">
            <FileSpreadsheet className="h-4 w-4" />
            <span>Active Lead File: {selectedBatch.fileName || selectedBatch.file_name || "Selected Lead List"}</span>
          </div>
          <span className="font-bold text-blue-600 dark:text-blue-400">
            Auto-detected {effectiveColumns.length} Dynamic Columns
          </span>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-neutral-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by lead name, phone, email..."
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

        <div className="flex items-center overflow-x-auto rounded-lg border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-1 text-xs shadow-xs">
          {["all", "new", "contacted", "qualified", "converted", "unreachable", "dnc"].map(
            (st) => (
              <button
                key={st}
                type="button"
                onClick={() => onStatusFilterChange(st)}
                className={`capitalize rounded-md px-3 py-1 font-semibold transition-colors ${
                  statusFilter === st
                    ? "bg-blue-600 dark:bg-[#253246] text-white shadow-xs"
                    : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
                }`}
              >
                {st}
              </button>
            )
          )}
        </div>
      </div>

      <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
        <div className="w-full overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-xs text-left">
            <thead>
              <tr className="border-b border-neutral-200 dark:border-neutral-800/80 text-neutral-600 dark:text-neutral-400 font-semibold uppercase tracking-wider text-[11px]">
                {effectiveColumns.map((colName) => (
                  <th key={colName} className="px-4 py-3 font-mono">
                    <div className="flex items-center gap-1">
                      <span>{colName}</span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
              {filteredLeads.map((lead) => (
                <tr
                  key={lead.id}
                  onClick={() => onSelectLead(lead.id)}
                  className="cursor-pointer transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-900/50"
                >
                  {effectiveColumns.map((col) => {
                    const lowerCol = col.toLowerCase();
                    let val = lead.customFields?.[col] || lead.customFields?.[lowerCol];

                    if (val === undefined || val === null || val === "") {
                      if (/first.*name|^first$/i.test(col)) val = lead.firstName || lead.first_name;
                      else if (/last.*name|^last$/i.test(col)) val = lead.lastName || lead.last_name;
                      else if (/name/i.test(col)) val = `${lead.firstName || ""} ${lead.lastName || ""}`.trim();
                      else if (/phone|mobile|cell/i.test(col)) val = lead.phone;
                      else if (/email/i.test(col)) val = lead.email;
                      else if (/state/i.test(col)) val = lead.state;
                      else if (/dob|birth/i.test(col)) val = lead.dateOfBirth || lead.date_of_birth;
                      else if (/zip|postal/i.test(col)) val = lead.zipCode || lead.zip_code;
                      else if (/campaign/i.test(col)) val = lead.campaign;
                      else if (/status/i.test(col)) val = lead.status;
                      else if (/id/i.test(col)) val = String(lead.id).slice(0, 8);
                      else val = "—";
                    }

                    if (val === undefined || val === null || val === "") val = "—";

                    return (
                      <td key={col} className="px-4 py-4 font-mono text-neutral-800 dark:text-neutral-200">
                        {String(val)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* PAGINATION CONTROLS FOOTER */}
        <div className="mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-800/60 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-medium text-neutral-500 dark:text-neutral-400">
          <div>
            Showing <span className="font-semibold text-neutral-900 dark:text-white">{startCount}</span>–
            <span className="font-semibold text-neutral-900 dark:text-white">{endCount}</span> of{" "}
            <span className="font-semibold text-neutral-900 dark:text-white">{totalLeads.toLocaleString()}</span> leads
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span>Per page:</span>
              <select
                value={pageSize}
                onChange={(e) => onPageSizeChange && onPageSizeChange(Number(e.target.value))}
                className="rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-2 py-1 text-xs font-medium text-neutral-900 dark:text-white outline-none"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={onPrevPage}
                className="inline-flex items-center justify-center h-8 w-8 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-700 dark:text-neutral-200 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              <span className="text-xs font-semibold text-neutral-900 dark:text-white px-1">
                Page {page} of {totalPages}
              </span>

              <button
                type="button"
                disabled={page >= totalPages}
                onClick={onNextPage}
                className="inline-flex items-center justify-center h-8 w-8 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-700 dark:text-neutral-200 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}