import { useState, useRef, useEffect, ReactNode } from 'react';

interface HoverCardProps {
  trigger: ReactNode;
  children: ReactNode;
  className?: string;
}

export function HoverCard({ trigger, children, className = '' }: HoverCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const closeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const clearCloseTimeout = () => {
    if (closeTimeoutRef.current) {
      clearTimeout(closeTimeoutRef.current);
      closeTimeoutRef.current = null;
    }
  };

  const handleTriggerEnter = () => {
    clearCloseTimeout();
    setIsOpen(true);
  };

  const handleTriggerLeave = () => {
    // "pop-up should stay there for at least 1 second after showing"
    // If user leaves trigger, give them 1s to move to content or just read it
    clearCloseTimeout();
    closeTimeoutRef.current = setTimeout(() => {
      setIsOpen(false);
    }, 1000);
  };

  const handleContentEnter = () => {
    // "if the user moves their cursor into the pop-up - it shouldn't disappear"
    clearCloseTimeout();
  };

  const handleContentLeave = () => {
    // "when the user moves their cursor out of the pop-up we should wait 200ms and exit"
    clearCloseTimeout();
    closeTimeoutRef.current = setTimeout(() => {
      setIsOpen(false);
    }, 200);
  };

  // Handle Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  // Cleanup on unmount
  useEffect(() => {
    return () => clearCloseTimeout();
  }, []);

  return (
    <div className="relative inline-block">
      <div
        onMouseEnter={handleTriggerEnter}
        onMouseLeave={handleTriggerLeave}
        className="inline-block"
      >
        {trigger}
      </div>
      {isOpen && (
        <div
          className={`absolute z-50 bottom-full left-0 mb-2 ${className}`}
          onMouseEnter={handleContentEnter}
          onMouseLeave={handleContentLeave}
        >
          {children}
        </div>
      )}
    </div>
  );
}
