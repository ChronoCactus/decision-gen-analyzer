import { useState, useEffect } from 'react';

export interface InterfaceSettings {
  autoDismissToasts: boolean;
  toastDismissTimeout: number; // in seconds
}

const DEFAULT_SETTINGS: InterfaceSettings = {
  autoDismissToasts: false,
  toastDismissTimeout: 5,
};

const STORAGE_KEY = 'decision-analyzer-interface-settings';

export function useInterfaceSettings() {
  const [settings, setSettings] = useState<InterfaceSettings>(DEFAULT_SETTINGS);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        // eslint-disable-next-line
        setSettings({ ...DEFAULT_SETTINGS, ...JSON.parse(stored) });
      } catch (e) {
        console.error('Failed to parse interface settings', e);
      }
    }
    setIsLoaded(true);
  }, []);

  const updateSettings = (newSettings: Partial<InterfaceSettings>) => {
    const updated = { ...settings, ...newSettings };
    setSettings(updated);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  };

  return {
    settings,
    updateSettings,
    isLoaded
  };
}
