'use client';

export type SidebarPanel = 'folders' | 'tags' | null;

interface SidebarNavProps {
  activePanel: SidebarPanel;
  onPanelChange: (panel: SidebarPanel) => void;
  folderCount?: number;
  tagCount?: number;
}

export function SidebarNav({ activePanel, onPanelChange, folderCount = 0, tagCount = 0 }: SidebarNavProps) {
  const handleClick = (panel: SidebarPanel) => {
    if (activePanel === panel) {
      onPanelChange(null); // Close if clicking the active panel
    } else {
      onPanelChange(panel);
    }
  };

  return (
    <div className="flex flex-col items-center py-2 bg-gray-100 dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 w-12 shrink-0">
      {/* Folders Icon */}
      <button
        onClick={() => handleClick('folders')}
        className={`p-2 rounded-md mb-1 transition-colors relative group ${
          activePanel === 'folders'
            ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400'
            : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-200'
        }`}
        title="Folders"
        aria-label="Toggle folders panel"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
          className="w-6 h-6"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"
          />
        </svg>
        {/* Tooltip */}
        <span className="absolute left-full ml-2 px-2 py-1 bg-gray-900 dark:bg-gray-700 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50">
          Folders {folderCount > 0 && `(${folderCount})`}
        </span>
      </button>

      {/* Tags Icon */}
      <button
        onClick={() => handleClick('tags')}
        className={`p-2 rounded-md transition-colors relative group ${
          activePanel === 'tags'
            ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400'
            : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-200'
        }`}
        title="Tags"
        aria-label="Toggle tags panel"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
          className="w-6 h-6"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z"
          />
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 6h.008v.008H6V6z" />
        </svg>
        {/* Badge for tag count */}
        {tagCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-blue-600 text-white text-xs font-bold rounded-full h-4 min-w-4 flex items-center justify-center px-1">
            {tagCount > 99 ? '99+' : tagCount}
          </span>
        )}
        {/* Tooltip */}
        <span className="absolute left-full ml-2 px-2 py-1 bg-gray-900 dark:bg-gray-700 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50">
          Tags {tagCount > 0 && `(${tagCount})`}
        </span>
      </button>
    </div>
  );
}
