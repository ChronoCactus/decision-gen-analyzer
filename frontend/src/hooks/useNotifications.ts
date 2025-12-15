"use client";

import { useState, useEffect } from "react";

export type NotificationPermission = "default" | "granted" | "denied";

interface UseNotificationsReturn {
  permission: NotificationPermission;
  requestPermission: () => Promise<NotificationPermission>;
  sendNotification: (title: string, options?: NotificationOptions) => void;
  isSupported: boolean;
}

/**
 * Hook for managing PWA notifications (stub implementation)
 * 
 * Provides:
 * - Permission management for browser notifications
 * - Function to request notification permission
 * - Function to send notifications (when permission granted)
 * - Check if notifications are supported
 */
export function useNotifications(): UseNotificationsReturn {
  const [permission, setPermission] = useState<NotificationPermission>("default");
  const [isSupported, setIsSupported] = useState(false);

  useEffect(() => {
    // Check if notifications are supported
    if (typeof window !== "undefined" && "Notification" in window) {
      setIsSupported(true);
      setPermission(Notification.permission as NotificationPermission);
    }
  }, []);

  const requestPermission = async (): Promise<NotificationPermission> => {
    if (!isSupported) {
      console.warn("Notifications are not supported in this browser");
      return "denied";
    }

    try {
      const result = await Notification.requestPermission();
      setPermission(result as NotificationPermission);
      return result as NotificationPermission;
    } catch (error) {
      console.error("Error requesting notification permission:", error);
      return "denied";
    }
  };

  const sendNotification = (title: string, options?: NotificationOptions) => {
    if (!isSupported) {
      console.warn("Notifications are not supported in this browser");
      return;
    }

    if (permission !== "granted") {
      console.warn("Notification permission not granted");
      return;
    }

    try {
      // Check if service worker is available for notifications
      if ("serviceWorker" in navigator && navigator.serviceWorker.controller) {
        // Use service worker to show notification
        navigator.serviceWorker.ready.then((registration) => {
          registration.showNotification(title, {
            icon: "/icon-192x192.png",
            badge: "/icon-192x192.png",
            ...options,
          });
        });
      } else {
        // Fallback to standard notification
        new Notification(title, {
          icon: "/icon-192x192.png",
          badge: "/icon-192x192.png",
          ...options,
        });
      }
    } catch (error) {
      console.error("Error sending notification:", error);
    }
  };

  return {
    permission,
    requestPermission,
    sendNotification,
    isSupported,
  };
}
