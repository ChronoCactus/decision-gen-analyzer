# Progressive Web App (PWA) Implementation

## Overview

The Decision Analyzer now includes full Progressive Web App (PWA) support, enabling users to install the application on their mobile devices and enjoy an app-like experience with offline capabilities.

## Features

### ✅ Installability
- **Home Screen Installation**: Users can install the app to their device home screen from the browser menu
- **Standalone Display**: Installed app launches without browser chrome for a native app experience
- **Custom Icons**: Branded 192x192 and 512x512 icons for home screen and splash screens

### ✅ Offline Support
- **Service Worker Caching**: Automatic caching of static assets and API responses
- **NetworkFirst Strategy**: Prioritizes fresh content while maintaining offline fallbacks
- **Runtime Caching**: Caches network requests with 30-day expiration and 200 entry limit

### ✅ Update Notifications
- **Visual Status Indicator**: Colored dot next to version number in lower-right corner
  - 🟢 **Green**: Running latest version
  - 🟡 **Yellow**: Update available (click to refresh)
  - 🔴 **Red**: Error checking for updates
  - ⚪ **Gray**: Checking for updates
- **Auto-Update Checks**: Service worker checks for updates every 60 seconds
- **Click to Update**: Yellow indicator is clickable to trigger immediate update

### ✅ Push Notifications (Stub)
- **Permission Management**: Hook for requesting notification permissions
- **Send Notifications**: Function to send browser notifications when permitted
- **Service Worker Integration**: Uses service worker for reliable notification delivery
- **Future-Ready**: Architecture prepared for future push notification features

## Architecture

### Technology Stack
- **next-pwa**: Next.js PWA plugin with automatic service worker generation
- **Workbox**: Google's service worker library for advanced caching strategies
- **workbox-window**: Client-side library for service worker lifecycle management

### Key Components

#### Service Worker Configuration
Location: `frontend/next.config.ts`

```typescript
const withPWA = withPWAInit({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
  skipWaiting: true,
  reloadOnOnline: true,
  runtimeCaching: [
    {
      urlPattern: /^https?.*/, 
      handler: "NetworkFirst",
      options: {
        cacheName: "offlineCache",
        expiration: {
          maxEntries: 200,
          maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
        },
        networkTimeoutSeconds: 10,
      },
    },
  ],
});
```

#### PWA Hooks

**`usePWAUpdateStatus`**: Monitors service worker update status
- Returns: `status`, `isInstalled`, `updateServiceWorker()`
- Listens to service worker lifecycle events
- Provides update notification mechanism

**`useNotifications`**: Manages browser notifications
- Returns: `permission`, `requestPermission()`, `sendNotification()`, `isSupported`
- Handles permission requests
- Sends notifications via service worker or Notification API

#### Visual Components

**`PWAStatusIndicator`**: Colored dot with tooltip
- Green: Latest version
- Yellow: Update available (clickable)
- Red: Update check error
- Gray: Checking for updates

**`VersionFooter`**: Version display with PWA indicator
- Shows app version from `NEXT_PUBLIC_APP_VERSION`
- Includes `PWAStatusIndicator` component
- Positioned in lower-right corner

### Manifest Configuration
Location: `frontend/public/manifest.json`

```json
{
  "name": "Decision Analyzer",
  "short_name": "DecisionGen",
  "description": "AI-powered ADR analysis and generation system",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#2563eb",
  "icons": [...]
}
```

## Usage

### For Developers

#### Local Development
Service worker is **disabled** in development mode to preserve Next.js hot reload functionality.

```bash
npm run dev
# PWA features are inactive in development
```

#### Production Build
Service worker is automatically generated during build:

```bash
npm run build
npm run start
# Access http://localhost:3000 and install PWA
```

#### Generating Icons
Custom icons can be generated from the SVG source:

```bash
npm run generate-icons
# Generates icon-192x192.png and icon-512x512.png from icon.svg
```

#### Docker Deployment
PWA features are enabled in Docker production builds:

```bash
docker compose up --build
# PWA installable on mobile devices
```

### For Users

#### Installing the PWA (Mobile)
1. Open the Decision Analyzer in your mobile browser (Chrome, Safari, Edge)
2. Look for "Add to Home Screen" or "Install" in browser menu
3. Tap "Add" or "Install" to add the icon to your home screen
4. Launch the app from your home screen for an app-like experience

