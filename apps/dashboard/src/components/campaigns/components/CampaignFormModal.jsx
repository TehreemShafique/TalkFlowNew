"use client";

import { ArrowLeft } from "lucide-react";

export default function CampaignFormModal({
  newCampName,
  onNewCampNameChange,
  newDialMode,
  onNewDialModeChange,
  newDialLevel,
  onNewDialLevelChange,
  newAmd,
  onNewAmdChange,
  newAmdSub,
  onNewAmdSubChange,
  newManualTrunk,
  onNewManualTrunkChange,
  newAutoTrunk,
  onNewAutoTrunkChange,
  newThreeWayTrunk,
  onNewThreeWayTrunkChange,
  onCancel,
  onSubmit,
}) {
  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h2 className="text-xl font-bold text-neutral-900 dark:text-white">
            Create New Campaign
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            Configure auto-dialer mode, trunks, AMD detection, and user allocations
          </p>
        </div>
      </div>

      <form
        onSubmit={onSubmit}
        className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-5 text-xs"
      >
        <div className="flex flex-col gap-1.5">
          <label className="font-bold text-neutral-800 dark:text-neutral-200">
            Campaign Name
          </label>
          <input
            type="text"
            required
            value={newCampName}
            onChange={(e) => onNewCampNameChange(e.target.value)}
            placeholder="e.g. Healthcare Outreach Campaign"
            className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-600"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="font-bold text-neutral-800 dark:text-neutral-200">
              Dial Mode
            </label>
            <select
              value={newDialMode}
              onChange={(e) => onNewDialModeChange(e.target.value)}
              className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-600"
            >
              <option value="ratio">Ratio Dialing</option>
              <option value="predictive">Predictive Dialing</option>
              <option value="manual">Manual Dialing</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="font-bold text-neutral-800 dark:text-neutral-200">
              Dial Level (Pacing Multiplier)
            </label>
            <input
              type="text"
              value={newDialLevel}
              onChange={(e) => onNewDialLevelChange(e.target.value)}
              className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-2 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-600"
            />
          </div>
        </div>



        <div className="flex flex-col gap-2 border-t border-neutral-200 dark:border-neutral-800 pt-4">
          <label className="font-bold text-neutral-800 dark:text-neutral-200">
            SIP Trunk Configuration
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input
              type="text"
              value={newManualTrunk}
              onChange={(e) => onNewManualTrunkChange(e.target.value)}
              placeholder="Manual Trunk"
              className="rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-1.5 text-xs text-neutral-900 dark:text-white outline-none"
            />
            <input
              type="text"
              value={newAutoTrunk}
              onChange={(e) => onNewAutoTrunkChange(e.target.value)}
              placeholder="Auto Trunk"
              className="rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-1.5 text-xs text-neutral-900 dark:text-white outline-none"
            />
            <input
              type="text"
              value={newThreeWayTrunk}
              onChange={(e) => onNewThreeWayTrunkChange(e.target.value)}
              placeholder="3-Way Trunk"
              className="rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#151518] px-3 py-1.5 text-xs text-neutral-900 dark:text-white outline-none"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-4 border-t border-neutral-200 dark:border-neutral-800">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-xs font-semibold text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="px-5 py-2 text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-md shadow-xs"
          >
            Save Campaign
          </button>
        </div>
      </form>
    </div>
  );
}