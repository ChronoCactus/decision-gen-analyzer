"use client";

import { useEffect, useState } from "react";
import { Workbox } from "workbox-window";

export type PWAUpdateStatus = "current" | "update-available" | "error" | "checking";

interface UsePWAUpdateStatusReturn {
  status: PWAUpdateStatus;
  isInstalled: boolean;
  updateServiceWorker: () => Promise<void>;
}

/**
 * Hook to monitor PWA service worker update status
 * 
 * Returns:
 * - status: "current" (green), "update-available" (yellow), "error" (red), "checking" (gray)
 * - isInstalled: whether the PWA is installed (service worker active)
 * - updateServiceWorker: function to manually trigger service worker update
 */
export function usePWAUpdateStatus(): UsePWAUpdateStatusReturn {
  // Determine if we should skip service worker setup
  const shouldSkipServiceWorker =
    typeof window === "undefined" ||
    !("serviceWorker" in navigator) ||
    process.env.NODE_ENV === "development";

  const [status, setStatus] = useState<PWAUpdateStatus>(
    shouldSkipServiceWorker ? "current" : "checking"
  );
  const [isInstalled, setIsInstalled] = useState(false);
  const [wb, setWb] = useState<Workbox | null>(null);

  useEffect(() => {
    // Only run in browser environment
    if (shouldSkipServiceWorker) {
      return;
    }

    let workbox: Workbox;

    const initServiceWorker = async () => {
      try {
        workbox = new Workbox("/sw.js", { scope: "/" });
        setWb(workbox);

        // Listen for waiting service worker (update available)
        workbox.addEventListener("waiting", () => {
          setStatus("update-available");
        });

        // Listen for controlling service worker (update installed)
        workbox.addEventListener("controlling", () => {
          setStatus("current");
          window.location.reload();
        });

        // Listen for activation (service worker active)
        workbox.addEventListener("activated", (event) => {
          if (!event.isUpdate) {
            setIsInstalled(true);
            setStatus("current");
          }
        });

        // Register the service worker
        const registration = await workbox.register();

        if (registration) {
          setIsInstalled(true);

          // Check for updates periodically (every 60 seconds)
          setInterval(() => {
            registration.update().catch((error) => {
              console.error("Error checking for service worker updates:", error);
              setStatus("error");
            });
          }, 60000);

          // Initial status check
          if (registration.waiting) {
            setStatus("update-available");
          } else if (registration.active) {
            setStatus("current");
          }
        } else {
          setStatus("error");
        }
      } catch (error) {
        console.error("Service worker registration failed:", error);
        setStatus("error");
      }
    };

    initServiceWorker();

    // Cleanup
    return () => {
      // No cleanup needed for Workbox
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateServiceWorker = async () => {
    if (wb) {
      // Tell the waiting service worker to skip waiting
      wb.messageSkipWaiting();
    }
  };

  return {
    status,
    isInstalled,
    updateServiceWorker,
  };
}
