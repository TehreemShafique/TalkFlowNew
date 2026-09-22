"use client";

import React from "react";
import { Download } from "lucide-react";

export default function SubHeader({ onExportCalls, onExportSales }) {
  return (
    <div className="flex flex-col gap-3 border-b border-neutral-200/60 bg-[#f8fafc]/50 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 dark:border-[#141414] dark:bg-[#000000]">
      {/* Title & Subtitle */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-white flex items-center gap-2">
          <span>Smart Brains</span>
          <span className="text-[#0059DD] font-extrabold">Dashboard</span>
        </h1>
        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5 font-medium">
          Real-time insights. Better decisions.
        </p>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onExportCalls}
          className="flex items-center gap-2 rounded-xl border border-[#0059DD]/40 bg-white px-4 py-2 text-xs font-bold text-[#0059DD] shadow-2xs transition-all hover:bg-blue-50/60 active:scale-95 dark:border-[#0059DD]/60 dark:bg-[#000000] dark:text-[#0059DD] dark:hover:bg-blue-950/30"
        >
          <Download className="h-4 w-4 text-[#0059DD]" />
          <span>Export Calls</span>
        </button>

        <button
          type="button"
          onClick={onExportSales}
          className="flex items-center gap-2 rounded-xl bg-[#0059DD] px-4 py-2 text-xs font-bold text-white shadow-md shadow-[#0059DD]/20 transition-all hover:bg-[#004bbd] active:scale-95 dark:bg-[#0059DD] dark:hover:bg-[#004bbd]"
        >
          <Download className="h-4 w-4 text-white" />
          <span>Export XFERs/Sales</span>
        </button>
      </div>
    </div>
  );
}