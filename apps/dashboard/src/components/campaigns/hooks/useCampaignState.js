import { useState, useMemo, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import {
  CAMPAIGN_TEAM_ASSIGNMENTS,
  CAMPAIGN_ACTIVE_SCRIPTS,
  CAMPAIGN_LIVE_OUTCOMES,
} from "@/data";

export function useCampaignState(initialAction, onActionChange) {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [teamAssignments, setTeamAssignments] = useState(CAMPAIGN_TEAM_ASSIGNMENTS);
  const [activeScripts, setActiveScripts] = useState(CAMPAIGN_ACTIVE_SCRIPTS);
  const [liveOutcomes, setLiveOutcomes] = useState(CAMPAIGN_LIVE_OUTCOMES);

  const fetchCampaigns = async () => {
    try {
      setLoading(true);
      const res = await apiFetch("/campaigns");
      if (res.ok) {
        const json = await res.json();
        const items = json.data || [];
        // Map backend DTO to frontend campaign model
        const mapped = items.map((c) => ({
          id: c.id,
          name: c.name,
          status: c.status,
          dialMode: c.dialing?.dialMode || c.dialing?.dial_mode || "ratio",
          dialLevel: String(c.dialing?.dialLevel || c.dialing?.dial_level || "1.5"),
          amd: c.dialing?.amd || "Disabled",
          amdSub: c.dialing?.amdSub || null,
          trunks: {
            manual: c.dialing?.trunks?.manual || "trunk_vici_01",
            auto: c.dialing?.trunks?.auto || "trunk_vici_01",
            threeWay: c.dialing?.trunks?.threeWay || "trunk_vici_01",
          },
          recording: "On bridge",
          userGroups: c.closerInGroup || "—",
          dialing: c.dialing || {},
          routing: { inboundQueue: "Default_Q", fallbackIvr: "Default_IVR" },
          scriptId: c.scriptId || c.script_id || null,
          activeScriptVersionId: c.activeScriptVersionId || c.active_script_version_id || null,
          script: {
            activeScript: (c.activeScriptVersionId || c.active_script_version_id) ? "Bound Active Script" : "No Script Bound",
            version: (c.activeScriptVersionId || c.active_script_version_id) ? "Active" : "None",
          },
          transfer: { verifierPool: c.closerInGroup || "Unassigned" },
          performance: {
            callsDialed: "0",
            answered: "0",
            contactRate: "0.0%",
            conversions: "0",
            conversionRate: "0.0%",
            avgDuration: "0m 00s",
            dropRate: "0.0%",
          },
        }));
        setCampaigns(mapped);
      }
    } catch {
      // Best-effort load
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortField, setSortField] = useState(null);
  const [sortAsc, setSortAsc] = useState(true);

  // Modals state
  const [isModalOpen, setIsModalOpen] = useState(initialAction === "new");
  const [selectedTeamCampaign, setSelectedTeamCampaign] = useState(null);
  const [newAgentName, setNewAgentName] = useState("");

  // Parse route segments
  const { currentMode, activeSubtab, activeCampId, subRoute } = useMemo(() => {
    if (!initialAction || initialAction === "all" || initialAction === "list") {
      return { currentMode: "subtab", activeSubtab: "all", activeCampId: null, subRoute: null };
    }
    if (initialAction === "performance" || initialAction === "team" || initialAction === "scripts" || initialAction === "outcomes") {
      return { currentMode: "subtab", activeSubtab: initialAction, activeCampId: null, subRoute: null };
    }
    if (initialAction === "new") {
      return { currentMode: "new", activeSubtab: "all", activeCampId: null, subRoute: null };
    }

    const parts = initialAction.split("/");
    const campId = parts[0];
    const sub = parts[1] || "overview";

    return { currentMode: "detail", activeSubtab: "all", activeCampId: campId, subRoute: sub };
  }, [initialAction]);

  const navigateToAction = (actionStr) => {
    if (onActionChange) {
      onActionChange(actionStr);
    }
  };

  // Find selected campaign for detail view
  const selectedCampaign = useMemo(() => {
    if (!activeCampId) return campaigns[0];
    return (
      campaigns.find(
        (c) =>
          c.id.toLowerCase() === activeCampId.toLowerCase() ||
          c.name.toLowerCase() === activeCampId.toLowerCase()
      ) || campaigns[0]
    );
  }, [campaigns, activeCampId]);

  // Form state for /campaigns/new
  const [newCampName, setNewCampName] = useState("");
  const [newDialMode, setNewDialMode] = useState("ratio");
  const [newDialLevel, setNewDialLevel] = useState("2.5");
  const [newAmd, setNewAmd] = useState("Enabled");
  const [newAmdSub, setNewAmdSub] = useState("Hangup");
  const [newManualTrunk, setNewManualTrunk] = useState("trunk_vici_01");
  const [newAutoTrunk, setNewAutoTrunk] = useState("trunk_vici_01");
  const [newThreeWayTrunk, setNewThreeWayTrunk] = useState("trunk_vici_01");
  const [newUserGroups, setNewUserGroups] = useState("Sales_Agents");

  // Summary metrics for list view
  const totalCount = campaigns.length;
  const activeCount = campaigns.filter((c) => c.status === "active").length;
  const pausedCount = campaigns.filter((c) => c.status === "paused").length;

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const filteredCampaigns = useMemo(() => {
    return campaigns
      .filter((camp) => {
        if (statusFilter === "active" && camp.status !== "active") return false;
        if (
          statusFilter === "inactive" &&
          camp.status !== "draft" &&
          camp.status !== "paused"
        )
          return false;

        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchName = camp.name.toLowerCase().includes(q);
          const matchMode = camp.dialMode.toLowerCase().includes(q);
          const matchStatus = camp.status.toLowerCase().includes(q);
          const matchTrunk =
            camp.trunks.manual.toLowerCase().includes(q) ||
            camp.trunks.auto.toLowerCase().includes(q);
          return matchName || matchMode || matchStatus || matchTrunk;
        }

        return true;
      })
      .sort((a, b) => {
        if (!sortField) return 0;
        let valA = a[sortField] || "";
        let valB = b[sortField] || "";
        if (typeof valA === "string") valA = valA.toLowerCase();
        if (typeof valB === "string") valB = valB.toLowerCase();

        if (valA < valB) return sortAsc ? -1 : 1;
        if (valA > valB) return sortAsc ? 1 : -1;
        return 0;
      });
  }, [campaigns, searchQuery, statusFilter, sortField, sortAsc]);

  const handleCreateCampaignSubmit = async (e) => {
    e.preventDefault();
    if (!newCampName.trim()) return;

    try {
      const res = await apiFetch("/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name: newCampName.trim(),
          dialing: {
            dialMode: newDialMode,
            dialLevel: newDialLevel,
            amd: newAmd,
            amdSub: newAmd === "Enabled" ? newAmdSub : null,
            trunks: {
              manual: newManualTrunk,
              auto: newAutoTrunk,
              threeWay: newThreeWayTrunk,
            },
          },
        }),
      });

      if (res.ok) {
        const json = await res.json();
        const created = json.data;
        await fetchCampaigns();
        setNewCampName("");
        setIsModalOpen(false);
        navigateToAction(created?.id || null);
      }
    } catch (err) {
      console.error("Failed to create campaign:", err);
    }
  };

  const handleAddAgentToTeam = (e) => {
    e.preventDefault();
    if (!selectedTeamCampaign || !newAgentName.trim()) return;

    setTeamAssignments((prev) =>
      prev.map((item) => {
        if (item.id === selectedTeamCampaign.id) {
          return {
            ...item,
            agentsCount: item.agentsCount + 1,
            agentsList: [
              ...item.agentsList,
              { name: newAgentName.trim(), role: "Licensed Agent", status: "Available" },
            ],
          };
        }
        return item;
      })
    );
    setNewAgentName("");
    setSelectedTeamCampaign(null);
  };

  return {
    campaigns,
    teamAssignments,
    activeScripts,
    liveOutcomes,
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    isModalOpen,
    setIsModalOpen,
    selectedTeamCampaign,
    setSelectedTeamCampaign,
    newAgentName,
    setNewAgentName,
    currentMode,
    activeSubtab,
    subRoute,
    selectedCampaign,
    totalCount,
    activeCount,
    pausedCount,
    filteredCampaigns,
    newCampName,
    setNewCampName,
    newDialMode,
    setNewDialMode,
    newDialLevel,
    setNewDialLevel,
    newAmd,
    setNewAmd,
    newAmdSub,
    setNewAmdSub,
    newManualTrunk,
    setNewManualTrunk,
    newAutoTrunk,
    setNewAutoTrunk,
    newThreeWayTrunk,
    setNewThreeWayTrunk,
    handleCreateCampaignSubmit,
    handleAddAgentToTeam,
    navigateToAction,
    fetchCampaigns,
  };
}