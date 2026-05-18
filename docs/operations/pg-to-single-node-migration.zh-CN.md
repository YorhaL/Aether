# Postgres 到 Aether Single Node 迁移

英文版：[pg-to-single-node-migration.md](pg-to-single-node-migration.md)

本文档用于把现有 Docker Compose Postgres 部署迁移到 Aether
single-node。当前版本里，**single-node** 指默认 SQLite 安装模式：
`install.sh --mode single-node`，也就是系统服务加 SQLite。Docker Compose
单机模板是 `docker-compose.single-node.yml`，安装脚本入口是
`--mode compose-single-node`。

迁移脚本：

```bash
scripts/migrate-pg-to-single-node.sh
```

如果目标形态仍然要保持 Docker Compose，而不是系统服务，使用镜像版迁移脚本：

```bash
scripts/migrate-pg-compose-to-single-node.sh
```

两种迁移脚本都会先拉取/安装目标 single-node 版本，再停止源 `app`，把 Postgres
记录直接写入临时 SQLite DB，不落 JSONL 中间文件；复制成功后替换目标
`aether.db`，最后启动 single-node。

也可以直接用安装脚本作为统一入口，由 `--mode` 选择迁移目标：

```bash
# 交互式执行时，先选择目标部署模式：
#   1) Docker Compose 标准部署（Postgres + Redis）
#   2) Docker Compose 单节点部署（SQLite）
#   3) 系统服务单节点部署（SQLite）
# 选择 2 或 3 后，再选择数据初始化方式：
#   1) 全新初始化（不迁移现有数据）
#   2) 从现有 Docker Compose PG 数据库迁移
install.sh

# 迁移到新的 single-node Docker Compose 目录
install.sh \
  --mode compose-single-node \
  --migrate-from-compose /root/Aether/docker-compose.yml \
  --compose-dir /opt/aether-single \
  --replace-existing

# 迁移到系统服务 + SQLite
sudo install.sh \
  --mode single-node \
  --migrate-from-compose /root/Aether/docker-compose.yml \
  --replace-existing
```

交互模式会先选择目标部署形态。如果目标是 `compose-single-node` 或
`single-node`，安装脚本会再询问数据初始化方式：全新初始化，或从现有 Docker
Compose PG 数据库迁移。选择迁移后，脚本会通过 `docker compose ls` 自动探测源
PG Compose 文件，并确认该 Compose 配置里存在默认的 `app` 和 `postgres` 服务；
如果能唯一识别，会作为默认值带入提示。探测不到或存在多个候选时会直接中止；
此时请用 `--migrate-from-compose` 显式指定源 compose 路径。

安装脚本只是统一参数入口：`compose-single-node` 会委托给
`scripts/migrate-pg-compose-to-single-node.sh`，`single-node` 会委托给
`scripts/migrate-pg-to-single-node.sh`。

## 迁移内容

脚本会尽量缩短生产停机窗口：

1. 读取源 Compose 目录下的 `.env`。
2. 生成 single-node 环境文件，保留 `JWT_SECRET_KEY`、`ENCRYPTION_KEY` 或
   `AETHER_GATEWAY_DATA_ENCRYPTION_KEY`、管理员配置、端口和应用配置。
3. 执行 `install.sh --mode single-node --skip-start`，提前安装 single-node
   release，但不启动服务。
4. 使用已安装的 single-node 二进制预检 SQLite schema migration。
5. 拉取目标 single-node 镜像，确认其 `copy` 命令可用，并检查源 `app`
   当前运行镜像 ID 与目标镜像 ID 一致。
6. 以目标 SQLite schema 作为迁移计划：把源 Postgres 中同名表、同名字段
   复制到临时 SQLite DB。
7. 检查请求体明细迁移策略；默认全部迁移，也可以选择只跳过请求体明细。
8. 检查 work-dir 和目标 SQLite 目录是否有足够空间容纳临时库和正式库。
9. 只停止源 Compose 的 `app` 服务，保留 Postgres 和 Redis 运行，方便回滚。
10. 从源 Postgres 直接复制记录到临时 SQLite 数据库，不生成 JSONL 中间文件。
11. 复制完成后替换目标 SQLite DB，包括 SQLite `-wal`、`-shm` 边车文件，
    然后启动 single-node 系统服务。

镜像一致性检查比较的是 Docker 镜像 ID，不只是 tag 字符串。即使源和目标都写着
`latest`，只要实际镜像 ID 不同，迁移也会中止。请先把源 PG Compose 的 `app`
升级到目标 single-node 相同版本，确认运行正常后再迁移。迁移脚本也会检查目标镜像
是否支持直接 copy 和请求体跳过开关；如果只是换了脚本但镜像还是旧版本，脚本会
直接中止，避免漏迁。

## 生产切换

切换前先做一次常规服务器备份或快照。确认后执行：

