"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  ChevronDown,
  RotateCw,
  X,
  Search,
  Check,
  Layers,
  ListFilter,
  LayoutGrid,
  PhoneCall,
  Server,
  Calendar,
} from "lucide-react";
import { useFilters } from "@/context";

export default function FilterToolbox({ onRefresh }) {
  // Active Dropdown UI state: null | 'limit' | 'disposition' | 'type' | 'dialer' | 'server' | 'date'
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [dispSearch, setDispSearch] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const containerRef = useRef(null);

  // Global Filter State lifted to FilterContext
  const {
    limit,
    setLimit,
    selectedDispositions,
    setSelectedDispositions,
    campaignType,
    setCampaignType,
    selectedDialer,
    setSelectedDialer,
    selectedServer,
    setSelectedServer,
    selectedDatePreset,
    setSelectedDatePreset,
    selectAllDispositions,
    clearAllDispositions,
    toggleDisposition,
    LIMIT_OPTIONS,
    TYPE_OPTIONS,
    DIALER_OPTIONS,
    SERVER_OPTIONS,
    DATE_PRESETS,
    ALL_DISPOSITIONS,
  } = useFilters();

  // Close open dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target)
      ) {
        setActiveDropdown(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleDropdown = (name) => {
    setActiveDropdown((prev) => (prev === name ? null : name));
  };

  // Check if all options are selected
  const isAllSelected = selectedDispositions.length === ALL_DISPOSITIONS.length;

  // Toggle "All" option
  const toggleAllDispositions = () => {
    if (isAllSelected) {
      clearAllDispositions();
    } else {
      selectAllDispositions();
    }
  };

  const removeDispositionTag = (tagToRemove) => {
    setSelectedDispositions((prev) => prev.filter((tag) => tag !== tagToRemove));
  };

  const handleRefreshClick = () => {
    setIsRefreshing(true);
    if (onRefresh) onRefresh();
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const filteredDispositions = ALL_DISPOSITIONS.filter((d) =>
    d.toLowerCase().includes(dispSearch.toLowerCase())
  );

  const buttonStyle =
    "relative flex items-center gap-2 rounded-xl border border-neutral-200/90 bg-white px-3 py-2 text-xs font-medium text-neutral-700 shadow-2xs transition-all hover:border-blue-300 hover:bg-blue-50/30 hover:text-neutral-900 dark:border-[#1a1a1a] dark:bg-[#000000] dark:text-neutral-300 dark:hover:border-blue-800 dark:hover:bg-[#111111] dark:hover:text-white";

  const dropdownContainerStyle =
    "absolute left-0 top-full mt-2 z-50 min-w-[220px] rounded-xl border border-neutral-200/80 bg-white p-2.5 shadow-xl backdrop-blur-md dark:border-[#1a1a1a] dark:bg-[#000000] dark:text-neutral-200 animate-in fade-in-0 zoom-in-95";

  return (
    <div
      ref={containerRef}
      className="flex flex-col gap-2.5 border-b border-neutral-200/70 bg-[#f8fafc]/80 px-4 py-3 text-xs transition-colors duration-200 dark:border-[#141414] dark:bg-[#000000] sm:px-6"
    >
      {/* Top Filter Buttons Row */}
      <div className="flex flex-wrap items-center gap-2.5">
        {/* 1. LIMIT DROPDOWN */}
        <div className="relative">
          <button
            type="button"
            onClick={() => toggleDropdown("limit")}
            className={buttonStyle}
          >
            <Layers className="h-3.5 w-3.5 text-blue-500 shrink-0" />
            <span className="text-neutral-400 dark:text-neutral-400">Limit</span>
            <span className="font-bold text-neutral-900 dark:text-neutral-100">
              {limit}
            </span>
            <ChevronDown
              className={`h-3 w-3 text-neutral-400 transition-transform ${
                activeDropdown === "limit" ? "rotate-180 text-blue-500" : ""
              }`}
            />
          </button>

          {activeDropdown === "limit" && (
            <div className={`${dropdownContainerStyle} w-40`}>
              <div className="text-[10px] font-bold text-neutral-400 px-2 py-1 uppercase tracking-wider">
                Select Limit
              </div>
              <div className="flex flex-col gap-0.5">
                {LIMIT_OPTIONS.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => {
                      setLimit(opt);
                      setActiveDropdown(null);
                    }}
                    className={`flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                      limit === opt
                        ? "bg-blue-50 font-bold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"
                        : "text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-[#171b28]"
                    }`}
                  >
                    <span>{opt}</span>
                    {limit === opt && <Check className="h-3.5 w-3.5 text-blue-500" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 2. DISPOSITION MULTI-SELECT DROPDOWN */}
        <div className="relative">
          <button
            type="button"
            onClick={() => toggleDropdown("disposition")}
            className={buttonStyle}
          >
            <ListFilter className="h-3.5 w-3.5 text-blue-500 shrink-0" />
            <span className="text-neutral-400 dark:text-neutral-400">
              Disposition
            </span>
            <span className="font-bold text-neutral-900 dark:text-neutral-100">
              {isAllSelected
                ? "All"
                : selectedDispositions.length === 0
                ? "None"
                : `${selectedDispositions.length} selected`}
            </span>
            <ChevronDown
              className={`h-3 w-3 text-neutral-400 transition-transform ${
                activeDropdown === "disposition" ? "rotate-180 text-blue-500" : ""
              }`}
            />
          </button>

          {activeDropdown === "disposition" && (
            <div className={`${dropdownContainerStyle} w-64`}>
              {/* Search Input */}
              <div className="relative mb-2">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-neutral-400" />
                <input
                  type="text"
                  value={dispSearch}
                  onChange={(e) => setDispSearch(e.target.value)}
                  placeholder="Search disposition..."
                  className="w-full rounded-lg border border-neutral-200 bg-neutral-50 py-1.5 pl-8 pr-3 text-xs outline-none focus:border-blue-500 dark:border-neutral-800 dark:bg-[#141824] dark:text-neutral-100 dark:focus:border-blue-500"
                />
              </div>

              {/* Disposition List with "All" Option + Individual Checkboxes */}
              <div className="max-h-60 overflow-y-auto flex flex-col gap-0.5 pr-1">
                {/* "All" Select Option */}
                <label
                  onClick={toggleAllDispositions}
                  className={`flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs cursor-pointer select-none border-b border-neutral-100 dark:border-neutral-800 pb-2 mb-1 transition-colors ${
                    isAllSelected
                      ? "bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 font-bold"
                      : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-[#171b28]"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      onChange={() => {}}
                      className="h-3.5 w-3.5 accent-blue-600 rounded cursor-pointer"
                    />
                    <span>All</span>
                  </div>
                  <span className="text-[10px] text-neutral-400 font-mono">
                    {selectedDispositions.length}/{ALL_DISPOSITIONS.length}
                  </span>
                </label>

                {/* Individual Disposition Options */}
                {filteredDispositions.map((disp) => {
                  const isChecked = selectedDispositions.includes(disp);
                  return (
                    <label
                      key={disp}
                      onClick={() => toggleDisposition(disp)}
                      className={`flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs cursor-pointer select-none transition-colors ${
                        isChecked
                          ? "bg-blue-50/70 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 font-semibold"
                          : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-[#171b28]"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {}}
                          className="h-3.5 w-3.5 accent-blue-600 rounded cursor-pointer"
                        />
                        <span>{disp}</span>
                      </div>
                    </label>
                  );
                })}

                {filteredDispositions.length === 0 && (
                  <div className="py-4 text-center text-xs text-neutral-400">
                    No dispositions match search.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 3. TYPE DROPDOWN */}
        <div className="relative">
          <button
            type="button"
            onClick={() => toggleDropdown("type")}
            className={buttonStyle}
          >
            <LayoutGrid className="h-3.5 w-3.5 text-blue-500 shrink-0" />
            <span className="text-neutral-400 dark:text-neutral-400">Type</span>
            <span className="font-bold text-neutral-900 dark:text-neutral-100">
              {campaignType}
            </span>
            <ChevronDown
              className={`h-3 w-3 text-neutral-400 transition-transform ${
                activeDropdown === "type" ? "rotate-180 text-blue-500" : ""
              }`}
            />
          </button>

          {activeDropdown === "type" && (
            <div className={`${dropdownContainerStyle} w-40`}>
              <div className="text-[10px] font-bold text-neutral-400 px-2 py-1 uppercase tracking-wider">
                Campaign Type
              </div>
              <div className="flex flex-col gap-0.5">
                {TYPE_OPTIONS.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => {
                      setCampaignType(t);
                      setActiveDropdown(null);
                    }}
                    className={`flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                      campaignType === t
                        ? "bg-blue-50 font-bold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"
                        : "text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-[#171b28]"
                    }`}
                  >
                    <span>{t}</span>
                    {campaignType === t && <Check className="h-3.5 w-3.5 text-blue-500" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 4. DIALER DROPDOWN */}
        <div className="relative">
          <button
            type="button"
            onClick={() => toggleDropdown("dialer")}
            className={buttonStyle}
          >
            <PhoneCall className="h-3.5 w-3.5 text-blue-500 shrink-0" />
            <span className="text-neutral-400 dark:text-neutral-400">Dialer</span>
            <span className="font-bold text-neutral-900 dark:text-neutral-100">
              {selectedDialer}
            </span>
            <ChevronDown
              className={`h-3 w-3 text-neutral-400 transition-transform ${
                activeDropdown === "dialer" ? "rotate-180 text-blue-500" : ""
              }`}
            />
          </button>

          {activeDropdown === "dialer" && (
            <div className={`${dropdownContainerStyle} w-48`}>
              <div className="text-[10px] font-bold text-neutral-400 px-2 py-1 uppercase tracking-wider">
                Select Dialer
              </div>
              <div className="flex flex-col gap-0.5">
                {DIALER_OPTIONS.map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => {
                      setSelectedDialer(d);
                      setActiveDropdown(null);
                    }}
                    className={`flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                      selectedDialer === d
                        ? "bg-blue-50 font-bold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"
                        : "text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-[#171b28]"
                    }`}
                  >
                    <span>{d}</span>
                    {selectedDialer === d && <Check className="h-3.5 w-3.5 text-blue-500" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 5. SERVER DROPDOWN */}
        <div className="relative">
          <button
            type="button"
            onClick={() => toggleDropdown("server")}
            className={buttonStyle}
          >
            <Server className="h-3.5 w-3.5 text-blue-500 shrink-0" />
            <span className="text-neutral-400 dark:text-neutral-400">Server</span>
            <span className="font-bold text-neutral-900 dark:text-neutral-100">
              {selectedServer}
            </span>
            <ChevronDown
              className={`h-3 w-3 text-neutral-400 transition-transform ${
                activeDropdown === "server" ? "rotate-180 text-blue-500" : ""
              }`}
            />
          </button>

          {activeDropdown === "server" && (
            <div className={`${dropdownContainerStyle} w-52`}>
              <div className="text-[10px] font-bold text-neutral-400 px-2 py-1 uppercase tracking-wider">
                Select Server
              </div>
              <div className="flex flex-col gap-0.5">
                {SERVER_OPTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => {
                      setSelectedServer(s);
                      setActiveDropdown(null);
                    }}
                    className={`flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                      selectedServer === s
                        ? "bg-blue-50 font-bold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"
                        : "text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-[#171b28]"
                    }`}
                  >
                    <span>{s}</span>
                    {selectedServer === s && <Check className="h-3.5 w-3.5 text-blue-500" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 6. DATE RANGE SELECTOR */}
        <div className="relative">
          <button
            type="button"
            onClick={() => toggleDropdown("date")}
            className={`${buttonStyle} py-1.5`}
          >
            <Calendar className="h-3.5 w-3.5 text-blue-500 shrink-0" />
            <div className="flex flex-col text-left">
              <span className="text-[11px] font-bold leading-tight text-neutral-900 dark:text-neutral-100">
                {selectedDatePreset.label}
              </span>
              <span className="text-[9px] leading-tight text-neutral-400">
                {selectedDatePreset.subtext}
              </span>
            </div>
            <ChevronDown
              className={`ml-1 h-3 w-3 text-neutral-400 transition-transform ${
                activeDropdown === "date" ? "rotate-180 text-blue-500" : ""
              }`}
            />
          </button>

          {activeDropdown === "date" && (
            <div className={`${dropdownContainerStyle} w-64`}>
              <div className="text-[10px] font-bold text-neutral-400 px-2 py-1 uppercase tracking-wider">
                Time Range Presets
              </div>
              <div className="flex flex-col gap-1">
                {DATE_PRESETS.map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => {
                      setSelectedDatePreset(preset);
                      setActiveDropdown(null);
                    }}
                    className={`flex flex-col rounded-lg px-2.5 py-1.5 text-left transition-colors ${
                      selectedDatePreset.label === preset.label
                        ? "bg-blue-50 font-semibold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"
                        : "text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-[#171b28]"
                    }`}
                  >
                    <span className="text-xs font-bold">{preset.label}</span>
                    <span className="text-[10px] text-neutral-400 font-mono">
                      {preset.subtext}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 7. REFRESH ACTION */}
        <button
          type="button"
          onClick={handleRefreshClick}
          title="Refresh Data"
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-blue-200/80 bg-blue-50/60 text-blue-600 shadow-2xs transition-all hover:bg-blue-100 hover:scale-105 active:scale-95 dark:border-blue-900/50 dark:bg-blue-950/40 dark:text-blue-400 dark:hover:bg-blue-900/60"
        >
          <RotateCw
            className={`h-4 w-4 ${
              isRefreshing ? "animate-spin text-blue-600 dark:text-blue-400" : ""
            }`}
          />
        </button>
      </div>

      {/* 8. ACTIVE DISPOSITION TAG PILLS */}
      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        {selectedDispositions.map((tag) => (
          <span
            key={tag}
            className="flex items-center gap-1.5 rounded-full border border-blue-200/80 bg-blue-50/80 px-3 py-0.5 text-[11px] font-semibold text-blue-600 transition-all dark:border-blue-900/40 dark:bg-blue-950/40 dark:text-blue-300"
          >
            {tag}
            <button
              type="button"
              onClick={() => removeDispositionTag(tag)}
              className="rounded-full p-0.5 text-blue-400 hover:bg-blue-200/60 hover:text-blue-800 dark:hover:bg-blue-900/50 dark:hover:text-blue-100 transition-colors"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}