"use client";

import { useState } from "react";

const DEFAULT_MAPPINGS = [
  { id: 1, did: "+1 (800) 555-0199", queue: "Medicare_Outbound_Q", fallback: "IVR_Main_Menu" },
  { id: 2, did: "+1 (888) 321-4321", queue: "Verifier_Transfer_Q", fallback: "Voicemail_Drop" },
];

export default function CampaignRoutingForm({ campaign, onUpdateRoutingRules }) {
  const [didMappings, setDidMappings] = useState(() => {
    return campaign.routing?.didMappings?.length > 0
      ? campaign.routing.didMappings
      : DEFAULT_MAPPINGS;
  });

  const [newDid, setNewDid] = useState("");
  const [newQueue, setNewQueue] = useState("Medicare_Outbound_Q");
  const [newFallback, setNewFallback] = useState("IVR_Main_Menu");
  const [savedMessage, setSavedMessage] = useState(false);

  const handleAddMapping = (e) => {
    e.preventDefault();
    if (!newDid.trim()) return;

    const newItem = {
      id: Date.now(),
      did: newDid.trim(),
      queue: newQueue,
      fallback: newFallback,
    };

    const updated = [...didMappings, newItem];
    setDidMappings(updated);
    if (!campaign.routing) campaign.routing = {};
    campaign.routing.didMappings = updated;

    if (onUpdateRoutingRules) {
      onUpdateRoutingRules(campaign.id, updated);
    }

    setNewDid("");
  };

  const handleRemoveMapping = (id) => {
    const updated = didMappings.filter((m) => m.id !== id);
    setDidMappings(updated);
    if (!campaign.routing) campaign.routing = {};
    campaign.routing.didMappings = updated;

    if (onUpdateRoutingRules) {
      onUpdateRoutingRules(campaign.id, updated);
    }
  };

  const handleSaveRouting = () => {
    if (!campaign.routing) campaign.routing = {};
    campaign.routing.didMappings = didMappings;

    if (onUpdateRoutingRules) {
      onUpdateRoutingRules(campaign.id, didMappings);
    }

    setSavedMessage(true);
    setTimeout(() => setSavedMessage(false), 2500);
  };

  return (
    <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-neutral-900 dark:text-white">
            Inbound & DID Routing Settings
          </h3>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            Map incoming DIDs and SIP trunks to target call queues and IVR fallbacks
          </p>
        </div>
        {savedMessage && (
          <span className="text-xs font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/80 px-3 py-1 rounded-md border border-emerald-300">
            Routing Saved!
          </span>
        )}
      </div>

      {/* DID List Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left border-collapse">
          <thead>
            <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-500 uppercase text-[11px] font-semibold">
              <th className="py-2.5 px-3">Mapped DID</th>
              <th className="py-2.5 px-3">Target Inbound Queue</th>
              <th className="py-2.5 px-3">Fallback Action</th>
              <th className="py-2.5 px-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
            {didMappings.map((map) => (
              <tr key={map.id}>
                <td className="py-3 px-3 font-mono font-bold text-blue-600 dark:text-blue-400">
                  {map.did}
                </td>
                <td className="py-3 px-3 font-bold text-neutral-800 dark:text-neutral-200">
                  {map.queue}
                </td>
                <td className="py-3 px-3 text-neutral-500">{map.fallback}</td>
                <td className="py-3 px-3 text-right">
                  <button
                    type="button"
                    onClick={() => handleRemoveMapping(map.id)}
                    className="text-xs text-red-600 dark:text-red-400 hover:underline font-semibold"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add New DID Route Form */}
      <form onSubmit={handleAddMapping} className="flex flex-col sm:flex-row items-end gap-3 pt-4 border-t border-neutral-200 dark:border-neutral-800">
        <div className="flex flex-col gap-1 flex-1">
          <label className="text-[11px] font-bold text-neutral-700 dark:text-neutral-300">
            New Phone DID / Number
          </label>
          <input
            type="text"
            required
            value={newDid}
            onChange={(e) => setNewDid(e.target.value)}
            placeholder="e.g. +1 (800) 555-0199"
            className="rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-1.5 text-xs outline-none"
          />
        </div>

        <div className="flex flex-col gap-1 flex-1">
          <label className="text-[11px] font-bold text-neutral-700 dark:text-neutral-300">
            Target Inbound Queue
          </label>
          <select
            value={newQueue}
            onChange={(e) => setNewQueue(e.target.value)}
            className="rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-1.5 text-xs outline-none"
          >
            <option value="Medicare_Outbound_Q">Medicare_Outbound_Q</option>
            <option value="Verifier_Transfer_Q">Verifier_Transfer_Q</option>
            <option value="Spanish_Language_Q">Spanish_Language_Q</option>
          </select>
        </div>

        <div className="flex flex-col gap-1 flex-1">
          <label className="text-[11px] font-bold text-neutral-700 dark:text-neutral-300">
            Fallback Action
          </label>
          <select
            value={newFallback}
            onChange={(e) => setNewFallback(e.target.value)}
            className="rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-1.5 text-xs outline-none"
          >
            <option value="IVR_Main_Menu">IVR_Main_Menu</option>
            <option value="Voicemail_Drop">Voicemail_Drop</option>
            <option value="Hangup_Call">Hangup_Call</option>
          </select>
        </div>

        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-md text-xs"
        >
          Add Route
        </button>
      </form>

      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={handleSaveRouting}
          className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-md text-xs shadow-xs"
        >
          Save Routing Settings
        </button>
      </div>
    </div>
  );
}