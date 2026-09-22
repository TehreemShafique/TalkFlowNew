"use client";

import React from "react";
import FilterToolbox from "./FilterToolbox";
import SubHeader from "./SubHeader";
import StatsGrid from "./StatsGrid";
import PerformanceSection from "./PerformanceSection";
import {
  DispositionChart,
  DispositionComparison,
  CallsBucketChart,
  CallsPerDayChart,
  ViciListBreakdown,
} from "@/components/charts";
import { CallsDataTable } from "@/components/reports";

export default function DashboardView() {
  const handleRefresh = () => {
    console.log("Refreshing dashboard telemetry...");
  };

  const handleExportCalls = () => {
    console.log("Exporting call logs...");
  };

  const handleExportSales = () => {
    console.log("Exporting sales & transfer reports...");
  };

  return (
    <div className="flex min-h-screen w-full flex-col bg-[#f4f7fb] text-neutral-900 transition-colors duration-200 dark:bg-[#000000] dark:text-neutral-100">
      {/* 1. Filter Toolbar */}
      <FilterToolbox onRefresh={handleRefresh} />

      {/* 2. SubHeader with Action Buttons */}
      <SubHeader
        onExportCalls={handleExportCalls}
        onExportSales={handleExportSales}
      />

      {/* 3. Main Analytics Dashboard Layout */}
      <main className="flex flex-col gap-6 px-4 py-5 sm:px-6">
        {/* Row 1: KPI Stats Grid Container (55%) + Disposition % Breakdown (45%) */}
        <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[57fr_43fr]">
          <div className="w-full rounded-2xl border border-neutral-200/80 bg-white p-5 shadow-2xs dark:border-[#1a1a1a] dark:bg-[#000000]">
            <StatsGrid />
          </div>
          <div className="w-full h-full">
            <DispositionChart />
          </div>
        </div>

        {/* Row 2: Full-Width Disposition Comparison */}
        <div className="w-full">
          <DispositionComparison />
        </div>

        {/* Row 3: Full-Width Calls Per 5-Minute Bucket */}
        <div className="w-full">
          <CallsBucketChart />
        </div>

        {/* Row 4: Full-Width Calls Per Day (Last 7 Days) */}
        <div className="w-full">
          <CallsPerDayChart />
        </div>

        {/* Row 5: Agent & Script Performance (XFER% Gauges) */}
        <div className="w-full">
          <PerformanceSection />
        </div>

        {/* Row 6: Disposition Breakdown by Vici List */}
        <div className="w-full">
          <ViciListBreakdown />
        </div>

        {/* Row 7: Calls Data Table */}
        <div className="w-full">
          <CallsDataTable />
        </div>

        {/* Footer Tagline */}
        <div className="flex justify-end pt-2 pb-4">
          <p className="text-[11px] font-medium text-neutral-400 dark:text-neutral-500 italic">
            Smart Insights for a Smarter Tomorrow
          </p>
        </div>
      </main>
    </div>
  );
}