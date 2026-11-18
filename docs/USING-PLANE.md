# Plane 个人使用速查

- 入口：`https://plane.xiaohe.team/research`
- 登录：走 xiaohe accounts SSO（apps 门户的 Plane 入口，或 `https://plane.xiaohe.team/auth/xiaohe/start/`）。
- 默认落点：登录后进入你最近访问/最早加入的 workspace；没有 workspace 时进 onboarding，可自建 workspace（创建者即 workspace Admin）。课题组成员可直接用 `?next=/research/` 指定课题组。
- 准入：账号需有有效的小荷订阅（新注册自带 1 个月试用；管理员豁免）。没有订阅时，accounts 会跳商店页，购买后回到登录流程。
- 本地 break-glass：`https://plane.xiaohe.team/sign-in/`，管理员密码在 `~/.xiaohe/plane/admin-password`（600）。
- 当前 workspace：课题组 `/research`
- 个人项目：**工作台** `/WORK`（示例项目已归档并改名为“示例项目（可删）”）。

## 开发项目

Plane 没有子项目；按产品线建两个项目，项目内用 Module 分代码仓：

| 项目 | identifier | Modules |
|---|---|---|
| xiaohe dev | XHD | agent / reader / cluster / plane |
| phynexis dev | PXD | core / viewer / graph / server |

- 旧的单仓项目 XHA/XHR/XHC/XHP 已删除；PXV 保留归档（作为迁移来源）。
- PXV-1 已迁移为 **PXD-1**（viewer 模块），附件、认领记录和排查结论都保留。
- 汇总视图：`https://plane.xiaohe.team/research/workspace-views/b67f5a09-8e05-4402-941f-329502b71dbc/`
- 视图已固定过滤 XHD + PXD，工作台的任务不会混进来。
- 图标：XHD `code`、PXD `science`，统一 indigo（`#5e6ad2`）；工作台用绿色 `home`。
- Plane 的 API 新建项目时 `logo_props` 只读，没显式指定会随机取图标；要改在项目设置里操作。
- Plane 项目名不允许连字符，所以用空格；identifier 用产品线缩写。
- 分支与 commit 带 identifier，如 `XHD-12: ...` 或 `PXD-3: ...`；module 说明涉及哪个仓。

## 研究项目

| 项目 | identifier | Modules |
|---|---|---|
| 海缆损伤与失效预测 | HC | 损伤识别与结构响应 / 耦合响应与数值模拟 / 寿命预测与可靠度 / 项目与交付 |

- 粤港联合基金：内地 2026A0505050020，港方 GHP/006/25GD；任务书 2026-01-01 至 2027-12-31。
- 项目 Pages：`项目概况`、`研究内容与分工`、`论文与成果致谢口径`、`论文想法（2026-11）`、
  `海缆模拟结果解读（2026-11-16）`、`模型参数与假设`、`讨论与跟进（2026-11）`。
- 研究问题、数据、阶段报告放工作项和 Pages；代码仍归各自仓库。
- Modules 按任务书三项研究内容拆分，`项目与交付` 承载启动会、中期、结题与成果盘点。

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
工作项状态以 Plane 为准。2026-11-18 时：WORK-1～5 Done；WORK-6/8/9/10 进行中（已有 agent 回写）；
WORK-7 进行中（等仓库/机器决策）；WORK-11 Done（含完整结果评论）。

## 视图

- `Work items`：列表，适合批量改状态/负责人/日期。
- 看板/分组：右上角切换，按状态或负责人分组。
- `Pages`：项目内自由文档；需要长文说明时用。
- 时间点：work item 的 start/target date；需要成组交付时用 module。

## 手机

Safari 打开 `https://plane.xiaohe.team/auth/xiaohe/start/?next=/research/`，用 xiaohe accounts 登录后可“添加到主屏幕”。公开注册已关闭。

## 账号与协作

- 有 xiaohe accounts 的同事首次 SSO 登录会自动建 Plane 用户，再由管理员加入 workspace/project。
- 添加成员顺序：先 workspace，后 project。
  1. 对方用同一邮箱注册 accounts，并确保有有效订阅（或由运营赠送一个月）。
  2. 你以 workspace Admin 进入 Settings → Members → Invite members，填邮箱、角色 Member。
  3. SMTP 未配置，邀请邮件不会发出；在 Pending invites 里点 ⋯ → Copy link，把链接直接发给对方。
  4. 对方打开链接、用同一邮箱 SSO 登录并 Accept，成为 workspace member。
  5. 进入项目 Settings → Members → Add member，选该成员并设置项目角色。
- `Agent Bot` 原本是 bot 用户，Plane 的负责人候选会排除 bot；本实例已把该账号的
  `is_bot` 改为 `false`（名称仍是 Agent Bot），所以能在下拉框里选到。升级/重装后若选不到，
  重设该字段即可。

### 成员添加自己的 bot

每个成员用**独立 bot 身份**，不共用你的 `Agent Bot` token。

**推荐：workspace 管理员在 Plane 里自助创建。**

1. 打开 **Settings → Bots**（仅 Admin 可见）。
2. 填名称（会生成 `<name>-bot@xiaohe.local`），勾选要参与的项目，点“创建 bot”。
3. 页面**只显示一次 token**；复制后私下发给成员，存到其本机 `~/.xiaohe/plane/agent-token`（600）。
4. 之后可在同一页轮换 token、停用或重新启用 bot；停用会撤销所有 token 并移除成员关系，重新启用后需要再轮换一次 token 才能继续使用。

