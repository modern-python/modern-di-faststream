---
summary: Migrate modern_di_faststream from faststream>=0.5,<1 to faststream>=0.7,<0.8 in two PRs — a defensive <0.7 pin (plus build-backend swap + coverage gate), then the 0.7 break dropping the <0.6 middleware shim.
---

# Design: FastStream 0.7 migration (two-PR split)

## Summary

Migrate `modern-di-faststream` from the unbounded-on-the-upper-side
`faststream>=0.5,<1` dependency to `faststream>=0.7,<0.8` in **two PRs
against `main`**:

1. **PR1 — `chore/pin-faststream-pre-0.7`**: Defensive pin + scaffolding +
   build-backend swap. Tighten the dependency to `faststream>=0.5,<0.7`,
   land the already-pending `--cov-fail-under=100` addition, ship the
   already-pending hatchling→`uv_build` build-backend swap, scaffold the
   `planning/specs/` and `planning/plans/` directories (mirroring the
   sister `faststream-concurrent-aiokafka`, `faststream-redis-timers`, and
   `faststream-outbox` projects), create a new `CLAUDE.md` carrying the
   standard `## Workflow` section, and ship this design doc in the same
   commit so PR2 has a home immediately.
2. **PR2 — `chore/faststream-0.7-migration`** (off `main` after PR1
   merges): Bump to `faststream>=0.7,<0.8`. Drop the `_OLD_MIDDLEWARES`
   runtime version-sniff and its <0.6 branch in `main.py` entirely
   (single code path, no compat shim). Fix whatever the bump surfaces —
   most likely the `faststream.types.DecodedMessage` import path, the
   `BaseMiddleware` override `# ty: ignore` comments, and possibly the
   `consume_scope` signature. Single bundled commit.

No new 0.7 features (broker-level `AckPolicy` default, multi-broker,
MQTT, Redis Cluster broker) are adopted.

## Motivation

FastStream 0.7.0 is released. The current `pyproject.toml` declares
`"faststream>=0.5,<1"` — the upper bound permits 0.7 silently. Fresh
resolves will already pull 0.7.x. That means the project is exposed to
whatever breaking changes 0.7 ships, with no documented intent and no
migration commit on record.

PR1 makes the supported range explicit and walks the local environment
back to a <0.7 release so the suite has a stable known-good baseline
before PR2 takes the break through review. PR2 then aligns the package
with the same upstream surface the sister
`faststream-concurrent-aiokafka` (already migrated),
`faststream-redis-timers`, and `faststream-outbox` projects target.

The PR1/PR2 split (vs. a single PR) is policy carried over from the
sister projects: ship the safety pin in minutes, then take the
migration through review on its own merits. The package is at version
`"0"` (sentinel / pre-release) with no stability promise, so a hard
break on the entire <0.7 range is in policy provided it is documented
in the commit/PR.

PR1 also lands two pending unrelated improvements already present in
the working tree — the build-backend swap from hatchling to `uv_build`,
and the `--cov-fail-under=100` pytest gate. Bundling them with the pin
is a conscious choice: the working tree's diff already implies both
changes are intended, and PR1's role as "set the floor before
migrating" naturally absorbs both.

## Scope decisions

- **Drop everything <0.7 in PR2.** Single code path, no `_compat.py`
  shim, no runtime version-sniff. `_OLD_MIDDLEWARES`, its branches, and
  the `from importlib.metadata import version` import all go. Justified
  by the package's `version = "0"` pre-release posture and the sister
  projects' precedent.
- **Pure compat migration in PR2.** No adoption of new 0.7 features.
  Whatever mechanical breaks 0.7 surfaces are the entire scope.
- **PR1 tightens to `>=0.5,<0.7`, not `>=0.6,<0.7`.** Preserves the
  current floor while bounding the upper. PR2 then jumps the floor to
  0.7 in one move. Splitting the floor-tightening across PRs would
  conflate "bound the upper" with "narrow the supported range".
