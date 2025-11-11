'use client';

import { useState, useRef } from 'react';
import { useEscapeKey } from '@/hooks/useEscapeKey';

interface ImportExportModalProps {
  onClose: () => void;
  onImport: (files: File[], overwrite: boolean) => Promise<{
    message: string;
    imported_count: number;
    skipped_count: number;
    errors: string[];
    imported_ids?: string[];
  }>;
  onExportAll: () => void;
  onImportSuccess?: (importedCount: number, importedIds: string[]) => void;
  onExportSuccess?: () => void;
}

export function ImportExportModal({ onClose, onImport, onExportAll, onImportSuccess, onExportSuccess }: ImportExportModalProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [overwriteExisting, setOverwriteExisting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState<{
    message: string;
    imported_count: number;
    skipped_count: number;
    errors: string[];
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEscapeKey(onClose);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files));
      setImportResult(null);
    }
  };

  const handleImport = async () => {
    if (selectedFiles.length === 0) return;

    setIsImporting(true);
    setImportResult(null);

    try {
      const result = await onImport(selectedFiles, overwriteExisting);
      setImportResult(result);
      // Clear selected files after successful import
      setSelectedFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      
      // If import was successful, notify parent and close modal after a brief delay
      if (result.imported_count > 0) {
        setTimeout(() => {
          onImportSuccess?.(result.imported_count, result.imported_ids || []);
          onClose();
        }, 500);
      }
    } catch (error) {
      console.error('Import failed:', error);
      setImportResult({
        message: 'Import failed',
        imported_count: 0,
        skipped_count: 0,
        errors: [error instanceof Error ? error.message : 'Unknown error'],
      });
    } finally {
      setIsImporting(false);
    }
  };

  const handleExportAll = () => {
    onExportAll();
    // Close modal and notify parent after a brief delay
    setTimeout(() => {
      onExportSuccess?.();
      onClose();
    }, 300);
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Import/Export ADRs</h2>
          <button
            onClick={onClose}
            className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 text-2xl"
          >
            ×
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Export Section */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-white dark:bg-gray-800">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Export</h3>
            <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
              Export all ADRs to a single versioned JSON file that can be imported later.
            </p>
            <button
              onClick={handleExportAll}
              className="w-full bg-blue-600 text-white px-4 py-3 rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              📥 Export All ADRs
            </button>
          </div>

          {/* Import Section */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-white dark:bg-gray-800">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Import</h3>
            <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
              Import ADRs from one or more exported JSON files. You can select multiple files at once.
            </p>

            <div className="space-y-4">
              {/* File Input */}
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json"
                  multiple
                  onChange={handleFileSelect}
                  className="hidden"
                  id="file-input"
                />
                <label
                  htmlFor="file-input"
                  className="block w-full text-center bg-gray-100 dark:bg-gray-700 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg px-4 py-8 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-600 hover:border-gray-400 dark:hover:border-gray-500 transition-colors"
                >
                  <div className="text-4xl mb-2">📁</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    Click to select files or drag and drop
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                    JSON files only, multiple files supported
                  </div>
                </label>
              </div>

              {/* Selected Files */}
              {selectedFiles.length > 0 && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Selected Files ({selectedFiles.length}):
                  </div>
                  <div className="max-h-32 overflow-y-auto space-y-1">
                    {selectedFiles.map((file, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between bg-gray-50 dark:bg-gray-700 px-3 py-2 rounded text-sm"
                      >
                        <span className="text-gray-700 dark:text-gray-300 truncate">{file.name}</span>
                        <button
                          onClick={() => removeFile(index)}
                          className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 ml-2"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Overwrite Option */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="overwrite"
                  checked={overwriteExisting}
                  onChange={(e) => setOverwriteExisting(e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 dark:border-gray-600 rounded focus:ring-blue-500"
                />
                <label htmlFor="overwrite" className="text-sm text-gray-700 dark:text-gray-300">
                  Overwrite existing ADRs with same ID
                </label>
              </div>

              {/* Import Button */}
              <button
                onClick={handleImport}
                disabled={selectedFiles.length === 0 || isImporting}
                className="w-full bg-green-600 text-white px-4 py-3 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {isImporting ? '⏳ Importing...' : `📤 Import ${selectedFiles.length} File${selectedFiles.length !== 1 ? 's' : ''}`}
              </button>
            </div>
          </div>

          {/* Import Result */}
          {importResult && (
            <div
              className={`border rounded-lg p-4 ${
                importResult.errors.length > 0
                ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
                : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
              }`}
            >
              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Import Result</h4>
              <div className="text-sm space-y-1">
                <p className="text-gray-700 dark:text-gray-300">
                  ✅ Imported: <span className="font-medium">{importResult.imported_count}</span>
                </p>
                <p className="text-gray-700 dark:text-gray-300">
                  ⏭️ Skipped: <span className="font-medium">{importResult.skipped_count}</span>
                </p>
                {importResult.errors.length > 0 && (
                  <div className="mt-2">
                    <p className="text-red-700 dark:text-red-400 font-medium">Errors:</p>
                    <ul className="list-disc list-inside text-xs text-red-600 dark:text-red-400 mt-1 max-h-32 overflow-y-auto">
                      {importResult.errors.map((error, index) => (
                        <li key={index}>{error}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="sticky bottom-0 bg-gray-50 dark:bg-gray-800 px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button
            onClick={onClose}
            className="bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 px-6 py-2 rounded-md hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
