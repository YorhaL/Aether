#!/usr/bin/env bash
set -euo pipefail

REPO="${AETHER_REPO:-fawney19/Aether}"
SOURCE_REF="${AETHER_SOURCE_REF:-main}"
VERSION="${AETHER_VERSION:-}"
CHANNEL="${AETHER_CHANNEL:-stable}"
CHANNEL_EXPLICIT="false"
if [[ -n "${AETHER_CHANNEL:-}" ]]; then
    CHANNEL_EXPLICIT="true"
fi
MODE="${AETHER_INSTALL_MODE:-auto}"
INSTALL_ROOT_EXPLICIT="false"
if [[ -n "${INSTALL_ROOT:-}" ]]; then
    INSTALL_ROOT_EXPLICIT="true"
fi
INSTALL_ROOT="${INSTALL_ROOT:-/opt/aether}"
CONFIG_DIR="${CONFIG_DIR:-/etc/aether}"
COMPOSE_DIR="${AETHER_COMPOSE_DIR:-}"
COMPOSE_DIR_EXPLICIT="false"
if [[ -n "${AETHER_COMPOSE_DIR:-}" ]]; then
    COMPOSE_DIR_EXPLICIT="true"
fi
IMAGE_REPO="${AETHER_IMAGE_REPO:-ghcr.io/fawney19/aether}"
APP_IMAGE="${AETHER_APP_IMAGE:-}"
SERVICE_USER_EXPLICIT="false"
SERVICE_GROUP_EXPLICIT="false"
if [[ -n "${SERVICE_USER:-}" ]]; then
    SERVICE_USER_EXPLICIT="true"
fi
if [[ -n "${SERVICE_GROUP:-}" ]]; then
    SERVICE_GROUP_EXPLICIT="true"
fi
SERVICE_USER="${SERVICE_USER:-aether}"
SERVICE_GROUP="${SERVICE_GROUP:-aether}"
SERVICE_NAME="aether-gateway"
LAUNCHD_LABEL="${AETHER_LAUNCHD_LABEL:-com.aether.gateway}"
LAUNCHD_LOG_DIR="${AETHER_LAUNCHD_LOG_DIR:-/var/log/aether}"
ENV_TARGET="${CONFIG_DIR}/aether-gateway.env"
SYSTEMD_UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
LAUNCHD_PLIST_PATH="/Library/LaunchDaemons/${LAUNCHD_LABEL}.plist"
TMP_ROOT=""
ARCHIVE_PATH=""
BUNDLE_DIR=""
ENV_SOURCE=""
SKIP_START="false"
GENERATED_ENV=""
ADMIN_PASSWORD_SOURCE=""
UI_LANG="${AETHER_LANG:-${AETHER_LANGUAGE:-auto}}"
RELEASE_KEEP="${AETHER_RELEASE_KEEP:-3}"
RELEASE_ARCHIVE_URL="${AETHER_RELEASE_ARCHIVE_URL:-${AETHER_DOWNLOAD_URL:-}}"
MIGRATE_FROM_COMPOSE=""
MIGRATE_TARGET_COMPOSE=""
MIGRATE_TARGET_ENV=""
MIGRATE_TARGET_DB=""
MIGRATE_WORK_DIR=""
MIGRATE_APP_SERVICE=""
MIGRATE_POSTGRES_SERVICE=""
MIGRATE_SINGLE_NODE_SERVICE=""
MIGRATE_REPLACE_EXISTING="false"
MIGRATE_REPLACE_TARGET_COMPOSE="false"
MIGRATE_KEEP_SOURCE_STOPPED_ON_ERROR="false"
MIGRATE_INTERACTIVE="false"
MIGRATE_REQUEST_BODY_MODE=""

usage() {
    cat <<'EOF'
Usage: install.sh [options]

Install Aether Gateway.

Options:
  --mode MODE          Deployment mode: compose, compose-single-node, or single-node
                      compose: Docker Compose app + Postgres + Redis
                      compose-single-node: Docker Compose single-node app
                      single-node: single-node system service
                      Linux services use systemd; macOS services use launchd
  --channel CHANNEL    Release channel to resolve when --version is omitted: stable, latest, rc, or beta
                      stable/latest resolves the latest stable tag (default)
                      rc resolves the latest tag like v0.7.0-rc.1
                      beta resolves the latest tag like v0.7.0-beta.1
  --version VERSION    Exact release tag to install, for example v0.7.0-rc.1
  --repo OWNER/REPO    GitHub repository to download from (default: fawney19/Aether)
  --source-ref REF     Source branch/tag used for compose templates (default: main)
  --archive PATH       Install from a local release tarball instead of downloading
  --download-url URL   Download the release archive from this URL instead of GitHub
  --env-file PATH      Use an existing aether-gateway.env file
  --install-root PATH  Install root for system service mode (default: /opt/aether)
                      Also makes the default Docker Compose directory PATH/compose
  --compose-dir PATH   Docker Compose deployment directory (default: current directory)
  --config-dir PATH    Config directory (default: /etc/aether)
  --lang LANG          Installer language: zh or en
  --skip-start         Install files, but do not start Docker Compose or restart the service
  --keep-releases N    Keep the latest N releases, prune older ones (default: 3, 0=disable)
  --migrate-from-compose PATH
                      Migrate an existing Postgres Compose deployment into the selected single-node mode
  --target-compose PATH
                      Migration target compose file for --mode compose-single-node
  --target-env PATH    Migration target env file for --mode compose-single-node
  --target-db PATH     Migration target SQLite DB path
  --work-dir PATH      Migration working directory
  --app-service NAME   Source compose app service for migration
  --postgres-service NAME
                      Source compose Postgres service for migration
  --single-node-service NAME
                      Target compose service for --mode compose-single-node migration
  --replace-existing   Allow replacing an existing target SQLite DB during migration
  --replace-target-compose
                      Overwrite target compose file from the single-node template during migration
  --request-body-mode MODE
                      Request/response body detail handling during migration: full/1 or omit/2
  --keep-source-stopped-on-error
                      Do not auto-restart source app if migration fails after stopping it
  -h, --help           Show this help

Migration examples:
  install.sh --mode compose-single-node --migrate-from-compose /root/Aether/docker-compose.yml --compose-dir /opt/aether-single --replace-existing
  sudo install.sh --mode single-node --migrate-from-compose /root/Aether/docker-compose.yml --replace-existing

Environment overrides:
  AETHER_REPO, AETHER_SOURCE_REF, AETHER_INSTALL_MODE, AETHER_CHANNEL, AETHER_VERSION
  AETHER_LANG or AETHER_LANGUAGE
  AETHER_RELEASE_ARCHIVE_URL or AETHER_DOWNLOAD_URL
  AETHER_LAUNCHD_LABEL, AETHER_LAUNCHD_LOG_DIR, AETHER_RELEASE_KEEP
  AETHER_IMAGE_REPO, AETHER_APP_IMAGE
  INSTALL_ROOT, AETHER_COMPOSE_DIR, CONFIG_DIR, SERVICE_USER, SERVICE_GROUP
  ADMIN_PASSWORD (required for non-interactive first install when generating a new env)
EOF
}

die() {
    if ui_is_zh; then
        echo "错误: $*" >&2
    else
        echo "ERROR: $*" >&2
    fi
    exit 1
}

info() {
    echo ">>> $*" >&2
}

warn() {
    if ui_is_zh; then
        echo "警告: $*" >&2
    else
        echo "WARNING: $*" >&2
    fi
}

ui_is_zh() {
    case "${UI_LANG}" in
        zh|zh-*|cn|chinese|Chinese|中文)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

interactive_tty_available() {
    [[ -r /dev/tty && -w /dev/tty ]]
}

normalize_ui_lang() {
    local value="$1"
    value="$(printf '%s' "${value}" | tr '[:upper:]' '[:lower:]')"
    case "${value}" in
        zh|zh-cn|cn|chinese|中文)
            echo "zh"
            ;;
        en|en-us|english|英语)
            echo "en"
            ;;
        auto|"")
            echo "auto"
            ;;
        *)
            die "unsupported installer language: ${value}; expected zh or en"
            ;;
    esac
}

select_language() {
    UI_LANG="$(normalize_ui_lang "${UI_LANG}")"
    if [[ "${UI_LANG}" != "auto" ]]; then
        return
    fi

    if interactive_tty_available; then
        cat >/dev/tty <<'EOF'

请选择安装语言 / Choose installer language:
  1) 中文
  2) English

请输入选项 / Enter choice [1]:
EOF
        local choice
        IFS= read -r choice </dev/tty || choice=""
        case "${choice:-1}" in
            1)
                UI_LANG="zh"
                ;;
            2)
                UI_LANG="en"
                ;;
            *)
                UI_LANG="zh"
                die "无效的语言选项: ${choice}"
                ;;
        esac
    else
        UI_LANG="en"
    fi
}

