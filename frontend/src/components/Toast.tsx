'use client';

import { useEffect } from 'react';

interface ToastProps {
  message: string;
  type?: 'info' | 'success' | 'warning' | 'error';
  onClose: () => void;
  duration?: number;
  position?: 'top' | 'bottom';
}

export function Toast({ message, type = 'info', onClose, duration = 5000, position = 'bottom' }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, duration);

    return () => clearTimeout(timer);
  }, [onClose, duration]);

  const bgColor = {
    info: 'bg-blue-600',
    success: 'bg-green-600',
    warning: 'bg-yellow-600',
    error: 'bg-red-600',
  }[type];

  const positionClasses = position === 'top'
    ? 'top-4 left-1/2 -translate-x-1/2 animate-slide-down'
    : 'bottom-4 right-4 animate-slide-up';

  return (
    <div className={`fixed ${positionClasses} z-50`}>
      <div className={`${bgColor} text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-3`}>
        <span>{message}</span>
        <button
          onClick={onClose}
          className="text-white hover:text-gray-200 transition-colors"
          aria-label="Close"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
