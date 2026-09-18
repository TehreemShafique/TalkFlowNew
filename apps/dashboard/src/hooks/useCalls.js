"use client";

import { useState, useMemo, useCallback } from "react";
import { INITIAL_CALLS, LIVE_CALLS_DATA } from "@/data";

// Generic CDR call-log data service hook.
// Decouples static call history / live-channel datasets from feature UI state.
export function useCalls(dispositionFilter = "all", searchQuery = "") {
  const [calls, setCalls] = useState(INITIAL_CALLS);
  const [liveCalls, setLiveCalls] = useState(LIVE_CALLS_DATA);

  const filteredCalls = useMemo(() => {
    return calls.filter((call) => {
      if (dispositionFilter !== "all" && !call.disposition.includes(dispositionFilter)) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return (
          call.callId.toLowerCase().includes(q) ||
          call.leadName.toLowerCase().includes(q) ||
          call.phone.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [calls, dispositionFilter, searchQuery]);

  const setCallsList = useCallback((updater) => {
    setCalls(updater);
  }, []);

  return {
    calls: filteredCalls,
    allCalls: calls,
    liveCalls,
    setCalls,
    setCallsList,
  };
}