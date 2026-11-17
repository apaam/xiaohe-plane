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

- 自定义镜像 `xiaohe-plane-backend:v1.5.0-xh2`（SSO + 邮箱映射 + hairpin 修复）。
- `api` 仅替换镜像；worker/beat/web/proxy 仍用上游 v1.5.0。
- 本地 `/sign-in/` 保留 break-glass。

## 待做（按优先级）

1. **提交两仓**：
   - `xiaohe-plane`：`git init` 已做，尚未 commit。
   - `xiaohe-accounts`：plane client / allowlist 4 个文件未 commit。
2. **Gitea 远程仓与 CI**：
   - 在 Gitea 建 `xiaohe-plane`，推送本仓。
   - 增加构建自定义 api 镜像的 workflow（或保留 VPS 手动 build + tag）。
   - 不建议把上游源码整包 vendor 进来；继续 pin 上游镜像，只维护 `auth/plane` 补丁。
3. **运行时 env 收窄**：在维护窗口把 `~/plane-selfhost/plane.env` 按 `plane.env.example` 收敛，先备份再重建容器。
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
