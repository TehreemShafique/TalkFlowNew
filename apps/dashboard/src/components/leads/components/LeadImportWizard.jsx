"use client";

import {
  ArrowLeft,
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ShieldCheck,
  Ban,
  Copy,
  FileWarning,
} from "lucide-react";

import { apiUrl } from "@/lib/api";

const inputClass =
  "w-full px-3 py-2 text-xs rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium";

const buttonPrimaryClass =
  "px-4 py-1.5 text-xs font-bold bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 dark:disabled:bg-blue-900 text-white rounded-md shadow-xs transition-colors";

const buttonGhostClass =
  "px-3 py-1.5 text-xs text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white disabled:opacity-50";

function ErrorBanner({ title, message }) {
  if (!message) return null;
  return (
    <div className="flex items-start gap-3 p-3.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
      <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
      <div className="flex flex-col gap-1">
        <span className="font-bold">{title}</span>
        <span>{message}</span>
      </div>
    </div>
  );
}

function StatTile({ icon: Icon, value, label, tone }) {
  const toneClass = {
    emerald: "text-emerald-600 dark:text-emerald-400",
    amber: "text-amber-600 dark:text-amber-400",
    rose: "text-rose-600 dark:text-rose-400",
    slate: "text-neutral-500 dark:text-neutral-400",
  }[tone];

  return (
    <div className="flex flex-col gap-1 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 px-3 py-2.5">
      <span className={`flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide ${toneClass}`}>
        <Icon className="h-3.5 w-3.5" />
        {label}
      </span>
      <span className="text-lg font-bold text-neutral-900 dark:text-white">
        {Number(value || 0).toLocaleString()}
      </span>
    </div>
  );
}

