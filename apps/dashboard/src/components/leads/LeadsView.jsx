"use client";

import React from "react";
import { ArrowLeft } from "lucide-react";
import { useLeadsState } from "./hooks/useLeadsState";
import LeadsHeader from "./components/LeadsHeader";
import LeadsSubtabsBar from "./components/LeadsSubtabsBar";
import LeadBatchesRegistryTable from "./components/LeadBatchesRegistryTable";
import LeadListTable from "./components/LeadListTable";
import LeadImportWizard from "./components/LeadImportWizard";
import LeadDetailView from "./components/LeadDetailView";
import SuppressionListView from "./components/SuppressionListView";
import LeadModals from "./components/LeadModals";

export default function LeadsView({ initialAction, onActionChange }) {
  const state = useLeadsState(initialAction, onActionChange);

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-6 text-neutral-900 dark:text-neutral-100 font-sans min-h-screen bg-neutral-50 dark:bg-[#050505] transition-colors duration-200">
      {/* 1. Header Title & Actions */}
      <LeadsHeader
        totalCount={state.totalCount}
        qualifiedCount={state.qualifiedCount}
        convertedCount={state.convertedCount}
        contactedCount={state.contactedCount}
        onImportClick={state.handleResetImportWizard}
        onAddClick={() => state.setIsAddModalOpen(true)}
      />

      {/* 2. Top Segmented Subtabs Bar */}
      <LeadsSubtabsBar
        viewMode={state.viewMode}
        onNavigate={(tab) => {
          if (tab === "import") {
            state.handleResetImportWizard();
          } else {
            state.navigateToAction(tab);
          }
        }}
      />

      {/* ========================================================================= */}
      {/* ROUTE 1: LEAD LIST FILE BATCHES REGISTRY (/leads or /leads/all) */}
      {/* ========================================================================= */}
      {state.viewMode === "all" && (
        <LeadBatchesRegistryTable
          batches={state.batches}
          activeCampaigns={state.activeCampaigns}
          onSelectBatch={state.handleSelectBatch}
          onAssignCampaign={state.handleAssignCampaign}
          onDeleteBatch={state.handleDeleteBatch}
          onToggleVicidialRun={state.handleToggleVicidialRun}
          vicidialBusyBatchId={state.vicidialBusyBatchId}
          vicidialError={state.vicidialError}
          batchError={state.batchError}
        />
      )}

      {/* ========================================================================= */}
      {/* ROUTE 2: LEAD LIST RECORDS WITH DYNAMIC COLUMNS (/leads/list) */}
      {/* ========================================================================= */}
      {state.viewMode === "list" && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between bg-white dark:bg-[#0d0d0d] p-3.5 rounded-xl border border-neutral-200 dark:border-neutral-800 shadow-xs">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={state.handleClearSelectedBatch}
                className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-900 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h4 className="text-xs font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                  <span>List Records:</span>
                  <span className="text-blue-600 dark:text-blue-400 font-mono">
                    {state.selectedBatch ? (state.selectedBatch.fileName || state.selectedBatch.file_name) : "All Lead Records"}
                  </span>
                </h4>
                <p className="text-[11px] text-neutral-500 dark:text-neutral-400">
                  Showing lead records with dynamic column schema matching this file
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={state.handleClearSelectedBatch}
              className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline"
            >
              ← Back to Lead Lists
            </button>
          </div>

          <LeadListTable
            searchQuery={state.searchQuery}
            onSearchChange={state.setSearchQuery}
            statusFilter={state.statusFilter}
            onStatusFilterChange={state.setStatusFilter}
            onSort={state.handleSort}
            filteredLeads={state.filteredLeads}
            leads={state.leads}
            onSelectLead={state.navigateToAction}
            page={state.page}
            pageSize={state.pageSize}
            totalLeads={state.totalLeads}
            totalPages={state.totalPages}
            onNextPage={state.handleNextPage}
            onPrevPage={state.handlePrevPage}
            onPageSizeChange={state.handlePageSizeChange}
            selectedBatch={state.selectedBatch}
            batchColumns={state.batchColumns}
          />
        </div>
      )}

      {/* ========================================================================= */}
      {/* ROUTE 3: IMPORT WIZARD (/leads/import) */}
      {/* ========================================================================= */}
      {state.viewMode === "import" && (
        <LeadImportWizard
          onBack={() => state.navigateToAction("all")}
          importStep={state.importStep}
          onSetImportStep={state.setImportStep}
          uploadedFileName={state.uploadedFileName}
          onFileUpload={state.handleFileUpload}
          onStartImport={state.handleStartImport}
          onValidateMapping={state.handleValidateMapping}
          onColumnMappingChange={state.handleColumnMappingChange}
          onViewList={state.handleViewImportedList}
          onResetWizard={state.handleResetImportWizard}
          importError={state.importError}
          importBusy={state.importBusy}
          detectedCount={state.detectedCount}
          importColumns={state.importColumns}
          columnMapping={state.columnMapping}
          importValidation={state.importValidation}
          importResult={state.importResult}
          importTargetFields={state.importTargetFields}
          importCustomField={state.importCustomField}
          importSkipColumn={state.importSkipColumn}
          activeCampaigns={state.activeCampaigns}
          importCampaignId={state.importCampaignId}
          onImportCampaignChange={state.setImportCampaignId}
        />
      )}

      {/* ========================================================================= */}
      {/* ROUTE 4: LEAD DETAIL + CALL HISTORY (/leads/[leadId]) */}
      {/* ========================================================================= */}
      {state.viewMode === "detail" && state.selectedLead && (
        <LeadDetailView
          lead={state.selectedLead}
          onBack={() => state.navigateToAction("list")}
        />
      )}

      {/* ========================================================================= */}
      {/* ROUTE 5: SUPPRESSION LIST / DNC (/leads/suppression) */}
      {/* ========================================================================= */}
      {state.viewMode === "suppression" && (
        <SuppressionListView
          suppressionList={state.suppressionList}
          suppressionBatches={state.suppressionBatches}
          selectedSuppressionBatch={state.selectedSuppressionBatch}
          onSelectSuppressionBatch={state.handleSelectSuppressionBatch}
          onClearSelectedSuppressionBatch={state.handleClearSelectedSuppressionBatch}
          onDeleteSuppressionBatch={state.handleDeleteSuppressionBatch}
          onImportSuppressionFile={() => state.setIsSuppressionImportModalOpen(true)}
        />
      )}

      {/* ========================================================================= */}
      {/* MODALS */}
      {/* ========================================================================= */}
      <LeadModals
        isAddModalOpen={state.isAddModalOpen}
        onCloseAddModal={() => state.setIsAddModalOpen(false)}
        newFirstName={state.newFirstName}
        onNewFirstName={state.setNewFirstName}
        newLastName={state.newLastName}
        onNewLastName={state.setNewLastName}
        newPhone={state.newPhone}
        onNewPhone={state.setNewPhone}
        newEmail={state.newEmail}
        onNewEmail={state.setNewEmail}
        newCampaign={state.newCampaign}
        onNewCampaign={state.setNewCampaign}
        newStatus={state.newStatus}
        onNewStatus={state.setNewStatus}
        onAddLeadSubmit={state.handleAddLead}
        isSuppressionImportModalOpen={state.isSuppressionImportModalOpen}
        onCloseSuppressionImportModal={() => state.setIsSuppressionImportModalOpen(false)}
        onImportSuppressionFileSubmit={state.handleImportSuppressionFileSubmit}
      />
    </div>
  );
}