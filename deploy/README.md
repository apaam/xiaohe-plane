# Plane deployment (4GB, public via nginx)

- Target: `ts-xiaohe`, Plane CE **v1.5.0**, 4GB container caps, bound to `100.64.0.4:8080` (tailnet).
- Status: **public running (xiaohe accounts SSO)**；公开注册关闭；Plane 准入需有效小荷订阅（管理员豁免）；本地登录 break-glass。

## 当前 staging（2026-11-17）

| 项 | 值 |
|---|---|
| 访问 | `https://plane.xiaohe.team/research`（公网，订阅准入 + workspace invite-only） |
| 实例名 | 中山大学 |
| 管理员 | `lai.zhengshou@outlook.com` |
| 密码 | 本机 `~/.xiaohe/plane/admin-password`（600）；VPS `~/plane-selfhost/admin-password`（600） |
| workspace | 课题组 / `research` |
| project | 工作台 / `WORK`（示例项目已归档） |
| work item | `WORK-1..5`；`WORK-5` 已完成并含 agent 评论 |
| 组件 | Postgres、Redis/Valkey、RabbitMQ、Silo(MinIO)、api、worker、beat、web、space、admin、live、proxy |
| agent 身份 | `agent-bot@xiaohe.local`；token `~/.xiaohe/plane/agent-token`（600） |
| agent MCP | `~/.xiaohe/plane/plane-mcp.sh`；笔记本已注册为 `plane` |
| 公网入口 | `plane.xiaohe.team` 已代理 Plane；SSO 入口 `/auth/xiaohe/start/` |
| api 镜像 | `gitea.xiaohe.team/lzhshou/xiaohe-plane-backend:v1.5.0-xh23`（`auth/plane` + 订阅门槛 + 请求防护） |
| 容器访问 accounts | `extra_hosts: accounts.xiaohe.team:host-gateway`，避免公网 hairpin 超时 |
| 备份 | 每日 03:17 cron，`~/plane-backups`（Postgres dump + uploads tar，保留 14 天） |
| 实际内存 | Plane 容器合计约 1.5GiB；host 可用约 4.6GiB |

## 发布与回滚（2026-11-20 起）

- 构建推送（ts-linux-ws）：`./scripts/build-and-push.sh <tag>`；backend 与 web
  **必须使用同一个 tag**，部署脚本按 tag 拉取并解析 digest。
- 部署（任意机器）：`./deploy/deploy-vps.sh <tag>`。脚本会快照 compose、
  按 digest 固定 api/web、跑一次备份、`compose up -d`、以
  `/version.json` 的 `build_id == tag` 加 12 个常驻服务 running 作为健康门；
  失败自动回上一份快照。
- 人工回滚：`./deploy/rollback-vps.sh [release-id]`，默认回上一个快照。
- 快照位置：`~/plane-selfhost/releases/<ts>/`，`releases/current` 指向活动版；
  保留当前 + 4 个上一版。
- **不做整体蓝绿**：12 个容器再起一份约需 1.2 GiB，超出本机余量；digest
  快照 + 健康门回滚是这里的等价保障。

## 0. 前置条件

- Docker 29+、`docker-compose-v2`。
- Docker registry mirror：`https://mirror.ccs.tencentyun.com`（VPS 直连 Docker Hub 会超时）。
- 目录 `~/plane-selfhost`。

## 0.1 镜像构建（ts-linux-ws 构建，Gitea 仓库分发）

backend 与 web 两个自定义镜像不在 VPS 上构建：VPS 只有 4 核 / 7.6 GB，与线上十几个容器共用，构建（尤其冷构建）会抢占 CPU、内存与临时磁盘。镜像推送和拉取对 VPS 都是入向流量，不受 5 Mbps 出网上限约束（实测入向可达约 19 Mbps）。构建在 ts-linux-ws 上完成，推送 Gitea 容器仓库，VPS 只拉取成品镜像（web 压缩传输约 94 MB）。

