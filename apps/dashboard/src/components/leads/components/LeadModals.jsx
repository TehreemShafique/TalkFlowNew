"use client";

import React, { useState } from "react";
import { X, UploadCloud, FileText, AlertCircle } from "lucide-react";

export default function LeadModals({
  isAddModalOpen,
  onCloseAddModal,
  newFirstName,
  onNewFirstName,
  newLastName,
  onNewLastName,
  newPhone,
  onNewPhone,
  newEmail,
  onNewEmail,
  newCampaign,
  onNewCampaign,
  newStatus,
  onNewStatus,
  newState,
  onNewState,
  onAddLeadSubmit,
  isDncModalOpen,
  onCloseDncModal,
  newDncPhone,
  onNewDncPhone,
  newDncReason,
  onNewDncReason,
  onAddDncSubmit,
  // Suppression Import Modal props
  isSuppressionImportModalOpen,
  onCloseSuppressionImportModal,
  onImportSuppressionFileSubmit,
}) {
  const [suppFile, setSuppFile] = useState(null);
  const [suppListName, setSuppListName] = useState("");
  const [suppReason, setSuppReason] = useState("Do Not Call");
  const [suppError, setSuppError] = useState("");

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setSuppFile(file);
      if (!suppListName) {
        setSuppListName(file.name);
      }
      setSuppError("");
    }
  };

  const handleSuppressionImportSubmit = (e) => {
    e.preventDefault();
    if (!suppFile && !suppListName) {
      setSuppError("Please select a CSV file or enter a list name.");
      return;
    }

    if (onImportSuppressionFileSubmit) {
      onImportSuppressionFileSubmit({
        file: suppFile,
        listName: suppListName || "Imported Suppression List",
        reason: suppReason,
      });
    }

    setSuppFile(null);
    setSuppListName("");
    setSuppError("");
    if (onCloseSuppressionImportModal) onCloseSuppressionImportModal();
  };

  return (
    <>
      {/* Add Lead Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/70 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#121214] p-6 shadow-2xl text-neutral-900 dark:text-neutral-100">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3 mb-4">
              <h3 className="text-base font-bold text-neutral-900 dark:text-white">
                Add New Lead
              </h3>
              <button
                onClick={onCloseAddModal}
                className="text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={onAddLeadSubmit} className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-neutral-700 dark:text-neutral-300 mb-1">
                    First Name
                  </label>
                  <input
                    type="text"
                    required
                    value={newFirstName}
                    onChange={(e) => onNewFirstName(e.target.value)}
                    placeholder="e.g. Alex"
                    className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-1.5 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-neutral-700 dark:text-neutral-300 mb-1">
                    Last Name
                  </label>
                  <input
                    type="text"
                    value={newLastName}
                    onChange={(e) => onNewLastName(e.target.value)}
                    placeholder="e.g. Johnson"
                    className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-1.5 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-neutral-700 dark:text-neutral-300 mb-1">
                  Phone Number
                </label>
                <input
                  type="text"
                  required
                  value={newPhone}
                  onChange={(e) => onNewPhone(e.target.value)}
                  placeholder="+1 (555) 000-0000"
                  className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-1.5 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-600"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-neutral-700 dark:text-neutral-300 mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => onNewEmail(e.target.value)}
                  placeholder="alex.johnson@example.com"
                  className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-1.5 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-600"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-neutral-700 dark:text-neutral-300 mb-1">
                    Campaign
                  </label>
                  <select
                    value={newCampaign}
                    onChange={(e) => onNewCampaign(e.target.value)}
                    className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-1.5 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-600"
                  >
                    <option value="Med Fronter">Med Fronter</option>
                    <option value="Solar Outreach East">Solar Outreach East</option>
                    <option value="Insurance Renewals">Insurance Renewals</option>
                    <option value="Data Campaign">Data Campaign</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-neutral-700 dark:text-neutral-300 mb-1">
                    Status
                  </label>
                  <select
                    value={newStatus}
                    onChange={(e) => onNewStatus(e.target.value)}
                    className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-1.5 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500 dark:focus:border-neutral-600"
                  >
                    <option value="New">New</option>
                    <option value="Contacted">Contacted</option>
                    <option value="Qualified">Qualified</option>
                    <option value="Converted">Converted</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-200 dark:border-neutral-800 mt-2">
                <button
                  type="button"
                  onClick={onCloseAddModal}
                  className="rounded-md px-3 py-1.5 text-xs text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md bg-blue-600 px-4 py-1.5 text-xs font-bold text-white hover:bg-blue-700"
                >
                  Save Lead
                </button>
              </div>
            </form>
          </div>
        </div>
      )}



      {/* Import Bulk Suppression CSV File Modal */}
      {isSuppressionImportModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/70 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#121214] p-6 shadow-2xl text-neutral-900 dark:text-neutral-100">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3 mb-4">
              <h3 className="text-base font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <UploadCloud className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                <span>Import Bulk Suppression CSV File</span>
              </h3>
              <button
                onClick={onCloseSuppressionImportModal}
                className="text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleSuppressionImportSubmit} className="flex flex-col gap-4">
              <div>
                <label className="block text-xs font-bold text-neutral-700 dark:text-neutral-300 mb-1">
                  Suppression List / Batch Name
                </label>
                <input
                  type="text"
                  required
                  value={suppListName}
                  onChange={(e) => setSuppListName(e.target.value)}
                  placeholder="e.g. Federal_DNC_September_2026.csv"
                  className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-2 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-neutral-700 dark:text-neutral-300 mb-1">
                  Upload CSV File (Phone column required)
                </label>
                <div className="relative border-2 border-dashed border-neutral-300 dark:border-neutral-700 rounded-lg p-6 text-center bg-neutral-50 dark:bg-[#18181b] hover:border-blue-500 transition-colors">
                  <input
                    type="file"
                    accept=".csv"
                    onChange={handleFileChange}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  <div className="flex flex-col items-center justify-center gap-2">
                    <UploadCloud className="h-8 w-8 text-neutral-400" />
                    {suppFile ? (
                      <div className="flex items-center gap-2 text-xs font-bold text-blue-600 dark:text-blue-400">
                        <FileText className="h-4 w-4" />
                        <span>{suppFile.name} ({(suppFile.size / 1024).toFixed(1)} KB)</span>
                      </div>
                    ) : (
                      <>
                        <p className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
                          Drag & drop your DNC CSV file here or <span className="text-blue-600 underline">browse</span>
                        </p>
                        <p className="text-[11px] text-neutral-500 dark:text-neutral-400">
                          CSV must contain a <code className="bg-neutral-200 dark:bg-neutral-800 px-1 py-0.5 rounded">phone</code> column
                        </p>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-neutral-700 dark:text-neutral-300 mb-1">
                  Default Suppression Reason
                </label>
                <select
                  value={suppReason}
                  onChange={(e) => setSuppReason(e.target.value)}
                  className="w-full rounded-md border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-[#18181b] px-3 py-2 text-xs text-neutral-900 dark:text-white outline-none focus:border-blue-500"
                >
                  <option value="Do Not Call">Do Not Call (DNC)</option>
                  <option value="Customer Request">Verbal Customer Opt-Out</option>
                  <option value="National DNC Match">National DNC Registry Match</option>
                  <option value="TCPA Litigant">TCPA Attorney Litigation Risk</option>
                  <option value="Disconnected">Disconnected / Invalid Phone</option>
                </select>
              </div>

              {suppError && (
                <div className="flex items-center gap-2 p-2.5 rounded-lg bg-rose-50 text-rose-700 text-xs font-medium">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{suppError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-200 dark:border-neutral-800 mt-2">
                <button
                  type="button"
                  onClick={onCloseSuppressionImportModal}
                  className="rounded-md px-3 py-1.5 text-xs text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md bg-blue-600 px-4 py-1.5 text-xs font-bold text-white hover:bg-blue-700 shadow-xs"
                >
                  Import Suppression File
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}