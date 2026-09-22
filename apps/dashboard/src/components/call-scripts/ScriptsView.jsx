"use client";

import React, { useState, useMemo } from "react";
import {
  Plus,
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  Play,
  Copy,
  History,
  FileText,
  Sparkles,
  ShieldCheck,
  PhoneForwarded,
  X,
  Check,
  Edit3,
  ArrowRight,
  Eye,
  Sliders,
  ChevronRight,
  Bot,
  UserCheck,
  ArrowLeft,
  GitCompare,
  CheckSquare,
  XCircle,
  RotateCcw,
  MessageSquare,
  Sparkle,
} from "lucide-react";
import { INITIAL_SCRIPTS, APPROVAL_QUEUE_SCRIPTS } from "@/data";
import { apiFetch } from "@/lib/api";

export default function ScriptsView({ initialAction, onActionChange }) {
  const [scripts, setScripts] = useState(INITIAL_SCRIPTS);
  const [approvalQueue, setApprovalQueue] = useState(APPROVAL_QUEUE_SCRIPTS);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const fetchScripts = async () => {
    try {
      const res = await apiFetch("/scripts");
      if (res.ok) {
        const json = await res.json();
        const items = json.items || json.data || [];
        const mapped = items.map((s) => ({
          id: s.id,
          name: s.name,
          version: s.active_version ? `v${s.active_version}.0` : `v${s.current_version || 1}.0`,
          campaignId: "c-custom",
          campaignName: s.name.includes("Med") ? "Med Fronter" : "Standard Campaign",
          status: s.status || "draft",
          approvedBy: s.status === "approved" || s.status === "active" ? "QA Director" : "Pending Approval",
          author: "Bilal Satti",
          updatedAt: "Recent",
          qualificationRate: "72.4%",
          transferRate: "68.1%",
          dropOffRate: "12.0%",
          fallbackCount: 0,
          greeting: s.greeting || "Hello, thank you for taking our call.",
          consent: s.consent || "Calls are recorded for quality assurance.",
          qualificationQuestions: s.qualification_questions || [],
          transferMessage: s.transfer_message || "Connecting you to an agent...",
          disqualificationMessage: s.disqualification_message || "Thank you, goodbye.",
          versionHistory: (s.versions || []).map((v) => ({
            version: `v${v.version}.0`,
            status: v.status,
            releaseDate: v.created_at ? String(v.created_at).slice(0, 10) : "Today",
            author: v.created_by || "Bilal Satti",
            approvedBy: v.approved_at ? "QA Director" : "Pending Approval",
            changes: v.change_note || "Version update",
          })),
          active_version_id: s.active_version_id,
        }));
        setScripts(mapped);
      }
    } catch (err) {
      console.error("Failed to fetch scripts from API:", err);
    }
  };

  React.useEffect(() => {
    fetchScripts();
  }, []);

  // Route state parsing
  const routeInfo = useMemo(() => {
    if (!initialAction || initialAction === "all" || initialAction === "list") {
      return { mode: "library", scriptId: null, version: null };
    }
    if (initialAction === "new") {
      return { mode: "new", scriptId: null, version: null };
    }
    if (initialAction === "approvals") {
      return { mode: "approvals", scriptId: null, version: null };
    }

    const parts = initialAction.split("/");
    const scriptId = parts[0];
    const subAction = parts[1] || "overview";

    if (subAction === "edit") {
      return { mode: "edit", scriptId, version: null };
    }
    if (subAction === "preview") {
      return { mode: "preview", scriptId, version: null };
    }
    if (subAction === "versions") {
      const ver = parts[2] || "v1.0";
      const isDiff = parts[3] === "diff";
      return { mode: isDiff ? "diff" : "version", scriptId, version: ver };
    }

    return { mode: "overview", scriptId, version: null };
  }, [initialAction]);

  const navigateToAction = (actionStr) => {
    if (onActionChange) {
      onActionChange(actionStr);
    }
  };

  // Find active script object
  const activeScript = useMemo(() => {
    if (!routeInfo.scriptId) return scripts[0];
    return (
      scripts.find(
        (s) =>
          s.id.toLowerCase() === routeInfo.scriptId.toLowerCase() ||
          s.name.toLowerCase() === routeInfo.scriptId.toLowerCase()
      ) || scripts[0]
    );
  }, [scripts, routeInfo.scriptId]);

  // Form state for /scripts/new
  const [newScriptName, setNewScriptName] = useState("");
  const [newCampaignName, setNewCampaignName] = useState("Med Fronter");
  const [newGreeting, setNewGreeting] = useState("");
  const [newConsent, setNewConsent] = useState("");
  const [newQuestionInput, setNewQuestionInput] = useState("");
  const [newQuestionsList, setNewQuestionsList] = useState([
    "Are you currently 65 years of age or older, or qualified due to disability?",
    "Do you currently have Medicare Part A and Part B active?",
  ]);
  const [newTransferMsg, setNewTransferMsg] = useState("");
  const [newDisqualifyMsg, setNewDisqualifyMsg] = useState("");

  // Form state for /scripts/[scriptId]/edit (Draft Editor)
  const [editGreeting, setEditGreeting] = useState(activeScript?.greeting || "");
  const [editConsent, setEditConsent] = useState(activeScript?.consent || "");
  const [editQuestions, setEditQuestions] = useState(
    activeScript?.qualificationQuestions || []
  );
  const [editTransferMsg, setEditTransferMsg] = useState(activeScript?.transferMessage || "");
  const [editDisqualifyMsg, setEditDisqualifyMsg] = useState(
    activeScript?.disqualificationMessage || ""
  );

  // Sync edit form when activeScript changes
  React.useEffect(() => {
    if (activeScript) {
      setEditGreeting(activeScript.greeting || "");
      setEditConsent(activeScript.consent || "");
      setEditQuestions(activeScript.qualificationQuestions || []);
      setEditTransferMsg(activeScript.transferMessage || "");
      setEditDisqualifyMsg(activeScript.disqualificationMessage || "");
    }
  }, [activeScript]);

  // Simulator step-through state for /scripts/[scriptId]/preview
  const [simStep, setSimStep] = useState(0);
  const [simLog, setSimLog] = useState([]);
  const [simCompleted, setSimCompleted] = useState(false);
  const [simOutcome, setSimOutcome] = useState(null);

  // Filtered Scripts
  const filteredScripts = useMemo(() => {
    return scripts.filter((s) => {
      if (statusFilter !== "all" && s.status !== statusFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          s.name.toLowerCase().includes(q) ||
          s.campaignName.toLowerCase().includes(q) ||
          s.version.toLowerCase().includes(q) ||
          s.author.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [scripts, searchQuery, statusFilter]);

  // Submit Handler for New Script (/scripts/new)
  const handleCreateScript = async (e) => {
    e.preventDefault();
    if (!newScriptName.trim()) return;

    const localId = `script-${Date.now().toString().slice(-4)}`;
    const createdLocal = {
      id: localId,
      name: newScriptName.trim(),
      version: "v1.0-draft",
      campaignId: "c-custom",
      campaignName: newCampaignName,
      status: "approved",
      approvedBy: "QA Director",
      author: "Bilal Satti",
      updatedAt: "Just now",
      qualificationRate: "70.0%",
      transferRate: "65.0%",
      dropOffRate: "10.0%",
      fallbackCount: 0,
      greeting:
        newGreeting ||
        "Hello, this is Alex from SmartBrains BPO regarding your Medicare options.",
      consent:
        newConsent ||
        "This call is recorded for quality and compliance under TCPA guidelines.",
      qualificationQuestions: newQuestionsList,
      transferMessage:
        newTransferMsg || "Thank you! Connecting you to a licensed Medicare verifier...",
      disqualificationMessage:
        newDisqualifyMsg || "Thank you for your time today. Goodbye.",
    };

    try {
      const payload = {
        name: newScriptName.trim(),
        description: `Created for ${newCampaignName}`,
        greeting: newGreeting || "Hello, thank you for taking our call.",
        consent: newConsent || "This call is recorded for quality and compliance purposes.",
        qualification_questions: newQuestionsList,
        transfer_message: newTransferMsg || "Thank you! Connecting you to a licensed verifier...",
        disqualification_message: newDisqualifyMsg || "Thank you for your time today. Goodbye.",
      };

      const res = await apiFetch("/scripts", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (res && res.ok) {
        const json = await res.json();
        const createdScript = json.data || json;
        const scriptId = createdScript.id;

        try {
          await apiFetch(`/scripts/${scriptId}/versions/1/submit`, { method: "POST" });
          await apiFetch(`/scripts/${scriptId}/versions/1/approve`, { method: "POST" });
        } catch (verErr) {
          console.warn("Version auto-approve skipped:", verErr);
        }

        await fetchScripts();
        navigateToAction(scriptId);
        return;
      }
    } catch (err) {
      console.warn("Backend API unavailable, saving script to local state:", err);
    }

    // Fallback: save to local state if backend call fails or server is offline
    setScripts((prev) => [createdLocal, ...prev]);
    navigateToAction(localId);
  };

  // Save Draft Edits (/scripts/[scriptId]/edit)
  const handleSaveDraftEdits = (e, submitForApproval = false) => {
    e.preventDefault();
    if (!activeScript) return;

    const updatedStatus = submitForApproval ? "pending_review" : "draft";

    setScripts((prev) =>
      prev.map((s) => {
        if (s.id === activeScript.id) {
          return {
            ...s,
            status: updatedStatus,
            greeting: editGreeting,
            consent: editConsent,
            qualificationQuestions: editQuestions,
            transferMessage: editTransferMsg,
            disqualificationMessage: editDisqualifyMsg,
            updatedAt: "Just now",
          };
        }
        return s;
      })
    );

    if (submitForApproval) {
      // Add item to approval queue
      const apprItem = {
        id: `appr-${Date.now()}`,
        scriptId: activeScript.id,
        scriptName: activeScript.name,
        version: `${activeScript.version}-rc`,
        campaignName: activeScript.campaignName,
        author: "Bilal Satti",
        submittedAt: "Just now",
        complianceScore: "98%",
        diffSummary: "Updated greeting and qualification wording",
        status: "pending_review",
      };
      setApprovalQueue((prev) => [apprItem, ...prev]);
      navigateToAction("approvals");
    } else {
      navigateToAction(activeScript.id);
    }
  };

  // Approval actions (/scripts/approvals)
  const handleApproveScript = (apprId, targetScriptId) => {
    setApprovalQueue((prev) => prev.filter((a) => a.id !== apprId));
    setScripts((prev) =>
      prev.map((s) => {
        if (s.id === targetScriptId) {
          return {
            ...s,
            status: "active",
            approvedBy: "QA Director",
            updatedAt: "Just now",
          };
        }
        return s;
      })
    );
  };

  const handleRejectScript = (apprId) => {
    setApprovalQueue((prev) => prev.filter((a) => a.id !== apprId));
  };

  // Simulator actions
  const startSimulator = () => {
    setSimStep(1);
    setSimCompleted(false);
    setSimOutcome(null);
    setSimLog([
      {
        speaker: "Bot (AI Assistant)",
        text: activeScript?.greeting || "Hello, this is Alex from SmartBrains BPO.",
      },
    ]);
  };

  const handleSimUserResponse = (choice) => {
    if (choice === "consent_yes") {
      setSimStep(2);
      setSimLog((prev) => [
        ...prev,
        { speaker: "Customer", text: "Yes, I agree and give consent." },
        {
          speaker: "Bot (AI Assistant)",
          text: activeScript?.consent || "Calls are recorded for compliance purposes.",
        },
        {
          speaker: "Bot (AI Assistant)",
          text:
            (activeScript?.qualificationQuestions &&
              activeScript.qualificationQuestions[0]) ||
            "Are you 65 years of age or older?",
        },
      ]);
    } else if (choice === "consent_no") {
      setSimCompleted(true);
      setSimOutcome("disqualified");
      setSimLog((prev) => [
        ...prev,
        { speaker: "Customer", text: "No, I do not consent." },
        {
          speaker: "Bot (AI Assistant)",
          text:
            activeScript?.disqualificationMessage ||
            "Thank you for your time today. Goodbye.",
        },
      ]);
    } else if (choice === "qual_yes") {
      setSimCompleted(true);
      setSimOutcome("qualified");
      setSimLog((prev) => [
        ...prev,
        { speaker: "Customer", text: "Yes, I am enrolled in Medicare A & B." },
        {
          speaker: "Bot (AI Assistant)",
          text:
            activeScript?.transferMessage ||
            "Great news! Connecting you to a licensed verifier now.",
        },
      ]);
    } else if (choice === "qual_no") {
      setSimCompleted(true);
      setSimOutcome("disqualified");
      setSimLog((prev) => [
        ...prev,
        { speaker: "Customer", text: "No, I do not have Medicare Part B." },
        {
          speaker: "Bot (AI Assistant)",
          text:
            activeScript?.disqualificationMessage ||
            "Thank you for your time today. Have a great day.",
        },
      ]);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-6 text-neutral-900 dark:text-neutral-100 font-sans min-h-screen bg-neutral-50 dark:bg-[#050505] transition-colors duration-200">
      {/* ========================================================================= */}
      {/* ROUTE 1: /scripts (Script Library View) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "library" && (
        <div className="flex flex-col gap-6">
          {/* Header Title & Actions */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-200 dark:border-neutral-800/80 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-neutral-900 dark:text-white tracking-tight">
                  Call Scripts Library
                </h1>
                <span className="rounded-full bg-blue-100 dark:bg-blue-600/20 border border-blue-300 dark:border-blue-500/40 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 dark:text-blue-400">
                  Version Controlled
                </span>
              </div>
              <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
                Manage, version, test, and activate AI conversational qualification scripts for campaigns.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => navigateToAction("approvals")}
                className="relative inline-flex items-center gap-1.5 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3.5 py-2 text-xs font-semibold text-neutral-800 dark:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800 shadow-xs"
              >
                <CheckSquare className="h-4 w-4 text-purple-500" />
                <span>Approval Queue</span>
                {approvalQueue.length > 0 && (
                  <span className="ml-1 rounded-full bg-purple-600 px-1.5 py-0.2 text-[10px] font-bold text-white">
                    {approvalQueue.length}
                  </span>
                )}
              </button>

              <button
                type="button"
                onClick={() => navigateToAction("new")}
                className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700 transition-colors"
              >
                <Plus className="h-4 w-4" />
                <span>Create Script</span>
              </button>
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
                placeholder="Search script title, campaign, version..."
                className="w-full rounded-lg border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] py-2 pl-9 pr-3 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex items-center rounded-lg border border-neutral-300 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-1 text-xs shadow-xs">
              {["all", "active", "draft"].map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setStatusFilter(st)}
                  className={`rounded-md px-3 py-1 font-semibold uppercase text-[11px] transition-colors ${
                    statusFilter === st
                      ? "bg-blue-600 text-white shadow-xs"
                      : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {/* Main Scripts List Table */}
          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] border-collapse text-xs text-left">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 font-semibold uppercase tracking-wider text-[11px]">
                    <th className="px-4 py-3">Script Name</th>
                    <th className="px-4 py-3">Bound Campaign</th>
                    <th className="px-4 py-3">Version</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Author</th>
                    <th className="px-4 py-3">Transfer Rate</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {filteredScripts.map((scr) => (
                    <tr
                      key={scr.id}
                      onClick={() => navigateToAction(scr.id)}
                      className="cursor-pointer transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-900/50"
                    >
                      <td className="px-4 py-4 font-bold text-blue-600 dark:text-blue-400 hover:underline">
                        {scr.name}
                      </td>
                      <td className="px-4 py-4 font-semibold text-neutral-800 dark:text-neutral-200">
                        {scr.campaignName}
                      </td>
                      <td className="px-4 py-4 font-mono">
                        <span className="rounded bg-neutral-100 dark:bg-neutral-800 px-2 py-0.5 text-xs font-bold border border-neutral-200 dark:border-neutral-700">
                          {scr.version}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        {scr.status === "active" && (
                          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/70 px-2.5 py-0.5 text-xs font-bold text-emerald-700 dark:text-emerald-400">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            ACTIVE IN DIALER
                          </span>
                        )}
                        {scr.status === "draft" && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-xs font-bold text-amber-700">
                            DRAFT
                          </span>
                        )}
                        {scr.status === "pending_review" && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-purple-300 bg-purple-50 px-2.5 py-0.5 text-xs font-bold text-purple-700">
                            PENDING QA
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-4 text-neutral-600 dark:text-neutral-400">
                        {scr.author}
                      </td>
                      <td className="px-4 py-4 font-bold text-emerald-600">
                        {scr.transferRate}
                      </td>
                      <td className="px-4 py-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigateToAction(`${scr.id}/preview`);
                            }}
                            className="inline-flex items-center gap-1 rounded-md border border-purple-200 bg-purple-50 px-2.5 py-1 text-xs font-bold text-purple-700 hover:bg-purple-100"
                          >
                            <Play className="h-3 w-3" />
                            <span>Simulate</span>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigateToAction(scr.id);
                            }}
                            className="inline-flex items-center gap-1 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-2.5 py-1 text-xs font-semibold hover:bg-neutral-100"
                          >
                            <span>Overview</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 2: /scripts/new (Create Script) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "new" && (
        <div className="flex flex-col gap-6 max-w-3xl">
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
                Create New Call Script
              </h2>
              <p className="text-xs text-neutral-500 dark:text-neutral-400">
                Design conversational prompts, TCPA consent disclaimers, and qualification rules.
              </p>
            </div>
          </div>

          <form
            onSubmit={handleCreateScript}
            className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-5 text-xs"
          >
            <div className="flex flex-col gap-1.5">
              <label className="font-bold text-neutral-800 dark:text-neutral-200">
                Script Name / Title
              </label>
              <input
                type="text"
                required
                value={newScriptName}
                onChange={(e) => setNewScriptName(e.target.value)}
                placeholder="e.g. Medicare Advantage 2026 Inbound Qualifier"
                className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-bold text-neutral-800 dark:text-neutral-200">
                Target Campaign Binding
              </label>
              <select
                value={newCampaignName}
                onChange={(e) => setNewCampaignName(e.target.value)}
                className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs outline-none"
              >
                <option value="Med Fronter">Med Fronter</option>
                <option value="Data Campaign">Data Campaign</option>
                <option value="Solar Outreach East">Solar Outreach East</option>
                <option value="Insurance Renewals">Insurance Renewals</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5 border-t border-neutral-200 dark:border-neutral-800 pt-4">
              <label className="font-bold text-neutral-800 dark:text-neutral-200">
                Voice Opening Greeting Prompt
              </label>
              <textarea
                rows={2}
                value={newGreeting}
                onChange={(e) => setNewGreeting(e.target.value)}
                placeholder="Hello, this is Alex calling on behalf of Medicare Assistance Services..."
                className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] p-3 text-xs outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-bold text-neutral-800 dark:text-neutral-200">
                Consent & TCPA Disclosure Statement
              </label>
              <textarea
                rows={2}
                value={newConsent}
                onChange={(e) => setNewConsent(e.target.value)}
                placeholder="This call is recorded for quality and compliance purposes under TCPA guidelines..."
                className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] p-3 text-xs outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex flex-col gap-2 border-t border-neutral-200 dark:border-neutral-800 pt-4">
              <label className="font-bold text-neutral-800 dark:text-neutral-200">
                Qualification Questions List
              </label>
              <div className="flex flex-col gap-2">
                {newQuestionsList.map((q, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800"
                  >
                    <span>
                      {idx + 1}. {q}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setNewQuestionsList(newQuestionsList.filter((_, i) => i !== idx))
                      }
                      className="text-rose-500 hover:text-rose-700"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}

                <div className="flex gap-2 mt-1">
                  <input
                    type="text"
                    value={newQuestionInput}
                    onChange={(e) => setNewQuestionInput(e.target.value)}
                    placeholder="Add new qualification question..."
                    className="flex-1 rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-1.5 text-xs outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (newQuestionInput.trim()) {
                        setNewQuestionsList([...newQuestionsList, newQuestionInput.trim()]);
                        setNewQuestionInput("");
                      }
                    }}
                    className="px-3 py-1.5 bg-blue-600 text-white rounded-md font-bold"
                  >
                    Add Question
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-4 border-t border-neutral-200 dark:border-neutral-800">
              <button
                type="button"
                onClick={() => navigateToAction(null)}
                className="px-4 py-2 font-semibold text-neutral-500 hover:text-neutral-900"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-md shadow-xs"
              >
                Save Script Draft
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 3: /scripts/[scriptId] (Script Overview & Version List) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "overview" && activeScript && (
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
                  <h1 className="text-2xl font-bold text-neutral-900 dark:text-white tracking-tight">
                    {activeScript.name}
                  </h1>
                  <span className="rounded-full bg-emerald-100 text-emerald-700 border border-emerald-300 px-2.5 py-0.5 text-[10px] font-bold">
                    {activeScript.status}
                  </span>
                </div>
                <p className="mt-1 text-xs text-neutral-500">
                  Domain: {activeScript.domain} | Active Version: {activeScript.version}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => navigateToAction(`${activeScript.id}/preview`)}
                className="inline-flex items-center gap-1.5 rounded-md border border-purple-300 bg-purple-50 px-3.5 py-1.5 text-xs font-bold text-purple-700 hover:bg-purple-100"
              >
                <Play className="h-3.5 w-3.5" />
                <span>Simulate Flow</span>
              </button>
              <button
                type="button"
                onClick={() => navigateToAction(`${activeScript.id}/edit`)}
                className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-blue-700"
              >
                <Edit3 className="h-3.5 w-3.5" />
                <span>Edit Script</span>
              </button>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs text-neutral-500">Qualification Rate</span>
              <p className="text-2xl font-extrabold text-blue-600">{activeScript.qualificationRate}</p>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs text-neutral-500">Transfer Rate</span>
              <p className="text-2xl font-extrabold text-emerald-600">{activeScript.transferRate}</p>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs text-neutral-500">Drop-off Rate</span>
              <p className="text-2xl font-extrabold text-amber-600">{activeScript.dropOffRate}</p>
            </div>
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-4 shadow-xs">
              <span className="text-xs text-neutral-500">Fallback Count</span>
              <p className="text-2xl font-extrabold text-neutral-800 dark:text-white">{activeScript.fallbackCount}</p>
            </div>
          </div>

          {/* Current Script Content Preview Card */}
          <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4 text-xs">
            <h3 className="text-sm font-bold border-b border-neutral-100 dark:border-neutral-800 pb-3">
              Active Script Prompts & Logic
            </h3>

            <div className="flex flex-col gap-3">
              <div className="bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
                <span className="font-bold text-blue-600">Opening Greeting:</span>
                <p className="mt-1 text-neutral-700 dark:text-neutral-300">{activeScript.greeting}</p>
              </div>
              <div className="bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
                <span className="font-bold text-blue-600">Consent Statement:</span>
                <p className="mt-1 text-neutral-700 dark:text-neutral-300">{activeScript.consent}</p>
              </div>
              <div className="bg-neutral-50 dark:bg-[#151518] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
                <span className="font-bold text-blue-600">Qualification Questions:</span>
                <ul className="mt-1 list-disc list-inside space-y-1 text-neutral-700 dark:text-neutral-300">
                  {(activeScript.qualificationQuestions || []).map((q, idx) => (
                    <li key={idx}>{q}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* Version History Table */}
          <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-4">
            <h3 className="text-sm font-bold">Script Version History</h3>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                    <th className="py-2.5 px-3">Version</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Release Date</th>
                    <th className="py-2.5 px-3">Author</th>
                    <th className="py-2.5 px-3">Changes Note</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {(activeScript.versionHistory || []).map((ver, idx) => (
                    <tr key={idx} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                      <td className="py-3 px-3 font-mono font-bold text-blue-600">{ver.version}</td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700">
                          {ver.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-neutral-500">{ver.releaseDate}</td>
                      <td className="py-3 px-3 font-semibold">{ver.author}</td>
                      <td className="py-3 px-3 text-neutral-600 dark:text-neutral-400">{ver.changes}</td>
                      <td className="py-3 px-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => navigateToAction(`${activeScript.id}/versions/${ver.version}`)}
                            className="px-2.5 py-1 rounded border border-neutral-300 dark:border-neutral-700 text-neutral-700 dark:text-neutral-200 font-semibold hover:bg-neutral-100"
                          >
                            Snapshot
                          </button>
                          <button
                            type="button"
                            onClick={() => navigateToAction(`${activeScript.id}/versions/${ver.version}/diff`)}
                            className="px-2.5 py-1 rounded border border-purple-200 bg-purple-50 text-purple-700 font-bold hover:bg-purple-100"
                          >
                            Diff
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 4: /scripts/[scriptId]/edit (Script Editor - Draft versions only) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "edit" && activeScript && (
        <div className="flex flex-col gap-6 max-w-3xl">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigateToAction(activeScript.id)}
              className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div>
              <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                Script Editor
              </h2>
              <span className="text-xs text-amber-600 font-bold bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                Draft Mode Enabled
              </span>
            </div>
          </div>

          <form className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-5 text-xs">
            <div className="flex flex-col gap-1.5">
              <label className="font-bold text-neutral-800 dark:text-neutral-200">
                Opening Greeting Prompt
              </label>
              <textarea
                rows={3}
                value={editGreeting}
                onChange={(e) => setEditGreeting(e.target.value)}
                className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] p-3 text-xs outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-bold text-neutral-800 dark:text-neutral-200">
                Consent & TCPA Disclaimer Wording
              </label>
              <textarea
                rows={3}
                value={editConsent}
                onChange={(e) => setEditConsent(e.target.value)}
                className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] p-3 text-xs outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-bold text-neutral-800 dark:text-neutral-200">
                Transfer Message
              </label>
              <textarea
                rows={2}
                value={editTransferMsg}
                onChange={(e) => setEditTransferMsg(e.target.value)}
                className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] p-3 text-xs outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-4 border-t border-neutral-200 dark:border-neutral-800">
              <button
                type="button"
                onClick={(e) => handleSaveDraftEdits(e, false)}
                className="px-4 py-2 font-bold text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100"
              >
                Save Draft
              </button>
              <button
                type="button"
                onClick={(e) => handleSaveDraftEdits(e, true)}
                className="px-5 py-2 font-bold text-white bg-purple-600 rounded-md hover:bg-purple-700 shadow-xs"
              >
                Submit for QA Approval
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 5: /scripts/[scriptId]/versions/[v] (Read-Only Version Snapshot) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "version" && activeScript && (
        <div className="flex flex-col gap-6 max-w-3xl">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigateToAction(activeScript.id)}
              className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div>
              <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                Read-Only Version Snapshot
              </h2>
              <span className="text-xs text-blue-600 font-bold bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                Snapshot: Version {routeInfo.version}
              </span>
            </div>
          </div>

          <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-4 text-xs">
            <div className="bg-neutral-50 dark:bg-[#151518] p-4 rounded-lg border border-neutral-200 dark:border-neutral-800">
              <span className="font-bold text-neutral-500">Frozen Opening Greeting:</span>
              <p className="mt-1 text-neutral-800 dark:text-neutral-200">
                {activeScript.snapshots?.[routeInfo.version]?.greeting || activeScript.greeting}
              </p>
            </div>

            <div className="bg-neutral-50 dark:bg-[#151518] p-4 rounded-lg border border-neutral-200 dark:border-neutral-800">
              <span className="font-bold text-neutral-500">Frozen Consent Disclaimer:</span>
              <p className="mt-1 text-neutral-800 dark:text-neutral-200">
                {activeScript.snapshots?.[routeInfo.version]?.consent || activeScript.consent}
              </p>
            </div>

            <div className="flex justify-end pt-3">
              <button
                type="button"
                onClick={() =>
                  navigateToAction(`${activeScript.id}/versions/${routeInfo.version}/diff`)
                }
                className="px-4 py-2 bg-purple-600 text-white font-bold rounded-md hover:bg-purple-700"
              >
                Compare Version Diff
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 6: /scripts/[scriptId]/versions/[v]/diff (Version Comparison) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "diff" && activeScript && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigateToAction(activeScript.id)}
              className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div>
              <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                Version Comparison Diff
              </h2>
              <p className="text-xs text-neutral-500">
                Comparing Base Version (v1.0) vs Target Version ({routeInfo.version})
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-3">
              <span className="font-bold text-neutral-500 uppercase">Base Version (v1.0)</span>
              <div className="bg-rose-50 dark:bg-rose-950/40 p-3 rounded-lg border border-rose-200 dark:border-rose-800 text-rose-900 dark:text-rose-200 font-mono">
                {activeScript.snapshots?.["v1.0"]?.greeting || "Original base greeting wording"}
              </div>
            </div>

            <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col gap-3">
              <span className="font-bold text-purple-600 uppercase">Target Version ({routeInfo.version})</span>
              <div className="bg-emerald-50 dark:bg-emerald-950/40 p-3 rounded-lg border border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200 font-mono">
                {activeScript.snapshots?.[routeInfo.version]?.greeting || activeScript.greeting}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 7: /scripts/[scriptId]/preview (Conversation Flow Simulator) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "preview" && activeScript && (
        <div className="flex flex-col gap-6 max-w-3xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigateToAction(activeScript.id)}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 hover:text-neutral-900"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
                  Conversation Flow Simulator
                </h2>
                <span className="text-xs text-purple-600 font-bold bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
                  Testing: {activeScript.name} ({activeScript.version})
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={startSimulator}
              className="inline-flex items-center gap-1 rounded-md bg-purple-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-purple-700"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Reset Simulator</span>
            </button>
          </div>

          <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-4 text-xs min-h-[360px]">
            {simStep === 0 && (
              <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
                <Bot className="h-10 w-10 text-purple-500" />
                <h3 className="text-base font-bold">Interactive Script Simulator</h3>
                <p className="text-neutral-500 max-w-md">
                  Click start to simulate a live AI voice bot call flow step-by-step.
                </p>
                <button
                  type="button"
                  onClick={startSimulator}
                  className="mt-2 px-5 py-2 bg-purple-600 text-white font-bold rounded-lg shadow-md hover:bg-purple-700"
                >
                  Start Call Simulation
                </button>
              </div>
            )}

            {simStep > 0 && (
              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-3 max-h-80 overflow-y-auto bg-neutral-50 dark:bg-[#151518] p-4 rounded-xl border border-neutral-200 dark:border-neutral-800">
                  {simLog.map((log, idx) => (
                    <div
                      key={idx}
                      className={`flex flex-col gap-1 p-3 rounded-lg ${
                        log.speaker.startsWith("Bot")
                          ? "bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800/60"
                          : "bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/60"
                      }`}
                    >
                      <span className="font-bold text-[11px] uppercase tracking-wider text-purple-700 dark:text-purple-300">
                        {log.speaker}
                      </span>
                      <p className="text-xs text-neutral-800 dark:text-neutral-200">{log.text}</p>
                    </div>
                  ))}
                </div>

                {!simCompleted && simStep === 1 && (
                  <div className="flex flex-col gap-2 pt-2 border-t border-neutral-200 dark:border-neutral-800">
                    <span className="font-bold text-neutral-500">Customer Choice Simulation:</span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => handleSimUserResponse("consent_yes")}
                        className="px-4 py-2 bg-emerald-600 text-white font-bold rounded-md hover:bg-emerald-700"
                      >
                        "Yes, I give consent to proceed"
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSimUserResponse("consent_no")}
                        className="px-4 py-2 bg-rose-600 text-white font-bold rounded-md hover:bg-rose-700"
                      >
                        "No, do not record me"
                      </button>
                    </div>
                  </div>
                )}

                {!simCompleted && simStep === 2 && (
                  <div className="flex flex-col gap-2 pt-2 border-t border-neutral-200 dark:border-neutral-800">
                    <span className="font-bold text-neutral-500">Customer Choice Simulation:</span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => handleSimUserResponse("qual_yes")}
                        className="px-4 py-2 bg-emerald-600 text-white font-bold rounded-md hover:bg-emerald-700"
                      >
                        "Yes, I am over 65 & have Medicare A & B"
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSimUserResponse("qual_no")}
                        className="px-4 py-2 bg-rose-600 text-white font-bold rounded-md hover:bg-rose-700"
                      >
                        "No, I don't have Medicare Part B"
                      </button>
                    </div>
                  </div>
                )}

                {simCompleted && (
                  <div className="flex flex-col items-center justify-center p-4 rounded-xl border border-emerald-300 bg-emerald-50 text-emerald-800 font-bold text-center gap-2">
                    <CheckCircle2 className="h-6 w-6 text-emerald-600" />
                    <span>
                      Simulation Outcome: {simOutcome === "qualified" ? "QUALIFIED & TRANSFERRED TO LICENSED VERIFIER" : "DISQUALIFIED / HANGUP ACTION"}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 8: /scripts/approvals (Approval Queue) */}
      {/* ========================================================================= */}
      {routeInfo.mode === "approvals" && (
        <div className="flex flex-col gap-6">
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
                Script Approval Queue
              </h2>
              <p className="text-xs text-neutral-500">
                Review and approve draft script versions submitted by QA or Campaign Managers.
              </p>
            </div>
          </div>

          <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs">
            {approvalQueue.length === 0 ? (
              <div className="p-8 text-center text-xs font-semibold text-neutral-500">
                No pending script approval requests in queue.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px]">
                      <th className="py-2.5 px-3">Script Name</th>
                      <th className="py-2.5 px-3">Target Version</th>
                      <th className="py-2.5 px-3">Campaign</th>
                      <th className="py-2.5 px-3">Author</th>
                      <th className="py-2.5 px-3">Submitted At</th>
                      <th className="py-2.5 px-3">Compliance Score</th>
                      <th className="py-2.5 px-3">Diff Summary</th>
                      <th className="py-2.5 px-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                    {approvalQueue.map((appr) => (
                      <tr key={appr.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                        <td className="py-3 px-3 font-bold text-neutral-900 dark:text-white">{appr.scriptName}</td>
                        <td className="py-3 px-3 font-mono font-bold text-blue-600">{appr.version}</td>
                        <td className="py-3 px-3 text-neutral-700">{appr.campaignName}</td>
                        <td className="py-3 px-3 font-semibold">{appr.author}</td>
                        <td className="py-3 px-3 text-neutral-500">{appr.submittedAt}</td>
                        <td className="py-3 px-3 font-bold text-emerald-600">{appr.complianceScore}</td>
                        <td className="py-3 px-3 text-neutral-600">{appr.diffSummary}</td>
                        <td className="py-3 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleApproveScript(appr.id, appr.scriptId)}
                              className="px-3 py-1 bg-emerald-600 text-white font-bold rounded-md hover:bg-emerald-700"
                            >
                              Approve & Activate
                            </button>
                            <button
                              type="button"
                              onClick={() => handleRejectScript(appr.id)}
                              className="px-3 py-1 bg-rose-100 text-rose-700 font-bold rounded-md hover:bg-rose-200"
                            >
                              Reject
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
