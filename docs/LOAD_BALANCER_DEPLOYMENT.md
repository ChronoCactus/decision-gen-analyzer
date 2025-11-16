# Deploying Behind a Load Balancer

This guide explains how to deploy the Decision Analyzer behind a load balancer or reverse proxy (nginx, Traefik, Kubernetes Ingress, etc.).

## How URL Detection Works

The frontend **automatically detects** the backend URL based on how it's accessed:

### Local Development (localhost)
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000` (hardcoded)

### LAN Access (with custom port)
- Frontend: `http://192.168.0.100:3000`
- Backend: `http://192.168.0.100:8000` (inferred from hostname + port 8000)

### Production (via load balancer, no port in URL)
- Frontend: `https://mywebsite.mydomain.com`
- Backend: `https://mywebsite.mydomain.com/api` (same host, load balancer routes `/api` to backend)

## Load Balancer Configuration

### Requirements

1. **Frontend routing**: All requests except `/api/*` → Frontend service (port 3000)
2. **Backend routing**: All requests to `/api/*` → Backend service (port 8000)
3. **WebSocket support**: Enable WebSocket upgrades for `/api/v1/adrs/ws/*`

### Example: Nginx

```nginx
upstream frontend {
    server frontend:3000;
}

upstream backend {
    server backend:8000;
}

server {
    listen 443 ssl;
    server_name mywebsite.mydomain.com;

    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Backend API routes
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        
        # WebSocket support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Standard proxy headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend routes (everything else)
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Example: Kubernetes Ingress (nginx-ingress)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: decision-analyzer-ingress
  namespace: decision-gen-analyzer
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    # Enable WebSocket support
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - mywebsite.mydomain.com
    secretName: tls-secret
  rules:
  - host: mywebsite.mydomain.com
    http:
      paths:
      # Backend routes
      - path: /api(/|$)(.*)
        pathType: Prefix
        backend:
          service:
            name: decision-gen-analyzer-backend
            port:
              number: 8000
      # Frontend routes (default)
      - path: /
        pathType: Prefix
        backend:
          service:
            name: decision-gen-analyzer-frontend
            port:
              number: 3000
```

### Example: Traefik (Docker labels)

```yaml
version: '3.8'
services:
  frontend:
    image: decision-analyzer-frontend:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`mywebsite.mydomain.com`)"
      - "traefik.http.routers.frontend.priority=1"
      - "traefik.http.services.frontend.loadbalancer.server.port=3000"

  backend:
    image: decision-analyzer-backend:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`mywebsite.mydomain.com`) && PathPrefix(`/api`)"
      - "traefik.http.routers.backend.priority=2"
      - "traefik.http.services.backend.loadbalancer.server.port=8000"
```

## Environment Variables

### Option 1: Set API_BASE_URL (Recommended for Production)

Set the `API_BASE_URL` environment variable on the **backend** to tell it what URL to return to the frontend:

**Kubernetes:**
```yaml
containers:
- name: backend
  image: decision-analyzer-backend:latest
  env:
  - name: API_BASE_URL
    value: "https://mywebsite.mydomain.com"
  # ... other env vars
```

**Docker Compose:**
```yaml
services:
  backend:
    environment:
      - API_BASE_URL=https://mywebsite.mydomain.com
```

**Direct Docker:**
```bash
docker run -e API_BASE_URL=https://mywebsite.mydomain.com decision-analyzer-backend
```

### Option 2: Frontend Auto-detection (Alternative)

### Option 2: Frontend Auto-detection (Alternative)

If you don't set `API_BASE_URL` on the backend, the frontend will auto-detect based on `window.location`:
- Production (no port): Uses same hostname
- LAN (with port): Uses hostname with port 8000

This works but is less explicit than setting `API_BASE_URL`.

**Dockerfile build-arg:**
```bash
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://mywebsite.mydomain.com \
  -t decision-analyzer-frontend:latest \
  -f Dockerfile.frontend .
```

**Kubernetes env var:**
```yaml
containers:
- name: frontend
  image: decision-analyzer-frontend:latest
  env:
  - name: NEXT_PUBLIC_API_URL
    value: "https://mywebsite.mydomain.com"
```

**Docker Compose:**
```yaml
services:
  frontend:
    environment:
      - NEXT_PUBLIC_API_URL=https://mywebsite.mydomain.com
```

## Verification

1. **Access your site**: `https://mywebsite.mydomain.com`
2. **Open browser console**: Check for log messages:
   ```
   Inferred backend URL (production mode): https://mywebsite.mydomain.com
   Using configured API base URL: https://mywebsite.mydomain.com
   ```
3. **Check network requests**: Should see requests to `https://mywebsite.mydomain.com/api/v1/...` (no `:8000`)
4. **Test WebSocket**: Check for `wss://mywebsite.mydomain.com/api/v1/adrs/ws/cache-status` connections

## Troubleshooting

### Issue: Still seeing `:8000` in URLs

**Cause**: `NEXT_PUBLIC_API_URL` is explicitly set to include `:8000`

**Fix**: 
- Remove `NEXT_PUBLIC_API_URL` env var (use auto-detection)
- OR set it to `https://mywebsite.mydomain.com` (no port)

### Issue: WebSocket connections failing

**Cause**: Load balancer not configured for WebSocket upgrades

**Fix**: Add WebSocket support to your load balancer:
- Nginx: `proxy_set_header Upgrade $http_upgrade;`
- Traefik: Automatic WebSocket support
- Kubernetes Ingress: Add timeout annotations

### Issue: API requests returning 404

**Cause**: Load balancer not routing `/api/*` to backend

**Fix**: Check your routing configuration:
- Nginx: Verify `location /api/` block
- Kubernetes: Check Ingress path rules and priorities
- Traefik: Verify `PathPrefix` rules

### Issue: CORS errors

**Cause**: Backend not recognizing the load balancer hostname

**Fix**: Add your domain to backend CORS configuration (if using CORS middleware)

## Summary

✅ **For production behind load balancer**: 
- Don't set `NEXT_PUBLIC_API_URL` (or set it without `:8000`)
- Configure LB to route `/api/*` → backend:8000
- Enable WebSocket support in LB
- Frontend will auto-detect and use same hostname as accessed

✅ **For LAN access**:
- Frontend at `http://192.168.0.100:3000` 
- Backend at `http://192.168.0.100:8000`
- Auto-detection works automatically

✅ **For local development**:
- Frontend at `http://localhost:3000`
- Backend at `http://localhost:8000`
- Hardcoded for convenience
