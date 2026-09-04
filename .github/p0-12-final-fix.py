from pathlib import Path

check = Path('security/supply-chain/check.php')
text = check.read_text()

old = """            $workspaceData = $lock['packages'][$workspacePath] ?? null;\n            if (!is_array($workspaceData)\n                || !isset($workspaceData['name'], $workspaceData['version'])\n                || !is_string($workspaceData['name']) || trim($workspaceData['name']) === ''\n                || !is_string($workspaceData['version']) || trim($workspaceData['version']) === '') {\n                return false;\n            }\n            $manifestName = $workspaceManifest['name'] ?? null;\n            if (!is_string($manifestName) || trim($manifestName) === '' || trim($manifestName) !== trim($workspaceData['name'])) {\n                return false;\n            }\n            if (array_key_exists('version', $workspaceManifest)) {\n                if (!is_string($workspaceManifest['version']) || trim($workspaceManifest['version']) === ''\n                    || trim($workspaceManifest['version']) !== trim($workspaceData['version'])) {\n                    return false;\n                }\n            }\n"""
new = """            $workspaceData = $lock['packages'][$workspacePath] ?? null;\n            if (!is_array($workspaceData)) {\n                return false;\n            }\n            $manifestName = $workspaceManifest['name'] ?? null;\n            if (!is_string($manifestName) || trim($manifestName) === '') {\n                return false;\n            }\n            $manifestName = trim($manifestName);\n            if (array_key_exists('name', $workspaceData)) {\n                if (!is_string($workspaceData['name']) || trim($workspaceData['name']) === ''\n                    || trim($workspaceData['name']) !== $manifestName) {\n                    return false;\n                }\n            }\n            if (array_key_exists('version', $workspaceData)\n                && (!is_string($workspaceData['version']) || trim($workspaceData['version']) === '')) {\n                return false;\n            }\n            if (array_key_exists('version', $workspaceManifest)) {\n                if (!is_string($workspaceManifest['version']) || trim($workspaceManifest['version']) === '') {\n                    return false;\n                }\n                if (array_key_exists('version', $workspaceData)\n                    && trim($workspaceManifest['version']) !== trim($workspaceData['version'])) {\n                    return false;\n                }\n            }\n"""
if old not in text:
    raise SystemExit('workspace anchor not found')
text = text.replace(old, new, 1)
workspace_name_old = "            $workspaceName = trim($workspaceData['name']);"
if workspace_name_old not in text:
    raise SystemExit('workspace name anchor not found')
text = text.replace(workspace_name_old, "            $workspaceName = $manifestName;", 1)

anchor = """    if (array_intersect_key($prodVersions, $devVersions) !== []) {\n        return false;\n    }\n\n    $allVersions = $prodVersions + $devVersions;\n"""
insert = """    if (array_intersect_key($prodVersions, $devVersions) !== []) {\n        return false;\n    }\n\n    $rootVersion = null;\n    if (array_key_exists('version', $manifest)) {\n        if (!is_string($manifest['version']) || trim($manifest['version']) === '') {\n            return false;\n        }\n        $rootVersion = trim($manifest['version']);\n    }\n    foreach (['provide', 'replace'] as $relation) {\n        $relations = $manifest[$relation] ?? [];\n        if (!is_array($relations)) {\n            return false;\n        }\n        foreach ($relations as $virtual => $provided) {\n            if (!is_string($virtual) || trim($virtual) === '' || !is_string($provided) || trim($provided) === '') {\n                return false;\n            }\n            $provided = trim($provided);\n            if (strcasecmp($provided, 'self.version') === 0) {\n                if ($rootVersion === null) {\n                    return false;\n                }\n                $provided = $rootVersion;\n            }\n            $prodProviders[trim($virtual)][] = $provided;\n        }\n    }\n\n    $allVersions = $prodVersions + $devVersions;\n"""
if anchor not in text:
    raise SystemExit('composer anchor not found')
text = text.replace(anchor, insert, 1)
check.write_text(text)

