import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { usePWAUpdateStatus } from './usePWAUpdateStatus';

// Mock Workbox
vi.mock('workbox-window', () => ({
  Workbox: vi.fn().mockImplementation(() => ({
    addEventListener: vi.fn(),
    register: vi.fn().mockResolvedValue({
      waiting: null,
      active: {},
      update: vi.fn().mockResolvedValue(undefined),
    }),
    messageSkipWaiting: vi.fn(),
  })),
}));

describe('usePWAUpdateStatus', () => {
  beforeEach(() => {
    // Mock service worker support
    Object.defineProperty(navigator, 'serviceWorker', {
      writable: true,
      configurable: true,
      value: {
        register: vi.fn(),
      },
    });

    // Set production environment
    process.env.NODE_ENV = 'production';
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('should initialize with checking status', () => {
    const { result } = renderHook(() => usePWAUpdateStatus());
    expect(result.current.status).toBe('checking');
  });

  it('should set status to current in development mode', () => {
    process.env.NODE_ENV = 'development';
    const { result } = renderHook(() => usePWAUpdateStatus());
    expect(result.current.status).toBe('current');
  });

  it('should register service worker and set installed status', async () => {
    const { result } = renderHook(() => usePWAUpdateStatus());

    await waitFor(() => {
      expect(result.current.isInstalled).toBe(true);
    });
  });

  it('should provide updateServiceWorker function', () => {
    const { result } = renderHook(() => usePWAUpdateStatus());
    expect(typeof result.current.updateServiceWorker).toBe('function');
  });

  it('should return current status when service worker not supported', async () => {
    // Remove service worker support
    Object.defineProperty(navigator, 'serviceWorker', {
      writable: true,
      configurable: true,
      value: undefined,
    });

    const { result } = renderHook(() => usePWAUpdateStatus());
    
    await waitFor(() => {
      expect(result.current.status).toBe('current');
    });
  });
});