- **PR1 bundles the hatchling→`uv_build` build-backend swap.** The
  working tree already has this change pending. PR1's commit body
  documents both the pin and the backend swap.
- **CLAUDE.md is new in PR1.** This repo has no `CLAUDE.md` yet (unlike
  the kafka sister project, which edited an existing file). The new
  file contains only the standard `## Workflow` section initially;
  commands/architecture/conventions sections are out of scope.
- **`--cov-fail-under=100` is already in the working tree.** PR1 simply
  commits it. The baseline-coverage check the kafka spec ran first is
  unnecessary here because the working diff already implies the
  baseline holds. PR1 implementation step verifies with `just test` at
  the start, in case the baseline drifted.
- **PR2 ships as a single bundled commit.** Splitting could create an
  incoherent intermediate state if a single failure mode requires
  changes across multiple files together.

## Project-specific surface differences from the sister migrations

This project's broker is NATS (in tests; the runtime package is
broker-agnostic and only imports `faststream.*` top-level symbols).
The kafka spec's `FakeConsumer` `type(...).__name__` string-match
concern has **no analog here** — `TestNatsBroker` is used as an
`async with` context wrapper, not via a class-name compare.

Unlike the redis-timers and outbox sister migrations, this package:

- **No `Producer` subclass.** The 0.7 `codec: CodecProto` attribute on
  `ProducerProto` is not an issue.
- **No `TestBroker` subclass.** The new
  `create_publisher_fake_subscriber` instance form is not an issue.
- **No `Registrator` / `Router` subclass exposing per-call
  `middlewares=`.** Upstream's removal of that kwarg from
  `subscriber()` / `publisher()` is not an issue.
- **No `faststream._internal.*` imports.** Verified via
  `grep -rn "_internal" modern_di_faststream/ tests/` returning
  nothing. So 0.7's internal reorganisation does not affect this
  package's source — the surface is entirely public.

What this package *does* touch that 0.7 may break:

- `modern_di_faststream/main.py:9` —
  `from faststream.types import DecodedMessage`. The `faststream.types`
  module was a known reorganisation target in 0.6 already; 0.7 may have
  further consolidated. Highest-likelihood site for a one-line import
  fix.
- `modern_di_faststream/main.py:20-21,56-66` —
  `_OLD_MIDDLEWARES = int(_major) == 0 and int(_minor) < 6` and the
  `if _OLD_MIDDLEWARES:` / `else:` branches for `faststream_context`.
  **Removed entirely in PR2.** The `else` branch (`self.context`)
  becomes the only code path; the `if` branch's
  `faststream.context` access (with
  `# ty: ignore[possibly-missing-submodule]`) is deleted. The
  `from importlib.metadata import version` import at line 4 is also
  removed (only consumer was the version sniff).
- `modern_di_faststream/main.py:34-54` —
  `_DiMiddleware(faststream.BaseMiddleware)` overrides `consume_scope`.
  The `super().__init__(*args, **kwargs)` call at line 37 carries
  `# ty: ignore[invalid-argument-type]`. If 0.7 refined the base
  signature, the ignore may be removable. If the override signature
  itself changed, the body needs to match.
- `modern_di_faststream/main.py:84` —
  `app.broker.add_middleware(_DIMiddlewareFactory(container))` carries
  `# ty: ignore[invalid-argument-type]`. Same — may be droppable in
  0.7.
- Public imports the package and tests use:
  - `import faststream` (for `BaseMiddleware`, `StreamMessage`,
    `ContextRepo`, `FastStream`, `Depends`, `TestApp`, `context`)
  - `from faststream.asgi import AsgiFastStream`
  - `from faststream.types import DecodedMessage` ← suspect
  - `from faststream.nats import NatsBroker, TestNatsBroker`

  Each is a public module path. PR2 implementation step grep-checks
  the installed 0.7 wheel before assuming any of them survived.

## Design

### PR1 — `chore/pin-faststream-pre-0.7`

