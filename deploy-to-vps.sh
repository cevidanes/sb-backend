#!/bin/bash
set -e

VPS_HOST="admin@193.180.213.104"
PROJECT_DIR="~/sb-backend"
GHCR_ORG="cevidanes"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "🚀 Deploying to VPS: $VPS_HOST"
echo "📦 GHCR Org: $GHCR_ORG"
echo "🏷️  Image Tag: $IMAGE_TAG"
echo ""

# Step 1: Upload prometheus.yml
echo "📤 Uploading prometheus.yml..."
scp prometheus.yml $VPS_HOST:$PROJECT_DIR/prometheus.yml

# Step 2: Upload docker-compose.prod.yml
echo "📤 Uploading docker-compose.yml..."
scp docker-compose.prod.yml $VPS_HOST:$PROJECT_DIR/docker-compose.yml

# Step 3: Set environment variables on VPS
echo "⚙️  Setting environment variables..."
ssh $VPS_HOST "cd $PROJECT_DIR && {
    # Create .env if it doesn't exist
    [ -f .env ] || touch .env
    
    # Add/update GHCR_ORG
    if grep -q '^GHCR_ORG=' .env 2>/dev/null; then
        sed -i \"s|^GHCR_ORG=.*|GHCR_ORG=$GHCR_ORG|\" .env
    else
        echo \"GHCR_ORG=$GHCR_ORG\" >> .env
    fi
    
    # Add/update IMAGE_TAG
    if grep -q '^IMAGE_TAG=' .env 2>/dev/null; then
        sed -i \"s|^IMAGE_TAG=.*|IMAGE_TAG=$IMAGE_TAG|\" .env
    else
        echo \"IMAGE_TAG=$IMAGE_TAG\" >> .env
    fi
    
    echo 'Environment variables set:'
    grep -E '^(GHCR_ORG|IMAGE_TAG)=' .env || true
}"

# Step 4: Authenticate with GHCR
echo ""
echo "🔐 Docker GHCR Authentication"
echo "Please provide your GitHub Personal Access Token (PAT) with 'read:packages' permission:"
echo "You can create one at: https://github.com/settings/tokens"
read -s GITHUB_TOKEN

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GitHub token is required"
    exit 1
fi

echo ""
echo "Logging in to GHCR..."
ssh $VPS_HOST "echo '$GITHUB_TOKEN' | docker login ghcr.io -u $GHCR_ORG --password-stdin" || {
    echo "❌ Failed to authenticate with GHCR"
    exit 1
}

# Step 5: Pull latest images
echo ""
echo "📥 Pulling latest Docker images..."
ssh $VPS_HOST "cd $PROJECT_DIR && docker compose pull api worker" || {
    echo "⚠️  Warning: Failed to pull some images. They may not exist yet."
    echo "   Make sure images are built and pushed to GHCR first."
}

# Step 6: Deploy services
echo ""
echo "🔄 Deploying services..."
ssh $VPS_HOST "cd $PROJECT_DIR && {
    # Start all services (including observability)
    docker compose up -d
    
    # Wait for services to start
    echo 'Waiting 30 seconds for services to start...'
    sleep 30
    
    # Show status
    docker compose ps
}"

# Step 7: Validation
echo ""
echo "✅ Running validation checks..."
echo ""

# API Health
echo "1. API Health Check..."
API_HEALTH=$(ssh $VPS_HOST "curl -s http://localhost:8000/api/health 2>/dev/null || echo 'FAILED'")
if echo "$API_HEALTH" | grep -q "healthy"; then
    echo "   ✅ API is healthy: $API_HEALTH"
else
    echo "   ❌ API health check failed: $API_HEALTH"
fi

# Metrics
echo "2. API Metrics Endpoint..."
METRICS_CODE=$(ssh $VPS_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/metrics 2>/dev/null || echo '000'")
if [ "$METRICS_CODE" = "200" ]; then
    echo "   ✅ Metrics endpoint accessible (HTTP $METRICS_CODE)"
else
    echo "   ❌ Metrics endpoint failed (HTTP $METRICS_CODE)"
fi

# Worker Metrics
echo "3. Worker Metrics Endpoint..."
WORKER_CODE=$(ssh $VPS_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:9090/metrics 2>/dev/null || echo '000'")
if [ "$WORKER_CODE" = "200" ]; then
    echo "   ✅ Worker metrics accessible (HTTP $WORKER_CODE)"
else
    echo "   ❌ Worker metrics failed (HTTP $WORKER_CODE)"
fi

# Prometheus Targets
echo "4. Prometheus Targets..."
PROM_TARGETS=$(ssh $VPS_HOST "curl -s http://localhost:9091/api/v1/targets 2>/dev/null | grep -o '\"health\":\"[^\"]*\"' | head -5 || echo ''")
if echo "$PROM_TARGETS" | grep -q "up"; then
    echo "   ✅ Prometheus targets UP"
    echo "   Targets: $PROM_TARGETS"
else
    echo "   ⚠️  Prometheus targets status: $PROM_TARGETS"
fi

# Grafana
echo "5. Grafana..."
GRAFANA_CODE=$(ssh $VPS_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:3001/api/health 2>/dev/null || echo '000'")
if [ "$GRAFANA_CODE" = "200" ]; then
    echo "   ✅ Grafana accessible (HTTP $GRAFANA_CODE)"
else
    echo "   ⚠️  Grafana check (HTTP $GRAFANA_CODE) - may need more time to start"
fi

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📋 Next Steps:"
echo "   - Check logs: ssh $VPS_HOST 'cd $PROJECT_DIR && docker compose logs -f'"
echo "   - View services: ssh $VPS_HOST 'cd $PROJECT_DIR && docker compose ps'"
echo "   - Access Grafana: http://193.180.213.104:3001 (if firewall allows)"
echo "   - Access Prometheus: http://193.180.213.104:9091 (if firewall allows)"

