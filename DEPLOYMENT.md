# Production Deployment Guide

This guide covers deploying the Second Brain backend to production using pre-built Docker images from GitHub Container Registry (GHCR).

## Prerequisites

- SSH access to VPS (admin@193.180.213.104)
- Docker and docker-compose installed on VPS
- GitHub Personal Access Token (PAT) with `read:packages` permission
- Existing `.env` file with production secrets

## Deployment Steps

### 1. SSH into VPS

```bash
ssh admin@193.180.213.104
```

### 2. Navigate to Project Directory

```bash
cd ~/sb-backend  # or wherever your project is located
```

### 3. Authenticate Docker with GHCR

You'll need a GitHub Personal Access Token (PAT) with `read:packages` permission.

```bash
# Option 1: Using PAT from environment variable (recommended)
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# Option 2: Interactive login
docker login ghcr.io -u YOUR_GITHUB_USERNAME
# Enter your PAT when prompted
```

**To create a PAT:**
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `read:packages` scope
3. Copy token and use it for login

### 4. Set Environment Variables

Add to your `.env` file:

```bash
# GitHub Container Registry organization/username
GHCR_ORG=your-github-org-or-username

# Image tag (use 'latest' or specific sha-<commit>)
IMAGE_TAG=latest
```

### 5. Backup Current docker-compose.yml

```bash
cp docker-compose.yml docker-compose.yml.backup
```

### 6. Update docker-compose.yml

Replace the current `docker-compose.yml` with the production version that uses GHCR images.

**Key changes:**
- Removed `build:` sections from `api` and `worker` services
- Added `image:` pointing to GHCR
- Removed volume mounts (`./backend:/app`) - code is baked into image
- Changed `--reload` to production mode (no reload)
- Added `restart: unless-stopped` for all services
- Changed log levels to `INFO` for production

### 7. Pull Latest Images

```bash
docker-compose pull api worker
```

### 8. Deploy with Zero Downtime

**Strategy: Rolling update**

```bash
# Step 1: Start new containers without stopping old ones
docker-compose up -d --no-deps api worker

# Step 2: Wait for health checks (30 seconds)
sleep 30

# Step 3: Verify new containers are healthy
docker-compose ps

# Step 4: Stop old containers (if any)
docker-compose stop api worker
docker-compose rm -f api worker

# Step 5: Ensure all services are running
docker-compose up -d
```

**Alternative: Full restart (brief downtime)**

```bash
# Restart services
docker-compose up -d --force-recreate api worker

# Or restart everything
docker-compose down
docker-compose up -d
```

### 9. Verify Deployment

See [Validation Checklist](#validation-checklist) below.

## Validation Checklist

### ✅ API Health Check

```bash
# From VPS
curl http://localhost:8000/api/health

# Expected response:
# {"status":"healthy","database":"connected","redis":"connected"}
```

### ✅ Metrics Endpoint

```bash
# From VPS
curl http://localhost:8000/metrics

# Should return Prometheus metrics in text format
```

### ✅ Worker Metrics Endpoint

```bash
# From VPS
curl http://localhost:9090/metrics

# Should return Celery worker metrics
```

### ✅ Prometheus Targets

```bash
# From VPS
curl http://localhost:9091/api/v1/targets

# Check that all targets are "up":
# - sb-api (api:8000)
# - sb-worker (worker:9090)
# - redis-exporter (redis-exporter:9121)
```

### ✅ Grafana Access

```bash
# From your local machine (if port forwarding)
ssh -L 3001:localhost:3001 admin@193.180.213.104

# Then open browser: http://localhost:3001
# Login: admin / (password from GRAFANA_ADMIN_PASSWORD)
```

### ✅ Container Status

```bash
docker-compose ps

# All services should show "Up" status
```

### ✅ Container Logs

```bash
# Check API logs
docker-compose logs --tail=50 api

# Check Worker logs
docker-compose logs --tail=50 worker

# Check for errors
docker-compose logs | grep -i error
```

## Rollback Procedure

If something goes wrong:

```bash
# Option 1: Rollback to previous image tag
# Edit .env: IMAGE_TAG=sha-<previous-commit>
docker-compose pull api worker
docker-compose up -d --force-recreate api worker

# Option 2: Restore backup docker-compose.yml
cp docker-compose.yml.backup docker-compose.yml
docker-compose up -d --build
```

## Updating Images

To update to a new version:

```bash
# Pull latest images
docker-compose pull api worker

# Restart services
docker-compose up -d --force-recreate api worker

# Verify
curl http://localhost:8000/api/health
```

## Troubleshooting

### Images Not Found

```bash
# Verify authentication
docker login ghcr.io

# Check image exists
docker pull ghcr.io/YOUR_ORG/sb-api:latest
```

### Container Fails to Start

```bash
# Check logs
docker-compose logs api
docker-compose logs worker

# Check environment variables
docker-compose config

# Verify .env file
cat .env | grep -v PASSWORD
```

### Metrics Not Working

```bash
# Verify Prometheus config
cat prometheus.yml

# Check Prometheus targets
curl http://localhost:9091/api/v1/targets

# Check Prometheus logs
docker-compose logs prometheus
```

## Maintenance

### View Logs

```bash
# Follow all logs
docker-compose logs -f

# Follow specific service
docker-compose logs -f api
```

### Clean Up

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes (careful!)
docker volume prune
```

### Update Observability Stack

```bash
# Pull latest Prometheus/Grafana images
docker-compose pull prometheus grafana redis-exporter

# Restart
docker-compose up -d prometheus grafana redis-exporter
```

