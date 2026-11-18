# Plane × xiaohe accounts SSO

后端适配层，不需要重建 Plane 前端。

## 文件

- `xiaohe_sso.py`：`/auth/xiaohe/start/` 与 `/auth/xiaohe/callback/`。
- `bots.py`：`/auth/xiaohe/bots/<slug>/`，workspace Admin 自助创建、轮换、停用 bot（`-bot@xiaohe.local` 账号 + 管理 token）。
- `urls_xiaohe.py`：两条路由。
- `patch_urls.py`：构建时把路由挂进 Plane 的 `authentication/urls.py`，并加载 Page 图片补丁。
- `asset_inline_patch.py`：让 Page 里的图片以 inline 方式返回，避免显示 “Error loading image”。
- `Dockerfile`：基于 `makeplane/plane-backend:v1.5.0`。
- `build.sh`：构建 `xiaohe-plane-backend:v1.5.0-xh13`。

## 环境变量

| 变量 | 默认 |
|---|---|
| `XIAOHE_ACCOUNTS_URL` | `https://accounts.xiaohe.team` |
| `XIAOHE_OAUTH_CLIENT_ID` | `plane` |
| `XIAOHE_OAUTH_REDIRECT` | `https://plane.xiaohe.team/auth/xiaohe/callback/` |
| `XIAOHE_SSO_EMAIL_MAP` | 可选，`accounts-email=plane-email`，逗号分隔 |

## 构建

```bash
cd auth/plane
./build.sh
```

在 VPS 上构建时，把本目录 scp 过去：

```bash
ssh ts-xiaohe 'mkdir -p ~/xiaohe-plane-auth'
scp -q auth/plane/* ts-xiaohe:~/xiaohe-plane-auth/
ssh ts-xiaohe 'cd ~/xiaohe-plane-auth && sudo docker build -t xiaohe-plane-backend:v1.5.0-xh13 .'
```

## 部署

`deploy/docker-compose.override.yml` 的 `api` 段：

```yaml
  api:
    image: xiaohe-plane-backend:v1.5.0-xh13
    environment:
      XIAOHE_ACCOUNTS_URL: https://accounts.xiaohe.team
      XIAOHE_OAUTH_CLIENT_ID: plane
      XIAOHE_OAUTH_REDIRECT: https://plane.xiaohe.team/auth/xiaohe/callback/
```

```bash
cd ~/plane-selfhost
sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml up -d api
```

api 启动后：

```bash
curl -sS -D - -o /dev/null "http://127.0.0.1:8080/auth/xiaohe/start/?next=/research/"
# 302 → https://accounts.xiaohe.team/oauth/authorize?client_id=plane...
```

## 回滚

```bash
cd ~/plane-selfhost
# 把 override 的 api.image 改回：
# image: makeplane/plane-backend:v1.5.0
sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml up -d api
```

本地 `/sign-in/` 始终可用，SSO 故障不会锁死管理员。

## 已验证

- staging：mock accounts 跑通 start → callback → 用户关联 → session → 200。
- production：start 302 到 accounts `/oauth/authorize`，非法 state 回 `/sign-in/?error=sso`。
- 浏览器：`https://plane.xiaohe.team/auth/xiaohe/start/?next=/research/` 跳到 xiaohe accounts 登录页。

## 网络注意

Plane 的 api 容器需要访问 `https://accounts.xiaohe.team/v1/oauth/token`。VPS 上容器直接访问自己的公网域名会 hairpin 超时（日志：`urlopen error timed out`），所以 compose override 给 api 加了：

```yaml
    extra_hosts:
      - "accounts.xiaohe.team:host-gateway"
```

容器内解析到宿主机网关（当前 `172.17.0.1:443`），由宿主机 nginx 处理 accounts 的 TLS 与反代。验证：

```bash
sudo docker exec plane-selfhost-api-1 python -c "import urllib.request; print(urllib.request.urlopen('https://accounts.xiaohe.team/healthz', timeout=8).status)"
# 200
```
