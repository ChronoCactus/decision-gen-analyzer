import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useEscapeKey } from './useEscapeKey';

describe('useEscapeKey', () => {
  let addEventListenerSpy: ReturnType<typeof vi.spyOn>;
  let removeEventListenerSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    addEventListenerSpy = vi.spyOn(document, 'addEventListener');
    removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');
  });

  afterEach(() => {
    addEventListenerSpy.mockRestore();
    removeEventListenerSpy.mockRestore();
  });

  it('should call callback when Escape key is pressed', () => {
    const onEscape = vi.fn();
    renderHook(() => useEscapeKey(onEscape));

    // Simulate Escape key press
    const event = new KeyboardEvent('keydown', { key: 'Escape' });
    document.dispatchEvent(event);

    expect(onEscape).toHaveBeenCalledTimes(1);
  });

  it('should not call callback when other keys are pressed', () => {
    const onEscape = vi.fn();
    renderHook(() => useEscapeKey(onEscape));

    // Simulate other key presses
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab' }));

    expect(onEscape).not.toHaveBeenCalled();
  });

  it('should add event listener on mount', () => {
    const onEscape = vi.fn();
    renderHook(() => useEscapeKey(onEscape));

    expect(addEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
  });

  it('should remove event listener on unmount', () => {
    const onEscape = vi.fn();
    const { unmount } = renderHook(() => useEscapeKey(onEscape));

    const handler = addEventListenerSpy.mock.calls[0][1];
    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', handler);
  });

  it('should not add event listener when enabled is false', () => {
    const onEscape = vi.fn();
    renderHook(() => useEscapeKey(onEscape, false));

    // Try to trigger Escape
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

    expect(onEscape).not.toHaveBeenCalled();
  });

  it('should update listener when callback changes', () => {
    const onEscape1 = vi.fn();
    const onEscape2 = vi.fn();
    
    const { rerender } = renderHook(
      ({ callback }) => useEscapeKey(callback),
      { initialProps: { callback: onEscape1 } }
    );

    // First callback
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(onEscape1).toHaveBeenCalledTimes(1);
    expect(onEscape2).not.toHaveBeenCalled();

    // Update callback
    rerender({ callback: onEscape2 });

    // New callback should be called
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(onEscape1).toHaveBeenCalledTimes(1); // Still 1
    expect(onEscape2).toHaveBeenCalledTimes(1); // Now called
  });

  it('should enable/disable when enabled prop changes', () => {
    const onEscape = vi.fn();
    
    const { rerender } = renderHook(
      ({ enabled }) => useEscapeKey(onEscape, enabled),
      { initialProps: { enabled: true } }
    );

    // Should work when enabled
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(onEscape).toHaveBeenCalledTimes(1);

    // Disable
    rerender({ enabled: false });
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(onEscape).toHaveBeenCalledTimes(1); // Still 1, not called again

    // Re-enable
    rerender({ enabled: true });
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(onEscape).toHaveBeenCalledTimes(2); // Called again
  });
});
