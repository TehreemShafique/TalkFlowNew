import { useState, useMemo, useEffect } from "react";
import { INITIAL_CALLS, LIVE_CALLS_DATA } from "@/data";
import { apiFetch } from "@/lib/api";

// Central state + route parsing for CallsView.
// initialAction can be 'live' (monitor), '[callId]' (detail), or null/'all'/'history' (CDR list).
export function useCallsState(initialAction, onActionChange) {
  const [callsList, setCallsList] = useState(INITIAL_CALLS);
  const [liveCalls, setLiveCalls] = useState(LIVE_CALLS_DATA);
  const [searchQuery, setSearchQuery] = useState("");
  const [dispositionFilter, setDispositionFilter] = useState("all");

  const fetchCalls = async () => {
    try {
      const res = await apiFetch("/calls?page_size=500");
      if (res.ok) {
        const json = await res.json();
        const items = json.items || json.data || [];
        if (items.length > 0) {
          const mapped = items.map((c) => ({
            id: c.id,
            callId: c.reference || `CALL-${c.id.slice(0, 8)}`,
            leadName: c.leadName || c.callerNumber || "Medicare Lead",
            phone: c.callerNumber || "+1 (202) 555-0134",
            campaign: c.campaignName || "Medicare Outbound Fronter",
            disposition: (c.disposition || c.qualificationStatus || "QUALIFIED").toUpperCase(),
            duration: `${Math.floor((c.durationSeconds || c.duration_seconds || 60) / 60).toString().padStart(2, "0")}:${((c.durationSeconds || c.duration_seconds || 60) % 60).toString().padStart(2, "0")}`,
            durationSec: c.durationSeconds || c.duration_seconds || 60,
            timestamp: c.startedAt ? String(c.startedAt).replace("T", " ").slice(0, 16) : "Just now",
            direction: c.direction || "Outbound Auto-Dialer",
            agent: c.agentAliasUsed || "Adriana (AI Voice Bot)",
            amdResult: "Human (99% confidence)",
            recordingUrl: "",
            sipCallId: c.channelId || `sip-${c.id}@talkflow-pbx`,
            qaScore: c.disposition === "qualified" ? 98 : 85,
            qaStatus: "Ingested from Gateway",
            sentiment: c.disposition === "qualified" ? "Very Positive" : "Neutral",
            audioWaveform: [20, 45, 75, 90, 60, 30, 40, 85, 95, 60, 40, 70, 80, 50, 30, 20, 80, 100, 40],
            transcript: (c.transcripts || []).map((t) => ({
              speaker: t.speaker || "Bot",
              time: t.start_ts_ms ? `${Math.floor(t.start_ts_ms / 1000)}s` : "00:05",
              text: t.text || "",
            })),
            notes: `Ingested via fake_gateway scenario. Outcome: ${c.disposition || c.qualificationStatus || "qualified"}.`,
          }));
          setCallsList(mapped);
        }
      }
    } catch (err) {
      console.warn("Failed to fetch ingested calls from API:", err);
    }
  };

  useEffect(() => {
    fetchCalls();
  }, []);

  // Route parsing
  const routeInfo = useMemo(() => {
    if (!initialAction || initialAction === "all" || initialAction === "history") {
      return { mode: "history", callId: null };
    }
    if (initialAction === "live") {
      return { mode: "live", callId: null };
    }
    return { mode: "detail", callId: initialAction };
  }, [initialAction]);

  const navigateToAction = (actionStr) => {
    if (onActionChange) {
      onActionChange(actionStr);
    }
  };

  // Find active call for detail view
  const activeCall = useMemo(() => {
    if (!routeInfo.callId) return callsList[0];
    return (
      callsList.find(
        (c) =>
          c.id.toLowerCase() === routeInfo.callId.toLowerCase() ||
          c.callId.toLowerCase() === routeInfo.callId.toLowerCase()
      ) || callsList[0]
    );
  }, [callsList, routeInfo.callId]);

  // Tabbed detail state for /calls/[callId]
  const [detailTab, setDetailTab] = useState("overview"); // 'overview' | 'audio' | 'transcript' | 'qa'

  // Audio player state
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [audioProgress, setAudioProgress] = useState(35); // %

  // Live monitor action modal / state
  const [activeMonitorChannel, setActiveMonitorChannel] = useState(null);
  const [monitorMode, setMonitorMode] = useState(null); // 'listen' | 'whisper' | 'barge'

  // Filtered CDR Call History
  const filteredCalls = useMemo(() => {
    return callsList.filter((c) => {
      if (dispositionFilter !== "all") {
        if (dispositionFilter === "sale" && !c.disposition.includes("SALE")) return false;
        if (dispositionFilter === "raxfer" && !c.disposition.includes("RAXFER")) return false;
        if (dispositionFilter === "dnc" && !c.disposition.includes("DNC")) return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          c.callId.toLowerCase().includes(q) ||
          c.leadName.toLowerCase().includes(q) ||
          c.phone.toLowerCase().includes(q) ||
          c.campaign.toLowerCase().includes(q) ||
          c.agent.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [callsList, searchQuery, dispositionFilter]);

  // Summary Metrics
  const totalCallsCount = callsList.length;
  const passedCount = callsList.filter((c) => c.disposition.includes("SALE")).length;
  const liveCount = liveCalls.length;

  const openMonitor = (channel, mode) => {
    setActiveMonitorChannel(channel);
    setMonitorMode(mode);
  };

  const closeMonitor = () => {
    setActiveMonitorChannel(null);
  };

  return {
    callsList,
    liveCalls,
    searchQuery,
    setSearchQuery,
    dispositionFilter,
    setDispositionFilter,
    routeInfo,
    activeCall,
    detailTab,
    setDetailTab,
    isPlaying,
    setIsPlaying,
    playbackSpeed,
    setPlaybackSpeed,
    setAudioProgress,
    activeMonitorChannel,
    monitorMode,
    filteredCalls,
    totalCallsCount,
    passedCount,
    liveCount,
    navigateToAction,
    openMonitor,
    closeMonitor,
  };
}