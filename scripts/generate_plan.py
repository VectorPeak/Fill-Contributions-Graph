from __future__ import annotations

import argparse
import csv
import html
import hashlib
import json
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote_plus


PROFILES = {
    "vibe_coding_builder": {
        "active_days": ([3, 4, 5, 6, 7], [0.12, 0.28, 0.30, 0.20, 0.10]),
        "commits": ([2, 3, 4, 5, 6, 8, 10, 12, 16], [0.08, 0.14, 0.20, 0.18, 0.14, 0.10, 0.08, 0.05, 0.03]),
    },
    "active_personal_builder": {
        "active_days": ([2, 3, 4, 5, 6], [0.10, 0.28, 0.32, 0.22, 0.08]),
        "commits": ([1, 2, 3, 4, 5, 6, 8, 10, 12], [0.10, 0.18, 0.22, 0.18, 0.12, 0.08, 0.06, 0.04, 0.02]),
    },
}

WEEKDAY_MULTIPLIER = {0: 1.00, 1: 0.95, 2: 1.00, 3: 1.05, 4: 1.10, 5: 1.35, 6: 1.25}
REPOS_PER_DAY = ([1, 2, 3, 4], [0.30, 0.38, 0.22, 0.10])
BURST_DAYS = ([1, 2, 3], [0.45, 0.40, 0.15])
BURST_EXTRA = ([3, 4, 5, 6, 8], [0.25, 0.25, 0.22, 0.18, 0.10])
TASK_TYPES = (["docs", "analysis", "eval", "chore", "tests", "config"], [0.32, 0.22, 0.14, 0.14, 0.10, 0.08])

WEEKDAY_SLOTS = [("09:00", "11:30", 0.12), ("13:30", "17:30", 0.24), ("19:30", "23:50", 0.52), ("00:10", "01:30", 0.12)]
WEEKEND_SLOTS = [("10:00", "12:00", 0.20), ("14:00", "18:00", 0.30), ("20:00", "23:50", 0.40), ("00:10", "01:30", 0.10)]


@dataclass
class Repo:
    name: str
    description: str
    language: str
    updated_at: str


def run_gh(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result


def check_gh_preflight() -> None:
    if shutil.which("gh") is None:
        raise SystemExit(
            "Preflight failed: GitHub CLI `gh` was not found on PATH. "
            "Install GitHub CLI and restart the terminal before generating a plan."
        )

    version = run_gh(["gh", "--version"])
    if version.returncode != 0:
        detail = (version.stderr or version.stdout).strip()
        raise SystemExit(f"Preflight failed: `gh --version` failed. {detail}")

    auth = run_gh(["gh", "auth", "status", "-h", "github.com"])
    if auth.returncode != 0:
        detail = (auth.stderr or auth.stdout).strip()
        raise SystemExit(
            "Preflight failed: `gh auth status -h github.com` did not pass. "
            "Run `gh auth login -h github.com` and try again.\n"
            f"{detail}"
        )

    api = run_gh(["gh", "api", "rate_limit"])
    if api.returncode != 0:
        detail = (api.stderr or api.stdout).strip()
        raise SystemExit(
            "Preflight failed: `gh api rate_limit` could not reach GitHub. "
            "Check network, proxy, DNS, or GitHub authentication.\n"
            f"{detail}"
        )


def run_gh_repo_list(account: str, include_private: bool) -> list[Repo]:
    cmd = [
        "gh",
        "repo",
        "list",
        account,
        "--limit",
        "200",
        "--json",
        "name,description,isFork,isArchived,primaryLanguage,updatedAt",
    ]
    if not include_private:
        cmd.insert(6, "--visibility=public")
    result = run_gh(cmd)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip())
    rows = json.loads(result.stdout)
    repos = []
    for row in rows:
        if row.get("isFork") or row.get("isArchived"):
            continue
        language = (row.get("primaryLanguage") or {}).get("name") or ""
        repos.append(Repo(row["name"], row.get("description") or "", language, row.get("updatedAt") or ""))
    return repos


def count_existing_commits(account: str, author: str, day: date) -> int:
    query = f"author:{author} author-date:{day.isoformat()}..{day.isoformat()} user:{account}"
    result = run_gh([
        "gh",
        "api",
        "-H",
        "Accept: application/vnd.github+json",
        f"/search/commits?q={quote_plus(query)}&per_page=1",
        "--jq",
        ".total_count",
    ])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SystemExit(f"Failed to count existing commits for {day.isoformat()}: {detail}")
    try:
        return int(result.stdout.strip() or "0")
    except ValueError as exc:
        raise SystemExit(f"Unexpected GitHub commit search output for {day.isoformat()}: {result.stdout}") from exc


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def week_chunks(start: date, end: date) -> list[list[date]]:
    days = []
    current = start
    while current < end:
        days.append(current)
        current += timedelta(days=1)
    chunks = []
    chunk = []
    for day in days:
        chunk.append(day)
        if day.weekday() == 6:
            chunks.append(chunk)
            chunk = []
    if chunk:
        chunks.append(chunk)
    return chunks


