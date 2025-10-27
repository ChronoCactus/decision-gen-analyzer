'use client';

import { useEscapeKey } from '@/hooks/useEscapeKey';

interface DeleteConfirmationModalProps {
  adrTitle: string;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}

export function DeleteConfirmationModal({
  adrTitle,
  onConfirm,
  onCancel,
  isDeleting,
}: DeleteConfirmationModalProps) {
  // Close with ESC key (unless we're in the middle of deleting)
  useEscapeKey(onCancel, !isDeleting);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div className="p-6">
          <div className="flex items-center mb-4">
            <div className="flex-shrink-0 w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
              <svg
                className="w-6 h-6 text-red-600"
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
            <h3 className="ml-4 text-lg font-semibold text-gray-900">
              Delete ADR
            </h3>
          </div>

          <p className="text-gray-600 mb-2">
            Are you sure you want to delete this ADR?
          </p>
          <p className="text-sm text-gray-700 font-medium mb-4 p-3 bg-gray-50 rounded-md">
            &quot;{adrTitle}&quot;
          </p>
          <p className="text-sm text-gray-600 mb-6">
            This action will delete the ADR from local storage and from LightRAG (if it exists there). 
            This action cannot be undone.
          </p>

          <div className="flex gap-3 justify-end">
            <button
              onClick={onCancel}
              disabled={isDeleting}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              disabled={isDeleting}
              className="px-4 py-2 text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isDeleting ? 'Deleting...' : 'Delete ADR'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
