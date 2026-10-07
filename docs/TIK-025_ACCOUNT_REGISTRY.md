# TIK-025 Account Registry

## Phase 1 backend foundation

The existing `accounts` table remains the canonical identity referenced by
Jobs, Workflows, PublishingSessions, and future registration/scheduling work.
Migration `20261007_0035` adds nullable discovered identity/contact data,
lifecycle, registration and bounded health state, niche/notes/tags, Runtime assignment views,
soft archival, and nullable metric snapshots without changing existing IDs.

`display_name` is the forward contract. The original `name` field remains a
synchronized compatibility alias, and `platform` remains available to existing
clients. Handles may be null until registration discovers them.

## Secret boundary

Account secrets are separate `account_secrets` rows keyed by Account and an
allowlisted purpose. `AccountSecretProvider` encrypts values with Fernet using
the same installation-owned external master key infrastructure as Runtime proxy
credentials. There is no decrypting HTTP endpoint. API responses expose only
`secret_present`, safe secret types, and update timestamps. Missing, unsafe, or
incorrect key material fails closed; there is no fallback cipher or plaintext
storage.

## Lifecycle and queries

DELETE soft-archives the Account so historical execution bindings remain
understandable. Default list/detail selection hides archived rows. List filters
are applied before deterministic `created_at DESC, id DESC` pagination and
support status, niche, tag, Runtime, derived Device, and free-text search.

Runtime assignment is accepted through normal PATCH for compatibility and the
explicit `PUT/DELETE /accounts/{id}/runtime` contract. Device ownership is
always derived through the authoritative Runtime relationship.

## Intentional Phase 1 limits

This phase does not register or log into accounts, handle OTP/CAPTCHA, publish
content, scrape metrics, or modify the frontend. Metrics are operator/API-fed
snapshots only. Phase 2 should consume the safe Account response and separate
secret-write endpoints without ever caching or rendering a secret value.