def make_seed(account: str, start: str, end: str, profile: str, seed: str | None) -> int:
    if seed:
        return int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16)
    text = f"{account}:{start}:{end}:{profile}:fill-contributions-graph:v1"
    return int(hashlib.sha256(text.encode()).hexdigest()[:16], 16)


def choose_time(rng: random.Random, day: date) -> str:
    slots = WEEKEND_SLOTS if day.weekday() >= 5 else WEEKDAY_SLOTS
    starts, ends, weights = [], [], []
    for start, end, weight in slots:
        starts.append(start)
        ends.append(end)
        weights.append(weight)
    index = rng.choices(range(len(slots)), weights=weights, k=1)[0]
    start_h, start_m = map(int, starts[index].split(":"))
    end_h, end_m = map(int, ends[index].split(":"))
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    if end_minutes < start_minutes:
        end_minutes += 24 * 60
    minute = rng.randint(start_minutes, end_minutes)
    minute %= 24 * 60
    return f"{minute // 60:02d}:{minute % 60:02d}"


def repo_kind(repo: Repo) -> str:
    text = f"{repo.name} {repo.description} {repo.language}".lower()
    if any(token in text for token in ["rag", "llm", "agent", "skill", "wiki"]):
        return "rag-llm-agent"
    if any(token in text for token in ["kaggle", "tabular", "predict", "classifier", "model", "bert"]):
        return "ml"
    if any(token in text for token in ["blog", "mdx", "knowledge"]):
        return "knowledge"
    if any(token in text for token in ["android", "kotlin", "chat", "desktop", "pyside"]):
        return "app"
    return "tooling"


TASK_TEMPLATES = {
    "ml": {
        "docs": ("docs/experiments/{date}-modeling-notes.md", "docs: add {month} modeling notes"),
        "analysis": ("docs/experiments/{date}-validation-notes.md", "analysis: document validation assumptions"),
        "eval": ("docs/evaluation/{date}-baseline-checklist.md", "eval: add baseline evaluation checklist"),
        "chore": ("docs/maintenance/{date}-experiment-checklist.md", "chore: add experiment maintenance checklist"),
        "tests": ("docs/testing/{date}-smoke-test-plan.md", "tests: document smoke test plan"),
        "config": ("docs/config/{date}-environment-notes.md", "config: document environment assumptions"),
    },
    "rag-llm-agent": {
        "docs": ("docs/notes/{date}-workflow-notes.md", "docs: add {month} workflow notes"),
        "analysis": ("docs/notes/{date}-quality-checklist.md", "analysis: document quality checklist"),
        "eval": ("docs/evaluation/{date}-regression-notes.md", "eval: add regression evaluation notes"),
        "chore": ("docs/maintenance/{date}-review-notes.md", "chore: add maintenance review notes"),
        "tests": ("docs/testing/{date}-smoke-test-plan.md", "tests: document smoke test plan"),
        "config": ("docs/config/{date}-runtime-notes.md", "config: document runtime assumptions"),
    },
    "knowledge": {
        "docs": ("docs/editorial/{date}-topic-notes.md", "docs: add {month} topic notes"),
        "analysis": ("docs/editorial/{date}-comparison-notes.md", "analysis: document comparison notes"),
        "eval": ("docs/review/{date}-content-review-checklist.md", "eval: add content review checklist"),
        "chore": ("docs/editorial/{date}-backlog.md", "chore: update editorial backlog"),
        "tests": ("docs/review/{date}-link-check-plan.md", "tests: document link check plan"),
        "config": ("docs/config/{date}-site-notes.md", "config: document site assumptions"),
    },
    "app": {
        "docs": ("docs/maintenance/{date}-module-notes.md", "docs: add {month} module notes"),
        "analysis": ("docs/maintenance/{date}-runtime-assumptions.md", "analysis: document runtime assumptions"),
        "eval": ("docs/release/{date}-verification-checklist.md", "eval: add release verification checklist"),
        "chore": ("docs/maintenance/{date}-release-checklist.md", "chore: add release checklist notes"),
        "tests": ("docs/testing/{date}-manual-test-plan.md", "tests: document manual test plan"),
        "config": ("docs/config/{date}-packaging-notes.md", "config: document packaging assumptions"),
    },
    "tooling": {
        "docs": ("docs/maintenance/{date}-workflow-notes.md", "docs: add {month} workflow notes"),
        "analysis": ("docs/maintenance/{date}-scoring-notes.md", "analysis: document scoring notes"),
        "eval": ("docs/evaluation/{date}-review-checklist.md", "eval: add review checklist"),
        "chore": ("docs/maintenance/{date}-maintenance-checklist.md", "chore: add maintenance checklist"),
        "tests": ("docs/testing/{date}-smoke-test-plan.md", "tests: document smoke test plan"),
        "config": ("docs/config/{date}-local-setup-notes.md", "config: document local setup assumptions"),
    },
}


