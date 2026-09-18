"use client";

import { useState, useMemo, useCallback } from "react";
import { INITIAL_CAMPAIGNS } from "@/data";

// Generic campaign data service hook.
// Decouples the static mock campaign dataset from feature UI state.
export function useCampaigns(statusFilter = "all", searchQuery = "") {
  const [campaigns, setCampaigns] = useState(INITIAL_CAMPAIGNS);

  const filteredCampaigns = useMemo(() => {
    return campaigns.filter((c) => {
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (searchQuery && !c.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });
  }, [campaigns, statusFilter, searchQuery]);

  const addCampaign = useCallback((newCamp) => {
    setCampaigns((prev) => [newCamp, ...prev]);
  }, []);

  const updateCampaign = useCallback((id, updates) => {
    setCampaigns((prev) => prev.map((c) => (c.id === id ? { ...c, ...updates } : c)));
  }, []);

  const removeCampaign = useCallback((id) => {
    setCampaigns((prev) => prev.filter((c) => c.id !== id));
  }, []);

  return {
    campaigns: filteredCampaigns,
    allCampaigns: campaigns,
    setCampaigns,
    addCampaign,
    updateCampaign,
    removeCampaign,
  };
}