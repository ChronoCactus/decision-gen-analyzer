import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useNotifications } from './useNotifications';

describe('useNotifications', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should detect notification support', () => {
    // Mock Notification API
    global.Notification = {
      permission: 'default',
      requestPermission: vi.fn(),
    } as any;

    const { result } = renderHook(() => useNotifications());
    
    waitFor(() => {
      expect(result.current.isSupported).toBe(true);
    });
  });

  it('should return default permission status', () => {
    global.Notification = {
      permission: 'default',
      requestPermission: vi.fn(),
    } as any;

    const { result } = renderHook(() => useNotifications());
    
    waitFor(() => {
      expect(result.current.permission).toBe('default');
    });
  });

  it('should provide requestPermission function', () => {
    global.Notification = {
      permission: 'default',
      requestPermission: vi.fn().mockResolvedValue('granted'),
    } as any;

    const { result } = renderHook(() => useNotifications());
    expect(typeof result.current.requestPermission).toBe('function');
  });

  it('should provide sendNotification function', () => {
    global.Notification = {
      permission: 'granted',
      requestPermission: vi.fn(),
    } as any;

    const { result } = renderHook(() => useNotifications());
    expect(typeof result.current.sendNotification).toBe('function');
  });

  it('should handle missing Notification API', async () => {
    global.Notification = undefined as any;

    const { result } = renderHook(() => useNotifications());
    
    await waitFor(() => {
      expect(result.current.isSupported).toBe(false);
    });
  });

  it('should request permission and update state', async () => {
    const mockRequestPermission = vi.fn().mockResolvedValue('granted');
    global.Notification = {
      permission: 'default',
      requestPermission: mockRequestPermission,
    } as any;

    const { result } = renderHook(() => useNotifications());

    await waitFor(async () => {
      const permission = await result.current.requestPermission();
      expect(permission).toBe('granted');
      expect(mockRequestPermission).toHaveBeenCalled();
    });
  });
});