def content_for(repo: Repo, kind: str, task_type: str, day: date) -> str:
    return (
        f"# {repo.name} {task_type.title()} Notes\n\n"
        f"Date: {day.isoformat()}\n\n"
        f"This retrospective note captures durable maintenance context for `{repo.name}`.\n\n"
        "- Scope: record assumptions that should stay visible during later project work.\n"
        "- Review: keep this note short enough to update during regular maintenance.\n"
        "- Follow-up: convert any repeated checklist item into an automated test or script when it becomes stable.\n"
    )


def unique_path(path: str, seen: dict[tuple[str, str], int], repo_name: str) -> str:
    key = (repo_name, path)
    seen[key] = seen.get(key, 0) + 1
    if seen[key] == 1:
        return path
    if "." in path.rsplit("/", 1)[-1]:
        stem, suffix = path.rsplit(".", 1)
        return f"{stem}-{seen[key]:02d}.{suffix}"
    return f"{path}-{seen[key]:02d}"


def append_plan_row(
    rows: list[dict[str, str]],
    repo_use: dict[str, int],
    seen_paths: dict[tuple[str, str], int],
    rng: random.Random,
    repo: Repo,
    day: date,
    time_value: str,
) -> None:
    repo_use[repo.name] += 1
    kind = repo_kind(repo)
    task_type = rng.choices(*TASK_TYPES, k=1)[0]
    path_template, message_template = TASK_TEMPLATES[kind][task_type]
    month = day.strftime("%B")
    path = path_template.format(date=day.isoformat(), month=month)
    path = unique_path(path, seen_paths, repo.name)
    message = message_template.format(date=day.isoformat(), month=month)
    rows.append({
        "date": day.isoformat(),
        "time": time_value,
        "repo": repo.name,
        "kind": kind,
        "task_type": task_type,
        "message": message,
        "path": path,
        "summary": content_for(repo, kind, task_type, day).splitlines()[0],
    })


def apply_existing_commit_deduction(
    rows: list[dict[str, str]],
    account: str,
    author: str,
    skip_deduction: bool,
) -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["date"], []).append(row)

    kept_rows: list[dict[str, str]] = []
    day_stats: dict[str, dict[str, int]] = {}
    for day_text in sorted(grouped):
        day_rows = sorted(grouped[day_text], key=lambda item: item["time"])
        target = len(day_rows)
        existing = 0 if skip_deduction else count_existing_commits(account, author, parse_date(day_text))
        planned_new = max(0, target - existing)
        for row in day_rows[:planned_new]:
            row["target_commit_count"] = str(target)
            row["existing_commit_count"] = str(existing)
            row["planned_new_commit_count"] = str(planned_new)
            kept_rows.append(row)
        day_stats[day_text] = {
            "target_commit_count": target,
            "existing_commit_count": existing,
            "planned_new_commit_count": planned_new,
        }
    return kept_rows, day_stats


