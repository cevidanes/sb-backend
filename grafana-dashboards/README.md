# Grafana Dashboards

Production-focused Grafana dashboards for monitoring the Second Brain backend.

## Dashboards

### 1. Backend Health Dashboard
**File**: `backend-health.json`

**Purpose**: Monitor API health, throughput, and errors

**Panels**:
- **Requests per Second**: Total request rate with breakdown by HTTP method (GET, POST)
- **Error Rate**: 4xx, 5xx, and exception errors per second
- **P95 Latency**: 95th percentile request latency (also shows P50 and P99)
- **Sessions Created vs Finalized**: Comparison of session creation and finalization rates
- **Total Sessions Created (24h)**: Stat panel showing total sessions created in last 24 hours
- **Total Sessions Finalized (24h)**: Stat panel showing total sessions finalized in last 24 hours
- **Session Completion Rate**: Percentage of created sessions that were finalized
- **Total Errors (24h)**: Total error count in last 24 hours

**Key Metrics**:
- Request rate thresholds: Green < 100 req/s, Yellow 100-500, Red > 500
- Error rate thresholds: Green < 0.1 err/s, Yellow 0.1-1, Red > 1
- Latency thresholds: Green < 0.5s, Yellow 0.5-1s, Red > 1s

### 2. AI Processing Dashboard
**File**: `ai-processing.json`

**Purpose**: Monitor Celery job processing, failures, and queue backlog

**Panels**:
- **Jobs Created vs Completed**: Time series showing job creation and completion rates by job type
- **Jobs Failed by Type**: Table showing failed jobs in last 24 hours grouped by job_type
- **Average Job Duration by Type**: Average execution time for each job type
- **Queue Backlog**: Gauge showing current queue length (thresholds: Green < 20, Yellow 20-50, Red > 50)
- **Active Jobs**: Gauge showing currently processing jobs (thresholds: Green < 5, Yellow 5-8, Red > 8)
- **Processing Throughput**: Jobs completed per second
- **Total Jobs Created (24h)**: Stat panel
- **Total Jobs Completed (24h)**: Stat panel
- **Total Jobs Failed (24h)**: Stat panel with thresholds (Green < 10, Yellow 10-50, Red > 50)
- **Success Rate**: Percentage of jobs that completed successfully

**Key Metrics**:
- Job duration thresholds: Green < 60s, Yellow 60-300s, Red > 300s
- Success rate thresholds: Red < 80%, Yellow 80-95%, Green > 95%

### 3. AI Cost Control Dashboard
**File**: `ai-cost-control.json`

**Purpose**: Track AI provider usage, costs, and failures

**Panels**:
- **Requests per Provider**: Stacked area chart showing request rate by provider (openai, deepseek, groq)
- **Failures per Provider**: Bar chart showing failure rate by provider
- **Estimated Tokens per Provider**: Token usage rate broken down by provider and token type (prompt, completion)
- **Provider Success Rate**: Table showing success rate percentage for each provider
- **Total Requests (24h) by Provider**: Stat panels showing total requests per provider
- **Total Failures (24h) by Provider**: Stat panels showing total failures per provider
- **Total Tokens Used (24h)**: Total token consumption across all providers
- **Average Latency by Provider**: Response latency comparison across providers

**Key Metrics**:
- Failure rate thresholds: Green < 0.1 req/s, Yellow 0.1-1, Red > 1
- Success rate thresholds: Red < 80%, Yellow 80-95%, Green > 95%
- Latency thresholds: Green < 2s, Yellow 2-5s, Red > 5s

## PromQL Queries Reference

### Backend Health

**Request Rate**:
```promql
sum(rate(http_requests_total[5m]))
```

**Error Rate**:
```promql
sum(rate(errors_total{error_type="4xx"}[5m]))
sum(rate(errors_total{error_type="5xx"}[5m]))
```

**P95 Latency**:
```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

**Session Metrics**:
```promql
rate(sessions_created_total[5m])
rate(sessions_finalized_total[5m])
```

### AI Processing

**Job Creation Rate**:
```promql
sum(rate(ai_jobs_created_total[5m])) by (job_type)
```

**Job Completion Rate**:
```promql
sum(rate(ai_jobs_completed_total{status="completed"}[5m])) by (job_type)
```

**Failed Jobs**:
```promql
sum(increase(ai_jobs_failed_total[24h])) by (job_type)
```

**Active Jobs**:
```promql
sum(ai_jobs_processing)
```

**Average Duration**:
```promql
avg(ai_job_duration_seconds{status="completed"}) by (job_type)
```

**Queue Backlog**:
```promql
sum(redis_queue_length)
```

### AI Cost Control

**Request Rate by Provider**:
```promql
sum(rate(ai_provider_requests_total[5m])) by (provider)
```

**Failure Rate by Provider**:
```promql
sum(rate(ai_provider_failures_total[5m])) by (provider)
```

**Token Usage**:
```promql
sum(rate(ai_provider_tokens_total[5m])) by (provider, token_type)
```

**Success Rate**:
```promql
(sum(rate(ai_provider_requests_total[5m])) by (provider) - sum(rate(ai_provider_failures_total[5m])) by (provider)) / sum(rate(ai_provider_requests_total[5m])) by (provider) * 100
```

**Average Latency**:
```promql
avg(ai_provider_latency_seconds) by (provider)
```

## Import Instructions

### Method 1: Grafana UI

1. Open Grafana (http://localhost:3001)
2. Go to **Dashboards** → **Import**
3. Click **Upload JSON file**
4. Select one of the dashboard JSON files
5. Click **Load**
6. Select Prometheus data source
7. Click **Import**

### Method 2: Grafana API

```bash
# Set Grafana credentials
GRAFANA_URL="http://localhost:3001"
GRAFANA_USER="admin"
GRAFANA_PASSWORD="admin"

# Import dashboard
curl -X POST \
  -H "Content-Type: application/json" \
  -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
  -d @backend-health.json \
  "${GRAFANA_URL}/api/dashboards/db"
```

### Method 3: Docker Volume Mount

If running Grafana in Docker, you can mount the dashboards directory:

```yaml
grafana:
  volumes:
    - ./grafana-dashboards:/etc/grafana/provisioning/dashboards
```

Then configure provisioning in Grafana.

## Configuration

### Default Settings

- **Refresh Interval**: 30 seconds
- **Time Range**: Last 24 hours
- **Data Source**: Prometheus (must be configured in Grafana)
- **Timezone**: Browser timezone

### Thresholds

Thresholds are configured per panel and use color coding:
- **Green**: Normal/healthy state
- **Yellow**: Warning state
- **Red**: Critical state

Adjust thresholds in panel settings based on your SLA requirements.

## Troubleshooting

### No Data Showing

1. Verify Prometheus is scraping targets:
   - Check Prometheus targets page: http://localhost:9091/targets
   - All targets should be UP

2. Verify metrics exist:
   ```bash
   curl http://localhost:8000/metrics | grep http_requests_total
   curl http://localhost:9090/metrics | grep ai_jobs_created_total
   ```

3. Check data source configuration:
   - Grafana → Configuration → Data Sources → Prometheus
   - URL should be: `http://prometheus:9090` (internal) or `http://localhost:9091` (external)

### Incorrect Values

1. Verify PromQL queries match your metric names
2. Check metric labels match query expectations
3. Ensure time range includes data (metrics may not exist for all time ranges)

## Notes

- Dashboards use simple time-series and stat panels for clarity
- No high-cardinality labels are used to avoid performance issues
- All queries use 5-minute rate windows for smooth visualization
- 24-hour aggregations use `increase()` function for counters