cleanup() {
    if [[ -n "${TMP_ROOT}" && -d "${TMP_ROOT}" ]]; then
        rm -rf "${TMP_ROOT}"
    fi
}
trap cleanup EXIT

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --mode)
                [[ $# -ge 2 ]] || die "--mode requires a value"
                MODE="$2"
                shift 2
                ;;
            --channel)
                [[ $# -ge 2 ]] || die "--channel requires a value"
                CHANNEL="$2"
                CHANNEL_EXPLICIT="true"
                shift 2
                ;;
            --version)
                [[ $# -ge 2 ]] || die "--version requires a value"
                VERSION="$2"
                shift 2
                ;;
            --repo)
                [[ $# -ge 2 ]] || die "--repo requires a value"
                REPO="$2"
                shift 2
                ;;
            --source-ref)
                [[ $# -ge 2 ]] || die "--source-ref requires a value"
                SOURCE_REF="$2"
                shift 2
                ;;
            --archive)
                [[ $# -ge 2 ]] || die "--archive requires a path"
                ARCHIVE_PATH="$2"
                shift 2
                ;;
            --download-url|--archive-url|--release-url)
                [[ $# -ge 2 ]] || die "--download-url requires a value"
                RELEASE_ARCHIVE_URL="$2"
                shift 2
                ;;
            --env-file)
                [[ $# -ge 2 ]] || die "--env-file requires a path"
                ENV_SOURCE="$2"
                shift 2
                ;;
            --install-root)
                [[ $# -ge 2 ]] || die "--install-root requires a path"
                INSTALL_ROOT="$2"
                INSTALL_ROOT_EXPLICIT="true"
                shift 2
                ;;
            --compose-dir)
                [[ $# -ge 2 ]] || die "--compose-dir requires a path"
                COMPOSE_DIR="$2"
                COMPOSE_DIR_EXPLICIT="true"
                shift 2
                ;;
            --config-dir)
                [[ $# -ge 2 ]] || die "--config-dir requires a path"
                CONFIG_DIR="$2"
                ENV_TARGET="${CONFIG_DIR}/aether-gateway.env"
                shift 2
                ;;
            --lang|--language)
                [[ $# -ge 2 ]] || die "--lang requires a value"
                UI_LANG="$2"
                shift 2
                ;;
            --skip-start)
                SKIP_START="true"
                shift
                ;;
            --keep-releases)
                [[ $# -ge 2 ]] || die "--keep-releases requires a number"
                RELEASE_KEEP="$2"
                shift 2
                ;;
            --migrate-from-compose)
                [[ $# -ge 2 ]] || die "--migrate-from-compose requires a path"
                MIGRATE_FROM_COMPOSE="$2"
                shift 2
                ;;
            --target-compose)
                [[ $# -ge 2 ]] || die "--target-compose requires a path"
                MIGRATE_TARGET_COMPOSE="$2"
                shift 2
                ;;
            --target-env)
                [[ $# -ge 2 ]] || die "--target-env requires a path"
                MIGRATE_TARGET_ENV="$2"
                shift 2
                ;;
            --target-db)
                [[ $# -ge 2 ]] || die "--target-db requires a path"
                MIGRATE_TARGET_DB="$2"
                shift 2
                ;;
            --work-dir)
                [[ $# -ge 2 ]] || die "--work-dir requires a path"
                MIGRATE_WORK_DIR="$2"
                shift 2
                ;;
            --app-service)
                [[ $# -ge 2 ]] || die "--app-service requires a service name"
                MIGRATE_APP_SERVICE="$2"
                shift 2
                ;;
            --postgres-service)
                [[ $# -ge 2 ]] || die "--postgres-service requires a service name"
                MIGRATE_POSTGRES_SERVICE="$2"
                shift 2
                ;;
            --single-node-service)
                [[ $# -ge 2 ]] || die "--single-node-service requires a service name"
                MIGRATE_SINGLE_NODE_SERVICE="$2"
                shift 2
                ;;
            --replace-existing)
                MIGRATE_REPLACE_EXISTING="true"
                shift
                ;;
            --replace-target-compose)
                MIGRATE_REPLACE_TARGET_COMPOSE="true"
                shift
                ;;
            --request-body-mode)
                [[ $# -ge 2 ]] || die "--request-body-mode requires a value"
                MIGRATE_REQUEST_BODY_MODE="$2"
                shift 2
                ;;
            --keep-source-stopped-on-error)
                MIGRATE_KEEP_SOURCE_STOPPED_ON_ERROR="true"
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

install_os() {
    case "$(uname -s)" in
        Linux)
            echo "linux"
            ;;
        Darwin)
            echo "macos"
            ;;
        *)
            if ui_is_zh; then
                die "Aether 二进制安装仅支持 Linux 和 macOS"
            else
                die "Aether binary install is only supported on Linux and macOS"
            fi
            ;;
    esac
}

is_darwin() {
    [[ "$(install_os)" == "macos" ]]
}

apply_platform_defaults() {
    if is_darwin; then
        if [[ "${SERVICE_USER_EXPLICIT}" != "true" ]]; then
            SERVICE_USER="_aether"
        fi
        if [[ "${SERVICE_GROUP_EXPLICIT}" != "true" ]]; then
            SERVICE_GROUP="_aether"
        fi
    fi
}

require_supported_os() {
    install_os >/dev/null
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        if ui_is_zh; then
            die "请使用 root 运行"
        else
            die "run as root"
        fi
    fi
}

require_systemd() {
    if ! command -v systemctl >/dev/null 2>&1; then
        if ui_is_zh; then
            die "未找到 systemctl"
        else
            die "systemctl not found"
        fi
    fi
}

require_launchd() {
    if ! command -v launchctl >/dev/null 2>&1; then
        if ui_is_zh; then
            die "未找到 launchctl"
        else
            die "launchctl not found"
        fi
    fi
}

require_service_manager() {
    case "$(install_os)" in
        linux)
            require_systemd
            ;;
        macos)
            require_launchd
            ;;
    esac
}

service_manager_name() {
    case "$(install_os)" in
        linux)
            echo "systemd"
            ;;
        macos)
            echo "launchd"
            ;;
    esac
}

select_version() {
    if [[ -n "${VERSION}" || -n "${ARCHIVE_PATH}" || "${CHANNEL_EXPLICIT}" == "true" ]]; then
        return
    fi

    if interactive_tty_available; then
        if ui_is_zh; then
            cat >/dev/tty <<'EOF'

请选择 Aether 版本:
  1) 最新正式版
  2) 最新 RC 预发布版
  3) 最新 Beta 预发布版
  4) 指定 tag，例如 v0.7.0-rc.1

请输入选项 [1]:
EOF
        else
            cat >/dev/tty <<'EOF'

Choose Aether version:
  1) Latest stable release
  2) Latest RC prerelease
  3) Latest beta prerelease
  4) Exact tag, for example v0.7.0-rc.1

Enter choice [1]:
EOF
        fi
        local choice
        IFS= read -r choice </dev/tty || choice=""
        case "${choice:-1}" in
            1)
                CHANNEL="stable"
                ;;
            2)
                CHANNEL="rc"
                ;;
            3)
                CHANNEL="beta"
                ;;
            4)
                if ui_is_zh; then
                    cat >/dev/tty <<'EOF'
请输入准确 tag:
EOF
                else
                    cat >/dev/tty <<'EOF'
Enter exact tag:
EOF
                fi
                IFS= read -r VERSION </dev/tty || VERSION=""
                if [[ -z "${VERSION}" ]]; then
                    if ui_is_zh; then
                        die "准确 tag 不能为空"
                    else
                        die "exact tag cannot be empty"
                    fi
                fi
                ;;
            *)
                if ui_is_zh; then
                    die "无效的版本选项: ${choice}"
                else
                    die "invalid version choice: ${choice}"
                fi
                ;;
        esac
    fi
}

select_mode() {
    case "${MODE}" in
        compose|docker|docker-compose)
            MODE="compose"
            return
            ;;
        compose-single-node|docker-single-node|docker-single-node-compose)
            MODE="compose-single-node"
            return
            ;;
        single-node|service|systemd|launchd|sqlite)
            MODE="single-node"
            return
            ;;
        cluster|multi|multi-node)
            if ui_is_zh; then
                die "集群部署模式暂未开放；请先选择 compose、compose-single-node 或 single-node"
            else
                die "cluster deployment mode is temporarily disabled; choose compose, compose-single-node, or single-node"
            fi
            ;;
        auto|"")
            ;;
        *)
            die "unsupported install mode: ${MODE}; expected compose, compose-single-node, or single-node"
            ;;
    esac

    if interactive_tty_available; then
        if ui_is_zh; then
            cat >/dev/tty <<EOF

请选择 Aether 部署模式:
  1) Docker Compose 标准部署（Postgres + Redis）
  2) Docker Compose 单节点部署（SQLite）
  3) 系统服务单节点部署（SQLite）

请输入选项 [3]:
EOF
        else
            cat >/dev/tty <<EOF

Choose Aether deployment mode:
  1) Docker Compose standard deployment (Postgres + Redis)
  2) Docker Compose single-node deployment (SQLite)
  3) System service single-node deployment (SQLite)

Enter choice [3]:
EOF
        fi
        local choice
        IFS= read -r choice </dev/tty || choice=""
        case "${choice:-3}" in
            1)
                MODE="compose"
                ;;
            2)
                MODE="compose-single-node"
                ;;
            3)
                MODE="single-node"
                ;;
            *)
                if ui_is_zh; then
                    die "无效的部署模式选项: ${choice}"
                else
                    die "invalid deployment mode choice: ${choice}"
                fi
                ;;
        esac
        if [[ -z "${MIGRATE_FROM_COMPOSE}" && "${MODE}" != "compose" ]]; then
            if ui_is_zh; then
                cat >/dev/tty <<'EOF'

请选择数据初始化方式:
  1) 全新初始化（不迁移现有数据）
  2) 从现有 Docker Compose PG 数据库迁移

请输入选项 [1]:
EOF
            else
                cat >/dev/tty <<'EOF'

Choose data initialization mode:
  1) Fresh initialization (do not migrate existing data)
  2) Migrate from an existing Docker Compose PG database

Enter choice [1]:
EOF
            fi
            local init_choice
            IFS= read -r init_choice </dev/tty || init_choice=""
            case "${init_choice:-1}" in
                1)
                    ;;
                2)
                    MIGRATE_INTERACTIVE="true"
                    ;;
                *)
                    if ui_is_zh; then
                        die "无效的数据初始化方式选项: ${init_choice}"
                    else
                        die "invalid data initialization choice: ${init_choice}"
                    fi
                    ;;
            esac
        fi
    else
        MODE="single-node"
    fi
}

prompt_admin_password() {
    if [[ -n "${ADMIN_PASSWORD:-}" ]]; then
        ADMIN_PASSWORD_SOURCE="environment"
        return
    fi

    if interactive_tty_available; then
        local password confirm
        while true; do
            if ui_is_zh; then
                printf '\n请输入初始管理员密码: ' >/dev/tty
            else
                printf '\nEnter initial admin password: ' >/dev/tty
            fi
            stty -echo </dev/tty
            IFS= read -r password </dev/tty || password=""
            stty echo </dev/tty
            if ui_is_zh; then
                printf '\n请再次输入初始管理员密码: ' >/dev/tty
            else
                printf '\nConfirm initial admin password: ' >/dev/tty
            fi
            stty -echo </dev/tty
            IFS= read -r confirm </dev/tty || confirm=""
            stty echo </dev/tty
            printf '\n' >/dev/tty

            [[ -n "${password}" ]] || {
                if ui_is_zh; then
                    echo "管理员密码不能为空。" >/dev/tty
                else
                    echo "Admin password cannot be empty." >/dev/tty
                fi
                continue
            }
            [[ "${password}" == "${confirm}" ]] || {
                if ui_is_zh; then
                    echo "两次输入的密码不一致。" >/dev/tty
                else
                    echo "Passwords did not match." >/dev/tty
                fi
                continue
            }
            ADMIN_PASSWORD="${password}"
            ADMIN_PASSWORD_SOURCE="prompt"
            return
        done
    fi

    if ui_is_zh; then
        die "非交互式安装生成新配置时必须设置 ADMIN_PASSWORD"
    else
        die "ADMIN_PASSWORD is required when installing without an interactive terminal"
    fi
}

detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64)
            echo "amd64"
            ;;
        aarch64|arm64)
            echo "arm64"
            ;;
        *)
            die "unsupported CPU architecture: $(uname -m)"
            ;;
    esac
}

download_to() {
    local url="$1"
    local output="$2"
    local mode="${3:-quiet}"
    local show_progress="false"
    if [[ "${mode}" == "progress" && -t 2 ]]; then
        show_progress="true"
    fi

    if command -v curl >/dev/null 2>&1; then
        if [[ "${show_progress}" == "true" ]]; then
            curl -fL --progress-bar "${url}" -o "${output}"
        else
            curl -fsSL "${url}" -o "${output}"
        fi
    elif command -v wget >/dev/null 2>&1; then
        if [[ "${show_progress}" == "true" ]]; then
            wget -O "${output}" "${url}"
        else
            wget -qO "${output}" "${url}"
        fi
    else
        die "curl or wget is required to download release assets"
    fi
}

download_stdout() {
    local url="$1"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "${url}"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- "${url}"
    else
        die "curl or wget is required to download release metadata"
    fi
}

select_release_download_urls() {
    local original_archive_url="$1"

    if [[ -z "${RELEASE_ARCHIVE_URL}" && interactive_tty_available ]]; then
        if ui_is_zh; then
            cat >/dev/tty <<'EOF'

是否使用下载加速源?
  1) 否，使用原始 GitHub 地址
  2) 是，手动填写新的下载 URL

请输入选项 [1]:
EOF
        else
            cat >/dev/tty <<'EOF'

Use an accelerated download URL?
  1) No, use the original GitHub URL
  2) Yes, enter a replacement download URL

Enter choice [1]:
EOF
        fi

        local choice
        IFS= read -r choice </dev/tty || choice=""
        case "${choice:-1}" in
            1)
                ;;
            2)
                if ui_is_zh; then
                    cat >/dev/tty <<EOF

原始压缩包 URL:
  ${original_archive_url}

请输入新的压缩包下载 URL:
EOF
                else
                    cat >/dev/tty <<EOF

Original archive URL:
  ${original_archive_url}

