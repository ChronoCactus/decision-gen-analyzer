# LAN Discovery Configuration Guide

This guide explains how to configure Decision Analyzer to be accessible from other devices on your local area network (LAN).

## Overview

By default, Decision Analyzer's frontend can only communicate with the backend via `localhost:8000`. This means:
- ✅ Works fine when accessing from the same machine
- ❌ Doesn't work when accessing from another device on the network

With **LAN Discovery** enabled:
- ✅ Access the UI from any device on your network
- ✅ Frontend automatically discovers the backend's network IP
- ✅ All API calls work seamlessly across devices

## Use Cases

- Access the app from your tablet or phone while working on your desktop
- Share the app with team members on the same network
- Test on multiple devices simultaneously
- Work on a laptop while the backend runs on a more powerful desktop

## Quick Start

### 1. Find Your Host IP Address

Run the provided script:
```bash
./scripts/get_host_ip.sh
```

This will show you available IP addresses. Choose the one for your primary network interface (usually starts with `192.168` or `10.0`).

**Example output:**
```
Available network interfaces:
  - 192.168.0.58  ← Use this one
  - 192.168.0.37
```

### 2. Configure Environment Variables

Add to your `.env` file (or set in docker-compose):

```bash
ENABLE_LAN_DISCOVERY=true
HOST_IP=192.168.0.58  # Replace with your actual IP
```

### 3. Start the Services

```bash
docker-compose up --build
```

### 4. Access from Any Device

From any device on your network:
- **Frontend UI**: `http://192.168.0.58:3003`
- **Backend API**: `http://192.168.0.58:8000`

The frontend will automatically discover and use the correct backend URL!

## How It Works

### Backend Changes

1. **Configuration Endpoint**: New `/api/v1/config` endpoint returns the API base URL
   ```json
   {
     "api_base_url": "http://192.168.0.58:8000",
     "lan_discovery_enabled": true
   }
   ```

2. **Dynamic CORS**: When `ENABLE_LAN_DISCOVERY=true`, CORS allows all origins
   - Normal mode: Only `localhost:3000`, `localhost:3001`, `localhost:3003`
   - LAN mode: All origins (`*`)

### Frontend Changes

1. **Smart URL Inference**: Frontend infers backend URL from the current browser location
   - If accessed via `http://192.168.0.58:3003`, backend is assumed at `http://192.168.0.58:8000`
   - If accessed via `http://localhost:3003`, backend is assumed at `http://localhost:8000`
2. **Dynamic API Discovery**: On first API call, frontend fetches configuration from inferred backend URL
3. **Automatic Failover**: If config fetch fails, uses the inferred URL as fallback
4. **Caching**: Configuration is fetched once per session

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_LAN_DISCOVERY` | No | `false` | Enable LAN discovery mode |
| `HOST_IP` | Conditional* | None | Your machine's IP address |
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000` | Override frontend API URL |

\* Required when `ENABLE_LAN_DISCOVERY=true`

### Docker Compose Configuration

```yaml
services:
  backend:
    environment:
      - ENABLE_LAN_DISCOVERY=${ENABLE_LAN_DISCOVERY:-false}
      - HOST_IP=${HOST_IP:-}
      # ... other variables

  frontend:
    environment:
      - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}
```

## Security Considerations

⚠️ **Important**: Only enable LAN discovery on trusted networks!

When LAN discovery is enabled:
- Backend accepts connections from any device on the network
- No authentication is required (unless you add it separately)
- All API endpoints are accessible network-wide

**Best Practices:**
- Only enable on private home or office networks
- Disable when on public WiFi
- Consider adding authentication for sensitive data
- Use firewall rules to restrict access if needed

## Troubleshooting

### Frontend can't connect to backend

**Symptom**: Frontend shows connection errors when accessing from another device

**Solutions:**
1. Verify `HOST_IP` is correctly set to your machine's LAN IP
2. Check that `ENABLE_LAN_DISCOVERY=true` is set
3. Ensure firewall allows connections on ports 8000 and 3003
4. Verify both devices are on the same network

```bash
# Test backend connectivity from another device
curl http://YOUR_HOST_IP:8000/health

# Should return: {"status":"healthy","service":"decision-analyzer-api"}
```

### Backend shows wrong IP in config

**Symptom**: `/api/v1/config` returns unexpected URL

**Solution**: Double-check `HOST_IP` environment variable matches your actual IP

