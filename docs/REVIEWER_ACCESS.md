# Reviewer Access

This repo is private by design. It contains the live scanner runtime, the
operator's trade journal, and AGTI paper-journal cron output. An external
reviewer needs read access to evaluate the work; this doc covers the two
supported paths and the rule about not flipping the repo public.

## TL;DR

**Use the collaborator path (A) below unless there is a specific reason to
mirror.** It is the standard practice for private-repo review and avoids
any risk of leaking operator-specific identifiers.

## Path A: reviewer-as-collaborator (recommended)

For a one-off review:

1. Owner -> repo Settings -> Collaborators and teams -> Add people.
2. GitHub handle of the reviewer.
3. Role: **Read**.

The reviewer gets a GitHub invite. Once accepted they can browse the repo,
read every file, comment on commits, open issues. They CANNOT push or
modify anything. Revoke access from the same page when the review is
complete.

This path requires no changes to repo content, no scrubbing of operator
identifiers, no separate mirror.

## Path B: slim public mirror

If the reviewer cannot accept a private invite (different org, contractor
policies, etc.), publish a stripped mirror:

1. Create a new public repo, e.g. `P-U-C/puc-trading-public`.
2. Copy only the M1 + M5 work:
   - `corpus/`
   - `scanner/` (with operator chat_id removed -- already done in the
     scrub; see notes below)
   - `scripts/`
   - `Makefile`
   - `README.md`
   - `docs/DESIGN.md`
   - `docs/REVIEWER_ACCESS.md`
   - `.env.example`
3. **Exclude**: `trades/`, `journal/`, `paper-journal/`. Those contain
   live trade context.
4. Run `make secret-scan` against the mirror tree before pushing.

The `make-review-bundle.sh` script (in `scripts/`) automates this -- it
emits a self-contained `review-bundle/` directory with a redaction notes
file. See `scripts/make-review-bundle.sh` for the exact contents.

## What MUST be scrubbed before any public mirror

These are operator-side identifiers that should never appear in a public
artifact. The repo-level `make secret-scan` target enforces these, but
they are listed here so a human reviewer can verify by eye.

- `TELEGRAM_CHAT_ID` numeric values (e.g. an integer that maps to a real
  Telegram user). The scanner and notify scripts now read this from env
  / `.env` and have NO hardcoded default.
- IBKR account numbers (pattern: `U\d{8}`). The docs that previously
  named one have been redacted to `<account-id>` references with a note
  pointing at the `IBKR_ACCOUNT` env var.
- The operator's real name in trade thesis files. The thesis docs use
  "the operator" / "you" / "we" -- if a new doc introduces a real name,
  it must be redacted before mirror.
- Paths under `/home/ubuntu/.claude/` or similar runtime-private
  directories. Code may reference those paths (since this repo runs on
  that host), but they should not be exposed as documentation /
  examples in a public mirror.

## What is allowed in a public mirror

- The M1 scanner seam (`corpus/capture-schema.ts`, populator, tests,
  loader/validator).
- The M5 deploy glue (with `DEPLOY_PUSH` defaulted off).
- Documentation that explains the architecture without operator
  specifics.
- `.env.example` (placeholder values only).

## Audit trail

When a reviewer is added as a collaborator, record it in this doc so
later operators can see who had access historically:

| Date | Reviewer (GitHub) | Path | Removed |
|---|---|---|---|
| (none yet) | | | |
