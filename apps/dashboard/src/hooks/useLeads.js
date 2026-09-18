"use client";

import { useState, useMemo, useCallback } from "react";
import { INITIAL_LEADS } from "@/data";

// Generic lead-record data service hook.
// Decouples static lead dataset from feature UI state, plus bulk state management.
export function useLeads(statusFilter = "all", searchQuery = "") {
  const [leads, setLeads] = useState(INITIAL_LEADS);

  const filteredLeads = useMemo(() => {
    return leads.filter((lead) => {
      if (statusFilter !== "all" && lead.status.toLowerCase() !== statusFilter.toLowerCase()) {
        return false;
      }

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const fullName = `${lead.firstName} ${lead.lastName}`.toLowerCase();
        const matchName = fullName.includes(q);
        const matchPhone = lead.phone.toLowerCase().includes(q);
        const matchEmail = lead.email.toLowerCase().includes(q);
        const matchCamp = lead.campaign.toLowerCase().includes(q);
        const matchId = lead.id.toLowerCase().includes(q);

        return matchName || matchPhone || matchEmail || matchCamp || matchId;
      }

      return true;
    });
  }, [leads, statusFilter, searchQuery]);

  const addLead = useCallback((newLead) => {
    setLeads((prev) => [newLead, ...prev]);
  }, []);

  const updateLead = useCallback((id, updates) => {
    setLeads((prev) => prev.map((l) => (l.id === id ? { ...l, ...updates } : l)));
  }, []);

  const removeLead = useCallback((id) => {
    setLeads((prev) => prev.filter((l) => l.id !== id));
  }, []);

  return {
    leads: filteredLeads,
    allLeads: leads,
    setLeads,
    addLead,
    updateLead,
    removeLead,
  };
}