# API examples (manual)

Base URLs:

```bash
# Local (dev)
export BASE=http://127.0.0.1:8080
export KEY=   # empty in default local .env (auth off)

# DigitalOcean (production)
export BASE=https://feature-flags-api-ie7au.ondigitalocean.app
export KEY='YOUR_API_KEY'   # App Platform secret API_KEY
```

Helper (omit `X-API-Key` when `KEY` is empty):

```bash
auth() { if [ -n "${KEY:-}" ]; then echo -H "X-API-Key: $KEY"; fi; }
```

Public routes never need a key: `/live`, `/ready`, `/health`, `/docs`.

---

## Health

```bash
curl -s "$BASE/live"; echo
curl -s "$BASE/ready"; echo
curl -s "$BASE/health"; echo
```

---

## Flags

### Create

```bash
curl -s -X POST "$BASE/flags" $(auth) \
  -H 'content-type: application/json' \
  -d '{"key":"new-checkout","description":"Checkout redesign","enabled":true,"rollout_percent":5}'
echo
```

### List / get

```bash
curl -s "$BASE/flags" $(auth); echo
curl -s "$BASE/flags/new-checkout" $(auth); echo
```

### Update (ramp / kill switch)

```bash
# Ramp cohort
curl -s -X PATCH "$BASE/flags/new-checkout" $(auth) \
  -H 'content-type: application/json' \
  -d '{"rollout_percent":25}'
echo

# Kill switch (everyone off unless override)
curl -s -X PATCH "$BASE/flags/new-checkout" $(auth) \
  -H 'content-type: application/json' \
  -d '{"enabled":false}'
echo
```

---

## Per-user overrides

```bash
# Force QA on
curl -s -X PUT "$BASE/flags/new-checkout/users/qa" $(auth) \
  -H 'content-type: application/json' \
  -d '{"enabled":true}'
echo

# Remove override
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  "$BASE/flags/new-checkout/users/qa" $(auth)
```

---

## Evaluate

```bash
curl -s "$BASE/evaluate/new-checkout?user_id=alice" $(auth); echo
curl -s "$BASE/evaluate/new-checkout?user_id=bob" $(auth); echo
curl -s "$BASE/evaluate/new-checkout?user_id=qa" $(auth); echo
```

Example response:

```json
{
  "key": "new-checkout",
  "user_id": "alice",
  "enabled": true,
  "source": "rollout",
  "bucket": 12,
  "cached": false
}
```

`source`: `override` | `rollout` | `default`  
Precedence: override → `enabled=false` (kill switch) → percentage rollout.

---

## Expected error samples

```bash
# Duplicate key → 409
curl -s -w "\nHTTP %{http_code}\n" -X POST "$BASE/flags" $(auth) \
  -H 'content-type: application/json' \
  -d '{"key":"new-checkout","enabled":true}'

# Invalid key → 422
curl -s -w "\nHTTP %{http_code}\n" -X POST "$BASE/flags" $(auth) \
  -H 'content-type: application/json' \
  -d '{"key":"bad key!","enabled":true}'

# Missing flag → 404
curl -s -w "\nHTTP %{http_code}\n" \
  "$BASE/evaluate/missing?user_id=alice" $(auth)

# Missing/invalid API key (production) → 401
curl -s -w "\nHTTP %{http_code}\n" -X POST "$BASE/flags" \
  -H 'content-type: application/json' \
  -d '{"key":"noauth","enabled":true}'
```

---

## One-shot smoke (production)

```bash
export BASE=https://feature-flags-api-ie7au.ondigitalocean.app
export KEY='YOUR_API_KEY'
FLAG="demo-$(date +%s)"

curl -s "$BASE/ready"; echo
curl -s -X POST "$BASE/flags" -H "X-API-Key: $KEY" -H 'content-type: application/json' \
  -d "{\"key\":\"$FLAG\",\"enabled\":true,\"rollout_percent\":100}"; echo
curl -s "$BASE/evaluate/$FLAG?user_id=me" -H "X-API-Key: $KEY"; echo
```
