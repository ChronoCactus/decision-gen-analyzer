'use client';

import { useState, useEffect, useRef } from 'react';
import { ADR } from '@/types/api';
import { SidebarNav, SidebarPanel } from './SidebarNav';
import { FoldersPanel } from './FoldersPanel';
import { TagsPanel } from './TagsPanel';

interface SidebarProps {
  adrs: ADR[];
  selectedFolder: string | null;
  selectedTag: string | null;
  onFolderSelect: (folderPath: string | null) => void;
  onTagSelect: (tag: string | null) => void;
  onADRFolderChange: (adrId: string, folderPath: string | null) => Promise<void>;
  onADRTagAdd: (adrId: string, tag: string) => Promise<void>;
  onADRTagRemove: (adrId: string, tag: string) => Promise<void>;
  onFolderCreated?: (folderPath: string) => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

export function Sidebar({
  adrs,
  selectedFolder,
  selectedTag,
  onFolderSelect,
  onTagSelect,
  onADRFolderChange,
  onADRTagAdd,
  onADRTagRemove,
  onFolderCreated,
  mobileOpen,
  onMobileClose,
}: SidebarProps) {
  const [activePanel, setActivePanel] = useState<SidebarPanel>('folders');
  const [sidebarWidth, setSidebarWidth] = useState(280); // Default width (current is ~280px)
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);

  const MIN_WIDTH = 140; // Half of default
  const MAX_WIDTH = 600; // Maximum width

  // Count unique folders and tags for badges
  const folderCount = new Set(
    adrs.map(adr => adr.metadata.folder_path).filter(Boolean)
  ).size;
  
  const tagCount = new Set(
    adrs.flatMap(adr => adr.metadata.tags)
  ).size;

  // Apply width only on desktop
  useEffect(() => {
    if (sidebarRef.current) {
      const isDesktop = window.innerWidth >= 768;
      if (isDesktop) {
        // When collapsed (no active panel), only show icon bar width
        if (activePanel === null) {
          sidebarRef.current.style.width = '48px';
        } else {
          sidebarRef.current.style.width = `${sidebarWidth}px`;
        }
      } else {
        sidebarRef.current.style.width = '';
      }
    }
  }, [sidebarWidth, mobileOpen, activePanel]);

  // Handle resize
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      
      const newWidth = e.clientX;
      if (newWidth >= MIN_WIDTH && newWidth <= MAX_WIDTH) {
        setSidebarWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, MIN_WIDTH, MAX_WIDTH]);

  // Clear selections when switching panels
  const handlePanelChange = (panel: SidebarPanel) => {
    if (panel !== activePanel) {
      // Clear folder filter when switching to tags
      if (panel === 'tags' && activePanel === 'folders') {
        onFolderSelect(null);
      }
      // Clear tag filter when switching to folders
      if (panel === 'folders' && activePanel === 'tags') {
        onTagSelect(null);
      }
    }
    setActivePanel(panel);
  };

  const handleClose = () => {
    setActivePanel(null);
    onMobileClose();
  };

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
          onClick={onMobileClose}
        />
      )}

      {/* Sidebar container */}
      <div
        ref={sidebarRef}
        className={`
          fixed inset-y-0 left-0 z-40
          md:relative md:inset-auto md:z-auto
          flex h-full flex-shrink-0
          transform transition-transform duration-300 ease-in-out
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
      >
        {/* Icon navigation bar */}
        <SidebarNav
          activePanel={activePanel}
          onPanelChange={handlePanelChange}
          folderCount={folderCount}
          tagCount={tagCount}
        />

        {/* Active panel */}
        {activePanel === 'folders' && (
          <FoldersPanel
            adrs={adrs}
            selectedFolder={selectedFolder}
            onFolderSelect={onFolderSelect}
            onADRFolderChange={onADRFolderChange}
            onFolderCreated={onFolderCreated}
            onClose={handleClose}
          />
        )}

        {activePanel === 'tags' && (
          <TagsPanel
            adrs={adrs}
            selectedTag={selectedTag}
            onTagSelect={onTagSelect}
            onADRTagAdd={onADRTagAdd}
            onADRTagRemove={onADRTagRemove}
            onClose={handleClose}
          />
        )}

        {/* Resize handle - only on desktop and when panel is open */}
        {activePanel !== null && (
          <div
            className="hidden md:block absolute right-0 top-0 h-full w-1.5 cursor-ew-resize hover:bg-blue-500 dark:hover:bg-blue-400 transition-colors bg-gray-200 dark:bg-gray-700"
            onMouseDown={() => setIsResizing(true)}
            style={{ height: '100%' }}
          />
        )}
      </div>
    </>
  );
}

// Re-export types and components for convenience
export { SidebarNav } from './SidebarNav';
export type { SidebarPanel } from './SidebarNav';
export { FoldersPanel } from './FoldersPanel';
export { TagsPanel } from './TagsPanel';