#### `pyproject.toml`

Combines the new pin change with the two already-pending working-tree
changes:

- `dependencies`: `"faststream>=0.5,<1"` → `"faststream>=0.5,<0.7"`.
- `[build-system]`: `hatchling` → `uv_build>=0.11,<1.0` (already in
  working tree).
- `[tool.hatch.build]` block removed; replaced by `[tool.uv.build-backend]`
  with `module-name = "modern_di_faststream"` and `module-root = ""`
  (already in working tree).
- `[tool.pytest.ini_options].addopts`: append `--cov-fail-under=100`
  (already in working tree).

#### `uv.lock`

- `uv.lock` is gitignored (`.gitignore:21` — verified). Regenerate
  locally via `uv lock` (no `--upgrade`) to confirm the resolver walks
  `faststream` back from whatever's currently resolved to a <0.7
  release. The file does not ship in the commit.
- After regeneration, run `uv sync` so the local virtualenv reflects
  the pin; then re-run `just test` to confirm the suite is green on
  <0.7.

#### `planning/specs/`, `planning/plans/`

- New directories with zero-byte `.gitkeep` files. The `.gitkeep` in
  `planning/specs/` is defensive but technically redundant once this
  design doc populates the dir.

#### `planning/specs/2026-06-04-faststream-0.7-migration-design.md`

- This design doc, committed alongside the pin so PR2 has a home.

#### `CLAUDE.md`

- New file at repo root, containing only the standard `## Workflow`
  section:

  ```markdown
  ## Workflow

  Per-feature workflow: brainstorming → spec in
  `planning/specs/YYYY-MM-DD-<slug>-design.md` → writing-plans →
  plan in `planning/plans/YYYY-MM-DD-<slug>-plan.md` →
  executing-plans / subagent-driven-development →
  requesting-code-review → finishing-a-development-branch.

  Topic slugs are kebab-case descriptions (e.g. `faststream-0.7-migration`),
  not story IDs.
  ```

- Commands / architecture / conventions sections deferred to a
  follow-up. The kafka sister project's `CLAUDE.md` had those sections
  pre-existing; here they would be a new authoring task that is out of
  scope for this migration.

#### `.gitignore`

- No change. The existing `*.pyc`, `.coverage`, `uv.lock`, etc. entries
  are not touched. No basename collision risk because no pattern
  targets `plan.md` or similar. Verify during implementation that
  `git check-ignore -v planning/plans/...` returns no match for the
  spec/plan paths.

#### `Justfile`

- No change. The existing recipes (`install`, `lint`, `lint-ci`,
  `test`, `test-branch`, `publish`) are unaffected. Note: `just
  install` runs `uv lock --upgrade` which would resolve forward to 0.7
  — but the `<0.7` pin holds, so 0.7 cannot slip in. `just test` (which
  `default` chains via `install lint test`) uses `--no-sync`, and PR1's
  manual flow is `uv lock` (no upgrade) → `uv sync` → `just test`.

### PR2 — `chore/faststream-0.7-migration`

#### `pyproject.toml`

- `dependencies`: `"faststream>=0.5,<0.7"` → `"faststream>=0.7,<0.8"`.

#### `uv.lock`

- Gitignored. Regenerate locally via `uv lock --upgrade` to resolve
  `faststream` to a `0.7.x` release. The file does not ship in the
  commit.

#### Discovery loop — `modern_di_faststream/main.py`

After bumping the pin, run `just lint && just test` and treat each
failure as a discrete fix. Expected sites (rough order of likelihood):

- **`main.py:9` — `from faststream.types import DecodedMessage`.**
  Verify with `python -c "from faststream.types import DecodedMessage"`
  and `python -c "import faststream; print(faststream.DecodedMessage)"`
  against the installed 0.7 wheel. Update the import to whatever 0.7
  exposes publicly.
