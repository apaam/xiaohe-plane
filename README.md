# xiaohe-plane

小荷自托管的 Plane：部署、xiaohe accounts SSO、运维与升级都在本仓。上游是 `makeplane/plane` CE **v1.5.0**（AGPL-3.0），本仓只保留我们自己的补丁与配置。

## 现状

- 实例：`https://plane.xiaohe.team`，登录走 xiaohe accounts SSO；本地 `/sign-in/` 保留为 break-glass。
- 个人工作台：`课题组 / research`，项目 `工作台 / WORK`。
- agent：`agent-bot@xiaohe.local` + Plane MCP。
- 许可：登录页和帮助菜单有 `Source (AGPL-3.0)` 链接，指向公开源码仓。
- SSO：后端适配 `auth/plane`，自定义 `api` 镜像；前端补丁见 `web/patches`。

## 结构

```
deploy/                 compose、4GB 限额、nginx、备份、账号脚本
deploy/upstream/        上游 compose 与 env 模板（v1.5.0）
auth/                   xiaohe accounts SSO 适配（设计 + 补丁）
docs/                   runbook、公网化、使用速查、SSO 方案
scripts/                部署/升级入口（建设中）
```

## 上游与许可

- 上游：<https://github.com/makeplane/plane>，固定 `v1.5.0` 镜像。
- 上游是 AGPL-3.0。本仓的修改同样以 AGPL-3.0 提供；对应源码与重建步骤见 `SOURCE.md`，公开地址为 <https://gitea.xiaohe.team/apaam/xiaohe-plane>。

## 快速入口

- 部署：`deploy/README.md`
- 运维：`docs/RUNBOOK.md`
- 使用：`docs/USING-PLANE.md`
- 公网化：`docs/PUBLICIZE.md`
- SSO 方案：`docs/SSO-ACCOUNTS.md`
- 迁移与清理：`docs/MIGRATION.md`

## 当前运行

| 项 | 值 |
|---|---|
| VPS | `ts-xiaohe`（Ubuntu，7.4GiB） |
| 运行目录 | `~/plane-selfhost` |
| proxy | 只监听 `127.0.0.1:8080`，nginx 终止 TLS |
| 数据 | Postgres + MinIO/Silo + RabbitMQ + Redis，4GB 上限 |
| 备份 | 每日 03:17，`~/plane-backups`，保留 14 天 |
