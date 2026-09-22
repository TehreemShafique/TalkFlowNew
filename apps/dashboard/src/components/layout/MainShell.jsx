"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import Sidebar from "./Sidebar";
import TopNavbar from "./TopNavbar";
import IncomingTransferBanner from "./IncomingTransferBanner";
import { FilterProvider, useAuth } from "@/context";
import { NAVIGATION_CONFIG, getRoleKey } from "@/config/navigation";
import { ProtectedRoute, PendingGuard } from "@/components/auth";
import { LoadingSpinner } from "@/components/ui";

// Dynamic View Imports with Code Splitting & Loading Fallbacks
const ViewSkeleton = () => (
  <div className="flex min-h-[400px] w-full items-center justify-center py-12">
    <LoadingSpinner size="lg" />
  </div>
);

const DashboardView = dynamic(() => import("@/components/dashboard/DashboardView"), { loading: ViewSkeleton });
const CampaignsView = dynamic(() => import("@/components/campaigns/CampaignsView"), { loading: ViewSkeleton });
const LeadsView = dynamic(() => import("@/components/leads/LeadsView"), { loading: ViewSkeleton });
const CallsView = dynamic(() => import("@/components/calls/CallsView"), { loading: ViewSkeleton });
const TransfersView = dynamic(() => import("@/components/transfers/TransfersView"), { loading: ViewSkeleton });
const VerifierView = dynamic(() => import("@/components/verifier/VerifierView"), { loading: ViewSkeleton });
const QaView = dynamic(() => import("@/components/qa/QaView"), { loading: ViewSkeleton });
const ScriptsView = dynamic(() => import("@/components/call-scripts/ScriptsView"), { loading: ViewSkeleton });
const SystemView = dynamic(() => import("@/components/system/SystemView"), { loading: ViewSkeleton });
const AnalyticsView = dynamic(() => import("@/components/analytics/AnalyticsView"), { loading: ViewSkeleton });
const RecordingView = dynamic(() => import("@/components/recording/RecordingView"), { loading: ViewSkeleton });
const AuditLogsView = dynamic(() => import("@/components/audit/AuditLogsView"), { loading: ViewSkeleton });
const UsersView = dynamic(() => import("@/components/users/UsersView"), { loading: ViewSkeleton });
const SettingsView = dynamic(() => import("@/components/settings/SettingsView"), { loading: ViewSkeleton });
const ProfileView = dynamic(() => import("@/components/profile/ProfileView"), { loading: ViewSkeleton });

