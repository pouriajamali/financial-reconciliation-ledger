# CI resource policy

This workflow policy separates documentation checks from unchanged runtime builds. It does not change application behavior, dependencies, release versions, published assets, account budgets or repository protection.

- Push validation targets the default `main` branch; pull requests retain validation without an extra feature-branch push run. Existing tag patterns are preserved. Manual dispatch always requests full native checks.
- A narrow documentation allowlist gets real UTF-8/framing, Markdown fence/relative-link and frozen-evidence JSON checks, plus policy contract tests and pinned actionlint. It does not run .NET/C++ builds or upload native artifacts. This is not an exhaustive prose/security audit.
- Runtime/configuration/fixtures/licenses/provenance/pipeline changes and unknown/failed Git comparisons always require the original native checks. Source, Windows/Linux execution, native package inspection and release/provenance commands remain present. Tags and manual runs cannot take the docs-only route.
- Lightweight checks also statically read the explicit source-package inventories where present, without importing the packager. A new unallowlisted document, symlink mode or computed/unknown inventory cannot hide behind docs-only success.
- Main, tag and manual runs have unique concurrency groups. A docs push cannot replace an earlier pending source run. Only superseded PR runs may be cancelled; classification uses the complete PR delta from its merge base.
- Matrix native jobs use `max-parallel: 1`; Book Replay keeps its two separately defined platform jobs. This is a per-workflow limit, not an account-wide cap. Rollouts are staged rather than starting fourteen heavy runs together.
- Existing native job timeouts remain. Previously unbounded native and comparison/release jobs receive finite timeouts. No source test is replaced by an artificial green check.
- Routine source/PR jobs still build, extract and execute the original native packages, but do not upload the large `bundle-*`, `binary-*` or `tested-*` archives. Finite proof receipts remain. Tag/manual runtime-review runs still upload those required archives; small `checked-source-*` pairs remain on ordinary runs because downstream byte-comparison jobs consume them. No source/native check or release gate is replaced by this upload saving.
- Future Actions uploads retain ordinary source/PR artifacts for **3 days**, and tag/manual review artifacts for **7 days**. These are temporary CI artifacts. Published release archives, checksums, signatures and keys are separate and remain immutable.
- New retention does not delete old artifacts or logs. No artifact/cache deletion, paid capacity, self-hosted runner, account permission or budget change is performed by this policy. Any historical cleanup requires a separately reviewed inventory and explicit authorization.

The lightweight job uses only the standard Ubuntu runner, Python's standard library, and actionlint 1.7.12 downloaded from its official release with an exact archive SHA256. It does not claim optional external ShellCheck/Pyflakes results. Current account storage usage is not inferred from one repository's artifact byte count.

## Preview.3 maintenance allocation proposal

No hosted event is authorized by source preparation. The proposed zero-additional-
cost ceiling is3 necessary events: protected PR if required, exact merged main,
then exact preview.3 tag. Policy5min + two serial native15min gives35min for each
source event; tag adds release5min, for110 summed runner-minutes maximum. Omit an
unneeded PR event; do not add workflow_dispatch duplicates. Manager must reconcile
current free minutes/storage/runner eligibility and serialize heavy work across
maintenance/Wave3 before any event. Existing permissions/protection/native gates
remain; max-parallel1 is not an account-wide cap.

Proposal bounds: native archive100MiB each, source5MiB, proof8MiB per OS/run,
ordinary3-day/tag7-day retention, tag-only large uploads; conservative1643MiB-days
reserved. These are allocation limits, not measured usage or a billing guarantee.
The independent compatibility runner is source-prepared only: binding its exact
control/wrapper/kernel proof and hosted invocation is pending the full execution
allocation. No hosted hardcap or compatibility PASS is inferred from old CI.
All native checks and the actual workflow syntax gate remain required. No event
may skip the new compatibility gate when its approved execution route is wired.
