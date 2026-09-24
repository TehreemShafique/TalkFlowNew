"use client";

import React, { useState } from "react";
import {
  ChevronDown,
  BarChart2,
  Phone,
  Clock,
  ShoppingCart,
  Percent,
  TrendingUp,
  Users,
  FileText,
  User,
  PhoneOff,
  Ban,
  HelpCircle,
} from "lucide-react";
import { STATS_DATA } from "@/data";

const STAT_ICONS = {
  "1": { Icon: Phone, bg: "bg-[#0059DD]", colorHex: "#0059DD", path: "M 0,35 L 0,24 C 40,32 75,30 120,12 L 120,35 Z", line: "M 0,24 C 40,32 75,30 120,12" },
  "2": { Icon: Clock, bg: "bg-purple-500", colorHex: "#8b5cf6", path: "M 0,35 L 0,18 C 45,28 80,12 120,20 L 120,35 Z", line: "M 0,18 C 45,28 80,12 120,20" },
  "3": { Icon: ShoppingCart, bg: "bg-emerald-500", colorHex: "#10b981", path: "M 0,35 L 0,26 C 40,14 80,24 120,10 L 120,35 Z", line: "M 0,26 C 40,14 80,24 120,10" },
  "4": { Icon: Percent, bg: "bg-teal-500", colorHex: "#14b8a6", path: "M 0,35 L 0,20 C 45,30 75,10 120,16 L 120,35 Z", line: "M 0,20 C 45,30 75,10 120,16" },
  "5": { Icon: TrendingUp, bg: "bg-orange-500", colorHex: "#f97316", path: "M 0,35 L 0,28 C 40,16 80,24 120,12 L 120,35 Z", line: "M 0,28 C 40,16 80,24 120,12" },
  "6": { Icon: Users, bg: "bg-blue-600", colorHex: "#3b82f6", path: "M 0,35 L 0,16 C 40,26 80,14 120,22 L 120,35 Z", line: "M 0,16 C 40,26 80,14 120,22" },
  "7": { Icon: FileText, bg: "bg-violet-500", colorHex: "#a855f7", path: "M 0,35 L 0,22 C 45,10 75,28 120,14 L 120,35 Z", line: "M 0,22 C 45,10 75,28 120,14" },
  "8": { Icon: User, bg: "bg-cyan-500", colorHex: "#06b6d4", path: "M 0,35 L 0,24 C 40,12 80,22 120,10 L 120,35 Z", line: "M 0,24 C 40,12 80,22 120,10" },
  "9": { Icon: PhoneOff, bg: "bg-rose-500", colorHex: "#ef4444", path: "M 0,35 L 0,18 C 45,28 75,14 120,24 L 120,35 Z", line: "M 0,18 C 45,28 75,14 120,24" },
  "10": { Icon: Ban, bg: "bg-pink-500", colorHex: "#ec4899", path: "M 0,35 L 0,26 C 40,14 80,24 120,16 L 120,35 Z", line: "M 0,26 C 40,14 80,24 120,16" },
  "11": { Icon: HelpCircle, bg: "bg-amber-400", colorHex: "#f59e0b", path: "M 0,35 L 0,20 C 45,30 75,12 120,18 L 120,35 Z", line: "M 0,20 C 45,30 75,12 120,18" },
};

const VALUE_COLORS = {
  "3": "#16A34A", // SALE (Green)
  "4": "#16A34A", // SALE % (Green)
  "9": "#DC2626", // DC (Red)
  "10": "#DC2626", // DNC (Red)
  "11": "#F59E0B", // DNQ (Orange)
};

function CardWaveGraph({ colorHex, gradientId, path, line }) {
  return (
    <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-10 w-full overflow-hidden">
      <svg
        className="h-full w-full"
        viewBox="0 0 120 35"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={colorHex} stopOpacity="0.30" />
            <stop offset="100%" stopColor={colorHex} stopOpacity="0.04" />
          </linearGradient>
        </defs>
        <path d={path} fill={`url(#${gradientId})`} />
        <path
          d={line}
          fill="none"
          stroke={colorHex}
          strokeWidth="0.7"
          strokeOpacity="0.4"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}

export default function StatsGrid() {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="flex w-full flex-col gap-3">
      {/* Collapsible Section Header */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-fit select-none items-center gap-2 text-xs font-bold tracking-wider text-[#0059DD] dark:text-[#0059DD] transition-colors hover:opacity-80"
      >
        <div className="flex items-center gap-1.5 rounded-lg bg-blue-50 px-2 py-1 dark:bg-blue-950/40">
          <BarChart2 className="h-4 w-4 text-[#0059DD] dark:text-[#0059DD]" />
          <span className="font-extrabold uppercase text-neutral-800 dark:text-neutral-200">S T A T S</span>
        </div>
        <ChevronDown
          className={`h-4 w-4 text-neutral-400 transition-transform duration-200 ${
            isOpen ? "rotate-0" : "-rotate-90"
          }`}
        />
      </button>

      {/* 4-Column Grid of Metric Cards */}
      {isOpen && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {STATS_DATA.map((item) => {
            const meta = STAT_ICONS[item.id] || {
              Icon: Phone,
              bg: "bg-[#0059DD]",
              colorHex: "#0059DD",
              path: "M 0,35 L 0,24 Q 30,8 60,22 T 120,12 L 120,35 Z",
              line: "M 0,24 Q 30,8 60,22 T 120,12",
            };
            const IconComponent = meta.Icon;
            const gradientId = `wave-grad-${item.id}`;
            const customColor = VALUE_COLORS[item.id];

            return (
              <div
                key={item.id}
                title={item.count}
                className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-neutral-200/80 bg-white p-3.5 shadow-2xs transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md dark:border-[#1a1a1a] dark:bg-[#000000]"
              >
                {/* Top Row: Icon Badge + Metric Label */}
                <div className="flex items-center gap-2.5 z-10">
                  <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-white shadow-xs ${meta.bg}`}>
                    <IconComponent className="h-4 w-4" />
                  </div>
                  <span className="truncate text-[10px] font-bold uppercase tracking-wider text-neutral-500 transition-colors group-hover:text-neutral-900 dark:text-neutral-400 dark:group-hover:text-white">
                    {item.title}
                  </span>
                </div>

                {/* Bottom Row: Large Metric Value */}
                <div className="mt-3 mb-1 flex items-baseline gap-1 z-10">
                  <span
                    className="text-xl font-medium tracking-tight text-neutral-900 sm:text-2xl dark:text-white"
                    style={{
                      fontFamily: "'Times New Roman', Times, serif",
                      color: customColor || undefined,
                    }}
                  >
                    {item.value}
                  </span>
                  {item.unit && (
                    <span
                      className="text-xs font-normal text-neutral-500 dark:text-neutral-400"
                      style={{
                        fontFamily: "'Times New Roman', Times, serif",
                        color: customColor || undefined,
                      }}
                    >
                      {item.unit}
                    </span>
                  )}
                </div>

                {/* Real-time Mini Area Wave Sparkline Graph */}
                <CardWaveGraph
                  colorHex={meta.colorHex}
                  gradientId={gradientId}
                  path={meta.path}
                  line={meta.line}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
