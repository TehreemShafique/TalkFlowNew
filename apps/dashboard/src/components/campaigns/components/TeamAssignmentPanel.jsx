"use client";

import { useState } from "react";
import { Users, User, UserPlus, X, Edit2 } from "lucide-react";

export default function TeamAssignmentPanel({
  campaigns = [],
  teamAssignments = [],
  onUpdateTeam,
}) {
  const [editingTeam, setEditingTeam] = useState(null);
  const [editManager, setEditManager] = useState("");
  const [editShift, setEditShift] = useState("");
  const [assigningTeam, setAssigningTeam] = useState(null);
  const [newAgentName, setNewAgentName] = useState("");
  const [newAgentRole, setNewAgentRole] = useState("Licensed QA Agent");

  // Filter ONLY active campaigns
  const activeCampaigns = campaigns.filter((c) => c.status === "active");

  // Match team assignments for active campaigns
  const activeTeamItems = activeCampaigns.map((camp) => {
    const existing = teamAssignments.find(
      (t) =>
        String(t.campaignId || "").toLowerCase() === String(camp.id).toLowerCase() ||
        String(t.campaignName || "").toLowerCase() === String(camp.name).toLowerCase()
    );

    if (existing) {
      return { ...existing, campaignName: camp.name, status: "Active" };
    }

    return {
      id: `team-${camp.id}`,
      campaignId: camp.id,
      campaignName: camp.name,
      manager: "Ahmad Raza (QA Lead)",
      shift: "Morning (09:00 - 17:00 EST)",
      status: "Active",
      agentsCount: 2,
      agentsList: [
        { name: "John Doe", role: "Licensed Agent", status: "Available" },
        { name: "Sarah Smith", role: "Licensed Agent", status: "In Call" },
      ],
    };
  });

  const handleStartEdit = (team) => {
    setEditingTeam(team);
    setEditManager(team.manager || "");
    setEditShift(team.shift || "Morning (09:00 - 17:00 EST)");
  };

  const handleSaveTeamEdit = (e) => {
    e.preventDefault();
    if (!editingTeam) return;

    const updated = activeTeamItems.map((t) => {
      if (t.id === editingTeam.id) {
        return {
          ...t,
          manager: editManager.trim() || t.manager,
          shift: editShift.trim() || t.shift,
        };
      }
      return t;
    });

    if (onUpdateTeam) {
      onUpdateTeam(updated);
    }
    setEditingTeam(null);
  };

  const handleAddAgent = (e) => {
    e.preventDefault();
    if (!assigningTeam || !newAgentName.trim()) return;

    const updated = activeTeamItems.map((t) => {
      if (t.id === assigningTeam.id) {
        const newList = [
          ...t.agentsList,
          { name: newAgentName.trim(), role: newAgentRole, status: "Available" },
        ];
        return {
          ...t,
          agentsCount: newList.length,
          agentsList: newList,
        };
      }
      return t;
    });

    if (onUpdateTeam) {
      onUpdateTeam(updated);
    }
    setNewAgentName("");
    setAssigningTeam(null);
  };

  const handleRemoveAgent = (teamId, agentIndex) => {
    const updated = activeTeamItems.map((t) => {
      if (t.id === teamId) {
        const newList = t.agentsList.filter((_, idx) => idx !== agentIndex);
        return {
          ...t,
          agentsCount: newList.length,
          agentsList: newList,
        };
      }
      return t;
    });

    if (onUpdateTeam) {
      onUpdateTeam(updated);
    }
  };

  return (
    <>
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3">
          <div>
            <h3 className="text-base font-bold text-neutral-900 dark:text-white">
              Active Campaigns Team Roster
            </h3>
            <p className="text-xs text-neutral-500">
              Manage licensed agents, managers, and shift hours for active dialer campaigns
            </p>
          </div>
          <span className="text-xs font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/80 px-2.5 py-1 rounded-md border border-emerald-200 dark:border-emerald-800">
            {activeTeamItems.length} Active Campaign Teams
          </span>
        </div>

        {activeTeamItems.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {activeTeamItems.map((team) => (
              <div
                key={team.id}
                className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-5 shadow-xs flex flex-col justify-between gap-4"
              >
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800/60 text-blue-600">
                        <Users className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-neutral-900 dark:text-white">
                          {team.campaignName}
                        </h4>
                        <span className="text-xs text-neutral-500">{team.shift}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700 border border-emerald-200">
                        Active
                      </span>
                      <button
                        type="button"
                        onClick={() => handleStartEdit(team)}
                        className="p-1 text-neutral-400 hover:text-neutral-700 dark:hover:text-white"
                        title="Edit Team Details"
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-neutral-500 font-medium">Team Manager</span>
                      <p className="font-bold text-neutral-800 dark:text-neutral-200 mt-0.5">
                        {team.manager}
                      </p>
                    </div>
                    <div>
                      <span className="text-neutral-500 font-medium">Assigned Agents</span>
                      <p className="font-bold text-blue-600 mt-0.5">
                        {team.agentsList.length} Active Agents
                      </p>
                    </div>
                  </div>

                  {/* Agents List Tag Box */}
                  <div className="flex flex-wrap gap-2 mt-2 bg-neutral-50 dark:bg-[#121215] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800">
                    {team.agentsList.length > 0 ? (
                      team.agentsList.map((ag, idx) => (
                        <div
                          key={idx}
                          className="flex items-center gap-1.5 rounded-md border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-[#1a1a1e] px-2.5 py-1 text-xs"
                        >
                          <User className="h-3 w-3 text-neutral-400" />
                          <span className="font-semibold">{ag.name}</span>
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              ag.status === "In Call" ? "bg-emerald-500" : "bg-blue-500"
                            }`}
                          />
                          <button
                            type="button"
                            onClick={() => handleRemoveAgent(team.id, idx)}
                            className="ml-1 text-neutral-400 hover:text-rose-600"
                            title="Remove agent"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      ))
                    ) : (
                      <span className="text-xs text-neutral-500 italic py-1">
                        No agents assigned yet. Click "Assign Agent" below.
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex justify-between items-center pt-2 border-t border-neutral-100 dark:border-neutral-800">
                  <button
                    type="button"
                    onClick={() => handleStartEdit(team)}
                    className="text-xs font-bold text-neutral-600 dark:text-neutral-400 hover:text-neutral-900"
                  >
                    Edit Shift / Manager
                  </button>

                  <button
                    type="button"
                    onClick={() => setAssigningTeam(team)}
                    className="inline-flex items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-600 hover:bg-blue-100"
                  >
                    <UserPlus className="h-3.5 w-3.5" />
                    <span>+ Assign Agent</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center text-xs text-neutral-500 italic bg-white dark:bg-[#0d0d0d] rounded-xl border border-neutral-200 dark:border-neutral-800">
            No active campaigns found. Activate a campaign in the list view to assign team rosters.
          </div>
        )}
      </div>

      {/* MODAL 1: Edit Team Manager & Shift */}
      {editingTeam && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#121214] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3 mb-4">
              <h3 className="text-base font-bold">Edit Team — {editingTeam.campaignName}</h3>
              <button onClick={() => setEditingTeam(null)} className="text-neutral-400 hover:text-white">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleSaveTeamEdit} className="flex flex-col gap-4">
              <div>
                <label className="block text-xs font-bold mb-1">Team Manager Name</label>
                <input
                  type="text"
                  required
                  value={editManager}
                  onChange={(e) => setEditManager(e.target.value)}
                  placeholder="e.g. Ahmad Raza (QA Lead)"
                  className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-2 text-xs outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold mb-1">Shift Hours</label>
                <select
                  value={editShift}
                  onChange={(e) => setEditShift(e.target.value)}
                  className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-2 text-xs outline-none"
                >
                  <option value="Morning (09:00 - 17:00 EST)">Morning (09:00 - 17:00 EST)</option>
                  <option value="Full Day (08:00 - 20:00 EST)">Full Day (08:00 - 20:00 EST)</option>
                  <option value="Mid Shift (12:00 - 20:00 EST)">Mid Shift (12:00 - 20:00 EST)</option>
                  <option value="Night Shift (20:00 - 04:00 EST)">Night Shift (20:00 - 04:00 EST)</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-neutral-200 dark:border-neutral-800">
                <button
                  type="button"
                  onClick={() => setEditingTeam(null)}
                  className="px-3 py-1.5 text-xs text-neutral-500"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-bold bg-blue-600 text-white rounded-md"
                >
                  Save Team Details
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Add Agent to Team */}
      {assigningTeam && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#121214] p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3 mb-4">
              <h3 className="text-base font-bold">Assign Agent to {assigningTeam.campaignName}</h3>
              <button onClick={() => setAssigningTeam(null)} className="text-neutral-400 hover:text-white">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleAddAgent} className="flex flex-col gap-4">
              <div>
                <label className="block text-xs font-bold mb-1">Agent Full Name</label>
                <input
                  type="text"
                  required
                  value={newAgentName}
                  onChange={(e) => setNewAgentName(e.target.value)}
                  placeholder="e.g. Alex Johnson"
                  className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-2 text-xs outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold mb-1">Agent Role</label>
                <select
                  value={newAgentRole}
                  onChange={(e) => setNewAgentRole(e.target.value)}
                  className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-2 text-xs outline-none"
                >
                  <option value="Licensed QA Agent">Licensed QA Agent</option>
                  <option value="Senior Closer">Senior Closer</option>
                  <option value="Verification Specialist">Verification Specialist</option>
                  <option value="Fronter Agent">Fronter Agent</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-neutral-200 dark:border-neutral-800">
                <button
                  type="button"
                  onClick={() => setAssigningTeam(null)}
                  className="px-3 py-1.5 text-xs text-neutral-500"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-bold bg-blue-600 text-white rounded-md"
                >
                  Add Agent
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}