#### Installing the PWA (Desktop)
1. Open the Decision Analyzer in Chrome or Edge
2. Look for the install icon (⊕) in the address bar
3. Click "Install" to add the app to your desktop
4. The app will open in a standalone window without browser chrome

#### Updating the PWA
1. When an update is available, the status indicator turns yellow
2. Hover over the yellow dot to see "Update available - click to refresh"
3. Click the yellow dot to install the update and reload the app
4. The indicator turns green once the update is applied

#### Enabling Notifications
Notification functionality is stubbed but ready for future use:

```typescript
import { useNotifications } from '@/hooks/useNotifications';

function MyComponent() {
  const { permission, requestPermission, sendNotification } = useNotifications();
  
  const handleEnableNotifications = async () => {
    const result = await requestPermission();
    if (result === 'granted') {
      sendNotification('Notifications Enabled', {
        body: 'You will now receive updates',
      });
    }
  };
  
  return <button onClick={handleEnableNotifications}>Enable Notifications</button>;
}
```

## Caching Strategy

### NetworkFirst
The PWA uses a **NetworkFirst** caching strategy for all network requests:

1. **Network Priority**: Attempts to fetch from network first
2. **Timeout**: Falls back to cache after 10 seconds
3. **Offline Fallback**: Serves cached content when network unavailable
4. **Cache Expiration**: Entries expire after 30 days
5. **Cache Limit**: Maximum 200 entries (LRU eviction)

### Why NetworkFirst?
- **Fresh Content**: Users always get the latest data when online
- **Offline Support**: Cached content available when offline
- **Prevents Stale Content**: Avoids showing outdated ADRs or UI
- **Balanced Performance**: Good compromise between speed and freshness

## Testing

### PWA Audit (Lighthouse)
```bash
# Build and start production server
npm run build && npm run start

# Run Lighthouse audit in Chrome DevTools
# Application > Lighthouse > Progressive Web App
```

### Manual Testing Checklist
- [ ] Install PWA from browser menu
- [ ] Launch PWA from home screen without browser chrome
- [ ] Verify offline functionality (airplane mode)
- [ ] Check update indicator turns yellow when new version deployed
- [ ] Click yellow indicator to apply update
- [ ] Verify green indicator after update applied
- [ ] Test notification permission request (if implemented)
- [ ] Verify PWA icons display correctly on home screen

### Browser DevTools
- **Application Tab**: View manifest, service worker status, cache storage
- **Service Workers**: Check registration, lifecycle, and update status
- **Cache Storage**: Inspect cached resources and expiration
- **Manifest**: Validate manifest.json properties

## Troubleshooting

### Service Worker Not Registering
- Ensure production build (`NODE_ENV=production`)
- Check HTTPS or localhost (service workers require secure context)
- Verify `sw.js` generated in `public/` directory after build
- Check browser console for service worker errors

### Update Indicator Stuck on Yellow
- Hard refresh the page (Cmd+Shift+R or Ctrl+Shift+F5)
- Click the yellow indicator to trigger manual update
- Check service worker status in DevTools Application tab
- Verify service worker update check interval

### Icons Not Displaying
- Run `npm run generate-icons` to regenerate icons
- Verify `icon-192x192.png` and `icon-512x512.png` exist in `public/`
- Check manifest.json icon paths are correct
- Clear browser cache and reinstall PWA

### Offline Mode Not Working
- Verify service worker is active in DevTools
- Check cache storage contains expected resources
- Review network requests in DevTools Network tab (should show "from ServiceWorker")
- Ensure NetworkFirst strategy is configured in next.config.ts

## Future Enhancements

### Push Notifications
- Backend API endpoints for notification subscriptions
- Notification payload management
- Subscription lifecycle handling
- User notification preferences

### Advanced Caching
- Route-specific caching strategies
- Background sync for offline form submissions
- Periodic background sync for ADR updates
- Cache warming on install

### Install Prompt
- Custom install prompt UI
- Deferred install prompt
- Install analytics tracking
- User install preferences

### Offline Features
- Offline ADR viewing with full functionality
- Queue ADR generation requests when offline
- Sync when connection restored
- Offline indicator in UI

## Resources

- [next-pwa Documentation](https://github.com/shadowwalker/next-pwa)
- [Workbox Documentation](https://developers.google.com/web/tools/workbox)
- [PWA Checklist](https://web.dev/pwa-checklist/)
- [Service Worker Lifecycle](https://developers.google.com/web/fundamentals/primers/service-workers/lifecycle)
- [Web App Manifest](https://developer.mozilla.org/en-US/docs/Web/Manifest)
