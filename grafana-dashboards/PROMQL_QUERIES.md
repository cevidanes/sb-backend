# PromQL Queries Reference

Complete reference of all PromQL queries used in the Grafana dashboards.

## Backend Health Dashboard

### Requests per Second
**Panel**: Requests per Second (Time Series)

**Queries**:
```promql
# Total request rate
sum(rate(http_requests_total[5m]))

# GET requests
sum(rate(http_requests_total{method="GET"}[5m]))

# POST requests
sum(rate(http_requests_total{method="POST"}[5m]))
```

**Description**: Shows total HTTP request rate and breakdown by method. Helps identify traffic patterns and peak usage times.

**Thresholds**: 
- Green: < 100 req/s
- Yellow: 100-500 req/s
- Red: > 500 req/s

---

### Error Rate
**Panel**: Error Rate (Time Series)

**Queries**:
```promql
# 4xx errors per second
sum(rate(errors_total{error_type="4xx"}[5m]))

# 5xx errors per second
sum(rate(errors_total{error_type="5xx"}[5m]))

# Exceptions per second
sum(rate(errors_total{error_type="exception"}[5m]))
```

**Description**: Tracks error rates by type. 4xx indicates client errors, 5xx indicates server errors, exceptions indicate unhandled errors.

**Thresholds**:
- Green: < 0.1 err/s
- Yellow: 0.1-1 err/s
- Red: > 1 err/s

---

### P95 Latency
**Panel**: P95 Latency (Time Series)

**Queries**:
```promql
# 95th percentile latency
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# 50th percentile (median)
histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# 99th percentile
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

**Description**: Shows latency percentiles. P95 is the latency that 95% of requests are faster than. Critical for understanding user experience.

**Thresholds**:
- Green: < 0.5s
- Yellow: 0.5-1s
- Red: > 1s

---

### Sessions Created vs Finalized
**Panel**: Sessions Created vs Finalized (Time Series)

**Queries**:
```promql
# Sessions created per second
rate(sessions_created_total[5m])

# Sessions finalized per second
rate(sessions_finalized_total[5m])
```

**Description**: Compares session creation and finalization rates. A large gap indicates sessions are being created but not finalized (possibly due to credit issues or user abandonment).

---

### Total Sessions Created (24h)
**Panel**: Total Sessions Created (24h) (Stat)

**Query**:
```promql
sum(increase(sessions_created_total[24h]))
```

**Description**: Total number of sessions created in the last 24 hours.

---

### Total Sessions Finalized (24h)
**Panel**: Total Sessions Finalized (24h) (Stat)

**Query**:
```promql
sum(increase(sessions_finalized_total[24h]))
```

**Description**: Total number of sessions finalized in the last 24 hours.

---

### Session Completion Rate
**Panel**: Session Completion Rate (Stat)

**Query**:
```promql
sum(rate(sessions_finalized_total[5m])) / sum(rate(sessions_created_total[5m])) * 100
```

**Description**: Percentage of created sessions that were finalized. Low rates may indicate credit issues or user abandonment.

**Thresholds**:
- Red: < 50%
- Yellow: 50-80%
- Green: > 80%

---

### Total Errors (24h)
**Panel**: Total Errors (24h) (Stat)

**Query**:
```promql
sum(increase(errors_total[24h]))
```

**Description**: Total error count in the last 24 hours across all error types.

**Thresholds**:
- Green: < 100
- Yellow: 100-1000
- Red: > 1000

---

## AI Processing Dashboard

### Jobs Created vs Completed
**Panel**: Jobs Created vs Completed (Time Series)

**Queries**:
```promql
# Job creation rate by type
sum(rate(ai_jobs_created_total[5m])) by (job_type)

