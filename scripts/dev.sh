#!/bin/bash
# Development environment startup script with hot-reload enabled

set -e

echo "🚀 Starting Decision Analyzer in DEVELOPMENT mode..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Features enabled:"
echo "  ✓ Backend auto-reload (uvicorn --reload)"
echo "  ✓ Celery auto-restart on code changes"
echo "  ✓ Frontend hot-reload (Next.js dev server)"
echo "  ✓ Volume mounts for instant code updates"
echo ""
echo "Services:"
echo "  • Backend API:  http://localhost:8000"
echo "  • Frontend:     http://localhost:3003"
echo "  • Redis:        localhost:6380"
echo ""
echo "To stop: Press Ctrl+C or run 'docker compose down'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Use both compose files - dev overrides production settings
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
