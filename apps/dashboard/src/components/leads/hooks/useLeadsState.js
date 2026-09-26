"use client";

import { useState, useMemo, useEffect } from "react";
import { apiFetch } from "@/lib/api";

// ---------------------------------------------------------------------------
// Imported lead identifiers
// ---------------------------------------------------------------------------
// Lead rows are no longer minted or parsed in the browser: the upload step posts
// the file to the import pipeline, which assigns every lead a real UUID and a
// vendor-safe external_key server-side.

// The API speaks two error shapes: the contract envelope (``error.message``)
// and FastAPI's own ``detail``, which is a list of per-field objects for a
// 422. Collapsing both into one generic string is what made a rejected request
// look like an unexplained failure, so pull the real reason out. Returns null
// when the body carries nothing usable and the caller must supply a fallback.
function readApiErrorMessage(body) {
  const envelope = body?.error?.message || body?.message;
  if (envelope) return envelope;

  const detail = body?.detail;
  if (typeof detail === "string" && detail) return detail;

  if (Array.isArray(detail) && detail.length > 0) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        const where = Array.isArray(item?.loc) ? item.loc.slice(1).join(".") : "";
        const msg = item?.msg || "invalid value";
        return where ? `${where}: ${msg}` : msg;
      })
      .filter(Boolean);
    if (parts.length > 0) return parts.join("; ");
  }

  return null;
}

function describeApiFailure(status, body) {
  const message = readApiErrorMessage(body);
  if (message) return message;

  if (status === 422) return "The server rejected the request as invalid.";
  if (status === 404) return "The server no longer has this lead list.";
  if (status === 403) return "You do not have permission to run lists in VICIdial.";
  if (status === 503) return "VICIdial is not configured on the server.";
  return "Could not update the VICIdial run for this list.";
}

// The import pipeline returns a specific message for every rejection it raises
// (bad mapping, empty file, oversized upload, wrong job state), so this only
// has to cover the cases where no body came back at all.
function describeImportFailure(status, body) {
  const message = readApiErrorMessage(body);
  if (message) return message;

  if (status === 403) {
    return "You do not have permission to import leads.";
  }
  if (status === 404) {
    return "This import job no longer exists on the server. Start the import again.";
  }
  return "Could not reach the import service. Check that the backend is running and try again.";
}

// ---------------------------------------------------------------------------
// Import wizard: column mapping vocabulary
// ---------------------------------------------------------------------------
// Mirrors the target fields the backend accepts (policies.SYSTEM_FIELDS). A
// mapping entry naming anything outside this list is stored verbatim under the
// lead's custom_fields, which is how IMPORT_CUSTOM_FIELD is honoured.
const IMPORT_TARGET_FIELDS = [
  ["phone", "Phone Number"],
  ["first_name", "First Name"],
  ["last_name", "Last Name"],
  ["alt_phone", "Alternate Phone"],
  ["email", "Email Address"],
  ["state", "State"],
  ["zip_code", "ZIP Code"],
  ["date_of_birth", "Date of Birth (YYYY-MM-DD)"],
  ["source", "Source"],
  ["source_batch_id", "Source Batch ID"],
];

// UI-only selections. Neither is a legal backend target, so both are resolved
// before the mapping is posted: the sentinel becomes the column's own name (a
// custom field), and "" drops the column entirely.
const IMPORT_CUSTOM_FIELD = "__custom__";
const IMPORT_SKIP_COLUMN = "";

// Headers that name the lead's primary phone outright. Anchored at the start so
// "Alt Phone" is not mistaken for it.
const IMPORT_PRIMARY_PHONE =
  /^(phone|mobile|cell|contact|telephone|tel|phone_number|mobile_number|cell_number|contact_number)[_\s-]?(number|no|num)?\b/i;

// Headers that name some *other* phone line (home/work/backup). These only take
// the alternate slot once a column has claimed the primary one.
const IMPORT_ALT_PHONE =
  /^(alt|alternate|secondary|home|work|other|backup|second)[_\s-]?(phone|mobile|cell|tel)/i;

const isPhoneHeader = (name) =>
  IMPORT_PRIMARY_PHONE.test(name) || IMPORT_ALT_PHONE.test(name);

// Ordered header patterns used to pre-fill the mapping table. The user can
// change every assignment before validating, and the server re-derives every
// value regardless - this only saves clicking, it never decides the outcome.
// Each target is claimed once, so two lookalike columns cannot silently
// overwrite each other.
const IMPORT_COLUMN_GUESSES = [
  [/e-?mail/i, "email"],
  [/first|given/i, "first_name"],
  [/last|family|surname/i, "last_name"],
  [/dob|birth/i, "date_of_birth"],
  [/zip|postal/i, "zip_code"],
  [/state|province|region/i, "state"],
  [/batch/i, "source_batch_id"],
  [/source|channel|list/i, "source"],
];

