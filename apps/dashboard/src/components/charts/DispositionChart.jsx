"use client";

import React, { useState } from "react";
import { PieChart, MoreHorizontal } from "lucide-react";
import { DISPOSITION_DATA } from "@/data";
import { useFilters } from "@/context";

export default function DispositionChart() {
  const [hoveredItem, setHoveredItem] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const { selectedDispositions } = useFilters();

  const handleMouseMove = (e, item) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
    setHoveredItem(item);
  };

  // Filter top dispositions (> 0% or top 9 matching screenshot)
  const displayItems = DISPOSITION_DATA.filter((d) => d.percentage > 0).slice(0, 9);

  return (
    <div className="relative flex h-full w-full flex-col rounded-2xl border border-neutral-200/80 bg-white p-5 shadow-2xs transition-all duration-200 dark:border-[#1a1a1a] dark:bg-[#000000]">
      {/* Header with PieChart icon on left and MoreHorizontal options menu on right */}
      <div className="flex items-center justify-between border-b border-neutral-100 pb-3 dark:border-neutral-800/80 mb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
            <PieChart className="h-4 w-4" />
          </div>
          <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
            Disposition %
          </h3>
        </div>
        <button
          type="button"
          title="More Options"
          className="rounded-lg p-1 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-white transition-colors"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </div>

      <div
        className="relative flex flex-col gap-2.5"
        onMouseLeave={() => setHoveredItem(null)}
      >
        {/* Floating Tooltip */}
        {hoveredItem && (
          <div
            className="pointer-events-none absolute z-50 rounded-xl border border-neutral-200 bg-white/95 px-3 py-2 text-xs shadow-xl backdrop-blur-md transition-all duration-75 dark:border-neutral-800 dark:bg-[#121624]/95"
            style={{
              top: `${mousePos.y + 12}px`,
              left: `${Math.min(Math.max(mousePos.x - 30, 20), 280)}px`,
            }}
          >
            <div className="font-bold text-neutral-900 dark:text-white">
              {hoveredItem.code}
            </div>
            <div className="mt-0.5 font-semibold text-blue-600 dark:text-blue-400">
              Count: {hoveredItem.count.toLocaleString()} ({hoveredItem.percentage.toFixed(1)}%)
            </div>
          </div>
        )}

        {/* Horizontal Progress Bars */}
        {displayItems.map((item) => {
          const isSelected =
            !selectedDispositions ||
            selectedDispositions.length === 0 ||
            selectedDispositions.includes(item.code);

          return (
            <div
              key={item.code}
              onMouseEnter={(e) => handleMouseMove(e, item)}
              onMouseMove={(e) => handleMouseMove(e, item)}
              className={`group relative flex cursor-pointer items-center text-xs transition-opacity duration-150 ${
                isSelected ? "opacity-100" : "opacity-35"
              }`}
            >
              {/* Left Code Label */}
              <span className="w-16 shrink-0 pr-2 text-right text-[11px] font-bold text-neutral-700 transition-colors group-hover:text-blue-600 dark:text-neutral-300 dark:group-hover:text-blue-400">
                {item.code}
              </span>

              {/* Pill Track with Progress Fill */}
              <div className="relative flex flex-1 items-center">
                <div className="h-4 w-full rounded-full bg-neutral-100/90 dark:bg-[#151926] overflow-hidden p-0.5 shadow-inner">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.max(item.percentage, 1.2)}%`,
                      backgroundColor: item.color,
                    }}
                  />
                </div>

                {/* Percentage Text on the Right */}
                <span className="ml-3 w-12 shrink-0 text-right text-[11px] font-bold text-neutral-800 dark:text-neutral-200 font-mono">
                  {item.percentage.toFixed(1)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}