# TIK-025C System Topology

## Phase 1 backend contract

`GET /dashboard/topology` returns one fresh, read-only normalized graph over the
canonical topology:

```text
Device -> Runtime -> Account
```

It does not create graph tables or duplicate domain entities. Device-to-Runtime
edges come only from `Runtime.device_id`; Runtime-to-Account edges come only
from `Account.runtime_id`. Names and labels are never used to infer an edge.

## Visibility and disconnected nodes

All Devices and Runtimes are returned, including Devices with no Runtime and
Runtimes with no visible Account. Accounts follow the Account Registry's normal
visibility rule: rows with `archived_at` are omitted. A visible Account without
an assigned existing Runtime remains in `nodes` with null `runtime_id` and
`device_id` and has no `assigned` edge.

There is no topology pagination or cache. Each request observes the current
database state, so assignment changes are reflected by the next response.

## Stable graph identity and ordering

Node IDs are globally unique and stable:

- `device:<database-id>`
- `runtime:<database-id>`
- `account:<database-id>`

Edge IDs are derived from their exact endpoints. Nodes are ordered by Device,
Runtime, then Account, with ascending entity ID inside each type. `hosts` edges
are ordered by Runtime ID, followed by `assigned` edges ordered by Account ID.
This ordering is part of the Phase 1 contract for predictable rendering and
tests.

## Summary semantics

Counts use the same entities present in the graph:

- `devices`, `runtimes`, `accounts`: total returned entities by type;
- `ready_accounts`: Accounts satisfying the canonical registration readiness
  policy;
- `not_ready_accounts`: returned Accounts not satisfying that policy;
- `attention_accounts`: Accounts with an explicit failure/attention signal:
  registration `failed`, health `warning`/`unhealthy`, or lifecycle
  `restricted`/`suspended`/`disabled`/`archived`.

Pending, unknown, and merely inactive Accounts count as not ready but do not
implicitly count as attention. This avoids inventing health meaning.

## Safety and performance

Account metadata exposes identity, assignment, lifecycle/registration/health
state, the canonical readiness boolean, and `secret_present`. It never exposes
secret types, ciphertext, values, email, phone, notes, or credential key data.
The service uses bounded batched queries for Devices, Runtimes, visible
Accounts, and secret-owning Account IDs; query count does not grow with graph
size. No Job, Content, Publishing, or Workflow nodes are included in Phase 1.
