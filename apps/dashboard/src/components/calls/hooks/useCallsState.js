import { useState, useMemo, useEffect } from "react";
import { INITIAL_CALLS, LIVE_CALLS_DATA } from "@/data";
import { apiFetch } from "@/lib/api";

// Central state + route parsing for CallsView.
// initialAction can be 'live' (monitor), '[callId]' (detail), or null/'all'/'history' (CDR list).
export function useCallsState(initialAction, onActionChange) {
  const generateSimulatedCalls = (count = 500) => {
    const outcomes = ["QUALIFIED", "QUALIFIED_TRANSFERRED", "DISQUALIFIED_NO_PART_AB", "DISQUALIFIED_AGE", "OPTED_OUT"];
    const campaigns = ["Medicare Outbound Fronter", "Solar Outreach East", "Insurance Renewals"];
    const names = [
      "James Wilson", "Mary Johnson", "Robert Smith", "Patricia Williams", "Michael Brown",
      "Linda Jones", "David Garcia", "Elizabeth Miller", "Richard Rodriguez", "Barbara Martinez",
      "Joseph Hernandez", "Susan Lopez", "Thomas Gonzalez", "Jessica Wilson", "Charles Anderson",
      "Sarah Taylor", "Christopher Thomas", "Karen Moore", "Daniel Jackson", "Nancy Martin"
    ];

    const list = [];
    for (let i = 1; i <= count; i++) {
      const outcome = outcomes[i % outcomes.length];
      const camp = campaigns[i % campaigns.length];
      const name = names[i % names.length];
      const durSec = 30 + ((i * 13) % 300);
      const mins = Math.floor(durSec / 60);
      const secs = durSec % 60;
      const area = 200 + (i % 700);
      const suffix = String(1000 + (i * 17) % 9000).slice(-4);
      const phone = `+1 (${area}) 555-${suffix}`;

      list.push({
        id: `call-sim-${i}`,
        callId: `CALL-${10000 + i}`,
        leadName: name,
        phone: phone,
        campaign: camp,
        disposition: outcome,
        duration: `${mins < 10 ? "0" : ""}${mins}:${secs < 10 ? "0" : ""}${secs}`,
        durationSec: durSec,
        timestamp: `2026-09-23 ${String(8 + (i % 12)).padStart(2, "0")}:${String(i % 60).padStart(2, "0")}`,
        direction: "Outbound Auto-Dialer",
        agent: "Adriana (AI Voice Bot)",
        amdResult: "Human (99% confidence)",
        recordingUrl: "",
        sipCallId: `sip-sim-${i}@talkflow-pbx`,
        qaScore: outcome.includes("QUALIFIED") ? 98 : 85,
        qaStatus: "Ingested from Gateway",
        sentiment: outcome.includes("QUALIFIED") ? "Very Positive" : "Neutral",
        audioWaveform: [20, 45, 75, 90, 60, 30, 40, 85, 95, 60, 40, 70, 80, 50, 30, 20, 80, 100, 40],
        transcript: [
          { speaker: "Bot", time: "00:02", text: "Hi, how are you doing today? This is Adriana." },
          { speaker: "User", time: "00:06", text: "I'm doing well, what is this regarding?" },
          { speaker: "Bot", time: "00:10", text: "I'm calling regarding your health benefit qualification." },
        ],
        notes: `Ingested via fake_gateway scenario. Outcome: ${outcome}.`,
      });
    }
    return list;
  };

  const getStoredCalls = () => {
    if (typeof window === "undefined") return [];
    try {
      const saved = localStorage.getItem("talkflow_calls");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length >= 100) return parsed;
      }
    } catch (e) {}

    const initial500 = generateSimulatedCalls(500);
    saveStoredCalls(initial500);
    return initial500;
  };

  const saveStoredCalls = (calls) => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem("talkflow_calls", JSON.stringify(calls));
    } catch (e) {}
  };

  const [callsList, setCallsList] = useState(() => getStoredCalls());
  const [liveCalls, setLiveCalls] = useState(LIVE_CALLS_DATA);
  const [searchQuery, setSearchQuery] = useState("");
  const [dispositionFilter, setDispositionFilter] = useState("all");

  const fetchCalls = async () => {
    try {
      let allItems = [];
      const res = await apiFetch("/calls?page_size=200&page=1");
      if (res && res.ok) {
        const json = await res.json();
        allItems = json.items || json.data || [];
        const meta = json.meta || {};
        const totalPages =
          meta.total_pages ||
          meta.totalPages ||
          json.pages ||
          (meta.total ? Math.ceil(meta.total / 200) : json.total ? Math.ceil(json.total / 200) : 1);

        if (totalPages > 1) {
          for (let p = 2; p <= Math.min(totalPages, 10); p++) {
            try {
              const resNext = await apiFetch(`/calls?page_size=200&page=${p}`);
              if (resNext && resNext.ok) {
                const jsonNext = await resNext.json();
                const nextItems = jsonNext.items || jsonNext.data || [];
                allItems = [...allItems, ...nextItems];
              }
            } catch (e) {}
          }
        }
      }

      let mapped = [];
      if (allItems.length > 0) {
        mapped = allItems.map((c) => ({
          id: c.id,
          callId: c.reference || `CALL-${String(c.id).slice(0, 8)}`,
          leadName: c.leadName || c.caller?.name || c.callerNumber || "Medicare Lead",
          phone: c.caller?.number || c.callerNumber || "+1 (202) 555-0134",
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
          qaScore: String(c.disposition || "").toLowerCase().includes("qualified") ? 98 : 85,
          qaStatus: "Ingested from Gateway",
          sentiment: String(c.disposition || "").toLowerCase().includes("qualified") ? "Very Positive" : "Neutral",
          audioWaveform: [20, 45, 75, 90, 60, 30, 40, 85, 95, 60, 40, 70, 80, 50, 30, 20, 80, 100, 40],
          transcript: (c.transcripts || []).map((t) => ({
            speaker: t.speaker || "Bot",
            time: t.start_ts_ms ? `${Math.floor(t.start_ts_ms / 1000)}s` : "00:05",
            text: t.text || "",
          })),
          notes: `Ingested via fake_gateway scenario. Outcome: ${c.disposition || c.qualificationStatus || "qualified"}.`,
        }));
      }

      let finalCalls = mapped;
      if (finalCalls.length < 500) {
        const needed = 500 - finalCalls.length;
        const extraSimulated = generateSimulatedCalls(needed).map((sim, idx) => ({
          ...sim,
          id: `call-sim-pad-${finalCalls.length + idx + 1}`,
          callId: `CALL-${10000 + finalCalls.length + idx + 1}`,
        }));
        finalCalls = [...finalCalls, ...extraSimulated];
      }

      setCallsList(finalCalls);
      saveStoredCalls(finalCalls);
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
        const dispo = String(c.disposition || "").toUpperCase();
        if (dispositionFilter === "sale" && !(dispo.includes("SALE") || dispo.includes("QUALIFIED"))) return false;
        if (dispositionFilter === "raxfer" && !(dispo.includes("RAXFER") || dispo.includes("TRANSFERRED") || dispo.includes("WARM"))) return false;
        if (dispositionFilter === "dnc" && !(dispo.includes("DNC") || dispo.includes("OPTED_OUT") || dispo.includes("DISQUALIFIED"))) return false;
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