test = Path('tests/security/SupplyChainReviewRound4RegressionTest.sh')
test.write_text(r'''#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
new_repo() {
  local name="$1" dir="$TMP/$1"
  mkdir -p "$dir/security/supply-chain"
  cp "$ROOT/security/supply-chain/"{policy.json,license-policy.json,accepted-risk.json,secret-scan.allowlist} "$dir/security/supply-chain/"
  git -C "$dir" init -q
  git -C "$dir" config user.email fixture@example.test
  git -C "$dir" config user.name fixture
  printf '%s\n' fixture > "$dir/README.md"
  git -C "$dir" add . && git -C "$dir" commit -qm init
  printf '%s\n' "$dir"
}
commit_all() { git -C "$1" add . && git -C "$1" commit -qm fixture; }
raw_check() {
  local dir="$1"; shift
  env SUPPLY_CHAIN_ROOT="$dir" SUPPLY_CHAIN_REPORT_FILE="$dir/report.json" SUPPLY_CHAIN_DISABLE_EXTERNAL_SCA=1 "$@" php "$ROOT/security/supply-chain/check.php"
}

workspace_no_name="$(new_repo npm-workspace-no-name)"
mkdir -p "$workspace_no_name/packages/a"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.4.2","workspaces":["packages/*"]}' > "$workspace_no_name/package.json"
printf '%s\n' '{"name":"a","version":"1.0.0"}' > "$workspace_no_name/packages/a/package.json"
printf '%s\n' '{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"},"node_modules/a":{"resolved":"packages/a","link":true},"packages/a":{"version":"1.0.0"}}}' > "$workspace_no_name/package-lock.json"
commit_all "$workspace_no_name"
raw_check "$workspace_no_name" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$workspace_no_name/out.txt"
! grep -q 'rule=node_lock_invalid_format' "$workspace_no_name/out.txt"

workspace_private="$(new_repo npm-private-workspace-no-version)"
mkdir -p "$workspace_private/packages/a"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.4.2","workspaces":["packages/*"]}' > "$workspace_private/package.json"
printf '%s\n' '{"name":"a","private":true}' > "$workspace_private/packages/a/package.json"
printf '%s\n' '{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"},"node_modules/a":{"resolved":"packages/a","link":true},"packages/a":{}}}' > "$workspace_private/package-lock.json"
commit_all "$workspace_private"
raw_check "$workspace_private" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$workspace_private/out.txt"
! grep -q 'rule=node_lock_invalid_format' "$workspace_private/out.txt"

workspace_name_drift="$(new_repo npm-workspace-name-drift)"
mkdir -p "$workspace_name_drift/packages/a"
printf '%s\n' '{"name":"fixture","private":true,"packageManager":"npm@11.4.2","workspaces":["packages/*"]}' > "$workspace_name_drift/package.json"
printf '%s\n' '{"name":"a","version":"1.0.0"}' > "$workspace_name_drift/packages/a/package.json"
printf '%s\n' '{"name":"fixture","lockfileVersion":3,"packages":{"":{"name":"fixture","version":"1.0.0"},"node_modules/a":{"resolved":"packages/a","link":true},"packages/a":{"name":"wrong","version":"1.0.0"}}}' > "$workspace_name_drift/package-lock.json"
commit_all "$workspace_name_drift"
set +e; raw_check "$workspace_name_drift" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$workspace_name_drift/out.txt" 2>&1; rc=$?; set -e
[[ "$rc" -eq 1 ]]; grep -q 'rule=node_lock_invalid_format' "$workspace_name_drift/out.txt"

composer_root_replace="$(new_repo composer-root-replace)"
printf '%s\n' '{"name":"fixture/app","version":"1.2.3","replace":{"vendor/virtual":"self.version"},"require":{"vendor/a":"^1.0"}}' > "$composer_root_replace/composer.json"
printf '%s\n' '{"packages":[{"name":"vendor/a","version":"1.0.0","require":{"vendor/virtual":"^1.2"}}],"packages-dev":[]}' > "$composer_root_replace/composer.lock"
commit_all "$composer_root_replace"
raw_check "$composer_root_replace" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$composer_root_replace/out.txt"
! grep -q 'rule=composer_lock_invalid_format' "$composer_root_replace/out.txt"

composer_root_provide="$(new_repo composer-root-provide)"
printf '%s\n' '{"name":"fixture/app","provide":{"vendor/virtual":"^2.0"},"require":{"vendor/a":"^1.0"}}' > "$composer_root_provide/composer.json"
printf '%s\n' '{"packages":[{"name":"vendor/a","version":"1.0.0","require":{"vendor/virtual":"^2.1"}}],"packages-dev":[]}' > "$composer_root_provide/composer.lock"
commit_all "$composer_root_provide"
raw_check "$composer_root_provide" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$composer_root_provide/out.txt"
! grep -q 'rule=composer_lock_invalid_format' "$composer_root_provide/out.txt"

composer_root_self_unknown="$(new_repo composer-root-self-version-unknown)"
printf '%s\n' '{"name":"fixture/app","replace":{"vendor/virtual":"self.version"},"require":{"vendor/a":"^1.0"}}' > "$composer_root_self_unknown/composer.json"
printf '%s\n' '{"packages":[{"name":"vendor/a","version":"1.0.0","require":{"vendor/virtual":"^1.0"}}],"packages-dev":[]}' > "$composer_root_self_unknown/composer.lock"
commit_all "$composer_root_self_unknown"
set +e; raw_check "$composer_root_self_unknown" SUPPLY_CHAIN_MODE=baseline SUPPLY_CHAIN_LEVEL=A > "$composer_root_self_unknown/out.txt" 2>&1; rc=$?; set -e
[[ "$rc" -eq 1 ]]; grep -q 'rule=composer_lock_invalid_format' "$composer_root_self_unknown/out.txt"

echo SUPPLY_CHAIN_REVIEW_ROUND4_REGRESSION_OK
''')

run = Path('tests/run.sh')
run_text = run.read_text()
anchor_run = 'bash "$ROOT/tests/security/SupplyChainReviewRound3RegressionTest.sh"\n'
if 'SupplyChainReviewRound4RegressionTest.sh' not in run_text:
    if anchor_run not in run_text:
        raise SystemExit('tests/run.sh anchor not found')
    run.write_text(run_text.replace(anchor_run, anchor_run + 'bash "$ROOT/tests/security/SupplyChainReviewRound4RegressionTest.sh"\n', 1))