def build_daily_rows(rows: list[dict[str, str]], day_stats: dict[str, dict[str, int]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["date"], []).append(row)

    daily_rows = []
    for day in sorted(day_stats):
        stats = day_stats[day]
        day_rows = sorted(grouped.get(day, []), key=lambda item: item["time"])
        details = []
        for row in day_rows:
            details.append(f'{row["time"]} {row["repo"]}: {row["message"]} -> {row["path"]}')
        daily_rows.append({
            "date": day,
            "target_commit_count": str(stats["target_commit_count"]),
            "existing_commit_count": str(stats["existing_commit_count"]),
            "planned_new_commit_count": str(stats["planned_new_commit_count"]),
            "commit_details": " ; ".join(details),
        })
    return daily_rows


def write_tsv(rows: list[dict[str, str]], fieldnames: list[str], output: Path | None) -> None:
    if output:
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_excel_xml(rows: list[dict[str, str]], fieldnames: list[str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    labels = {
        "date": "日期",
        "target_commit_count": "目标提交数",
        "existing_commit_count": "已有作者提交数",
        "planned_new_commit_count": "本次计划新增数",
        "commit_details": "commit细则",
        "time": "时间",
        "repo": "仓库",
        "kind": "类型",
        "task_type": "任务类型",
        "message": "commit message",
        "path": "文件路径",
        "summary": "摘要",
    }
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
        'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">',
        '  <Worksheet ss:Name="Plan">',
        '    <Table>',
    ]
    lines.append("      <Row>" + "".join(
        f'<Cell><Data ss:Type="String">{html.escape(labels.get(field, field))}</Data></Cell>'
        for field in fieldnames
    ) + "</Row>")
    for row in rows:
        cells = []
        for field in fieldnames:
            value = row.get(field, "")
            cell_type = "Number" if field.endswith("_count") and str(value).isdigit() else "String"
            cells.append(f'<Cell><Data ss:Type="{cell_type}">{html.escape(str(value))}</Data></Cell>')
        lines.append("      <Row>" + "".join(cells) + "</Row>")
    lines.extend([
        "    </Table>",
        "  </Worksheet>",
        "</Workbook>",
    ])
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="vibe_coding_builder")
    parser.add_argument("--granularity", choices=["daily", "commit"], default="daily")
    parser.add_argument("--author", default="")
    parser.add_argument("--skip-existing-deduction", action="store_true")
    parser.add_argument("--excel-out", default="")
    parser.add_argument("--seed")
    parser.add_argument("--include-private", action="store_true")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    start = parse_date(args.start)
    end = parse_date(args.end)
    if end <= start:
        raise SystemExit("--end must be after --start")

    check_gh_preflight()
    repos = run_gh_repo_list(args.account, args.include_private)
    if len(repos) <= 10:
        raise SystemExit(f"Need >10 eligible repositories, found {len(repos)}.")

    seed_value = make_seed(args.account, args.start, args.end, args.profile, args.seed)
    rng = random.Random(seed_value)
    profile = PROFILES[args.profile]

    all_days = [start + timedelta(days=i) for i in range((end - start).days)]

    rows = []
    repo_use = {repo.name: 0 for repo in repos}
    seen_paths: dict[tuple[str, str], int] = {}
    burst_count = rng.choices(*BURST_DAYS, k=1)[0]
    burst_days = set(rng.sample(all_days, min(burst_count, len(all_days))))
    for week in week_chunks(start, end):
        active_count = min(rng.choices(*profile["active_days"], k=1)[0], len(week))
        weights = [WEEKDAY_MULTIPLIER[day.weekday()] for day in week]
        active_days = set(rng.choices(week, weights=weights, k=active_count))
        while len(active_days) < active_count:
            active_days.add(rng.choice(week))
        for day in sorted(active_days):
            commits = rng.choices(*profile["commits"], k=1)[0]
            if day in burst_days:
                commits += rng.choices(*BURST_EXTRA, k=1)[0]
            repos_today = min(rng.choices(*REPOS_PER_DAY, k=1)[0], len(repos), commits)
            repo_weights = [1 / (1 + repo_use[repo.name]) for repo in repos]
            chosen_repos = rng.choices(repos, weights=repo_weights, k=repos_today)
            times = sorted(choose_time(rng, day) for _ in range(commits))
            for index in range(commits):
                repo = chosen_repos[index % len(chosen_repos)]
                append_plan_row(rows, repo_use, seen_paths, rng, repo, day, times[index])

    author = args.author or args.account
    rows, day_stats = apply_existing_commit_deduction(rows, args.account, author, args.skip_existing_deduction)

    output = Path(args.out) if args.out else None
    if args.granularity == "commit":
        fieldnames = [
            "date",
            "time",
            "repo",
            "kind",
            "task_type",
            "message",
            "path",
            "summary",
            "target_commit_count",
            "existing_commit_count",
            "planned_new_commit_count",
        ]
        output_rows = rows
        write_tsv(rows, fieldnames, output)
    else:
        fieldnames = ["date", "target_commit_count", "existing_commit_count", "planned_new_commit_count", "commit_details"]
        output_rows = build_daily_rows(rows, day_stats)
        write_tsv(output_rows, fieldnames, output)

    if args.excel_out:
        write_excel_xml(output_rows, fieldnames, Path(args.excel_out))

    print(
        f"# profile={args.profile} granularity={args.granularity} seed={seed_value} "
        f"repos={len(repos)} commits={len(rows)} author={author} existing_deduction={not args.skip_existing_deduction}"
    )


if __name__ == "__main__":
    main()
