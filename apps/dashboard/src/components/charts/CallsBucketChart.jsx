"use client";

import React, { useState } from "react";
import { ChevronDown } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { GENERATE_DEFAULT_BUCKETS } from "@/data";

// Custom Tooltip matching screenshot style
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="pointer-events-none z-50 rounded-lg border border-neutral-700/80 bg-[#161618] px-3.5 py-2 text-xs shadow-2xl backdrop-blur-md">
        <div className="font-semibold text-neutral-300">{label}</div>
        <div className="mt-0.5 font-medium text-cyan-400">
          Calls : {payload[0].value?.toLocaleString()}
        </div>
      </div>
    );
  }
  return null;
};

export default function CallsBucketChart({ data = GENERATE_DEFAULT_BUCKETS() }) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="flex w-full flex-col gap-3">
      {/* Collapsible Header */}
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
        <span>CALLS PER 5-MINUTE BUCKET</span>
      </button>

      {/* Main Chart Container */}
      {isOpen && (
        <div className="w-full rounded-xl border border-neutral-200 bg-white p-5 shadow-sm transition-colors duration-200 dark:border-[#1a1a1a] dark:bg-[#000000]">
          <h3 className="mb-4 text-sm font-bold text-neutral-800 dark:text-neutral-200">
            Calls per 5-minute bucket
          </h3>

          {/* Responsive container with horizontal scroll protection for mobile */}
          <div className="w-full overflow-x-auto">
            <div className="h-72 min-w-[760px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data}
                  margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
                  barCategoryGap={1.5}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="#262626"
                    opacity={0.3}
                  />
                  <XAxis
                    dataKey="time"
                    stroke="#737373"
                    tick={{ fontSize: 10, fill: "#737373" }}
                    tickLine={false}
                    axisLine={{ stroke: "#262626" }}
                    interval={5} // Displays evenly spaced interval labels
                  />
                  <YAxis
                    domain={[0, 3800]}
                    ticks={[0, 950, 1900, 2850, 3800]}
                    stroke="#737373"
                    tick={{ fontSize: 10, fill: "#737373" }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(val) => val.toLocaleString()}
                  />
                  <Tooltip
                    content={<CustomTooltip />}
                    cursor={{ fill: "rgba(255, 255, 255, 0.05)" }}
                  />
                  <Bar
                    dataKey="calls"
                    fill="#1d61f2"
                    radius={[1, 1, 0, 0]}
                    animationDuration={600}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}