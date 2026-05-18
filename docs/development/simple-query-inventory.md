# Aether Data Simple Query Inventory

This inventory tracks repository read paths that are intended to use the
internal `aether-data-query` helpers. The first layer centralizes SQL fragments;
the newer `SelectQuery` layer lets repositories describe simple `SELECT`
queries once and render dialect-specific projections for Postgres and SQLite.

## Included In This Pass

- `background_tasks`
  - `find_run`
  - `list_runs`
  - `list_events`
  - simple `summarize_runs` count/group reads remain behavior-locked in SQL
- `announcements`
  - `find_by_id`
  - `list_announcements`
  - `count_unread_active_announcements`
- `auth_modules`
  - `list_enabled_oauth_providers`
  - `get_ldap_config`
- `oauth_providers`
  - `list_oauth_provider_configs`
  - `get_oauth_provider_config`
- `quota`
  - `find_by_provider_id`
  - `find_by_provider_ids`
  - now uses one `SelectQuery` specification for the quota snapshot projection
    across Postgres and SQLite
- `provider_catalog`
  - provider by-id/provider list reads in PG/SQLite
  - endpoint/key by-id and by-provider-id `IN` reads in PG/SQLite
  - provider key page filters, search, order, limit/offset in PG/SQLite
  - key stats by provider ids in PG/SQLite
- `proxy_nodes`
  - node list/find reads
  - event list/filter reads
- `management_tokens`
  - `list_management_tokens`
  - `get_management_token_with_user`
  - `get_management_token_with_user_by_hash`
- `pool_scores`
  - `find_scores_by_identity`
  - `list_ranked_pool_members`
  - `list_pool_member_scores`
  - `list_pool_member_probe_candidates`
  - `get_pool_member_scores_by_ids`
- `candidates`
  - `list_by_request_id`
  - `list_recent`
  - `list_by_provider_id`
  - `list_finalized_by_endpoint_ids_since`
  - simple finalized status count
- `gemini_file_mappings`
  - list/count filters and search

## Deferred

- `usage` aggregation, dashboard, leaderboard, cache-hit, provider/key/user
  statistics, rebuild paths, and body/blob reads.
- `candidate_selection` JSON/alias matching and scoring.
- `wallet` ledger, order, refund, callback, and redeem-code list logic.
- write/upsert/delete paths, transactions, `RETURNING`, CTEs, window functions,
  advisory locks, and schema compatibility probes.
- `users/auth` and `global_models` still contain additional simple read paths.
  `global_models/sqlite.rs` had pre-existing local edits and must be handled
  carefully in a dedicated slice.

## Helper Coverage

- dialect-aware identifier quoting
- dialect-specific SQL expressions through `DialectSql`
- simple `SELECT` rendering through `SelectQuery`
- `WHERE`/`AND` sequencing
- equality and optional equality filters
- `IN` filters
- case-insensitive contains/search
- whitelisted order-by rendering
- `LIMIT` and `LIMIT/OFFSET`

## Query Abstraction Shape

The intended direction is:

- repository defines table-specific projections, joins, and row mapping
- `SelectQuery` renders `SELECT ... FROM ... JOIN ...` for the active dialect
- `SelectStatement` owns dynamic filters, search, ordering, and pagination with
  stable bind order
- complex SQL remains hand-written until it has enough repeated structure to
  justify a dedicated abstraction
