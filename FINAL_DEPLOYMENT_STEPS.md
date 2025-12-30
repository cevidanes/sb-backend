# Final Deployment Steps

## ✅ Pre-Deployment Checklist

- [x] `docker-compose.yml` updated to use GHCR images
- [x] `prometheus.yml` uploaded and configured
- [x] Environment variables set (`GHCR_ORG=cevidanes`, `IMAGE_TAG=latest`)
- [x] Backup created
- [ ] **Docker authenticated with GHCR** ← **YOU ARE HERE**
- [ ] Images pulled
- [ ] Services deployed
- [ ] Validation complete

## Step 1: Authenticate Docker with GHCR

**You need a GitHub Personal Access Token (PAT) with `read:packages` permission.**

### Create PAT:
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Name: `GHCR Docker Login`
4. Expiration: Choose appropriate (90 days recommended)
5. Scopes: Check `read:packages`
6. Click "Generate token"
7. **Copy the token immediately** (you won't see it again)

### Authenticate:
```bash
ssh admin@193.180.213.104
cd ~/sb-backend

# Login to GHCR (replace YOUR_PAT with the token you copied)
echo "YOUR_PAT" | docker login ghcr.io -u cevidanes --password-stdin
```

**Expected output:**
```
Login Succeeded
```

## Step 2: Pull Docker Images

```bash
cd ~/sb-backend
docker compose pull api worker
```

**Expected output:**
```
Pulling api   ... done
Pulling worker ... done
```

## Step 3: Deploy Services

```bash
cd ~/sb-backend

# Start all services (including observability)
docker compose up -d

# Wait for services to initialize
sleep 30

# Check status
docker compose ps
```

**Expected output:**
```
NAME                IMAGE                                    STATUS
sb-api              ghcr.io/cevidanes/sb-api:latest         Up
sb-worker           ghcr.io/cevidanes/sb-worker:latest      Up
sb-redis            redis:7-alpine                          Up
sb-prometheus       prom/prometheus:latest                   Up
sb-grafana          grafana/grafana:latest                   Up
sb-redis-exporter   oliver006/redis_exporter:latest         Up
```

## Step 4: Validation Checklist

Run these commands to validate the deployment:

### ✅ 1. API Health Check
```bash
curl http://localhost:8000/api/health
```
**Expected:** `{"status":"healthy","database":"connected","redis":"connected"}`

### ✅ 2. API Metrics Endpoint
```bash
curl http://localhost:8000/metrics | head -20
```
**Expected:** Prometheus metrics in text format starting with `# HELP`

### ✅ 3. Worker Metrics Endpoint
```bash
curl http://localhost:9090/metrics | head -20
```
**Expected:** Celery worker metrics in Prometheus format

### ✅ 4. Prometheus Targets
```bash
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```
**Expected:** All targets showing `"health":"up"`

**Or without jq:**
```bash
curl -s http://localhost:9091/api/v1/targets | grep -o '"health":"[^"]*"'
```
**Expected:** Multiple `"health":"up"` entries

### ✅ 5. Grafana Health
```bash
curl http://localhost:3001/api/health
```
**Expected:** JSON response with `"database":"ok"`

### ✅ 6. Container Status
```bash
docker compose ps
```
**Expected:** All containers showing `Up` status

### ✅ 7. Check Logs (No Errors)
```bash
docker compose logs --tail=50 api | grep -i error
docker compose logs --tail=50 worker | grep -i error
```
**Expected:** No critical errors (warnings are OK)

## Quick Validation Script

Run this to check everything at once:

```bash
cd ~/sb-backend

echo "=== API Health ==="
curl -s http://localhost:8000/api/health && echo ""

echo "=== API Metrics ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/metrics

echo "=== Worker Metrics ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:9090/metrics

echo "=== Prometheus Targets ==="
curl -s http://localhost:9091/api/v1/targets | grep -o '"health":"[^"]*"' | sort | uniq -c

echo "=== Grafana ==="
curl -s http://localhost:3001/api/health | jq -r '.database' || echo "Check manually"

echo "=== Container Status ==="
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
```

## Troubleshooting

### Images Not Found / Authentication Failed

```bash
# Verify authentication
docker login ghcr.io

# Check if images exist (from your local machine)
curl -H "Authorization: Bearer YOUR_PAT" https://ghcr.io/v2/cevidanes/sb-api/manifests/latest

# Re-authenticate if needed
echo "YOUR_PAT" | docker login ghcr.io -u cevidanes --password-stdin
```

### Containers Fail to Start

```bash
# Check logs
docker compose logs api
docker compose logs worker

# Check configuration
docker compose config

# Verify environment variables
cat .env | grep -E '^(GHCR_ORG|IMAGE_TAG)='

# Check if images exist locally
docker images | grep ghcr.io/cevidanes
```

### Metrics Not Working

```bash
# Check Prometheus config
cat prometheus.yml

# Check Prometheus logs
docker compose logs prometheus

# Check if targets are reachable
docker compose exec prometheus wget -qO- http://api:8000/metrics | head -5
docker compose exec prometheus wget -qO- http://worker:9090/metrics | head -5
```

### API Not Responding

```bash
# Check API logs
docker compose logs --tail=100 api

# Check if API container is running
docker compose ps api

# Check API health from inside container
docker compose exec api curl http://localhost:8000/api/health

# Check database connection
docker compose logs api | grep -i "database\|postgres\|connection"
```

## Rollback Procedure

If something goes wrong:

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

## Success Criteria

Deployment is successful when:
- ✅ All containers are running (`docker compose ps` shows all `Up`)
- ✅ API health check returns `healthy`
- ✅ `/metrics` endpoints return HTTP 200
- ✅ Prometheus shows all targets as `up`
- ✅ Grafana is accessible
- ✅ No critical errors in logs

## Next Steps After Deployment

1. **Access Grafana**: http://193.180.213.104:3001 (if firewall allows)
   - Default login: `admin` / (password from `GRAFANA_ADMIN_PASSWORD`)
   - Add Prometheus data source: `http://prometheus:9090`

2. **Access Prometheus**: http://193.180.213.104:9091 (if firewall allows)
   - Check targets: Status → Targets
   - Run queries: Graph tab

3. **Monitor Logs**:
   ```bash
   docker compose logs -f
   ```

4. **Set up Grafana Dashboards**:
   - Import dashboards from `grafana-dashboards/` directory
   - See `grafana-dashboards/README.md` for instructions

## Support

If you encounter issues:
1. Check logs: `docker compose logs -f`
2. Verify configuration: `docker compose config`
3. Check Prometheus targets: `curl http://localhost:9091/api/v1/targets`
4. Review this guide's troubleshooting section

