# auth

xiaohe accounts SSO 适配层。

- `../docs/SSO-ACCOUNTS.md`：完整方案（accounts 协议、Plane 后端视图、迁移与回滚）。
- 待落地：
  - `plane/xiaohe.py`：Plane Django SSO 视图。
  - `plane/urls.patch`：URLconf 补丁。
  - `plane/Dockerfile`：基于 `makeplane/plane-backend:v1.5.0` 的自定义镜像。
  - `accounts/`：xiaohe-accounts 的 plane client / redirect 允许列表补丁。

已实现：`plane/xiaohe_sso.py` + 自定义 api 镜像；本地登录保留 break-glass。
