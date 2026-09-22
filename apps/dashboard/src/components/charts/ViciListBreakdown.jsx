"use client";

import React, { useState } from "react";
import { ChevronDown } from "lucide-react";
import { DISPOSITION_COLUMNS, DEFAULT_VICI_DATA } from "@/data";

export default function ViciListBreakdown({ data = DEFAULT_VICI_DATA }) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="flex w-full flex-col gap-3">
      {/* Collapsible Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-fit select-none items-center gap-1.5 text-xs font-bold tracking-wider text-neutral-500 transition-colors hover:text-neutral-800 dark:text-neutral-400 dark:hover:text-white"
      >
        <ChevronDown
          className={`h-4 w-4 transition-transform duration-200 ${
            isOpen ? "rotate-0" : "-rotate-90"
          }`}
        />
        <span>DISPOSITION BREAKDOWN BY VICI LIST</span>
      </button>

      {/* Main Table Card Container */}
      {isOpen && (
        <div className="w-full rounded-xl border border-neutral-200 bg-white p-5 shadow-sm transition-colors duration-200 dark:border-[#1a1a1a] dark:bg-[#000000]">
          <h3 className="mb-4 text-sm font-bold text-neutral-800 dark:text-neutral-200">
            Disposition breakdown by Vici List
          </h3>

          {/* Scrollable Container for Wide Table */}
          <div className="w-full overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
            <table className="w-full min-w-[1100px] border-collapse text-xs text-left">
              <thead>
                {/* Header Row 1: Titles and Disposition Categories */}
                <tr className="border-b border-neutral-200 bg-neutral-100/80 text-neutral-700 dark:border-neutral-800 dark:bg-[#121214] dark:text-neutral-300">
                  <th
                    rowSpan={2}
                    className="border-r border-neutral-200 px-4 py-2.5 font-bold dark:border-neutral-800"
                  >
                    Vici List
                  </th>
                  <th
                    rowSpan={2}
                    className="border-r border-neutral-200 px-4 py-2.5 font-bold text-right dark:border-neutral-800"
                  >
                    Total Calls
                  </th>
                  {DISPOSITION_COLUMNS.map((disp, idx) => (
                    <th
                      key={disp}
                      colSpan={2}
                      className={`px-3 py-1.5 text-center font-bold ${
                        idx < DISPOSITION_COLUMNS.length - 1
                          ? "border-r border-neutral-200 dark:border-neutral-800"
                          : ""
                      }`}
                    >
                      {disp}
                    </th>
                  ))}
                </tr>

                {/* Header Row 2: Sub-headers % and # */}
                <tr className="border-b border-neutral-200 bg-neutral-50/90 text-neutral-500 dark:border-neutral-800 dark:bg-[#161618] dark:text-neutral-400">
                  {DISPOSITION_COLUMNS.map((disp, idx) => (
                    <React.Fragment key={`${disp}-sub`}>
                      <th className="px-2 py-1 text-right font-medium">%</th>
                      <th
                        className={`px-2 py-1 text-right font-medium ${
                          idx < DISPOSITION_COLUMNS.length - 1
                            ? "border-r border-neutral-200 dark:border-neutral-800"
                            : ""
                        }`}
                      >
                        #
                      </th>
                    </React.Fragment>
                  ))}
                </tr>
              </thead>

              <tbody>
                {data.map((row) => (
                  <tr
                    key={row.viciList}
                    className="border-b border-neutral-200/70 transition-colors hover:bg-neutral-50 dark:border-neutral-800/70 dark:hover:bg-neutral-900/40"
                  >
                    {/* Vici List ID */}
                    <td className="border-r border-neutral-200 px-4 py-2.5 font-bold text-neutral-900 dark:border-neutral-800 dark:text-neutral-100">
                      {row.viciList}
                    </td>

                    {/* Total Calls */}
                    <td className="border-r border-neutral-200 px-4 py-2.5 text-right font-bold text-neutral-900 dark:border-neutral-800 dark:text-neutral-100">
                      {typeof row.totalCalls === "number"
                        ? row.totalCalls.toLocaleString()
                        : row.totalCalls}
                    </td>

                    {/* Disposition Columns */}
                    {DISPOSITION_COLUMNS.map((disp, idx) => {
                      const val = row.dispositions?.[disp];
                      const isLast = idx === DISPOSITION_COLUMNS.length - 1;

                      return (
                        <React.Fragment key={disp}>
                          {/* Percentage Cell */}
                          <td className="px-2 py-2 text-right text-neutral-500 dark:text-neutral-400">
                            {val ? val.percent : "-"}
                          </td>

                          {/* Count Cell */}
                          <td
                            className={`px-2 py-2 text-right font-bold text-neutral-900 dark:text-neutral-100 ${
                              !isLast
                                ? "border-r border-neutral-200 dark:border-neutral-800"
                                : ""
                            }`}
                          >
                            {val
                              ? typeof val.count === "number"
                                ? val.count.toLocaleString()
                                : val.count
                              : "-"}
                          </td>
                        </React.Fragment>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