**归属**：bot 有归属人，创建时默认是创建者。只有归属人或 workspace 管理员能把工作项指派给它；其他成员指派会被拒绝（403）。

**旧镜像的备用流程**（没有 Bots 页时）：由管理员在 VPS 的 api 容器里创建用户、加入项目并签发 token：

```bash
cd ~/xiaohe-plane  # 或在 VPS 上放 deploy/create_bot.py
sudo docker cp deploy/create_bot.py plane-selfhost-api-1:/tmp/create_bot.py
sudo docker exec -e PLANE_BOT_EMAIL=zhangsan-bot@xiaohe.local \
  -e PLANE_BOT_NAME='Zhangsan Bot' \
  -e PLANE_PROJECT_IDS=<project_uuid> \
  -i plane-selfhost-api-1 python manage.py shell < deploy/create_bot.py
```

脚本会打印一次 `token plane_api_...`，把它私下发给成员；不要贴 Plane、群聊或仓库。

3. 成员在自己机器上保存 token：`~/.xiaohe/plane/agent-token`（600），并配置
   `plane-agent` 技能或 `plane` MCP wrapper；agent 用这个 token 读写 Plane。
4. 每个 bot 都是独立账号、独立 token，可单独停用/轮换；成员的 bot 只加入需要参与的项目。
5. 脚本把 `is_bot` 设为 `false`，否则 Plane 不会把 bot 放进负责人候选；显示名仍保持
   `XXX Bot`，身份靠 token 和成员关系区分。
- 没有 accounts 的临时账号用 `xiaohe-plane/deploy/create_user.py` 开通。
- 一个合作组一个 workspace；个人工作台不要放合作方内容。
- 不给合作者 mini 的 shell/tailnet 权限；只给 Plane 账号。

### 用你自己的 Claude Code / Codex / Cursor

技能 `plane-agent` 与 harness 无关，任何能跑 shell 或连 MCP 的 agent 都能用：

1. 拿到自己的 bot token（见上一节）。
2. 保存：`~/.xiaohe/plane/agent-token`（600），或环境变量 `PLANE_API_KEY`；
   同时设 `PLANE_BASE_URL=https://plane.xiaohe.team`、`PLANE_WORKSPACE_SLUG=research`。
3. 入口二选一：
   - **REST**：`curl -H "X-API-Key: $TOKEN" https://plane.xiaohe.team/api/v1/workspaces/research/projects/`；
     能力面见技能的 `references/api.md`。
   - **MCP**：`uvx plane-mcp-server stdio`；Claude Code 用
     `claude mcp add plane -e PLANE_BASE_URL=... -e PLANE_WORKSPACE_SLUG=research -e PLANE_API_KEY=... -- uvx plane-mcp-server stdio`；
     Codex 写 `~/.codex/config.toml` 的 `[mcp_servers.plane]`（command / args / env）。
4. 装技能：Claude Code `~/.claude/skills/plane-agent/`；Codex `~/.agents/skills/plane-agent/`；
   Cursor 在仓库 `AGENTS.md` 里指向该技能。

token 一人一份，不共用、不进仓库。要让 agent 定时接单，可用 cron/launchd 轮询“指派给自己且未完成”的工作项，
交给 `claude -p` / `codex exec` 处理并回写评论；单并发与幂等（记录最后处理到的评论 ID）需自行保证。

## Agent 会话桥接

- 实现在小荷技能 `plane-bridge`（`.claude/skills/plane-bridge/`）：一个 work item 对应一个 xiaohe session；轮询 workspace 下**所有项目**（不限于工作台），人类评论转发到该 session，agent 的结果写回 Plane 评论。安装与配置见该技能的 `SKILL.md`。
- 映射 `~/.xiaohe/plane/threads.json`，锁 `threads.lock` / `agent.lock`，日志 `threads.log`；launchd 每 120 秒一轮，每次最多一个 turn。
- 取件顺序：可开始的优先 → 优先级（urgent/high/medium/low/none）→ 截止日期（逾期在前）→ 进行中先于待办/Backlog → 最近有活动的先；`start_date` 在未来的新工作项排在所有可开始项之后，但一旦有人回复或进入重试就视为“现在要做”。
- 失败处理：15 分钟无新输出 → 取消会话并写超时评论；error、无回复、超时都按 1 小时退避重试，最多 3 次；人类新评论会清零重试并立即转发。
- 完成判定看会话最后一条是否为 assistant 文本，不只看状态，避免把取消/崩溃当成完成。
- 2026-11-18 在 mini 上验证：WORK-11 完成并回写完整结果评论；WORK-7 回写核对结果并停在等决策。
  旧会话若已卡住（transcript 停在半截 tool_use），新建 session 并把 `threads.json` 的 `session_id` 指过去。
- 自带 Claude Code / Codex 不走这个桥（没有 xiaohe Session API），按上一节的手动或自建轮询方式接单。

### Agent 读取 Pages

官方 v1 API 没有 Pages 端点；本实例补了只读接口，bot token 可直接读：

```bash
TOKEN=$(cat ~/.xiaohe/plane/agent-token)
curl -s -H "X-API-Key: $TOKEN" https://plane.xiaohe.team/auth/xiaohe/pages/research/
curl -s -H "X-API-Key: $TOKEN" https://plane.xiaohe.team/auth/xiaohe/pages/research/<page_id>/
```

public 页面，或 bot 所在项目的页面可读；写入仍走网页。

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
