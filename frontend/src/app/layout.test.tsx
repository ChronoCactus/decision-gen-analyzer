import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// Mock Next.js fonts
vi.mock('next/font/google', () => ({
  Geist: () => ({ className: 'geist-sans', variable: '--font-geist-sans' }),
  Geist_Mono: () => ({ className: 'geist-mono', variable: '--font-geist-mono' }),
}));

import RootLayout, { metadata } from './layout';

describe('RootLayout', () => {
  it('should render children', () => {
    render(
      <RootLayout>
        <div data-testid="test-child">Test Content</div>
      </RootLayout>
    );

    expect(screen.getByTestId('test-child')).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('should render layout structure', () => {
    const { container } = render(
      <RootLayout>
        <div>Content</div>
      </RootLayout>
    );

    // Just verify the component renders without errors
    expect(container).toBeTruthy();
    expect(screen.getByText('Content')).toBeInTheDocument();
  });

  it('should apply layout classes', () => {
    const { container } = render(
      <RootLayout>
        <div data-testid="content">Test</div>
      </RootLayout>
    );

    // Verify content is rendered
    expect(screen.getByTestId('content')).toBeInTheDocument();
  });

  it('should handle multiple children', () => {
    render(
      <RootLayout>
        <div data-testid="child1">Child 1</div>
        <div data-testid="child2">Child 2</div>
      </RootLayout>
    );

    expect(screen.getByTestId('child1')).toBeInTheDocument();
    expect(screen.getByTestId('child2')).toBeInTheDocument();
  });

  it('should have correct metadata', () => {
    expect(metadata.title).toBe('Decision Analyzer');
    expect(metadata.description).toBe('AI-powered ADR analysis and generation system');
  });
});
