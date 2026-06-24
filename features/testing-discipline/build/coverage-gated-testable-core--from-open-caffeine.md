# Coverage-Gated Testable Core (build spec) — distilled from open-caffeine

## Summary
A reusable discipline for making a UI/system app provably tested: (1) extract logic behind protocol seams so it runs without the OS, (2) enforce 100% line coverage over everything except a curated, self-policing exclude-list, (3) run that check from a pre-push git hook. Language-agnostic; example is Swift/Xcode.

## Core logic (inlined)

**1. The architecture rule.** For each OS/UI dependency, define a protocol; the live implementation is a thin forwarder (added to EXCLUDE), the logic uses the protocol, tests inject a fake.
```swift
protocol PowerAssertionAPI { func create(...) -> IOReturn; func release(id:) -> IOReturn }
struct IOKitPowerAssertionAPI: PowerAssertionAPI { /* 4 lines forwarding to IOKit -> EXCLUDED */ }
final class SleepAssertion { init(api: PowerAssertionAPI = IOKitPowerAssertionAPI()) ... }  // logic -> 100% tested
// test: SleepAssertion(api: FakePowerAssertionAPI()) — runs the state machine with no hardware
```

**2. The coverage gate script** (`Scripts/coverage-gate.sh`):
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
RESULT="$(mktemp -d)/coverage.xcresult"
xcodegen generate >/dev/null
xcodebuild -project App.xcodeproj -scheme App -destination 'platform=macOS' \
    -enableCodeCoverage YES -resultBundlePath "$RESULT" test >/dev/null
xcrun xccov view --report --json "$RESULT" | REPO="$(pwd)" python3 Scripts/coverage_check.py
```

**3. The checker** (`Scripts/coverage_check.py`, the heart of the pattern):
```python
EXCLUDE = {
    "App/Services/SystemAdapters.swift",        # thin IOKit/SMAppService shims, no logic
    "App/MenuBar/MenuPanelView.swift",          # declarative SwiftUI body, logic in models
    "App/Services/UpdaterService.swift",        # Sparkle SPUStandardUpdaterController wrapper
    # ... every entry carries a one-line justification ...
}
def main():
    repo = os.environ.get("REPO", os.getcwd())
    src_prefix = os.path.join(repo, "App") + os.sep
    report = json.load(sys.stdin)
    failures, excluded_seen, checked = [], set(), 0
    for target in report.get("targets", []):
        for entry in target.get("files", []):
            path = entry["path"]
            if not path.startswith(src_prefix): continue          # skip SPM/test sources
            rel = os.path.relpath(path, repo)
            if rel in EXCLUDE: excluded_seen.add(rel); continue    # exempt shells
            checked += 1
            if entry["coveredLines"] != entry["executableLines"]:  # default-deny: any non-excluded file must be 100%
                failures.append((rel, entry["coveredLines"], entry["executableLines"]))
    stale = EXCLUDE - excluded_seen                                # self-policing: flag exclude entries matching no file
    if stale: print("EXCLUDE entries that matched no file:", sorted(stale))
    if failures:
        for rel, c, t in sorted(failures): print(f"  {rel}: {c}/{t}")
        sys.exit(1)
    print("All logic files at 100% line coverage.")
```

**4. The enforcement hook** (`Scripts/hooks/pre-push`), enabled with `git config core.hooksPath Scripts/hooks`:
```bash
#!/usr/bin/env bash
exec "$(git rev-parse --show-toplevel)/Scripts/coverage-gate.sh"
# emergency escape hatch: pass git's no-verify flag on a single push.
```

## Data contracts
- Input to the checker: `xcrun xccov view --report --json` shape: `{targets: [{files: [{path, coveredLines, executableLines}]}]}`. Adapt the field names for other coverage tools (lcov, `coverage.py`, `c8`/`nyc`) — the policy is identical.

## Dependencies & assumptions
- Swift example: XcodeGen (regenerate project), xcodebuild + `xccov`, python3, git hooks, SwiftLint (complexity/length caps reinforce extract-the-logic). 
- The PATTERN is tool-agnostic: any coverage reporter that emits per-file covered/total lines + any pre-push/CI gate. Port the EXCLUDE policy verbatim.

## To port this, you need:
- [ ] A coverage reporter that gives per-file line counts.
- [ ] A checker that: skips a justified EXCLUDE set, fails if any other file < 100%, default-denies new files, and flags stale EXCLUDE entries.
- [ ] A pre-push hook (or CI required-check) that runs it.
- [ ] An architecture habit: protocol seam per OS/UI dependency, logic in pure types, shells in EXCLUDE.

## Gotchas
- **A pure-100% rule without a disciplined EXCLUDE list is theater** — the justification comments and stale-detection are what make it honest.
- Don't exempt by directory/glob; exempt by explicit file path so new files in an "excluded" folder still get caught.
- 100% LINE coverage is not 100% behavior coverage; pair with meaningful assertions (open-caffeine's tests assert real outcomes, not just execution).
- Running UI that blocks (modal `runModal`, `NSPanel`) belongs in EXCLUDE — it hangs the test runner.

## Origin (reference only)
`Scripts/coverage-gate.sh`, `Scripts/coverage_check.py`, `Scripts/hooks/pre-push`, `.swiftlint.yml`, `project.yml` (coverage scheme), plus the whole `OpenCaffeine/` + `OpenCaffeineTests/` tree as the worked example (22 test files; `Mocks/`, `Fake*` seams).
