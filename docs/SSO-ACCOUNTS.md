# xiaohe accounts SSO：方案与落地

- 状态：**已实现**（`xiaohe-plane-backend:v1.5.0-xh2`）；本地登录保留 break-glass。

- 目标：Plane 登录改走 xiaohe accounts，保留本地登录作为 break-glass。
- 不做 OIDC：xiaohe accounts 已有给 cluster / skills 用的 OAuth2 授权码 + PKCE，Plane 只需要一个后端适配。

## 现有协议（accounts）

1. 浏览器打开 `https://accounts.xiaohe.team/oauth/authorize?client_id=plane&redirect_uri=...&code_challenge=...&code_challenge_method=S256&state=...`
2. accounts 页面若未登录，跳 `/login?next=...`；登录后调用 `POST /v1/oauth/authorize`（Bearer access token），拿到一次性 `code`。
3. 重定向到 `redirect_uri?code=...&state=...`。
4. 后端 `POST /v1/oauth/token`：

```json
{
  "grant_type": "authorization_code",
  "code": "...",
  "code_verifier": "...",
  "client_id": "plane",
  "redirect_uri": "https://plane.xiaohe.team/auth/xiaohe/callback/"
}
```

返回：

```json
{"user": {"id": "...", "email": "...", "is_admin": false}}
```

## accounts 侧改动

1. `api/internal/oauth/store.go`
   - 增加 `clientPlane = "plane"`。
   - `AllowedRedirect` 允许 `https://plane.xiaohe.team/auth/xiaohe/callback/`，以及 loopback `http://127.0.0.1:8080/auth/xiaohe/callback/`。
2. `web/src/platform/redirect.ts`
   - `allowedRedirect` 同步允许上述两个 URL。
3. 测试：`redirect.test.ts` 增加 plane 的正/负用例；OAuth store 增加 client 校验。
4. 部署 accounts（Go + web 重建）；现有 cluster / skills / download 客户端不受影响。

## Plane 侧改动（后端，不改前端）

新增一个 Django 视图模块，例如 `auth/plane/xiaohe.py`：

- `GET /auth/xiaohe/start?next=/research/`
  - 生成 32 字节 verifier、S256 challenge、state。
  - 存到 Django session（`xiaohe_oauth_verifier`、`xiaohe_oauth_state`、`xiaohe_oauth_next`）。
  - 302 到 accounts `/oauth/authorize`，`client_id=plane`，`redirect_uri=https://plane.xiaohe.team/auth/xiaohe/callback/`。
- `GET /auth/xiaohe/callback/?code=&state=`
  - 校验 state；从 session 取 verifier。
  - 服务端 POST accounts `/v1/oauth/token`。
  - 拿 `{id,email,is_admin}`；按 email 查 Plane `User`：
    - 已存在：直接登录。
    - 不存在：创建 `User`（`is_active=True`, `is_email_verified=True`），不自动给实例管理员。
  - 调 `plane.authentication.utils.login.user_login(request, user, is_app=False)` 写 Plane session。
  - 302 到 session 里的 `next`（只允许站内相对路径）或 `/research/`。
- URL 接入：在 Plane 的 URLconf 加两条路由；不改 React 前端。
- 构建：`FROM makeplane/plane-backend:v1.5.0`，复制模块并 patch URLconf；镜像 tag `xiaohe-plane-backend:v1.5.0-xh2`。
- compose override 只替换 `api` 的 image；worker/beat 可继续用上游镜像（不涉及登录）。

## 入口

- SSO 登录入口：`https://plane.xiaohe.team/auth/xiaohe/start/?next=/research/`
- apps 门户的 Plane 链接改为该入口；旧本地登录仍可从 `/sign-in` 使用。
- 以后要“Plane 登录页上也放按钮”，再重建前端；第一阶段不做。

## 用户与权限

- 邮箱映射：`XIAOHE_SSO_EMAIL_MAP`，格式 `accounts-email=plane-email`。当前把 `lai.zhengshou@outlook.com` 映射到 `laizhengsh@mail.sysu.edu.cn`，避免 accounts 登录新建一个没有 workspace 的重复用户。


- 按 email 关联已有 Plane 用户；管理员 `laizhengsh@mail.sysu.edu.cn` 直接关联。
- 新用户只创建 Plane 账号，不自动加入 workspace；成员关系仍由管理员在 Plane 或 `create_user.py` 管理。
- `is_admin` 只作为审计信息，不自动授予 Plane 实例管理员。
- bot `agent-bot@xiaohe.local` 不走 SSO，继续用 API token。

## 安全

- PKCE S256；state 一次性；session 存 verifier。
- `redirect_uri` 只接受 accounts 允许列表中的 plane 回调。
- `next` 只允许站内相对路径，拒绝 `//` 与外域。
- 回调失败统一跳到本地 `/sign-in?error=sso`，不泄露 accounts 错误细节。
- 保留 `ENABLE_SIGNUP=0`；SSO 用户创建由适配器控制。
- 记录登录审计（email、accounts user id、时间、IP）。

## 迁移步骤

1. [x] accounts 加 plane client / redirect，测试并部署。
2. [x] 构建 `xiaohe-plane-backend:v1.5.0-xh2`，staging + mock accounts 跑通。
3. [x] compose 替换 api 镜像；旧镜像可回滚。
4. [x] apps 门户指向 `/auth/xiaohe/start/?next=/research/`。
5. [ ] 真实 accounts 账号浏览器登录验收；本地登录保留 break-glass。

## 回滚

- compose 把 `api` 镜像切回 `makeplane/plane-backend:v1.5.0`，重建 api。
- accounts 的 plane client 可以保留，不影响其他客户端。
- 本地登录始终可用，SSO 故障不锁死管理员。

## 网络修复（2026-11-17）

Plane api 容器直接访问 `https://accounts.xiaohe.team/v1/oauth/token` 会 hairpin 超时，导致 accounts 登录成功后 Plane 仍停在登录页。已在 compose override 给 api 加 `extra_hosts: accounts.xiaohe.team:host-gateway`，容器内经宿主机 nginx 访问 accounts；容器内 `/healthz` 已验证 200。
