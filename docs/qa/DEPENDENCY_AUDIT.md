# Dashboard Dependency Audit

Result: full audit reduced from 8 nodes (2 moderate, 6 high) to 5 high nodes
from one unresolved braces advisory. Production-only lock audit: 0 findings.
Typechecks, production build and targeted dependency regression probes passed.
Docker build was not run; the required Node base image is not cached locally.

## Goal and Scope

- Date: 2026-10-10, Europe/Moscow.
- Worktree: `F:\Проекты MyWave\NEW2026\Ruza-qa-20261010` only.
- Starting HEAD and locally recorded origin/main: `1256d9016eb45e04343670eaf06d5fec2ea9fe40`.
- Branch: `codex/ruza-scenario-hardening-20261010`.
- Owned paths: this report and `icebeach-wakeclub/apps/dashboard/package.json` / `package-lock.json`.
- No source, framework configuration, Docker/Compose, backend, environment, production, commit or push changes. Other agents' pre-existing work is preserved.
- Local environment: Windows PowerShell, Node `v24.13.0`, npm `11.6.2`, npm registry `https://registry.npmjs.org/`.
- Docker daemon was inspected read-only. No Ruza containers were running. DB/API/business-flow verification is outside this dependency-only scope; no external application API was called and no secrets were read.

## Plan

1. Inspect the locked dependency tree and `npm audit --json`.
2. Verify affected ranges and published fixes against registry metadata and upstream advisories.
3. Apply the smallest targeted resolutions without migrating Tailwind or changing application code.
4. Reinstall with `npm ci`, check the exact lock, typecheck, build, and compare CSS compatibility probes.
5. Document residual risk and the separately scoped migration needed to remove it.

## Initial Audit Evidence

`npm audit --json` exited 1 with auditReportVersion 2:

```json
{"info":0,"low":0,"moderate":2,"high":6,"critical":0,"total":8}
```

These are eight vulnerable dependency nodes, not eight independent advisories. The three root advisories were:

