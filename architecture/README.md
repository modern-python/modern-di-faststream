# Architecture

The living truth about what `modern-di-faststream` does **now** — one file per
capability, updated by hand whenever a change ships. The *why* and *how it got
here* live in [`../planning/changes/`](../planning/changes/), and decisions
deliberately taken (including options rejected) in
[`../planning/decisions/`](../planning/decisions/); this directory is the present.

Each capability file is an **implementation-detail** page. Its terse
**invariant summary** ("what Claude must not break") lives in
[`../CLAUDE.md`](../CLAUDE.md) § Architecture.

These files carry **no frontmatter** — they are prose, dated by git.

## Capabilities

- [`dependency-injection.md`](dependency-injection.md) — wiring a `modern-di`
  container into a FastStream app: `setup_di`, the per-message container seam,
  and `FromDI` resolution.

## Promotion rule

Shipping a change hand-edits the affected capability file(s) here to match the
new reality, in the same PR as the code. The change bundle stays in place under
[`../planning/changes/`](../planning/changes/) — no folder move.
