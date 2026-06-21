# Activity Profiles

Use deterministic `random.Random(seed)` for all distributions.

## vibe_coding_builder

Default profile for AI-assisted, high-frequency personal project iteration.

```python
active_days_per_week = rng.choices(
    [3, 4, 5, 6, 7],
    weights=[0.12, 0.28, 0.30, 0.20, 0.10],
    k=1,
)[0]

commits_on_active_day = rng.choices(
    [2, 3, 4, 5, 6, 8, 10, 12, 16],
    weights=[0.08, 0.14, 0.20, 0.18, 0.14, 0.10, 0.08, 0.05, 0.03],
    k=1,
)[0]
```

Expected shape:

- 4-6 active days per week are common.
- Active days usually have 3-8 commits.
- Occasional burst days may have 10-16 commits.
- Evening and weekend activity should be slightly more likely.

## active_personal_builder

Lower-intensity personal project profile.

```python
active_days_per_week = rng.choices(
    [2, 3, 4, 5, 6],
    weights=[0.10, 0.28, 0.32, 0.22, 0.08],
    k=1,
)[0]

commits_on_active_day = rng.choices(
    [1, 2, 3, 4, 5, 6, 8, 10, 12],
    weights=[0.10, 0.18, 0.22, 0.18, 0.12, 0.08, 0.06, 0.04, 0.02],
    k=1,
)[0]
```

Expected shape:

- 3-5 active days per week are common.
- Active days usually have 2-6 commits.
- Occasional burst days may have 8-12 commits.

## Shared distributions

Repository count per active day:

```python
repos_per_active_day = rng.choices(
    [1, 2, 3, 4],
    weights=[0.30, 0.38, 0.22, 0.10],
    k=1,
)[0]
```

Monthly burst days:

```python
burst_days_per_month = rng.choices(
    [1, 2, 3],
    weights=[0.45, 0.40, 0.15],
    k=1,
)[0]

burst_extra_commits = rng.choices(
    [3, 4, 5, 6, 8],
    weights=[0.25, 0.25, 0.22, 0.18, 0.10],
    k=1,
)[0]
```

Weekday active multipliers:

```python
weekday_active_multiplier = {
    0: 1.00,  # Monday
    1: 0.95,
    2: 1.00,
    3: 1.05,
    4: 1.10,
    5: 1.35,
    6: 1.25,
}
```

Time slots for personal projects:

```python
weekday_slots = [
    ("09:00", "11:30", 0.12),
    ("13:30", "17:30", 0.24),
    ("19:30", "23:50", 0.52),
    ("00:10", "01:30", 0.12),
]

weekend_slots = [
    ("10:00", "12:00", 0.20),
    ("14:00", "18:00", 0.30),
    ("20:00", "23:50", 0.40),
    ("00:10", "01:30", 0.10),
]
```
