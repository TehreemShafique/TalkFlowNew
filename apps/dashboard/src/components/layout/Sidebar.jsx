"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import logoDark from "../../../public/logo-dark.png";
import logoLight from "../../../public/logo-light.png";
import {
  LayoutDashboard,
  Megaphone,
  FileText,
  Plug,
  BarChart3,
  Headphones,
  ClipboardList,
  Users,
  User,
  Settings,
  ChevronDown,
  ChevronRight,
  TrendingUp,
  UserPlus,
  ScrollText,
  Activity,
  Contact,
  UploadCloud,
  ShieldAlert,
  ListFilter,
  Plus,
  Sliders,
  GitFork,
  FileCode,
  ShieldCheck,
  PhoneCall,
  PhoneForwarded,
  Bot,
  Download,
  Target,
  Server,
  Mic,
  Volume2,
  Lock,
  UserCheck,
  History,
  X,
  PanelLeftClose,
} from "lucide-react";
import { NAVIGATION_CONFIG, getRoleKey } from "@/config/navigation";
import { useAuth, useTheme } from "@/context";

const ICON_MAP = {
  LayoutDashboard,
  Megaphone,
  FileText,
  Plug,
  BarChart3,
  Headphones,
  ClipboardList,
  Users,
  User,
  Settings,
  TrendingUp,
  UserPlus,
  ScrollText,
  Activity,
  Contact,
  UploadCloud,
  ShieldAlert,
  ListFilter,
  Sliders,
  ShieldCheck,
  PhoneCall,
  PhoneForwarded,
  Bot,
  Download,
  Target,
  Server,
  Mic,
  Volume2,
  Lock,
  UserCheck,
  History,
};

