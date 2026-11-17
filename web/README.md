# Plane web — xiaohe UI cleanup

Plane 上游前端原样构建，只在构建时打几个小补丁，不改业务逻辑：

| 补丁 | 去掉 / 替换的内容 |
|---|---|
| `0001-remove-github-star-link.patch` | 顶栏“在 GitHub 上为我们加星” |
| `0002-hide-edition-badge.patch` | 侧栏底部 `Community` 版本徽标 |
| `0003-remove-auth-footer.patch` | 登录页 “Join 10,000+ teams” 与品牌 Logo |
| `0004-remove-quickstart-guide.patch` | 首页“快速入门指南”引导卡 |
| `0006-replace-billing-page.patch` | 把上游 Billing & Plans 套餐页换成小荷订阅入口 |
| `0007-sso-only-auth.patch` | 登录/注册/密码页统一跳 accounts SSO；退出同时清 accounts 会话 |
| `0008-remove-help-button.patch` | 去掉顶栏帮助按钮（键盘快捷键/Source/版本菜单） |

## 构建

在 VPS 上（源码克隆到 `~/plane-web-src`，不 vendor 进仓）：

```bash
DOCKER="sudo docker" ./web/build.sh
# 产物：xiaohe-plane-web:v1.5.0-xh7
```

脚本先 `git clone --depth 1 --branch v1.5.0` 上游源码，重置到 tag，打补丁，再用上游
`apps/web/Dockerfile.web` 构建。首次构建需要拉 node/caddy 镜像并安装前端依赖，约 15–30 分钟。

## 部署

`deploy/docker-compose.override.yml` 的 `web` 段指定镜像：

```yaml
  web:
    image: xiaohe-plane-web:v1.5.0-xh7
```

仍挂载 `web-Caddyfile`（放宽静态资源限流到 10000/min）。

```bash
cd ~/plane-selfhost
sudo docker compose --env-file plane.env \
  -f docker-compose.yaml -f docker-compose.override.yml up -d web
```

## 回滚

把 `web.image` 改回 `makeplane/plane-web:v1.5.0`，重建 `web` 容器即可。

## 说明

- 只动展示层，API、路由、权限、SSO 不受影响。
- 上游升级时先核对补丁是否仍能 apply；路径或组件结构变化就重做补丁。
- 这是自部署实例的本地修改，不对外分发前端构建产物。
