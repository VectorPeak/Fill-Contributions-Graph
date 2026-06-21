<h1 align="center">
  Fill Contributions Graph | GitHub 贡献图补全规划技能
</h1>

<p align="center">
  显式调用的 Codex Skill：扫描用户自己的 GitHub 仓库，生成 Excel 审核计划，扣除已有提交数，并在确认后执行 push-and-withdraw 工作流
</p>

<p align="center">
  <a href="https://github.com/VectorPeak/vectorpeak-agent-skills"><img src="https://img.shields.io/badge/agent-skills-blue" alt="agent skills"></a>
  <a href="./"><img src="https://img.shields.io/badge/fill--contributions--graph-github-green" alt="fill contributions graph"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-lightgrey" alt="license Apache-2.0"></a>
</p>

```text
GitHub account  ->  repo scan  ->  existing commit deduction  ->  Excel review  ->  push  ->  withdraw
```

---

## 为什么要做 Fill Contributions Graph?

GitHub contribution graph 只会统计已经进入 GitHub 仓库、位于默认分支或 `gh-pages` 分支、并且作者邮箱能归属到账号的提交。只在本地 `git commit` 不会改变贡献图；提交后不 push，也不会被 GitHub 统计。

Fill Contributions Graph 解决的是“把贡献图补全动作拆成可审核、可执行、可撤回流程”的问题。它不会隐式触发，也不会直接跳到提交，而是先生成 Excel 审核表，让用户确认日期、提交数、仓库分布和 commit 细则，再进入执行阶段。

核心策略是 **Excel-first, existing-commit-aware, push-before-withdraw**：

- **Excel-first**：任何执行前必须先生成 Excel 审核表，并等待用户明确确认
- **existing-commit-aware**：先查询 GitHub 上同一天已有的作者提交数，再扣减计划新增数
- **push-before-withdraw**：执行阶段必须 push 到 GitHub 默认分支并验证远端可达，然后再进入 withdraw

## 工作原理

1. **显式触发**：只在用户明确调用 `fill-contributions-graph` 或 `$fill-contributions-graph` 时使用

2. **前置检查**：确认本机存在 `gh`、已登录 GitHub、API 连通正常

3. **仓库扫描**：通过 `gh repo list <account>` 扫描账号或组织仓库，默认排除 fork 和 archived 仓库

4. **仓库数量门槛**：eligible repositories 必须 `> 10`，否则停止并要求用户调整范围或补充真实仓库

5. **活跃模型生成**：使用 `vibe_coding_builder` 或 `active_personal_builder` 生成活跃日和每日目标提交数

6. **已有提交扣除**：使用 GitHub commit search 查询当天已有作者提交数：

   ```text
   author:<author> author-date:<YYYY-MM-DD>..<YYYY-MM-DD> user:<account>
   ```

   然后计算：

   ```python
   planned_new_commit_count = max(0, target_commit_count - existing_author_commit_count)
   ```

7. **Excel 审核**：输出每日聚合表，字段包括日期、目标提交数、已有提交数、本次新增数和 commit 细则

8. **执行确认**：用户明确确认 Excel 后，才允许进入 push-and-withdraw

9. **Push-And-Withdraw**：创建 durable maintenance commits，push 到 GitHub 默认分支，验证远端包含提交，再准备 withdraw

10. **Withdraw**：默认使用 `git revert` 并 push revert commit；只有用户单独确认时才允许 force rewriting

## 快速上手

### 1. 生成 Excel 审核计划

```powershell
python .\scripts\generate_plan.py `
  --account VectorPeak `
  --start 2026-03-01 `
  --end 2026-04-01 `
  --profile vibe_coding_builder `
  --excel-out plan.xls
```

`--end` 使用左闭右开语义。如果要包含 `2026-03-31`，应传入 `--end 2026-04-01`。

### 2. 导出逐 commit 明细

下游执行器如果需要一行对应一个 commit，可以使用：

```powershell
python .\scripts\generate_plan.py `
  --account VectorPeak `
  --start 2026-03-01 `
  --end 2026-04-01 `
  --granularity commit `
  --excel-out commit-detail.xls `
  --out commit-detail.tsv
```

### 3. 指定作者

默认作者等于 `--account`。如果 GitHub author 不是账号名，可以显式传入：

```powershell
python .\scripts\generate_plan.py `
  --account VectorPeak `
  --author VectorPeak `
  --start 2026-03-01 `
  --end 2026-04-01 `
  --excel-out plan.xls
```

### 4. 跳过已有提交扣除

通常不建议跳过。只有在调试分布模型时使用：

```powershell
python .\scripts\generate_plan.py `
  --account VectorPeak `
  --start 2026-03-01 `
  --end 2026-04-01 `
  --skip-existing-deduction `
  --excel-out plan.xls
```

## 输出格式

默认 Excel 审核表字段：

```text
日期 | 目标提交数 | 已有作者提交数 | 本次计划新增数 | commit细则
```

逐 commit 明细字段：

```text
date | time | repo | kind | task_type | message | path | summary | target_commit_count | existing_commit_count | planned_new_commit_count
```

计划脚本只负责生成审核材料，不会 commit、push 或 withdraw。

## Activity Profiles

当前只保留两个 profile：

- `vibe_coding_builder`：默认，高频 AI 辅助迭代模型
- `active_personal_builder`：较保守的个人项目维护模型

详细分布见 `references/activity-profiles.md`。

## 目录结构

```text
fill-contributions-graph/
├── SKILL.md
├── README.md
├── LICENSE
├── agents/
│   └── openai.yaml
├── references/
│   └── activity-profiles.md
└── scripts/
    └── generate_plan.py
```

## 注意事项

- 只允许显式触发，不从普通 GitHub、commit、贡献图讨论中隐式启动
- 生成 Excel 后必须等待用户确认，不能直接进入执行
- 贡献图不会统计本地未 push 的 commit
- push 后 GitHub contribution graph 可能需要延迟刷新
- 默认 withdraw 使用 `git revert`，这样内容被撤回但公共历史保留
- 不默认使用 `reset --hard + force push`，因为移除默认分支可达提交可能让贡献图归属不稳定
- 不创建空 commit、不写临时占位代码、不生成提交后再删除的假内容
- 如果本地已有同仓库 dirty worktree，必须先询问用户是否使用隔离 clone
