"use client";

import { useState, useMemo, useEffect } from "react";
import { INITIAL_LEADS, SUPPRESSION_LIST_DATA } from "@/data";
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

  const DEFAULT_INITIAL_BATCHES = [
    {
      id: "batch-101",
      fileName: "Medicare_Outbound_Q3_Leads.csv",
      file_name: "Medicare_Outbound_Q3_Leads.csv",
      totalRows: 2000,
      total_rows: 2000,
      importedRows: 2000,
      imported_rows: 2000,
      columns: ["phone", "first_name", "last_name", "state", "campaign", "status"],
      campaignId: null,
      campaignName: "Medicare Outbound",
      createdAt: new Date().toISOString(),
    },
    {
      id: "batch-102",
      fileName: "Final_Expense_Inbound_Sept.csv",
      file_name: "Final_Expense_Inbound_Sept.csv",
      totalRows: 500,
      total_rows: 500,
      importedRows: 500,
      imported_rows: 500,
      columns: ["phone", "first_name", "last_name", "state", "coverage_amount"],
      campaignId: null,
      campaignName: "Final Expense Inbound",
      createdAt: new Date(Date.now() - 86400000).toISOString(),
    },
  ];

  // State datasets
  const [leads, setLeads] = useState(INITIAL_LEADS);
  const [batches, setBatches] = useState(() => {
    const stored = getStoredBatches();
    const deleted = getDeletedBatchIds();
    if (stored && Array.isArray(stored)) {
      return stored.filter((b) => !deleted.has(String(b.id)));
    }
    return DEFAULT_INITIAL_BATCHES.filter((b) => !deleted.has(String(b.id)));
  });
  const [activeCampaigns, setActiveCampaigns] = useState([]);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [batchColumns, setBatchColumns] = useState([]);
  const [suppressionList, setSuppressionList] = useState(SUPPRESSION_LIST_DATA);

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalLeads, setTotalLeads] = useState(INITIAL_LEADS.length);
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
              campaign: l.campaignName || l.campaign_name || "Medicare Outbound",
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
            setLeads(INITIAL_LEADS);
            setTotalLeads(INITIAL_LEADS.length);
            setTotalPages(Math.ceil(INITIAL_LEADS.length / pageSize));
          }
        }
      } catch (err) {
        // Fallback
      }

      try {
        const dncRes = await apiFetch("/suppression");
        if (dncRes.ok) {
          const body = await dncRes.json();
          if (body?.data && Array.isArray(body.data)) {
            setSuppressionList(body.data);
          }
        }
      } catch (err) {
        // Fallback
      }
    }
    loadData();
  }, [page, pageSize, statusFilter, searchQuery, selectedBatch]);

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
      setLeads(INITIAL_LEADS);
      setTotalLeads(INITIAL_LEADS.length);
      setTotalPages(Math.ceil(INITIAL_LEADS.length / pageSize));
    }

    setPage(1);
    navigateToAction("list");
  };

  const handleDeleteBatch = async (batchId) => {
    // Record deletion in LocalStorage so deleted item NEVER reappears on refresh
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
      setLeads(INITIAL_LEADS);
      setTotalLeads(INITIAL_LEADS.length);
      setTotalPages(Math.ceil(INITIAL_LEADS.length / pageSize));
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
    setLeads(INITIAL_LEADS);
    setTotalLeads(INITIAL_LEADS.length);
    setTotalPages(Math.ceil(INITIAL_LEADS.length / pageSize));
    navigateToAction("all");
  };

  const handleAssignCampaign = async (batchId, campaignId) => {
    setBatches((prev) =>
      prev.map((b) => (b.id === batchId ? { ...b, campaignId, campaign_id: campaignId } : b))
    );
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
  const [newCampaign, setNewCampaign] = useState("Med Fronter");
  const [newStatus, setNewStatus] = useState("New");
  const [newState, setNewState] = useState("CA");

  // Add DNC Modal State
  const [isDncModalOpen, setIsDncModalOpen] = useState(false);
  const [newDncPhone, setNewDncPhone] = useState("");
  const [newDncReason, setNewDncReason] = useState("Customer Request");

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

        // Auto-detect delimiter (\t, ;, ,, or whitespace \s+)
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

        const hasPhoneColumn = headers.some((h) =>
          /phone|mobile|cell|contact|number|tele/i.test(h)
        );

        if (!hasPhoneColumn) {
          setImportError(
            `Invalid File format: "${file.name}" contains non-lead data (Detected columns: ${headers.slice(0, 4).join(", ")}...). A valid lead sheet must contain phone numbers.`
          );
          return;
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
        const phoneIdx = headers.findIndex((h) => /phone|mobile|cell|contact|tele/i.test(h));
        const firstIdx = headers.findIndex((h) => /first/i.test(h));
        const lastIdx = headers.findIndex((h) => /last/i.test(h));
        const emailIdx = headers.findIndex((h) => /mail/i.test(h));
        const stateIdx = headers.findIndex((h) => /state|province/i.test(h));
        const statusIdx = headers.findIndex((h) => /^status$/i.test(h));

        for (let i = 1; i < lines.length && i <= 500; i++) {
          const values = splitLine(lines[i]);
          if (values.length === 0) continue;
          const rowObj = {};
          headers.forEach((h, idx) => {
            rowObj[h] = values[idx] || "";
          });

          const phoneVal = (phoneIdx !== -1 ? values[phoneIdx] : values[10]) || "—";
          const firstVal = (firstIdx !== -1 ? values[firstIdx] : values[12]) || `Lead #${i}`;
          const lastVal = (lastIdx !== -1 ? values[lastIdx] : values[14]) || "";
          const emailVal = (emailIdx !== -1 ? values[emailIdx] : values[27]) || "—";
          const stateVal = (stateIdx !== -1 ? values[stateIdx] : values[19]) || "US";
          const rawStatus = (statusIdx !== -1 ? values[statusIdx] : values[3]) || "New";

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
    }, 1200);
  };

  // View imported batch after completion
  const handleViewImportedList = () => {
    navigateToAction("all");
  };

  // Summary Metrics
  const totalCount = totalLeads;
  const qualifiedCount = leads.filter((l) => l.status === "Qualified").length;
  const convertedCount = leads.filter((l) => l.status === "Converted").length;
  const contactedCount = leads.filter((l) => l.status === "Contacted").length;

  // Selected lead for detail view
  const selectedLead = useMemo(() => {
    if (!activeLeadId) return leads[0] || null;
    return leads.find((l) => String(l.id).toLowerCase() === activeLeadId.toLowerCase()) || leads[0];
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

  const handleAddDnc = async (e) => {
    e.preventDefault();
    if (!newDncPhone.trim()) return;

    const payload = {
      phone: newDncPhone.trim(),
      reason: "internal_dnc",
    };

    try {
      const res = await apiFetch("/suppression", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const body = await res.json();
        if (body?.data) {
          setSuppressionList((prev) => [body.data, ...prev]);
        }
      }
    } catch (err) {
      const fallbackDnc = {
        id: `dnc-${Date.now().toString().slice(-3)}`,
        phone: newDncPhone.trim(),
        reason: newDncReason,
        addedAt: new Date().toISOString(),
      };
      setSuppressionList((prev) => [fallbackDnc, ...prev]);
    }

    setNewDncPhone("");
    setIsDncModalOpen(false);
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
    isDncModalOpen,
    setIsDncModalOpen,
    newDncPhone,
    setNewDncPhone,
    newDncReason,
    setNewDncReason,
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
    handleAddDnc,
    handleFileUpload,
    handleStartImport,
    handleViewImportedList,
    handleDeleteBatch,
    handleClearSelectedBatch,
    handleResetImportWizard,
  };
}