function guessColumnMapping(columns) {
  const mapping = {};
  const claimed = new Set();

  const claim = (column, target) => {
    mapping[column.name] = target;
    claimed.add(target);
  };

  const phoneCandidates = columns.filter((c) => c?.name && isPhoneHeader(c.name));

  // An unambiguous primary header wins the phone slot. A file whose only
  // phone-ish column is "Home Phone" still needs one, so the first candidate
  // takes it when nothing else claimed it - otherwise extra phone columns
  // become the alternate line rather than being dropped.
  const primary = phoneCandidates.find((c) => IMPORT_PRIMARY_PHONE.test(c.name));
  const fallback = phoneCandidates.find((c) => c.name !== primary?.name);
  if (primary) {
    claim(primary, "phone");
  } else if (fallback) {
    claim(fallback, "phone");
  }

  phoneCandidates.forEach((column) => {
    if (mapping[column.name]) return;
    claim(column, "alt_phone");
  });

  columns.forEach((column) => {
    const name = column?.name;
    if (!name || mapping[name]) return;
    const guess = IMPORT_COLUMN_GUESSES.find(
      ([pattern, target]) => pattern.test(name) && !claimed.has(target)
    );
    mapping[name] = guess ? guess[1] : IMPORT_CUSTOM_FIELD;
    if (guess) claimed.add(guess[1]);
  });

  return mapping;
}

// Turn the UI selections into the mapping the backend validates: the custom
// sentinel resolves to the column's own name, skipped columns are omitted.
function buildMappingPayload(columnMapping) {
  const payload = {};
  Object.entries(columnMapping).forEach(([column, target]) => {
    if (target === IMPORT_CUSTOM_FIELD) {
      payload[column] = column;
    } else if (target) {
      payload[column] = target;
    }
  });
  return payload;
}

// Legacy browser-only cache keys. Nothing reads them any more; they are cleared
// once so a stale copy of imported rows cannot linger in the user's browser.
const RETIRED_BATCH_KEYS = ["talkflow_lead_batches", "talkflow_deleted_batches"];

// The registry speaks one dialect (LeadBatchDTO). This fills in the camelCase
// aliases the table reads so every consumer sees one shape.
function normalizeBatch(batch) {
  return {
    ...batch,
    vicidialListId: batch.vicidialListId ?? batch.vicidial_list_id ?? null,
    runCount: Number(batch.runCount ?? batch.vicidial_run_count ?? 0) || 0,
    vicidialStatus: batch.vicidialStatus ?? batch.vicidial_status ?? "idle",
    isActiveForVicidial: Boolean(
      batch.isActiveForVicidial ?? batch.is_active_for_vicidial ?? false
    ),
  };
}

