# OpenClaw on Dedicated Mac (Prototype Guidance)

This prototype supports two OpenClaw modes:

- `OPENCLAW_MODE=mock` (default)
- `OPENCLAW_MODE=remote`

Use `remote` mode when you want to isolate browser automation to a dedicated Mac.

## Why this setup

- Browser automation and login sessions are isolated from the main prototype host.
- Failures in collector automation do not break the core API process.
- Security controls can be applied specifically to collector infrastructure.

## Expected remote collector contract

The prototype expects the dedicated Mac collector service to expose:

- `POST /api/v1/collect`

Request example:

```json
{
  "platform": "jd",
  "url": "https://item.jd.com/mock",
  "template_version": "default_v1"
}
```

Response example:

```json
{
  "raw_fields": {
    "price_text": "base price 3199",
    "coupon_text": "coupon 200",
    "gift_text": "earbuds",
    "final_price_text": "final price 2999"
  },
  "snapshot_id": "snap_12345",
  "screenshot_urls": [
    "https://collector.local/screens/snap_12345.png"
  ]
}
```

## Configure prototype to use dedicated Mac collector

```bash
export OPENCLAW_MODE=remote
export OPENCLAW_REMOTE_BASE_URL=http://<dedicated-mac-ip>:9001
export OPENCLAW_TIMEOUT_SECONDS=20
uvicorn app.main:app --reload
```

## Reliability controls

- Keep per-platform extraction templates versioned.
- Preserve screenshot and raw fields for each collection.
- If collection fails, mark task as failed and require manual review.
- Never allow uncertain fields to silently default into business decisions.
