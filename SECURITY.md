# Security

The Gold Brick is software that can influence how people allocate
money. We take that seriously, which means being honest about what this
codebase does and does not protect against. This document describes the
security posture of the `software/` package today.

## What this codebase defends against

1. **Silent code tampering on a running install.**
   `software.integrity` hashes every `.py` file under the package and
   compares the result against a pinned manifest. Any file added,
   removed, or modified without a matching signed manifest update is
   flagged, and the assistant refuses to answer until the mismatch is
   explained.

2. **Silent rewriting of the recommendation history.**
   `software.audit` is a hash-chained, append-only JSONL log. Every
   recommendation, every refusal, and every security event is written
   with the SHA-256 of the previous entry. Modifying, inserting, or
   deleting any past entry breaks the chain and is detectable via
   `AuditLog.verify()`.

3. **Ungrounded financial advice.**
   `software.persona.default_persona` bakes hard rules into every
   system prompt: the assistant must show the numbers before making a
   recommendation, must refuse retirement / college-fund / borrowed-
   money questions, and must append a financial disclaimer. Refusal
   topics are matched before the LLM is called, so a prompt-injection
   that gets the LLM to ignore its instructions still cannot route a
   retirement question to the recommendation path.

4. **Credential leakage into logs or disk.**
   API keys are only ever read from the environment. They are never
   written to disk, never included in the audit log, and never logged
   to stdout.

5. **Path-traversal via `user_id`.**
   `ConversationMemory` and `ProfileStore` reject any `user_id` that
   contains `/` or `..`.

## What this codebase does NOT defend against

We are stating these explicitly so no one is misled.

1. **Arbitrary code execution on a compromised host.**
   If an attacker already has shell access with the same privileges as
   the assistant process, they can replace files, manifest, and public
   key all at once. Host hardening is outside the scope of this
   package.

2. **Attacks on the LLM provider.**
   If OpenAI or Anthropic (or whichever backend you configure) is
   compromised, responses may be tainted. The audit log still records
   exactly which numbers the user's question was grounded in, which
   constrains the damage, but the natural-language answer itself is
   only as trustworthy as the backend.

3. **Market manipulation and upstream price feeds.**
   The assistant is only as accurate as the `Coin` parameters passed
   in. We do not currently fetch prices ourselves, and we do not
   defend against manipulated or stale quotes from whatever source you
   provide.

4. **Truly continuous self-patching.**
   We intentionally do not pull and run code from the network on a
   timer. That pattern is how several high-profile supply-chain
   attacks (SolarWinds, 3CX, XZ) succeeded. Updates are opt-in and
   will require a signed release manifest.

## Guidance for operators

- Generate a manifest at release time with
  `software.integrity.compute_manifest` and
  `software.integrity.write_manifest`, and ship the manifest alongside
  the code.
- Run `software.integrity.verify_manifest` on startup. Fail closed —
  refuse to answer questions if the report is not `ok`.
- Run `software.audit.AuditLog.verify` periodically and alert on any
  mismatch.
- Keep the `data/` directory on a filesystem the assistant can write
  to but outside users can only read (so they can audit it) or not see
  at all (so PII stays contained). Do not back it up to a location
  that rewrites history.
- Rotate API keys regularly. If a key leaks, revoke it at the provider
  first, then update the environment.

## Reporting

If you find a vulnerability, please open a private security advisory
on GitHub rather than a public issue.