```bash
# Verify environment variable
docker-compose exec backend env | grep HOST_IP

# Should show: HOST_IP=192.168.0.58
```

### Frontend sends requests to localhost instead of network IP

**Symptom**: Browser console shows requests to `http://localhost:8000` but you want it to use your network IP

**Root Cause**: This happens when:
1. Backend's `ENABLE_LAN_DISCOVERY` is not set to `true`, OR
2. Backend's `HOST_IP` is not set correctly

**Solution**: 
```bash
# Check backend configuration
docker-compose exec backend env | grep -E "ENABLE_LAN_DISCOVERY|HOST_IP"

# Should show:
# ENABLE_LAN_DISCOVERY=true
# HOST_IP=192.168.0.58

# If not set correctly, update .env and restart
docker-compose down
docker-compose up --build
```

**How to verify**: Check the config endpoint returns the correct IP:
```bash
curl http://localhost:8000/api/v1/config
# Should return: {"api_base_url":"http://192.168.0.58:8000","lan_discovery_enabled":true}
```

**Note**: The frontend infers the backend URL from the browser's current location. For example:
- Accessing from `http://192.168.0.58:3003` → Backend inferred as `http://192.168.0.58:8000`
- Accessing from `http://localhost:3003` → Backend inferred as `http://localhost:8000`

The frontend then fetches the config endpoint to confirm and get the official backend URL.

### CORS errors in browser console

**Symptom**: Browser shows CORS policy errors

**Solution**: Ensure `ENABLE_LAN_DISCOVERY=true` and restart services

```bash
docker-compose down
docker-compose up --build
```

### Can't find host IP

**Symptom**: Not sure which IP address to use

**Solution**: Run the discovery script or check manually

```bash
# Using the script
./scripts/get_host_ip.sh

# Manual check (macOS)
ifconfig | grep "inet " | grep -v 127.0.0.1

# Manual check (Linux)
hostname -I

# Manual check (Windows)
ipconfig
```

## Development Mode

For local development without Docker:

### Backend
```bash
# Set environment variables
export ENABLE_LAN_DISCOVERY=true
export HOST_IP=192.168.0.58

# Start backend
./scripts/run_backend.sh
```

### Frontend
```bash
cd frontend

# Optional: Set default API URL
export NEXT_PUBLIC_API_URL=http://192.168.0.58:8000

# Start frontend
npm run dev
```

## Testing

Verify the setup works:

```bash
# 1. Check backend health from another device
curl http://YOUR_HOST_IP:8000/health

# 2. Check config endpoint
curl http://YOUR_HOST_IP:8000/api/v1/config

# Expected response:
# {
#   "api_base_url": "http://YOUR_HOST_IP:8000",
#   "lan_discovery_enabled": true
# }

# 3. Access frontend from another device
# Open browser to: http://YOUR_HOST_IP:3003
# Check browser console for: "API base URL configured: http://YOUR_HOST_IP:8000"
```

## Disabling LAN Discovery

To return to localhost-only mode:

```bash
# Remove or set to false in .env
ENABLE_LAN_DISCOVERY=false

# Restart services
docker-compose down
docker-compose up --build
```

Or simply comment out the variables:
```bash
# ENABLE_LAN_DISCOVERY=true
# HOST_IP=192.168.0.58
```

## Advanced Usage

### Multiple Network Interfaces

If your machine has multiple network interfaces (WiFi + Ethernet):

1. Choose the interface your other devices will connect through
2. Use that interface's IP for `HOST_IP`
3. Both interfaces will work, but use the primary one for consistency

### Dynamic IP Assignment

If your router uses DHCP and your IP changes:

**Option 1: Static IP** (Recommended)
- Configure a static IP in your router settings
- Set `HOST_IP` to the static IP

**Option 2: Dynamic Update**
- Update `HOST_IP` when your IP changes
- Restart services: `docker-compose restart`

**Option 3: DNS**
- Set up local DNS (like mDNS/Bonjour)
- Use hostname instead of IP (requires additional configuration)

## Related Documentation

- [Main README](../README.md) - General setup and usage
- [Parallel Processing Guide](./PARALLEL_PROCESSING.md) - Multi-backend LLM configuration
- [Docker Compose Reference](../docker-compose.yml) - Service configuration

## Support

If you encounter issues:
1. Check the [Troubleshooting](#troubleshooting) section
2. Verify environment variables are set correctly
3. Check Docker logs: `docker-compose logs backend`
4. Test connectivity with curl commands above
