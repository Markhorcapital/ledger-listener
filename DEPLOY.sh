#!/bin/bash
# Markhor CEX Balance Service - Server Deployment Script

set -e  # Exit on error

echo "🚀 Markhor CEX Balance Service - Deployment"
echo "============================================"

# Configuration
PROJECT_DIR="Ledger-Update_Service"
SERVICE_NAME="markhor-cex-balance"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker and Docker Compose found${NC}"

# Stop existing service if running
echo ""
echo "📦 Stopping existing service (if any)..."
docker-compose down 2>/dev/null || true

# Build the image
echo ""
echo "🔨 Building Docker image..."
docker-compose build --no-cache

# Start the service
echo ""
echo "🚀 Starting service..."
docker-compose up -d

# Wait for service to be healthy
echo ""
echo "⏳ Waiting for service to be ready..."
sleep 5

# Check health
echo ""
echo "🏥 Checking service health..."
if curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Service is healthy!${NC}"
else
    echo -e "${RED}❌ Service health check failed${NC}"
    echo "Checking logs..."
    docker-compose logs --tail=50
    exit 1
fi

# Show service info
echo ""
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo ""
echo "Service Info:"
echo "  Container: $SERVICE_NAME"
echo "  Port: 8080"
echo "  Health: http://localhost:8080/health"
echo "  API Docs: http://localhost:8080/docs"
echo ""
echo "Useful Commands:"
echo "  View logs:    docker-compose logs -f"
echo "  Stop service: docker-compose down"
echo "  Restart:      docker-compose restart"
echo "  Status:       docker-compose ps"
echo ""
echo -e "${YELLOW}⚠️  Remember to configure firewall/nginx for production access${NC}"

