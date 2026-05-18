#!/usr/bin/env bash
set -euo pipefail

SOURCE_COMPOSE="docker-compose.yml"
INSTALL_ROOT="/opt/aether"
CONFIG_DIR="/etc/aether"
TARGET_DB=""
WORK_DIR=""
APP_SERVICE="app"
POSTGRES_SERVICE="postgres"
SERVICE_NAME="aether-gateway"
SERVICE_USER="aether"
SERVICE_GROUP="aether"
SERVICE_USER_EXPLICIT="false"
SERVICE_GROUP_EXPLICIT="false"
INSTALLER="./install.sh"
IMAGE_REPO="ghcr.io/fawney19/aether"
APP_IMAGE=""
REPLACE_EXISTING="false"
DRY_RUN="false"
SKIP_SINGLE_NODE_INSTALL="false"
KEEP_SOURCE_STOPPED_ON_ERROR="false"
DISK_SPACE_MULTIPLIER="${AETHER_MIGRATION_DISK_SPACE_MULTIPLIER:-2}"
DISK_SPACE_MIN_FREE_BYTES="${AETHER_MIGRATION_MIN_FREE_BYTES:-1073741824}"
REQUEST_BODY_MODE="${AETHER_MIGRATION_REQUEST_BODY_MODE:-full}"
INSTALL_CHANNEL=""
INSTALL_VERSION=""
INSTALL_ARCHIVE=""
INSTALL_DOWNLOAD_URL=""
INSTALL_REPO=""
INSTALL_SOURCE_REF=""

APP_STOPPED="false"
CUTOVER_COMPLETE="false"
SOURCE_COMPOSE_ABS=""
SOURCE_COMPOSE_DIR=""
SOURCE_ENV=""
SOURCE_NETWORK=""
DB_USER=""
DB_NAME=""
DB_PASSWORD=""
SINGLE_NODE_ENV=""
SINGLE_NODE_BIN=""
NOW=""
ENV_FILE_ARGS=()

usage() {
  cat <<'EOF'
Usage: scripts/migrate-pg-to-single-node.sh [options]

Migrate an existing Docker Compose Postgres deployment to Aether single-node.
In this repository, "single-node" means install.sh --mode single-node: system service + SQLite.

Options:
  --source-compose PATH       Source Postgres docker compose file (default: docker-compose.yml)
  --install-root PATH         Single Node install root (default: /opt/aether)
  --config-dir PATH           Single Node config directory (default: /etc/aether)
  --target-db PATH            Final SQLite database path (default: INSTALL_ROOT/data/aether.db)
  --work-dir PATH             Working directory (default: source ./data/pg-to-single-node-<timestamp>)
  --app-service NAME          Source compose app service (default: app)
  --postgres-service NAME     Source compose Postgres service (default: postgres)
  --service-name NAME         Single Node service name (default: aether-gateway)
  --service-user NAME         Single Node service user for SQLite ownership (default: aether)
  --service-group NAME        Single Node service group for SQLite ownership (default: aether)
  --installer PATH            install.sh path (default: ./install.sh)
  --app-image IMAGE           App image used for direct Postgres-to-SQLite copy
  --image-repo IMAGE          Image repository when --app-image is omitted (default: ghcr.io/fawney19/aether)
  --install-channel CHANNEL   Pass --channel to install.sh
  --install-version VERSION   Pass --version to install.sh
  --install-archive PATH      Pass --archive to install.sh
  --install-download-url URL  Pass --download-url to install.sh
  --install-repo OWNER/REPO   Pass --repo to install.sh
  --install-source-ref REF    Pass --source-ref to install.sh
  --replace-existing          Allow replacing an existing target SQLite database
  --dry-run                   Install/preflight and copy to a temporary SQLite DB, but do not stop/switch
  --request-body-mode MODE    Request/response body detail handling: full/1 or omit/2
                            full: migrate all migratable data, including request body details
                            omit: migrate all other data; skip only request body large fields and HTTP body detail tables; source PG is unchanged
  --skip-single-node-install         Skip install.sh preinstall step; requires existing single-node binary
  --keep-source-stopped-on-error
                            Do not auto-restart source app if migration fails after stopping it
  -h, --help                  Show this help

Default cutover behavior:
  1. Derive a single-node env file from the source .env, preserving JWT/encryption keys.
  2. Run install.sh --mode single-node --skip-start with that env file.
  3. Preflight SQLite migrations with the single-node binary.
  4. Check request-body policy and available disk space.
  5. Pull the target single-node image and verify it matches the running source app image ID.
  6. Stop only the source app service; keep Postgres/Redis running.
  7. Copy Postgres records directly into a temporary SQLite DB without JSONL files.
  8. Replace the final SQLite DB and start the single-node service.
EOF
}

