from pathlib import Path

root = Path('.')
check = root / 'security/supply-chain/check.php'
test = root / 'tests/security/SupplyChainReviewRound2RegressionTest.sh'

src = check.read_text()

old = '''function normalizeSeverity(?string $severity): string
{
    $value = strtolower(trim((string)$severity));
    return in_array($value, ['critical', 'high', 'medium', 'low'], true) ? $value : 'unknown';
}
'''
new = '''function normalizeSeverity(?string $severity): string
{
    $value = strtolower(trim((string)$severity));
    if ($value === 'moderate') {
        return 'medium';
    }
    return in_array($value, ['critical', 'high', 'medium', 'low'], true) ? $value : 'unknown';
}
'''
assert src.count(old) == 1, 'normalizeSeverity block mismatch'
src = src.replace(old, new)

old = '''    if (preg_match('/^(<=|>=|<|>|=)\\s*v?(\\d+)(?:\\.(\\d+))?(?:\\.(\\d+))?$/', $token, $matches) === 1) {
        $target = [(int)$matches[2], (int)($matches[3] ?? 0), (int)($matches[4] ?? 0)];
        return version_compare($lockedString, npmVersionString($target), $matches[1]);
    }
'''
new = '''    if (preg_match('/^(<=|>=|<|>|=)\\s*v?(\\d+)(?:\\.(\\d+))?(?:\\.(\\d+))?$/', $token, $matches) === 1) {
        $operator = $matches[1];
        $specified = isset($matches[3]) && $matches[3] !== '' ? (isset($matches[4]) && $matches[4] !== '' ? 3 : 2) : 1;
        $target = [(int)$matches[2], (int)($matches[3] ?? 0), (int)($matches[4] ?? 0)];
        $targetString = npmVersionString($target);
        if ($specified === 3 || in_array($operator, ['>=', '<'], true)) {
            return version_compare($lockedString, $targetString, $operator);
        }
        $nextPartial = $specified === 1
            ? [$target[0] + 1, 0, 0]
            : [$target[0], $target[1] + 1, 0];
        $nextPartialString = npmVersionString($nextPartial);
        return match ($operator) {
            '>' => version_compare($lockedString, $nextPartialString, '>='),
            '<=' => version_compare($lockedString, $nextPartialString, '<'),
            '=' => version_compare($lockedString, $targetString, '>=')
                && version_compare($lockedString, $nextPartialString, '<'),
            default => false,
        };
    }
'''
assert src.count(old) == 1, 'npm partial comparator block mismatch'
src = src.replace(old, new)

start_marker = '/** @return array<int,array<string,mixed>> */\nfunction npmVulnerabilities(array $audit): array\n{'
end_marker = '\n/** @return array<int,array<string,mixed>> */\nfunction composerVulnerabilities(array $audit): array\n{'
start = src.index(start_marker)
end = src.index(end_marker, start)
new_func = '''/** @return array<int,array<string,mixed>> */
function npmVulnerabilities(array $audit): array
{
    $result = [];
    foreach ((array)($audit['vulnerabilities'] ?? []) as $package => $data) {
        if (!is_array($data)) {
            continue;
        }
        $packageSeverity = normalizeSeverity((string)($data['severity'] ?? 'unknown'));
        $emitted = 0;
        $maxEmittedRank = 0;
        $seen = [];
        foreach ((array)($data['via'] ?? []) as $entry) {
            if (is_string($entry)) {
                $indirect = trim($entry);
                if ($indirect === '') {
                    continue;
                }
                $advisory = 'npm:' . (string)$package . ':via:' . $indirect;
                $key = (string)$package . '|' . $advisory;
                if (isset($seen[$key])) {
                    continue;
                }
                $seen[$key] = true;
                $result[] = [
                    'package' => (string)$package,
                    'severity' => $packageSeverity,
                    'advisory' => $advisory,
                    'title' => 'npm audit indirect dependency via ' . $indirect,
                    'url' => '',
                ];
                $emitted++;
                $maxEmittedRank = max($maxEmittedRank, severityRank($packageSeverity));
                continue;
            }
            if (!is_array($entry)) {
                continue;
            }
            $advisory = isset($entry['source']) ? 'npm:' . (string)$entry['source'] : 'npm:' . $package . ':via:' . ($emitted + 1);
            $key = (string)$package . '|' . $advisory;
            if (isset($seen[$key])) {
                continue;
            }
            $seen[$key] = true;
            $severity = normalizeSeverity((string)($entry['severity'] ?? $packageSeverity));
            if ($severity === 'unknown') {
                $severity = $packageSeverity;
            }
            $result[] = [
                'package' => (string)$package,
                'severity' => $severity,
                'advisory' => $advisory,
                'title' => (string)($entry['title'] ?? 'npm audit finding'),
                'url' => (string)($entry['url'] ?? ''),
            ];
            $emitted++;
            $maxEmittedRank = max($maxEmittedRank, severityRank($severity));
        }
        if ($emitted === 0) {
            $result[] = [
                'package' => (string)$package,
                'severity' => $packageSeverity,
                'advisory' => 'npm:' . (string)$package,
                'title' => 'npm audit package finding',
                'url' => '',
            ];
        } elseif (severityRank($packageSeverity) > $maxEmittedRank) {
            $result[] = [
                'package' => (string)$package,
                'severity' => $packageSeverity,
                'advisory' => 'npm:' . (string)$package . ':aggregate',
                'title' => 'npm audit aggregate package severity',
                'url' => '',
            ];
        }
    }
    return $result;
}
'''
src = src[:start] + new_func + src[end:]
check.write_text(src)

