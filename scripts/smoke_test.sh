#!/usr/bin/env bash
# Smoke tests for a running instance of the service.
#   scripts/smoke_test.sh http://localhost:8080
set -euo pipefail
BASE="${1:?usage: smoke_test.sh <base-url>}"

echo "== GET /healthcheck"
curl -fsS "$BASE/healthcheck" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d == {"status": "ok"}, d'

echo "== GET /characters"
curl -fsS "$BASE/characters" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["count"] == len(d["characters"]) > 0, "expected at least one character"
for c in d["characters"]:
    assert set(c) == {"name", "location", "image"}, c
    assert c["image"].startswith("https://rickandmortyapi.com/api/character/avatar/"), c
print("characters:", d["count"])'

echo "== GET /characters.csv"
curl -fsS "$BASE/characters.csv" | python3 -c '
import csv, sys
rows = list(csv.reader(sys.stdin))
assert rows[0] == ["Name", "Location", "Image"], rows[0]
assert len(rows) > 1, "no data rows"
print("csv rows:", len(rows) - 1)'

echo "== GET /nope -> 404"
test "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/nope")" = 404

echo "smoke tests passed"