# Job completion rate by type
sum(rate(ai_jobs_completed_total{status="completed"}[5m])) by (job_type)
```

**Description**: Shows job creation and completion rates by job type. Helps identify bottlenecks in specific job types.

---

### Jobs Failed by Type
**Panel**: Jobs Failed by Type (Table)

**Query**:
```promql
sum(increase(ai_jobs_failed_total[24h])) by (job_type)
```

**Description**: Total failed jobs in last 24 hours grouped by job type. Helps identify which job types are failing most frequently.

**Thresholds**:
- Green: < 10
- Yellow: 10-50
- Red: > 50

---

### Average Job Duration by Type
**Panel**: Average Job Duration by Type (Time Series)

**Query**:
```promql
avg(ai_job_duration_seconds{status="completed"}) by (job_type)
```

**Description**: Average execution time for each job type. Helps identify slow jobs that may need optimization.

**Thresholds**:
- Green: < 60s
- Yellow: 60-300s
- Red: > 300s

---

### Queue Backlog
**Panel**: Queue Backlog (Gauge)

**Query**:
```promql
sum(redis_queue_length)
```

**Description**: Current number of jobs waiting in the queue. High backlog indicates workers are overloaded or not processing fast enough.

**Thresholds**:
- Green: < 20
- Yellow: 20-50
- Red: > 50

---

### Active Jobs
**Panel**: Active Jobs (Gauge)

**Query**:
```promql
sum(ai_jobs_processing)
```

**Description**: Number of jobs currently being processed. Should match worker concurrency settings.

**Thresholds**:
- Green: < 5
- Yellow: 5-8
- Red: > 8

---

### Processing Throughput
**Panel**: Processing Throughput (Time Series)

**Query**:
```promql
sum(rate(ai_jobs_completed_total{status="completed"}[5m]))
```

**Description**: Jobs completed per second. Shows overall processing capacity.

---

### Total Jobs Created (24h)
**Panel**: Total Jobs Created (24h) (Stat)

**Query**:
```promql
sum(increase(ai_jobs_created_total[24h]))
```

**Description**: Total jobs created in last 24 hours.

---

### Total Jobs Completed (24h)
**Panel**: Total Jobs Completed (24h) (Stat)

**Query**:
```promql
sum(increase(ai_jobs_completed_total{status="completed"}[24h]))
```

**Description**: Total jobs completed successfully in last 24 hours.

---

### Total Jobs Failed (24h)
**Panel**: Total Jobs Failed (24h) (Stat)

**Query**:
```promql
sum(increase(ai_jobs_failed_total[24h]))
```

**Description**: Total jobs that failed in last 24 hours.

**Thresholds**:
- Green: < 10
- Yellow: 10-50
- Red: > 50

---

### Success Rate
**Panel**: Success Rate (Stat)

**Query**:
```promql
sum(rate(ai_jobs_completed_total{status="completed"}[5m])) / sum(rate(ai_jobs_created_total[5m])) * 100
```

**Description**: Percentage of jobs that completed successfully. Critical metric for system reliability.

**Thresholds**:
- Red: < 80%
- Yellow: 80-95%
- Green: > 95%

---

## AI Cost Control Dashboard

### Requests per Provider
**Panel**: Requests per Provider (Time Series - Stacked Area)

**Query**:
```promql
sum(rate(ai_provider_requests_total[5m])) by (provider)
```

**Description**: Request rate by AI provider (openai, deepseek, groq). Stacked area shows total usage and provider distribution.

---

### Failures per Provider
**Panel**: Failures per Provider (Bar Chart)

**Query**:
```promql
sum(rate(ai_provider_failures_total[5m])) by (provider)
```

**Description**: Failure rate by provider. Helps identify unreliable providers.

**Thresholds**:
- Green: < 0.1 req/s
- Yellow: 0.1-1 req/s
- Red: > 1 req/s

---

### Estimated Tokens per Provider
**Panel**: Estimated Tokens per Provider (Time Series)

**Query**:
```promql
sum(rate(ai_provider_tokens_total[5m])) by (provider, token_type)
```

**Description**: Token consumption rate broken down by provider and token type (prompt, completion). Critical for cost estimation.

---

### Provider Success Rate
**Panel**: Provider Success Rate (Table)

**Query**:
```promql
(sum(rate(ai_provider_requests_total[5m])) by (provider) - sum(rate(ai_provider_failures_total[5m])) by (provider)) / sum(rate(ai_provider_requests_total[5m])) by (provider) * 100
```

**Description**: Success rate percentage for each provider. Helps compare provider reliability.

**Thresholds**:
- Red: < 80%
- Yellow: 80-95%
- Green: > 95%

---

### Total Requests (24h) by Provider
**Panel**: Total Requests (24h) by Provider (Stat)

**Query**:
```promql
sum(increase(ai_provider_requests_total[24h])) by (provider)
```

**Description**: Total requests per provider in last 24 hours. Shows usage distribution.

---

### Total Failures (24h) by Provider
**Panel**: Total Failures (24h) by Provider (Stat)

**Query**:
```promql
sum(increase(ai_provider_failures_total[24h])) by (provider)
```

**Description**: Total failures per provider in last 24 hours.

**Thresholds**:
- Green: < 10
- Yellow: 10-100
- Red: > 100

---

### Total Tokens Used (24h)
**Panel**: Total Tokens Used (24h) (Stat)

**Query**:
```promql
sum(increase(ai_provider_tokens_total[24h]))
```

**Description**: Total tokens consumed across all providers in last 24 hours. Use for cost estimation.

---

### Average Latency by Provider
**Panel**: Average Latency by Provider (Time Series)

**Query**:
```promql
avg(ai_provider_latency_seconds) by (provider)
```

**Description**: Average response latency by provider. Helps compare provider performance.

**Thresholds**:
- Green: < 2s
- Yellow: 2-5s
- Red: > 5s

---

## Query Patterns

### Rate Calculation
All rate queries use a 5-minute window `[5m]` for smooth visualization:
```promql
rate(metric_name[5m])
```

### Counter Increase
For 24-hour totals, use `increase()`:
```promql
increase(metric_name[24h])
```

### Histogram Quantiles
For latency percentiles:
```promql
histogram_quantile(0.95, sum(rate(histogram_bucket[5m])) by (le))
```

### Aggregation by Label
Group metrics by specific labels:
```promql
sum(rate(metric[5m])) by (label_name)
```

### Success Rate Calculation
Calculate success rate as percentage:
```promql
(success_rate - failure_rate) / total_rate * 100
```

## Notes

- All queries use 5-minute rate windows for consistency
- 24-hour aggregations use `increase()` for counter metrics
- Histogram queries require `by (le)` for quantile calculations
- Label selectors can be added to filter specific values: `{label="value"}`
- Use `sum()` to aggregate across all instances/labels
- Use `by (label)` to group by specific dimensions