| Advisory | Locked package | Severity / affected range | Decision |
| --- | --- | --- | --- |
| [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q) | source-map-js 1.2.1 | High; >=1.0.0 <1.2.2; indexed source-map offset DoS | Resolve exactly 1.2.2, the first patched release. |
| [GHSA-rj75-hqrm-r3gf](https://github.com/advisories/GHSA-rj75-hqrm-r3gf) | postcss-selector-parser 6.1.4 | Moderate; <7.1.6; flat-selector CPU exhaustion | Resolve exactly 7.1.6 after targeted compatibility verification. |
| [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) | braces 3.0.3 | High; <=3.0.3; deeply nested glob-pattern stack exhaustion | No published patched braces release; keep visible as unresolved. |

Initial vulnerable-node names: `braces`, `chokidar`, `fast-glob`, `micromatch`, `postcss-nested`, `postcss-selector-parser`, `source-map-js`, `tailwindcss`.

## Changes and Compatibility

Only two exact npm overrides were added:

```json
"overrides": {
  "postcss-selector-parser": "7.1.6",
  "source-map-js": "1.2.2"
}
```

The lock was regenerated using `npm install --package-lock-only --ignore-scripts --no-audit --no-fund` (exit 0). Its diff changes only the version, resolved URL, and integrity fields for those two existing package nodes. No direct dependency ranges changed, and no package was added or removed.

The source-map patch satisfies PostCSS's existing `^1.2.1` range. The selector-parser override deliberately crosses a transitive major boundary: Tailwind 3.4.19 requests `^6.1.2`, and postcss-nested 6.2.0 requests `^6.1.1`. There is no patched 6.x release in the advisory. [Upstream changelog](https://github.com/postcss/postcss-selector-parser/blob/main/CHANGELOG.md) identifies changed insertion-during-iteration semantics in 7.0.0; this is not presented as a semver-compatible patch. Exact pinning plus real build and independent CSS regression probes bound the compatibility risk without a framework migration. Revisit/remove this override when upstream consumers support patched versions naturally.

Registry metadata confirms patched selector-parser requires Node >=4 and source-map-js Node >=0.10.0. Existing Vite/plugin-react require Node `^20.19.0 || >=22.12.0`; the local Node version satisfies that unchanged requirement.

## Validation

Source tests/build exercise the shared working tree at execution time, which includes other agents' authorized source fixes; they are not an immutable build of the starting SHA.

Baseline before installing the new lock:

- `node node_modules/typescript/bin/tsc --noEmit`: exit 0.
- In-memory PostCSS/Tailwind regression probe: exit 0. Covered flex/padding, responsive, hover/group-hover, arbitrary selector and arbitrary width utilities, plus grouped nested hover/child selectors.
- Tailwind probe output: 457 characters, SHA256 `56261bec275a77241ab8e1505136fe295963f517471ef5f5fc84ae0b89ea6830`.
- Nested-selector output SHA256: `21a01d04b8c3ce55448a51321eda95c344fdd686b3bf80a7ca6bd3d6229dad4e`.

Baseline lock SHA256: `2BB11748FA18CD23980BE9283A74B7120CACF78A4CD9E948326647FA6CB43747`.

Updated lock SHA256: `B54F95CE66AB10BFA35F939F6DA892BCD508FB08DD0FC1E1B5568D3F74ECD7BE`.

Final results:

| Check | Result |
| --- | --- |
| Clean installation of copied manifests with `npm ci --prefix .runlogs/dependency-install-20261010 --no-audit --no-fund` from the worktree root | Exit 0; installed 107 packages. No source files copied. The isolated lock's SHA256 matches the updated lock above. |
| `node node_modules/typescript/bin/tsc --noEmit` | Exit 0. |
| `node node_modules/typescript/bin/tsc --noEmit --moduleResolution Bundler --module ESNext --target ES2020 --types node --skipLibCheck vite.config.ts` | Exit 0; validates the Vite config without emitting files. |
| `npm run build` | Exit 0; Vite 8.2.2, 50 modules transformed. CSS 32.37 kB, JS 313.25 kB. Non-fatal plugin timing notice only. |
| PostCSS/Tailwind and postcss-nested probes | Exit 0; both output hashes are byte-for-byte identical to the baseline hashes above. |
| Flat selector regression | Exit 0; 20,000 `.a` classes parsed and round-tripped correctly (120 ms observed, not an acceptance timing threshold). |
| Indexed source-map regression | Exit 0; negative, fractional, infinite, NaN, and excessive safe-integer line offsets rejected. A normal indexed offset maps to `input.js`, line 1, column 0. |
| `npm ls --depth=0` and `npm ls postcss-selector-parser source-map-js` | Exit 0; patched versions resolved for both selector-parser consumers and PostCSS. |
| Structural baseline/current lock comparison | Exit 0; identical package-node set, exactly two changed nodes, and only version/URL/integrity differ. All other metadata and direct dependencies unchanged. |
| `npm audit --package-lock-only --json` | Exit 1; 5 high, 0 moderate, 0 critical; residual nodes are braces, chokidar, fast-glob, micromatch, tailwindcss. |
| `npm audit --package-lock-only --omit=dev --json` | Exit 0; 0 findings. This is the dependency graph result, not a production runtime penetration test. |

Final full-audit vulnerability metadata:

```json
{"info":0,"low":0,"moderate":0,"high":5,"critical":0,"total":5}
```

The first `npm ci` in the shared dashboard directory failed with Windows
`EPERM` / exit -4048 while unlinking the native rolldown DLL. No process was
stopped. `npm install --ignore-scripts --no-audit --no-fund` restored the local
dependency installation with exit 0 and retained the exact lock hash; npm
reported a non-fatal cleanup warning for the DLL's retired temporary directory.
Clean `npm ci` reproducibility was then independently verified in the ignored
`.runlogs/dependency-install-20261010` directory. That local validation artifact
is retained, not a new tracked source file. If reproducing in the shared
dashboard directory, coordinate with owners of active dev/build processes
before a destructive node_modules reinstall.

Docker validation is unverified: read-only image inspection found
`nginx:1.27-alpine` but no `node:20-alpine`. No image was pulled or built, and no
container/network/service state was changed. Integration/UI visual scenarios
belong to the other QA/frontend agents and were not claimed here.

## Residual Risk and Required Follow-Up

`npm view braces dist-tags --json` reports latest `3.0.3`, still affected. `npm view 'tailwindcss@3' version --json` ends at `3.4.19`, already locked. No compatible update on the retained Tailwind 3 dependency chain removes the braces advisory. Do not replace braces with an unrelated package, invent a fixed version, suppress audit findings, or use `npm audit fix --force`.

The remaining chain is development/build-time tooling: Tailwind -> chokidar -> braces and Tailwind -> fast-glob/micromatch -> braces. The checked configuration uses repository HTML/TS/TSX content patterns, not attacker-supplied patterns. This bounds observed exposure but does not fix the dependency vulnerability or prove all deployment paths safe. Restrict build/watch inputs to trusted repository content and do not expose build/watch tooling as a public service.

npm proposes Tailwind `4.3.3` as a major fix. Removing this vulnerable chain with that suggested version requires a separate Tailwind 4 migration, not a package-only bump: verify the new PostCSS integration, CSS entry directives, configuration/content detection, utility behavior and visual regressions. Such source/config edits are outside this agent's ownership. This report does not claim the uninstalled Tailwind 4 tree has been audited.

## Reproduce and Deployment Gate

Run locally in PowerShell from `F:\Проекты MyWave\NEW2026\Ruza-qa-20261010\icebeach-wakeclub\apps\dashboard`:

```powershell
npm ci --no-audit --no-fund
node node_modules/typescript/bin/tsc --noEmit
node node_modules/typescript/bin/tsc --noEmit --moduleResolution Bundler --module ESNext --target ES2020 --types node --skipLibCheck vite.config.ts
npm run build
npm audit --package-lock-only --json
npm audit --package-lock-only --omit=dev --json
Get-FileHash package-lock.json -Algorithm SHA256
```

The source-map security regression can be repeated without adding a test file:

```powershell
@'
const assert = require('node:assert/strict');
const {SourceMapConsumer} = require('source-map-js');
const map = {version:3, sources:['input.js'], names:[], mappings:'AAAA'};
const indexed = line => ({version:3,sections:[{offset:{line,column:0},map}]});
for (const line of [-1, 0.5, Infinity, NaN]) {
  assert.throws(() => new SourceMapConsumer(indexed(line)),
    /Section offset line and column must be non-negative integers/);
}
assert.throws(() => new SourceMapConsumer(indexed(Number.MAX_SAFE_INTEGER)),
  /Section offset line must not exceed/);
const normal = new SourceMapConsumer(indexed(1))
  .originalPositionFor({line:2,column:1});
assert.equal(normal.source, 'input.js');
assert.equal(normal.line, 1);
assert.equal(normal.column, 0);
console.log('source-map regression passed');
'@ | node
```

The full audit is expected to remain nonzero while the braces chain is unresolved. Do not mistake this for a clean security gate.

Docker validation, when authorized, from the worktree root:

```powershell
docker build -f icebeach-wakeclub/apps/dashboard/Dockerfile -t ruza-dashboard-dependency-qa icebeach-wakeclub/apps/dashboard
```

Before deployment, validate the resolved Node 20 base-image version satisfies Vite's >=20.19 requirement, run the existing Docker build and UI smoke/visual scenarios, recheck both audits, and explicitly accept/remediate residual build-tool risk. Existing Dockerfiles use `npm install`, not `npm ci`; converting them to a strict lock-only installation is a separate infra change and was not performed here. Retain this exact lockfile and install it with `npm ci` in reproducible QA/CI checks.

## Rollback

Reverse only this agent's two overrides and the two corresponding lockfile node changes, or restore just these two dependency files from their recorded starting version after checking nobody else has changed them. Then run `npm ci` and repeat typecheck/build. Do not reset the shared worktree or restore source files. Rolling back intentionally reintroduces the patched advisories and therefore needs an explicit security decision. No schema/data migration or production rollback is involved.

## Changed Paths

- `icebeach-wakeclub/apps/dashboard/package.json`
- `icebeach-wakeclub/apps/dashboard/package-lock.json`
- `docs/qa/DEPENDENCY_AUDIT.md`
