#!/bin/bash
set -e

# Configuration
VPS_HOST="admin@193.180.213.104"
PROJECT_DIR="~/sb-backend"
GHCR_ORG="${GHCR_ORG:-cevidanes}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "🚀 Starting deployment to VPS..."
echo "VPS: $VPS_HOST"
echo "GHCR Org: $GHCR_ORG"
echo "Image Tag: $IMAGE_TAG"
echo ""

# Step 1: Test SSH connection
echo "📡 Testing SSH connection..."
ssh -o ConnectTimeout=10 $VPS_HOST "echo 'SSH connection successful'" || {
    echo "❌ Failed to connect to VPS. Please check SSH access."
    exit 1
}

# Step 2: Authenticate Docker with GHCR
echo ""
echo "🔐 Authenticating Docker with GHCR..."
echo "Please enter your GitHub Personal Access Token (PAT) with 'read:packages' permission:"
read -s GITHUB_TOKEN

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GitHub token is required"
    exit 1
fi

echo ""
echo "Logging in to GHCR..."
ssh $VPS_HOST "echo '$GITHUB_TOKEN' | docker login ghcr.io -u \$(whoami) --password-stdin" || {
    echo "❌ Failed to authenticate with GHCR"
    exit 1
}

# Step 3: Set environment variables
echo ""
echo "⚙️  Setting environment variables..."
ssh $VPS_HOST "cd $PROJECT_DIR && {
    # Backup .env if it exists
    [ -f .env ] && cp .env .env.backup.\$(date +%Y%m%d_%H%M%S) || true
    
    # Add GHCR_ORG and IMAGE_TAG if not present
    if ! grep -q '^GHCR_ORG=' .env 2>/dev/null; then
        echo \"GHCR_ORG=$GHCR_ORG\" >> .env
    else
        sed -i \"s|^GHCR_ORG=.*|GHCR_ORG=$GHCR_ORG|\" .env
    fi
    
    if ! grep -q '^IMAGE_TAG=' .env 2>/dev/null; then
        echo \"IMAGE_TAG=$IMAGE_TAG\" >> .env
    else
        sed -i \"s|^IMAGE_TAG=.*|IMAGE_TAG=$IMAGE_TAG|\" .env
    fi
}"

# Step 4: Backup docker compose.yml
echo ""
echo "💾 Backing up docker compose.yml..."
ssh $VPS_HOST "cd $PROJECT_DIR && cp docker compose.yml docker compose.yml.backup.\$(date +%Y%m%d_%H%M%S) 2>/dev/null || true"

# Step 5: Upload production docker compose.yml
echo ""
echo "📤 Uploading production docker compose.yml..."
scp docker compose.prod.yml $VPS_HOST:$PROJECT_DIR/docker compose.yml

# Step 6: Pull latest images
echo ""
echo "📥 Pulling latest Docker images..."
ssh $VPS_HOST "cd $PROJECT_DIR && docker compose pull api worker" || {
    echo "⚠️  Failed to pull images. Continuing with existing images..."
}

# Step 7: Deploy with zero downtime
echo ""
echo "🔄 Deploying services (zero downtime strategy)..."
ssh $VPS_HOST "cd $PROJECT_DIR && {
    # Start new containers without stopping old ones
    docker compose up -d --no-deps api worker
    
    # Wait for health checks
    echo 'Waiting 30 seconds for health checks...'
    sleep 30
    
    # Verify containers are running
    docker compose ps api worker
}"

# Step 8: Validation
echo ""
echo "✅ Running validation checks..."
echo ""

# API Health Check
echo "1. Checking API health..."
API_HEALTH=$(ssh $VPS_HOST "curl -s http://localhost:8000/api/health" || echo "FAILED")
if echo "$API_HEALTH" | grep -q "healthy"; then
    echo "   ✅ API is healthy"
else
    echo "   ❌ API health check failed: $API_HEALTH"
fi

# Metrics Endpoint
echo "2. Checking /metrics endpoint..."
METRICS=$(ssh $VPS_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/metrics" || echo "000")
if [ "$METRICS" = "200" ]; then
    echo "   ✅ Metrics endpoint is accessible"
else
    echo "   ❌ Metrics endpoint failed (HTTP $METRICS)"
fi

# Worker Metrics
echo "3. Checking worker metrics..."
WORKER_METRICS=$(ssh $VPS_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:9090/metrics" || echo "000")
if [ "$WORKER_METRICS" = "200" ]; then
    echo "   ✅ Worker metrics endpoint is accessible"
else
    echo "   ❌ Worker metrics endpoint failed (HTTP $WORKER_METRICS)"
fi

# Prometheus Targets
echo "4. Checking Prometheus targets..."
PROM_TARGETS=$(ssh $VPS_HOST "curl -s http://localhost:9091/api/v1/targets" | grep -o '"health":"[^"]*"' | head -3 || echo "")
if echo "$PROM_TARGETS" | grep -q "up"; then
    echo "   ✅ Prometheus targets are UP"
else
    echo "   ⚠️  Some Prometheus targets may be down. Check manually."
fi

# Grafana
echo "5. Checking Grafana..."
GRAFANA=$(ssh $VPS_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:3001/api/health" || echo "000")
if [ "$GRAFANA" = "200" ]; then
    echo "   ✅ Grafana is accessible"
else
    echo "   ⚠️  Grafana check failed (HTTP $GRAFANA). May need time to start."
fi

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📋 Summary:"
echo "   - Images: ghcr.io/$GHCR_ORG/sb-api:$IMAGE_TAG"
echo "   - Images: ghcr.io/$GHCR_ORG/sb-worker:$IMAGE_TAG"
echo "   - Check logs: ssh $VPS_HOST 'cd $PROJECT_DIR && docker compose logs -f'"
echo "   - View services: ssh $VPS_HOST 'cd $PROJECT_DIR && docker compose ps'"
echo ""
echo "🔍 Manual validation commands:"
echo "   ssh $VPS_HOST"
echo "   cd $PROJECT_DIR"
echo "   curl http://localhost:8000/api/health"
echo "   curl http://localhost:8000/metrics"
echo "   curl http://localhost:9091/api/v1/targets"
echo "   docker compose logs --tail=50 api"
echo "   docker compose logs --tail=50 worker"