- **`main.py:20-21,56-66` — `_OLD_MIDDLEWARES` compat shim.** Removed
  entirely per the locked-in scope decision. Steps:
  - Delete line 4 (`from importlib.metadata import version`).
  - Delete lines 20-21 (`_major, _minor, *_ = version("faststream").split(".")` and `_OLD_MIDDLEWARES = ...`).
  - Replace lines 56-66 (the `if _OLD_MIDDLEWARES:` / `else:` pair)
    with a single property definition:
    ```python
    @property
    def faststream_context(self) -> faststream.ContextRepo:
        return self.context
    ```
  - The deleted `if` branch carried `# pragma: no cover`, so the
    `--cov-fail-under=100` gate is unaffected by its removal.
- **`main.py:37` — `super().__init__(*args, **kwargs)  # ty: ignore[invalid-argument-type]`.**
  Run `python -c "from faststream import BaseMiddleware; help(BaseMiddleware.__init__)"`
  against the 0.7 wheel. If 0.7 tightened the signature so the call is
  now type-clean, drop the `# ty: ignore`. If still loose, keep.
- **`main.py:39-43` — `consume_scope` override signature.** Run
  `python -c "from faststream import BaseMiddleware; help(BaseMiddleware.consume_scope)"`.
  If 0.7 changed the protocol (new required param, different
  `call_next` shape, different return type), update the override to
  match. The current override has no `# ty: ignore` on the method
  itself, so any structural mismatch surfaces immediately under
  `just lint`.
- **`main.py:84` — `add_middleware(...)  # ty: ignore[invalid-argument-type]`.**
  Same approach: re-run ty after the bump. If 0.7 typed
  `add_middleware` to accept the factory callable cleanly, drop the
  comment.

#### Tests

- `tests/conftest.py` and `tests/test_faststream_di.py` use
  `faststream.FastStream`, `faststream.TestApp`, and
  `faststream.nats.{NatsBroker, TestNatsBroker}`. `tests/dependencies.py`
  uses `faststream.StreamMessage`. Verify each survived; one-line fix
  per moved symbol.
- No subscriber-level `middlewares=` kwarg appears in any test
  (verified via `grep -rn 'middlewares=' tests/` returning nothing).
- No `TestNatsBroker` subclass and no class-name string compares, so
  the kafka-spec `FakeConsumer` regression vector has no analog here.
- `--cov-fail-under=100` (adopted in PR1) is the hard gate: every
  removed code branch's coverage line must be gone, and every new
  branch (e.g., a refactored `consume_scope` body, if any) must be
  exercised.

#### Docs

- `README.md` — spot-check for any 0.6-specific import paths or
  examples. Re-verify during PR2 implementation in case intervening
  commits added one.

## Verification

### PR1

PR1 is done iff:

- Local `uv lock` regenerates without resolving `faststream>=0.7`
  (lockfile gitignored — verified by inspecting the local lock, not
  by diff).
- `uv sync` succeeds against the regenerated lock; installed
  `faststream` is <0.7.
- `just lint` clean (eof-fixer + ruff format + ruff check + ty).
- `just test` green at `--cov-fail-under=100`.
- `git grep -nE '"faststream>=0\.5,<1"|faststream>=0\.7'` returns
  nothing on the branch.
- `git grep -n "hatchling" pyproject.toml` returns nothing.
- `planning/specs/2026-06-04-faststream-0.7-migration-design.md`
  exists in the working tree and is tracked.
