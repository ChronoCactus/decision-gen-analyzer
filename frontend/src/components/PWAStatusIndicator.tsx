"use client";

import { usePWAUpdateStatus, type PWAUpdateStatus } from "@/hooks/usePWAUpdateStatus";

interface PWAStatusIndicatorProps {
  showTooltip?: boolean;
}

/**
 * Visual indicator component showing PWA update status
 * - Green dot: Running latest version
 * - Yellow dot: Update available
 * - Red dot: Error checking for updates
 * - Gray dot: Checking for updates
 */
export function PWAStatusIndicator({ showTooltip = true }: PWAStatusIndicatorProps) {
  const { status, updateServiceWorker } = usePWAUpdateStatus();

  const getStatusColor = (status: PWAUpdateStatus): string => {
    switch (status) {
      case "current":
        return "bg-green-500";
      case "update-available":
        return "bg-yellow-500";
      case "error":
        return "bg-red-500";
      case "checking":
        return "bg-gray-400";
    }
  };

  const getStatusText = (status: PWAUpdateStatus): string => {
    switch (status) {
      case "current":
        return "Running latest version";
      case "update-available":
        return "Update available - click to refresh";
      case "error":
        return "Error checking for updates";
      case "checking":
        return "Checking for updates...";
    }
  };

  const handleClick = async () => {
    if (status === "update-available") {
      await updateServiceWorker();
    }
  };

  const statusColor = getStatusColor(status);
  const statusText = getStatusText(status);
  const isClickable = status === "update-available";

  return (
    <div className="relative inline-flex items-center group">
      <button
        onClick={handleClick}
        disabled={!isClickable}
        className={`w-2.5 h-2.5 rounded-full ${statusColor} ${
          isClickable ? "cursor-pointer hover:ring-2 hover:ring-offset-1 hover:ring-yellow-500" : "cursor-default"
        } transition-all`}
        aria-label={statusText}
        title={showTooltip ? statusText : undefined}
      />
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 dark:bg-gray-700 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
          {statusText}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-gray-900 dark:border-t-gray-700" />
        </div>
      )}
    </div>
  );
}
