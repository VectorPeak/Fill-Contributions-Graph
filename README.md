<h1 align="center">
  Fill Contributions Graph | GitHub 贡献计划审核技能
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
GitHub account -> repo scan -> existing commit deduction -> Excel review -> push -> withdraw
```

---

## 为什么要做

GitHub contribution graph 只会统计已经进入 GitHub 仓库、位于默认分支或 `gh-pages` 分支、并且作者邮箱能归属到账号的提交。只在本地 `git commit` 不会改变贡献图；提交后不 push，也不会被 GitHub 统计。

Fill Contributions Graph 把这类跨仓库维护操作拆成可审核、可执行、可撤回的流程。它不会隐式触发，也不会直接跳到提交，而是先生成 Excel 审核表，让用户确认日期、提交数、仓库分布和 commit 细则。

核心策略：

- **Excel-first**：任何执行前必须先生成 Excel 审核表，并等待用户明确确认
- **existing-commit-aware**：先查询 GitHub 上同一天已有的作者提交数，再扣减计划新增数
- **push-before-withdraw**：执行阶段必须 push 到 GitHub 默认分支并验证远端可达，然后再进入 withdraw

## 工作原理

1. 显式调用 `fill-contributions-graph` 或 `$fill-contributions-graph`
2. 检查 `gh`、GitHub 登录和 API 连通性
3. 扫描账号仓库，默认排除 fork 和 archived 仓库
4. 要求 eligible repositories `> 10`
5. 使用 activity profile 生成活跃日和每日目标提交数
6. 查询当天已有作者提交数并扣减：

```python
planned_new_commit_count = max(0, target_commit_count - existing_author_commit_count)
```

7. 输出 Excel 审核表
8. 用户确认后才允许执行
9. push 到默认分支并验证远端包含提交
10. withdraw 默认使用 `git revert` 并 push revert commit

## 快速上手

生成每日聚合审核表：

```powershell
python .\scripts\generate_plan.py `
  --account VectorPeak `
  --start 2026-03-01 `
  --end 2026-04-01 `
  --profile vibe_coding_builder `
  --excel-out plan.xls
```

导出逐 commit 明细：

```powershell
python .\scripts\generate_plan.py `
  --account VectorPeak `
  --start 2026-03-01 `
  --end 2026-04-01 `
  --granularity commit `
  --excel-out commit-detail.xls `
  --out commit-detail.tsv
```

`--end` 使用左闭右开语义。如果要包含 `2026-03-31`，应传入 `--end 2026-04-01`。

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
- 默认 withdraw 使用 `git revert`，这样内容被撤回但公共历史保留
- 不默认使用 `reset --hard + force push`
- 不创建空 commit、不写临时占位代码、不生成提交后再删除的假内容
- 如果本地已有同仓库 dirty worktree，必须先询问用户是否使用隔离 clone
