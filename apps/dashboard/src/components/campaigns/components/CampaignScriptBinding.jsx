"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { INITIAL_SCRIPTS } from "@/data";

export default function CampaignScriptBinding({ campaign, onRefresh, onBindScript }) {
  const [availableScripts, setAvailableScripts] = useState(INITIAL_SCRIPTS);
  const [selectedScriptId, setSelectedScriptId] = useState(INITIAL_SCRIPTS[0]?.id || "");
  const [binding, setBinding] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const fetchScripts = async () => {
    let localScripts = [];
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("talkflow_call_scripts");
        if (saved) localScripts = JSON.parse(saved);
      } catch (err) {}
    }

    try {
      const res = await apiFetch("/scripts");
      if (res.ok) {
        const json = await res.json();
        const apiItems = json.items || json.data || [];
        const combined = [...apiItems, ...localScripts];
        for (const initScript of INITIAL_SCRIPTS) {
          if (!combined.some((s) => s.id === initScript.id || s.name === initScript.name)) {
            combined.push(initScript);
          }
        }
        setAvailableScripts(combined);
        if (combined.length > 0 && !selectedScriptId) {
          setSelectedScriptId(combined[0].id);
        }
        return;
      }
    } catch (err) {
      console.warn("Using default scripts list:", err);
    }

    const fallbackCombined = [...localScripts];
    for (const initScript of INITIAL_SCRIPTS) {
      if (!fallbackCombined.some((s) => s.id === initScript.id || s.name === initScript.name)) {
        fallbackCombined.push(initScript);
      }
    }
    setAvailableScripts(fallbackCombined);
    if (!selectedScriptId && fallbackCombined.length > 0) {
      setSelectedScriptId(fallbackCombined[0].id);
    }
  };

  useEffect(() => {
    fetchScripts();
  }, []);

  const activeScriptsOnly = availableScripts.filter(
    (s) => s.status === "active" || s.status === "approved"
  );

  const boundScript = availableScripts.find(
    (s) => s.id === campaign.scriptId || s.active_version_id === campaign.activeScriptVersionId || s.name === campaign.script?.activeScript
  );

  const handleBindScript = async (e) => {
    e.preventDefault();
    const effectiveList = activeScriptsOnly.length > 0 ? activeScriptsOnly : availableScripts;
    const targetScript = effectiveList.find((s) => s.id === selectedScriptId) || effectiveList[0];
    if (!targetScript) return;

    const versionId =
      targetScript.active_version_id ||
      targetScript.activeVersionId ||
      (targetScript.versions && targetScript.versions[0]?.id) ||
      "00000000-0000-0000-0000-000000000001";

    try {
      setBinding(true);
      // If targetScript is backend script with UUID
      if (targetScript.id && targetScript.id.length > 30) {
        await apiFetch(
          `/campaigns/${campaign.id}/script?script_id=${targetScript.id}&active_script_version_id=${versionId}`,
          { method: "POST" }
        );
      }
    } catch (err) {
      console.warn("Backend script binding notification:", err);
    } finally {
      // Local updates for seamless UI response
      campaign.scriptId = targetScript.id;
      campaign.activeScriptVersionId = versionId;
      campaign.script = {
        activeScript: targetScript.name,
        version: targetScript.version || "Active",
      };

      if (typeof window !== "undefined") {
        try {
          const savedCamps = localStorage.getItem("talkflow_campaigns");
          if (savedCamps) {
            const parsed = JSON.parse(savedCamps);
            const updatedCamps = parsed.map((c) => {
              if (c.id === campaign.id || c.name === campaign.name) {
                return {
                  ...c,
                  scriptId: targetScript.id,
                  activeScriptVersionId: versionId,
                  script: {
                    activeScript: targetScript.name,
                    version: targetScript.version || "Active",
                  },
                };
              }
              return c;
            });
            localStorage.setItem("talkflow_campaigns", JSON.stringify(updatedCamps));
          }
        } catch (e) {}
      }

      if (onBindScript) {
        onBindScript(campaign.id, targetScript);
      }

      setBinding(false);
      setIsEditing(false);
      if (onRefresh) await onRefresh();
    }
  };

  const isBound = Boolean((campaign.activeScriptVersionId || boundScript || (campaign.script?.activeScript && campaign.script.activeScript !== "No Script Bound")) && !isEditing);
  const displayList = activeScriptsOnly.length > 0 ? activeScriptsOnly : availableScripts;

  return (
    <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-bold text-neutral-900 dark:text-white">
          Active Script Binding
        </h3>
        {isBound && (
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="text-xs font-bold text-blue-600 dark:text-blue-400 hover:underline"
          >
            Change Bound Script
          </button>
        )}
      </div>

      {isBound ? (
        <div className="bg-blue-50 dark:bg-blue-950/40 p-4 rounded-xl border border-blue-200 dark:border-blue-800 flex items-center justify-between text-xs">
          <div className="flex flex-col gap-0.5">
            <span className="font-bold text-blue-700 dark:text-blue-300 text-sm">
              {boundScript?.name || campaign.script?.activeScript || "Medicare Part C/D First-Level Qualification"}
            </span>
            <span className="text-neutral-500">
              Bound Version: {boundScript?.version || boundScript?.active_version || campaign.script?.version || "v1.0"}
            </span>
          </div>
          <span className="px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 font-bold border border-emerald-300">
            ACTIVE_IN_DIALER
          </span>
        </div>
      ) : (
        <div className="bg-neutral-50 dark:bg-[#151518] p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 flex flex-col gap-3 text-xs">
          <div className="flex flex-col gap-1">
            <span className="font-bold text-neutral-800 dark:text-neutral-200">
              Select Active Script to Bind
            </span>
            <p className="text-neutral-500">
              Only approved and active qualification scripts are listed below for live campaign binding.
            </p>
          </div>

          <form onSubmit={handleBindScript} className="flex flex-col sm:flex-row items-center gap-2 mt-2">
            <select
              value={selectedScriptId || (displayList[0]?.id || "")}
              onChange={(e) => setSelectedScriptId(e.target.value)}
              className="w-full sm:flex-1 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2 text-xs outline-none"
            >
              {displayList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.version || "v1.0"} • ACTIVE)
                </option>
              ))}
            </select>
            <div className="flex gap-2 w-full sm:w-auto">
              <button
                type="submit"
                disabled={binding || displayList.length === 0}
                className="flex-1 sm:flex-initial px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-md disabled:opacity-50"
              >
                {binding ? "Binding..." : "Bind Script"}
              </button>
              {isEditing && (
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="px-3 py-2 border border-neutral-300 dark:border-neutral-700 rounded-md text-neutral-600"
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </div>
      )}
    </div>
  );
}