log() {
  printf '>>> %s\n' "$*"
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

strip_optional_quotes() {
  local value="$1"
  if [[ "${#value}" -ge 2 ]]; then
    if [[ "${value:0:1}" == "\"" && "${value: -1}" == "\"" ]]; then
      printf '%s' "${value:1:${#value}-2}"
      return
    fi
    if [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
      printf '%s' "${value:1:${#value}-2}"
      return
    fi
  fi
  printf '%s' "$value"
}

absolute_path() {
  local path="$1"
  local dir
  local base

  if [[ "$path" == /* ]]; then
    printf '%s\n' "$path"
    return
  fi

  dir="$(dirname "$path")"
  base="$(basename "$path")"
  printf '%s/%s\n' "$(cd "$dir" && pwd -P)" "$base"
}

absolute_path_maybe_missing() {
  local path="$1"
  if [[ "$path" == /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s/%s\n' "$(pwd -P)" "$path"
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --source-compose)
        [[ $# -ge 2 ]] || die "--source-compose requires a value"
        SOURCE_COMPOSE="$2"
        shift 2
        ;;
      --install-root)
        [[ $# -ge 2 ]] || die "--install-root requires a value"
        INSTALL_ROOT="$2"
        shift 2
        ;;
      --config-dir)
        [[ $# -ge 2 ]] || die "--config-dir requires a value"
        CONFIG_DIR="$2"
        shift 2
        ;;
      --target-db)
        [[ $# -ge 2 ]] || die "--target-db requires a value"
        TARGET_DB="$2"
        shift 2
        ;;
      --work-dir)
        [[ $# -ge 2 ]] || die "--work-dir requires a value"
        WORK_DIR="$2"
        shift 2
        ;;
      --app-service)
        [[ $# -ge 2 ]] || die "--app-service requires a value"
        APP_SERVICE="$2"
        shift 2
        ;;
      --postgres-service)
        [[ $# -ge 2 ]] || die "--postgres-service requires a value"
        POSTGRES_SERVICE="$2"
        shift 2
        ;;
      --service-name)
        [[ $# -ge 2 ]] || die "--service-name requires a value"
        SERVICE_NAME="$2"
        shift 2
        ;;
      --service-user)
        [[ $# -ge 2 ]] || die "--service-user requires a value"
        SERVICE_USER="$2"
        SERVICE_USER_EXPLICIT="true"
        shift 2
        ;;
      --service-group)
        [[ $# -ge 2 ]] || die "--service-group requires a value"
        SERVICE_GROUP="$2"
        SERVICE_GROUP_EXPLICIT="true"
        shift 2
        ;;
      --installer)
        [[ $# -ge 2 ]] || die "--installer requires a value"
        INSTALLER="$2"
        shift 2
        ;;
      --app-image)
        [[ $# -ge 2 ]] || die "--app-image requires a value"
        APP_IMAGE="$2"
        shift 2
        ;;
      --image-repo)
        [[ $# -ge 2 ]] || die "--image-repo requires a value"
        IMAGE_REPO="$2"
        shift 2
        ;;
      --install-channel)
        [[ $# -ge 2 ]] || die "--install-channel requires a value"
        INSTALL_CHANNEL="$2"
        shift 2
        ;;
      --install-version)
        [[ $# -ge 2 ]] || die "--install-version requires a value"
        INSTALL_VERSION="$2"
        shift 2
        ;;
      --install-archive)
        [[ $# -ge 2 ]] || die "--install-archive requires a value"
        INSTALL_ARCHIVE="$2"
        shift 2
        ;;
      --install-download-url)
        [[ $# -ge 2 ]] || die "--install-download-url requires a value"
        INSTALL_DOWNLOAD_URL="$2"
        shift 2
        ;;
      --install-repo)
        [[ $# -ge 2 ]] || die "--install-repo requires a value"
        INSTALL_REPO="$2"
        shift 2
        ;;
      --install-source-ref)
        [[ $# -ge 2 ]] || die "--install-source-ref requires a value"
        INSTALL_SOURCE_REF="$2"
        shift 2
        ;;
      --replace-existing)
        REPLACE_EXISTING="true"
        shift
        ;;
      --dry-run)
        DRY_RUN="true"
        shift
        ;;
      --request-body-mode)
        [[ $# -ge 2 ]] || die "--request-body-mode requires a value"
        REQUEST_BODY_MODE="$2"
        shift 2
        ;;
      --skip-single-node-install)
        SKIP_SINGLE_NODE_INSTALL="true"
        shift
        ;;
      --keep-source-stopped-on-error)
        KEEP_SOURCE_STOPPED_ON_ERROR="true"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
  done
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

normalize_request_body_mode() {
  case "$REQUEST_BODY_MODE" in
    ""|1|full|all|include)
      REQUEST_BODY_MODE="full"
      ;;
    2|omit|skip)
      REQUEST_BODY_MODE="omit"
      ;;
    *)
      die "--request-body-mode must be full/1 or omit/2"
      ;;
  esac
}

apply_service_account_defaults() {
  if [[ "$(uname -s)" == "Darwin" ]]; then
    if [[ "$SERVICE_USER_EXPLICIT" != "true" ]]; then
      SERVICE_USER="_aether"
    fi
    if [[ "$SERVICE_GROUP_EXPLICIT" != "true" ]]; then
      SERVICE_GROUP="_aether"
    fi
  fi
}

sudo_prefix() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi
  require_command sudo
  printf 'sudo'
}

run_privileged() {
  local sudo_bin
  sudo_bin="$(sudo_prefix)"
  if [[ -n "$sudo_bin" ]]; then
    "$sudo_bin" "$@"
  else
    "$@"
  fi
}

env_file_get() {
  local file="$1"
  local wanted="$2"
  local line key value
  local found=""

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    line="$(trim "$line")"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    [[ "$line" == export\ * ]] && line="${line#export }"
    key="$(trim "${line%%=*}")"
    [[ "$key" == "$wanted" ]] || continue
    value="${line#*=}"
    found="$(strip_optional_quotes "$(trim "$value")")"
  done < "$file"

  printf '%s' "$found"
}

should_skip_single_node_env_key() {
  case "$1" in
    APP_IMAGE|LOCAL_APP_IMAGE|APP_PORT|DB_HOST|DB_PORT|DB_USER|DB_NAME|DB_PASSWORD|POSTGRES_*|MYSQL_*|REDIS_HOST|REDIS_PORT|REDIS_PASSWORD|REDIS_URL|AETHER_GATEWAY_DATA_REDIS_URL|AETHER_GATEWAY_DATA_REDIS_KEY_PREFIX|DATABASE_URL|AETHER_DATABASE_URL|AETHER_DATABASE_DRIVER|AETHER_GATEWAY_DATA_POSTGRES_URL|AETHER_RUNTIME_BACKEND|AETHER_RUNTIME_REDIS_URL|AETHER_RUNTIME_REDIS_KEY_PREFIX|AETHER_GATEWAY_DEPLOYMENT_TOPOLOGY|AETHER_GATEWAY_NODE_ROLE|AETHER_GATEWAY_STATIC_DIR|AETHER_LOG_DIR|AETHER_GATEWAY_AUTO_PREPARE_DATABASE)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

validate_env_line_for_copy() {
  local line="$1"
  local line_no="$2"
  [[ "$line" == *'${'* ]] && die "source env line ${line_no} uses variable expansion; write a concrete value before migration"
  [[ "$line" == *'$('* ]] && die "source env line ${line_no} uses command substitution; write a concrete value before migration"
  [[ "$line" == *'`'* ]] && die "source env line ${line_no} uses command substitution; write a concrete value before migration"
  return 0
}

write_single_node_env() {
  local output="$1"
  local line raw_line key
  local line_no=0
  local app_port

  app_port="$(env_file_get "$SOURCE_ENV" "APP_PORT")"
  app_port="${app_port:-8084}"

  : > "$output"
  {
    printf '# Generated by scripts/migrate-pg-to-single-node.sh from %s\n' "$SOURCE_ENV"
    printf '# single-node means install.sh --mode single-node: system service + SQLite.\n\n'
  } >> "$output"

  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    line_no=$((line_no + 1))
    line="${raw_line%$'\r'}"
    line="$(trim "$line")"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    [[ "$line" == export\ * ]] && die "source env line ${line_no} uses export; write KEY=VALUE before migration"
    [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || die "source env line ${line_no} must be KEY=VALUE"
    validate_env_line_for_copy "$line" "$line_no"

    key="${line%%=*}"
    if should_skip_single_node_env_key "$key"; then
      continue
    fi
    printf '%s\n' "$line" >> "$output"
  done < "$SOURCE_ENV"

  {
    printf '\n# Single Node runtime overrides\n'
    printf 'APP_PORT=%s\n' "$app_port"
    printf 'AETHER_GATEWAY_STATIC_DIR=%s/current/frontend\n' "$INSTALL_ROOT"
    printf 'AETHER_LOG_DIR=%s/logs\n' "$INSTALL_ROOT"
    printf 'AETHER_DATABASE_DRIVER=sqlite\n'
    printf 'AETHER_DATABASE_URL=sqlite://%s\n' "$TARGET_DB"
    printf 'DATABASE_URL=sqlite://%s\n' "$TARGET_DB"
    printf 'AETHER_RUNTIME_BACKEND=memory\n'
    printf 'AETHER_GATEWAY_DEPLOYMENT_TOPOLOGY=single-node\n'
    printf 'AETHER_GATEWAY_NODE_ROLE=all\n'
    printf 'AETHER_GATEWAY_AUTO_PREPARE_DATABASE=true\n'
  } >> "$output"
}

append_env_file_args() {
  local file="$1"
  local raw_line line key value
  local line_no=0

  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    line_no=$((line_no + 1))
    line="${raw_line%$'\r'}"
    line="$(trim "$line")"
    [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
    [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || die "env file ${file}:${line_no} must be KEY=VALUE"
    validate_env_line_for_copy "$line" "$line_no"
    key="${line%%=*}"
    value="${line#*=}"
    value="$(strip_optional_quotes "$value")"
    ENV_FILE_ARGS+=("${key}=${value}")
  done < "$file"
}

run_single_node_gateway() {
  local database_url="$1"
  shift
  ENV_FILE_ARGS=()
  append_env_file_args "$SINGLE_NODE_ENV"
  env "${ENV_FILE_ARGS[@]}" \
    AETHER_LOG_DESTINATION=stdout \
    AETHER_DATABASE_DRIVER=sqlite \
    AETHER_DATABASE_URL="$database_url" \
    DATABASE_URL="$database_url" \
    "$SINGLE_NODE_BIN" "$@"
}

compose() {
  docker compose -f "$SOURCE_COMPOSE_ABS" "$@"
}

source_postgres_url() {
  printf 'postgresql://%s:%s@%s:5432/%s' "$DB_USER" "$DB_PASSWORD" "$POSTGRES_SERVICE" "$DB_NAME"
}

copy_image() {
  local tag

  if [[ -n "$APP_IMAGE" ]]; then
    printf '%s\n' "$APP_IMAGE"
    return
  fi

  if [[ -n "$INSTALL_VERSION" ]]; then
    tag="${INSTALL_VERSION#v}"
  else
    case "${INSTALL_CHANNEL:-stable}" in
      stable|latest)
        tag="latest"
        ;;
      rc|beta)
        tag="${INSTALL_CHANNEL}"
        ;;
      *)
        die "unsupported install channel for app image: ${INSTALL_CHANNEL}; pass --app-image"
        ;;
    esac
  fi

  printf '%s:%s\n' "$IMAGE_REPO" "$tag"
}

copy_source_to_sqlite() {
  local target_temp_db="$1"
  local target_url
  local image
  local -a copy_args

  image="$(copy_image)"
  target_url="sqlite:///migration/$(basename "$target_temp_db")"

  rm -f "$target_temp_db" "${target_temp_db}-wal" "${target_temp_db}-shm"
  run_single_node_gateway "sqlite://${target_temp_db}" --migrate
  copy_args=(
    copy
    --source-driver postgres
    --source-url "$(source_postgres_url)"
    --target-driver sqlite
    --target-url "$target_url"
  )
  if [[ "$REQUEST_BODY_MODE" == "omit" ]]; then
    copy_args+=(--omit-request-body-details)
  fi

  docker run --rm \
    --network "$SOURCE_NETWORK" \
    -v "${WORK_DIR}:/migration" \
    --env-file "$SINGLE_NODE_ENV" \
    -e AETHER_LOG_DESTINATION=stdout \
    "$image" \
    "${copy_args[@]}"
}

run_psql_stdin() {
  local sql_file="$1"
  compose exec -T \
    -e "PGPASSWORD=${DB_PASSWORD}" \
    "$POSTGRES_SERVICE" \
    psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -At -f - < "$sql_file"
}

source_database_size_bytes() {
  local sql_file
  local result

  sql_file="${WORK_DIR}/source-database-size.sql"
  if [[ "$REQUEST_BODY_MODE" == "omit" ]]; then
    cat > "$sql_file" <<'SQL'
SELECT GREATEST(
  pg_database_size(current_database())
  - COALESCE(pg_total_relation_size(to_regclass('public.usage_body_blobs')), 0)
  - COALESCE(pg_total_relation_size(to_regclass('public.usage_http_audits')), 0),
  0
);
SQL
  else
    printf 'SELECT pg_database_size(current_database());\n' > "$sql_file"
  fi
  result="$(run_psql_stdin "$sql_file" | tr -d '[:space:]')"
  [[ "$result" =~ ^[0-9]+$ ]] || die "could not determine source Postgres database size"
  printf '%s\n' "$result"
}

file_size_bytes() {
  local path="$1"

  if ! run_privileged test -e "$path"; then
    printf '0\n'
    return
  fi
  run_privileged stat -c '%s' "$path" 2>/dev/null || run_privileged stat -f '%z' "$path" 2>/dev/null || die "could not stat file: ${path}"
}

target_sqlite_size_bytes() {
  local total=0
  local suffix
  local size

  for suffix in "" "-wal" "-shm"; do
    size="$(file_size_bytes "${TARGET_DB}${suffix}")"
    total=$((total + size))
  done
  printf '%s\n' "$total"
}

available_bytes_for_path() {
  local path="$1"
  run_privileged df -Pk "$path" | awk 'NR == 2 { printf "%.0f\n", $4 * 1024 }'
}

filesystem_key_for_path() {
  local path="$1"
  run_privileged df -Pk "$path" | awk 'NR == 2 { print $1 }'
}

format_bytes() {
  local bytes="$1"
  awk -v bytes="$bytes" 'BEGIN {
    if (bytes >= 1073741824) {
      printf "%.1f GiB", bytes / 1073741824
    } else {
      printf "%.1f MiB", bytes / 1048576
    }
  }'
}

assert_available_space() {
  local path="$1"
  local required_bytes="$2"
  local label="$3"
  local available_bytes

  available_bytes="$(available_bytes_for_path "$path")"
  [[ "$available_bytes" =~ ^[0-9]+$ ]] || die "could not determine free disk space for ${path}"
  log "${label} free space: $(format_bytes "$available_bytes"); required: $(format_bytes "$required_bytes")"

  if (( available_bytes < required_bytes )); then
    die "${label} does not have enough free disk space; required $(format_bytes "$required_bytes"), available $(format_bytes "$available_bytes")"
  fi
}

check_disk_space() {
  local source_bytes
  local estimated_db_bytes
  local backup_bytes=0
  local target_dir
  local work_fs
  local target_fs
  local required_bytes

  [[ "$DISK_SPACE_MULTIPLIER" =~ ^[1-9][0-9]*$ ]] || die "AETHER_MIGRATION_DISK_SPACE_MULTIPLIER must be a positive integer"
  [[ "$DISK_SPACE_MIN_FREE_BYTES" =~ ^[0-9]+$ ]] || die "AETHER_MIGRATION_MIN_FREE_BYTES must be a non-negative integer"

  source_bytes="$(source_database_size_bytes)"
  estimated_db_bytes=$((source_bytes * DISK_SPACE_MULTIPLIER + DISK_SPACE_MIN_FREE_BYTES))
  target_dir="$(dirname "$TARGET_DB")"
  run_privileged mkdir -p "$target_dir"

  if [[ "$REPLACE_EXISTING" == "true" ]]; then
    backup_bytes="$(target_sqlite_size_bytes)"
  fi

  log "source Postgres size used for disk estimate: $(format_bytes "$source_bytes")"

  if [[ "$DRY_RUN" == "true" ]]; then
    assert_available_space "$WORK_DIR" "$estimated_db_bytes" "work dir"
    return
  fi

  work_fs="$(filesystem_key_for_path "$WORK_DIR")"
  target_fs="$(filesystem_key_for_path "$target_dir")"
  if [[ "$work_fs" == "$target_fs" ]]; then
    required_bytes=$((estimated_db_bytes * 2 + backup_bytes))
    assert_available_space "$WORK_DIR" "$required_bytes" "work/target filesystem"
  else
    assert_available_space "$WORK_DIR" "$((estimated_db_bytes + backup_bytes))" "work dir"
    assert_available_space "$target_dir" "$estimated_db_bytes" "target DB dir"
  fi
}

check_request_body_artifacts() {
  local sql_file
  local result_file

  sql_file="${WORK_DIR}/check-request-body-artifacts.sql"
  result_file="${WORK_DIR}/request-body-artifacts.txt"

  cat > "$sql_file" <<'SQL'
CREATE TEMP TABLE aether_request_body_artifacts (
  artifact text PRIMARY KEY
) ON COMMIT PRESERVE ROWS;

DO $$
DECLARE
  candidate record;
  has_rows boolean;
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = 'usage_body_blobs'
  ) THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM public.usage_body_blobs LIMIT 1)'
      INTO has_rows;
    IF has_rows THEN
      INSERT INTO aether_request_body_artifacts(artifact)
      VALUES ('usage_body_blobs')
      ON CONFLICT DO NOTHING;
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = 'usage_http_audits'
  ) THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM public.usage_http_audits LIMIT 1)'
      INTO has_rows;
    IF has_rows THEN
      INSERT INTO aether_request_body_artifacts(artifact)
      VALUES ('usage_http_audits')
      ON CONFLICT DO NOTHING;
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = 'usage'
  ) THEN
    FOR candidate IN
      SELECT unnest(ARRAY[
        'request_body',
        'response_body',
        'provider_request_body',
        'client_response_body',
        'request_body_compressed',
        'response_body_compressed',
        'provider_request_body_compressed',
        'client_response_body_compressed'
      ]) AS column_name
    LOOP
      IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'usage'
          AND column_name = candidate.column_name
      ) THEN
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM public.usage WHERE %I IS NOT NULL LIMIT 1)', candidate.column_name)
          INTO has_rows;
        IF has_rows THEN
          INSERT INTO aether_request_body_artifacts(artifact)
          VALUES ('usage.' || candidate.column_name)
          ON CONFLICT DO NOTHING;
        END IF;
      END IF;
    END LOOP;
  END IF;
END
$$;

SELECT artifact FROM aether_request_body_artifacts ORDER BY artifact;
SQL

  run_psql_stdin "$sql_file" > "$result_file"

  if [[ ! -s "$result_file" ]]; then
    return
  fi

  if [[ "$REQUEST_BODY_MODE" == "omit" ]]; then
    warn "source has request/response body details that will not be copied into single-node SQLite"
    cat "$result_file" >&2
    return
  fi

  warn "source has request/response body details that will be copied into single-node SQLite"
  cat "$result_file" >&2
}

source_service_is_running() {
  compose ps --services --status running | grep -Fxq "$1"
}

source_app_container_id() {
  compose ps -q "$APP_SERVICE"
}

docker_image_id() {
  local image="$1"
  docker image inspect -f '{{.Id}}' "$image" 2>/dev/null || true
}

assert_source_and_target_images_match() {
  local target_image="$1"
  local source_container_id
  local source_image_ref
  local source_image_id
  local target_image_id

  source_container_id="$(source_app_container_id)"
  [[ -n "$source_container_id" ]] || die "could not resolve running source app container for service: ${APP_SERVICE}"

  source_image_ref="$(docker inspect -f '{{.Config.Image}}' "$source_container_id")"
  source_image_id="$(docker inspect -f '{{.Image}}' "$source_container_id")"
  target_image_id="$(docker_image_id "$target_image")"
  [[ -n "$target_image_id" ]] || die "target single-node image is not available locally after pull: ${target_image}"

  log "source app image: ${source_image_ref} (${source_image_id})"
  log "target single-node image: ${target_image} (${target_image_id})"

  if [[ "$source_image_id" != "$target_image_id" ]]; then
    die "source app image and target single-node image are different; upgrade the source PG Compose app to ${target_image} before migration"
  fi
}

assert_target_copy_command_available() {
  local target_image="$1"
  local help_output

  help_output="$(docker run --rm --entrypoint aether-gateway "$target_image" copy --help 2>&1 || true)"
  if [[ "$help_output" != *"--source-driver"* || "$help_output" != *"--target-driver"* || "$help_output" != *"--omit-request-body-details"* ]]; then
    die "target single-node image does not support direct PG-to-SQLite copy; use a matching Aether release image"
  fi
}

resolve_source_network() {
  local container_id
  local network

  container_id="$(compose ps -q "$POSTGRES_SERVICE")"
  [[ -n "$container_id" ]] || die "could not resolve container id for source Postgres service: ${POSTGRES_SERVICE}"

  SOURCE_NETWORK=""
  while IFS= read -r network; do
    [[ -n "$network" ]] || continue
    SOURCE_NETWORK="$network"
    break
  done < <(docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$container_id")

  [[ -n "$SOURCE_NETWORK" ]] || die "could not resolve Docker network for source Postgres service: ${POSTGRES_SERVICE}"
}

install_single_node_release() {
  local install_args=(
    "$INSTALLER"
    --mode single-node
    --skip-start
    --install-root "$INSTALL_ROOT"
    --config-dir "$CONFIG_DIR"
    --env-file "$SINGLE_NODE_ENV"
  )

  [[ -z "$INSTALL_CHANNEL" ]] || install_args+=(--channel "$INSTALL_CHANNEL")
  [[ -z "$INSTALL_VERSION" ]] || install_args+=(--version "$INSTALL_VERSION")
  [[ -z "$INSTALL_ARCHIVE" ]] || install_args+=(--archive "$INSTALL_ARCHIVE")
  [[ -z "$INSTALL_DOWNLOAD_URL" ]] || install_args+=(--download-url "$INSTALL_DOWNLOAD_URL")
  [[ -z "$INSTALL_REPO" ]] || install_args+=(--repo "$INSTALL_REPO")
  [[ -z "$INSTALL_SOURCE_REF" ]] || install_args+=(--source-ref "$INSTALL_SOURCE_REF")

  log "installing single-node release without starting service"
  run_privileged env \
    "SERVICE_USER=${SERVICE_USER}" \
    "SERVICE_GROUP=${SERVICE_GROUP}" \
    bash "${install_args[@]}"
}

start_single_node_service() {
  if command -v systemctl >/dev/null 2>&1; then
    run_privileged systemctl restart "$SERVICE_NAME"
    return
  fi

  if command -v launchctl >/dev/null 2>&1; then
    run_privileged launchctl kickstart -k "system/com.aether.gateway"
    return
  fi

  die "neither systemctl nor launchctl is available to start ${SERVICE_NAME}"
}

target_sqlite_file_exists() {
  run_privileged test -e "$TARGET_DB" \
    || run_privileged test -e "${TARGET_DB}-wal" \
    || run_privileged test -e "${TARGET_DB}-shm"
}

finalize_target_db() {
  local temp_db="$1"
  local target_dir
  local backup_path
  local suffix

  target_dir="$(dirname "$TARGET_DB")"
  run_privileged mkdir -p "$target_dir"

  if target_sqlite_file_exists; then
    [[ "$REPLACE_EXISTING" == "true" ]] || die "target DB already exists: ${TARGET_DB}; pass --replace-existing to replace it"
    for suffix in "" "-wal" "-shm"; do
      if run_privileged test -e "${TARGET_DB}${suffix}"; then
        backup_path="${WORK_DIR}/$(basename "$TARGET_DB")${suffix}.backup.${NOW}"
        log "backing up existing target SQLite file to ${backup_path}"
        run_privileged cp -p "${TARGET_DB}${suffix}" "$backup_path"
      fi
    done
  fi

  log "installing migrated SQLite DB at ${TARGET_DB}"
  run_privileged install -m 0640 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$temp_db" "$TARGET_DB"
  for suffix in "-wal" "-shm"; do
    if [[ -e "${temp_db}${suffix}" ]]; then
      run_privileged install -m 0640 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "${temp_db}${suffix}" "${TARGET_DB}${suffix}"
    else
      run_privileged rm -f "${TARGET_DB}${suffix}"
    fi
  done
  run_privileged chown "$SERVICE_USER:$SERVICE_GROUP" "$target_dir"
  run_privileged chmod 0750 "$target_dir"
}

cleanup_on_exit() {
  local status=$?
  if [[ "$status" -eq 0 ]]; then
    return
  fi

  warn "migration failed with exit status ${status}"
  if [[ "$APP_STOPPED" == "true" && "$CUTOVER_COMPLETE" != "true" && "$KEEP_SOURCE_STOPPED_ON_ERROR" != "true" ]]; then
    warn "attempting to restart source compose app because cutover did not complete"
    compose up -d "$APP_SERVICE" || warn "source app restart failed; check ${SOURCE_COMPOSE_ABS}"
  fi
}

preflight() {
  require_command docker
  require_command awk
  require_command df
  docker compose version >/dev/null
  apply_service_account_defaults

  SOURCE_COMPOSE_ABS="$(absolute_path "$SOURCE_COMPOSE")"
  [[ -f "$SOURCE_COMPOSE_ABS" ]] || die "source compose file not found: ${SOURCE_COMPOSE}"
  SOURCE_COMPOSE_DIR="$(dirname "$SOURCE_COMPOSE_ABS")"
  SOURCE_ENV="${SOURCE_COMPOSE_DIR}/.env"
  [[ -f "$SOURCE_ENV" ]] || die "source env file not found: ${SOURCE_ENV}"

  INSTALLER="$(absolute_path "$INSTALLER")"
  [[ -f "$INSTALLER" ]] || die "installer not found: ${INSTALLER}"

  TARGET_DB="${TARGET_DB:-${INSTALL_ROOT}/data/aether.db}"
  TARGET_DB="$(absolute_path_maybe_missing "$TARGET_DB")"
  NOW="$(date +%Y%m%d%H%M%S)"
  if [[ -z "$WORK_DIR" ]]; then
    WORK_DIR="${SOURCE_COMPOSE_DIR}/data/pg-to-single-node-${NOW}"
  fi
  WORK_DIR="$(absolute_path_maybe_missing "$WORK_DIR")"
  mkdir -p "$WORK_DIR"

  SINGLE_NODE_ENV="${WORK_DIR}/aether-gateway.single-node.env"
  SINGLE_NODE_BIN="${INSTALL_ROOT}/current/bin/aether-gateway"
  DB_USER="$(env_file_get "$SOURCE_ENV" "DB_USER")"
  DB_USER="${DB_USER:-postgres}"
  DB_NAME="$(env_file_get "$SOURCE_ENV" "DB_NAME")"
  DB_NAME="${DB_NAME:-aether}"
  DB_PASSWORD="$(env_file_get "$SOURCE_ENV" "DB_PASSWORD")"
  DB_PASSWORD="${DB_PASSWORD:-aether}"

  [[ -n "$(env_file_get "$SOURCE_ENV" "JWT_SECRET_KEY")" ]] || die "source env must define JWT_SECRET_KEY"
  if [[ -z "$(env_file_get "$SOURCE_ENV" "ENCRYPTION_KEY")" && -z "$(env_file_get "$SOURCE_ENV" "AETHER_GATEWAY_DATA_ENCRYPTION_KEY")" ]]; then
    die "source env must define ENCRYPTION_KEY or AETHER_GATEWAY_DATA_ENCRYPTION_KEY"
  fi

  log "source compose: ${SOURCE_COMPOSE_ABS}"
  log "source env: ${SOURCE_ENV}"
  log "single-node install root: ${INSTALL_ROOT}"
  log "single-node config dir: ${CONFIG_DIR}"
  log "target SQLite DB: ${TARGET_DB}"
  log "work dir: ${WORK_DIR}"

  source_service_is_running "$POSTGRES_SERVICE" || die "source Postgres service is not running: ${POSTGRES_SERVICE}"
  resolve_source_network
  log "source Docker network: ${SOURCE_NETWORK}"
}

main() {
  local preflight_db
  local target_temp_db
  local dry_run_db
  local target_image

  parse_args "$@"
  normalize_request_body_mode
  trap cleanup_on_exit EXIT
  preflight

  preflight_db="${WORK_DIR}/single-node-preflight.db"
  target_temp_db="${WORK_DIR}/target-aether.db"
  dry_run_db="${WORK_DIR}/dry-run-target-aether.db"

  write_single_node_env "$SINGLE_NODE_ENV"
  chmod 0600 "$SINGLE_NODE_ENV"

  if [[ "$SKIP_SINGLE_NODE_INSTALL" != "true" ]]; then
    install_single_node_release
  else
    log "skipping single-node install step by request"
  fi
  [[ -x "$SINGLE_NODE_BIN" ]] || die "single-node binary not found or not executable: ${SINGLE_NODE_BIN}"

  log "preflighting single-node SQLite schema migration"
  rm -f "$preflight_db"
  run_single_node_gateway "sqlite://${preflight_db}" --migrate

  log "checking request body detail policy"
  check_request_body_artifacts

  log "checking available disk space before copy"
  check_disk_space

  log "pulling direct-copy app image before downtime"
  target_image="$(copy_image)"
  docker pull "$target_image"

  log "checking target image copy command is available"
  assert_target_copy_command_available "$target_image"

  log "checking source app image matches target single-node image"
  assert_source_and_target_images_match "$target_image"

  if [[ "$DRY_RUN" == "true" ]]; then
    warn "dry-run copy happens while the source app may still be writing; use only for rehearsal"
    log "copying source Postgres tables directly into dry-run SQLite target"
    copy_source_to_sqlite "$dry_run_db"
    log "dry run complete; temporary SQLite DB is ${dry_run_db}"
    return
  fi

  if target_sqlite_file_exists && [[ "$REPLACE_EXISTING" != "true" ]]; then
    die "target DB already exists: ${TARGET_DB}; pass --replace-existing to replace it"
  fi

  log "stopping source app service; Postgres and Redis stay running"
  compose stop "$APP_SERVICE"
  APP_STOPPED="true"

  log "checking request body detail policy again after the app has stopped"
  check_request_body_artifacts

  log "copying source Postgres tables directly into temporary SQLite DB"
  copy_source_to_sqlite "$target_temp_db"

  finalize_target_db "$target_temp_db"

  log "starting single-node service"
  start_single_node_service
  CUTOVER_COMPLETE="true"

  log "migration complete"
  log "source Postgres/Redis volumes were left in place for rollback"
}

main "$@"
