# Postgres to Aether Single Node Migration

Chinese version: [pg-to-single-node-migration.zh-CN.md](pg-to-single-node-migration.zh-CN.md)

This runbook migrates an existing Docker Compose Postgres deployment to Aether
single-node. In this repository, **single-node** means the default SQLite installer mode:
`install.sh --mode single-node`, a system service backed by SQLite. The Docker Compose
single-node template is `docker-compose.single-node.yml`, exposed through `--mode compose-single-node`.

The migration script is:

```bash
scripts/migrate-pg-to-single-node.sh
```

If the target should stay on Docker Compose instead of becoming a system
service, use the image-based Compose migration script:

```bash
scripts/migrate-pg-compose-to-single-node.sh
```

Both migration scripts pull/install the target single-node version before
downtime, stop only the source `app`, copy Postgres records directly into a
temporary SQLite DB without writing a JSONL file, replace the target
`aether.db`, and start single-node.

You can also use the installer as the unified entrypoint and let `--mode`
select the migration target:

```bash
# In interactive mode, first choose the target deployment mode:
#   1) Docker Compose standard deployment (Postgres + Redis)
#   2) Docker Compose single-node deployment (SQLite)
#   3) System service single-node deployment (SQLite)
# After choosing 2 or 3, choose the data initialization mode:
#   1) Fresh initialization (do not migrate existing data)
#   2) Migrate from an existing Docker Compose PG database
install.sh

# Migrate into a new single-node Docker Compose directory.
install.sh \
  --mode compose-single-node \
  --migrate-from-compose /root/Aether/docker-compose.yml \
  --compose-dir /opt/aether-single \
  --replace-existing

# Migrate into the system service + SQLite layout.
sudo install.sh \
  --mode single-node \
  --migrate-from-compose /root/Aether/docker-compose.yml \
  --replace-existing
```

Interactive mode first asks for the target deployment shape. If the target is
`compose-single-node` or `single-node`, the installer then asks for the data
initialization mode: fresh initialization, or migration from an existing Docker
Compose PG database. If you choose migration, it tries to detect the source PG
Compose file from `docker compose ls`, then verifies that the Compose config
contains the default `app` and `postgres` services. If exactly one match is
found, it is used as the default prompt value. If detection is ambiguous or
fails, the installer stops; rerun it with `--migrate-from-compose` to specify
the source compose path.

The installer only normalizes the entrypoint: `compose-single-node` delegates to
`scripts/migrate-pg-compose-to-single-node.sh`, while `single-node` delegates to
`scripts/migrate-pg-to-single-node.sh`.

## What It Does

The script keeps the production cutover window short:

1. Reads the source Compose `.env`.
2. Builds a single-node env file that preserves `JWT_SECRET_KEY`, `ENCRYPTION_KEY` or
   `AETHER_GATEWAY_DATA_ENCRYPTION_KEY`, admin settings, port, and app config.
3. Installs the single-node release with `install.sh --mode single-node --skip-start`.
4. Preflights SQLite migrations with the installed single-node binary.
5. Pulls the target single-node image, confirms its `copy` command is available,
   and verifies that its Docker image ID matches the currently running source
   `app` image ID.
6. Uses the target SQLite schema as the migration plan: same-name source
   Postgres tables and columns are copied into the temporary SQLite DB.
7. Applies the compressed body and HTTP body detail policy. The default is full,
   and you can opt into an omit mode for large artifacts.
8. Checks that the work directory and target SQLite directory have enough free
   disk space for the temporary and final SQLite files.
9. Stops only the source `app` service, leaving Postgres and Redis running.
10. Copies source Postgres records directly into a temporary SQLite database
   without generating JSONL files.
11. Replaces the target SQLite DB, including SQLite `-wal`/`-shm` sidecar files
    when present, and starts the single-node service.

The image check compares Docker image IDs, not just tag strings. If both source
and target say `latest` but resolve to different image IDs, migration stops.
Upgrade the source PG Compose `app` to the target single-node version first,
verify it is healthy, then run the migration. The scripts also check that the
target image supports direct copy and the request-body omit flag; using a new
script with an old image stops before cutover to avoid missing data.

## Production Cutover

Before production cutover, take a normal server backup or snapshot. Then run:

```bash
sudo scripts/migrate-pg-to-single-node.sh \
  --source-compose /root/Aether/docker-compose.yml \
  --replace-existing
```

