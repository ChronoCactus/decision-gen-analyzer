'use client';

import { diffWords } from 'diff';

interface DiffViewerProps {
  oldText: string;
  newText: string;
  label?: string;
}

export function DiffViewer({ oldText, newText, label }: DiffViewerProps) {
  const diff = diffWords(oldText || '', newText || '');

  return (
    <div className="mb-4">
      {label && <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</h4>}
      <div className="p-3 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded text-sm whitespace-pre-wrap font-mono">
        {diff.map((part, index) => {
          const color = part.added
            ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
            : part.removed
            ? 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 line-through'
            : 'text-gray-800 dark:text-gray-200';
          return (
            <span key={index} className={color}>
              {part.value}
            </span>
          );
        })}
      </div>
    </div>
  );
}

interface ArrayDiffViewerProps {
  oldArray: string[];
  newArray: string[];
  label?: string;
}

export function ArrayDiffViewer({ oldArray, newArray, label }: ArrayDiffViewerProps) {
  // Simple array diff: show removed items then added items
  const safeOld = oldArray || [];
  const safeNew = newArray || [];
  
  const removed = safeOld.filter(item => !safeNew.includes(item));
  const added = safeNew.filter(item => !safeOld.includes(item));
  const unchanged = safeOld.filter(item => safeNew.includes(item));

  return (
    <div className="mb-4">
      {label && <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</h4>}
      <div className="p-3 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded text-sm space-y-1">
        {unchanged.map((item, i) => (
          <div key={`unchanged-${i}`} className="text-gray-600 dark:text-gray-400">{item}</div>
        ))}
        {removed.map((item, i) => (
          <div key={`removed-${i}`} className="bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 px-2 py-1 rounded -mx-2">
            - {item}
          </div>
        ))}
        {added.map((item, i) => (
          <div key={`added-${i}`} className="bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 px-2 py-1 rounded -mx-2">
            + {item}
          </div>
        ))}
      </div>
    </div>
  );
}