构建机一次性准备：

- docker 已登录 `gitea.xiaohe.team`，凭据写在 `~/.docker/config.json`（600）。
- `/etc/docker/daemon.json` 配置 `registry-mirrors: ["https://docker.1ms.run"]`（直连 Docker Hub 的 CloudFront 会 reset）与 `insecure-registries: ["100.64.0.4:3000"]`。
- 源码在 `~/plane-build`，上游前端源码在 `~/plane-web-src`。

构建与推送：

```bash
# on ts-linux-ws
cd ~/plane-build/xiaohe-plane
./scripts/build-and-push.sh v1.5.0-xh23              # backend + web
COMPONENTS=web ./scripts/build-and-push.sh v1.5.0-xh23
```

推送走 tailnet 的 `100.64.0.4:3000`（绕开 `gitea.xiaohe.team` 的 nginx 限流），镜像仓库路径与公网名一致，VPS 用公网名拉取即可。

VPS 拉取（登录一次，凭据在 `/root/.docker/config.json`，600）：

```bash
sudo docker login gitea.xiaohe.team -u git --password-stdin   # 密码从标准输入读，不落 shell 历史
sudo docker pull gitea.xiaohe.team/lzhshou/xiaohe-plane-backend:v1.5.0-xh23
sudo docker pull gitea.xiaohe.team/lzhshou/xiaohe-plane-web:v1.5.0-xh24
```

## 1. 下载 release 资产

```bash
mkdir -p ~/plane-selfhost
cd ~/plane-selfhost
# 使用本仓固定的上游 compose，避免每次拉 GitHub
cp upstream/docker-compose.v1.5.0.yml docker-compose.yaml
cp plane.env.example plane.env
```

把本目录的 `docker-compose.override.yml`、`configure.py`、`web-Caddyfile`、`plane.env.example` 复制到 `~/plane-selfhost/`。

env 模板只保留我们实际使用的键；GitHub/Gitea/Google/SMTP/LLM 等上游社区配置不再写入。

## 2. 配置

```bash
cd ~/plane-selfhost
# staging origin；公网时改为 PLANE_APP_DOMAIN=plane.xiaohe.team, PLANE_WEB_URL=https://plane.xiaohe.team
PLANE_BIND_IP=100.64.0.4 PLANE_APP_DOMAIN=100.64.0.4:8080 python3 configure.py
sudo docker compose --env-file plane.env \
  -f docker-compose.yaml -f docker-compose.override.yml config >/tmp/plane-config.yml
```

确认 `proxy` 的 published 端口是 `${PLANE_BIND_IP}:8080`（staging 为 `100.64.0.4`），13 个服务都有 `mem_limit`。

`configure.py` 会把 `__GENERATE__` 替换成独立密码，并把 `DATABASE_URL` / `AMQP_URL` 指向它们；不会打印密钥。

## 3. 拉取与启动

`pull` 同时会从 Gitea 容器仓库拉取 override 里指定的 backend/web 镜像，需先在 VPS 上登录一次（§0.1）。

```bash
sudo docker compose --env-file plane.env \
  -f docker-compose.yaml -f docker-compose.override.yml pull
sudo docker compose --env-file plane.env \
  -f docker-compose.yaml -f docker-compose.override.yml up -d
```

首次启动 migrator 会跑几分钟；等它退出后再访问。api 启动完成前 proxy 可能短暂 502，属正常。

## 4. 访问与初始化

浏览器打开 `http://100.64.0.4:8080`（需在同一 tailnet）：

1. Get started → 填实例名、管理员邮箱、密码。
2. God Mode → Create workspace。
3. 进入 workspace → Add project → 填项目名、Project ID、描述。
4. 建第一条 work item，确认列表与详情可打开。

## 5. static 资源限流