```bash
sudo scripts/migrate-pg-to-single-node.sh \
  --source-compose /root/Aether/docker-compose.yml \
  --replace-existing
```

如果要迁移到 Docker Compose single-node，而不是系统服务：

```bash
scripts/migrate-pg-compose-to-single-node.sh \
  --source-compose /root/Aether/docker-compose.yml \
  --replace-existing
```

源 Postgres Compose 目录和目标 single-node Compose 目录可以不一样。例如：

```bash
install.sh \
  --mode compose-single-node \
  --migrate-from-compose /root/Aether/docker-compose.yml \
  --compose-dir /opt/aether-single \
  --replace-existing
```

等价地，也可以直接调底层脚本并显式传入每个目标路径：

```bash
scripts/migrate-pg-compose-to-single-node.sh \
  --source-compose /root/Aether/docker-compose.yml \
  --target-compose /opt/aether-single/docker-compose.single-node.yml \
  --target-env /opt/aether-single/.env.single-node \
  --target-db /opt/aether-single/data/aether.db \
  --replace-existing
```

切换时脚本只会停止并移除源 `app` 容器，用来释放固定的 `aether-app`
容器名；Postgres、Redis 和它们的 volume 都会保留，方便回滚。

默认路径和服务名：

| 配置项 | 默认值 |
| --- | --- |
| 源 Compose 文件 | `docker-compose.yml` |
| single-node 安装目录 | `/opt/aether` |
| single-node 配置目录 | `/etc/aether` |
| 目标 SQLite DB | `/opt/aether/data/aether.db` |
| 源 app 服务 | `app` |
| 源 Postgres 服务 | `postgres` |
| single-node 服务 | `aether-gateway` |

除非显式传入 `--work-dir`，脚本会把迁移产物写到源 Compose 文件旁边的
`./data/pg-to-single-node-<timestamp>`。

## 回滚

脚本会保留原 Postgres 和 Redis volume。迁移已经完成但需要回滚时：

```bash
sudo systemctl stop aether-gateway
cd /root/Aether
docker compose -f docker-compose.yml up -d app
```

对于 Compose single-node 脚本，回滚思路相同：重新用原 Postgres compose 文件
拉起 `app`。

如果迁移在切换完成前失败，脚本默认会尝试自动拉起源 `app` 服务。需要失败后
保持源应用停止以便人工排查时，增加：

```bash
--keep-source-stopped-on-error
```

## 数据覆盖保护

迁移不再维护一份额外的业务表清单。目标 single-node 镜像会先用正常
migrations 建出临时 SQLite 数据库，然后 `aether-gateway copy` 读取这个
SQLite schema，把源 Postgres 里同名表、同名字段复制过去。

如果源 Postgres 里存在非空 public 表，但目标 SQLite schema 中没有同名表，
copy 会直接中止，不会静默丢弃。生命周期元数据表 `_sqlx_migrations` 和
`schema_backfills` 会被忽略。源表中存在但目标 SQLite 不存在的额外字段不会复制。

## 请求体明细策略

single-node SQLite 生产迁移默认迁移所有可迁移数据，唯一可选的跳过项是请求体明细。

选择“不迁移请求体”时，不会迁移 `usage_body_blobs`、`usage_http_audits`，也不会迁移 `usage`
表里的 `request_body` / `provider_request_body` / `response_body` /
`client_response_body` / `*_body_compressed` 等请求体大字段。

交互安装时可以选择：

```text
1) 全部迁移：迁移所有可迁移数据，包括请求体明细
2) 不迁移请求体：迁移其他所有数据；仅跳过请求体大字段和 HTTP 请求体明细，源 PG 不清除
```

非交互执行时，全部迁移可以显式指定：

```bash
scripts/migrate-pg-to-single-node.sh \
  --request-body-mode full
```

不迁移请求体可以显式指定：

```bash
scripts/migrate-pg-to-single-node.sh \
  --request-body-mode omit
```

`omit` 只是不把这些大字段和明细表写进目标 SQLite，不会删除或清空源 Postgres。

## 注意事项

- single-node 安装需要 root 或 sudo 权限，因为会写入 `/opt/aether`、
  `/etc/aether` 和系统服务定义。
- 脚本不会解密或重新加密供应商密钥；它会沿用源环境的加密密钥，并原样迁移已加密数据。
- 已存在的目标 SQLite DB，包括 `-wal`、`-shm` 边车文件，只有在传入
  `--replace-existing` 时才会被替换。
- 空间检查会用 `pg_database_size(current_database()) * 2 + 1 GiB` 作为单份
  SQLite 的保守估算。如果 work-dir 和目标 DB 目录在同一个文件系统，会要求同时
  容纳临时 SQLite 和正式 SQLite。选择 `--request-body-mode omit` 时，
  估算会扣除 `usage_body_blobs` 和 `usage_http_audits` 的表空间。
- 非标准 Compose 服务名需要通过 `--app-service` 和 `--postgres-service`
  明确指定。