For Docker Compose single-node cutover instead of a system service:

```bash
scripts/migrate-pg-compose-to-single-node.sh \
  --source-compose /root/Aether/docker-compose.yml \
  --replace-existing
```

The source Postgres compose directory and target single-node compose directory
can be different. For example:

```bash
install.sh \
  --mode compose-single-node \
  --migrate-from-compose /root/Aether/docker-compose.yml \
  --compose-dir /opt/aether-single \
  --replace-existing
```

Equivalently, call the lower-level script and pass each target path explicitly:

```bash
scripts/migrate-pg-compose-to-single-node.sh \
  --source-compose /root/Aether/docker-compose.yml \
  --target-compose /opt/aether-single/docker-compose.single-node.yml \
  --target-env /opt/aether-single/.env.single-node \
  --target-db /opt/aether-single/data/aether.db \
  --replace-existing
```

During cutover, the script stops and removes only the source `app` container to
free the fixed `aether-app` container name. Postgres, Redis, and their volumes
remain in place for rollback.

Defaults:

| Setting | Default |
| --- | --- |
| Source Compose | `docker-compose.yml` |
| Single Node install root | `/opt/aether` |
| Single Node config dir | `/etc/aether` |
| Target SQLite DB | `/opt/aether/data/aether.db` |
| Source app service | `app` |
| Source Postgres service | `postgres` |
| Single Node service | `aether-gateway` |

The script writes migration artifacts under `./data/pg-to-single-node-<timestamp>` next
to the source Compose file unless `--work-dir` is provided.

## Rollback

The script leaves the original Postgres and Redis volumes in place. If cutover
finishes but you need to roll back:

```bash
sudo systemctl stop aether-gateway
cd /root/Aether
docker compose -f docker-compose.yml up -d app
```

For the Compose single-node script, rollback is the same idea: start the app
again from the original Postgres compose file.

If the migration fails before cutover completes, the script attempts to restart
the source `app` service automatically. Pass `--keep-source-stopped-on-error` if
you want to inspect the stopped source deployment manually instead.

## Data Coverage Guard

The migration does not maintain a separate business-domain table list. The
target single-node image first builds a temporary SQLite database with its
normal migrations, then `aether-gateway copy` reads that SQLite schema and copies
matching public Postgres tables and columns.

If the source Postgres database has a non-empty public table that does not exist
in the target SQLite schema, the copy stops instead of silently dropping it. It
ignores lifecycle metadata tables such as `_sqlx_migrations` and
`schema_backfills`. Extra source columns that are absent from the target schema
are not copied.

## Request Body Detail Policy

The production migration migrates all migratable data by default. The only
optional exclusion is request body detail data.

When you choose to skip request bodies, the migration does not copy
`usage_body_blobs`, `usage_http_audits`, or legacy `usage` request body columns
such as `request_body`, `provider_request_body`, `response_body`,
`client_response_body`, and `*_body_compressed`.

Interactive installation lets you choose:

```text
1) Full migration: migrate all migratable data, including request body details
2) Skip request bodies: migrate all other data; skip only request body large fields and HTTP body detail tables; source PG is unchanged
```

For non-interactive full runs:

```bash
scripts/migrate-pg-to-single-node.sh \
  --request-body-mode full
```

For non-interactive omit runs:

```bash
scripts/migrate-pg-to-single-node.sh \
  --request-body-mode omit
```

`omit` only skips writing those large artifacts and detail tables into the
target SQLite database. It does not delete or clear the source Postgres data.

## Notes

- Single Node requires root or sudo because it writes `/opt/aether`, `/etc/aether`, and
  the system service definition.
- The script does not decrypt or re-encrypt provider keys. It preserves the
  original encryption key and moves encrypted data as-is.
- Existing target SQLite databases, including `-wal`/`-shm` sidecars, are not
  replaced unless `--replace-existing` is provided.
- Disk space checks use `pg_database_size(current_database()) * 2 + 1 GiB` as the
  conservative estimate for one SQLite copy. If the work directory and target DB
  directory are on the same filesystem, the script requires enough space for both
  the temporary and final SQLite files. With `--request-body-mode omit`, the
  estimate subtracts `usage_body_blobs` and `usage_http_audits` relation sizes.
- For non-standard source Compose files, set `--app-service` and
  `--postgres-service` to match the service names.