Enter replacement archive download URL:
EOF
                fi
                IFS= read -r RELEASE_ARCHIVE_URL </dev/tty || RELEASE_ARCHIVE_URL=""
                [[ -n "${RELEASE_ARCHIVE_URL}" ]] || {
                    if ui_is_zh; then
                        die "新的压缩包下载 URL 不能为空"
                    else
                        die "replacement archive download URL cannot be empty"
                    fi
                }
                ;;
            *)
                if ui_is_zh; then
                    die "无效的下载源选项: ${choice}"
                else
                    die "invalid download source choice: ${choice}"
                fi
                ;;
        esac
    fi

    if [[ -z "${RELEASE_ARCHIVE_URL}" ]]; then
        RELEASE_ARCHIVE_URL="${original_archive_url}"
    elif [[ "${RELEASE_ARCHIVE_URL}" != "${original_archive_url}" ]]; then
        if ui_is_zh; then
            info "使用自定义压缩包下载 URL"
            info "原始压缩包 URL: ${original_archive_url}"
        else
            info "using custom archive download URL"
            info "original archive URL: ${original_archive_url}"
        fi
    fi
}

raw_project_url() {
    local path="$1"
    printf 'https://raw.githubusercontent.com/%s/%s/%s' "${REPO}" "${SOURCE_REF}" "${path}"
}

same_path() {
    local left="$1"
    local right="$2"
    local left_dir right_dir left_base right_base

    [[ -e "${left}" && -e "${right}" ]] || return 1

    left_dir="$(cd -- "$(dirname -- "${left}")" && pwd -P)"
    right_dir="$(cd -- "$(dirname -- "${right}")" && pwd -P)"
    left_base="$(basename -- "${left}")"
    right_base="$(basename -- "${right}")"

    [[ "${left_dir}/${left_base}" == "${right_dir}/${right_base}" ]]
}

resolve_compose_dir() {
    if [[ -n "${COMPOSE_DIR}" ]]; then
        return
    fi

    if [[ "${INSTALL_ROOT_EXPLICIT}" == "true" || "${COMPOSE_DIR_EXPLICIT}" == "true" ]]; then
        COMPOSE_DIR="${INSTALL_ROOT}/compose"
    else
        COMPOSE_DIR="$(pwd -P)"
    fi
}

install_project_file() {
    local source_path="$1"
    local target_path="$2"
    local mode="$3"
    local script_dir
    script_dir="$(current_script_dir)"

    install -d -m 0755 "$(dirname "${target_path}")"
    if [[ -f "${script_dir}/${source_path}" ]]; then
        if same_path "${script_dir}/${source_path}" "${target_path}"; then
            chmod "${mode}" "${target_path}"
        else
            install -m "${mode}" "${script_dir}/${source_path}" "${target_path}"
        fi
    else
        download_to "$(raw_project_url "${source_path}")" "${target_path}"
        chmod "${mode}" "${target_path}"
    fi
}

install_generate_keys_script() {
    local target_path="$1"
    local script_dir
    script_dir="$(current_script_dir)"

    install -d -m 0755 "$(dirname "${target_path}")"
    if [[ -f "${script_dir}/generate_keys.sh" ]]; then
        if same_path "${script_dir}/generate_keys.sh" "${target_path}"; then
            chmod 0755 "${target_path}"
        else
            install -m 0755 "${script_dir}/generate_keys.sh" "${target_path}"
        fi
    else
        write_generate_keys_script "${target_path}"
    fi
}

ensure_directory() {
    local path="$1"
    local mode="${2:-0755}"
    if [[ ! -d "${path}" ]]; then
        install -d -m "${mode}" "${path}"
    fi
}

require_compose_runtime() {
    if docker compose version >/dev/null 2>&1; then
        return
    fi

    if command -v docker-compose >/dev/null 2>&1; then
        return
    fi

    if ui_is_zh; then
        die "未找到可用的 Docker Compose，请先安装 Docker 和 Compose 插件"
    else
        die "no usable Docker Compose found; install Docker and the Compose plugin first"
    fi
}

compose_command() {
    if docker compose version >/dev/null 2>&1; then
        printf '%s\n' "docker compose"
    else
        printf '%s\n' "docker-compose"
    fi
}

compose_next_steps() {
    local gateway_port
    local compose_cmd
    compose_cmd="$(compose_command)"
    gateway_port="$(awk -F= '/^[[:space:]]*APP_PORT=/{print $2}' "${COMPOSE_DIR}/.env" | tail -n1 | tr -d '[:space:]')"
    gateway_port="${gateway_port:-8084}"

    cat <<EOF

Install complete.

Docker Compose service:
  cd ${COMPOSE_DIR}
  ${compose_cmd} ps
  ${compose_cmd} logs -f app

Health checks:
  curl -fsS http://127.0.0.1:${gateway_port}/_gateway/health
  curl -fsS http://127.0.0.1:${gateway_port}/readyz

Install directory:
  ${COMPOSE_DIR}

EOF
}

compose_manual_start_steps() {
    local compose_cmd
    compose_cmd="$(compose_command)"

    cat <<EOF

Next steps:
  cd ${COMPOSE_DIR}
  ${compose_cmd} pull
  ${compose_cmd} up -d
  ${compose_cmd} logs -f app

Generate a fresh key set any time:
  cd ${COMPOSE_DIR}
  ./generate_keys.sh
EOF
}

start_compose_deployment() {
    local compose_cmd
    compose_cmd="$(compose_command)"

    info "pulling Docker Compose images"
    if [[ "${compose_cmd}" == "docker compose" ]]; then
        docker compose pull
        info "starting Docker Compose services"
        docker compose up -d
    else
        docker-compose pull
        info "starting Docker Compose services"
        docker-compose up -d
    fi
}

migration_options_requested() {
    [[ -n "${MIGRATE_TARGET_COMPOSE}" ]] && return 0
    [[ -n "${MIGRATE_TARGET_ENV}" ]] && return 0
    [[ -n "${MIGRATE_TARGET_DB}" ]] && return 0
    [[ -n "${MIGRATE_WORK_DIR}" ]] && return 0
    [[ -n "${MIGRATE_APP_SERVICE}" ]] && return 0
    [[ -n "${MIGRATE_POSTGRES_SERVICE}" ]] && return 0
    [[ -n "${MIGRATE_SINGLE_NODE_SERVICE}" ]] && return 0
    [[ "${MIGRATE_REPLACE_EXISTING}" == "true" ]] && return 0
    [[ "${MIGRATE_REPLACE_TARGET_COMPOSE}" == "true" ]] && return 0
    [[ -n "${MIGRATE_REQUEST_BODY_MODE}" ]] && return 0
    [[ "${MIGRATE_KEEP_SOURCE_STOPPED_ON_ERROR}" == "true" ]] && return 0
    return 1
}

normalize_migration_request_body_mode() {
    case "${MIGRATE_REQUEST_BODY_MODE}" in
        ""|1|full|all|include)
            MIGRATE_REQUEST_BODY_MODE="full"
            ;;
        2|omit|skip)
            MIGRATE_REQUEST_BODY_MODE="omit"
            ;;
        *)
            die "--request-body-mode must be full/1 or omit/2"
            ;;
    esac
}

prompt_with_default() {
    local prompt="$1"
    local default_value="$2"
    local value

    if [[ -n "${default_value}" ]]; then
        printf '%s [%s]: ' "${prompt}" "${default_value}" >/dev/tty
    else
        printf '%s: ' "${prompt}" >/dev/tty
    fi
    IFS= read -r value </dev/tty || value=""
    if [[ -z "${value}" ]]; then
        printf '%s\n' "${default_value}"
    else
        printf '%s\n' "${value}"
    fi
}

prompt_yes_no() {
    local prompt="$1"
    local default_value="$2"
    local suffix choice

    case "${default_value}" in
        yes)
            if ui_is_zh; then
                suffix="[y/n，默认 y]"
            else
                suffix="[y/n, default y]"
            fi
            ;;
        *)
            default_value="no"
            if ui_is_zh; then
                suffix="[y/n，默认 n]"
            else
                suffix="[y/n, default n]"
            fi
            ;;
    esac

    while true; do
        printf '%s %s: ' "${prompt}" "${suffix}" >/dev/tty
        IFS= read -r choice </dev/tty || choice=""
        choice="$(printf '%s' "${choice}" | tr '[:upper:]' '[:lower:]')"
        case "${choice:-${default_value}}" in
            y|yes)
                return 0
                ;;
            n|no)
                return 1
                ;;
            *)
                if ui_is_zh; then
                    echo "请输入 y 或 n。" >/dev/tty
                else
                    echo "Enter y or n." >/dev/tty
                fi
                ;;
        esac
    done
}

docker_compose_ls_config_files() {
    local output

    output="$(docker compose ls --format json 2>/dev/null || true)"
    if [[ -n "${output}" && "${output}" == *ConfigFiles* ]]; then
        printf '%s' "${output}" |
            tr '{' '\n' |
            sed -n 's/.*"ConfigFiles"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p'
        return
    fi

    docker compose ls 2>/dev/null | awk 'NR > 1 && NF > 0 { print $NF }'
}

compose_file_has_source_services() {
    local compose_file="$1"
    local app_service="${MIGRATE_APP_SERVICE:-app}"
    local postgres_service="${MIGRATE_POSTGRES_SERVICE:-postgres}"
    local services

    services="$(docker compose -f "${compose_file}" config --services 2>/dev/null || true)"
    [[ -n "${services}" ]] || return 1
    printf '%s\n' "${services}" | grep -Fxq "${app_service}" || return 1
    printf '%s\n' "${services}" | grep -Fxq "${postgres_service}" || return 1
}

append_unique_candidate() {
    local candidate="$1"
    shift
    local existing

    for existing in "$@"; do
        [[ "${existing}" != "${candidate}" ]] || return 1
    done
    printf '%s\n' "${candidate}"
}

detect_source_compose_from_docker_compose_ls() {
    local config_files compose_file candidate
    local -a candidates=()

    command -v docker >/dev/null 2>&1 || return 0
    docker compose version >/dev/null 2>&1 || return 0

    while IFS= read -r config_files || [[ -n "${config_files}" ]]; do
        config_files="$(trim_whitespace "${config_files}")"
        [[ -n "${config_files}" ]] || continue

        # The migration scripts currently accept one source compose file. If the
        # source project was launched with multiple compose files, ask explicitly.
        [[ "${config_files}" != *,* ]] || continue

        compose_file="${config_files}"
        [[ -f "${compose_file}" ]] || continue
        compose_file="$(absolute_path "${compose_file}")"
        compose_file_has_source_services "${compose_file}" || continue
        candidate="$(append_unique_candidate "${compose_file}" "${candidates[@]}" || true)"
        [[ -z "${candidate}" ]] || candidates+=("${candidate}")
    done < <(docker_compose_ls_config_files)

    case "${#candidates[@]}" in
        0)
            return 0
            ;;
        1)
            printf '%s\n' "${candidates[0]}"
            ;;
        *)
            if interactive_tty_available; then
                if ui_is_zh; then
                    echo "从 docker compose ls 找到多个可能的源 Compose，无法安全自动选择：" >/dev/tty
                else
                    echo "docker compose ls found multiple possible source Compose files and cannot choose safely:" >/dev/tty
                fi
                printf '  %s\n' "${candidates[@]}" >/dev/tty
            fi
            return 0
            ;;
    esac
}

