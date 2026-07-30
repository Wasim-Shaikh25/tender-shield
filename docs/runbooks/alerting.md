# Alerting and operational runbooks

## Default alert thresholds

| Alert | Threshold | Source | Runbook |
|---|---|---|---|
| `ErrorRateHigh` | HTTP 5xx rate > 0.1% over 5 minutes | Prometheus `http_requests_total{status=~"5.."}` | See "Investigate 5xx spike" below |
| `ErrorRateCritical` | HTTP 5xx rate > 1% over 5 minutes | Prometheus `http_requests_total{status=~"5.."}` | Escalate on-call |
| `DeadlineDigestFailing` | `deadline_alert_tick` job has not completed in 25 hours | Scheduler heartbeat metric | Check scheduler, Celery worker, Redis lock |
| `StorageHigh` | Disk usage > 85% | Node exporter | Scale storage or prune old exports |
| `DBPoolSaturation` | Waiting connections > 80% of `pool_size` for 5 minutes | SQLAlchemy/Postgres metrics | Restart workers or scale Postgres |

## Investigate 5xx spike

1. Check `/api/health/details` as super-admin for failing dependencies.
2. Review Sentry / structured logs for `request_id` of 5xx responses.
3. If dependency (DB, Redis, MinIO) is failing, follow dependency runbook.
4. Roll back to previous deployment image if code regression suspected.

## Silencing policy

Alert silencing in production requires an audit-logged change request. Do not silence without approval.
