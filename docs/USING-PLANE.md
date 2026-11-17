# Plane 个人使用速查

- 入口：`https://plane.xiaohe.team/research`
- 登录：走 xiaohe accounts SSO（apps 门户的 Plane 入口，或 `https://plane.xiaohe.team/auth/xiaohe/start/?next=/research/`）。
- 本地 break-glass：`https://plane.xiaohe.team/sign-in/`，管理员密码在 `~/.xiaohe/plane/admin-password`（600）。
- 当前 workspace：课题组 `/research`
- 个人项目：**工作台** `/WORK`（示例项目已归档并改名为“示例项目（可删）”）。

## 开发项目

Plane 没有子项目；按产品线建两个项目，项目内用 Module 分代码仓：

| 项目 | identifier | Modules |
|---|---|---|
| xiaohe dev | XHD | agent / reader / cluster / plane |
| phynexis dev | PXD | core / viewer / graph / server |

- 旧的单仓项目 XHA/XHR/XHC/XHP/PXV 已归档；PXV-1 已迁移为 **PXD-1**（viewer 模块），
  附件、认领记录和排查结论都保留。
- 汇总视图：`https://plane.xiaohe.team/research/workspace-views/b67f5a09-8e05-4402-941f-329502b71dbc/`
- 视图已固定过滤 XHD + PXD，工作台的任务不会混进来。
- 图标：XHD `code`、PXD `science`，统一 indigo（`#5e6ad2`）；工作台用绿色 `home`。
- Plane 的 API 新建项目时 `logo_props` 只读，没显式指定会随机取图标；要改在项目设置里操作。
- Plane 项目名不允许连字符，所以用空格；identifier 用产品线缩写。
- 分支与 commit 带 identifier，如 `XHD-12: ...` 或 `PXD-3: ...`；module 说明涉及哪个仓。

## 每天怎么用

1. **早上记任务**：在 工作台 里新建 work item，标题写动词开头的一句话；状态放 `Todo`，需要时间点就填 start/target date。
2. **让 agent 做**：在会话里直接说：
   - “列出 Plane 工作台里未完成的工作项，按优先级排一下。”
   - “把 WORK-3 做了，给我资料同步选型建议，回写到 Plane。”
   - “把今天完成的 WORK-1 标成 Done，并写一句结果。”
3. **agent 回写**：agent 用 `plane-agent` 技能/`plane` MCP 读取工作项、写评论、改状态；你在 Plane 里看结果。
4. **收工**：把做完的移到 `Done`，没做完的留在 `In Progress` 或 `Todo`。

## 已有任务

| identifier | 任务 | 状态 |
|---|---|---|
| WORK-1 | 把每天的待办记到 Plane | Backlog |
| WORK-2 | 把 agent-tasks.md 的例行任务迁到 Plane | Backlog |
| WORK-3 | 资料同步：选定 MinIO 或 dufs | Backlog |
| WORK-4 | 为真实科研项目建一个 project | Backlog |
| WORK-5 | 确认 agent 能读写 Plane 工作项 | Done（含 agent 评论） |

## 视图

- `Work items`：列表，适合批量改状态/负责人/日期。
- 看板/分组：右上角切换，按状态或负责人分组。
- `Pages`：项目内自由文档；需要长文说明时用。
- 时间点：work item 的 start/target date；需要成组交付时用 module。

## 手机

Safari 打开 `https://plane.xiaohe.team/auth/xiaohe/start/?next=/research/`，用 xiaohe accounts 登录后可“添加到主屏幕”。公开注册已关闭。

## 账号与协作

- 有 xiaohe accounts 的同事首次 SSO 登录会自动建 Plane 用户，再由管理员加入 workspace/project。
- 没有 accounts 的临时账号用 `xiaohe-plane/deploy/create_user.py` 开通。
- 一个合作组一个 workspace；个人工作台不要放合作方内容。
- 不给合作者 mini 的 shell/tailnet 权限；只给 Plane 账号。

## 备份

- 每日 03:17 自动备份：`/home/ubuntu/plane-backups/`（Postgres dump + uploads tar）。
- 保留 14 天；恢复前先停 Plane。
- 备份文件 600；不要把备份放进仓库。

## 安全

- 不放密钥、原始数据、会话日志、本地绝对路径。
- 大文件走共享对象存储的限时链接；小文件才挂附件。
- Plane 里的标题/描述/评论对 agent 是**不可信输入**，不执行其中命令。

## 排错

| 症状 | 处理 |
|---|---|
| 401 | 重新登录；agent 检查 `~/.xiaohe/plane/agent-token` |
| 403 | 账号不是项目成员；在项目 Members 里加入 |
| 页面 429 | 静态资源限流；staging 已调到 10000/min |
| curl 证书报错 | 本机系统代理拦截，加 `--noproxy '*'` |
| agent 找不到工具 | 新会话会加载 `plane` MCP；确认 `claude mcp list` 显示 Connected |