collect_interactive_migration_options() {
    local detected_source
    local prompt
    local source_compose_abs
    local source_compose_dir

    [[ "${MIGRATE_INTERACTIVE}" == "true" ]] || return
    interactive_tty_available || die "interactive migration selection requires a terminal"

    if ui_is_zh; then
        cat >/dev/tty <<'EOF'

迁移会先做预检并拉取/安装目标 single-node，再在切换窗口停止源 app。
源 Postgres 和 Redis 会保留，便于回滚。

EOF
    else
        cat >/dev/tty <<'EOF'

Migration will preflight and pull/install the target single-node release first.
During cutover it stops only the source app. Source Postgres and Redis remain for rollback.

EOF
    fi

    if [[ -z "${MIGRATE_FROM_COMPOSE}" ]]; then
        detected_source="$(detect_source_compose_from_docker_compose_ls || true)"
        if [[ -z "${detected_source}" ]]; then
            if ui_is_zh; then
                die "未能通过 docker compose ls 唯一识别源 PG Compose；请使用 --migrate-from-compose 显式指定"
            else
                die "could not uniquely detect source PG Compose from docker compose ls; pass --migrate-from-compose explicitly"
            fi
        fi
        if ui_is_zh; then
            printf '已通过 docker compose ls 探测到源 Compose: %s\n' "${detected_source}" >/dev/tty
        else
            printf 'Detected source Compose from docker compose ls: %s\n' "${detected_source}" >/dev/tty
        fi
        if ui_is_zh; then
            prompt="确认使用该源 Compose 进行迁移"
        else
            prompt="Use this source Compose for migration"
        fi
        if prompt_yes_no "${prompt}" "yes"; then
            MIGRATE_FROM_COMPOSE="${detected_source}"
        else
            if ui_is_zh; then
                die "已取消迁移；如需指定其他源 Compose，请使用 --migrate-from-compose"
            else
                die "migration cancelled; pass --migrate-from-compose to use another source Compose"
            fi
        fi
    fi
    [[ -n "${MIGRATE_FROM_COMPOSE}" ]] || die "--migrate-from-compose cannot be empty"
    source_compose_abs="$(absolute_path "${MIGRATE_FROM_COMPOSE}")"
    source_compose_dir="$(dirname "${source_compose_abs}")"

    if [[ "${MODE}" == "compose-single-node" ]]; then
        if [[ "${COMPOSE_DIR_EXPLICIT}" != "true" ]]; then
            COMPOSE_DIR="${source_compose_dir}-single-node"
        fi
        if ui_is_zh; then
            printf '已自动选择目标 single-node Compose 目录: %s\n' "${COMPOSE_DIR}" >/dev/tty
            prompt="确认使用该目标目录"
        else
            printf 'Selected target single-node Compose directory: %s\n' "${COMPOSE_DIR}" >/dev/tty
            prompt="Use this target directory"
        fi
        if ! prompt_yes_no "${prompt}" "yes"; then
            if ui_is_zh; then
                die "已取消迁移；如需指定其他目标目录，请使用 --compose-dir"
            else
                die "migration cancelled; pass --compose-dir to use another target directory"
            fi
        fi
    fi

    if [[ "${MIGRATE_REPLACE_EXISTING}" != "true" ]]; then
        if ui_is_zh; then
            prompt="如果目标 SQLite 已存在，是否允许备份后替换"
        else
            prompt="If the target SQLite DB already exists, allow backup and replacement"
        fi
        if prompt_yes_no "${prompt}" "no"; then
            MIGRATE_REPLACE_EXISTING="true"
        fi
    fi

    if [[ -z "${MIGRATE_REQUEST_BODY_MODE}" ]]; then
        if ui_is_zh; then
            cat >/dev/tty <<'EOF'

请求体明细迁移策略:
  1) 全部迁移：迁移所有可迁移数据，包括请求体明细
  2) 不迁移请求体：迁移其他所有数据；仅跳过请求体大字段和 HTTP 请求体明细，源 PG 不清除

请输入选项 [1]:
EOF
        else
            cat >/dev/tty <<'EOF'

Request/response body detail migration mode:
  1) Full migration: migrate all migratable data, including request body details
  2) Skip request bodies: migrate all other data; skip only request body large fields and HTTP body detail tables; source PG is unchanged

Enter choice [1]:
EOF
        fi
        local body_choice
        IFS= read -r body_choice </dev/tty || body_choice=""
        MIGRATE_REQUEST_BODY_MODE="${body_choice:-1}"
    fi
    normalize_migration_request_body_mode
}

install_migration_project_file() {
    local source_path="$1"
    local mode="$2"
    local target_path

    ensure_tmp_root
    target_path="${TMP_ROOT}/$(basename "${source_path}")"
    install_project_file "${source_path}" "${target_path}" "${mode}"
    printf '%s\n' "${target_path}"
}

run_compose_single_node_migration() {
    local migration_script
    local target_template
    local source_compose_abs
    local source_compose_dir
    local compose_dir_abs
    local target_compose
    local target_compose_abs
    local target_compose_dir
    local target_env
    local target_env_abs
    local table
    local -a migrate_args

    source_compose_abs="$(absolute_path "${MIGRATE_FROM_COMPOSE}")"
    [[ -f "${source_compose_abs}" ]] || die "source compose file not found: ${MIGRATE_FROM_COMPOSE}"
    source_compose_dir="$(dirname "${source_compose_abs}")"
    compose_dir_abs="$(absolute_path_maybe_missing "${COMPOSE_DIR}")"

    if [[ -n "${MIGRATE_TARGET_COMPOSE}" ]]; then
        target_compose="${MIGRATE_TARGET_COMPOSE}"
    elif [[ "${compose_dir_abs}" == "${source_compose_dir}" ]]; then
        target_compose="${compose_dir_abs}/docker-compose.single-node.yml"
    else
        target_compose="${compose_dir_abs}/docker-compose.yml"
    fi
    target_compose_abs="$(absolute_path_maybe_missing "${target_compose}")"
    target_compose_dir="$(dirname "${target_compose_abs}")"

    if [[ -n "${MIGRATE_TARGET_ENV}" ]]; then
        target_env="${MIGRATE_TARGET_ENV}"
    elif [[ "$(basename "${target_compose_abs}")" == "docker-compose.yml" ]]; then
        target_env="${target_compose_dir}/.env"
    else
        target_env="${target_compose_dir}/.env.single-node"
    fi
    target_env_abs="$(absolute_path_maybe_missing "${target_env}")"

    [[ "${target_compose_abs}" != "${source_compose_abs}" ]] || die "target compose would overwrite the source compose file; pass --target-compose or --compose-dir"
    [[ "${target_env_abs}" != "${source_compose_dir}/.env" ]] || die "target env would overwrite the source .env; pass --target-env or --compose-dir"

    migration_script="$(install_migration_project_file "scripts/migrate-pg-compose-to-single-node.sh" "0755")"
    target_template="$(install_migration_project_file "docker-compose.single-node.yml" "0644")"

    migrate_args=(
        "${migration_script}"
        --source-compose "${source_compose_abs}"
        --target-compose "${target_compose_abs}"
        --target-template "${target_template}"
        --target-env "${target_env_abs}"
        --app-image "$(compose_image)"
    )
    [[ -z "${MIGRATE_TARGET_DB}" ]] || migrate_args+=(--target-db "${MIGRATE_TARGET_DB}")
    [[ -z "${MIGRATE_WORK_DIR}" ]] || migrate_args+=(--work-dir "${MIGRATE_WORK_DIR}")
    [[ -z "${MIGRATE_APP_SERVICE}" ]] || migrate_args+=(--app-service "${MIGRATE_APP_SERVICE}")
    [[ -z "${MIGRATE_POSTGRES_SERVICE}" ]] || migrate_args+=(--postgres-service "${MIGRATE_POSTGRES_SERVICE}")
    [[ -z "${MIGRATE_SINGLE_NODE_SERVICE}" ]] || migrate_args+=(--single-node-service "${MIGRATE_SINGLE_NODE_SERVICE}")
    [[ "${MIGRATE_REPLACE_EXISTING}" != "true" ]] || migrate_args+=(--replace-existing)
    [[ "${MIGRATE_REPLACE_TARGET_COMPOSE}" != "true" ]] || migrate_args+=(--replace-target-compose)
    [[ -z "${MIGRATE_REQUEST_BODY_MODE}" ]] || migrate_args+=(--request-body-mode "${MIGRATE_REQUEST_BODY_MODE}")
    [[ "${MIGRATE_KEEP_SOURCE_STOPPED_ON_ERROR}" != "true" ]] || migrate_args+=(--keep-source-stopped-on-error)

    bash "${migrate_args[@]}"
}

run_single_node_service_migration() {
    local migration_script
    local installer
    local table
    local -a migrate_args

    [[ -z "${MIGRATE_TARGET_COMPOSE}" ]] || die "--target-compose is only valid with --mode compose-single-node"
    [[ -z "${MIGRATE_TARGET_ENV}" ]] || die "--target-env is only valid with --mode compose-single-node"
    [[ -z "${MIGRATE_SINGLE_NODE_SERVICE}" ]] || die "--single-node-service is only valid with --mode compose-single-node"
    [[ "${MIGRATE_REPLACE_TARGET_COMPOSE}" != "true" ]] || die "--replace-target-compose is only valid with --mode compose-single-node"

    migration_script="$(install_migration_project_file "scripts/migrate-pg-to-single-node.sh" "0755")"
    installer="$(install_migration_project_file "install.sh" "0755")"

    migrate_args=(
        "${migration_script}"
        --source-compose "${MIGRATE_FROM_COMPOSE}"
        --installer "${installer}"
        --install-root "${INSTALL_ROOT}"
        --config-dir "${CONFIG_DIR}"
        --service-name "${SERVICE_NAME}"
        --service-user "${SERVICE_USER}"
        --service-group "${SERVICE_GROUP}"
        --app-image "$(compose_image)"
        --install-channel "${CHANNEL}"
        --install-repo "${REPO}"
        --install-source-ref "${SOURCE_REF}"
    )
    [[ -z "${VERSION}" ]] || migrate_args+=(--install-version "${VERSION}")
    [[ -z "${ARCHIVE_PATH}" ]] || migrate_args+=(--install-archive "${ARCHIVE_PATH}")
    [[ -z "${RELEASE_ARCHIVE_URL}" ]] || migrate_args+=(--install-download-url "${RELEASE_ARCHIVE_URL}")
    [[ -z "${MIGRATE_TARGET_DB}" ]] || migrate_args+=(--target-db "${MIGRATE_TARGET_DB}")
    [[ -z "${MIGRATE_WORK_DIR}" ]] || migrate_args+=(--work-dir "${MIGRATE_WORK_DIR}")
    [[ -z "${MIGRATE_APP_SERVICE}" ]] || migrate_args+=(--app-service "${MIGRATE_APP_SERVICE}")
    [[ -z "${MIGRATE_POSTGRES_SERVICE}" ]] || migrate_args+=(--postgres-service "${MIGRATE_POSTGRES_SERVICE}")
    [[ "${MIGRATE_REPLACE_EXISTING}" != "true" ]] || migrate_args+=(--replace-existing)
    [[ -z "${MIGRATE_REQUEST_BODY_MODE}" ]] || migrate_args+=(--request-body-mode "${MIGRATE_REQUEST_BODY_MODE}")
    [[ "${MIGRATE_KEEP_SOURCE_STOPPED_ON_ERROR}" != "true" ]] || migrate_args+=(--keep-source-stopped-on-error)

    bash "${migrate_args[@]}"
}

run_migration_from_compose() {
    if [[ -n "${MIGRATE_REQUEST_BODY_MODE}" ]]; then
        normalize_migration_request_body_mode
    fi

    case "${MODE}" in
        compose-single-node)
            run_compose_single_node_migration
            ;;
        single-node)
            run_single_node_service_migration
            ;;
        compose)
            die "--migrate-from-compose target mode must be compose-single-node or single-node"
            ;;
        *)
            die "unsupported migration target mode: ${MODE}"
            ;;
    esac
}

