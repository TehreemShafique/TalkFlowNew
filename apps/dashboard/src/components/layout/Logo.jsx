"use client";

import React, { useId } from "react";

export function Logo({ compact = false, theme = "auto", className = "" }) {
  const instanceId = useId().replace(/:/g, "");
  const shieldGradientId = `sb-shield-grad-${instanceId}`;
  const pillGradientId = `sb-pill-grad-${instanceId}`;

  return (
    <div
      className={`inline-flex items-center justify-center mx-auto select-none bg-transparent cursor-pointer group transition-transform duration-200 ${
        compact ? "gap-2" : "gap-4"
      } ${theme === "light" ? "text-[#061024]" : theme === "dark" ? "text-white" : "text-slate-900 dark:text-white"} ${className}`}
      aria-label="SmartBrains BPO"
    >
      {/* Shield Icon (1px slightly smaller) */}
      <svg
        className={`flex-shrink-0 transition-all duration-200 group-hover:-translate-y-0.5 group-hover:scale-105 ${
          compact ? "w-[43px] h-[49px]" : "w-[81px] h-[93px] sm:w-[87px] sm:h-[101px]"
        }`}
        viewBox="0 0 100 115"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={shieldGradientId} x1="0" y1="0" x2="100" y2="115" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#00C4FF" />
            <stop offset="45%" stopColor="#0072FF" />
            <stop offset="100%" stopColor="#0047FF" />
          </linearGradient>
          <linearGradient id={pillGradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#00A3FF" />
            <stop offset="100%" stopColor="#0052D4" />
          </linearGradient>
        </defs>
        <path
          d="M 50 4 C 70 4, 88 10, 93 20 C 97 30, 96 52, 90 69 C 80 93, 58 108, 50 112 C 42 108, 20 93, 10 69 C 4 52, 3 30, 7 20 C 12 10, 30 4, 50 4 Z"
          fill={`url(#${shieldGradientId})`}
        />
        <text
          x="50"
          y="76"
          fontWeight="800"
          fontSize="64"
          fontFamily="system-ui, -apple-system, sans-serif"
          textAnchor="middle"
          fill="#FFFFFF"
        >
          S
        </text>
      </svg>

      {/* Copy & Sub-line */}
      <div className="flex flex-col justify-center items-start min-w-0">
        <span
          className={`font-extrabold tracking-tight leading-none whitespace-nowrap text-current ${
            compact ? "text-[1.45rem]" : "text-[2.75rem]"
          }`}
        >
          SmartBrains
        </span>
        <div className={`flex items-center w-full ${compact ? "gap-1.5 mt-[3px]" : "gap-2 mt-[5px]"}`}>
          {/* Blue Underline */}
          <span className="flex-1 h-[3px] bg-gradient-to-r from-[#00A3FF] to-[#0066FF] rounded-full shadow-[0_0_8px_rgba(0,132,255,0.3)]" />
          {/* BPO Pill Badge */}
          <span
            className={`inline-flex items-center justify-center font-extrabold text-white rounded-full bg-gradient-to-r from-[#00A3FF] to-[#0052D4] shadow-[0_2px_10px_rgba(0,102,255,0.35)] ${
              compact ? "text-[9.5px] px-2 py-[1px]" : "text-[0.95rem] px-2.5 py-0.5"
            }`}
          >
            BPO
          </span>
        </div>
      </div>
    </div>
  );
}

export default Logo;
