# Deployment Commands - Quick Reference

## Prerequisites

1. **GitHub Personal Access Token (PAT)**
   - Create at: https://github.com/settings/tokens
   - Required scopes: `read:packages`
   - Save token securely

## Deployment Steps

### 1. Authenticate Docker with GHCR

```bash
ssh admin@193.180.213.104
cd ~/sb-backend

# Login to GHCR (replace YOUR_PAT with your token)
echo "YOUR_PAT" | docker login ghcr.io -u cevidanes --password-stdin
```

### 2. Set Environment Variables

```bash
# Ensure .env file exists and has GHCR_ORG and IMAGE_TAG
cd ~/sb-backend
echo "GHCR_ORG=cevidanes" >> .env
echo "IMAGE_TAG=latest" >> .env

# Verify
grep -E '^(GHCR_ORG|IMAGE_TAG)=' .env
```

### 3. Pull Latest Images

```bash
cd ~/sb-backend
docker compose pull api worker
```

### 4. Deploy Services (Zero Downtime)

**Option A: Rolling Update (Recommended)**

```bash
cd ~/sb-backend

# Start new containers without stopping old ones
docker compose up -d --no-deps api worker

# Wait for health checks
sleep 30

# Verify new containers
docker compose ps api worker

# If healthy, stop old containers
docker compose stop api worker
docker compose rm -f api worker

# Ensure all services are running
docker compose up -d
```

**Option B: Full Restart (Brief Downtime)**

```bash
cd ~/sb-backend
docker compose down
docker compose up -d
```

### 5. Validation Checklist

```bash
# 1. API Health Check
curl http://localhost:8000/api/health
# Expected: {"status":"healthy","database":"connected","redis":"connected"}

# 2. API Metrics
curl http://localhost:8000/metrics
# Should return Prometheus metrics

# 3. Worker Metrics
curl http://localhost:9090/metrics
# Should return Celery worker metrics

# 4. Prometheus Targets
curl http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
# All targets should show "up"

# 5. Grafana Health
curl http://localhost:3001/api/health
# Should return {"commit":"...","database":"ok","version":"..."}

# 6. Container Status
docker compose ps
# All services should show "Up"
```

### 6. View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f prometheus
docker compose logs -f grafana
```

## Rollback Procedure

If deployment fails:

```bash
cd ~/sb-backend

# Option 1: Use previous image tag
# Edit .env: IMAGE_TAG=sha-<previous-commit>
docker compose pull api worker
docker compose up -d --force-recreate api worker

# Option 2: Restore backup docker-compose.yml
cp docker-compose.yml.backup.* docker-compose.yml
docker compose up -d --build
```

## Troubleshooting

### Images Not Found

```bash
# Verify authentication
docker login ghcr.io

# Check image exists
docker pull ghcr.io/cevidanes/sb-api:latest
docker pull ghcr.io/cevidanes/sb-worker:latest
```

### Container Fails to Start

```bash
# Check logs
docker compose logs api
docker compose logs worker

# Check configuration
docker compose config

# Verify environment variables
cat .env | grep -v PASSWORD
```

### Metrics Not Working

```bash
# Check Prometheus config
cat prometheus.yml

# Check Prometheus targets
curl http://localhost:9091/api/v1/targets

# Check Prometheus logs
docker compose logs prometheus
```

## Quick Status Check

```bash
ssh admin@193.180.213.104 "cd ~/sb-backend && docker compose ps && echo '---' && curl -s http://localhost:8000/api/health && echo '' && echo '---' && curl -s -o /dev/null -w 'Metrics: %{http_code}\n' http://localhost:8000/metrics"
```

