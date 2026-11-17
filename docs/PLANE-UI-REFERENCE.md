# Plane 视觉参考 → xiaohe-ui

- 结论：可以借鉴**设计语言与交互模式**，不建议直接搬 Plane 的 CSS/React 组件。
- 原因：Plane CE 是 AGPL-3.0；把它的组件代码/样式复制进要分发的 `xiaohe-ui`，会把许可与维护耦合带进来。另外 Plane 是蓝色、Tailwind + headless 组件体系，`xiaohe-ui` 是 shadcn 基线 + 绿荷 accent，直接搬会破坏品牌一致性。

## 值得借鉴的

| Plane 模式 | 可借鉴点 | xiaohe-ui 落点 |
|---|---|---|
| 工作项行 | 高密度、单行信息层级、状态/优先级/负责人右侧对齐 | 新的 `WorkItemRow` 模式，沿用 `--xui-*` token |
| 看板卡片 | 轻边线、低阴影、卡片密度与拖拽反馈 | `Card` + board 视图的 density 变体 |
| 状态/优先级 chip | 小尺寸、低饱和背景、文字+图标并用 | `Badge` 的 compact 变体 |
| 行内属性编辑 | 点击属性就地编辑，不弹大表单 | 属性行 + popover，键盘优先 |
| 命令面板 | 全局搜索与快捷动作 | 复用现有 command palette，不引入新依赖 |
| 空状态 | 插画克制、文案短 | `EmptyState` 的插图区 |
| 侧栏 | 项目分组、折叠、计数 | 现有 sidebar 的密度调整 |

## 不建议照搬的

- Plane 的蓝色主色与渐变/插图风格。
- Tailwind 原子类命名与自定义 headless 组件 API。
- 整套 36/44px 行高与字号；先对照 `xiaohe-ui` 的现有密度再定。
- 任何 `apps/web` 下的组件源码或 CSS 文件。

## 建议的落地方式

1. **截图/ token 盘点**：选 6–8 个代表性界面（工作项列表、看板、详情、命令面板、空状态、移动端），记录间距、圆角、字号、状态色。
2. **映射到 xiaohe-ui token**：优先复用 `--xui-*`，只补缺少的语义 token（如 `--xui-row-height-compact`），不新增一套 Plane 命名。
3. **一个原型**：先做 `WorkItemRow` 或 board card，放进 xiaohe-ui 的 story/预览；保持绿荷 accent，不引入 Plane 的蓝色。
4. **评审后再扩散**：原型通过后再做 badge、inline property、命令面板；不做一次性全量迁移。

## 许可

Plane 上游 AGPL-3.0。参考视觉与交互模式不构成复制代码；若复制具体 CSS/组件实现，需要按 AGPL 处理，并与 `xiaohe-ui` 的分发方式一起评估。

## 下一步

如果要做，先产出上面的 6–8 张界面盘点与 token 映射表，再选一个组件在 `xiaohe-ui` 做原型；不建议直接开分支大改。
