# Plane 公网化清单

- 当前：Plane 已公网运行 `https://plane.xiaohe.team`，订阅准入 + invite-only。
- DNS 托管：DNSPod（`active.dnspod.net` / `bootes.dnspod.net`）。
- `plane.xiaohe.team` 当前无 A 记录。

## 当前进度（2026-11-17）

- [x] DNSPod A 记录：`plane.xiaohe.team` → `159.75.28.184`（RecordId 2452397385）。
- [x] 证书：`/etc/letsencrypt/live/plane.xiaohe.team/`，到期 2027-02-15。
- [x] nginx 入口：HTTP 301、HTTPS 已代理 Plane。
- [x] 认证：xiaohe accounts SSO；公开注册关闭；本地登录 break-glass。
- [x] nginx 已切换为代理，公网可登录。

## 1. DNS

已完成。记录如下（供核对）：

| 主机记录 | 类型 | 记录值 | TTL |
|---|---|---|---|
| `plane` | A | `159.75.28.184` | 600 |

验证：

```bash
dig +short plane.xiaohe.team A   # 应返回 159.75.28.184
```

不要加 wildcard；只加这一条。

## 2. 证书

已完成。HTTP-01 webroot 方式：

```bash
sudo certbot certonly --webroot -w /var/www/certbot \
  -d plane.xiaohe.team --email lai.zhengshou@outlook.com --agree-tos --non-interactive
```

证书路径：`/etc/letsencrypt/live/plane.xiaohe.team/`。

## 3. nginx

当前 `/etc/nginx/sites-available/plane.xiaohe.team` 使用代理版，见
`xiaohe-plane/deploy/nginx-plane.conf.example`（保留版见 `nginx-plane-reserved.conf.example`）。

```bash
sudo ln -s /etc/nginx/sites-available/plane.xiaohe.team /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

不要用 `/plane` 子路径；Plane 的绝对路径与 cookie 不适合子路径。

## 4. 把 Plane 收回本地端口

已完成：Plane proxy 只监听 `127.0.0.1:8080`，由 nginx 对外。

```bash
cd ~/plane-selfhost
PLANE_BIND_IP=127.0.0.1 \
PLANE_APP_DOMAIN=plane.xiaohe.team \
PLANE_WEB_URL=https://plane.xiaohe.team \
PLANE_CORS=https://plane.xiaohe.team \
python3 configure.py
sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml up -d api proxy web
```

验证：

```bash
curl -I https://plane.xiaohe.team/
curl -I https://plane.xiaohe.team/uploads/
```

## 5. 认证与准入

- CE 不支持 OIDC；通过 `auth/xiaohe` 后端适配接 accounts OAuth2+PKCE。
- 已关闭公开注册与公开建 workspace；accounts 用户首次 SSO 登录自动建 Plane 用户。
- 合作者只给 workspace 成员权限；不要给实例管理员。
- 不暴露 Plane 的 MinIO 控制台；只通过 Plane 的 `/uploads` 访问附件。

## 6. 智能体接入

- 现有 bot：`agent-bot@xiaohe.local`，token 在 `~/.xiaohe/plane/agent-token`（600）。
- MCP wrapper：`~/.xiaohe/plane/plane-mcp.sh`。
- 公网切换后，把 wrapper 的 `PLANE_BASE_URL` 改成 `https://plane.xiaohe.team`，或保留 tailnet 内部地址（推荐内部走 tailnet，不绕公网）。
- token 只放 mini 和笔记本，不进仓库、不进 Plane issue。

## 7. 验收

- [ ] `dig` 返回 VPS IP。
- [ ] 证书有效，`https://plane.xiaohe.team` 可登录。
- [ ] 关闭公开注册；只有受邀成员能进。
- [ ] 工作项、评论、附件上传/下载正常。
- [ ] mini 通过 MCP 读取并回写一条工作项。
- [ ] `pg_dump` 备份与恢复演练。

## 8. 回滚

1. 禁用 nginx vhost：`sudo rm /etc/nginx/sites-enabled/plane.xiaohe.team && sudo nginx -t && sudo systemctl reload nginx`。
2. 把 env 改回 `PLANE_BIND_IP=100.64.0.4`、`APP_DOMAIN=100.64.0.4:8080`、`WEB_URL=http://100.64.0.4:8080`，重建 api/proxy/web。
3. 保留 DNS 记录不影响；必要时在 DNSPod 删除。
