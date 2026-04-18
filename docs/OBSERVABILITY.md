# Observability Runbook

Three signals make up day-2 operations for the platform:

1. **Structured logs** — structlog JSON per request.
2. **Sentry errors** — unhandled exceptions + performance traces.
3. **Uptime / latency** — `/api/v1/health` polled by Render + GitHub Actions prod-deploy workflow.

## 1. Structured logging

Every HTTP request produces one JSON line on stdout via `structlog`. The
`RequestLoggingMiddleware` (backend/app/middleware/request_log.py) binds these
context vars to the request:

```
request_id  — X-Request-ID header if supplied, else a UUID4
method      — HTTP method
path        — request path
```

On completion:
```json
{
  "event": "http.request",
  "status_code": 200,
  "duration_ms": 42,
  "request_id": "c0ffee00-…",
  "method": "POST",
  "path": "/api/v1/risk/var",
  "timestamp": "2026-04-17T21:09:12.345Z",
  "level": "info"
}
```

On unhandled error:
```json
{
  "event": "http.request.failed",
  "request_id": "…",
  "duration_ms": 17,
  "exception": "…stacktrace…",
  "level": "error"
}
```

### Querying in Render

```
[Logs tab]  filter: path=/api/v1/risk/var  level=error
```

Render supports structured filters; paste JSON key/value pairs.

### Querying locally (dev)

```
uvicorn app.main:app --reload 2>&1 | jq 'select(.event=="http.request" and .status_code>=500)'
```

## 2. Sentry

Backend integration lives in `app/core/sentry.py`. It is a no-op unless
`SENTRY_DSN` is set — dev stays quiet, prod enables it.

### Activating

1. Create a backend Sentry project (FastAPI). Copy its DSN.
2. Set the env var on Render:
   ```
   SENTRY_DSN=https://<public>@<org>.ingest.sentry.io/<project>
   SENTRY_TRACES_SAMPLE_RATE=0.05       # 5% of transactions
   ```
3. Redeploy. On startup the log line `app.startup sentry=True` confirms activation.

### What is captured

- Every unhandled exception (FastAPI + Starlette + asyncpg integrations).
- 5 % of transactions for performance traces.
- PII is disabled (`send_default_pii=False`) — no request bodies or cookies in events.

### Forcing a test event

Hit a protected endpoint with a malformed bearer token, then check the Sentry issue list:
```bash
curl -X POST https://<backend>/api/v1/risk/var \
    -H "Authorization: Bearer not-a-real-jwt" \
    -H "Content-Type: application/json" \
    -d '{}'
```
The decoder raises `JWTError` which bubbles into Sentry.

### Frontend Sentry (optional, wizard-based)

```
cd frontend
npx @sentry/wizard@latest -i nextjs
```

The wizard will write:
- `frontend/sentry.client.config.ts`
- `frontend/sentry.server.config.ts`
- `frontend/sentry.edge.config.ts`
- updates to `next.config.ts`

Commit those files and set `NEXT_PUBLIC_SENTRY_DSN` on Vercel. Not run from
Claude Code because it needs the Sentry auth cookie.

## 3. Rate limiting

`RateLimitMiddleware` (in-process, 60 req/min per user-or-IP on `/risk/*`).
Exceeded requests return:
```json
{
  "type": "about:blank",
  "title": "rate limit exceeded",
  "detail": "Limit of 60/minute per client on /risk/*",
  "retry_after_seconds": 37
}
```
…with HTTP 429 + `Retry-After` header.

To tune: set `RATE_LIMIT_RISK` env var (e.g. `"120/minute"`, `"10/second"`).

## 4. What to watch

| Signal                          | Threshold       | Action                                                 |
|---------------------------------|-----------------|--------------------------------------------------------|
| Sentry new issue                | any             | Triage within 1 business day                           |
| Render deploy red               | any             | Roll back via `git revert`                             |
| `/health` 5xx for > 3 min       | —               | Check Render service logs + Supabase dashboard          |
| `http.request.failed` rate      | > 1 / minute    | Inspect most recent request_id                          |
| Rate-limit 429s                 | > 10 / minute   | Possibly wrong client loop — inspect `user:` key        |
| GitHub Actions red on main      | any             | Block merges until green                                 |

## 5. Request-id correlation

Every response carries `X-Request-Id`. Capture it from the frontend on error:
```ts
catch (err) {
  if (err instanceof ProblemDetailsError) {
    console.error("backend problem", err.problem, "request_id:", err.problem.request_id);
  }
}
```

Look up that id in Render logs to see the exact request chain.
