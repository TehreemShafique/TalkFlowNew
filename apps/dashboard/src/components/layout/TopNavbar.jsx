"use client";

import React, { useState } from "react";
import {
  Menu,
  Search,
  Bell,
  Monitor,
  Sun,
  ShieldAlert,
  Radio,
  X,
  ExternalLink,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { useTheme } from "@/context";
import CommandSearchModal from "./CommandSearchModal";

export default function TopNavbar({
  onToggleMobileSidebar,
  onToggleDesktopSidebar,
  isSidebarCollapsed,
  onNavigate,
}) {
  const { theme, toggleTheme } = useTheme();
  const isLightMode = theme === "light";

  // Modal & Dropdown States
  const [alertMenuOpen, setAlertMenuOpen] = useState(false);
  const [liveMenuOpen, setLiveMenuOpen] = useState(false);
  const [searchModalOpen, setSearchModalOpen] = useState(false);

  // Connection State: 'connected', 'reconnecting', 'disconnected'
  const [connectionStatus, setConnectionStatus] = useState("connected");

  // Mock Unacknowledged Alerts (surfacing system alerts & PRD §13 failed transfer risk)
  const unacknowledgedAlerts = [
    {
      id: "alt-101",
      severity: "CRITICAL",
      title: "PRD §13 Transfer Risk Alert",
      description: "3 consecutive verifier ring timeouts on Campaign Medicare-Q3. Fallback queue activated.",
      timestamp: "10m ago",
      type: "transfer",
    },
    {
      id: "alt-102",
      severity: "WARNING",
      title: "STT GPU Worker Latency Spike",
      description: "Whisper CUDA worker #4 latency reached 138ms (threshold 100ms).",
      timestamp: "25m ago",
      type: "system",
    },
    {
      id: "alt-103",
      severity: "INFO",
      title: "DNC Suppression Scrub Complete",
      description: "Batch lead intake scrubbed 14 matching opt-outs.",
      timestamp: "1h ago",
      type: "suppression",
    },
  ];

  const handleJumpAlerts = () => {
    setAlertMenuOpen(false);
    if (onNavigate) {
      onNavigate("system", "alerts");
    }
  };

  return (
    <>
      <header className="flex h-14 w-full items-center justify-between border-b border-neutral-200 bg-white px-4 md:px-6 text-neutral-900 transition-colors duration-200 dark:border-[#141414] dark:bg-[#000000] dark:text-white shrink-0 z-30">
        {/* Left Slot: Hamburger Menu + Brand Title + Global Search Bar */}
        <div className="flex items-center gap-3">
          {/* Mobile Overlay Drawer Hamburger Button [☰] */}
          <button
            type="button"
            onClick={onToggleMobileSidebar}
            title="Open Mobile Navigation Drawer"
            className="flex items-center justify-center rounded-lg p-2 text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800 lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>

          {/* Desktop Sidebar Toggle Button */}
          {onToggleDesktopSidebar && (
            <button
              type="button"
              onClick={onToggleDesktopSidebar}
              title={isSidebarCollapsed ? "Open Sidebar" : "Close Sidebar"}
              className="hidden lg:flex items-center justify-center rounded-lg p-2 text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800 transition-colors"
            >
              {isSidebarCollapsed ? (
                <PanelLeftOpen className="h-5 w-5" />
              ) : (
                <PanelLeftClose className="h-5 w-5" />
              )}
            </button>
          )}

          {/* Reserved Global Search Slot (⌘K / Ctrl+K) */}
          <button
            type="button"
            onClick={() => setSearchModalOpen(true)}
            className="hidden sm:flex items-center gap-3 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs text-neutral-500 hover:border-neutral-300 hover:bg-neutral-100 dark:border-neutral-800 dark:bg-[#121215] dark:text-neutral-400 dark:hover:border-neutral-700 dark:hover:bg-neutral-800 transition-all w-64 md:w-80"
          >
            <Search className="h-3.5 w-3.5 text-neutral-400" />
            <span className="flex-1 text-left truncate">Search calls, leads, campaigns...</span>
            <kbd className="rounded border border-neutral-300 bg-white px-1.5 py-0.5 text-[10px] font-mono text-neutral-600 shadow-2xs dark:border-neutral-700 dark:bg-[#1a1a1e] dark:text-neutral-300">
              ⌘K
            </kbd>
          </button>
        </div>

        {/* Right Slot: Live Indicator + Alert Bell + Display Mode + User Dropdown */}
        <div className="flex items-center gap-2.5">
          {/* Global Live Connection Indicator Dropdown */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setLiveMenuOpen(!liveMenuOpen)}
              className={`flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold transition-all ${
                connectionStatus === "connected"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/40 dark:text-emerald-300"
                  : connectionStatus === "reconnecting"
                  ? "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-300"
                  : "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/40 dark:text-rose-300"
              }`}
            >
              <span className="relative flex h-2 w-2">
                {connectionStatus === "connected" && (
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                )}
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${
                    connectionStatus === "connected"
                      ? "bg-emerald-500"
                      : connectionStatus === "reconnecting"
                      ? "bg-amber-500"
                      : "bg-rose-500"
                  }`}
                />
              </span>
              <span className="hidden xs:inline">
                Live: {connectionStatus === "connected" ? "Connected" : connectionStatus === "reconnecting" ? "Reconnecting" : "Disconnected"}
              </span>
            </button>

            {/* Live Indicator Telemetry Popover */}
            {liveMenuOpen && (
              <div className="absolute right-0 mt-2 w-64 rounded-xl border border-neutral-200 bg-white p-3 shadow-lg dark:border-neutral-800 dark:bg-[#0d0d0f] z-50 text-xs">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-2 dark:border-neutral-800 mb-2">
                  <span className="font-bold text-neutral-900 dark:text-white flex items-center gap-1.5">
                    <Radio className="h-3.5 w-3.5 text-emerald-500" /> Control Plane Telemetry
                  </span>
                  <button onClick={() => setLiveMenuOpen(false)}>
                    <X className="h-3.5 w-3.5 text-neutral-400" />
                  </button>
                </div>

                <div className="space-y-2 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-neutral-500 dark:text-neutral-400">AudioSocket Gateway</span>
                    <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">25ms (412 streams)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-500 dark:text-neutral-400">SIP Trunk Gateway</span>
                    <span className="font-bold text-neutral-800 dark:text-neutral-200">Asterisk v20.4</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-neutral-500 dark:text-neutral-400">WebSocket Link</span>
                    <span className="font-mono font-bold text-neutral-800 dark:text-neutral-200">2ms latency</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Alert Bell Surface ([alerts N]) */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setAlertMenuOpen(!alertMenuOpen)}
              title="System Alerts & Failed Transfers"
              className="relative flex items-center justify-center rounded-lg border border-neutral-200 bg-neutral-50 p-2 text-neutral-600 hover:bg-neutral-100 dark:border-neutral-800 dark:bg-[#121215] dark:text-neutral-300 dark:hover:bg-neutral-800 transition-colors"
            >
              <Bell className="h-4 w-4" />
              {unacknowledgedAlerts.length > 0 && (
                <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white shadow-2xs">
                  {unacknowledgedAlerts.length}
                </span>
              )}
            </button>

            {/* Alert Bell Overlay */}
            {alertMenuOpen && (
              <div className="absolute right-0 mt-2 w-80 rounded-xl border border-neutral-200 bg-white p-3 shadow-xl dark:border-neutral-800 dark:bg-[#0d0d0f] z-50 text-xs">
                <div className="flex items-center justify-between border-b border-neutral-100 pb-2 dark:border-neutral-800 mb-2">
                  <span className="font-bold text-neutral-900 dark:text-white flex items-center gap-1.5">
                    <ShieldAlert className="h-4 w-4 text-rose-500" /> Unacknowledged Alerts ({unacknowledgedAlerts.length})
                  </span>
                  <button onClick={() => setAlertMenuOpen(false)}>
                    <X className="h-3.5 w-3.5 text-neutral-400" />
                  </button>
                </div>

                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {unacknowledgedAlerts.map((alt) => (
                    <div
                      key={alt.id}
                      className={`p-2.5 rounded-lg border text-xs ${
                        alt.severity === "CRITICAL"
                          ? "bg-rose-50/70 border-rose-200 dark:bg-rose-950/40 dark:border-rose-900/40"
                          : "bg-amber-50/70 border-amber-200 dark:bg-amber-950/40 dark:border-amber-900/40"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className={`font-bold text-[10px] uppercase ${alt.severity === "CRITICAL" ? "text-rose-700 dark:text-rose-400" : "text-amber-700 dark:text-amber-400"}`}>
                          {alt.title}
                        </span>
                        <span className="text-[10px] text-neutral-400 font-mono">{alt.timestamp}</span>
                      </div>
                      <p className="text-[11px] text-neutral-700 dark:text-neutral-300 mt-1">
                        {alt.description}
                      </p>
                    </div>
                  ))}
                </div>

                <div className="border-t border-neutral-100 pt-2 mt-2 dark:border-neutral-800 flex justify-between items-center">
                  <button
                    type="button"
                    onClick={handleJumpAlerts}
                    className="flex items-center gap-1 text-[11px] font-bold text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    <span>View All System Alerts</span>
                    <ExternalLink className="h-3 w-3" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Theme Display Switcher */}
          <button
            type="button"
            onClick={toggleTheme}
            title={isLightMode ? "Switch to Dark Display" : "Switch to Light Display"}
            className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-2.5 py-1.5 text-xs font-semibold text-neutral-700 transition-all hover:bg-neutral-100 dark:border-neutral-800 dark:bg-[#121215] dark:text-neutral-300 dark:hover:bg-neutral-800"
          >
            {isLightMode ? (
              <Sun className="h-3.5 w-3.5 text-amber-500" />
            ) : (
              <Monitor className="h-3.5 w-3.5 text-blue-400" />
            )}
          </button>
        </div>
      </header>

      {/* Global Command Search Modal (⌘K / Ctrl+K) */}
      <CommandSearchModal
        isOpen={searchModalOpen}
        onClose={() => setSearchModalOpen(false)}
        onNavigate={onNavigate}
      />
    </>
  );
}