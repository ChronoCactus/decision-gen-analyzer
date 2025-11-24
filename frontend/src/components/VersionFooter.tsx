'use client';

export function VersionFooter() {
  const version = process.env.NEXT_PUBLIC_APP_VERSION || 'dev';
  
  return (
    <footer className="fixed bottom-0 right-0 px-3 py-1.5 text-xs text-gray-500 dark:text-gray-400 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm border-t border-l border-gray-200 dark:border-gray-700 rounded-tl-md z-10">
      <span className="font-mono">v{version}</span>
    </footer>
  );
}