resolve_version() {
    if [[ -n "${VERSION}" ]]; then
        echo "${VERSION}"
        return
    fi

    local tag=""
    case "${CHANNEL}" in
        stable|latest)
            tag="$(download_stdout "https://api.github.com/repos/${REPO}/releases?per_page=50" |
                sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' |
                grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' |
                head -n1 || true)"
            ;;
        rc)
            tag="$(download_stdout "https://api.github.com/repos/${REPO}/releases?per_page=50" |
                sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' |
                grep -E '^v[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+$' |
                head -n1 || true)"
            ;;
        beta)
            tag="$(download_stdout "https://api.github.com/repos/${REPO}/releases?per_page=50" |
                sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' |
                grep -E '^v[0-9]+\.[0-9]+\.[0-9]+-beta\.[0-9]+$' |
                head -n1 || true)"
            ;;
        *)
            die "unsupported release channel: ${CHANNEL}; expected stable, latest, rc, or beta"
            ;;
    esac
    echo "${tag}"
}

current_script_dir() {
    local source="${BASH_SOURCE[0]}"
    if [[ -n "${source}" && -f "${source}" ]]; then
        cd -- "$(dirname -- "${source}")" && pwd
    else
        pwd
    fi
}

ensure_tmp_root() {
    if [[ -z "${TMP_ROOT}" ]]; then
        TMP_ROOT="$(mktemp -d)"
    fi
}

absolute_path() {
    local path="$1"
    local dir
    local base

    if [[ "${path}" == /* ]]; then
        printf '%s\n' "${path}"
        return
    fi

    dir="$(dirname "${path}")"
    base="$(basename "${path}")"
    printf '%s/%s\n' "$(cd "${dir}" && pwd -P)" "${base}"
}

absolute_path_maybe_missing() {
    local path="$1"
    if [[ "${path}" == /* ]]; then
        printf '%s\n' "${path}"
    else
        printf '%s/%s\n' "$(pwd -P)" "${path}"
    fi
}

local_bundle_dir() {
    local dir
    dir="$(current_script_dir)"
    if [[ -x "${dir}/bin/aether-gateway" && -d "${dir}/frontend" ]]; then
        echo "${dir}"
    fi
}

download_or_unpack_bundle() {
    TMP_ROOT="$(mktemp -d)"
    if [[ -n "${ARCHIVE_PATH}" ]]; then
        [[ -f "${ARCHIVE_PATH}" ]] || die "archive not found: ${ARCHIVE_PATH}"
        info "using local archive ${ARCHIVE_PATH}"
        tar -xzf "${ARCHIVE_PATH}" -C "${TMP_ROOT}"
    else
        local os arch
        os="$(install_os)"
        arch="$(detect_arch)"

        local tag asset base_url archive_url archive_file
        tag="$(resolve_version)"
        [[ -n "${tag}" ]] || die "could not resolve ${CHANNEL} release tag for ${REPO}"
        VERSION="${tag}"
        asset="aether-${tag}-${os}-${arch}.tar.gz"
        base_url="https://github.com/${REPO}/releases/download/${tag}"
        archive_url="${base_url}/${asset}"
        archive_file="${TMP_ROOT}/${asset}"

        select_release_download_urls "${archive_url}"
        if [[ "${RELEASE_ARCHIVE_URL}" == "${archive_url}" ]]; then
            info "downloading ${asset} from ${REPO}"
        elif ui_is_zh; then
            info "从自定义 URL 下载 ${asset}"
        else
            info "downloading ${asset} from custom URL"
        fi
        download_to "${RELEASE_ARCHIVE_URL}" "${archive_file}" progress
        tar -xzf "${archive_file}" -C "${TMP_ROOT}"
    fi

    local bundle
    bundle="$(find "${TMP_ROOT}" -mindepth 1 -maxdepth 1 -type d | head -n1)"
    [[ -n "${bundle}" ]] || die "release archive did not contain a bundle directory"
    [[ -x "${bundle}/bin/aether-gateway" ]] || die "bundle is missing bin/aether-gateway"
    [[ -d "${bundle}/frontend" ]] || die "bundle is missing frontend"
    if [[ -z "${VERSION}" ]]; then
        VERSION="$(derive_local_bundle_version "${bundle}")"
    fi
    BUNDLE_DIR="${bundle}"
}

urlsafe_rand() {
    local bytes="$1"
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -base64 "${bytes}" | tr '+/' '-_' | tr -d '='
    else
        od -An -N "${bytes}" -tx1 /dev/urandom | tr -d ' \n'
    fi
}

write_generate_keys_script() {
    local output="$1"
    local output_dir output_dir_normalized config_dir_normalized
    output_dir="$(dirname "${output}")"
    output_dir_normalized="${output_dir%/}"
    config_dir_normalized="${CONFIG_DIR%/}"
    [[ -n "${output_dir_normalized}" ]] || output_dir_normalized="/"
    [[ -n "${config_dir_normalized}" ]] || config_dir_normalized="/"
    if is_darwin && [[ "${output_dir_normalized}" == "${config_dir_normalized}" ]]; then
        install_config_dir
    else
        install -d -m 0755 "${output_dir}"
    fi
    cat > "${output}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

urlsafe_rand() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -base64 "$1" | tr '+/' '-_' | tr -d '='
    else
        od -An -N "$1" -tx1 /dev/urandom | tr -d ' \n'
    fi
}

cat <<KEYS
JWT_SECRET_KEY=$(urlsafe_rand 32)
ENCRYPTION_KEY=$(urlsafe_rand 32)
KEYS
EOF
    chmod 0755 "${output}"
}

replace_or_append_env() {
    local file="$1"
    local key="$2"
    local value="$3"

    if grep -qE "^#?[[:space:]]*${key}=" "${file}"; then
        local tmp_file
        tmp_file="$(mktemp)"
        awk -v key="${key}" -v value="${value}" '
            BEGIN {
                pattern = "^#?[[:space:]]*" key "="
                replacement = key "=" value
            }
            $0 ~ pattern && replaced == 0 {
                print replacement
                replaced = 1
                next
            }
            { print }
        ' "${file}" > "${tmp_file}"
        cat "${tmp_file}" > "${file}"
        rm -f "${tmp_file}"
    else
        printf '%s=%s\n' "${key}" "${value}" >> "${file}"
    fi
}

trim_whitespace() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "${value}"
}

strip_optional_quotes() {
    local value="$1"
    if [[ ${#value} -ge 2 ]]; then
        if [[ "${value:0:1}" == "\"" && "${value: -1}" == "\"" ]]; then
            value="${value:1:${#value}-2}"
        elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
            value="${value:1:${#value}-2}"
        fi
    fi
    printf '%s' "${value}"
}

is_placeholder_value() {
    local value="$1"
    case "${value}" in
        *change-me*|*change-this*|*your_secure_password_here*|*your_redis_password_here*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

derive_local_bundle_version() {
    local bundle="$1"
    local name
    name="$(basename "${bundle}")"
    case "${name}" in
        aether-*-linux-*|aether-*-macos-*)
            name="${name#aether-}"
            name="${name%-linux-*}"
            name="${name%-macos-*}"
            ;;
    esac
    if [[ -z "${name}" || "${name}" == "." || "${name}" == "/" ]]; then
        name="$(date +%Y%m%d%H%M%S)"
    fi
    echo "${name}"
}

generate_first_install_env() {
    local output="$1"
    local jwt_key encryption_key
    prompt_admin_password
    jwt_key="$(urlsafe_rand 32)"
    encryption_key="$(urlsafe_rand 32)"

    cat > "${output}" <<EOF
ENVIRONMENT=production
TZ=Asia/Shanghai
RUST_LOG=aether_gateway=info
AETHER_LOG_DESTINATION=both
AETHER_LOG_FORMAT=pretty
AETHER_LOG_DIR=${INSTALL_ROOT}/logs
AETHER_LOG_ROTATION=daily
AETHER_LOG_RETENTION_DAYS=7
AETHER_LOG_MAX_FILES=30

APP_PORT=${APP_PORT:-8084}
AETHER_GATEWAY_STATIC_DIR=${INSTALL_ROOT}/current/frontend
AETHER_GATEWAY_VIDEO_TASK_TRUTH_SOURCE_MODE=rust-authoritative
AETHER_GATEWAY_AUTO_PREPARE_DATABASE=true
AETHER_RUNTIME_BACKEND=memory
API_KEY_PREFIX=sk

AETHER_DATABASE_DRIVER=sqlite
AETHER_DATABASE_URL=sqlite://${INSTALL_ROOT}/data/aether.db
DATABASE_URL=sqlite://${INSTALL_ROOT}/data/aether.db

JWT_SECRET_KEY=${jwt_key}
ENCRYPTION_KEY=${encryption_key}

ADMIN_EMAIL=admin@example.local
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASSWORD}
EOF
}

generate_cluster_env() {
    local output="$1"
    local jwt_key encryption_key role
    prompt_admin_password
    jwt_key="$(urlsafe_rand 32)"
    encryption_key="$(urlsafe_rand 32)"
    role="${AETHER_GATEWAY_NODE_ROLE:-frontdoor}"

    cat > "${output}" <<EOF
ENVIRONMENT=production
TZ=Asia/Shanghai
RUST_LOG=aether_gateway=info
AETHER_LOG_DESTINATION=both
AETHER_LOG_FORMAT=pretty
AETHER_LOG_DIR=${INSTALL_ROOT}/logs
AETHER_LOG_ROTATION=daily
AETHER_LOG_RETENTION_DAYS=7
AETHER_LOG_MAX_FILES=30

APP_PORT=${APP_PORT:-8084}
AETHER_GATEWAY_DEPLOYMENT_TOPOLOGY=multi-node
AETHER_GATEWAY_NODE_ROLE=${role}
AETHER_GATEWAY_STATIC_DIR=${INSTALL_ROOT}/current/frontend
AETHER_GATEWAY_VIDEO_TASK_TRUTH_SOURCE_MODE=rust-authoritative
AETHER_GATEWAY_AUTO_PREPARE_DATABASE=true
AETHER_RUNTIME_BACKEND=redis
API_KEY_PREFIX=sk

DATABASE_URL=${DATABASE_URL:-}
REDIS_URL=${REDIS_URL:-}

JWT_SECRET_KEY=${jwt_key}
ENCRYPTION_KEY=${encryption_key}

ADMIN_EMAIL=${ADMIN_EMAIL:-admin@example.local}
ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
EOF
}

compose_image() {
    if [[ -n "${APP_IMAGE}" ]]; then
        echo "${APP_IMAGE}"
        return
    fi

    local tag=""
    if [[ -n "${VERSION}" ]]; then
        tag="${VERSION#v}"
    else
        case "${CHANNEL}" in
            stable|latest)
                tag="latest"
                ;;
            rc|beta)
                tag="${CHANNEL}"
                ;;
            *)
                die "unsupported release channel: ${CHANNEL}; expected stable, latest, rc, or beta"
                ;;
        esac
    fi

    printf '%s:%s\n' "${IMAGE_REPO}" "${tag}"
}

generate_compose_env() {
    local output="$1"
    local jwt_key encryption_key
    prompt_admin_password
    jwt_key="$(urlsafe_rand 32)"
    encryption_key="$(urlsafe_rand 32)"

    cp "${COMPOSE_DIR}/.env.example" "${output}"
    replace_or_append_env "${output}" "APP_IMAGE" "$(compose_image)"
    replace_or_append_env "${output}" "APP_PORT" "${APP_PORT:-8084}"
    replace_or_append_env "${output}" "DB_PASSWORD" "aether"
    replace_or_append_env "${output}" "REDIS_PASSWORD" "aether"
    replace_or_append_env "${output}" "JWT_SECRET_KEY" "${JWT_SECRET_KEY:-${jwt_key}}"
    replace_or_append_env "${output}" "ENCRYPTION_KEY" "${ENCRYPTION_KEY:-${encryption_key}}"
    replace_or_append_env "${output}" "ADMIN_EMAIL" "${ADMIN_EMAIL:-admin@example.local}"
    replace_or_append_env "${output}" "ADMIN_USERNAME" "${ADMIN_USERNAME:-admin}"
    replace_or_append_env "${output}" "ADMIN_PASSWORD" "${ADMIN_PASSWORD}"
    replace_or_append_env "${output}" "AETHER_LOG_DESTINATION" "both"
    replace_or_append_env "${output}" "AETHER_LOG_FORMAT" "pretty"
    replace_or_append_env "${output}" "AETHER_LOG_DIR" "/app/logs"
    replace_or_append_env "${output}" "AETHER_GATEWAY_AUTO_PREPARE_DATABASE" "true"
}

generate_compose_single_node_env() {
    local output="$1"
    local jwt_key encryption_key
    prompt_admin_password
    jwt_key="$(urlsafe_rand 32)"
    encryption_key="$(urlsafe_rand 32)"

    cat > "${output}" <<EOF
ENVIRONMENT=production
TZ=Asia/Shanghai
RUST_LOG=aether_gateway=info
AETHER_LOG_DESTINATION=both
AETHER_LOG_FORMAT=pretty
AETHER_LOG_DIR=/app/logs
AETHER_LOG_ROTATION=daily
AETHER_LOG_RETENTION_DAYS=7
AETHER_LOG_MAX_FILES=30

APP_IMAGE=$(compose_image)
APP_PORT=${APP_PORT:-8084}
AETHER_GATEWAY_STATIC_DIR=/srv/frontend
AETHER_GATEWAY_VIDEO_TASK_TRUTH_SOURCE_MODE=rust-authoritative
AETHER_GATEWAY_AUTO_PREPARE_DATABASE=true
AETHER_RUNTIME_BACKEND=memory
API_KEY_PREFIX=sk

AETHER_DATABASE_DRIVER=sqlite
AETHER_DATABASE_URL=sqlite:///app/data/aether.db
DATABASE_URL=sqlite:///app/data/aether.db

JWT_SECRET_KEY=${JWT_SECRET_KEY:-${jwt_key}}
ENCRYPTION_KEY=${ENCRYPTION_KEY:-${encryption_key}}

ADMIN_EMAIL=${ADMIN_EMAIL:-admin@example.local}
ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
EOF
}

install_config_dir() {
    if is_darwin; then
        install -d -o root -g "${SERVICE_GROUP}" -m 0750 "${CONFIG_DIR}"
    else
        install -d -m 0750 "${CONFIG_DIR}"
    fi
}

install_env_target_from() {
    local source="$1"
    if is_darwin; then
        install -o root -g "${SERVICE_GROUP}" -m 0640 "${source}" "${ENV_TARGET}"
    else
        install -m 0600 "${source}" "${ENV_TARGET}"
    fi
}

ensure_env_target_permissions() {
    if is_darwin && [[ -f "${ENV_TARGET}" ]]; then
        chown root:"${SERVICE_GROUP}" "${ENV_TARGET}"
        chmod 0640 "${ENV_TARGET}"
    fi
}

install_systemd_support_files() {
    install_config_dir
    write_generate_keys_script "${CONFIG_DIR}/generate_keys.sh"
}

find_nologin_shell() {
    if [[ -x /usr/sbin/nologin ]]; then
        echo "/usr/sbin/nologin"
    elif [[ -x /sbin/nologin ]]; then
        echo "/sbin/nologin"
    else
        echo "/bin/false"
    fi
}

ensure_service_account() {
    if ! getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
        info "creating group ${SERVICE_GROUP}"
        groupadd --system "${SERVICE_GROUP}"
    fi

    if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
        info "creating user ${SERVICE_USER}"
        useradd \
            --system \
            --gid "${SERVICE_GROUP}" \
            --home-dir "${INSTALL_ROOT}" \
            --shell "$(find_nologin_shell)" \
            "${SERVICE_USER}"
    fi
}

macos_next_system_id() {
    local record_type="$1"
    local id_attr="$2"
    dscl . -list "/${record_type}" "${id_attr}" 2>/dev/null |
        awk '
            $NF ~ /^[0-9]+$/ && $NF >= 350 && $NF < 500 { used[$NF] = 1 }
            END {
                for (i = 350; i < 500; i++) {
                    if (!(i in used)) {
                        print i
                        exit
                    }
                }
            }
        '
}

macos_group_id() {
    dscl . -read "/Groups/${SERVICE_GROUP}" PrimaryGroupID 2>/dev/null |
        awk '/PrimaryGroupID:/ { print $2 }'
}

ensure_macos_service_account() {
    local gid uid

    if ! command -v dscl >/dev/null 2>&1; then
        if ui_is_zh; then
            die "未找到 dscl，无法创建 macOS 服务账号"
        else
            die "dscl not found; cannot create macOS service account"
        fi
    fi

    if ! dscl . -read "/Groups/${SERVICE_GROUP}" >/dev/null 2>&1; then
        gid="$(macos_next_system_id Groups PrimaryGroupID)"
        [[ -n "${gid}" ]] || die "could not allocate a macOS service group id"
        info "creating macOS group ${SERVICE_GROUP}"
        dscl . -create "/Groups/${SERVICE_GROUP}"
        dscl . -create "/Groups/${SERVICE_GROUP}" PrimaryGroupID "${gid}"
        dscl . -create "/Groups/${SERVICE_GROUP}" Password "*"
    fi

    gid="$(macos_group_id)"
    [[ -n "${gid}" ]] || die "could not resolve macOS group id for ${SERVICE_GROUP}"

    if ! dscl . -read "/Users/${SERVICE_USER}" >/dev/null 2>&1; then
        uid="$(macos_next_system_id Users UniqueID)"
        [[ -n "${uid}" ]] || die "could not allocate a macOS service user id"
        info "creating macOS user ${SERVICE_USER}"
        dscl . -create "/Users/${SERVICE_USER}"
        dscl . -create "/Users/${SERVICE_USER}" UserShell /usr/bin/false
        dscl . -create "/Users/${SERVICE_USER}" RealName "Aether Gateway"
        dscl . -create "/Users/${SERVICE_USER}" UniqueID "${uid}"
        dscl . -create "/Users/${SERVICE_USER}" PrimaryGroupID "${gid}"
        dscl . -create "/Users/${SERVICE_USER}" NFSHomeDirectory "${INSTALL_ROOT}"
        dscl . -create "/Users/${SERVICE_USER}" IsHidden 1
        dscl . -create "/Users/${SERVICE_USER}" Password "*"
    fi
}

env_file_value() {
    local file="$1"
    local key="$2"
    awk -v key="${key}" '
        {
            line = $0
            sub(/^[[:space:]]*/, "", line)
            if (line ~ /^#/ || line !~ /^[A-Za-z_][A-Za-z0-9_]*=/) {
                next
            }
            name = line
            sub(/=.*/, "", name)
            if (name == key) {
                value = line
                sub(/^[^=]*=/, "", value)
                print value
            }
        }
    ' "${file}" | tail -n1 | tr -d '[:space:]'
}