- `planning/specs/.gitkeep` and `planning/plans/.gitkeep` exist.
- `CLAUDE.md` exists and contains the `## Workflow` section.
- `uv build` succeeds against the new `uv_build` backend (sanity
  check that the build-system swap didn't break wheel construction).

### PR2

PR2 is done iff:

- Local `uv lock --upgrade` resolves `faststream` to a `0.7.x`
  release.
- `uv sync` succeeds against the regenerated lock.
- `just lint` clean (ruff + ty).
- `just test` green at `--cov-fail-under=100`.
- `git grep -n "faststream>=0\.5,<0\.7\|faststream<0\.7"` returns
  nothing.
- `git grep -n "_OLD_MIDDLEWARES\|from importlib.metadata import version" modern_di_faststream/`
  returns nothing.
- `python -c "from modern_di_faststream import FromDI, faststream_message_provider, fetch_di_container, setup_di"`
  exits 0.
- `tests/test_faststream_di.py` passes against `TestNatsBroker` (the
  integration path is the regression gate for the middleware
  refactor).

## Risk register

- **R1 — Coverage drops after dropping `_OLD_MIDDLEWARES`.** The
  deleted `if _OLD_MIDDLEWARES` branch carried `# pragma: no cover`,
  so removal *shouldn't* affect coverage. But if any path in the
  surviving `consume_scope` body becomes unreachable on 0.7 (e.g.,
  0.7 changed how `call_next` signals exceptions), the gate fails.
  Mitigation: standard TDD-on-test cleanup as part of PR2.
- **R2 — `faststream.types.DecodedMessage` moved.** High-likelihood,
  low-effort: one-line import fix. Mitigation: PR2 implementation
  step inspects the 0.7 wheel before editing.
- **R3 — `BaseMiddleware.consume_scope` signature change.** The
  override currently has no `# ty: ignore` on the method (only on
  `super().__init__`), so any structural mismatch in 0.7 surfaces
  immediately under `just lint`. Mitigation: implementation plan
  reads 0.7's `BaseMiddleware` source before editing the override.
- **R4 — `BaseMiddleware.__init__` signature change.** The
  `# ty: ignore[invalid-argument-type]` comment on `super().__init__`
  may need to stay, go, or be re-tagged. Mitigation: re-run ty after
  the bump and adjust.
- **R5 — `add_middleware` signature change.** Same as R4 but at the
  broker call site. Single-line fix.
- **R6 — Public test imports move.** `NatsBroker`, `TestNatsBroker`,
  `TestApp`, `StreamMessage`, `AsgiFastStream`, `Depends`,
  `ContextRepo`, `FastStream` are all current. Each is a one-line
  import fix if moved. Mitigation: rely on the lint + test pipeline.
- **R7 — Build-system swap regresses wheel construction.** Bundling
  hatchling→`uv_build` into PR1 means a wheel-construction regression
  would surface as a PR1 failure (not separately attributable).
  Mitigation: PR1 implementation runs `uv build` and inspects the
  produced wheel before opening the PR.
- **R8 — `just install` runs `uv lock --upgrade`.** Anyone running
  `just install` on PR1's branch would re-resolve forward — but the
  `<0.7` pin holds, so 0.7 won't slip in. Mentioned for completeness;
  no mitigation needed.

## Unknowns the implementation plan will resolve

1. Whether `faststream.types.DecodedMessage` survived under that path
   in 0.7, or moved (and where).
2. Whether `BaseMiddleware.consume_scope`'s signature changed in 0.7
   (and if so, the shape of the new signature).
3. Whether `BaseMiddleware.__init__` and `add_middleware` are now
   type-clean in 0.7, allowing the two `# ty: ignore[invalid-argument-type]`
   comments to be dropped.
4. Whether `NatsBroker`, `TestNatsBroker`, `TestApp`, `StreamMessage`,
   `AsgiFastStream`, `Depends`, `ContextRepo`, or `FastStream` moved
   module paths.

Each is a small inspection step; none materially shifts the design.

## Out of scope (deferred to follow-up specs)

- Adopting broker-level `AckPolicy` default (per-broker default that
  subscribers inherit unless overridden).
- Adopting multi-broker capability.
- Adopting `RedisClusterBroker`, MQTT, or any other new transport.
- README/docs rewrite beyond mechanical fixes for any moved import
  paths.
- Expanding `CLAUDE.md` beyond the `## Workflow` section (commands,
  architecture, conventions sections come later if/when needed).
- Any `CHANGELOG.md` entry — none exists; package version is `"0"`.

## Order of operations

### PR1 — `chore/pin-faststream-pre-0.7`

1. `git switch -c chore/pin-faststream-pre-0.7`.
2. `just test` — confirm baseline green at `--cov-fail-under=100`
   (the pending working-tree diff already implies it; verify).
3. `pyproject.toml`: change `"faststream>=0.5,<1"` →
   `"faststream>=0.5,<0.7"`. (The build-backend swap and
   `--cov-fail-under=100` are already in the working tree from the
   user's pending diff.)
4. `uv lock && uv sync` (lockfile gitignored — local resolve only).
   Confirm local `faststream` walks back to a <0.7 release.
5. `just test` — confirm green at `--cov-fail-under=100`.
6. `uv build` — sanity check that `uv_build` produces a valid wheel.
7. `mkdir -p planning/specs planning/plans` (already done as part of
   writing this spec).
8. `touch planning/specs/.gitkeep planning/plans/.gitkeep`.
9. Confirm
   `planning/specs/2026-06-04-faststream-0.7-migration-design.md`
   is staged (this file).
10. Create `CLAUDE.md` at repo root with the `## Workflow` section.
11. `just lint`.
12. Single commit:
    `chore: pin faststream <0.7, swap build backend, adopt planning/ workflow`.
    Body lists: pin tightening, build-backend swap, cov-gate
    adoption, planning-dir layout, `CLAUDE.md` creation.
13. Push; open PR. Body re-states the pin reason ("guard users
    against the silent pull of 0.7 the previous `<1` bound allowed;
    companion PR migrates to 0.7 and drops <0.7 support").

### PR2 — `chore/faststream-0.7-migration` (off `main` after PR1 merges)

1. `git switch main && git pull && git switch -c chore/faststream-0.7-migration`.
2. `pyproject.toml`: `"faststream>=0.5,<0.7"` →
   `"faststream>=0.7,<0.8"`.
3. `uv lock --upgrade && uv sync` (lockfile gitignored — local
   resolve only).
4. Inspect 0.7's surface for the affected sites:
   - `python -c "from faststream.types import DecodedMessage"` (or
     alternate path discovery).
   - `python -c "from faststream import BaseMiddleware; help(BaseMiddleware.consume_scope); help(BaseMiddleware.__init__)"`.
   - `python -c "from faststream.nats import NatsBroker, TestNatsBroker; from faststream import TestApp, StreamMessage, FastStream, Depends, ContextRepo, BaseMiddleware; from faststream.asgi import AsgiFastStream"`
     — catch-all for moved public symbols.
5. Edit `modern_di_faststream/main.py`:
   - Delete line 4 (`from importlib.metadata import version`).
   - Delete lines 20-21 (version sniff).
   - Replace lines 56-66 with a single `else`-branch property
     (no `if`/`else`).
   - Fix `DecodedMessage` import per discovery.
   - Re-evaluate `# ty: ignore` comments at `:37` and `:84`; drop if
     0.7 made them unnecessary.
   - Update `consume_scope` signature/body if 0.7 changed it.
6. Fix any moved imports in `tests/`.
7. `just lint && just test` until green at 100% coverage.
8. Single commit:
   `chore: migrate to faststream 0.7 (drop 0.5/0.6 support)`.
   Body enumerates each break point with file pointers (or notes
   "no break points required" if 0.7 is structurally compatible).
9. Push; open PR. Body re-states the explicit drop of <0.7 support
   for downstream consumers.

## Acceptance criteria

- Both PRs' verification commands pass.
- PR1 commit body documents pin + build-backend swap + cov-gate +
  planning scaffold + `CLAUDE.md`.
- PR2 commit body documents each break point (or its absence) and
  the explicit drop of <0.7 support.
- No grep hit for `"faststream>=0.5,<1"`, `"faststream>=0.5,<0.7"`,
  or `_OLD_MIDDLEWARES` after PR2.
