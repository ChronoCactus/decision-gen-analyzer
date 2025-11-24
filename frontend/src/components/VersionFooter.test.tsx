import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { VersionFooter } from './VersionFooter';

describe('VersionFooter', () => {
  const originalEnv = process.env.NEXT_PUBLIC_APP_VERSION;

  afterEach(() => {
    process.env.NEXT_PUBLIC_APP_VERSION = originalEnv;
  });

  it('renders version from environment variable', () => {
    process.env.NEXT_PUBLIC_APP_VERSION = '1.2.3';
    render(<VersionFooter />);
    expect(screen.getByText('v1.2.3')).toBeInTheDocument();
  });

  it('falls back to dev version when env var not set', () => {
    delete process.env.NEXT_PUBLIC_APP_VERSION;
    render(<VersionFooter />);
    expect(screen.getByText('vdev')).toBeInTheDocument();
  });

  it('has proper styling for light and dark modes', () => {
    render(<VersionFooter />);
    const footer = screen.getByRole('contentinfo');
    
    // Check for dark mode classes
    expect(footer.className).toContain('dark:text-gray-400');
    expect(footer.className).toContain('dark:bg-gray-900/80');
    expect(footer.className).toContain('dark:border-gray-700');
  });
});
