"use client";

import { useState } from "react";

export default function CampaignTransferRules({ campaign, onUpdateTransferRules }) {
  const getInitialPools = () => {
    if (Array.isArray(campaign?.transfer?.pools) && campaign.transfer.pools.length > 0) {
      return campaign.transfer.pools;
    }
    return [
      {
        id: "pool-1",
        verifierPool: campaign?.transfer?.verifierPool || "Licensed QA Verifier Pool",
        transferRules: campaign?.transfer?.transferRules || "Warm Transfer (3-Way Bridge)",
        ringTimeout: campaign?.transfer?.ringTimeout || "30s",
        fallbackAction: campaign?.transfer?.fallbackAction || "Queue Callback",
      },
    ];
  };

  const [pools, setPools] = useState(getInitialPools);
  const [verifierPool, setVerifierPool] = useState("Licensed QA Verifier Pool");
  const [transferMode, setTransferMode] = useState("Warm Transfer (3-Way Bridge)");
  const [ringTimeout, setRingTimeout] = useState("30s");
  const [fallbackAction, setFallbackAction] = useState("Queue Callback");
  const [savedMessage, setSavedMessage] = useState(false);

  const handleAddTransferPool = (e) => {
    e.preventDefault();
    const newPool = {
      id: `pool-${Date.now()}`,
      verifierPool,
      transferRules: transferMode,
      ringTimeout,
      fallbackAction,
    };

    const updatedPools = [...pools, newPool];
    setPools(updatedPools);

    const config = {
      pools: updatedPools,
      verifierPool: updatedPools[0]?.verifierPool || verifierPool,
      transferRules: updatedPools[0]?.transferRules || transferMode,
      ringTimeout: updatedPools[0]?.ringTimeout || ringTimeout,
      fallbackAction: updatedPools[0]?.fallbackAction || fallbackAction,
    };

    if (onUpdateTransferRules) {
      onUpdateTransferRules(campaign.id, config);
    }

    setSavedMessage("Transfer Pool Added & Synced!");
    setTimeout(() => setSavedMessage(false), 2500);
  };

  const handleRemovePool = (poolId) => {
    const updatedPools = pools.filter((p) => p.id !== poolId);
    setPools(updatedPools);

    const config = {
      pools: updatedPools,
      verifierPool: updatedPools[0]?.verifierPool || "None",
      transferRules: updatedPools[0]?.transferRules || "Cold Transfer (Blind)",
      ringTimeout: updatedPools[0]?.ringTimeout || "30s",
      fallbackAction: updatedPools[0]?.fallbackAction || "Queue Callback",
    };

    if (onUpdateTransferRules) {
      onUpdateTransferRules(campaign.id, config);
    }
  };

  return (
    <div className="w-full flex flex-col gap-6">
      {/* FORM: Add New Transfer Pool */}
      <form
        onSubmit={handleAddTransferPool}
        className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-6"
      >
        <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-4">
          <div>
            <h3 className="text-base font-bold text-neutral-900 dark:text-white">
              Add Transfer Pool Rule
            </h3>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              Configure and append verifier pools, execution modes, ring timeouts, and fallback policies
            </p>
          </div>
          {savedMessage && (
            <span className="text-xs font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/80 px-3 py-1 rounded-md border border-emerald-300">
              {savedMessage}
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 text-xs">
          <div className="flex flex-col gap-1.5 bg-neutral-50 dark:bg-[#151518] p-4 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <label className="font-bold text-neutral-800 dark:text-neutral-200">
              Target Verifier Pool
            </label>
            <select
              value={verifierPool}
              onChange={(e) => setVerifierPool(e.target.value)}
              className="w-full rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2 text-xs outline-none"
            >
              <option value="Licensed QA Verifier Pool">Licensed QA Verifier Pool</option>
              <option value="Senior Licensed Closers">Senior Licensed Closers</option>
              <option value="Medicare Specialists Group A">Medicare Specialists Group A</option>
              <option value="Overflow Queue">Overflow Queue</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5 bg-neutral-50 dark:bg-[#151518] p-4 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <label className="font-bold text-neutral-800 dark:text-neutral-200">
              Transfer Execution Mode
            </label>
            <select
              value={transferMode}
              onChange={(e) => setTransferMode(e.target.value)}
              className="w-full rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2 text-xs outline-none"
            >
              <option value="Warm Transfer (3-Way Bridge)">Warm Transfer (3-Way Bridge)</option>
              <option value="Cold Transfer (Blind)">Cold Transfer (Blind)</option>
              <option value="Attended Transfer">Attended Transfer</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5 bg-neutral-50 dark:bg-[#151518] p-4 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <label className="font-bold text-neutral-800 dark:text-neutral-200">
              Ring Timeout (Seconds)
            </label>
            <select
              value={ringTimeout}
              onChange={(e) => setRingTimeout(e.target.value)}
              className="w-full rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2 text-xs outline-none"
            >
              <option value="15s">15 Seconds</option>
              <option value="30s">30 Seconds (Recommended)</option>
              <option value="45s">45 Seconds</option>
              <option value="60s">60 Seconds</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5 bg-neutral-50 dark:bg-[#151518] p-4 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <label className="font-bold text-neutral-800 dark:text-neutral-200">
              Timeout Fallback Action
            </label>
            <select
              value={fallbackAction}
              onChange={(e) => setFallbackAction(e.target.value)}
              className="w-full rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-3 py-2 text-xs outline-none"
            >
              <option value="Queue Callback">Queue Automatic Callback</option>
              <option value="Play Voicemail Drop">Play Voicemail Drop</option>
              <option value="Hangup Call">Hangup Call</option>
            </select>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-md text-xs shadow-xs flex items-center gap-1.5"
          >
            <span>+</span> Add Transfer Pool
          </button>
        </div>
      </form>

      {/* LIST: Configured Transfer Pools */}
      <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-4">
        <h4 className="text-sm font-bold text-neutral-900 dark:text-white border-b border-neutral-100 dark:border-neutral-800 pb-3 flex justify-between items-center">
          <span>Active Configured Transfer Pools ({pools.length})</span>
          <span className="text-xs text-neutral-500 font-normal">Syncs live to Overview tab</span>
        </h4>

        {pools.length > 0 ? (
          <div className="flex flex-col gap-3">
            {pools.map((p, idx) => (
              <div
                key={p.id || idx}
                className="flex items-center justify-between p-4 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] text-xs"
              >
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-neutral-900 dark:text-white text-sm">
                      {p.verifierPool}
                    </span>
                    <span className="px-2 py-0.5 bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300 font-semibold rounded text-[10px]">
                      Pool #{idx + 1}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-neutral-500 text-[11px]">
                    <span>Mode: <strong className="text-neutral-700 dark:text-neutral-300">{p.transferRules}</strong></span>
                    <span>•</span>
                    <span>Timeout: <strong className="text-neutral-700 dark:text-neutral-300">{p.ringTimeout}</strong></span>
                    <span>•</span>
                    <span>Fallback: <strong className="text-neutral-700 dark:text-neutral-300">{p.fallbackAction}</strong></span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleRemovePool(p.id)}
                  className="px-3 py-1.5 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/60 dark:hover:bg-rose-900 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-800 font-semibold rounded-md text-xs"
                >
                  Remove Pool
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-neutral-500 italic py-2">
            No transfer pools configured yet. Select options above and click "+ Add Transfer Pool".
          </p>
        )}
      </div>
    </div>
  );
}