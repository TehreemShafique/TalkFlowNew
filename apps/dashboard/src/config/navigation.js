// TalkFlow Navigation Configuration per TalkFlow.md §7 (Navigation Model by Role)

// Canonical Role Keys:
// MASTER_ADMIN | CAMPAIGN_MANAGER | VERIFIER | QA | REPORTING_USER | DEVOPS_IT | DEVELOPER | VIEWER

export function getRoleKey(roleStr = "") {
  const str = String(roleStr || "").toLowerCase();
  if (
    str.includes("master") ||
    str.includes("super") ||
    str.includes("admin") ||
    str === "super_admin" ||
    str === "admin"
  ) {
    return "MASTER_ADMIN";
  }
  if (str.includes("campaign")) return "CAMPAIGN_MANAGER";
  if (str.includes("verifier") || str.includes("licensed")) return "VERIFIER";
  if (str.includes("qa")) return "QA";
  if (str.includes("reporting") || str.includes("analyst")) return "REPORTING_USER";
  if (str.includes("it") || str.includes("devops")) return "DEVOPS_IT";
  if (str.includes("developer")) return "DEVELOPER";
  return "MASTER_ADMIN";
}

export const NAVIGATION_CONFIG = [
  {
    id: "dashboard",
    label: "Dashboard",
    icon: "LayoutDashboard",
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER", "VERIFIER", "QA", "REPORTING_USER", "DEVOPS_IT", "DEVELOPER"],
  },
  {
    id: "leads",
    label: "Leads",
    icon: "Contact",
    hasSubtabs: true,
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER"],
    subtabs: [
      { id: "list", label: "Lead list", icon: "ListFilter" },
      { id: "import", label: "Import wizard", icon: "UploadCloud" },
      { id: "suppression", label: "Suppression list (DNC)", icon: "ShieldAlert" },
    ],
  },
  {
    id: "campaigns",
    label: "Campaigns",
    icon: "Megaphone",
    hasSubtabs: true,
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER", "QA", "REPORTING_USER"],
    subtabs: [
      { id: "performance", label: "Performance review", icon: "TrendingUp" },
      { id: "team", label: "Assign team", icon: "UserPlus" },
      { id: "scripts", label: "Active Scripts", icon: "ScrollText" },
      { id: "outcomes", label: "Live outcomes", icon: "Activity" },
    ],
  },
  {
    id: "scripts",
    label: "Scripts",
    icon: "FileText",
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER", "QA"],
  },
  {
    id: "calls",
    label: "Calls",
    icon: "PhoneCall",
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER", "VERIFIER", "QA", "REPORTING_USER", "DEVOPS_IT"],
  },
  {
    id: "transfers",
    label: "Transfers",
    icon: "PhoneForwarded",
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER", "VERIFIER", "QA"],
  },
  {
    id: "verifier",
    label: "Verifier Workspace",
    icon: "UserCheck",
    hasSubtabs: true,
    roles: ["MASTER_ADMIN", "VERIFIER"],
    subtabs: [{ id: "history", label: "Verification history", icon: "History" }],
  },
  {
    id: "qa",
    label: "QA",
    icon: "ShieldCheck",
    hasSubtabs: true,
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER", "QA", "REPORTING_USER"],
    subtabs: [
      { id: "review", label: "Review workspace", icon: "ShieldCheck" },
      { id: "scorecards", label: "Scorecard templates", icon: "Sliders" },
      { id: "results", label: "QA results and trends", icon: "TrendingUp" },
      { id: "calibration", label: "Calibration sessions", icon: "Users" },
    ],
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: "BarChart3",
    hasSubtabs: true,
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER", "QA", "REPORTING_USER"],
    subtabs: [
      { id: "campaigns", label: "Daily campaign summary", icon: "Target" },
      { id: "scripts", label: "Script performance by version", icon: "FileText" },
      { id: "sources", label: "Lead source quality", icon: "ListFilter" },
      { id: "bot", label: "Bot performance", icon: "Bot" },
      { id: "compliance", label: "Compliance review", icon: "ShieldCheck" },
      { id: "performance", label: "AI latency / engineering metrics", icon: "Activity" },
      { id: "exports", label: "Export history & scheduled exports", icon: "Download" },
    ],
  },
  {
    id: "system",
    label: "System Health",
    icon: "Server",
    hasSubtabs: true,
    roles: ["MASTER_ADMIN", "DEVOPS_IT"],
    subtabs: [
      { id: "alerts", label: "Active and historical alerts", icon: "ShieldAlert" },
      { id: "integrations", label: "CRM, webhooks, dialer status", icon: "Plug" },
    ],
  },
  {
    id: "recording",
    label: "Recordings",
    icon: "Headphones",
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER", "VERIFIER", "QA"],
  },
  {
    id: "audit_logs",
    label: "Audit Logs",
    icon: "ClipboardList",
    roles: ["MASTER_ADMIN", "QA", "DEVOPS_IT"],
  },
  {
    id: "users",
    label: "Users & Roles",
    icon: "Users",
    roles: ["MASTER_ADMIN", "DEVOPS_IT"],
  },
  {
    id: "profile",
    label: "My Profile",
    icon: "User",
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER", "VERIFIER", "QA", "REPORTING_USER", "DEVOPS_IT", "DEVELOPER"],
  },
  {
    id: "settings",
    label: "Settings",
    icon: "Settings",
    hasSubtabs: true,
    roles: ["MASTER_ADMIN", "CAMPAIGN_MANAGER", "QA", "DEVOPS_IT"],
    subtabs: [
      { id: "general", label: "General", icon: "Sliders" },
      { id: "telephony", label: "Telephony", icon: "PhoneCall" },
      { id: "stt", label: "Speech-to-Text (STT)", icon: "Mic" },
      { id: "tts", label: "Text-to-Speech (TTS)", icon: "Volume2" },
      { id: "llm", label: "LLM Engine", icon: "Bot" },
      { id: "qualification", label: "Eligibility Rules", icon: "ShieldCheck" },
      { id: "recordings", label: "Recordings Policy", icon: "Headphones" },
      { id: "compliance", label: "Compliance", icon: "ShieldAlert" },
      { id: "security", label: "Security", icon: "Lock" },
      { id: "users", label: "Users", icon: "Users" },
      { id: "roles", label: "Roles & Permissions", icon: "UserCheck" },
    ],
  },
];
