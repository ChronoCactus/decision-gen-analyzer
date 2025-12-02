'use client';

import { useEscapeKey } from '@/hooks/useEscapeKey';

interface DeleteConfirmationModalProps {
  adrTitle: string;
  recordType?: 'decision' | 'principle';
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}

export function DeleteConfirmationModal({
  adrTitle,
  recordType = 'decision',
  onConfirm,
  onCancel,
  isDeleting,
}: DeleteConfirmationModalProps) {
  const recordLabel = recordType === 'principle' ? 'Principle' : 'Decision';

  // Close with ESC key (unless we're in the middle of deleting)
  useEscapeKey(onCancel, !isDeleting);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full">
        <div className="p-6">
          <div className="flex items-center mb-4">
            <div className="flex-shrink-0 w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
              <svg
                className="w-6 h-6 text-red-600 dark:text-red-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <h3 className="ml-4 text-lg font-semibold text-gray-900 dark:text-gray-100">
              Delete {recordLabel}
            </h3>
          </div>

          <p className="text-gray-600 dark:text-gray-400 mb-2">
            Are you sure you want to delete this {recordLabel.toLowerCase()}?
          </p>
          <p className="text-sm text-gray-700 dark:text-gray-300 font-medium mb-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-md">
            &quot;{adrTitle}&quot;
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
            This action will delete the {recordLabel.toLowerCase()} from local storage and from LightRAG (if it exists there). 
            This action cannot be undone.
          </p>

          <div className="flex gap-3 justify-end">
            <button
              onClick={onCancel}
              disabled={isDeleting}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              disabled={isDeleting}
              className="px-4 py-2 text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isDeleting ? 'Deleting...' : `Delete ${recordLabel}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
