#!/bin/sh
# smoke-gateway.sh - regression test for the gateway -> web Host-header path.
#
# Why this exists: the gateway must forward the client's Host header exactly
# (including the port). If it is ever changed back to $host (which strips the
# port), Django's CSRF origin check rejects every browser POST through the
# gateway with 403, while direct-to-web tests still pass. This script catches
# that in seconds against a running stack.
#
# Usage (stack up):  ./scripts/smoke-gateway.sh [base-url]   (default http://127.0.0.1:8000)
# Exits 0 when a realistic browser POST passes CSRF, 1 otherwise.

BASE="${1:-http://127.0.0.1:8000}"
JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT

fail() { echo "SMOKE FAIL: $1"; exit 1; }

# 1. Fetch a real form (owner login needs no seeded data) and keep cookies.
PAGE=$(curl -s -c "$JAR" -b "$JAR" "$BASE/owner/login/") || fail "gateway unreachable at $BASE"
TOKEN=$(printf '%s' "$PAGE" | grep -o 'name="csrfmiddlewaretoken" value="[^"]*"' | head -1 | sed 's/.*value="//; s/"$//')
[ -n "$TOKEN" ] || fail "no CSRF token in /owner/login/ (web up?)"

# 2. POST with exactly the headers a browser sends through the gateway.
CODE=$(curl -s -o /dev/null -w '%{http_code}' -c "$JAR" -b "$JAR" -X POST "$BASE/owner/login/" \
  -H "Origin: $BASE" -H "Referer: $BASE/owner/login/" \
  --data-urlencode "csrfmiddlewaretoken=$TOKEN" \
  --data-urlencode "username=smoke" --data-urlencode "password=smoke")

# 3. 403 here means the gateway is rewriting Host (or CSRF config broke).
[ "$CODE" = "403" ] && fail "POST through gateway rejected with 403 (check proxy_set_header Host \$http_host in gateway/nginx.conf)"
echo "SMOKE OK: gateway forwards Host correctly (POST returned HTTP $CODE, CSRF passed)"