Plane 的 web 容器内置 Caddy 限流：`300 events / 1m / IP`。首屏一次加载就可能超过，表现为 `HTTP ERROR 429`。本目录的 `web-Caddyfile` 把它调到 `10000/min`，并通过 override 挂到 `/etc/caddy/Caddyfile`。

改动后重建 web：

```bash
sudo docker compose --env-file plane.env \
  -f docker-compose.yaml -f docker-compose.override.yml up -d web
```

## 6. 公网（已完成）

1. 已加 `plane.xiaohe.team` A 记录到 `159.75.28.184`。
2. 重新生成 env：

```bash
cd ~/plane-selfhost
PLANE_BIND_IP=127.0.0.1 \
PLANE_APP_DOMAIN=plane.xiaohe.team \
PLANE_WEB_URL=https://plane.xiaohe.team \
PLANE_CORS=https://plane.xiaohe.team \
python3 configure.py
```

3. 让 proxy 只监听本地，前面用 nginx 终止 TLS：

override 里 proxy 的 `ports` 使用 `${PLANE_BIND_IP:-127.0.0.1}:8080:80`；公网时把 `PLANE_BIND_IP` 设为 `127.0.0.1`，由 nginx 反代。

4. nginx vhost 反代到 `127.0.0.1:8080`，证书走现有 certbot。
5. `sudo docker compose ... up -d api proxy web`，确认登录、附件、WebSocket 正常。

## 7. 运维

恢复数据库或手工创建用户后，跑一次 Profile 回填（避免 `/users/me/profile/` 404 把前端打进维护页）：

```bash
sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml \
  exec -T api sh -c "python manage.py shell < /tmp/ensure_profiles.py"
```

脚本在 `deploy/ensure_profiles.py`；SSO 登录也会为缺失 Profile 的用户自动补建。


```bash
# 状态
sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml ps

# 日志
sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml logs -f api

# 备份
sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml \
  exec -T plane-db pg_dump -U plane plane > ~/plane-backup-$(date +%F).sql

# 停止（保留数据）
sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml down

# 删除数据（不可逆）
sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml down -v
```

### 请求防护（v1.5.0-xh23 起）

签名用户可以无上限地打 API，一个渲染循环就能压垮后端，所以请求路径有三层上限：

- **限流**：Redis 令牌桶，按用户计。人类会话持续 5 req/s、突发 40；bot / API-key 持续 2 req/s、突发 20（plane-bridge 轮询节奏）。超限返回 429 与 `Retry-After`；同一用户超过 300 req/min 写一条 WARNING（`name=plane.authentication`，含 user id、路径、计数）。
- **读缓存 + ETag**：`projects`、`members`、`bots`、`pages` 列表按用户缓存 3 秒并返回 `W/` ETag，重复请求多为 304；同一用户的任何写请求都会让缓存失效。
- **版本兜底**：API 响应带 `X-Build-Id`，web 产物带 `/version.json`（含 `build_id`），前端据此提示新版本，不强制刷新。

运行时开关，均在 `api` 容器的 environment 里，改后 `up -d api` 即生效，无需重建镜像：

| 变量 | 默认 | 作用 |
|---|---|---|
| `XIAOHE_THROTTLE_ENABLED` | 1 | 0 关闭限流 |
| `XIAOHE_READ_CACHE_ENABLED` | 1 | 0 关闭读缓存与 ETag |
| `XIAOHE_USER_RATE` / `XIAOHE_USER_BURST` | 5 / 40 | 人类会话速率与突发 |
| `XIAOHE_BOT_RATE` / `XIAOHE_BOT_BURST` | 2 / 20 | bot 速率与突发 |
| `XIAOHE_RATE_WARN_PER_MIN` | 300 | 告警阈值 |
| `XIAOHE_READ_CACHE_TTL` | 3 | 读缓存秒数 |

误伤时先关对应层（无需重建镜像），确认后再决定是否调参。回滚镜像仍按上面的 tag 回退。

### 部署后清理

