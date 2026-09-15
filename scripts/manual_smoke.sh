#!/usr/bin/env bash
set -euo pipefail
BASE=http://127.0.0.1:8080
UNIQUE=$(date +%s)
FLAG="checkout-${UNIQUE}"

run() {
  local title="$1"
  shift
  echo ""
  echo "============================================================"
  echo "TEST: ${title}"
  echo "CMD:  $*"
  echo "------------------------------------------------------------"
  "$@"
  echo ""
}

echo "Server restart verification + comprehensive manual tests"
echo "Base URL: ${BASE}"
echo "Flag key: ${FLAG}"

run "1. Liveness" curl -sS -w "\nHTTP %{http_code}\n" "${BASE}/live"
run "2. Readiness" curl -sS -w "\nHTTP %{http_code}\n" "${BASE}/ready"
run "3. Health" curl -sS -w "\nHTTP %{http_code}\n" "${BASE}/health"

run "4. Create flag (rollout 5%)" curl -sS -w "\nHTTP %{http_code}\n" -X POST "${BASE}/flags" \
  -H "content-type: application/json" \
  -d "{\"key\":\"${FLAG}\",\"description\":\"manual test\",\"enabled\":true,\"rollout_percent\":5}"

run "5. Duplicate create -> 409" curl -sS -w "\nHTTP %{http_code}\n" -X POST "${BASE}/flags" \
  -H "content-type: application/json" \
  -d "{\"key\":\"${FLAG}\",\"enabled\":true}"

run "6. Invalid key -> 422" curl -sS -w "\nHTTP %{http_code}\n" -X POST "${BASE}/flags" \
  -H "content-type: application/json" \
  -d '{"key":"bad key!","enabled":true}'

run "7. Get flag" curl -sS -w "\nHTTP %{http_code}\n" "${BASE}/flags/${FLAG}"
run "8. List flags (snippet)" curl -sS -w "\nHTTP %{http_code}\n" "${BASE}/flags"
run "9. Missing flag -> 404" curl -sS -w "\nHTTP %{http_code}\n" "${BASE}/flags/does-not-exist-${UNIQUE}"

run "10. Evaluate alice (rollout)" curl -sS -w "\nHTTP %{http_code}\n" \
  "${BASE}/evaluate/${FLAG}?user_id=alice"
run "11. Evaluate alice again (expect cached true)" curl -sS -w "\nHTTP %{http_code}\n" \
  "${BASE}/evaluate/${FLAG}?user_id=alice"
run "12. Evaluate bob (rollout)" curl -sS -w "\nHTTP %{http_code}\n" \
  "${BASE}/evaluate/${FLAG}?user_id=bob"

run "13. Patch ramp to 100%" curl -sS -w "\nHTTP %{http_code}\n" -X PATCH "${BASE}/flags/${FLAG}" \
  -H "content-type: application/json" \
  -d '{"rollout_percent":100}'

run "14. Evaluate bob after ramp" curl -sS -w "\nHTTP %{http_code}\n" \
  "${BASE}/evaluate/${FLAG}?user_id=bob"

run "15. Upsert override alice=false" curl -sS -w "\nHTTP %{http_code}\n" -X PUT \
  "${BASE}/flags/${FLAG}/users/alice" \
  -H "content-type: application/json" \
  -d '{"enabled":false}'

run "16. Evaluate alice override wins" curl -sS -w "\nHTTP %{http_code}\n" \
  "${BASE}/evaluate/${FLAG}?user_id=alice"

run "17. Delete override" curl -sS -w "\nHTTP %{http_code}\n" -o /tmp/del_body -X DELETE \
  "${BASE}/flags/${FLAG}/users/alice"
cat /tmp/del_body; echo

run "18. Evaluate alice after delete override" curl -sS -w "\nHTTP %{http_code}\n" \
  "${BASE}/evaluate/${FLAG}?user_id=alice"

run "19. Kill switch enabled=false" curl -sS -w "\nHTTP %{http_code}\n" -X PATCH "${BASE}/flags/${FLAG}" \
  -H "content-type: application/json" \
  -d '{"enabled":false}'

run "20. Evaluate after kill switch" curl -sS -w "\nHTTP %{http_code}\n" \
  "${BASE}/evaluate/${FLAG}?user_id=bob"

run "21. Evaluate missing flag -> 404" curl -sS -w "\nHTTP %{http_code}\n" \
  "${BASE}/evaluate/missing-${UNIQUE}?user_id=u1"

run "22. Evaluate missing user_id -> 422" curl -sS -w "\nHTTP %{http_code}\n" \
  "${BASE}/evaluate/${FLAG}"

run "23. Empty patch -> 422" curl -sS -w "\nHTTP %{http_code}\n" -X PATCH "${BASE}/flags/${FLAG}" \
  -H "content-type: application/json" \
  -d '{}'

echo "ALL MANUAL TESTS FINISHED for flag=${FLAG}"