export default function Sidebar({
  activeTab,
  activeAction,
  setActiveTab,
  onNavigate,
  isMobileOpen,
  onCloseMobile,
  isCollapsed,
  onToggleCollapse,
}) {
  const { role, user } = useAuth();
  const { isDark } = useTheme();
  const rawRole = user?.role || user?.type || role || "MASTER_ADMIN";
  const roleKey = getRoleKey(rawRole);

  const [isCampaignsExpanded, setIsCampaignsExpanded] = useState(activeTab === "campaigns");
  const [isLeadsExpanded, setIsLeadsExpanded] = useState(activeTab === "leads");
  const [isQaExpanded, setIsQaExpanded] = useState(activeTab === "qa");
  const [isAnalyticsExpanded, setIsAnalyticsExpanded] = useState(
    activeTab === "analytics" || activeTab === "reports"
  );
  const [isSystemExpanded, setIsSystemExpanded] = useState(
    activeTab === "system" || activeTab === "integrations"
  );
  const [isSettingsExpanded, setIsSettingsExpanded] = useState(activeTab === "settings");
  const [isVerifierExpanded, setIsVerifierExpanded] = useState(activeTab === "verifier");

  // Keep expanded state in sync when activeTab changes
  useEffect(() => {
    if (activeTab === "campaigns") setIsCampaignsExpanded(true);
    if (activeTab === "leads") setIsLeadsExpanded(true);
    if (activeTab === "qa") setIsQaExpanded(true);
    if (activeTab === "analytics" || activeTab === "reports") setIsAnalyticsExpanded(true);
    if (activeTab === "system" || activeTab === "integrations") setIsSystemExpanded(true);
    if (activeTab === "settings") setIsSettingsExpanded(true);
    if (activeTab === "verifier") setIsVerifierExpanded(true);
  }, [activeTab]);

  const handleNavClick = (tabId, action = null) => {
    if (onNavigate) {
      onNavigate(tabId, action);
    } else if (setActiveTab) {
      setActiveTab(tabId);
    }
    if (onCloseMobile) {
      onCloseMobile();
    }
  };

  // Filter navigation items based on canonical role key per TalkFlow.md §7
  const filteredNavItems = NAVIGATION_CONFIG.filter((item) => {
    if (!item.roles || item.roles.length === 0) return true;
    return item.roles.includes(roleKey);
  }).map((item) => ({
    ...item,
    icon: ICON_MAP[item.icon] || LayoutDashboard,
    subtabs: item.subtabs
      ? item.subtabs.map((sub) => ({
          ...sub,
          icon: ICON_MAP[sub.icon] || FileText,
        }))
      : undefined,
  }));

  const sidebarContent = (
    <div className="flex h-full flex-col border-r border-neutral-200 bg-white text-neutral-700 transition-all duration-200 dark:border-[#141414] dark:bg-[#000000] dark:text-neutral-300">
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-center relative border-b border-neutral-200 px-2 py-2 dark:border-[#141414] bg-neutral-50/50 dark:bg-black overflow-hidden">
        <div className="flex flex-1 items-center justify-center w-full h-full min-w-0">
          <Image
            src={isDark ? logoDark : logoLight}
            alt="SmartBrains BPO Logo"
            className="w-[94%] h-full max-h-14 object-contain object-center scale-x-110 origin-center transition-all duration-200"
            priority
          />
        </div>

        {/* Close Button for Overlay Drawer (< 1024px) */}
        {onCloseMobile && (
          <button
            type="button"
            onClick={onCloseMobile}
            className="absolute right-2 rounded-lg p-1 text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        )}

        {/* Close Button for Desktop Sidebar Toggle (>= 1024px) */}
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            title="Close Sidebar"
            className="absolute right-2 rounded-lg p-1.5 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-white hidden lg:flex items-center justify-center transition-colors"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Role Scoped Indicator Badge */}
      <div className="px-4 py-2 border-b border-neutral-100 bg-neutral-50/80 dark:border-neutral-800 dark:bg-[#111113] flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
          Role Scope:
        </span>
        <span className="text-[11px] font-bold text-blue-600 dark:text-blue-400 truncate max-w-[130px]">
          {rawRole}
        </span>
      </div>

      {/* Navigation Links */}
      <div className="flex flex-1 flex-col gap-1 px-3 py-3 overflow-y-auto">
        {filteredNavItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            activeTab === item.id ||
            (item.id === "analytics" && activeTab === "reports") ||
            (item.id === "system" && activeTab === "integrations");

          if (item.hasSubtabs) {
            const isExpanded =
              item.id === "campaigns"
                ? isCampaignsExpanded
                : item.id === "leads"
                ? isLeadsExpanded
                : item.id === "qa"
                ? isQaExpanded
                : item.id === "analytics"
                ? isAnalyticsExpanded
                : item.id === "system"
                ? isSystemExpanded
                : item.id === "settings"
                ? isSettingsExpanded
                : item.id === "verifier"
                ? isVerifierExpanded
                : false;

            const toggleExpanded = () => {
              if (item.id === "campaigns") {
                if (isCampaignsExpanded) setIsCampaignsExpanded(false);
                else {
                  setIsCampaignsExpanded(true);
                  if (activeTab !== "campaigns") handleNavClick("campaigns", null);
                }
              } else if (item.id === "leads") {
                if (isLeadsExpanded) setIsLeadsExpanded(false);
                else {
                  setIsLeadsExpanded(true);
                  if (activeTab !== "leads") handleNavClick("leads", null);
                }
              } else if (item.id === "qa") {
                if (isQaExpanded) setIsQaExpanded(false);
                else {
                  setIsQaExpanded(true);
                  if (activeTab !== "qa") handleNavClick("qa", null);
                }
              } else if (item.id === "analytics") {
                if (isAnalyticsExpanded) setIsAnalyticsExpanded(false);
                else {
                  setIsAnalyticsExpanded(true);
                  if (activeTab !== "analytics" && activeTab !== "reports") handleNavClick("analytics", null);
                }
              } else if (item.id === "system") {
                if (isSystemExpanded) setIsSystemExpanded(false);
                else {
                  setIsSystemExpanded(true);
                  if (activeTab !== "system" && activeTab !== "integrations") handleNavClick("system", null);
                }
              } else if (item.id === "settings") {
                if (isSettingsExpanded) setIsSettingsExpanded(false);
                else {
                  setIsSettingsExpanded(true);
                  if (activeTab !== "settings") handleNavClick("settings", null);
                }
              } else if (item.id === "verifier") {
                if (isVerifierExpanded) setIsVerifierExpanded(false);
                else {
                  setIsVerifierExpanded(true);
                  if (activeTab !== "verifier") handleNavClick("verifier", null);
                }
              }
            };

            return (
              <div key={item.id} className="flex flex-col gap-1">
                {/* Main Tab Button with Dropdown Indicator */}
                <button
                  type="button"
                  onClick={toggleExpanded}
                  className={`flex w-full items-center justify-between rounded-lg px-3.5 py-2.5 text-xs font-semibold transition-all duration-150 ${
                    isActive
                      ? "bg-blue-50 text-blue-600 font-bold shadow-xs border border-blue-200 dark:border-white/10 dark:bg-[#1a2333] dark:text-blue-400"
                      : "text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#121215] dark:hover:text-white"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Icon
                      className={`h-4 w-4 shrink-0 ${
                        isActive
                          ? "text-blue-600 dark:text-blue-400"
                          : "text-neutral-400 dark:text-neutral-400"
                      }`}
                    />
                    <span className="truncate">{item.label}</span>
                  </div>

                  <div className="flex items-center shrink-0">
                    {isExpanded ? (
                      <ChevronDown className="h-3.5 w-3.5 text-neutral-400" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5 text-neutral-400" />
                    )}
                  </div>
                </button>

                {/* Subtabs Collapsible Dropdown List */}
                {isExpanded && (
                  <div className="ml-4 pl-3.5 border-l border-neutral-200 dark:border-neutral-800 flex flex-col gap-1 py-0.5">
                    {/* Option to go to main view (Omit for settings to avoid duplicate General tab) */}
                    {item.id !== "settings" && (
                      <button
                        type="button"
                        onClick={() => handleNavClick(item.id, null)}
                        className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                          isActive && (!activeAction || activeAction === "new" || activeAction === "list" || activeAction === "queue" || activeAction === "overview" || activeAction === "health")
                            ? "bg-blue-100/60 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-bold"
                            : "text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-[#141417]"
                        }`}
                      >
                        <span className="h-1.5 w-1.5 rounded-full bg-blue-500 shrink-0" />
                        <span className="truncate">
                          {item.id === "campaigns"
                            ? "All Campaigns"
                            : item.id === "leads"
                            ? "All Leads"
                            : item.id === "qa"
                            ? "QA review queue"
                            : item.id === "system"
                            ? "Service health"
                            : item.id === "verifier"
                            ? "Active workspace"
                            : "Business overview"}
                        </span>
                      </button>
                    )}

                    {item.subtabs.map((sub) => {
                      const SubIcon = sub.icon;
                      const isSubActive =
                        isActive &&
                        (activeAction === sub.id ||
                          (sub.id === "general" && (!activeAction || activeAction === "general")));

                      return (
                        <button
                          key={sub.id}
                          type="button"
                          onClick={() => handleNavClick(item.id, sub.id)}
                          className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                            isSubActive
                              ? "bg-blue-100/60 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-bold"
                              : "text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-[#141417]"
                          }`}
                        >
                          <SubIcon className="h-3.5 w-3.5 shrink-0 opacity-70" />
                          <span className="truncate">{sub.label}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => handleNavClick(item.id, null)}
              className={`flex w-full items-center gap-3 rounded-lg px-3.5 py-2.5 text-xs font-semibold transition-all duration-150 ${
                isActive
                  ? "bg-blue-50 text-blue-600 font-bold shadow-xs border border-blue-200 dark:border-white/10 dark:bg-[#1a2333] dark:text-blue-400"
                  : "text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-[#121215] dark:hover:text-white"
              }`}
            >
              <Icon
                className={`h-4 w-4 shrink-0 ${
                  isActive
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-neutral-400 dark:text-neutral-400"
                }`}
              />
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop & Tablet Responsive Sidebar */}
      <aside
        className={`hidden lg:flex flex-col shrink-0 min-h-screen transition-all duration-300 ease-in-out ${
          isCollapsed ? "w-0 overflow-hidden opacity-0 border-none pointer-events-none" : "w-16 xl:w-64 opacity-100"
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Overlay Drawer */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
            onClick={onCloseMobile}
          />
          <div className="relative flex w-72 max-w-full flex-1 flex-col z-50 bg-white dark:bg-[#09090b] shadow-2xl">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
