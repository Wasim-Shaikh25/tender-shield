# TS-106 — S3 storage adapter; extend the `Storage` protocol with get/delete/presign

**Status:** todo
**Requirement:** [R-016 §B](../../specs/requirements/R-016-platform-scale.md)
**Spec(s) updated:** `specs/modules/ingestion.md` (to be updated when built)
**Module(s):** `ingestion`
**Severity / Gate:** P1 · Gate 4

## What this builds

`ingestion/storage.py`'s own docstring describes an S3 backend that doesn't
exist — only `LocalStorage` is implemented. Consequences: horizontal
scaling breaks (each replica sees only its own uploads), a container
replacement loses documents, and there's no encryption at rest or
ap-south-1 residency guarantee (an explicit NFR).

## Current (the gap)

```python
# backend/app/modules/ingestion/storage.py:1 (current)
"""File storage abstraction. LocalStorage writes to a per-org directory and
is the dev/test backend; an S3 backend (SSE-KMS, per-org prefix, Doc §11.2)
is the production adapter behind the same interface."""
# ^ describes a backend that was never actually built
```

## Implementation (reference plan — not yet built)

```python
# backend/app/modules/ingestion/storage_s3.py
class S3Storage:
    """S3-compatible (AWS S3, MinIO). Per-workspace key prefix, SSE-KMS at
    rest, presigned URLs for direct download."""

    def put(self, workspace_id: str, filename: str, data: bytes) -> tuple[str, str]:
        sha = hashlib.sha256(data).hexdigest()
        key = f"{workspace_id}/{sha}{Path(filename).suffix}"
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data,
            ServerSideEncryption="aws:kms", SSEKMSKeyId=self._kms_key_id,
            Metadata={"workspace_id": str(workspace_id), "original_name": filename})
        return key, sha

    def presigned_get(self, key: str, *, expires_in: int = 300) -> str:
        """5-minute bearer-credential URL — never logged."""
```

`Storage` protocol currently declares only `put` — extend with `get`,
`delete`, `presigned_get` (today nothing can re-read an uploaded document
at all). Also changes `put` to accept a file-like object rather than
`bytes`, so it composes with R-003/TS-095's streaming upload instead of
requiring the whole file in memory first.

Ops requirements: bucket in ap-south-1 (Mumbai, data-residency NFR);
versioning on; lifecycle to Glacier after 180 days; block all public
access; presigned URLs ≤5 minutes, never logged; MinIO in
`docker-compose` so local dev exercises the same code path as production.

## Files touched (planned)

- `backend/app/modules/ingestion/{storage,storage_s3}.py`
- `docker-compose.yml` (MinIO service)

## Tests (planned)

- `backend/tests/modules/ingestion/test_storage_s3.py` (against MinIO in CI)

## Acceptance criteria (R-016 §B, A7–A9)

- [ ] `S3Storage` implements `put`/`get`/`delete`/`presigned_get` against a
      real S3-compatible endpoint (MinIO in tests).
- [ ] Uploaded documents survive a replica/container restart.
- [ ] A presigned URL expires within 5 minutes and never appears in logs.

## Commit

Not yet implemented.