ensure_env_matches_requested_mode() {
    local file="$1"
    local mode="$2"
    local topology
    topology="$(env_file_value "${file}" "AETHER_GATEWAY_DEPLOYMENT_TOPOLOGY")"
    topology="${topology:-single-node}"

    if [[ "${mode}" == "cluster" ]]; then
        [[ "${topology}" == "multi-node" ]] || die "existing env ${file} is ${topology}; set AETHER_GATEWAY_DEPLOYMENT_TOPOLOGY=multi-node or use --mode single-node"
        cluster_env_has_required_backends "${file}" || die "existing multi-node env ${file} must define DATABASE_URL and REDIS_URL"
    elif [[ "${mode}" == "single-node" && "${topology}" == "multi-node" ]]; then
        die "existing env ${file} is multi-node; cluster mode is temporarily disabled, edit the env file"
    fi
}

cluster_env_has_required_backends() {
    local file="$1"
    local database_url redis_url
    database_url="$(env_file_value "${file}" "AETHER_DATABASE_URL")"
    [[ -n "${database_url}" ]] || database_url="$(env_file_value "${file}" "DATABASE_URL")"
    [[ -n "${database_url}" ]] || database_url="$(env_file_value "${file}" "AETHER_GATEWAY_DATA_POSTGRES_URL")"
    redis_url="$(env_file_value "${file}" "REDIS_URL")"
    [[ -n "${redis_url}" ]] || redis_url="$(env_file_value "${file}" "AETHER_GATEWAY_DATA_REDIS_URL")"

    [[ -n "${database_url}" && -n "${redis_url}" ]]
}

