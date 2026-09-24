"use client";

import { useState, useMemo, useEffect } from "react";
import { apiFetch } from "@/lib/api";

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

  // Helpers for local persistence
  const getStoredBatches = () => {
    if (typeof window === "undefined") return null;
    try {
      const saved = localStorage.getItem("talkflow_lead_batches");
      if (saved) return JSON.parse(saved);
    } catch (err) {
      // Fallback
    }
    return null;
  };

  const getDeletedBatchIds = () => {
    if (typeof window === "undefined") return new Set();
    try {
      const saved = localStorage.getItem("talkflow_deleted_batches");
      if (saved) return new Set(JSON.parse(saved));
    } catch (err) {
      // Fallback
    }
    return new Set();
  };

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

  // State datasets - initialize completely empty (no dummy data)
  const [leads, setLeads] = useState([]);
  const [batches, setBatches] = useState(() => {
    const stored = getStoredBatches();
    const deleted = getDeletedBatchIds();
    if (stored && Array.isArray(stored)) {
      return stored.filter((b) => !deleted.has(String(b.id)));
    }
    return [];
  });

  const [activeCampaigns, setActiveCampaigns] = useState([]);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [batchColumns, setBatchColumns] = useState([]);

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

  // Load Active Campaigns for batch dropdown assignment
  useEffect(() => {
    async function loadCampaigns() {
      try {
        const res = await apiFetch("/campaigns");
        if (res.ok) {
          const body = await res.json();
          if (body?.data && Array.isArray(body.data)) {
            setActiveCampaigns(body.data);
          }
        }
      } catch (err) {
        // Fallback
      }
    }
    loadCampaigns();
  }, []);

  // Load Lead Batches / Files Registry
  const loadBatches = async () => {
    try {
      const deletedIds = getDeletedBatchIds();
      const res = await apiFetch("/leads/batches");
      if (res.ok) {
        const body = await res.json();
        if (body?.data && Array.isArray(body.data)) {
          const validBackendBatches = body.data.filter((b) => !deletedIds.has(String(b.id)));
          setBatches((prev) => {
            const storedUserBatches = prev.filter(
              (p) => p.id.startsWith("batch-") && !deletedIds.has(String(p.id))
            );
            const merged = [...validBackendBatches, ...storedUserBatches];
            if (typeof window !== "undefined") {
              localStorage.setItem("talkflow_lead_batches", JSON.stringify(merged));
            }
            return merged;
          });
        }
      }
    } catch (err) {
      // Fallback
    }
  };

  useEffect(() => {
    loadBatches();
  }, []);

  const [parsedLeadsBatch, setParsedLeadsBatch] = useState([]);

  // Fetch real leads & suppression entries from backend API
  useEffect(() => {
    async function loadData() {
      try {
        if (selectedBatch?.parsedLeads && selectedBatch.parsedLeads.length > 0) {
          setLeads(selectedBatch.parsedLeads);
          setTotalLeads(selectedBatch.parsedLeads.length);
          setTotalPages(Math.ceil(selectedBatch.parsedLeads.length / pageSize));
          return;
        }

        const queryParams = new URLSearchParams({
          page: String(page),
          page_size: String(pageSize),
        });
        if (statusFilter && statusFilter !== "all") {
          queryParams.set("status", statusFilter);
        }
        if (searchQuery.trim()) {
          queryParams.set("search", searchQuery.trim());
        }
        if (selectedBatch?.id && !selectedBatch.id.startsWith("batch-")) {
          queryParams.set("source", String(selectedBatch.id));
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

    // 1. Scan lead batches (including parsedLeads from imports like LIST_1011_20260922-164919)
    batches.forEach((batch) => {
      const listName = batch.fileName || batch.file_name || batch.name || batch.id;
      const batchId = `supp-batch-${listName.toLowerCase().replace(/[^a-z0-9]/g, "-")}`;
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
              name: listName,
              source: listName,
              totalCount: 0,
              columns: batchCols,
              createdAt: batch.createdAt || new Date().toISOString(),
              type: "auto_extracted",
            };
          }

          if (!dncEntries.some((e) => e.phone === l.phone && e.source === listName)) {
            dncBatchesMap[batchId].totalCount += 1;
            dncEntries.push({
              id: `dnc-${l.id || Math.random()}-${batchId}`,
              phone: l.phone,
              reason: l.reason || "Lead Import DNC",
              addedBy: "System (Lead Auto-Filter)",
              source: listName,
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

    if (batch?.parsedLeads && Array.isArray(batch.parsedLeads) && batch.parsedLeads.length > 0) {
      setLeads(batch.parsedLeads);
      setTotalLeads(batch.parsedLeads.length);
      setTotalPages(Math.ceil(batch.parsedLeads.length / pageSize));
    } else if (leads.length === 0) {
      setLeads([]);
      setTotalLeads(0);
      setTotalPages(1);
    }

    setPage(1);
    navigateToAction("list");
  };

  const handleDeleteBatch = async (batchId) => {
    if (typeof window !== "undefined") {
      try {
        const deleted = getDeletedBatchIds();
        deleted.add(String(batchId));
        localStorage.setItem("talkflow_deleted_batches", JSON.stringify(Array.from(deleted)));
      } catch (err) {
        // Fallback
      }
    }

    setBatches((prev) => {
      const updated = prev.filter((b) => b.id !== batchId);
      if (typeof window !== "undefined") {
        localStorage.setItem("talkflow_lead_batches", JSON.stringify(updated));
      }
      return updated;
    });

    if (selectedBatch?.id === batchId) {
      setSelectedBatch(null);
      setBatchColumns([]);
      setLeads([]);
      setTotalLeads(0);
      setTotalPages(1);
    }

    try {
      await apiFetch(`/leads/batches/${batchId}`, {
        method: "DELETE",
      });
    } catch (err) {
      // Best effort deletion
    }
  };

  const handleResetImportWizard = () => {
    setImportStep(1);
    setUploadedFileName(null);
    setCustomListName("");
    setImportProgress(0);
    setImportError(null);
    setDetectedCount(0);
    setCsvHeaders([]);
    setSampleRow({});
    setParsedLeadsBatch([]);
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

  const handleAssignCampaign = async (batchId, campaignId) => {
    setBatches((prev) => {
      const updated = prev.map((b) =>
        b.id === batchId ? { ...b, campaignId, campaign_id: campaignId } : b
      );
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("talkflow_lead_batches", JSON.stringify(updated));
        } catch (err) {}
      }
      return updated;
    });

    try {
      await apiFetch(`/leads/batches/${batchId}/campaign`, {
        method: "PATCH",
        body: JSON.stringify({ campaign_id: campaignId }),
      });
      loadBatches();
    } catch (err) {
      // Best effort
    }
  };

  const handleStatusFilterChange = (st) => {
    setStatusFilter(st);
    setPage(1);
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

  // Import Wizard State & Validation
  const [importStep, setImportStep] = useState(1);
  const [uploadedFileName, setUploadedFileName] = useState(null);
  const [customListName, setCustomListName] = useState("");
  const [importProgress, setImportProgress] = useState(0);
  const [importError, setImportError] = useState(null);
  const [detectedCount, setDetectedCount] = useState(0);
  const [csvHeaders, setCsvHeaders] = useState([]);
  const [sampleRow, setSampleRow] = useState({});

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImportError(null);
    setUploadedFileName(file.name);
    setCustomListName(file.name.replace(/\.[^/.]+$/, ""));

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const text = event.target.result;
        const lines = text.split(/\r\n|\n/).filter((l) => l.trim().length > 0);
        if (lines.length < 2) {
          setImportError("The uploaded CSV file is empty or missing data rows.");
          return;
        }

        let delimiter = ",";
        if (lines[0].includes("\t")) {
          delimiter = "\t";
        } else if (lines[0].includes(";")) {
          delimiter = ";";
        } else if (!lines[0].includes(",") && /\s{2,}|\s+/.test(lines[0])) {
          delimiter = /\s+/;
        }

        const splitLine = (line) => {
          if (typeof delimiter === "string") {
            return line.split(delimiter).map((v) => v.trim().replace(/^"|"$/g, ""));
          }
          return line.trim().split(delimiter).map((v) => v.trim().replace(/^"|"$/g, ""));
        };

        const headers = splitLine(lines[0]);

        let phoneIdx = headers.findIndex((h) => !/code|dial_code|country/i.test(h) && /phone_number|mobile_number|cell_number|phone|mobile|cell|contact|tele|number/i.test(h));
        if (phoneIdx === -1) {
          phoneIdx = headers.findIndex((h) => /phone|mobile|cell|contact|tele|number|num/i.test(h));
        }
        if (phoneIdx === -1) {
          const sampleVals = splitLine(lines[1] || "");
          phoneIdx = sampleVals.findIndex((v) => /\d{5,}/.test(String(v)));
          if (phoneIdx === -1) phoneIdx = 0;
        }

        const rowCount = lines.length - 1;
        setDetectedCount(rowCount);
        setCsvHeaders(headers);

        const sampleValues = splitLine(lines[1]);
        const sampleObj = {};
        headers.forEach((h, idx) => {
          sampleObj[h] = sampleValues[idx] || "";
        });
        setSampleRow(sampleObj);

        // Parse rows into parsedLeadsBatch
        const parsedRows = [];
        const firstIdx = headers.findIndex((h) => /first/i.test(h));
        const lastIdx = headers.findIndex((h) => /last/i.test(h));
        const emailIdx = headers.findIndex((h) => /mail/i.test(h));
        const stateIdx = headers.findIndex((h) => /state|province/i.test(h));
        const statusIdx = headers.findIndex((h) => /^status$|^dnc$|^suppressed$/i.test(h));
        const dncIdx = headers.findIndex((h) => /^dnc$|^suppressed$/i.test(h));

        for (let i = 1; i < lines.length && i <= 2000; i++) {
          const values = splitLine(lines[i]);
          if (values.length === 0) continue;
          const rowObj = {};
          headers.forEach((h, idx) => {
            rowObj[h] = values[idx] !== undefined ? values[idx] : "";
          });

          const phoneVal = values[phoneIdx] || values[0] || "—";
          const firstVal = (firstIdx !== -1 ? values[firstIdx] : "") || `Lead #${i}`;
          const lastVal = (lastIdx !== -1 ? values[lastIdx] : "") || "";
          const emailVal = (emailIdx !== -1 ? values[emailIdx] : "") || "—";
          const stateVal = (stateIdx !== -1 ? values[stateIdx] : "") || "US";
          let rawStatus = (statusIdx !== -1 ? values[statusIdx] : "") || "New";

          // DNC Check inside CSV row
          const dncVal = (dncIdx !== -1 ? values[dncIdx] : "").toString().toLowerCase();
          const rowStr = values.join(" ").toLowerCase();
          if (
            dncVal === "true" ||
            dncVal === "yes" ||
            dncVal === "1" ||
            dncVal === "dnc" ||
            rowStr.includes("dnc") ||
            rowStr.includes("do not call") ||
            rowStr.includes("opt-out") ||
            rowStr.includes("suppressed")
          ) {
            rawStatus = "DNC";
            rowObj.dnc = true;
            rowObj.status = "DNC";
          }

          parsedRows.push({
            id: values[0] || `LEAD-${1000 + i}`,
            firstName: firstVal,
            lastName: lastVal,
            phone: phoneVal,
            email: emailVal,
            state: stateVal,
            campaign: customListName || file.name,
            score: 80,
            status: rawStatus ? (rawStatus.charAt(0).toUpperCase() + rawStatus.slice(1).toLowerCase()) : "New",
            createdAt: new Date().toLocaleDateString(),
            lastContacted: "—",
            customFields: rowObj,
          });
        }
        setParsedLeadsBatch(parsedRows);

        setImportStep(2);
      } catch (err) {
        setImportError("Failed to parse CSV file. Please ensure it is a valid UTF-8 CSV file.");
      }
    };
    reader.readAsText(file);
  };

  const handleStartImport = () => {
    setImportStep(3);
    setImportProgress(25);
    setTimeout(() => setImportProgress(65), 500);
    setTimeout(() => {
      setImportProgress(100);

      const listTitle = customListName.trim() || uploadedFileName || "Imported Lead List";
      const count = detectedCount || (parsedLeadsBatch.length > 0 ? parsedLeadsBatch.length : 500);

      const newBatchObj = {
        id: `batch-${Date.now()}`,
        fileName: listTitle,
        file_name: listTitle,
        totalRows: count,
        total_rows: count,
        importedRows: count,
        imported_rows: count,
        columns: csvHeaders.length > 0 ? csvHeaders : ["phone", "first_name", "last_name", "state"],
        parsedLeads: parsedLeadsBatch,
        campaignId: null,
        campaignName: "Unassigned",
        createdAt: new Date().toISOString(),
      };

      setBatches((prev) => {
        const updated = [newBatchObj, ...prev];
        if (typeof window !== "undefined") {
          try {
            localStorage.setItem("talkflow_lead_batches", JSON.stringify(updated));
          } catch (err) {
            // Fallback
          }
        }
        return updated;
      });

      if (parsedLeadsBatch.length > 0) {
        setLeads(parsedLeadsBatch);
        setTotalLeads(parsedLeadsBatch.length);
        setTotalPages(Math.ceil(parsedLeadsBatch.length / pageSize));
      }
      setSelectedBatch(newBatchObj);
      setBatchColumns(newBatchObj.columns);

      // Extract DNC entries for this newly imported file with the exact SAME name & dynamic columns
      if (parsedLeadsBatch && parsedLeadsBatch.length > 0) {
        const dncLeads = parsedLeadsBatch.filter((l) => {
          const st = (l.status || "").toLowerCase();
          const dncVal = String(l.customFields?.dnc || l.customFields?.suppressed || "").toLowerCase();
          return st.includes("dnc") || st.includes("suppress") || st.includes("opt-out") || st.includes("opt_out") || dncVal === "true" || dncVal === "yes" || dncVal === "1";
        });

        if (dncLeads.length > 0) {
          const dncBatchId = `supp-batch-${listTitle.toLowerCase().replace(/[^a-z0-9]/g, "-")}`;
          const extractedEntries = dncLeads.map((l, idx) => ({
            id: `dnc-auto-${Date.now()}-${idx}`,
            phone: l.phone,
            reason: l.reason || "Lead Import DNC",
            addedBy: "System (Lead Auto-Filter)",
            source: listTitle,
            addedAt: new Date().toISOString(),
            status: "Suppressed",
            batchId: dncBatchId,
            customFields: l.customFields || l,
          }));

          setSuppressionList((prev) => {
            const existingKeys = new Set(prev.map((p) => `${p.phone}-${p.source}`));
            const toAdd = extractedEntries.filter((e) => !existingKeys.has(`${e.phone}-${e.source}`));
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

          const newSuppBatch = {
            id: dncBatchId,
            name: listTitle,
            source: listTitle,
            columns: csvHeaders.length > 0 ? csvHeaders : ["phone", "first_name", "last_name", "status"],
            totalCount: extractedEntries.length,
            createdAt: new Date().toISOString(),
            type: "auto_extracted",
          };

          setSuppressionBatches((prev) => {
            const map = {};
            prev.forEach((b) => { map[b.id] = b; });
            map[newSuppBatch.id] = newSuppBatch;
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
      }
    }, 1200);
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
    navigateToAction("all");
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
    customListName,
    setCustomListName,
    importProgress,
    importError,
    detectedCount,
    csvHeaders,
    sampleRow,
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
    handleStartImport,
    handleViewImportedList,
    handleDeleteBatch,
    handleClearSelectedBatch,
    handleResetImportWizard,
  };
}