import React, { useState, useMemo, useEffect } from "react";
import {
  ShieldCheck,
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  Play,
  Pause,
  Download,
  Volume2,
  FileText,
  UserCheck,
  ArrowLeft,
  Activity,
  Plus,
  X,
  Check,
  BarChart3,
  TrendingUp,
  Award,
  Users,
  Target,
  Sliders,
  CheckSquare,
  HelpCircle,
  Calendar,
  ListFilter,
  ChevronLeft,
  ChevronRight,
  Info,
} from "lucide-react";
import {
  QA_SCORECARD_TEMPLATES,
  QA_RESULTS_ANALYTICS,
  QA_CALIBRATION_SESSIONS,
  INITIAL_CALLS,
} from "@/data";
import { apiFetch } from "@/lib/api";

export default function QaView({ initialAction, onActionChange }) {
  // Load call records from storage (or API) matching the Calls tab
  const getStoredCalls = () => {
    if (typeof window === "undefined") return INITIAL_CALLS;
    try {
      const saved = localStorage.getItem("talkflow_calls");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) {}
    return INITIAL_CALLS;
  };

  const [callsList, setCallsList] = useState(() => getStoredCalls());

  // Re-fetch calls from storage/API on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = getStoredCalls();
      if (stored && stored.length > 0) {
        setCallsList(stored);
      }
    }
  }, []);

  const [samplingMode, setSamplingMode] = useState("sampled"); // 'sampled' | 'all'

  // Map calls into QA Review Queue records
  const reviewQueue = useMemo(() => {
    const list = callsList.map((c, idx) => {
      const dispo = String(c.disposition || "").toUpperCase();
      const isQualified = dispo.includes("QUALIFIED") || dispo.includes("SALE") || dispo.includes("TRANSFERRED");
      const isFailed = dispo.includes("OPTED_OUT") || dispo.includes("DNC") || dispo.includes("DISQUALIFIED");
      const isLowScore = (c.qaScore || 100) < 90;
      const isRandomSample = idx % 6 === 0;

      const isSampledForQA = isQualified || isFailed || isLowScore || isRandomSample;

      let complianceStatus = isQualified ? "PASSED" : isFailed ? "FAILED" : "NEEDS_REVIEW";
      let samplingBasis = isQualified
        ? "100% Qualified Transfer Audit (PRD FR-10)"
        : isFailed
        ? "Auto-Fail Compliance Audit (FR-06)"
        : isLowScore
        ? "Low Auto-Score Review (<90%)"
        : "15% Random Pilot Daily Sample (FR-10)";

      return {
        id: c.id || `qa-queue-${idx}`,
        callId: c.callId,
        leadName: c.leadName || "Medicare Lead",
        phone: c.phone || "+1 (555) 000-0000",
        agentName: c.agent || "Adriana (AI Voice Bot)",
        campaignName: c.campaign || "Medicare Outbound Fronter",
        callDate: c.timestamp || "Just now",
        duration: c.duration || "02:15",
        autoScore: `${c.qaScore || 85}%`,
        complianceStatus,
        samplingBasis,
        isSampledForQA,
        status: c.qaStatus === "Audited" ? "AUDITED" : "PENDING_MANUAL_AUDIT",
        scorecardTemplate: (c.campaign || "").includes("Medicare")
          ? "Medicare Compliance Standard v2"
          : (c.campaign || "").includes("Solar")
          ? "Solar Lead Qualification Scorecard"
          : "Inbound Customer Care QA",
        rawCall: c,
      };
    });

    if (samplingMode === "sampled") {
      return list.filter((item) => item.isSampledForQA);
    }
    return list;
  }, [callsList, samplingMode]);

  const [scorecards, setScorecards] = useState(QA_SCORECARD_TEMPLATES);
  const [calibrationSessions, setCalibrationSessions] = useState(QA_CALIBRATION_SESSIONS);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  // Pagination for QA Queue
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter]);

  // Parse route string
  const routeInfo = useMemo(() => {
    if (!initialAction || initialAction === "all" || initialAction === "queue") {
      return { mode: "queue", callId: null };
    }
    if (initialAction === "review" || initialAction === "review/") {
      return { mode: "review", callId: null };
    }
    if (initialAction === "scorecards") {
      return { mode: "scorecards", callId: null };
    }
    if (initialAction === "results") {
      return { mode: "results", callId: null };
    }
    if (initialAction === "calibration") {
      return { mode: "calibration", callId: null };
    }

    const parts = initialAction.split("/");
    if (parts[0] === "review") {
      const callId = parts[1] || null;
      return { mode: "review", callId };
    }

    return { mode: "queue", callId: null };
  }, [initialAction]);

  const navigateToAction = (actionStr) => {
    if (onActionChange) {
      onActionChange(actionStr);
    }
  };

  // Find active call for /qa/review and /qa/review/[callId]
  const reviewCall = useMemo(() => {
    if (!routeInfo.callId) return callsList[0] || INITIAL_CALLS[0];
    return (
      callsList.find(
        (c) =>
          c.callId.toLowerCase() === routeInfo.callId.toLowerCase() ||
          c.id.toLowerCase() === routeInfo.callId.toLowerCase()
      ) || callsList[0] || INITIAL_CALLS[0]
    );
  }, [callsList, routeInfo.callId]);

  // Review Workspace Scoring state
  const [scores, setScores] = useState({
    c1: 15,
    c2: 25,
    c3: 30,
    c4: 15,
    c5: 15,
  });
  const [supervisorNotes, setSupervisorNotes] = useState(
    "Agent followed all mandatory TCPA consent disclosures and correctly passed caller to licensed verifier."
  );
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  const calculatedTotalScore = useMemo(() => {
    return Object.values(scores).reduce((acc, curr) => acc + Number(curr), 0);
  }, [scores]);

  const handleSubmitAudit = (e) => {
    e.preventDefault();
    if (!reviewCall) return;

    const updatedCalls = callsList.map((c) => {
      if (
        (c.callId && reviewCall.callId && c.callId.toLowerCase() === reviewCall.callId.toLowerCase()) ||
        (c.id && reviewCall.id && String(c.id).toLowerCase() === String(reviewCall.id).toLowerCase())
      ) {
        return {
          ...c,
          qaStatus: "Audited",
          qaScore: calculatedTotalScore,
        };
      }
      return c;
    });

    setCallsList(updatedCalls);
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("talkflow_calls", JSON.stringify(updatedCalls));
      } catch (err) {}
    }

    navigateToAction(null);
  };

  // Create Scorecard Modal state
  const [isScorecardModalOpen, setIsScorecardModalOpen] = useState(false);
  const [newScTitle, setNewScTitle] = useState("");
  const [newScCampaign, setNewScCampaign] = useState("Med Fronter");

  const handleCreateScorecardSubmit = (e) => {
    e.preventDefault();
    if (!newScTitle.trim()) return;

    const newSc = {
      id: `sc-${Date.now()}`,
      title: newScTitle.trim(),
      campaign: newScCampaign,
      version: "v1.0",
      criteriaCount: 3,
      maxScore: 100,
      status: "active",
      author: "Usama Awan",
      lastUpdated: new Date().toISOString().slice(0, 10),
      criteria: [
        { id: "c1", label: "Greeting & Agent Identification", weight: 30 },
        { id: "c2", label: "Mandatory Consent Disclosure", weight: 40 },
        { id: "c3", label: "Closing / Handoff Accuracy", weight: 30 },
      ],
    };

    setScorecards((prev) => [newSc, ...prev]);
    setIsScorecardModalOpen(false);
    setNewScTitle("");
  };

  // Create Calibration Session / Report Modal state
  const [isCalibModalOpen, setIsCalibModalOpen] = useState(false);
  const [selectedCalibReport, setSelectedCalibReport] = useState(null);

  const [newCalibTitle, setNewCalibTitle] = useState("");
  const [newCalibCallId, setNewCalibCallId] = useState("CALL-98124");
  const [newCalibCampaign, setNewCalibCampaign] = useState("Med Fronter");
  const [newCalibEvaluators, setNewCalibEvaluators] = useState("QA Manager, Usama Awan, Bilal Satti");
  const [newCalibConsensus, setNewCalibConsensus] = useState("96");
  const [newCalibVariance, setNewCalibVariance] = useState("1.4%");
  const [newCalibStatus, setNewCalibStatus] = useState("COMPLETED");
  const [newCalibNotes, setNewCalibNotes] = useState(
    "Evaluators audited sample call together. Reached 96% consensus on Medicare Part B qualification guidelines with minimal scoring variance."
  );

  const handleCreateCalibrationSubmit = (e) => {
    e.preventDefault();
    if (!newCalibTitle.trim()) return;

    const evaluatorsArray = newCalibEvaluators.split(",").map((s) => s.trim()).filter(Boolean);

    const newCalib = {
      id: `cal-${Date.now()}`,
      sessionTitle: newCalibTitle.trim(),
      date: new Date().toISOString().slice(0, 16).replace("T", " "),
      evaluators: evaluatorsArray.length > 0 ? evaluatorsArray : ["QA Manager", "Usama Awan"],
      sampleCallId: newCalibCallId,
      campaign: newCalibCampaign,
      varianceScore: newCalibVariance,
      consensusScore: Number(newCalibConsensus) || 95,
      status: newCalibStatus,
      notes: newCalibNotes,
    };

    setCalibrationSessions((prev) => [newCalib, ...prev]);
    setIsCalibModalOpen(false);
    setNewCalibTitle("");
    setNewCalibNotes("");
  };

  // Filtered Review Queue with Pagination
  const filteredQueue = useMemo(() => {
    return reviewQueue.filter((item) => {
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          item.callId.toLowerCase().includes(q) ||
          item.agentName.toLowerCase().includes(q) ||
          item.campaignName.toLowerCase().includes(q) ||
          item.leadName.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [reviewQueue, searchQuery, statusFilter]);

  const totalItems = filteredQueue.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage) || 1;
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedQueue = filteredQueue.slice(startIndex, startIndex + itemsPerPage);

  const subtabs = [
    { id: "queue", label: "QA review queue", icon: ListFilter, action: null },
    { id: "review", label: "Review workspace", icon: ShieldCheck, action: "review" },
    { id: "scorecards", label: "Scorecard templates", icon: Sliders, action: "scorecards" },
    { id: "results", label: "QA results and trends", icon: TrendingUp, action: "results" },
    { id: "calibration", label: "Calibration sessions", icon: Users, action: "calibration" },
  ];

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-6 text-neutral-900 dark:text-neutral-100 font-sans min-h-screen bg-neutral-50 dark:bg-[#050505] transition-colors duration-200">
      {/* Top Segmented Subtabs Navigation Bar */}
      <div className="flex items-center gap-1 overflow-x-auto rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-1.5 shadow-xs">
        {subtabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = routeInfo.mode === tab.id;

          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => navigateToAction(tab.action)}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition-all duration-150 ${
                isActive
                  ? "bg-blue-600 text-white dark:bg-[#253246] dark:text-blue-300 shadow-xs font-bold"
                  : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 hover:text-neutral-900 dark:hover:bg-[#151518] dark:hover:text-white"
              }`}
            >
              <Icon className={`h-3.5 w-3.5 ${isActive ? "text-white dark:text-blue-300" : "opacity-70"}`} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* ========================================================================= */}
      {/* ROUTE 1: /qa (QA Review Queue) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "queue" && (
        <div className="flex flex-col gap-6">
          {/* Header Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-200 dark:border-neutral-800/80 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-neutral-900 dark:text-white tracking-tight">
                  QA Review Queue
                </h1>
                <span className="rounded-full bg-blue-100 text-blue-700 dark:bg-blue-950/80 dark:text-blue-400 px-2.5 py-0.5 text-[10px] font-bold border border-blue-300">
                  {totalItems} Calls Synced from CDR
                </span>
              </div>
              <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
                Audit all calls from the Calls tab, evaluate agent compliance checklists, and submit quality scores.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => navigateToAction("scorecards")}
                className="inline-flex items-center gap-1.5 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3.5 py-2 text-xs font-semibold text-neutral-800 dark:text-white hover:bg-neutral-100"
              >
                <Sliders className="h-4 w-4 text-purple-500" />
                <span>Scorecard Templates</span>
              </button>

              <button
                type="button"
                onClick={() => navigateToAction("results")}
                className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700 transition-colors"
              >
                <BarChart3 className="h-4 w-4" />
                <span>QA Results & Trends</span>
              </button>
            </div>
          </div>



          {/* Quick Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs text-neutral-500 font-medium">Total Calls in QA Queue</span>
              <div className="text-2xl font-extrabold text-neutral-900 dark:text-white mt-1">
                {totalItems}
              </div>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs text-neutral-500 font-medium">Audited Calls</span>
              <div className="text-2xl font-extrabold text-blue-600 dark:text-blue-400 mt-1">
                {reviewQueue.filter((q) => q.status === "AUDITED").length || 42}
              </div>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs text-neutral-500 font-medium">Average QA Score</span>
              <div className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-1">
                {QA_RESULTS_ANALYTICS.avgQaScore}%
              </div>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs text-neutral-500 font-medium">TCPA Compliance Rate</span>
              <div className="text-2xl font-extrabold text-purple-600 dark:text-purple-400 mt-1">
                {QA_RESULTS_ANALYTICS.overallPassRate}
              </div>
            </div>
          </div>

          {/* Search & Filter Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-neutral-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search Call ID, lead name, agent, campaign..."
                className="w-full rounded-lg border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] py-2 pl-9 pr-3 text-xs outline-none focus:border-blue-500"
              />
            </div>

            {/* QA Queue Sampling Filter Toggle */}
            <div className="flex items-center rounded-lg border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-1 text-xs shadow-xs">
              <button
                type="button"
                onClick={() => setSamplingMode("sampled")}
                className={`rounded-md px-3 py-1 font-semibold text-[11px] transition-colors ${
                  samplingMode === "sampled"
                    ? "bg-blue-600 text-white shadow-xs"
                    : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
                }`}
              >
                Sampled QA Queue (PRD FR-10)
              </button>
              <button
                type="button"
                onClick={() => setSamplingMode("all")}
                className={`rounded-md px-3 py-1 font-semibold text-[11px] transition-colors ${
                  samplingMode === "all"
                    ? "bg-blue-600 text-white shadow-xs"
                    : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
                }`}
              >
                All CDR Log ({callsList.length} Calls)
              </button>
            </div>
          </div>

          {/* Review Queue Table */}
          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[950px] text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                    <th className="py-2.5 px-3">Call Reference</th>
                    <th className="py-2.5 px-3">Customer / Lead</th>
                    <th className="py-2.5 px-3">Campaign</th>
                    <th className="py-2.5 px-3">Duration</th>
                    <th className="py-2.5 px-3">Auto Score</th>
                    <th className="py-2.5 px-3">Compliance</th>
                    <th className="py-2.5 px-3">Evaluation Basis (PRD)</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {paginatedQueue.length > 0 ? (
                    paginatedQueue.map((item) => (
                      <tr
                        key={item.id}
                        onClick={() => navigateToAction(`review/${item.callId}`)}
                        className="cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-900/50 transition-colors"
                      >
                        <td className="py-3.5 px-3 font-mono font-bold text-blue-600 dark:text-blue-400 hover:underline">
                          {item.callId}
                        </td>
                        <td className="py-3.5 px-3 font-semibold text-neutral-900 dark:text-white">
                          <div className="flex flex-col">
                            <span>{item.leadName}</span>
                            <span className="font-mono text-[11px] text-neutral-400 font-normal">{item.phone}</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-3 font-medium text-neutral-700 dark:text-neutral-300">
                          {item.campaignName}
                        </td>
                        <td className="py-3.5 px-3 font-mono">{item.duration}</td>
                        <td className="py-3.5 px-3 font-bold text-emerald-600">{item.autoScore}</td>
                        <td className="py-3.5 px-3">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold border ${
                              item.complianceStatus === "PASSED"
                                ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                                : item.complianceStatus === "FAILED"
                                ? "border-rose-300 bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300"
                                : "border-amber-300 bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300"
                            }`}
                          >
                            {item.complianceStatus}
                          </span>
                        </td>
                        <td className="py-3.5 px-3 text-[11px] text-neutral-600 dark:text-neutral-400">
                          {item.samplingBasis}
                        </td>
                        <td className="py-3.5 px-3 text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigateToAction(`review/${item.callId}`);
                            }}
                            className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1 text-xs font-bold text-white hover:bg-blue-700"
                          >
                            <ShieldCheck className="h-3.5 w-3.5" />
                            <span>Audit Call</span>
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-xs text-neutral-500 italic">
                        No matching call records found in QA review queue.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-neutral-200 dark:border-neutral-800 text-xs">
              <div className="text-neutral-500">
                Showing <strong className="text-neutral-900 dark:text-white">{totalItems > 0 ? startIndex + 1 : 0}</strong> to{" "}
                <strong className="text-neutral-900 dark:text-white">{Math.min(startIndex + itemsPerPage, totalItems)}</strong> of{" "}
                <strong className="text-neutral-900 dark:text-white">{totalItems}</strong> QA Review Calls
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                  className="inline-flex items-center gap-1 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-3 py-1.5 text-xs font-semibold hover:bg-neutral-100 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="h-4 w-4" />
                  <span>Previous</span>
                </button>

                <span className="px-3 py-1 font-bold text-neutral-800 dark:text-neutral-200">
                  Page {currentPage} of {totalPages}
                </span>

                <button
                  type="button"
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                  className="inline-flex items-center gap-1 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-3 py-1.5 text-xs font-semibold hover:bg-neutral-100 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <span>Next</span>
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 2 & 3: /qa/review & /qa/review/[callId] (Review Workspace) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "review" && reviewCall && (
        <div className="flex flex-col gap-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-200 dark:border-neutral-800/80 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                    QA Review Workspace
                  </h2>
                  <span className="font-mono text-xs font-bold bg-blue-100 text-blue-700 px-2 py-0.5 rounded border border-blue-200">
                    {routeInfo.callId ? `Call ${routeInfo.callId}` : "All Calls Queue"}
                  </span>
                </div>
                <span className="text-xs text-neutral-500">
                  Audit call recordings, evaluate agent compliance checklist, and submit quality scores.
                </span>
              </div>
            </div>

            {/* Select Call Selector Dropdown */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 px-3 py-1.5 rounded-lg text-xs">
                <span className="font-bold text-neutral-500 whitespace-nowrap">Select Call to Audit:</span>
                <select
                  value={reviewCall.callId}
                  onChange={(e) => navigateToAction(`review/${e.target.value}`)}
                  className="bg-transparent font-mono font-bold text-blue-600 outline-none cursor-pointer"
                >
                  {INITIAL_CALLS.map((c) => (
                    <option key={c.id} value={c.callId}>
                      {c.callId} - {c.leadName} ({c.campaign})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-neutral-500">Total QA Score:</span>
                <span className="text-2xl font-extrabold text-emerald-600">{calculatedTotalScore} / 100</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column: Audio Player & AI Transcript */}
            <div className="flex flex-col gap-4">
              <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold">Stereo Audio Recording Playback</span>
                  <span className="font-mono text-blue-600 font-bold">{reviewCall.callId}</span>
                </div>
                <div className="bg-neutral-50 dark:bg-[#151518] p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => setIsPlayingAudio(!isPlayingAudio)}
                    className="p-2.5 bg-blue-600 text-white rounded-full hover:bg-blue-700"
                  >
                    {isPlayingAudio ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
                  </button>
                  <div className="flex items-center gap-1 h-6 flex-1 mx-4">
                    {reviewCall.audioWaveform.map((val, idx) => (
                      <div
                        key={idx}
                        className="w-1.5 bg-blue-500 rounded-full"
                        style={{ height: `${val}%` }}
                      />
                    ))}
                  </div>
                  <span className="font-mono text-[11px] text-neutral-500">{reviewCall.duration}</span>
                </div>
              </div>

              <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-3 text-xs max-h-96 overflow-y-auto">
                <span className="font-bold">Time-coded Call Transcript</span>
                {reviewCall.transcript.map((item, idx) => (
                  <div key={idx} className="bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 flex flex-col gap-0.5">
                    <div className="flex justify-between font-bold text-[10px] text-blue-600">
                      <span>{item.speaker}</span>
                      <span className="font-mono text-neutral-400">{item.time}</span>
                    </div>
                    <p className="text-neutral-800 dark:text-neutral-200">{item.text}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Right Column: Interactive Scorecard */}
            <form
              onSubmit={handleSubmitAudit}
              className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-5 text-xs"
            >
              <h3 className="text-sm font-bold border-b border-neutral-100 dark:border-neutral-800 pb-3">
                Scorecard Evaluation Checklist (Medicare Compliance Standard v2)
              </h3>

              <div className="flex flex-col gap-4">
                {[
                  { key: "c1", label: "Greeting & Agent Identification", max: 15 },
                  { key: "c2", label: "TCPA Recorded Consent Capture", max: 25 },
                  { key: "c3", label: "Medicare A & B Qualification Check", max: 30 },
                  { key: "c4", label: "Professional Tone & Active Listening", max: 15 },
                  { key: "c5", label: "Licensed Verifier Handoff Protocol", max: 15 },
                ].map((item) => (
                  <div key={item.key} className="flex items-center justify-between bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
                    <span className="font-semibold text-neutral-800 dark:text-neutral-200">{item.label} (Max {item.max} pts)</span>
                    <input
                      type="number"
                      min={0}
                      max={item.max}
                      value={scores[item.key]}
                      onChange={(e) =>
                        setScores({ ...scores, [item.key]: Number(e.target.value) })
                      }
                      className="w-16 rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-[#09090b] px-2 py-1 text-center font-bold text-blue-600 outline-none"
                    />
                  </div>
                ))}
              </div>

              <div className="flex flex-col gap-1.5 border-t border-neutral-200 dark:border-neutral-800 pt-4">
                <label className="font-bold text-neutral-800 dark:text-neutral-200">
                  Evaluator Feedback & Coaching Notes
                </label>
                <textarea
                  rows={3}
                  value={supervisorNotes}
                  onChange={(e) => setSupervisorNotes(e.target.value)}
                  className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] p-3 text-xs outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-neutral-200 dark:border-neutral-800">
                <button
                  type="button"
                  onClick={() => navigateToAction(null)}
                  className="px-4 py-2 font-semibold text-neutral-500 hover:text-neutral-900"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-md shadow-xs"
                >
                  Submit Official Audit Score ({calculatedTotalScore}%)
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 4: /qa/scorecards (Scorecard Templates) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "scorecards" && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800/80 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  Scorecard Templates
                </h2>
                <p className="text-xs text-neutral-500">
                  Configure evaluation criteria, point weights, and compliance rules for QA audits.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setIsScorecardModalOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700"
            >
              <Plus className="h-4 w-4" />
              <span>Create Scorecard Template</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {scorecards.map((sc) => (
              <div key={sc.id} className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col justify-between gap-4">
                <div className="flex flex-col gap-3 text-xs">
                  <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
                    <span className="font-bold text-neutral-900 dark:text-white">{sc.title}</span>
                    <span className="font-mono text-xs font-bold text-blue-600">{sc.version}</span>
                  </div>
                  <span className="text-neutral-500">Campaign: {sc.campaign}</span>
                  <div className="flex flex-col gap-1.5 bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
                    <span className="font-bold text-neutral-700 dark:text-neutral-300">Criteria ({sc.criteriaCount} rules):</span>
                    <ul className="list-disc list-inside space-y-1 text-neutral-600 dark:text-neutral-400 text-[11px]">
                      {sc.criteria.map((c) => (
                        <li key={c.id}>{c.label} ({c.weight} pts)</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Modal */}
          {isScorecardModalOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
              <div className="w-full max-w-md rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#121214] p-6 shadow-2xl flex flex-col gap-4 text-xs">
                <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3">
                  <h3 className="text-base font-bold">Create New Scorecard Template</h3>
                  <button onClick={() => setIsScorecardModalOpen(false)} className="text-neutral-400 hover:text-white">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <form onSubmit={handleCreateScorecardSubmit} className="flex flex-col gap-4">
                  <div>
                    <label className="block font-bold mb-1">Scorecard Title</label>
                    <input
                      type="text"
                      required
                      value={newScTitle}
                      onChange={(e) => setNewScTitle(e.target.value)}
                      placeholder="e.g. Inbound Retention QA Scorecard"
                      className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-2 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block font-bold mb-1">Target Campaign</label>
                    <select
                      value={newScCampaign}
                      onChange={(e) => setNewScCampaign(e.target.value)}
                      className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-2 outline-none"
                    >
                      <option value="Med Fronter">Med Fronter</option>
                      <option value="Solar Outreach East">Solar Outreach East</option>
                      <option value="Insurance Renewals">Insurance Renewals</option>
                    </select>
                  </div>
                  <div className="flex justify-end gap-2 pt-2 border-t border-neutral-200 dark:border-neutral-800">
                    <button type="button" onClick={() => setIsScorecardModalOpen(false)} className="px-3 py-1.5 text-neutral-500">
                      Cancel
                    </button>
                    <button type="submit" className="px-4 py-1.5 font-bold bg-blue-600 text-white rounded-md">
                      Create Template
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 5: /qa/results (QA Results and Trends) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "results" && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800/80 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  QA Results & Analytics Trends
                </h2>
                <p className="text-xs text-neutral-500">
                  Compliance rule violations, agent QA rankings, and monthly score trends.
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
              <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                Top Compliance Violations Tracked
              </h3>
              <div className="flex flex-col gap-3 text-xs">
                {QA_RESULTS_ANALYTICS.topViolations.map((v, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
                    <span className="font-semibold text-neutral-800 dark:text-neutral-200">{v.rule}</span>
                    <span className="font-bold text-rose-600">{v.count} occurrences ({v.percentage})</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
              <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                Agent Quality Ranking Summary
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                      <th className="py-2.5 px-3">Agent</th>
                      <th className="py-2.5 px-3">Total Audited</th>
                      <th className="py-2.5 px-3">Avg Score</th>
                      <th className="py-2.5 px-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                    {QA_RESULTS_ANALYTICS.agentRankings.map((ag, idx) => (
                      <tr key={idx}>
                        <td className="py-3 px-3 font-bold">{ag.agent}</td>
                        <td className="py-3 px-3 font-mono">{ag.totalAudited}</td>
                        <td className="py-3 px-3 font-bold text-emerald-600">{ag.avgScore}%</td>
                        <td className="py-3 px-3 font-semibold text-blue-600">{ag.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 6: /qa/calibration (Calibration Sessions & Reports) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "calibration" && (
        <div className="flex flex-col gap-6">
          {/* Section Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-200 dark:border-neutral-800/80 pb-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  QA Calibration Sessions & Reports
                </h2>
                <p className="text-xs text-neutral-500">
                  Align evaluators, audit sample calls together, and measure scoring variance.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setIsCalibModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-blue-600 rounded-lg shadow-xs hover:bg-blue-700 transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>Create Calibration Report</span>
            </button>
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs flex flex-col gap-1">
              <span className="text-neutral-500">Total Audit Sessions</span>
              <span className="text-xl font-extrabold text-neutral-900 dark:text-white">{calibrationSessions.length}</span>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs flex flex-col gap-1">
              <span className="text-neutral-500">Avg Scoring Variance</span>
              <span className="text-xl font-extrabold text-purple-600">1.8%</span>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs flex flex-col gap-1">
              <span className="text-neutral-500">Benchmark Consensus</span>
              <span className="text-xl font-extrabold text-emerald-600">95.3%</span>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs flex flex-col gap-1">
              <span className="text-neutral-500">Aligned Evaluators</span>
              <span className="text-xl font-extrabold text-blue-600">8 Members</span>
            </div>
          </div>

          {/* Calibration Sessions Table */}
          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                    <th className="py-2.5 px-3">Session Title</th>
                    <th className="py-2.5 px-3">Date</th>
                    <th className="py-2.5 px-3">Sample Call ID</th>
                    <th className="py-2.5 px-3">Campaign</th>
                    <th className="py-2.5 px-3">Variance Score</th>
                    <th className="py-2.5 px-3">Consensus Score</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Report Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {calibrationSessions.map((cal) => (
                    <tr key={cal.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                      <td className="py-3.5 px-3 font-bold text-neutral-900 dark:text-white">{cal.sessionTitle}</td>
                      <td className="py-3.5 px-3 text-neutral-500">{cal.date}</td>
                      <td className="py-3.5 px-3 font-mono font-bold text-blue-600">{cal.sampleCallId}</td>
                      <td className="py-3.5 px-3 font-semibold">{cal.campaign}</td>
                      <td className="py-3.5 px-3 font-bold text-purple-600">{cal.varianceScore}</td>
                      <td className="py-3.5 px-3 font-bold text-emerald-600">
                        {cal.consensusScore > 0 ? `${cal.consensusScore}%` : "—"}
                      </td>
                      <td className="py-3.5 px-3">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          cal.status === "COMPLETED"
                            ? "bg-emerald-100 text-emerald-700 border border-emerald-300"
                            : cal.status === "SCHEDULED"
                            ? "bg-amber-100 text-amber-700 border border-amber-300"
                            : "bg-blue-100 text-blue-700 border border-blue-300"
                        }`}>
                          {cal.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 text-right">
                        <button
                          type="button"
                          onClick={() => setSelectedCalibReport(cal)}
                          className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold text-blue-600 bg-blue-50 dark:bg-blue-950/40 rounded-md border border-blue-200 dark:border-blue-800 hover:bg-blue-100"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          <span>View Report</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* MODAL 1: Create Calibration Report / Session Modal */}
          {isCalibModalOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
              <div className="w-full max-w-xl rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-2xl flex flex-col gap-4 text-xs">
                <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-5 w-5 text-blue-600" />
                    <h3 className="text-base font-bold text-neutral-900 dark:text-white">
                      Create QA Calibration Session & Report
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsCalibModalOpen(false)}
                    className="p-1 text-neutral-400 hover:text-neutral-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <form onSubmit={handleCreateCalibrationSubmit} className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label className="font-bold text-neutral-800 dark:text-neutral-200">
                      Calibration Session Title
                    </label>
                    <input
                      type="text"
                      required
                      value={newCalibTitle}
                      onChange={(e) => setNewCalibTitle(e.target.value)}
                      placeholder="e.g. Q3 Medicare Part B Qualification Alignment"
                      className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none focus:border-blue-500"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="font-bold text-neutral-800 dark:text-neutral-200">
                        Target Campaign
                      </label>
                      <select
                        value={newCalibCampaign}
                        onChange={(e) => setNewCalibCampaign(e.target.value)}
                        className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none"
                      >
                        <option value="Med Fronter">Med Fronter</option>
                        <option value="Solar Outreach East">Solar Outreach East</option>
                        <option value="Insurance Renewals">Insurance Renewals</option>
                      </select>
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="font-bold text-neutral-800 dark:text-neutral-200">
                        Sample Call ID
                      </label>
                      <select
                        value={newCalibCallId}
                        onChange={(e) => setNewCalibCallId(e.target.value)}
                        className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none font-mono"
                      >
                        <option value="CALL-98124">CALL-98124 (Adriana)</option>
                        <option value="CALL-98125">CALL-98125 (Harper)</option>
                        <option value="CALL-98130">CALL-98130 (Carlos Ray)</option>
                        <option value="CALL-98127">CALL-98127 (Jennifer)</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="font-bold text-neutral-800 dark:text-neutral-200">
                      Evaluators & Participants (comma separated)
                    </label>
                    <input
                      type="text"
                      required
                      value={newCalibEvaluators}
                      onChange={(e) => setNewCalibEvaluators(e.target.value)}
                      placeholder="e.g. QA Manager, Usama Awan, Bilal Satti, Adriana"
                      className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none focus:border-blue-500"
                    />
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    <div className="flex flex-col gap-1.5">
                      <label className="font-bold text-neutral-800 dark:text-neutral-200">
                        Consensus Score (%)
                      </label>
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={newCalibConsensus}
                        onChange={(e) => setNewCalibConsensus(e.target.value)}
                        className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none"
                      />
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="font-bold text-neutral-800 dark:text-neutral-200">
                        Scoring Variance
                      </label>
                      <input
                        type="text"
                        value={newCalibVariance}
                        onChange={(e) => setNewCalibVariance(e.target.value)}
                        placeholder="e.g. 1.2%"
                        className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none"
                      />
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="font-bold text-neutral-800 dark:text-neutral-200">
                        Session Status
                      </label>
                      <select
                        value={newCalibStatus}
                        onChange={(e) => setNewCalibStatus(e.target.value)}
                        className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none"
                      >
                        <option value="COMPLETED">COMPLETED</option>
                        <option value="SCHEDULED">SCHEDULED</option>
                        <option value="IN_PROGRESS">IN_PROGRESS</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="font-bold text-neutral-800 dark:text-neutral-200">
                      Calibration Findings & Evaluator Alignment Summary
                    </label>
                    <textarea
                      rows={3}
                      value={newCalibNotes}
                      onChange={(e) => setNewCalibNotes(e.target.value)}
                      placeholder="Detail scoring differences, TCPA consent interpretation, and guidelines agreed upon..."
                      className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] p-3 text-xs outline-none focus:border-blue-500"
                    />
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-200 dark:border-neutral-800">
                    <button
                      type="button"
                      onClick={() => setIsCalibModalOpen(false)}
                      className="px-4 py-2 font-semibold text-neutral-600 dark:text-neutral-400 hover:text-neutral-900"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-5 py-2 font-bold text-white bg-blue-600 rounded-md hover:bg-blue-700 shadow-xs"
                    >
                      Save Calibration Report
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* MODAL 2: View Calibration Report Detail Modal */}
          {selectedCalibReport && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
              <div className="w-full max-w-2xl rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-2xl flex flex-col gap-5 text-xs max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-purple-50 dark:bg-purple-950/40 text-purple-600 border border-purple-200 dark:border-purple-800">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-neutral-900 dark:text-white">
                        QA Calibration Report & Evaluator Audit
                      </h3>
                      <p className="text-xs text-neutral-500">
                        {selectedCalibReport.sessionTitle}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedCalibReport(null)}
                    className="p-1 text-neutral-400 hover:text-neutral-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                {/* Key Metrics Cards */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 flex flex-col gap-0.5">
                    <span className="text-[11px] font-semibold text-neutral-500">Consensus Score</span>
                    <span className="text-lg font-bold text-emerald-600">
                      {selectedCalibReport.consensusScore > 0 ? `${selectedCalibReport.consensusScore}%` : "Pending"}
                    </span>
                  </div>
                  <div className="bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 flex flex-col gap-0.5">
                    <span className="text-[11px] font-semibold text-neutral-500">Scoring Variance</span>
                    <span className="text-lg font-bold text-purple-600">{selectedCalibReport.varianceScore}</span>
                  </div>
                  <div className="bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 flex flex-col gap-0.5">
                    <span className="text-[11px] font-semibold text-neutral-500">Sample Call</span>
                    <span className="text-sm font-bold text-blue-600 font-mono">{selectedCalibReport.sampleCallId}</span>
                  </div>
                </div>

                {/* Evaluator Alignment Breakdown */}
                <div className="flex flex-col gap-2">
                  <h4 className="font-bold text-neutral-900 dark:text-white text-xs uppercase tracking-wider text-neutral-500">
                    Participating Evaluators & Individual Scoring
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {(selectedCalibReport.evaluators || []).map((ev, idx) => (
                      <div key={idx} className="flex items-center justify-between p-2.5 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518]">
                        <span className="font-bold text-neutral-800 dark:text-neutral-200">{ev}</span>
                        <span className="font-mono text-xs font-bold text-emerald-600">
                          {selectedCalibReport.consensusScore > 0 ? `${selectedCalibReport.consensusScore + (idx % 2 === 0 ? 1 : -1)}%` : "Pending"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Calibration Findings & Summary */}
                <div className="flex flex-col gap-2 bg-blue-50 dark:bg-blue-950/40 p-4 rounded-xl border border-blue-200 dark:border-blue-800">
                  <h4 className="font-bold text-blue-900 dark:text-blue-200 text-xs">
                    Calibration Audit Findings & Consensus Notes
                  </h4>
                  <p className="text-xs text-blue-800 dark:text-blue-300 leading-relaxed">
                    {selectedCalibReport.notes ||
                      "Evaluators audited the sample recording together. Discrepancies in consent phrasing were discussed and resolved, aligning evaluator criteria within acceptable 1.5% variance threshold."}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-neutral-200 dark:border-neutral-800">
                  <span className="text-xs text-neutral-500">
                    Session Date: {selectedCalibReport.date} | Campaign: {selectedCalibReport.campaign}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => alert(`Calibration report for ${selectedCalibReport.sessionTitle} exported.`)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 font-bold text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100 border border-blue-200"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>Export PDF</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedCalibReport(null)}
                      className="px-4 py-1.5 font-bold text-white bg-neutral-900 dark:bg-neutral-800 rounded-md hover:bg-neutral-700"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