只在验收通过后执行。以下任一项不满足就先不清，保留现场：

- `docker compose ps` 全部服务 `healthy` / `running`；
- `curl -I https://plane.xiaohe.team/` 与 `curl -I https://plane.xiaohe.team/uploads/` 正常；
- SSO 能从 `/auth/xiaohe/start/` 登录并进入 workspace。

保留：当前运行的 backend / web 镜像，外加两个前缀各自最近 2 个可回滚 tag。

只删：

- `^xiaohe-plane-backend:`、`^xiaohe-plane-web:` 下比保留集更旧的 tag；
- `xiaohe-plane-web-build:*` 中间镜像（`web/build.sh` 构建成功后会自动删，只剩残留的才手工清）。

方式：先 `docker images` 列清单，核对后用显式 `docker rmi <tag>` 逐个删。**不要用 `docker image prune -a` 或 `docker system prune`**：这台 daemon 多租户共用，上面有 `hetu-app/*`、`xiaohe-review:*` 和手工备份镜像，prune 会把它们一起清掉且不可恢复。

清理前后各记一次磁盘：

```bash
df -h /
sudo docker system df
```

可用空间低于 15 GB 时在 `docs/RUNBOOK.md` 记一条告警；删掉的镜像名与时间写进当次部署记录。

可直接复制的清单与删除命令：

```bash
# 当前在用的镜像：保留
sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml \
  ps --format '{{.Image}}' | grep -E '^xiaohe-plane-(backend|web):'

# 候选：每个前缀按创建时间倒序，跳过前 3 个（当前 + 2 个回滚点），其余列出
for prefix in xiaohe-plane-backend xiaohe-plane-web; do
  docker images --format '{{.CreatedAt}}  {{.Repository}}:{{.Tag}}  {{.Size}}' "$prefix" \
    | sort -r | tail -n +4
done

# 中间构建镜像
docker images --format '{{.CreatedAt}}  {{.Repository}}:{{.Tag}}  {{.Size}}' xiaohe-plane-web-build

# 核对清单后逐个显式删除，保留集不要动
docker rmi xiaohe-plane-web:v1.5.0-xh13 xiaohe-plane-web-build:v1.5.0
```

## 8. 注意

- 4GB 是**上限**，不是常驻占用；当前 worker 接近 384MiB 上限，若 OOM 先调高 worker 并下调 db 的 `mem_limit`，保持总和约 4GB。
- 本机 Docker 重启会停掉没有重启策略的容器；`hetu-apps-broker` 已补 `unless-stopped`。
- 升级固定 `APP_RELEASE`，先备份 `plane-db` 与 `uploads` 卷。

## 9. api worker 数与 max-requests

上游入口脚本把 `--max-requests 1200` 写死；gunicorn 的命令行参数优先级高于 `GUNICORN_CMD_ARGS`，环境变量覆盖不了，所以通过挂载参数化入口脚本实现：

- `docker-entrypoint-api-xh.sh`：上游 `bin/docker-entrypoint-api.sh` 的副本，末行改为
  `-w ${GUNICORN_WORKERS}`、`--max-requests ${GUNICORN_MAX_REQUESTS}`、`--max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER}`。
- override 中 api 的 `command:` 指向该脚本，并以只读 bind mount 挂到 `/code/bin/`。
- 取值由 `plane.env` 的 `GUNICORN_WORKERS` / `GUNICORN_MAX_REQUESTS` / `GUNICORN_MAX_REQUESTS_JITTER` 控制；默认 4 / 5000 / 1000。
- 4 个 worker 常驻约 560MiB，api `mem_limit` 相应为 1g。

上游镜像升级时，对照新镜像的 `bin/docker-entrypoint-api.sh` 更新该副本。

回滚到上游默认：删除 override 中 api 的 `command` 与 `volumes` 两行，`GUNICORN_WORKERS=1`，然后 `up -d api`。