export default function LeadImportWizard({
  onBack,
  importStep,
  onSetImportStep,
  uploadedFileName,
  onFileUpload,
  onStartImport,
  onValidateMapping,
  onColumnMappingChange,
  onViewList,
  onResetWizard,
  importError,
  importBusy = null,
  detectedCount = 0,
  importColumns = [],
  columnMapping = {},
  importValidation = null,
  importResult = null,
  importTargetFields = [],
  importCustomField = "__custom__",
  importSkipColumn = "",
  activeCampaigns = [],
  importCampaignId = "",
  onImportCampaignChange,
}) {
  // The backend refuses a mapping with no phone column, so say so before the
  // round trip instead of letting the user submit and eat a 422.
  const phoneMapped = Object.values(columnMapping).includes("phone");
  const isUploading = importBusy === "upload";
  const isMapping = importBusy === "mapping";
  const isCommitting = importBusy === "commit";
  const skipped = (importValidation?.total ?? detectedCount) - (importValidation?.valid ?? 0);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="p-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h3 className="text-base font-bold text-neutral-900 dark:text-white">
              Bulk Lead Import Wizard
            </h3>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              Upload a CSV list, map the columns, and scrub every row against the DNC register
            </p>
          </div>
        </div>
      </div>

      <div className="w-full rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-6 shadow-xs flex flex-col gap-6">
        {/* Step Indicators */}
        <div className="grid grid-cols-3 gap-4 border-b border-neutral-200 dark:border-neutral-800 pb-5">
          <div className={`flex items-center gap-3 ${importStep >= 1 ? "text-blue-600 dark:text-blue-400" : "text-neutral-400"}`}>
            <div className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${importStep >= 1 ? "bg-blue-600 text-white" : "bg-neutral-200 dark:bg-neutral-800"}`}>
              1
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold">Upload File</span>
              <span className="text-[11px] opacity-70">CSV format</span>
            </div>
          </div>

          <div className={`flex items-center gap-3 ${importStep >= 2 ? "text-blue-600 dark:text-blue-400" : "text-neutral-400"}`}>
            <div className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${importStep >= 2 ? "bg-blue-600 text-white" : "bg-neutral-200 dark:bg-neutral-800"}`}>
              2
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold">Column Mapping</span>
              <span className="text-[11px] opacity-70">Map &amp; Validate</span>
            </div>
          </div>

          <div className={`flex items-center gap-3 ${importStep >= 3 ? "text-blue-600 dark:text-blue-400" : "text-neutral-400"}`}>
            <div className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${importStep >= 3 ? "bg-blue-600 text-white" : "bg-neutral-200 dark:bg-neutral-800"}`}>
              3
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold">Import Leads</span>
              <span className="text-[11px] opacity-70">Write to Registry</span>
            </div>
          </div>
        </div>

        {/* Step 1: Dropzone File Upload */}
        {importStep === 1 && (
          <div className="flex flex-col gap-4">
            <ErrorBanner title="File Rejected" message={importError} />

            <div className="flex flex-col items-center justify-center border-2 border-dashed border-neutral-300 dark:border-neutral-800 rounded-xl p-10 bg-neutral-50/50 dark:bg-[#121215] text-center gap-3">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800/60">
                {isUploading ? (
                  <Loader2 className="h-7 w-7 animate-spin" />
                ) : (
                  <UploadCloud className="h-7 w-7" />
                )}
              </div>
              <div>
                <h4 className="text-sm font-bold text-neutral-900 dark:text-white">
                  {isUploading ? "Uploading to the import service..." : "Select a CSV lead list to import"}
                </h4>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
                  UTF-8 CSV with a header row, up to 10&nbsp;MB and 25,000 rows
                </p>
              </div>

              <label
                className={`cursor-pointer inline-flex items-center gap-2 rounded-md bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 text-xs font-bold shadow-xs transition-colors mt-2 ${isUploading ? "opacity-50 pointer-events-none" : ""}`}
              >
                <FileSpreadsheet className="h-4 w-4" />
                <span>{isUploading ? "Uploading..." : "Choose Lead File"}</span>
                <input
                  type="file"
                  accept=".csv"
                  disabled={isUploading}
                  onChange={onFileUpload}
                  className="hidden"
                />
              </label>
            </div>
          </div>
        )}

        {/* Step 2: Column Mapping */}
        {importStep === 2 && (
          <div className="flex flex-col gap-4">
            <ErrorBanner title="Import Failed" message={importError} />

            <div className="flex items-center justify-between bg-blue-50 dark:bg-blue-950/40 p-3 rounded-lg border border-blue-200 dark:border-blue-800/60 text-xs">
              <div className="flex items-center gap-2 text-blue-700 dark:text-blue-300 font-semibold">
                <FileSpreadsheet className="h-4 w-4" />
                <span>Loaded File: {uploadedFileName || "leads_batch.csv"}</span>
              </div>
              <span className="font-bold text-blue-600 dark:text-blue-400">
                {detectedCount.toLocaleString()} Leads Detected
              </span>
            </div>

            {/* Campaign assignment - applied by the backend to every committed row */}
            <div className="flex flex-col gap-1.5 p-3.5 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-[#121215]">
              <label htmlFor="import-campaign" className="text-xs font-bold text-neutral-800 dark:text-neutral-200">
                Assign to Campaign
              </label>
              <select
                id="import-campaign"
                value={importCampaignId}
                onChange={(e) => onImportCampaignChange && onImportCampaignChange(e.target.value)}
                className={inputClass}
              >
                <option value="">Unassigned</option>
                {activeCampaigns.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <span className="text-[11px] text-neutral-500 dark:text-neutral-400">
                Optional. Applied to every lead this file creates.
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 font-semibold uppercase text-[11px]">
                    <th className="py-2.5 px-3">CSV Column Header</th>
                    <th className="py-2.5 px-3">Mapped TalkFlow Field</th>
                    <th className="py-2.5 px-3">Sample Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800/60">
                  {importColumns.map((column) => {
                    const samples = Array.isArray(column.sampleValues)
                      ? column.sampleValues.filter(Boolean)
                      : [];
                    return (
                      <tr key={column.name}>
                        <td className="py-2 px-3 font-mono align-top">{column.name}</td>
                        <td className="py-2 px-3 align-top">
                          <select
                            value={columnMapping[column.name] ?? importSkipColumn}
                            onChange={(e) =>
                              onColumnMappingChange && onColumnMappingChange(column.name, e.target.value)
                            }
                            className="w-full min-w-52 px-2 py-1.5 text-xs rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-blue-600 dark:text-blue-400 font-bold focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            <option value={importSkipColumn}>— Do not import —</option>
                            {importTargetFields.map(([value, label]) => (
                              <option key={value} value={value}>
                                {label}
                              </option>
                            ))}
                            <option value={importCustomField}>Custom Field (keep as &quot;{column.name}&quot;)</option>
                          </select>
                        </td>
                        <td className="py-2 px-3 text-neutral-600 dark:text-neutral-400 align-top">
                          {samples.length > 0 ? samples.join(" · ") : "—"}
                        </td>
                      </tr>
                    );
                  })}
                  {importColumns.length === 0 && (
                    <tr>
                      <td colSpan={3} className="py-4 px-3 text-neutral-500 dark:text-neutral-400">
                        No columns were returned for this file. Start the import again.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {!phoneMapped && (
              <div className="flex items-start gap-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-xs text-amber-700 dark:text-amber-300">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>Map one column to Phone Number — it is the only field the importer requires.</span>
              </div>
            )}

            {importValidation && (
              <div className="flex flex-col gap-3 p-3.5 rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/20">
                <div className="flex items-center gap-2 text-xs font-bold text-emerald-700 dark:text-emerald-300">
                  <ShieldCheck className="h-4 w-4" />
                  <span>Scrubbed against the DNC register and existing leads</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <StatTile icon={CheckCircle2} tone="emerald" value={importValidation.valid} label="Ready" />
                  <StatTile icon={Ban} tone="amber" value={importValidation.suppressed} label="Suppressed" />
                  <StatTile icon={Copy} tone="amber" value={(importValidation.duplicatesFile ?? 0) + (importValidation.duplicatesSystem ?? 0)} label="Duplicates" />
                  <StatTile icon={FileWarning} tone="rose" value={importValidation.invalid} label="Invalid" />
                </div>
                {skipped > 0 && (
                  <span className="text-[11px] text-emerald-700/80 dark:text-emerald-300/80">
                    {skipped.toLocaleString()} of {Number(importValidation.total ?? 0).toLocaleString()} rows will be skipped.
                  </span>
                )}
              </div>
            )}

            <div className="flex justify-end gap-2 pt-4 border-t border-neutral-200 dark:border-neutral-800">
              <button
                type="button"
                onClick={() => onSetImportStep(1)}
                disabled={isMapping}
                className={buttonGhostClass}
              >
                Back
              </button>

              {importValidation ? (
                <button
                  type="button"
                  onClick={onStartImport}
                  disabled={isMapping || isCommitting || importValidation.valid === 0}
                  className={buttonPrimaryClass}
                >
                  {importValidation.valid === 0
                    ? "Nothing left to import"
                    : `Import ${Number(importValidation.valid).toLocaleString()} Leads`}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onValidateMapping}
                  disabled={!phoneMapped || isMapping}
                  className={buttonPrimaryClass}
                >
                  {isMapping ? "Validating..." : "Validate & Scrub DNC"}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Step 3: Commit */}
        {importStep === 3 && (
          <div className="flex flex-col items-center justify-center py-8 gap-4 text-center">
            {isCommitting && (
              <>
                <Loader2 className="h-8 w-8 animate-spin text-blue-600 dark:text-blue-400" />
                <h4 className="text-sm font-bold text-neutral-900 dark:text-white">
                  Importing leads...
                </h4>
                <span className="text-xs text-neutral-500 dark:text-neutral-400">
                  Writing validated rows to the lead registry.
                </span>
              </>
            )}

            {!isCommitting && importError && (
              <>
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 dark:bg-rose-950/80 text-rose-600 dark:text-rose-400 border border-rose-300 dark:border-rose-800">
                  <AlertCircle className="h-6 w-6" />
                </div>
                <h4 className="text-sm font-bold text-neutral-900 dark:text-white">
                  The import could not be completed
                </h4>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 max-w-md">{importError}</p>
                <div className="flex items-center gap-3 mt-3">
                  <button
                    type="button"
                    onClick={onResetWizard}
                    className="px-4 py-1.5 text-xs font-bold border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-800 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 rounded-md transition-colors"
                  >
                    + Import Another File
                  </button>
                  <button
                    type="button"
                    onClick={() => onSetImportStep(2)}
                    className="px-4 py-1.5 text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-md shadow-xs"
                  >
                    Back to Mapping
                  </button>
                </div>
              </>
            )}

            {!isCommitting && !importError && importResult && (
              <>
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <h4 className="text-sm font-bold text-neutral-900 dark:text-white">
                  {Number(importResult.importedRows || 0).toLocaleString()} leads imported.
                </h4>
                <p className="text-xs text-neutral-500 dark:text-neutral-400">
                  {Number(importResult.suppressedRows || 0).toLocaleString()} suppressed &middot;{" "}
                  {Number(importResult.duplicateRows || 0).toLocaleString()} duplicates &middot;{" "}
                  {Number(importResult.invalidRows || 0).toLocaleString()} invalid rows skipped
                </p>

                {importResult.errorReportUrl && (
                  <a
                    href={apiUrl(importResult.errorReportUrl)}
                    className="text-xs font-bold text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    Download skipped-row report (CSV)
                  </a>
                )}

                <div className="flex items-center gap-3 mt-3">
                  <button
                    type="button"
                    onClick={onResetWizard}
                    className="px-4 py-1.5 text-xs font-bold border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-800 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-800 rounded-md transition-colors"
                  >
                    + Import Another File
                  </button>
                  <button
                    type="button"
                    onClick={onViewList}
                    className="px-4 py-1.5 text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-md shadow-xs"
                  >
                    View Lead List
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
