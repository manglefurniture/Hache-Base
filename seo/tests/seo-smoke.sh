#!/usr/bin/env bash
set -euo pipefail

: "${SEO_BASE_URL:?SEO_BASE_URL is required}"
SEO_MODE="${SEO_MODE:-public}"
SEO_EXPECT_INDEXABLE="${SEO_EXPECT_INDEXABLE:-1}"
BASE="${SEO_BASE_URL%/}"

fail() { echo "$1 FAIL $2" >&2; exit 1; }
pass() { echo "$1 PASS $2"; }

HOME_HEADERS="$(mktemp)"
HOME_BODY="$(mktemp)"
ROBOTS_BODY="$(mktemp)"
trap 'rm -f "$HOME_HEADERS" "$HOME_BODY" "$ROBOTS_BODY"' EXIT

code="$(curl --silent --show-error --location --max-time 20 -D "$HOME_HEADERS" -o "$HOME_BODY" -w '%{http_code}' "$BASE/")"
[[ "$code" == "200" ]] || fail SEO-SERVER-002 "home returned HTTP $code"
pass SEO-SERVER-002 "home HTTP 200"

if [[ "$SEO_MODE" == "public" || "$SEO_MODE" == "hybrid" ]]; then
  robots_code="$(curl --silent --show-error --max-time 20 -o "$ROBOTS_BODY" -w '%{http_code}' "$BASE/robots.txt")"
  [[ "$robots_code" == "200" ]] || fail SEO-CRAWL-001 "robots.txt returned HTTP $robots_code"
  if awk '
    BEGIN { all=0; blocked=0 }
    {
      line=$0; sub(/#.*/, "", line); gsub(/^[ \t]+|[ \t]+$/, "", line);
      low=tolower(line);
      if (low ~ /^user-agent:[ \t]*\*$/) all=1;
      else if (low ~ /^user-agent:/) all=0;
      else if (all && low ~ /^disallow:[ \t]*\/$/) blocked=1;
    }
    END { exit blocked ? 0 : 1 }
  ' "$ROBOTS_BODY"; then
    fail SEO-CRAWL-002 'robots.txt contains global Disallow: /'
  fi
  pass SEO-CRAWL-002 'no global Disallow: /'
fi

if [[ "$SEO_EXPECT_INDEXABLE" == "1" ]] && grep -Eiq '<meta[^>]+name=["'"']robots["'"'][^>]+content=["'"'][^"'"']*noindex' "$HOME_BODY"; then
  fail SEO-INDEX-001 'home contains noindex'
fi
pass SEO-INDEX-001 'home indexability meta check'

if ! grep -Eiq '<title[^>]*>[^<]+</title>' "$HOME_BODY"; then
  fail SEO-ONPAGE-001 'home missing non-empty title'
fi
pass SEO-ONPAGE-001 'home title present'

if ! grep -Eiq '<meta[^>]+name=["'"']viewport["'"']' "$HOME_BODY"; then
  fail SEO-MOBILE-001 'viewport meta missing'
fi
pass SEO-MOBILE-001 'viewport present'

echo "SEO_SMOKE_OK $BASE"
