# Deployment Summary

## ✅ Completed Steps

1. ✅ **Files Uploaded to VPS**
   - `prometheus.yml` - Prometheus configuration
   - `docker-compose.yml` - Production docker-compose using GHCR images
   - Backup created: `docker-compose.yml.backup.*`

2. ✅ **Docker Compose Updated**
   - Removed `build:` sections from `api` and `worker`
   - Added `image:` pointing to `ghcr.io/cevidanes/sb-api:latest` and `ghcr.io/cevidanes/sb-worker:latest`
   - Removed volume mounts (`./backend:/app`) - code is baked into images
   - Changed `--reload` to production mode
   - Added `restart: unless-stopped` for all services
   - Changed log levels to `INFO` for production
   - Observability services (Prometheus, Grafana, redis-exporter) already configured

3. ✅ **Configuration Ready**
   - `prometheus.yml` updated with correct service names
   - Environment variables ready to be set in `.env`

## 🔄 Next Steps (Manual)

### Step 1: Authenticate Docker with GHCR

**You need a GitHub Personal Access Token (PAT) with `read:packages` permission.**

```bash
ssh admin@193.180.213.104
cd ~/sb-backend

# Create PAT at: https://github.com/settings/tokens
# Then login:
echo "YOUR_GITHUB_PAT" | docker login ghcr.io -u cevidanes --password-stdin
```

### Step 2: Set Environment Variables

```bash
cd ~/sb-backend

# Create/update .env file
cat >> .env << EOF
GHCR_ORG=cevidanes
IMAGE_TAG=latest
EOF

# Verify
grep -E '^(GHCR_ORG|IMAGE_TAG)=' .env
```

### Step 3: Pull and Deploy

```bash
cd ~/sb-backend

# Pull latest images
docker compose pull api worker

# Start all services
docker compose up -d

# Wait for services to start
sleep 30

# Check status
docker compose ps
```

### Step 4: Validate Deployment

Run these validation checks:

```bash
# 1. API Health
curl http://localhost:8000/api/health
# Expected: {"status":"healthy","database":"connected","redis":"connected"}

# 2. API Metrics
curl http://localhost:8000/metrics | head -20
# Should show Prometheus metrics

# 3. Worker Metrics  
curl http://localhost:9090/metrics | head -20
# Should show Celery worker metrics

# 4. Prometheus Targets
curl -s http://localhost:9091/api/v1/targets | grep -o '"health":"[^"]*"' | head -5
# Should show "up" for all targets

# 5. Grafana
curl http://localhost:3001/api/health
# Should return JSON with status

# 6. Container Status
docker compose ps
# All should show "Up"
```

## 📋 Validation Checklist

- [ ] Docker authenticated with GHCR
- [ ] Environment variables set (GHCR_ORG, IMAGE_TAG)
- [ ] Images pulled successfully
- [ ] All containers running (`docker compose ps`)
- [ ] API health check passes (`/api/health`)
- [ ] API metrics endpoint accessible (`/metrics`)
- [ ] Worker metrics endpoint accessible (`:9090/metrics`)
- [ ] Prometheus targets UP (check `/api/v1/targets`)
- [ ] Grafana accessible (`:3001`)
- [ ] No errors in logs (`docker compose logs`)

## 🚨 Important Notes

1. **GitHub Images Must Exist**: Make sure images are built and pushed to GHCR first:
   - `ghcr.io/cevidanes/sb-api:latest`
   - `ghcr.io/cevidanes/sb-worker:latest`
   
   If images don't exist yet, push to `main` branch to trigger CI/CD workflow.

2. **No Database Reset**: Database and volumes are preserved. Only containers are updated.

3. **Secrets Preserved**: `.env` file with secrets is not modified (only GHCR_ORG and IMAGE_TAG added).

4. **Zero Downtime**: Since no containers were running, this is a clean deployment with no downtime.

## 📚 Additional Resources

- **Deployment Guide**: See `DEPLOYMENT.md` for detailed instructions
- **Quick Commands**: See `DEPLOYMENT_COMMANDS.md` for command reference
- **Rollback**: See rollback section in `DEPLOYMENT.md`

## 🔍 Troubleshooting

If images are not found:
```bash
# Verify images exist in GHCR
docker pull ghcr.io/cevidanes/sb-api:latest
docker pull ghcr.io/cevidanes/sb-worker:latest
```

If containers fail to start:
```bash
# Check logs
docker compose logs api
docker compose logs worker

# Check configuration
docker compose config
```

## 📞 Support

For issues:
1. Check logs: `docker compose logs -f`
2. Verify configuration: `docker compose config`
3. Check Prometheus targets: `curl http://localhost:9091/api/v1/targets`

