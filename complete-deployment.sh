#!/bin/bash
set -e

VPS_HOST="admin@193.180.213.104"
PROJECT_DIR="~/sb-backend"

echo "🚀 Completing Deployment to VPS"
echo "=================================="
echo ""

# Step 1: Verify docker-compose.yml
echo "✅ Step 1: Verifying docker-compose.yml..."
ssh $VPS_HOST "cd $PROJECT_DIR && docker compose config --quiet && echo 'docker-compose.yml is valid'"

# Step 2: Check if Docker is authenticated
echo ""
echo "🔐 Step 2: Checking Docker authentication..."
AUTH_CHECK=$(ssh $VPS_HOST "cat ~/.docker/config.json 2>/dev/null | grep -q 'ghcr.io' && echo 'authenticated' || echo 'not_authenticated'")

if [ "$AUTH_CHECK" = "authenticated" ]; then
    echo "✅ Docker is already authenticated with GHCR"
else
    echo "⚠️  Docker is not authenticated with GHCR"
    echo ""
    echo "To authenticate, run:"
    echo "  ssh $VPS_HOST"
    echo "  echo 'YOUR_GITHUB_PAT' | docker login ghcr.io -u cevidanes --password-stdin"
    echo ""
    echo "Create a PAT at: https://github.com/settings/tokens"
    echo "Required scope: read:packages"
    echo ""
    read -p "Have you authenticated Docker? (y/n): " AUTH_CONFIRM
    if [ "$AUTH_CONFIRM" != "y" ]; then
        echo "Please authenticate Docker first, then run this script again."
        exit 1
    fi
fi

# Step 3: Pull images
echo ""
echo "📥 Step 3: Pulling Docker images..."
ssh $VPS_HOST "cd $PROJECT_DIR && docker compose pull api worker" || {
    echo "⚠️  Warning: Failed to pull images. They may not exist yet."
    echo "   Make sure CI/CD has built and pushed images to GHCR."
    echo "   Check: https://github.com/cevidanes/sb-backend/actions"
    read -p "Continue anyway? (y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        exit 1
    fi
}

# Step 4: Deploy services
echo ""
echo "🔄 Step 4: Deploying services..."
ssh $VPS_HOST "cd $PROJECT_DIR && {
    echo 'Starting all services...'
    docker compose up -d
    
    echo 'Waiting 30 seconds for services to start...'
    sleep 30
    
    echo ''
    echo 'Container status:'
    docker compose ps
}"

# Step 5: Validation
echo ""
echo "✅ Step 5: Running validation checks..."
echo ""

# API Health
echo "1. API Health Check..."
API_HEALTH=$(ssh $VPS_HOST "curl -s http://localhost:8000/api/health 2>/dev/null || echo 'FAILED'")
if echo "$API_HEALTH" | grep -q "healthy"; then
    echo "   ✅ API is healthy: $API_HEALTH"
else
    echo "   ❌ API health check failed: $API_HEALTH"
    echo "   Check logs: ssh $VPS_HOST 'cd $PROJECT_DIR && docker compose logs api'"
fi

# Metrics
echo ""
echo "2. API Metrics Endpoint..."
METRICS_CODE=$(ssh $VPS_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/metrics 2>/dev/null || echo '000'")
if [ "$METRICS_CODE" = "200" ]; then
    echo "   ✅ Metrics endpoint accessible (HTTP $METRICS_CODE)"
    METRICS_SAMPLE=$(ssh $VPS_HOST "curl -s http://localhost:8000/metrics 2>/dev/null | head -3")
    echo "   Sample: $METRICS_SAMPLE"
else
    echo "   ❌ Metrics endpoint failed (HTTP $METRICS_CODE)"
fi

# Worker Metrics
echo ""
echo "3. Worker Metrics Endpoint..."
WORKER_CODE=$(ssh $VPS_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:9090/metrics 2>/dev/null || echo '000'")
if [ "$WORKER_CODE" = "200" ]; then
    echo "   ✅ Worker metrics accessible (HTTP $WORKER_CODE)"
else
    echo "   ❌ Worker metrics failed (HTTP $WORKER_CODE)"
fi

# Prometheus Targets
echo ""
echo "4. Prometheus Targets..."
PROM_TARGETS=$(ssh $VPS_HOST "curl -s http://localhost:9091/api/v1/targets 2>/dev/null | grep -o '\"health\":\"[^\"]*\"' | head -5 || echo ''")
if echo "$PROM_TARGETS" | grep -q "up"; then
    echo "   ✅ Prometheus targets UP"
    echo "   Targets: $PROM_TARGETS"
else
    echo "   ⚠️  Prometheus targets: $PROM_TARGETS"
    echo "   Check: ssh $VPS_HOST 'curl -s http://localhost:9091/api/v1/targets | jq .'"
fi

# Grafana
echo ""
echo "5. Grafana Health..."
GRAFANA_CODE=$(ssh $VPS_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:3001/api/health 2>/dev/null || echo '000'")
if [ "$GRAFANA_CODE" = "200" ]; then
    echo "   ✅ Grafana accessible (HTTP $GRAFANA_CODE)"
    GRAFANA_HEALTH=$(ssh $VPS_HOST "curl -s http://localhost:3001/api/health 2>/dev/null")
    echo "   Health: $GRAFANA_HEALTH"
else
    echo "   ⚠️  Grafana check (HTTP $GRAFANA_CODE) - may need more time to start"
fi

# Container Status
echo ""
echo "6. Container Status..."
CONTAINER_STATUS=$(ssh $VPS_HOST "cd $PROJECT_DIR && docker compose ps --format json 2>/dev/null | jq -r '.[] | \"\(.Name): \(.State)\"' || docker compose ps")
echo "$CONTAINER_STATUS"

echo ""
echo "🎉 Deployment Complete!"
echo ""
echo "📋 Summary:"
echo "   - Services deployed from: ghcr.io/cevidanes/sb-api:latest"
echo "   - Services deployed from: ghcr.io/cevidanes/sb-worker:latest"
echo "   - Observability: Prometheus (9091), Grafana (3001), Redis Exporter (9121)"
echo ""
echo "🔍 Useful Commands:"
echo "   ssh $VPS_HOST 'cd $PROJECT_DIR && docker compose logs -f'"
echo "   ssh $VPS_HOST 'cd $PROJECT_DIR && docker compose ps'"
echo "   ssh $VPS_HOST 'curl http://localhost:8000/api/health'"
echo "   ssh $VPS_HOST 'curl http://localhost:9091/api/v1/targets'"