validate_env_file() {
    local env_file="$1"
    local raw_line=""
    local line=""
    local key=""
    local value=""
    local line_no=0
    local topology="single-node"
    local node_role="all"
    local database_driver=""
    local runtime_backend=""
    local db_password=""
    local redis_password=""
    local database_url=""
    local redis_url=""
    local jwt_secret_key=""
    local encryption_key=""
    local video_task_store_path=""
    local static_dir=""

    [[ -f "${env_file}" ]] || die "env file not found: ${env_file}"

    info "validating env file ${env_file}"
    while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
        line_no=$((line_no + 1))
        line="${raw_line%$'\r'}"
        line="$(trim_whitespace "${line}")"

        [[ -z "${line}" ]] && continue
        [[ "${line:0:1}" == "#" ]] && continue

        [[ "${line}" == export\ * ]] && die "env file ${env_file}:${line_no} must not use 'export'"
        [[ "${line}" == *'${'* ]] && die "env file ${env_file}:${line_no} must not use variable expansion"
        [[ "${line}" == *'$('* ]] && die "env file ${env_file}:${line_no} must not use command substitution"
        [[ "${line}" == *'`'* ]] && die "env file ${env_file}:${line_no} must not use command substitution"
        [[ "${line}" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || die "env file ${env_file}:${line_no} must be KEY=VALUE"

        key="${line%%=*}"
        value="${line#*=}"
        value="$(strip_optional_quotes "${value}")"

        case "${key}" in
            AETHER_GATEWAY_DEPLOYMENT_TOPOLOGY)
                topology="${value}"
                ;;
            AETHER_GATEWAY_NODE_ROLE)
                node_role="${value}"
                ;;
            AETHER_DATABASE_DRIVER)
                database_driver="$(printf '%s' "${value}" | tr '[:upper:]' '[:lower:]')"
                ;;
            AETHER_RUNTIME_BACKEND)
                runtime_backend="$(printf '%s' "${value}" | tr '[:upper:]' '[:lower:]')"
                ;;
            AETHER_DATABASE_URL|DATABASE_URL|AETHER_GATEWAY_DATA_POSTGRES_URL)
                [[ -n "${value}" ]] && database_url="${value}"
                ;;
            REDIS_URL|AETHER_GATEWAY_DATA_REDIS_URL)
                [[ -n "${value}" ]] && redis_url="${value}"
                ;;
            DB_PASSWORD)
                db_password="${value}"
                ;;
            REDIS_PASSWORD)
                redis_password="${value}"
                ;;
            JWT_SECRET_KEY)
                jwt_secret_key="${value}"
                ;;
            ENCRYPTION_KEY|AETHER_GATEWAY_DATA_ENCRYPTION_KEY)
                [[ -n "${value}" ]] && encryption_key="${value}"
                ;;
            AETHER_GATEWAY_VIDEO_TASK_STORE_PATH)
                video_task_store_path="${value}"
                ;;
            AETHER_GATEWAY_STATIC_DIR)
                static_dir="${value}"
                ;;
        esac
    done < "${env_file}"

    case "${topology}" in
        single-node|multi-node)
            ;;
        *)
            die "AETHER_GATEWAY_DEPLOYMENT_TOPOLOGY must be single-node or multi-node"
            ;;
    esac

    case "${node_role}" in
        all|frontdoor|background)
            ;;
        *)
            die "AETHER_GATEWAY_NODE_ROLE must be all, frontdoor, or background"
            ;;
    esac

    [[ -n "${jwt_secret_key}" ]] || die "JWT_SECRET_KEY is required"
    [[ -n "${encryption_key}" ]] || die "ENCRYPTION_KEY or AETHER_GATEWAY_DATA_ENCRYPTION_KEY is required"

    is_placeholder_value "${jwt_secret_key}" && die "JWT_SECRET_KEY still uses the example placeholder"
    is_placeholder_value "${encryption_key}" && die "ENCRYPTION_KEY still uses the example placeholder"
    if [[ -n "${database_url}" ]] && is_placeholder_value "${database_url}"; then
        die "DATABASE_URL still uses the example placeholder"
    fi
    if [[ -n "${redis_url}" ]] && is_placeholder_value "${redis_url}"; then
        die "REDIS_URL still uses the example placeholder"
    fi

    local database_is_sqlite="false"
    if [[ "${database_driver}" == "sqlite" || "${database_url}" == sqlite:* ]]; then
        database_is_sqlite="true"
    fi

    if [[ "${topology}" == "multi-node" ]]; then
        [[ "${node_role}" != "all" ]] || die "multi-node deployment requires AETHER_GATEWAY_NODE_ROLE=frontdoor or background"
        [[ -n "${database_url}" ]] || die "multi-node deployment requires AETHER_DATABASE_URL, DATABASE_URL, or AETHER_GATEWAY_DATA_POSTGRES_URL"
        [[ "${database_is_sqlite}" != "true" ]] || die "multi-node deployment must use shared Postgres/MySQL, not SQLite"
        [[ -n "${redis_url}" ]] || die "multi-node deployment requires REDIS_URL or AETHER_GATEWAY_DATA_REDIS_URL"
        [[ "${runtime_backend}" != "memory" ]] || die "multi-node deployment must not use AETHER_RUNTIME_BACKEND=memory"
        [[ -z "${video_task_store_path}" ]] || die "multi-node deployment must not set AETHER_GATEWAY_VIDEO_TASK_STORE_PATH"
    else
        if [[ "${node_role}" != "all" ]]; then
            warn "single-node deployment usually uses AETHER_GATEWAY_NODE_ROLE=all; split roles are not enabled by this installer"
        fi
        if [[ "${runtime_backend}" == "redis" && -z "${redis_url}" ]]; then
            die "AETHER_RUNTIME_BACKEND=redis requires REDIS_URL or AETHER_GATEWAY_DATA_REDIS_URL"
        fi
        if [[ -z "${database_url}" && -z "${redis_url}" ]]; then
            warn "single-node env is running in minimal mode without full Postgres/Redis persistence"
        elif [[ "${database_is_sqlite}" == "true" && -z "${redis_url}" ]]; then
            info "single-node env is using SQLite with in-process runtime coordination"
        fi
    fi

    if is_placeholder_value "${db_password}"; then
        warn "DB_PASSWORD still uses the example placeholder"
    fi
    if is_placeholder_value "${redis_password}"; then
        warn "REDIS_PASSWORD still uses the example placeholder"
    fi

    if [[ -n "${static_dir}" && "${static_dir}" != "${INSTALL_ROOT}/current/frontend" ]]; then
        warn "AETHER_GATEWAY_STATIC_DIR points to ${static_dir}; install script still publishes frontend to ${INSTALL_ROOT}/current/frontend"
    fi
}

resolve_service_env_source() {
    local mode="$1"
    if [[ -n "${ENV_SOURCE}" ]]; then
        [[ -f "${ENV_SOURCE}" ]] || die "env file not found: ${ENV_SOURCE}"
        ensure_env_matches_requested_mode "${ENV_SOURCE}" "${mode}"
        echo "${ENV_SOURCE}"
        return
    fi

    if [[ -f "${ENV_TARGET}" ]]; then
        ensure_env_matches_requested_mode "${ENV_TARGET}" "${mode}"
        echo ""
        return
    fi

    GENERATED_ENV="${TMP_ROOT:-$(mktemp -d)}/aether-gateway.env"
    if [[ -z "${TMP_ROOT}" ]]; then
        TMP_ROOT="$(dirname "${GENERATED_ENV}")"
    fi

    if [[ "${mode}" == "cluster" ]]; then
        info "generating multi-node env file"
        generate_cluster_env "${GENERATED_ENV}"
        if ! cluster_env_has_required_backends "${GENERATED_ENV}"; then
            install_config_dir
            install_env_target_from "${GENERATED_ENV}"
            cat <<EOF

Multi-node env scaffolded:
  ${ENV_TARGET}

Fill DATABASE_URL and REDIS_URL, then rerun:
  sudo AETHER_INSTALL_MODE=cluster bash install.sh

Or provide them non-interactively:
  curl -fsSL https://raw.githubusercontent.com/${REPO}/${SOURCE_REF}/install.sh | sudo DATABASE_URL=postgresql://... REDIS_URL=redis://... bash -s -- --mode cluster
EOF
            exit 1
        fi
    else
        info "generating first-install single-node env file"
        generate_first_install_env "${GENERATED_ENV}"
    fi
    echo "${GENERATED_ENV}"
}

install_compose_mode() {
    resolve_compose_dir
    info "preparing Docker Compose deployment in ${COMPOSE_DIR}"
    ensure_directory "${COMPOSE_DIR}"
    ensure_directory "${COMPOSE_DIR}/logs"

    install_project_file "docker-compose.yml" "${COMPOSE_DIR}/docker-compose.yml" "0644"
    install_project_file ".env.example" "${COMPOSE_DIR}/.env.example" "0644"
    install_generate_keys_script "${COMPOSE_DIR}/generate_keys.sh"

    if [[ -f "${COMPOSE_DIR}/.env" ]]; then
        warn "keeping existing ${COMPOSE_DIR}/.env"
    else
        info "generating ${COMPOSE_DIR}/.env"
        generate_compose_env "${COMPOSE_DIR}/.env"
        chmod 0600 "${COMPOSE_DIR}/.env"
    fi

    cat <<EOF

Docker Compose files are ready:
  ${COMPOSE_DIR}/docker-compose.yml
  ${COMPOSE_DIR}/.env
  ${COMPOSE_DIR}/.env.example
  ${COMPOSE_DIR}/generate_keys.sh
  ${COMPOSE_DIR}/logs
EOF

    if [[ "${SKIP_START}" == "true" ]]; then
        compose_manual_start_steps
        return
    fi

    require_compose_runtime
    start_compose_deployment
    compose_next_steps
}

install_compose_single_node_mode() {
    resolve_compose_dir
    info "preparing Docker Compose single-node deployment in ${COMPOSE_DIR}"
    ensure_directory "${COMPOSE_DIR}"
    ensure_directory "${COMPOSE_DIR}/logs"
    ensure_directory "${COMPOSE_DIR}/data"

    install_project_file "docker-compose.single-node.yml" "${COMPOSE_DIR}/docker-compose.yml" "0644"
    install_project_file ".env.example" "${COMPOSE_DIR}/.env.example" "0644"
    install_generate_keys_script "${COMPOSE_DIR}/generate_keys.sh"

    if [[ -f "${COMPOSE_DIR}/.env" ]]; then
        warn "keeping existing ${COMPOSE_DIR}/.env"
    else
        info "generating ${COMPOSE_DIR}/.env"
        generate_compose_single_node_env "${COMPOSE_DIR}/.env"
        chmod 0600 "${COMPOSE_DIR}/.env"
    fi

    cat <<EOF

Docker Compose single-node files are ready:
  ${COMPOSE_DIR}/docker-compose.yml
  ${COMPOSE_DIR}/.env
  ${COMPOSE_DIR}/.env.example
  ${COMPOSE_DIR}/generate_keys.sh
  ${COMPOSE_DIR}/data
  ${COMPOSE_DIR}/logs
EOF

    if [[ "${SKIP_START}" == "true" ]]; then
        compose_manual_start_steps
        return
    fi

    require_compose_runtime
    start_compose_deployment
    compose_next_steps
}

install_env_file() {
    local env_file="$1"
    install_config_dir

    if [[ -n "${env_file}" ]]; then
        info "installing env file to ${ENV_TARGET}"
        install_env_target_from "${env_file}"
    else
        ensure_env_target_permissions
    fi
}

install_release() {
    local bundle="$1"
    local release_dir="${INSTALL_ROOT}/releases/${VERSION}"
    local current_link="${INSTALL_ROOT}/current"

    [[ -x "${bundle}/bin/aether-gateway" ]] || die "binary not found or not executable: ${bundle}/bin/aether-gateway"
    [[ -d "${bundle}/frontend" ]] || die "frontend directory not found: ${bundle}/frontend"

    info "installing release ${VERSION} into ${release_dir}"
    install -d -m 0755 "${INSTALL_ROOT}" "${INSTALL_ROOT}/releases" "${INSTALL_ROOT}/data" "${INSTALL_ROOT}/logs"
    if is_darwin; then
        install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0750 \
            "${INSTALL_ROOT}/data" \
            "${INSTALL_ROOT}/logs"
    else
        install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0750 \
            "${INSTALL_ROOT}/data" \
            "${INSTALL_ROOT}/logs"
    fi
    rm -rf "${release_dir}"
    install -d -m 0755 "${release_dir}/bin" "${release_dir}/frontend"
    install -m 0755 "${bundle}/bin/aether-gateway" "${release_dir}/bin/aether-gateway"
    cp -R "${bundle}/frontend/." "${release_dir}/frontend/"
    chmod -R u=rwX,go=rX "${release_dir}"
    if is_darwin; then
        chown -R root:wheel "${release_dir}"
    else
        chown -R root:root "${release_dir}"
    fi
    ln -sfn "${release_dir}" "${current_link}"
}

prune_old_releases() {
    local keep="${RELEASE_KEEP}"
    [[ "${keep}" =~ ^[0-9]+$ ]] || return 0
    [[ "${keep}" -gt 0 ]] || return 0

    local releases_dir="${INSTALL_ROOT}/releases"
    [[ -d "${releases_dir}" ]] || return 0

    local current_target
    current_target="$(readlink "${INSTALL_ROOT}/current" 2>/dev/null || true)"
    current_target="$(basename "${current_target}" 2>/dev/null || true)"

    local count=0
    local dir
    while IFS= read -r dir; do
        [[ -n "${dir}" ]] || continue
        local name
        name="$(basename "${dir}")"
        [[ "${name}" != "${current_target}" ]] || continue
        count=$((count + 1))
    done < <(ls -1dt "${releases_dir}"/*/ 2>/dev/null)

    if [[ "${count}" -ge "${keep}" ]]; then
        local to_remove
        to_remove="$(ls -1dt "${releases_dir}"/*/ 2>/dev/null | while IFS= read -r d; do
            local n
            n="$(basename "${d}")"
            [[ "${n}" != "${current_target}" ]] || continue
            printf '%s\n' "${d}"
        done | tail -n +$((keep)))"

        local removed=0
        while IFS= read -r dir; do
            [[ -n "${dir}" ]] || continue
            info "pruning old release: $(basename "${dir}")"
            rm -rf "${dir}"
            removed=$((removed + 1))
        done <<< "${to_remove}"

        if [[ "${removed}" -gt 0 ]]; then
            if ui_is_zh; then
                info "已清理 ${removed} 个旧版本（保留最新 ${keep} 个）"
            else
                info "pruned ${removed} old release(s), keeping latest ${keep}"
            fi
        fi
    fi
}

