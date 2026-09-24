import { useState, useMemo, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import {
  CAMPAIGN_TEAM_ASSIGNMENTS,
  CAMPAIGN_ACTIVE_SCRIPTS,
  CAMPAIGN_LIVE_OUTCOMES,
} from "@/data";

export function useCampaignState(initialAction, onActionChange) {
  const getStoredCampaigns = () => {
    if (typeof window === "undefined") return [];
    try {
      const saved = localStorage.getItem("talkflow_campaigns");
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return [];
  };

  const saveStoredCampaigns = (camps) => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem("talkflow_campaigns", JSON.stringify(camps));
    } catch (e) {}
  };

  const getStoredTeamAssignments = () => {
    if (typeof window === "undefined") return null;
    try {
      const saved = localStorage.getItem("talkflow_team_assignments");
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return null;
  };

  const saveStoredTeamAssignments = (teams) => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem("talkflow_team_assignments", JSON.stringify(teams));
    } catch (e) {}
  };

  const [campaigns, setCampaigns] = useState(() => getStoredCampaigns());
  const [loading, setLoading] = useState(false);
  const [teamAssignments, setTeamAssignments] = useState(() => getStoredTeamAssignments() || CAMPAIGN_TEAM_ASSIGNMENTS);
  const [activeScripts, setActiveScripts] = useState(CAMPAIGN_ACTIVE_SCRIPTS);
  const [liveOutcomes, setLiveOutcomes] = useState(CAMPAIGN_LIVE_OUTCOMES);

  const fetchCampaigns = async () => {
    const localCamps = getStoredCampaigns();
    try {
      setLoading(true);
      const res = await apiFetch("/campaigns");
      if (res.ok) {
        const json = await res.json();
        const items = json.data || [];
        const mapped = items.map((c) => ({
          id: String(c.id),
          name: c.name,
          status: c.status || "draft",
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
          userGroups: c.userGroups || c.user_groups || c.closerInGroup || "Sales_Agents",
          dialing: c.dialing || {},
          routing: { inboundQueue: "Default_Q", fallbackIvr: "Default_IVR" },
          scriptId: c.scriptId || c.script_id || "s-medicare-01",
          activeScriptVersionId: c.activeScriptVersionId || c.active_script_version_id || "v1.0",
          script: {
            activeScript: (c.script?.activeScript && c.script.activeScript !== "No Script Bound")
              ? c.script.activeScript
              : "Medicare Outbound Verification Script",
            version: (c.script?.version && c.script.version !== "None")
              ? c.script.version
              : "v1.0",
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

        const map = {};
        mapped.forEach((b) => { map[b.id] = b; });
        localCamps.forEach((l) => {
          if (!map[l.id]) {
            map[l.id] = l;
          }
        });

        const merged = Object.values(map);
        setCampaigns(merged);
        saveStoredCampaigns(merged);
        return;
      }
    } catch {
      // Best-effort load
    } finally {
      setLoading(false);
    }

    if (localCamps.length > 0) {
      setCampaigns(localCamps);
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

    const newCampObj = {
      id: `camp-${Date.now().toString().slice(-4)}`,
      name: newCampName.trim(),
      status: "draft",
      dialMode: newDialMode,
      dialLevel: String(newDialLevel),
      amd: newAmd,
      amdSub: newAmd === "Enabled" ? newAmdSub : null,
      trunks: {
        manual: newManualTrunk,
        auto: newAutoTrunk,
        threeWay: newThreeWayTrunk,
      },
      recording: "On bridge",
      userGroups: newUserGroups || "Sales_Agents",
      dialing: {
        dialMode: newDialMode,
        dialLevel: String(newDialLevel),
        amd: newAmd,
      },
      routing: { inboundQueue: "Default_Q", fallbackIvr: "Default_IVR" },
      scriptId: null,
      activeScriptVersionId: null,
      script: {
        activeScript: "Medicare Outbound Verification Script",
        version: "v1.0",
      },
      transfer: { verifierPool: "Unassigned" },
      performance: {
        callsDialed: "0",
        answered: "0",
        contactRate: "0.0%",
        conversions: "0",
        conversionRate: "0.0%",
        avgDuration: "0m 00s",
        dropRate: "0.0%",
      },
    };

    setCampaigns((prev) => {
      const updated = [newCampObj, ...prev];
      saveStoredCampaigns(updated);
      return updated;
    });

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

      if (res && res.ok) {
        const json = await res.json();
        const created = json.data;
        if (created?.id) {
          await fetchCampaigns();
          setNewCampName("");
          setIsModalOpen(false);
          navigateToAction(String(created.id));
          return;
        }
      }
    } catch (err) {
      console.warn("Backend API unavailable, saving campaign locally:", err);
    }

    setNewCampName("");
    setIsModalOpen(false);
    navigateToAction(newCampObj.id);
  };

  const handleSaveTeamAssignments = (updatedTeams) => {
    setTeamAssignments(updatedTeams);
    saveStoredTeamAssignments(updatedTeams);
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

  const handleToggleCampaignStatus = async (targetId) => {
    let nextStatus = "active";
    setCampaigns((prev) => {
      const updated = prev.map((c) => {
        if (c.id === targetId || c.name === targetId) {
          nextStatus = c.status === "active" ? "paused" : "active";
          return { ...c, status: nextStatus };
        }
        return c;
      });
      saveStoredCampaigns(updated);
      return updated;
    });

    try {
      await apiFetch(`/campaigns/${targetId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus }),
      });
    } catch (err) {
      console.warn("Failed to update status on API:", err);
    }
  };

  const handleDeleteCampaign = async (targetId) => {
    if (typeof window !== "undefined" && !window.confirm("Are you sure you want to delete this campaign?")) {
      return;
    }
    setCampaigns((prev) => {
      const updated = prev.filter((c) => c.id !== targetId && c.name !== targetId);
      saveStoredCampaigns(updated);
      return updated;
    });

    try {
      await apiFetch(`/campaigns/${targetId}`, { method: "DELETE" });
    } catch (err) {
      console.warn("Failed to delete campaign on API:", err);
    }
  };

  const handleBindScriptToCampaign = (targetCampId, targetScript) => {
    setCampaigns((prev) => {
      const updated = prev.map((c) => {
        if (c.id === targetCampId || c.name === targetCampId) {
          return {
            ...c,
            scriptId: targetScript.id,
            activeScriptVersionId: targetScript.active_version_id || targetScript.id,
            script: {
              activeScript: targetScript.name,
              version: targetScript.version || "v1.0",
            },
          };
        }
        return c;
      });
      saveStoredCampaigns(updated);
      return updated;
    });
  };

  const handleUpdateCampaignTransferRules = async (targetId, transferData) => {
    setCampaigns((prev) => {
      const updated = prev.map((c) => {
        if (c.id === targetId || c.name === targetId) {
          return {
            ...c,
            transfer: {
              ...c.transfer,
              ...transferData,
            },
          };
        }
        return c;
      });
      saveStoredCampaigns(updated);
      return updated;
    });

    try {
      await apiFetch(`/campaigns/${targetId}`, {
        method: "PATCH",
        body: JSON.stringify({
          transfer: transferData,
        }),
      });
    } catch (err) {
      console.warn("Backend API unavailable for campaign transfer rules update:", err);
    }
  };

  const handleUpdateCampaignRouting = async (targetId, routingData) => {
    setCampaigns((prev) => {
      const updated = prev.map((c) => {
        if (c.id === targetId || c.name === targetId) {
          return {
            ...c,
            routing: {
              ...c.routing,
              didMappings: routingData,
            },
          };
        }
        return c;
      });
      saveStoredCampaigns(updated);
      return updated;
    });

    try {
      await apiFetch(`/campaigns/${targetId}`, {
        method: "PATCH",
        body: JSON.stringify({
          routing: { didMappings: routingData },
        }),
      });
    } catch (err) {
      console.warn("Backend API unavailable for campaign routing update:", err);
    }
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
    handleSaveTeamAssignments,
    handleToggleCampaignStatus,
    handleDeleteCampaign,
    handleBindScriptToCampaign,
    handleUpdateCampaignTransferRules,
    handleUpdateCampaignRouting,
    navigateToAction,
    fetchCampaigns,
  };
}