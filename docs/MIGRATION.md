# 迁移与清理记录

## 已完成

### 从 agent-bus 迁出

- Plane 的 deploy/docs 已移到本仓；`agent-bus` 只保留消息 hub。
- `agent-bus/docs/ADR.md` 保留三层架构，Plane 细节指向本仓。

### VPS 清理

- 删除上游源码克隆 `~/plane`（约 101MB，含 `.github`、`deployments/cli/community` 等）。
- 删除临时构建目录 `~/xiaohe-plane-auth`；源码在本仓 `auth/plane/`。
- 删除 `/tmp` 下的 Plane 临时脚本、渲染后的 compose（可能含密钥）、mock accounts、SSO cookie jar。
- 删除 staging 容器 `plane-sso-test` / `plane-mock-accounts`，删除旧镜像 `xh1`。
- 运行时只保留 `~/plane-selfhost`（约 44KB）+ Docker 卷；`~/plane` 不再被引用。

### env 模板收窄

- 删除上游 `variables.env`（含 GitHub/Gitea/Google/SMTP/LLM/Unsplash 等社区配置）。
- 新增 `deploy/plane.env.example`，只保留实际使用的键；密钥用 `__GENERATE__`，由 `configure.py` 填充。
- 运行时 `~/plane-selfhost/plane.env` 暂保留完整键，避免无维护窗口时改动线上配置；新部署用最小模板。

### 运行时

- 自定义镜像 `xiaohe-plane-backend:v1.5.0-xh8`（SSO + 直接邮箱关联 + hairpin 修复 +
  Page 图片 inline 补丁 + Plane 订阅门槛/会话到期）。
- 自定义前端 `xiaohe-plane-web:v1.5.0-xh6`：去掉顶栏 GitHub 加星、侧栏 Community
  徽标、登录页上游营销、首页快速入门引导；登录页和帮助菜单加入 `Source (AGPL-3.0)`，Billing & Plans 替换为小荷订阅入口；登录/注册/密码页统一跳 accounts SSO，退出同时清 accounts 会话
  链接；帮助菜单移除文档/联系销售/论坛/What’s new，登录页移除上游 Terms/Privacy，邀请页移除 GitHub/Forum 按钮。补丁在 `web/patches/`，构建脚本 `web/build.sh`。
- `api`、`web` 仅替换镜像；worker/beat/proxy 仍用上游 v1.5.0。
- 本地 `/sign-in/` 保留 break-glass。

## 已完成（提交与远程）

- `xiaohe-plane` 初始提交 `d2ea1a5`，已推送 `http://100.64.0.4:3000/apaam/xiaohe-plane`。
- `xiaohe-accounts` 提交 `5115102`（plane OAuth client / allowlist），已推送 `apaam/xiaohe-accounts`。

## 待做（按优先级）

1. **CI 构建镜像**：
   - Gitea 28.3.0；未确认 container registry 与 amd64 builder。
   - 暂保留 VPS 手动 `auth/plane/build.sh` + tag；确认 registry/runner 后再加 workflow。
   - 不建议把上游源码整包 vendor 进来；继续 pin 上游镜像，只维护 `auth/plane` 补丁。
2. **运行时 env 收窄**：在维护窗口把 `~/plane-selfhost/plane.env` 按 `plane.env.example` 收敛，先备份再重建容器。
3. **SSO 真实验收**：用 accounts 账号完成一次浏览器登录；Plane 用户邮箱已与 accounts 一致。
4. **密钥归位**：
   - `admin-password`、`agent-bot.token` 目前在 VPS 600 文件；可迁到密码管理器/accounts 体系。
   - 不要把 token/密码写进仓库或 Plane issue。
5. **备份恢复演练**：Plane 每日 03:17 备份已跑通；还需实际恢复一次。
6. **资料同步**：`agent-bus/docs/MATERIALS-SYNC.md` 仍是策略，未迁移数据。
7. **UI 参考**：见 `PLANE-UI-REFERENCE.md`；只借鉴模式，不直接复制 AGPL 代码。

## 不迁移/不保留

- 上游 `.github`、`deployments/cli/community`、swarm/kubernetes 部署样例。
- GitHub/Gitea/Google/SMTP/LLM 等未启用的社区 provider 配置。
- 上游 setup.sh 交互安装流程；我们用自己的 compose + configure.py。