export default function MainShell({ initialTab, initialAction }) {
  const [activeTab, setActiveTab] = useState(initialTab || "dashboard");
  const [activeAction, setActiveAction] = useState(initialAction || null);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("talkflow_sidebar_collapsed") === "true";
    }
    return false;
  });
  const { role } = useAuth();
  const roleKey = getRoleKey(role);

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      if (typeof window !== "undefined") {
        localStorage.setItem("talkflow_sidebar_collapsed", String(next));
      }
      return next;
    });
  };

  // Role-based navigation guard: any active tab (from URL, search, or state)
  // not permitted for the current role falls back to the dashboard view.
  const canonicalTab =
    activeTab === "integrations" ? "system" : activeTab === "reports" ? "analytics" : activeTab;
  const allowedTab = NAVIGATION_CONFIG.find((item) => item.id === canonicalTab);
  const isTabAllowed = allowedTab && allowedTab.roles.includes(roleKey);
  const viewTab = isTabAllowed ? activeTab : "dashboard";
  const viewAction = isTabAllowed ? activeAction : null;

  // Synchronize URL path & query parameters on load
  useEffect(() => {
    if (typeof window !== "undefined") {
      const pathname = window.location.pathname;
      const searchParams = new URLSearchParams(window.location.search);
      const queryTab = searchParams.get("tab");

      if (queryTab) {
        setActiveTab(queryTab);
      } else {
        const pathSegments = pathname.split("/").filter(Boolean);
        if (pathSegments.length > 0) {
          if (pathSegments[0] === "dashboard") {
            const subTab = pathSegments[1];
            const action = pathSegments.length > 2 ? pathSegments.slice(2).join("/") : null;
            if (subTab) {
              setActiveTab(subTab);
              setActiveAction(action);
            } else {
              setActiveTab("dashboard");
              setActiveAction(null);
            }
          } else {
            setActiveTab(pathSegments[0]);
            setActiveAction(pathSegments.length > 1 ? pathSegments.slice(1).join("/") : null);
          }
        }
      }
    }
  }, []);

  // Update browser URL bar when active tab or action changes
  const handleTabChange = (tabId, action = null) => {
    setActiveTab(tabId);
    setActiveAction(action);
    if (typeof window !== "undefined") {
      let newPath = tabId === "dashboard" ? "/dashboard" : `/${tabId}`;
      if (action) {
        newPath += `/${action}`;
      }
      window.history.pushState({ tab: tabId, action }, "", newPath);
    }
  };

  const handleActionChange = (action) => {
    handleTabChange(viewTab, action);
  };

  return (
    <ProtectedRoute>
      <PendingGuard>
      <FilterProvider>
        <div className="flex min-h-screen w-full bg-neutral-100 text-neutral-900 transition-colors duration-200 dark:bg-[#000000] dark:text-neutral-100 font-sans">
          {/* 1. Left-Side Navigation Sidebar */}
          <Sidebar
            activeTab={viewTab}
            activeAction={viewAction}
            setActiveTab={(t) => handleTabChange(t, null)}
            onNavigate={(t, a) => handleTabChange(t, a)}
            isMobileOpen={isMobileSidebarOpen}
            onCloseMobile={() => setIsMobileSidebarOpen(false)}
            isCollapsed={isSidebarCollapsed}
            onToggleCollapse={handleToggleSidebar}
          />

          {/* 2. Main Workspace Display Area */}
          <div className="flex flex-1 flex-col overflow-x-hidden min-w-0">
            <TopNavbar
              onToggleMobileSidebar={() => setIsMobileSidebarOpen((prev) => !prev)}
              onToggleDesktopSidebar={handleToggleSidebar}
              isSidebarCollapsed={isSidebarCollapsed}
              onNavigate={(t, a) => handleTabChange(t, a)}
            />

            {/* Persistent Incoming Transfer Banner across ALL routes (Shell Requirement 5) */}
            <IncomingTransferBanner
              onNavigate={(t, a) => handleTabChange(t, a)}
            />

            {viewTab === "dashboard" && <DashboardView />}
            {viewTab === "campaigns" && (
              <CampaignsView
                initialAction={viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {viewTab === "leads" && (
              <LeadsView
                initialAction={viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {viewTab === "calls" && (
              <CallsView
                initialAction={viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {viewTab === "transfers" && (
              <TransfersView
                initialAction={viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {viewTab === "verifier" && (
              <VerifierView
                initialAction={viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {viewTab === "qa" && (
              <QaView
                initialAction={viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {viewTab === "scripts" && (
              <ScriptsView
                initialAction={viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {(viewTab === "system" || viewTab === "integrations") && (
              <SystemView
                initialAction={viewTab === "integrations" && !viewAction ? "integrations" : viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {(viewTab === "analytics" || viewTab === "reports") && (
              <AnalyticsView
                initialAction={viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {viewTab === "recording" && <RecordingView />}
            {viewTab === "audit_logs" && <AuditLogsView />}
            {viewTab === "users" && (
              <UsersView
                initialAction={viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {viewTab === "settings" && (
              <SettingsView
                initialAction={viewAction}
                onActionChange={handleActionChange}
              />
            )}
            {viewTab === "profile" && <ProfileView />}
          </div>
        </div>
      </FilterProvider>
      </PendingGuard>
    </ProtectedRoute>
  );
}
