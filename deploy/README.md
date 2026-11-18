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
| api 镜像 | `xiaohe-plane-backend:v1.5.0-xh12`（`auth/plane` + 订阅门槛） |
| 容器访问 accounts | `extra_hosts: accounts.xiaohe.team:host-gateway`，避免公网 hairpin 超时 |
| 备份 | 每日 03:17 cron，`~/plane-backups`（Postgres dump + uploads tar，保留 14 天） |
| 实际内存 | Plane 容器合计约 1.5GiB；host 可用约 4.6GiB |

## 0. 前置条件

- Docker 29+、`docker-compose-v2`。
- Docker registry mirror：`https://mirror.ccs.tencentyun.com`（VPS 直连 Docker Hub 会超时）。
- 目录 `~/plane-selfhost`。

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

## 8. 注意

- 4GB 是**上限**，不是常驻占用；当前 worker 接近 384MiB 上限，若 OOM 先调高 worker 并下调 db 的 `mem_limit`，保持总和约 4GB。
- 本机 Docker 重启会停掉没有重启策略的容器；`hetu-apps-broker` 已补 `unless-stopped`。
- 升级固定 `APP_RELEASE`，先备份 `plane-db` 与 `uploads` 卷。