render_systemd_unit() {
    cat <<EOF
[Unit]
Description=Aether Gateway
Documentation=https://github.com/${REPO}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${INSTALL_ROOT}/current
EnvironmentFile=${ENV_TARGET}
ExecStart=${INSTALL_ROOT}/current/bin/aether-gateway
Restart=on-failure
RestartSec=3
TimeoutStopSec=20
UMask=0027
LimitNOFILE=65535
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
}

install_systemd_unit() {
    local rendered_unit
    rendered_unit="$(mktemp)"
    render_systemd_unit > "${rendered_unit}"
    info "installing systemd unit to ${SYSTEMD_UNIT_PATH}"
    install -m 0644 "${rendered_unit}" "${SYSTEMD_UNIT_PATH}"
    rm -f "${rendered_unit}"
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}" >/dev/null
}

restart_service_if_requested() {
    if [[ "${SKIP_START}" == "true" ]]; then
        info "skipping service restart"
        return
    fi

    info "restarting ${SERVICE_NAME}"
    systemctl restart "${SERVICE_NAME}"
}

print_systemd_next_steps() {
    local gateway_port
    local database_driver
    local database_url
    gateway_port="$(awk -F= '/^[[:space:]]*APP_PORT=/{print $2}' "${ENV_TARGET}" | tail -n1 | tr -d '[:space:]')"
    gateway_port="${gateway_port:-8084}"
    database_driver="$(awk -F= '/^[[:space:]]*AETHER_DATABASE_DRIVER=/{print tolower($2)}' "${ENV_TARGET}" | tail -n1 | tr -d '[:space:]')"
    database_url="$(awk -F= '/^[[:space:]]*(AETHER_DATABASE_URL|DATABASE_URL|AETHER_GATEWAY_DATA_POSTGRES_URL)=/{print $2}' "${ENV_TARGET}" | tail -n1 | tr -d '[:space:]')"

    cat <<EOF

Install complete.

Gateway service:
  sudo systemctl status ${SERVICE_NAME} --no-pager
  sudo journalctl -u ${SERVICE_NAME} -n 100 --no-pager
  sudo journalctl -u ${SERVICE_NAME} -f

Health checks:
  curl -fsS http://127.0.0.1:${gateway_port}/_gateway/health
  curl -fsS http://127.0.0.1:${gateway_port}/readyz

Install directory:
  ${INSTALL_ROOT}
  data: ${INSTALL_ROOT}/data
  logs: ${INSTALL_ROOT}/logs

EOF

    if [[ "${database_driver}" == "sqlite" || "${database_url}" == sqlite:* ]]; then
        cat <<EOF
SQLite data:
  ${database_url#sqlite://}

EOF
    fi

    cat <<EOF
Database:
  empty database: first service start auto-bootstraps to the current baseline
  later schema upgrades: ${INSTALL_ROOT}/current/bin/aether-gateway --migrate

Current release:
  ${INSTALL_ROOT}/current
EOF
}

launchd_wrapper_path() {
    printf '%s/bin/%s-launchd\n' "${INSTALL_ROOT}" "${SERVICE_NAME}"
}

install_launchd_support_files() {
    install_config_dir
    write_generate_keys_script "${CONFIG_DIR}/generate_keys.sh"
}

write_launchd_wrapper() {
    local wrapper
    wrapper="$(launchd_wrapper_path)"
    install -d -o root -g wheel -m 0755 "$(dirname "${wrapper}")"
    cat > "${wrapper}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

ENV_TARGET="${ENV_TARGET}"
AETHER_BIN="${INSTALL_ROOT}/current/bin/aether-gateway"
EOF
    cat >> "${wrapper}" <<'EOF'

trim_whitespace() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "${value}"
}

strip_optional_quotes() {
    local value="$1"
    if [[ ${#value} -ge 2 ]]; then
        if [[ "${value:0:1}" == "\"" && "${value: -1}" == "\"" ]]; then
            value="${value:1:${#value}-2}"
        elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
            value="${value:1:${#value}-2}"
        fi
    fi
    printf '%s' "${value}"
}

if [[ ! -r "${ENV_TARGET}" ]]; then
    echo "Aether env file not found or not readable: ${ENV_TARGET}" >&2
    exit 1
fi

while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    line="${raw_line%$'\r'}"
    line="$(trim_whitespace "${line}")"
    [[ -z "${line}" ]] && continue
    [[ "${line:0:1}" == "#" ]] && continue

    if [[ "${line}" == export\ * || ! "${line}" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
        echo "Invalid Aether env line: ${line}" >&2
        exit 1
    fi

    key="${line%%=*}"
    value="${line#*=}"
    value="$(strip_optional_quotes "${value}")"
    export "${key}=${value}"
done < "${ENV_TARGET}"

exec "${AETHER_BIN}"
EOF
    chmod 0755 "${wrapper}"
    chown root:wheel "${wrapper}"
}

render_launchd_plist() {
    local wrapper
    wrapper="$(launchd_wrapper_path)"
    cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LAUNCHD_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${wrapper}</string>
    </array>
    <key>UserName</key>
    <string>${SERVICE_USER}</string>
    <key>GroupName</key>
    <string>${SERVICE_GROUP}</string>
    <key>WorkingDirectory</key>
    <string>${INSTALL_ROOT}/current</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LAUNCHD_LOG_DIR}/${SERVICE_NAME}.out.log</string>
    <key>StandardErrorPath</key>
    <string>${LAUNCHD_LOG_DIR}/${SERVICE_NAME}.err.log</string>
    <key>Umask</key>
    <integer>23</integer>
</dict>
</plist>
EOF
}

install_launchd_log_files() {
    install -d -o root -g wheel -m 0755 "${LAUNCHD_LOG_DIR}"
    touch "${LAUNCHD_LOG_DIR}/${SERVICE_NAME}.out.log" "${LAUNCHD_LOG_DIR}/${SERVICE_NAME}.err.log"
    chown "${SERVICE_USER}:${SERVICE_GROUP}" "${LAUNCHD_LOG_DIR}/${SERVICE_NAME}.out.log" "${LAUNCHD_LOG_DIR}/${SERVICE_NAME}.err.log"
    chmod 0640 "${LAUNCHD_LOG_DIR}/${SERVICE_NAME}.out.log" "${LAUNCHD_LOG_DIR}/${SERVICE_NAME}.err.log"
}

install_launchd_unit() {
    local rendered_plist
    rendered_plist="$(mktemp)"
    render_launchd_plist > "${rendered_plist}"
    info "installing launchd plist to ${LAUNCHD_PLIST_PATH}"
    install_launchd_log_files
    install -d -o root -g wheel -m 0755 "$(dirname "${LAUNCHD_PLIST_PATH}")"
    install -o root -g wheel -m 0644 "${rendered_plist}" "${LAUNCHD_PLIST_PATH}"
    rm -f "${rendered_plist}"
}

restart_launchd_if_requested() {
    if [[ "${SKIP_START}" == "true" ]]; then
        info "skipping launchd service restart"
        return
    fi

    info "restarting ${LAUNCHD_LABEL} with launchd"
    launchctl bootout system "${LAUNCHD_PLIST_PATH}" >/dev/null 2>&1 || true
    launchctl bootstrap system "${LAUNCHD_PLIST_PATH}"
    launchctl kickstart -k "system/${LAUNCHD_LABEL}"
}

print_launchd_next_steps() {
    local gateway_port
    local database_driver
    local database_url
    gateway_port="$(awk -F= '/^[[:space:]]*APP_PORT=/{print $2}' "${ENV_TARGET}" | tail -n1 | tr -d '[:space:]')"
    gateway_port="${gateway_port:-8084}"
    database_driver="$(awk -F= '/^[[:space:]]*AETHER_DATABASE_DRIVER=/{print tolower($2)}' "${ENV_TARGET}" | tail -n1 | tr -d '[:space:]')"
    database_url="$(awk -F= '/^[[:space:]]*(AETHER_DATABASE_URL|DATABASE_URL|AETHER_GATEWAY_DATA_POSTGRES_URL)=/{print $2}' "${ENV_TARGET}" | tail -n1 | tr -d '[:space:]')"

    cat <<EOF

Install complete.

Gateway service:
  sudo launchctl print system/${LAUNCHD_LABEL}
  sudo launchctl kickstart -k system/${LAUNCHD_LABEL}
  sudo launchctl bootout system ${LAUNCHD_PLIST_PATH}

Logs:
  tail -f ${LAUNCHD_LOG_DIR}/${SERVICE_NAME}.out.log ${LAUNCHD_LOG_DIR}/${SERVICE_NAME}.err.log

Health checks:
  curl -fsS http://127.0.0.1:${gateway_port}/_gateway/health
  curl -fsS http://127.0.0.1:${gateway_port}/readyz

Install directory:
  ${INSTALL_ROOT}
  data: ${INSTALL_ROOT}/data
  logs: ${INSTALL_ROOT}/logs

EOF

    if [[ "${database_driver}" == "sqlite" || "${database_url}" == sqlite:* ]]; then
        cat <<EOF
SQLite data:
  ${database_url#sqlite://}

EOF
    fi

    cat <<EOF
Database:
  empty database: first service start auto-bootstraps to the current baseline
  later schema upgrades: ${INSTALL_ROOT}/current/bin/aether-gateway --migrate

Current release:
  ${INSTALL_ROOT}/current
EOF
}

install_systemd_mode() {
    local bundle="$1"
    local env_file="$2"

    ensure_service_account
    install_systemd_support_files
    install_env_file "${env_file}"
    validate_env_file "${ENV_TARGET}"
    install_release "${bundle}"
    prune_old_releases
    install_systemd_unit
    restart_service_if_requested
    print_systemd_next_steps
}

install_launchd_mode() {
    local bundle="$1"
    local env_file="$2"

    ensure_macos_service_account
    install_launchd_support_files
    install_env_file "${env_file}"
    validate_env_file "${ENV_TARGET}"
    install_release "${bundle}"
    prune_old_releases
    write_launchd_wrapper
    install_launchd_unit
    restart_launchd_if_requested
    print_launchd_next_steps
}

main() {
    local bundle env_file

    parse_args "$@"
    select_language
    require_supported_os
    apply_platform_defaults
    select_version
    select_mode
    collect_interactive_migration_options

    if [[ -n "${MIGRATE_FROM_COMPOSE}" ]]; then
        run_migration_from_compose
        return
    fi
    if migration_options_requested; then
        die "migration options require --migrate-from-compose"
    fi

    if [[ "${MODE}" == "compose" ]]; then
        install_compose_mode
    elif [[ "${MODE}" == "compose-single-node" ]]; then
        install_compose_single_node_mode
    else
        require_root
        require_service_manager
        bundle="$(local_bundle_dir || true)"
        if [[ -z "${bundle}" ]]; then
            download_or_unpack_bundle
            bundle="${BUNDLE_DIR}"
        else
            if [[ -z "${VERSION}" ]]; then
                VERSION="$(derive_local_bundle_version "${bundle}")"
            fi
            info "installing from local extracted bundle ${bundle}"
        fi

        if is_darwin; then
            ensure_macos_service_account
        fi
        env_file="$(resolve_service_env_source "${MODE}")"
        case "$(install_os)" in
            linux)
                install_systemd_mode "${bundle}" "${env_file}"
                ;;
            macos)
                install_launchd_mode "${bundle}" "${env_file}"
                ;;
        esac
    fi

    if [[ -n "${ADMIN_PASSWORD_SOURCE}" ]]; then
        local password_note
        if [[ "${ADMIN_PASSWORD_SOURCE}" == "prompt" ]]; then
            password_note="set from prompt"
        else
            password_note="set from ADMIN_PASSWORD"
        fi
        cat <<EOF

Initial admin:
  username: admin
  password: ${password_note}

The password is stored in the generated env file. Change it after first login.
EOF
    fi
}

main "$@"