// Central state + route parsing for LeadsView with dynamic batches & pagination.
export function useLeadsState(initialAction, onActionChange) {
  const viewMode = useMemo(() => {
    if (!initialAction || initialAction === "all") return "all";
    if (initialAction === "list") return "list";
    if (initialAction === "import") return "import";
    if (initialAction === "suppression") return "suppression";
    return "detail";
  }, [initialAction]);

  const activeLeadId = viewMode === "detail" ? initialAction : null;

  const navigateToAction = (actionStr) => {
    if (onActionChange) {
      onActionChange(actionStr);
    }
  };

  // Imported lead lists are server state only. They used to be mirrored into
  // localStorage, which meant the browser could show - and permanently hide -
  // lists the server knew nothing about, and served rows the database never
  // held. The LeadImportJob registry is the single source of truth.
  const getStoredSuppressionBatches = () => {
    if (typeof window === "undefined") return null;
    try {
      const saved = localStorage.getItem("talkflow_suppression_batches");
      if (saved) return JSON.parse(saved);
    } catch (err) {
      // Fallback
    }
    return null;
  };

  const getStoredSuppressionList = () => {
    if (typeof window === "undefined") return [];
    try {
      const saved = localStorage.getItem("talkflow_suppression_entries");
      if (saved) return JSON.parse(saved);
    } catch (err) {
      // Fallback
    }
    return [];
  };

  const getStoredCampaigns = () => {
    if (typeof window === "undefined") return [];
    try {
      const saved = localStorage.getItem("talkflow_campaigns");
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return [];
  };

  // State datasets - initialize completely empty (no dummy data, no local cache)
  const [leads, setLeads] = useState([]);
  const [batches, setBatches] = useState([]);

  const [activeCampaigns, setActiveCampaigns] = useState(() => getStoredCampaigns());
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [batchColumns, setBatchColumns] = useState([]);
  // Registry-level failure (delete / campaign assign), surfaced in the table
  // instead of swallowed - a silent failure used to leave the UI showing a list
  // the server still had.
  const [batchError, setBatchError] = useState(null);

  // Suppression State (No dummy data - only real imported & extracted DNC lists)
  const [suppressionList, setSuppressionList] = useState(getStoredSuppressionList);
  const [suppressionBatches, setSuppressionBatches] = useState(() => {
    const stored = getStoredSuppressionBatches();
    if (stored && Array.isArray(stored)) return stored;
    return [];
  });
  const [selectedSuppressionBatch, setSelectedSuppressionBatch] = useState(null);
  const [isSuppressionImportModalOpen, setIsSuppressionImportModalOpen] = useState(false);

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalLeads, setTotalLeads] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortField, setSortField] = useState("createdAt");
  const [sortAsc, setSortAsc] = useState(false);

  // Drop the retired browser-side batch caches once, so an old copy of
  // imported rows (and the delete tombstones that used to hide real lists) does
  // not sit in the browser indefinitely.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      RETIRED_BATCH_KEYS.forEach((key) => window.localStorage.removeItem(key));
    } catch (err) {
      // A blocked storage API must not break the registry.
    }
  }, []);

  // Load Active Campaigns for batch dropdown assignment
  useEffect(() => {
    async function loadCampaigns() {
      const localCamps = getStoredCampaigns();
      try {
        const res = await apiFetch("/campaigns");
        if (res.ok) {
          const body = await res.json();
          if (body?.data && Array.isArray(body.data)) {
            const apiItems = body.data.map((c) => ({
              id: String(c.id),
              name: c.name,
              status: c.status || "draft",
              ...c,
            }));
            const map = {};
            apiItems.forEach((c) => {
              map[String(c.id)] = c;
            });
            localCamps.forEach((l) => {
              if (l?.id) {
                map[String(l.id)] = {
                  ...(map[String(l.id)] || {}),
                  ...l,
                  status: l.status || map[String(l.id)]?.status || "draft",
                };
              }
            });
            const merged = Object.values(map);
            setActiveCampaigns(merged);
            return;
          }
        }
      } catch (err) {
        // Fallback
      }
      if (localCamps.length > 0) {
        setActiveCampaigns(localCamps);
      }
    }
    loadCampaigns();
  }, [viewMode]);

  // Load Lead Batches / Files Registry. Returns the merged registry so a caller
  // that just created a job (the import wizard) can find its own entry without
  // a second round trip.
  const loadBatches = async () => {
    try {
      const res = await apiFetch("/leads/batches");
      if (res.ok) {
        const body = await res.json();
        if (body?.data && Array.isArray(body.data)) {
          const merged = body.data.map(normalizeBatch);
          setBatches(merged);
          return merged;
        }
      }
    } catch (err) {
      // Fallback
    }
    return [];
  };

  useEffect(() => {
    loadBatches();
  }, []);

  // Fetch real leads & suppression entries from backend API
  useEffect(() => {
    async function loadData() {
      try {
        const queryParams = new URLSearchParams({
          page: String(page),
          // Query keys are the schema's camelCase aliases. FastAPI binds
          // query params by alias only, so a snake_case key is not rejected -
          // it is silently dropped and the endpoint answers with unfiltered,
          // default-paged results.
          pageSize: String(pageSize),
        });
        if (statusFilter && statusFilter !== "all") {
          queryParams.set("status", statusFilter);
        }
        if (searchQuery.trim()) {
          queryParams.set("search", searchQuery.trim());
        }
        if (selectedBatch?.id) {
          // Filter on the import job, not on the lead's free-text `source`.
          // `source` is only populated when the CSV happened to map a source
          // column, so filtering by it returned an empty list for most imports.
          queryParams.set("importJobId", String(selectedBatch.id));
        }

        const leadsRes = await apiFetch(`/leads?${queryParams.toString()}`);
        if (leadsRes.ok) {
          const body = await leadsRes.json();
          if (body?.data && Array.isArray(body.data) && body.data.length > 0) {
            const mapped = body.data.map((l) => ({
              id: l.id || l.externalKey || `LEAD-${String(l.id || "").slice(0, 6)}`,
              firstName: l.firstName || l.first_name || "Lead",
              lastName: l.lastName || l.last_name || "",
              phone: l.phone || l.phone_normalized || l.phone_raw || "—",
              email: l.email || "—",
              state: l.state || "US",
              campaign: l.campaignName || l.campaign_name || "Outbound Campaign",
              score: l.score || 75,
              status: l.status ? (l.status.charAt(0).toUpperCase() + l.status.slice(1).toLowerCase()) : "New",
              createdAt: l.createdAt ? new Date(l.createdAt).toLocaleDateString() : "Today",
              lastContacted: l.lastAttemptAt ? new Date(l.lastAttemptAt).toLocaleDateString() : "—",
              customFields: l.customFields || l.custom_fields || {},
            }));
            setLeads(mapped);
            if (body?.meta) {
              setTotalLeads(body.meta.total || body.data.length);
              setTotalPages(body.meta.total_pages || Math.ceil((body.meta.total || 1) / pageSize));
            }
          } else if (!selectedBatch) {
            setLeads([]);
            setTotalLeads(0);
            setTotalPages(1);
          }
        }
      } catch (err) {
        // Fallback
      }

      try {
        const dncRes = await apiFetch("/suppression");
        if (dncRes.ok) {
          const body = await dncRes.json();
          if (body?.data && Array.isArray(body.data) && body.data.length > 0) {
            const backendEntries = body.data.map((item) => ({
              id: item.id || `dnc-${Math.random()}`,
              phone: item.phone || item.phone_normalized || "—",
              reason: item.reason || "Do Not Call",
              addedBy: item.added_by || item.addedBy || "Admin",
              source: item.source || "API Import",
              addedAt: item.added_at || item.addedAt || new Date().toISOString(),
              status: "Suppressed",
              customFields: item.customFields || item,
            }));

            setSuppressionList((prev) => {
              const existingKeys = new Set(prev.map((p) => `${p.phone}-${p.source}`));
              const newItems = backendEntries.filter((e) => !existingKeys.has(`${e.phone}-${e.source}`));
              return [...prev, ...newItems];
            });
          }
        }
      } catch (err) {
        // Fallback
      }
    }
    loadData();
  }, [page, pageSize, statusFilter, searchQuery, selectedBatch]);

  // Dynamic DNC Auto-Extraction Effect: Scans all lead batches & lead records from /leads/all,
  // creating a Suppression List with the EXACT SAME NAME as the lead list and storing dynamic CSV columns.
  useEffect(() => {
    const dncBatchesMap = {};
    const dncEntries = [];

    // 1. Scan lead batches (including parsedLeads from imports like LIST_1011.csv)
    batches.forEach((batch) => {
      const rawFile = batch.fileName || batch.file_name || batch.name || batch.id;
      const stem = String(rawFile).replace(/\.csv$/i, "");
      const suppressionListName = stem.toLowerCase().endsWith("dnc suppression")
        ? stem
        : `${stem} DNC Suppression`;
      const batchId = `supp-batch-${suppressionListName.toLowerCase().replace(/[^a-z0-9]/g, "-")}`;
      const batchCols = batch.columns && Array.isArray(batch.columns) && batch.columns.length > 0
        ? batch.columns
        : ["phone", "first_name", "last_name", "status", "reason", "added_at"];

      const leadRows = batch.parsedLeads && Array.isArray(batch.parsedLeads) ? batch.parsedLeads : [];
      leadRows.forEach((l) => {
        const st = String(l.status || "").toLowerCase();
        const dncFlag = String(l.customFields?.dnc || l.customFields?.suppressed || l.customFields?.opt_out || "").toLowerCase();
        const isDnc =
          st.includes("dnc") ||
          st.includes("suppress") ||
          st.includes("opt-out") ||
          st.includes("opt_out") ||
          st.includes("do not call") ||
          st.includes("block") ||
          dncFlag === "true" ||
          dncFlag === "yes" ||
          dncFlag === "1" ||
          dncFlag === "dnc";

        if (isDnc) {
          if (!dncBatchesMap[batchId]) {
            dncBatchesMap[batchId] = {
              id: batchId,
              name: suppressionListName,
              source: suppressionListName,
              totalCount: 0,
              columns: batchCols,
              createdAt: batch.createdAt || new Date().toISOString(),
              type: "auto_extracted",
            };
          }

          if (!dncEntries.some((e) => e.phone === l.phone && e.source === suppressionListName)) {
            dncBatchesMap[batchId].totalCount += 1;
            dncEntries.push({
              id: `dnc-${l.id || Math.random()}-${batchId}`,
              phone: l.phone,
              reason: l.reason || "Lead Import DNC",
              addedBy: "System (Lead Auto-Filter)",
              source: suppressionListName,
              addedAt: batch.createdAt || new Date().toISOString(),
              status: "Suppressed",
              batchId: batchId,
              customFields: l.customFields || l,
            });
          }
        }
      });
    });

    // 2. Scan active leads dataset
    leads.forEach((l) => {
      const st = String(l.status || "").toLowerCase();
      const dncFlag = String(l.customFields?.dnc || l.customFields?.suppressed || l.customFields?.opt_out || "").toLowerCase();
      const isDnc =
        st.includes("dnc") ||
        st.includes("suppress") ||
        st.includes("opt-out") ||
        st.includes("opt_out") ||
        st.includes("do not call") ||
        st.includes("block") ||
        dncFlag === "true" ||
        dncFlag === "yes" ||
        dncFlag === "1" ||
        dncFlag === "dnc";

      if (isDnc) {
        const listName = l.campaign || l.batchName || "Lead List DNCs";
        const batchId = `supp-batch-${listName.toLowerCase().replace(/[^a-z0-9]/g, "-")}`;
        const leadCols = l.customFields ? Object.keys(l.customFields) : ["phone", "firstName", "lastName", "status"];

        if (!dncBatchesMap[batchId]) {
          dncBatchesMap[batchId] = {
            id: batchId,
            name: listName,
            source: listName,
            totalCount: 0,
            columns: leadCols,
            createdAt: l.createdAt || new Date().toISOString(),
            type: "auto_extracted",
          };
        }

        const exists = dncEntries.some((e) => e.phone === l.phone && e.source === listName);
        if (!exists) {
          dncBatchesMap[batchId].totalCount += 1;
          dncEntries.push({
            id: `dnc-${l.id || Math.random()}-act`,
            phone: l.phone,
            reason: l.reason || "Lead DNC Status",
            addedBy: "System (Lead Auto-Filter)",
            source: listName,
            addedAt: l.createdAt || new Date().toISOString(),
            status: "Suppressed",
            batchId: batchId,
            customFields: l.customFields || l,
          });
        }
      }
    });

    const extractedBatchesList = Object.values(dncBatchesMap);

    // Keep user-imported CSV suppression batches and update auto-extracted batches matching current lead lists
    setSuppressionBatches((prev) => {
      const map = {};
      prev.filter((b) => b.type === "csv").forEach((b) => { map[b.id] = b; });
      extractedBatchesList.forEach((b) => { map[b.id] = b; });
      const updated = Object.values(map);
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("talkflow_suppression_batches", JSON.stringify(updated));
        } catch (e) {
          // Fallback
        }
      }
      return updated;
    });

    setSuppressionList((prev) => {
      const csvEntries = prev.filter((e) => e.addedBy && e.addedBy.includes("File Import"));
      const existingKeys = new Set(csvEntries.map((item) => `${item.phone}-${item.source}`));
      const toAdd = dncEntries.filter((e) => !existingKeys.has(`${e.phone}-${e.source}`));
      const updated = [...csvEntries, ...toAdd];
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("talkflow_suppression_entries", JSON.stringify(updated));
        } catch (e) {
          // Fallback
        }
      }
      return updated;
    });
  }, [batches, leads]);

  const handleSelectBatch = (batch) => {
    setSelectedBatch(batch);
    if (batch?.columns && Array.isArray(batch.columns)) {
      setBatchColumns(batch.columns);
    } else {
      setBatchColumns([]);
    }

    setPage(1);
    navigateToAction("list");
  };

  // Delete a list and every lead it committed. The server owns the outcome, so
  // the row is only removed from the table once the request succeeds - the old
  // client-side tombstone hid the list forever even when the DELETE failed.
  const handleDeleteBatch = async (batchId) => {
    setBatchError(null);

    const res = await apiFetch(`/leads/batches/${batchId}`, { method: "DELETE" });
    const body = await res.json().catch(() => ({}));

    if (!res.ok) {
      setBatchError(describeApiFailure(res.status, body));
      return false;
    }

    setBatches((prev) => prev.filter((b) => String(b.id) !== String(batchId)));

    if (String(selectedBatch?.id) === String(batchId)) {
      setSelectedBatch(null);
      setBatchColumns([]);
      setLeads([]);
      setTotalLeads(0);
      setTotalPages(1);
    }

    return true;
  };

  const handleResetImportWizard = () => {
    setImportStep(1);
    setUploadedFileName(null);
    setImportError(null);
    setDetectedCount(0);
    setImportJobId(null);
    setImportColumns([]);
    setColumnMapping({});
    setImportValidation(null);
    setImportResult(null);
    setImportCampaignId("");
    setImportVicidialListId("");
    navigateToAction("import");
  };

  const handleClearSelectedBatch = () => {
    setSelectedBatch(null);
    setBatchColumns([]);
    setLeads([]);
    setTotalLeads(0);
    setTotalPages(1);
    navigateToAction("all");
  };

  const handleSelectSuppressionBatch = (batch) => {
    setSelectedSuppressionBatch(batch);
  };

  const handleClearSelectedSuppressionBatch = () => {
    setSelectedSuppressionBatch(null);
  };

  const handleDeleteSuppressionBatch = (batchId) => {
    setSuppressionBatches((prev) => {
      const updated = prev.filter((b) => b.id !== batchId);
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("talkflow_suppression_batches", JSON.stringify(updated));
        } catch (e) {
          // Fallback
        }
      }
      return updated;
    });
    if (selectedSuppressionBatch?.id === batchId) {
      setSelectedSuppressionBatch(null);
    }
  };

  // Assign a campaign to a whole imported list. Optimistic for responsiveness,
  // then reconciled against the server - which is now the only place the
  // assignment is stored.
  const handleAssignCampaign = async (batchId, campaignId) => {
    setBatchError(null);

    setBatches((prev) =>
      prev.map((b) =>
        String(b.id) === String(batchId)
          ? normalizeBatch({ ...b, campaignId, campaign_id: campaignId })
          : b
      )
    );

    const res = await apiFetch(`/leads/batches/${batchId}/campaign`, {
      method: "PATCH",
      body: JSON.stringify({ campaign_id: campaignId }),
    });
    const body = await res.json().catch(() => ({}));

    if (!res.ok) {
      setBatchError(describeApiFailure(res.status, body));
    }

    // Re-read either way: on success this is the confirmation, on failure it
    // rolls the optimistic row back to what the server actually has.
    await loadBatches();
  };

  const handleUpdateVicidialList = async (batchId, vicidialListId) => {
    setBatchError(null);

    setBatches((prev) =>
      prev.map((b) =>
        String(b.id) === String(batchId)
          ? normalizeBatch({ ...b, vicidialListId: vicidialListId || null, vicidial_list_id: vicidialListId || null })
          : b
      )
    );

    const res = await apiFetch(`/leads/batches/${batchId}/vicidial-list`, {
      method: "PATCH",
      body: JSON.stringify({ vicidial_list_id: vicidialListId || null }),
    });
    const body = await res.json().catch(() => ({}));

    if (!res.ok) {
      setBatchError(describeApiFailure(res.status, body));
    }

    await loadBatches();
  };

  const handleStatusFilterChange = (st) => {
    setStatusFilter(st);
    setPage(1);
  };

  // Start / stop the VICIdial run for one imported list. The dialer push is a
  // backend call (the browser cannot reach non_agent_api.php), so the toggle
  // stays disabled until the server confirms - an optimistic flip that later
  // 502s would show a list as "running" that the dialer never received.
  const [vicidialBusyBatchId, setVicidialBusyBatchId] = useState(null);
  const [vicidialError, setVicidialError] = useState(null);

  const handleToggleVicidialRun = async (batchId, activeState) => {
    if (vicidialBusyBatchId) return null;

    setVicidialBusyBatchId(batchId);
    setVicidialError(null);

    try {
      const res = await apiFetch(`/leads/batches/${batchId}/vicidial-run`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: Boolean(activeState) }),
      });

      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setVicidialError(describeApiFailure(res.status, body));
        return null;
      }

      // The DTO is camelCase on the wire; reading snake_case here silently
      // yielded undefined for every field, so the run state on screen never
      // reflected what the dialer was told.
      const data = body?.data;
      const applyRunState = (b) =>
        normalizeBatch({
          ...b,
          vicidialListId: data?.vicidialListId ?? b.vicidialListId,
          vicidial_run_count: data?.vicidialRunCount ?? b.runCount,
          vicidial_status: data?.vicidialStatus ?? b.vicidialStatus,
          is_active_for_vicidial: data?.isActiveForVicidial ?? activeState,
        });

      setBatches((prev) =>
        prev.map((b) => (String(b.id) === String(batchId) ? applyRunState(b) : b))
      );

      if (String(selectedBatch?.id) === String(batchId)) {
        setSelectedBatch((prev) => (prev ? applyRunState(prev) : prev));
      }

      return data;
    } catch (err) {
      setVicidialError("Network error while updating the VICIdial run.");
      return null;
    } finally {
      setVicidialBusyBatchId(null);
    }
  };

  const handleSearchChange = (q) => {
    setSearchQuery(q);
    setPage(1);
  };

  const handleNextPage = () => {
    if (page < totalPages) setPage((prev) => prev + 1);
  };

  const handlePrevPage = () => {
    if (page > 1) setPage((prev) => prev - 1);
  };

  const handlePageSizeChange = (newSize) => {
    setPageSize(Number(newSize));
    setPage(1);
  };

  // Add Lead Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newFirstName, setNewFirstName] = useState("");
  const [newLastName, setNewLastName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newCampaign, setNewCampaign] = useState("Outbound Campaign");
  const [newStatus, setNewStatus] = useState("New");
  const [newState, setNewState] = useState("CA");

  // Import Wizard State
  // The wizard is a thin driver over the backend pipeline: the upload parks a
  // LeadImportJob, the mapping step classifies every row, the commit writes the
  // leads. Only the job id and the server's own answers are held here - the
  // browser never parses or stores lead rows.
  const [importStep, setImportStep] = useState(1);
  const [uploadedFileName, setUploadedFileName] = useState(null);
  const [importError, setImportError] = useState(null);
  const [detectedCount, setDetectedCount] = useState(0);
  const [importJobId, setImportJobId] = useState(null);
  const [importColumns, setImportColumns] = useState([]);
  const [columnMapping, setColumnMapping] = useState({});
  const [importValidation, setImportValidation] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [importBusy, setImportBusy] = useState(null);
  const [importCampaignId, setImportCampaignId] = useState("");
  const [importVicidialListId, setImportVicidialListId] = useState("");

  // STEP 1-2: hand the file to the backend. It parses the CSV, infers the
  // columns, and parks a LeadImportJob in `mapping`; nothing is written to the
  // leads table yet, and no rows are held in the browser.
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    // Clear the input so choosing the same file again re-triggers the change.
    e.target.value = "";
    if (!file) return;

    setImportError(null);
    setImportValidation(null);
    setImportResult(null);
    setImportBusy("upload");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await apiFetch("/leads/import", { method: "POST", body: formData });
      const body = await res.json().catch(() => ({}));

      if (!res.ok) {
        setImportError(describeImportFailure(res.status, body));
        return;
      }

      const data = body?.data;
      const columns = Array.isArray(data?.columns) ? data.columns : [];

      setImportJobId(data?.jobId ? String(data.jobId) : null);
      setUploadedFileName(data?.fileName || file.name);
      setDetectedCount(Number(data?.totalRows) || 0);
      setImportColumns(columns);
      setColumnMapping(guessColumnMapping(columns));
      setImportStep(2);
    } catch (err) {
      setImportError("Network error while uploading the file. Please try again.");
    } finally {
      setImportBusy(null);
    }
  };

  const handleColumnMappingChange = (column, target) => {
    setColumnMapping((prev) => ({ ...prev, [column]: target }));
    // Any edit invalidates the last classification, so the commit button must
    // not stay enabled against counts the server produced for a stale mapping.
    setImportValidation(null);
  };

  // STEP 3-4: save the mapping. This is also the DNC scrub: the server
  // classifies every row against the suppression register and the existing
  // leads, drops the losers, and returns the counts the commit will act on.
  const handleValidateMapping = async () => {
    if (!importJobId || importBusy) return;

    setImportError(null);
    setImportBusy("mapping");

    try {
      const res = await apiFetch(`/leads/import/${importJobId}/mapping`, {
        method: "POST",
        body: JSON.stringify({
          mapping: buildMappingPayload(columnMapping),
          ...(importCampaignId ? { campaignId: importCampaignId } : {}),
          ...(importVicidialListId ? { vicidialListId: importVicidialListId } : {}),
        }),
      });
      const body = await res.json().catch(() => ({}));

      if (!res.ok) {
        setImportError(describeImportFailure(res.status, body));
        return;
      }

      setImportValidation(body?.data?.validation ?? null);
    } catch (err) {
      setImportError("Network error while validating the column mapping.");
    } finally {
      setImportBusy(null);
    }
  };

  // STEP 5: commit. The job is already validated, so this writes the surviving
  // rows in 1000-row chunks and returns the real imported count.
  const handleStartImport = async () => {
    if (!importJobId || importBusy) return;

    setImportError(null);
    setImportStep(3);
    setImportBusy("commit");

    try {
      const res = await apiFetch(`/leads/import/${importJobId}/commit`, {
        method: "POST",
      });
      const body = await res.json().catch(() => ({}));

      if (!res.ok || !body?.data) {
        setImportError(describeImportFailure(res.status, body));
        return;
      }

      setImportResult(body.data);

      // Pull the job from the registry so the new list appears in its canonical
      // LeadBatchDTO shape, then select it so "View Lead List" lands on it.
      const merged = await loadBatches();
      const created = merged.find((b) => String(b.id) === String(importJobId));
      if (created) {
        setSelectedBatch(created);
        setBatchColumns(Array.isArray(created.columns) ? created.columns : []);
      }
    } catch (err) {
      setImportError("Network error while committing the import. The job is saved - retry from the lead lists registry.");
    } finally {
      setImportBusy(null);
    }
  };

  // Import Bulk Suppression File Handler
  const handleImportSuppressionFileSubmit = async ({ file, listName, reason }) => {
    const name = listName || (file ? file.name : "Imported Suppression List");
    const batchId = `supp-batch-${name.toLowerCase().replace(/[^a-z0-9]/g, "-")}`;

    const processText = (text) => {
      const lines = text.split(/\r\n|\n/).filter((l) => l.trim().length > 0);
      if (lines.length < 2) return;

      let delimiter = ",";
      if (lines[0].includes("\t")) delimiter = "\t";
      else if (lines[0].includes(";")) delimiter = ";";

      const splitLine = (l) => l.split(delimiter).map((v) => v.trim().replace(/^"|"$/g, ""));
      const headers = splitLine(lines[0]);
      let phoneIdx = headers.findIndex((h) => !/code|dial_code|country/i.test(h) && /phone_number|mobile_number|cell_number|phone|mobile|cell|contact|tele|number/i.test(h));
      if (phoneIdx === -1) {
        phoneIdx = headers.findIndex((h) => /phone|mobile|cell|number|contact|tele/i.test(h));
      }
      if (phoneIdx === -1) {
        const sampleVals = splitLine(lines[1] || "");
        phoneIdx = sampleVals.findIndex((v) => /\d{5,}/.test(String(v)));
        if (phoneIdx === -1) phoneIdx = 0;
      }
      const reasonIdx = headers.findIndex((h) => /reason|type|category/i.test(h));

      const newEntries = [];
      for (let i = 1; i < lines.length; i++) {
        const values = splitLine(lines[i]);
        if (!values || values.length === 0) continue;
        const phoneVal = values[phoneIdx] || values[0];
        if (!phoneVal || phoneVal.length < 3) continue;
        const rowReason = (reasonIdx !== -1 ? values[reasonIdx] : null) || reason || "Do Not Call";

        const rowObj = {};
        headers.forEach((h, idx) => {
          rowObj[h] = values[idx] !== undefined ? values[idx] : "";
        });

        newEntries.push({
          id: `dnc-${Date.now()}-${i}`,
          phone: phoneVal,
          reason: rowReason,
          addedBy: "Admin (File Import)",
          source: name,
          addedAt: new Date().toISOString(),
          status: "Suppressed",
          batchId: batchId,
          customFields: rowObj,
        });
      }

      if (newEntries.length > 0) {
        setSuppressionList((prev) => {
          const existingKeys = new Set(prev.map((p) => `${p.phone}-${p.source}`));
          const toAdd = newEntries.filter((e) => !existingKeys.has(`${e.phone}-${e.source}`));
          const updated = [...prev, ...toAdd];
          if (typeof window !== "undefined") {
            try {
              localStorage.setItem("talkflow_suppression_entries", JSON.stringify(updated));
            } catch (e) {
              // Fallback
            }
          }
          return updated;
        });

        const newBatch = {
          id: batchId,
          name: name,
          source: name,
          columns: headers,
          totalCount: newEntries.length,
          createdAt: new Date().toISOString(),
          type: "csv",
        };

        setSuppressionBatches((prev) => {
          const map = {};
          prev.forEach((b) => { map[b.id] = b; });
          map[newBatch.id] = newBatch;
          const updated = Object.values(map);
          if (typeof window !== "undefined") {
            try {
              localStorage.setItem("talkflow_suppression_batches", JSON.stringify(updated));
            } catch (e) {
              // Fallback
            }
          }
          return updated;
        });
      }
    };

    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => processText(e.target.result);
      reader.readAsText(file);
    } else {
      const demoEntries = [
        { id: `dnc-${Date.now()}-1`, phone: "+1 (555) 234-5678", reason: reason || "Do Not Call", addedBy: "Admin", source: name, addedAt: new Date().toISOString(), status: "Suppressed", batchId },
      ];
      setSuppressionList((prev) => [...demoEntries, ...prev]);
      const newBatch = { id: batchId, name, source: name, columns: ["phone", "reason", "addedBy", "source"], totalCount: demoEntries.length, createdAt: new Date().toISOString(), type: "csv" };
      setSuppressionBatches((prev) => {
        const map = {};
        prev.forEach((b) => { map[b.id] = b; });
        map[newBatch.id] = newBatch;
        const updated = Object.values(map);
        if (typeof window !== "undefined") {
          try {
            localStorage.setItem("talkflow_suppression_batches", JSON.stringify(updated));
          } catch (e) {
            // Fallback
          }
        }
        return updated;
      });
    }

    if (file) {
      try {
        const formData = new FormData();
        formData.append("file", file);
        await apiFetch("/suppression/import", {
          method: "POST",
          body: formData,
        });
      } catch (err) {
        // Best-effort backend upload
      }
    }
  };

  // View imported batch after completion
  const handleViewImportedList = () => {
    // The commit selects the new job, so "View Lead List" opens that list. Fall
    // back to the registry when there is nothing selected (e.g. after a reset).
    navigateToAction(selectedBatch ? "list" : "all");
  };

  // Dynamic Summary Metrics based on lead statuses & dataset
  const totalCount = totalLeads;

  const qualifiedCount = useMemo(() => {
    if (!leads || leads.length === 0) return 0;
    const directMatch = leads.filter((l) => {
      const st = String(l.status || "").toLowerCase();
      return st.includes("qualified") || st.includes("sale") || (l.score && l.score >= 80);
    }).length;
    if (directMatch > 0) {
      const ratio = directMatch / leads.length;
      return Math.round(totalCount * ratio);
    }
    return 0;
  }, [leads, totalCount]);

  const convertedCount = useMemo(() => {
    if (!leads || leads.length === 0) return 0;
    const directMatch = leads.filter((l) => {
      const st = String(l.status || "").toLowerCase();
      return st.includes("converted") || st.includes("sale") || st.includes("won");
    }).length;
    if (directMatch > 0) {
      const ratio = directMatch / leads.length;
      return Math.round(totalCount * ratio);
    }
    return 0;
  }, [leads, totalCount]);

  const contactedCount = useMemo(() => {
    if (!leads || leads.length === 0) return 0;
    const directMatch = leads.filter((l) => {
      const st = String(l.status || "").toLowerCase();
      const lastContact = String(l.lastContacted || "").toLowerCase();
      return st.includes("contacted") || st.includes("called") || (lastContact && lastContact !== "—" && lastContact !== "none");
    }).length;
    if (directMatch > 0) {
      const ratio = directMatch / leads.length;
      return Math.round(totalCount * ratio);
    }
    return 0;
  }, [leads, totalCount]);

  // Selected lead for detail view
  const selectedLead = useMemo(() => {
    if (!activeLeadId) return leads[0] || null;
    return leads.find((l) => String(l.id).toLowerCase() === activeLeadId.toLowerCase()) || null;
  }, [leads, activeLeadId]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const filteredLeads = useMemo(() => {
    return leads
      .filter((lead) => {
        if (statusFilter !== "all" && lead.status.toLowerCase() !== statusFilter.toLowerCase()) {
          return false;
        }

        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const fullName = `${lead.firstName} ${lead.lastName}`.toLowerCase();
          const matchName = fullName.includes(q);
          const matchPhone = String(lead.phone).toLowerCase().includes(q);
          const matchEmail = String(lead.email).toLowerCase().includes(q);
          const matchCamp = String(lead.campaign).toLowerCase().includes(q);
          const matchId = String(lead.id).toLowerCase().includes(q);

          return matchName || matchPhone || matchEmail || matchCamp || matchId;
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
  }, [leads, searchQuery, statusFilter, sortField, sortAsc]);

  const handleAddLead = async (e) => {
    e.preventDefault();
    if (!newFirstName.trim() || !newPhone.trim()) return;

    const payload = {
      firstName: newFirstName.trim(),
      lastName: newLastName.trim(),
      phone: newPhone.trim(),
      email: newEmail.trim() || null,
      state: newState,
      status: "new",
    };

    try {
      const res = await apiFetch("/leads", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const body = await res.json();
        if (body?.data) {
          setLeads((prev) => [body.data, ...prev]);
          setTotalLeads((prev) => prev + 1);
        }
      }
    } catch (err) {
      const fallbackObj = {
        id: `LEAD-${Date.now().toString().slice(-4)}`,
        ...payload,
        createdAt: new Date().toISOString(),
      };
      setLeads((prev) => [fallbackObj, ...prev]);
    }

    setNewFirstName("");
    setNewLastName("");
    setNewPhone("");
    setNewEmail("");
    setIsAddModalOpen(false);
  };

  return {
    viewMode,
    leads,
    setLeads,
    batches,
    activeCampaigns,
    selectedBatch,
    batchColumns,
    handleSelectBatch,
    handleAssignCampaign,
    handleUpdateVicidialList,
    handleToggleVicidialRun,
    vicidialBusyBatchId,
    vicidialError,
    batchError,
    suppressionList,
    suppressionBatches,
    selectedSuppressionBatch,
    handleSelectSuppressionBatch,
    handleClearSelectedSuppressionBatch,
    handleDeleteSuppressionBatch,
    isSuppressionImportModalOpen,
    setIsSuppressionImportModalOpen,
    handleImportSuppressionFileSubmit,
    searchQuery,
    setSearchQuery: handleSearchChange,
    statusFilter,
    setStatusFilter: handleStatusFilterChange,
    sortField,
    sortAsc,
    page,
    pageSize,
    totalLeads,
    totalPages,
    handleNextPage,
    handlePrevPage,
    handlePageSizeChange,
    isAddModalOpen,
    setIsAddModalOpen,
    newFirstName,
    setNewFirstName,
    newLastName,
    setNewLastName,
    newPhone,
    setNewPhone,
    newEmail,
    setNewEmail,
    newCampaign,
    setNewCampaign,
    newStatus,
    setNewStatus,
    newState,
    setNewState,
    importStep,
    setImportStep,
    uploadedFileName,
    importError,
    importBusy,
    detectedCount,
    importColumns,
    columnMapping,
    importValidation,
    importResult,
    importCampaignId,
    setImportCampaignId,
    importVicidialListId,
    setImportVicidialListId,
    activeCampaigns,
    importTargetFields: IMPORT_TARGET_FIELDS,
    importCustomField: IMPORT_CUSTOM_FIELD,
    importSkipColumn: IMPORT_SKIP_COLUMN,
    totalCount,
    qualifiedCount,
    convertedCount,
    contactedCount,
    selectedLead,
    filteredLeads,
    navigateToAction,
    handleSort,
    handleAddLead,
    handleFileUpload,
    handleColumnMappingChange,
    handleValidateMapping,
    handleStartImport,
    handleViewImportedList,
    handleDeleteBatch,
    handleClearSelectedBatch,
    handleResetImportWizard,
  };
}