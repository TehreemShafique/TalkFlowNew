"use client";

import { ListFilter, UploadCloud, ShieldAlert } from "lucide-react";

export default function LeadsSubtabsBar({ viewMode, onNavigate }) {
  const subtabs = [
    { id: "all", label: "Lead List", icon: ListFilter },
    { id: "import", label: "Import wizard", icon: UploadCloud },
    { id: "suppression", label: "Suppression list (DNC)", icon: ShieldAlert },
  ];

  return (
    <div className="flex items-center gap-1 overflow-x-auto rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0d0d0d] p-1.5 shadow-xs">
      {subtabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = tab.id === "all" ? (viewMode === "all" || viewMode === "list") : viewMode === tab.id;

        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onNavigate(tab.id)}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition-all duration-150 ${
              isActive
                ? "bg-blue-600 text-white dark:bg-[#253246] dark:text-blue-300 shadow-xs"
                : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 hover:text-neutral-900 dark:hover:bg-[#151518] dark:hover:text-white"
            }`}
          >
            <Icon className={`h-3.5 w-3.5 ${isActive ? "text-white dark:text-blue-300" : "opacity-70"}`} />
            <span>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}