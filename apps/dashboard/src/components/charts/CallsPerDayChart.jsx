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
  LabelList,
} from "recharts";
import { DEFAULT_DAILY_CALLS } from "@/data";

// Custom floating hover tooltip
const CustomDailyTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="pointer-events-none z-50 rounded-lg border border-neutral-700/80 bg-[#161618] px-3.5 py-2 text-xs shadow-2xl backdrop-blur-md">
        <div className="font-semibold text-neutral-300">Date: {label}</div>
        <div className="mt-0.5 font-medium text-cyan-400">
          Calls : {data.calls.toLocaleString()}
        </div>
      </div>
    );
  }
  return null;
};

// Custom top label renderer to omit labels for zero-count days
const renderCustomBarLabel = (props) => {
  const { x, y, width, value } = props;
  if (!value) return null;
  return (
    <text
      x={x + width / 2}
      y={y - 8}
      fill="#a3a3a3"
      textAnchor="middle"
      fontSize={11}
      fontWeight={500}
    >
      {value}
    </text>
  );
};

export default function CallsPerDayChart({
  data = DEFAULT_DAILY_CALLS,
  totalCalls = "1,612,426",
  shiftWindow = "08:00–22:00",
}) {
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
        <span>CALLS PER DAY (LAST 7 DAYS)</span>
      </button>

      {/* Main Chart Container */}
      {isOpen && (
        <div className="w-full rounded-xl border border-neutral-200 bg-white p-5 shadow-sm transition-colors duration-200 dark:border-[#1a1a1a] dark:bg-[#000000]">
          <h3 className="mb-6 text-sm font-bold text-neutral-800 dark:text-neutral-200">
            Calls per day (last 7 days)
          </h3>

          {/* Responsive Scrollable Container for Mobile Screens */}
          <div className="w-full overflow-x-auto">
            <div className="h-72 min-w-[700px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data}
                  margin={{ top: 25, right: 20, left: 20, bottom: 5 }}
                  barCategoryGap={18}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={true}
                    horizontal={true}
                    stroke="#262626"
                    opacity={0.25}
                  />
                  <XAxis
                    dataKey="date"
                    stroke="#737373"
                    tick={{ fontSize: 10, fill: "#737373" }}
                    tickLine={false}
                    axisLine={{ stroke: "#262626" }}
                  />
                  <YAxis hide={true} domain={[0, 440000]} />
                  <Tooltip
                    content={<CustomDailyTooltip />}
                    cursor={{ fill: "rgba(255, 255, 255, 0.04)" }}
                  />
                  <Bar
                    dataKey="calls"
                    fill="#1d61f2"
                    radius={[2, 2, 0, 0]}
                    animationDuration={600}
                  >
                    <LabelList
                      dataKey="displayLabel"
                      content={renderCustomBarLabel}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Bottom Operational Shift Metric Summary */}
          <div className="mt-4 flex items-center gap-2 border-t border-neutral-100 pt-3 text-xs font-medium text-neutral-600 dark:border-neutral-900 dark:text-neutral-400">
            <span className="h-0.5 w-4 rounded-full bg-[#1d61f2]" />
            <span>
              Calls ({shiftWindow}) Total:{" "}
              <strong className="font-semibold text-neutral-900 dark:text-white">
                {totalCalls}
              </strong>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}