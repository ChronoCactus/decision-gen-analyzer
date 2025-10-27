import { useEffect } from 'react';

/**
 * Hook to handle ESC key press for closing modals
 * @param onEscape - Callback function to execute when ESC is pressed
 * @param enabled - Whether the hook is currently enabled (default: true)
 */
export function useEscapeKey(onEscape: () => void, enabled: boolean = true) {
  useEffect(() => {
    if (!enabled) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onEscape();
      }
    };

    // Add event listener to document
    document.addEventListener('keydown', handleEscape);

    // Cleanup
    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onEscape, enabled]);
}
