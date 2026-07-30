# Backup and restore runbook

## Backup

Daily automated backup:

```bash
# Postgres
docker compose exec db pg_dump -U tendershield tendershield > backup-$(date +%F).sql

# Object storage (MinIO/S3 compatible)
mc mirror myminio/tendershield ./storage-backup-$(date +%F)
```

Verify backup integrity by restoring to a temporary Postgres container and running `alembic upgrade head`.

## Restore

1. Stop frontend/backend traffic.
2. Restore Postgres from the latest verified dump.
3. Sync object storage back to bucket.
4. Run `alembic upgrade head` to ensure migrations are applied.
5. Run `pytest` smoke tests and verify `/api/health`.
6. Re-enable traffic.

## Rollback

For docker compose deployments, tag the previous image and run:

```bash
docker compose pull
docker compose up -d --no-deps --build backend frontend
```

For Kubernetes, use the previous deployment revision:

```bash
kubectl rollout undo deployment/tendershield-backend
kubectl rollout undo deployment/tendershield-frontend
```
