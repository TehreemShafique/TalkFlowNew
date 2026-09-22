"use client";

import React from "react";
import { useCampaignState } from "./hooks/useCampaignState";
import CampaignHeader from "./components/CampaignHeader";
import CampaignListTable from "./components/CampaignListTable";
import CampaignMetricsGrid from "./components/CampaignMetricsGrid";
import TeamAssignmentPanel from "./components/TeamAssignmentPanel";
import ActiveScriptsPanel from "./components/ActiveScriptsPanel";
import LiveOutcomesPanel from "./components/LiveOutcomesPanel";
import CampaignFormModal from "./components/CampaignFormModal";
import CampaignDetailHeader from "./components/CampaignDetailHeader";
import CampaignOverviewPanels from "./components/CampaignOverviewPanels";
import CampaignDialingForm from "./components/CampaignDialingForm";
import CampaignRoutingForm from "./components/CampaignRoutingForm";
import CampaignScriptBinding from "./components/CampaignScriptBinding";
import CampaignTransferRules from "./components/CampaignTransferRules";
import CampaignPerformancePanel from "./components/CampaignPerformancePanel";

export default function CampaignsView({ initialAction, onActionChange }) {
  const state = useCampaignState(initialAction, onActionChange);

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-6 text-neutral-900 dark:text-neutral-100 font-sans min-h-screen bg-neutral-50 dark:bg-[#050505] transition-colors duration-200">
      <CampaignHeader
        totalCount={state.totalCount}
        activeCount={state.activeCount}
        pausedCount={state.pausedCount}
        currentMode={state.currentMode}
        activeSubtab={state.activeSubtab}
        onNavigate={state.navigateToAction}
      />

      {/* SUBTAB 1: ALL CAMPAIGNS MAIN TABLE */}
      {state.currentMode === "subtab" && state.activeSubtab === "all" && (
        <CampaignListTable
          searchQuery={state.searchQuery}
          onSearchChange={state.setSearchQuery}
          statusFilter={state.statusFilter}
          onStatusFilterChange={state.setStatusFilter}
          filteredCampaigns={state.filteredCampaigns}
          totalCampaigns={state.campaigns.length}
          onSort={state.handleSort}
          onOpenCampaign={state.navigateToAction}
        />
      )}

      {/* SUBTAB 2: PERFORMANCE REVIEW VIEW (/campaigns/performance) */}
      {state.currentMode === "subtab" && state.activeSubtab === "performance" && (
        <CampaignMetricsGrid />
      )}

      {/* SUBTAB 3: ASSIGN TEAM VIEW (/campaigns/team) */}
      {state.currentMode === "subtab" && state.activeSubtab === "team" && (
        <TeamAssignmentPanel
          teamAssignments={state.teamAssignments}
          selectedTeamCampaign={state.selectedTeamCampaign}
          newAgentName={state.newAgentName}
          onOpenAssign={state.setSelectedTeamCampaign}
          onCloseAssign={() => state.setSelectedTeamCampaign(null)}
          onNewAgentNameChange={state.setNewAgentName}
          onSubmitAssign={state.handleAddAgentToTeam}
        />
      )}

      {/* SUBTAB 4: ACTIVE SCRIPTS VIEW (/campaigns/scripts) */}
      {state.currentMode === "subtab" && state.activeSubtab === "scripts" && (
        <ActiveScriptsPanel activeScripts={state.activeScripts} />
      )}

      {/* SUBTAB 5: LIVE OUTCOMES VIEW (/campaigns/outcomes) */}
      {state.currentMode === "subtab" && state.activeSubtab === "outcomes" && (
        <LiveOutcomesPanel liveOutcomes={state.liveOutcomes} />
      )}

      {/* ROUTE 2: CREATE CAMPAIGN PAGE (/campaigns/new) */}
      {state.currentMode === "new" && (
        <CampaignFormModal
          newCampName={state.newCampName}
          onNewCampNameChange={state.setNewCampName}
          newDialMode={state.newDialMode}
          onNewDialModeChange={state.setNewDialMode}
          newDialLevel={state.newDialLevel}
          onNewDialLevelChange={state.setNewDialLevel}
          newAmd={state.newAmd}
          onNewAmdChange={state.setNewAmd}
          newAmdSub={state.newAmdSub}
          onNewAmdSubChange={state.setNewAmdSub}
          newManualTrunk={state.newManualTrunk}
          onNewManualTrunkChange={state.setNewManualTrunk}
          newAutoTrunk={state.newAutoTrunk}
          onNewAutoTrunkChange={state.setNewAutoTrunk}
          newThreeWayTrunk={state.newThreeWayTrunk}
          onNewThreeWayTrunkChange={state.setNewThreeWayTrunk}
          onCancel={() => state.navigateToAction(null)}
          onSubmit={state.handleCreateCampaignSubmit}
        />
      )}

      {/* ROUTE 3: CAMPAIGN OVERVIEW & CARDS FOR REMAINING URLS (/campaigns/[campaignId]) */}
      {state.currentMode === "detail" && state.selectedCampaign && (
        <div className="flex flex-col gap-6">
          <CampaignDetailHeader
            campaign={state.selectedCampaign}
            subRoute={state.subRoute}
            onBack={() => state.navigateToAction(null)}
            onNavigate={state.navigateToAction}
          />
          {(state.subRoute === "overview" || !state.subRoute) && (
            <CampaignOverviewPanels campaign={state.selectedCampaign} />
          )}
          {state.subRoute === "dialing" && (
            <CampaignDialingForm campaign={state.selectedCampaign} />
          )}
          {state.subRoute === "routing" && (
            <CampaignRoutingForm campaign={state.selectedCampaign} />
          )}
          {state.subRoute === "script" && (
            <CampaignScriptBinding campaign={state.selectedCampaign} onRefresh={state.fetchCampaigns} />
          )}
          {state.subRoute === "transfer" && (
            <CampaignTransferRules campaign={state.selectedCampaign} />
          )}
          {state.subRoute === "performance" && (
            <CampaignPerformancePanel campaign={state.selectedCampaign} />
          )}
        </div>
      )}
    </div>
  );
}