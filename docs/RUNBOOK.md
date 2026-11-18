# Plane 协作层 runbook

- 状态：**已公网运行（订阅准入 + invite-only）**。
- 定位：Plane 只做协作面（目标、节点、issue、讨论、成果链接）；执行面仍是 mini 的 agent-bus / xiaohe server。

## 1. 已完成（2026-11-17）

| 项 | 值 |
|---|---|
| 主机 | `ts-xiaohe`（7.4GiB 内存，Plane 容器实际约 1.5GiB） |
| 版本 | Plane CE `v1.5.0`，镜像固定，不用 `latest` |
| 部署目录 | `~/plane-selfhost` |
| 访问 | `https://plane.xiaohe.team/research`（公网，订阅准入 + invite-only） |
| 实例 | 中山大学 |
| 管理员 | `lai.zhengshou@outlook.com`；密码在 `~/.xiaohe/plane/admin-password`（600，break-glass） |
| 登录 | xiaohe accounts SSO：`/auth/xiaohe/start/?next=/research/`；需有效小荷订阅（管理员豁免）；登录/注册/密码页统一跳 SSO；退出同时清 accounts 会话 |
| api 镜像 | `xiaohe-plane-backend:v1.5.0-xh15`（auth/plane 适配 + 订阅门槛 + Bots API） |
| web 镜像 | `xiaohe-plane-web:v1.5.0-xh13`（Billing 订阅、Bots 管理页、收件箱密度与 IME Enter 修复） |
| agent 身份 | `agent-bot@xiaohe.local`；token `~/.xiaohe/plane/agent-token`（600） |
| agent MCP | `~/.xiaohe/plane/plane-mcp.sh`；笔记本已注册为 `plane` |
| workspace | 课题组 / `research` |
| project | 工作台 / `WORK`（示例项目已归档） |
| work item | `WORK-1..5`；`WORK-5` 已完成并含 agent 评论 |
| 资源上限 | 13 个服务合计约 4.1GB 上限；实际约 1.5GiB |
| 静态资源 | web Caddy 限流由 300/min 调到 10000/min，否则首屏 429 |
| 公网入口 | `plane.xiaohe.team` 已代理 Plane；公开注册关闭 |
| 备份 | 每日 03:17 cron，`/home/ubuntu/plane-backups`，保留 14 天 |

部署细节与命令见 `xiaohe-plane/deploy/README.md`；日常使用见 `xiaohe-plane/docs/USING-PLANE.md`。

## 2. 公网化前置

- [x] DNS：`plane.xiaohe.team` A 记录指向 `159.75.28.184`。
- [x] TLS：证书已签发，到期 2027-02-15。
- [x] 认证：xiaohe accounts SSO；本地登录 break-glass；公开注册关闭。
- [ ] 合作者名单与 workspace 划分。
- [ ] 备份窗口与磁盘余量（当前 47GiB 可用）。

## 3. 公网化步骤

1. DNS 与证书已完成。
2. 公网 env 已切换；以下命令保留作复核：

```bash
cd ~/plane-selfhost
PLANE_APP_DOMAIN=plane.xiaohe.team \
PLANE_WEB_URL=https://plane.xiaohe.team \
PLANE_CORS=https://plane.xiaohe.team \
python3 configure.py
```

3. 保持 proxy 只监听 `127.0.0.1:8080`，nginx 终止 TLS 并反代；不要用 `/plane` 子路径。
4. `sudo docker compose ... up -d api proxy web`，验证登录、附件、WebSocket。
5. 公网入口走 nginx；Plane proxy 只监听 `127.0.0.1:8080`。

## 4. 智能体接入

在 mini / 笔记本上配置官方 MCP（wrapper 已就位）：

```bash
PLANE_BASE_URL=http://100.64.0.4:8080 \
PLANE_API_KEY=$(cat ~/.xiaohe/plane/agent-token) \
PLANE_WORKSPACE_SLUG=research \
uvx plane-mcp-server stdio
```

- 独立 bot 账号已建；token 只放 mini 与笔记本，不进仓库。
- 先跑通：从 issue 开工 → 会话 → 回写 comment + 状态。
- 合作者触发的 issue 不直接拉起高权限会话；默认要本人确认或指派。

## 5. 协作边界

- 一个合作组一个 workspace；成员最小权限。
- 只放目标、节点、issue、状态、决策、成果链接。
- 原始数据、会话日志、机器路径、密钥、未定稿草稿不进 Plane。
- 大文件走共享 MinIO/dufs 限时签名链接；小文件挂 issue 附件。
- 合作者不获得 mini 的 shell/tailnet 权限。

## 6. 备份与升级

- 恢复数据库或手工建用户后运行 `deploy/ensure_profiles.py`，补齐 `Profile` 并标记已有 workspace 的用户 onboarded。

```bash
# 每日
docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml \
  exec -T plane-db pg_dump -U plane plane > ~/plane-backup-$(date +%F).sql
# uploads 卷单独快照
# 升级前备份；固定 APP_RELEASE，升级后检查 migration 日志
```

验收：登录、项目/issue、附件、MCP 调用均正常，再删旧备份。

## 7. 验收清单

- [x] staging 登录成功。
- [x] 公网 DNS + TLS + nginx 代理。
- [x] 公开注册关闭（页面提示 Sign up disabled）。
- [x] 创建 workspace / project / work item。
- [x] bot 通过 REST 创建/更新工作项、写评论。
- [x] bot 通过 MCP 读取并更新工作项。
- [x] 公网代理与 SSO 切换。
- [ ] 邀请合作者并验证权限。
- [x] bot 账号通过 MCP 创建 issue、评论、改状态。
- [ ] 用真实 accounts 账号完成一次浏览器登录。
- [ ] 大文件走签名链接，不暴露本地路径。
- [x] 备份脚本手动跑通（Postgres + uploads）。
- [ ] 备份恢复演练。

## 8. 未决事项

1. 合作者名单与 workspace 权限；accounts 用户首次登录自动建 Plane 用户。
2. 合作者范围与 workspace 划分。
3. 对象存储与 Plane 的 MinIO 是否复用。
4. 是否给 worker 调高内存上限（当前接近 384MiB）。