txt = test.read_text()
needle = '\necho "SUPPLY_CHAIN_REVIEW_ROUND2_REGRESSION_OK"\n'
assert txt.count(needle) == 1, 'round2 echo marker mismatch'
append = r'''

moderate="$(new_repo npm-audit-moderate)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"^1.0.0"}}' > "$moderate/package.json"
cat > "$moderate/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"^1.0.0"}},"node_modules/pkg":{"name":"pkg","version":"1.5.0","license":"MIT"}}}
JSON
commit_all "$moderate"
moderate_hash="$(git -C "$moderate" show HEAD:package-lock.json | sha256sum | awk '{print $1}')"
cat > "$moderate/npm-audit.json" <<JSON
{"auditReportVersion":2,"vulnerabilities":{"pkg":{"severity":"critical","via":[{"source":3101,"severity":"moderate","title":"moderate advisory","url":"https://example.test/3101"},{"source":3102,"severity":"critical","title":"critical advisory","url":"https://example.test/3102"}]}},"hache_lock_sha256":"$moderate_hash"}
JSON
set +e
raw_check "$moderate" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$moderate/npm-audit.json" > "$moderate/out.txt" 2>&1
moderate_rc=$?
set -e
[[ "$moderate_rc" -eq 1 ]]
! grep -q 'rule=sca_unavailable' "$moderate/out.txt"
grep -q '"severity": "medium"' "$moderate/report.json"
grep -q '"severity": "critical"' "$moderate/report.json"
grep -q 'npm:3101' "$moderate/report.json"
grep -q 'npm:3102' "$moderate/report.json"

indirect="$(new_repo npm-audit-indirect-critical)"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.0.0","dependencies":{"pkg":"^1.0.0"}}' > "$indirect/package.json"
cat > "$indirect/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0","dependencies":{"pkg":"^1.0.0"}},"node_modules/pkg":{"name":"pkg","version":"1.5.0","license":"MIT"}}}
JSON
commit_all "$indirect"
indirect_hash="$(git -C "$indirect" show HEAD:package-lock.json | sha256sum | awk '{print $1}')"
cat > "$indirect/npm-audit.json" <<JSON
{"auditReportVersion":2,"vulnerabilities":{"pkg":{"severity":"critical","via":[{"source":3201,"severity":"low","title":"low direct advisory","url":"https://example.test/3201"},"meta-pkg"]}},"hache_lock_sha256":"$indirect_hash"}
JSON
set +e
raw_check "$indirect" SUPPLY_CHAIN_MODE=block SUPPLY_CHAIN_LEVEL=C SUPPLY_CHAIN_NPM_AUDIT_FILE="$indirect/npm-audit.json" > "$indirect/out.txt" 2>&1
indirect_rc=$?
set -e
[[ "$indirect_rc" -eq 1 ]]
! grep -q 'rule=sca_unavailable' "$indirect/out.txt"
grep -q 'npm:pkg:via:meta-pkg' "$indirect/report.json"
grep -q '"severity": "critical"' "$indirect/report.json"

constraint_case() {
  local name="$1"
  local constraint="$2"
  local version="$3"
  local expected="$4"
  local dir
  dir="$(new_repo "$name")"
  printf '%s\n' "{\"name\":\"fixture\",\"private\":true,\"packageManager\":\"npm@11.0.0\",\"dependencies\":{\"pkg\":\"$constraint\"}}" > "$dir/package.json"
  printf '%s\n' "{\"name\":\"fixture\",\"lockfileVersion\":3,\"packages\":{\"\":{\"name\":\"fixture\",\"version\":\"1.0.0\",\"dependencies\":{\"pkg\":\"$constraint\"}},\"node_modules/pkg\":{\"name\":\"pkg\",\"version\":\"$version\",\"license\":\"MIT\"}}}" > "$dir/package-lock.json"
  commit_all "$dir"
  set +e
  raw_check "$dir" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$dir/out.txt" 2>&1
  local rc=$?
  set -e
  if [[ "$expected" == valid ]]; then
    [[ "$rc" -eq 0 ]]
    ! grep -q 'rule=node_lock_invalid_format' "$dir/out.txt"
  else
    [[ "$rc" -eq 1 ]]
    grep -q 'rule=node_lock_invalid_format' "$dir/out.txt"
  fi
}

constraint_case npm-partial-gt-major-bad '>1' '1.5.0' invalid
constraint_case npm-partial-gt-major-good '>1' '2.0.0' valid
constraint_case npm-partial-gt-minor-bad '>1.2' '1.2.9' invalid
constraint_case npm-partial-gt-minor-good '>1.2' '1.3.0' valid
constraint_case npm-partial-le-major-good '<=1' '1.9.9' valid
constraint_case npm-partial-le-major-bad '<=1' '2.0.0' invalid
'''
txt = txt.replace(needle, append + needle)
test.write_text(txt)
