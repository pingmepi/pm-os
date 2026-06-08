---
name: pm-status
description: Display the current state of a PM-OS project — stage statuses, recent events, and feedback count.
---

# Role and goal

You are displaying a concise, human-readable project status dashboard. Read `.meta.yaml` and `telemetry.jsonl` from the current project and print structured output.

# Steps

1. **Resolve project root** — find the nearest parent directory containing `.meta.yaml` from CWD. If not found, print "Not inside a PM-OS project." and stop.

2. **Load `.meta.yaml`** and `telemetry.jsonl`.

3. **Print the status block** in this exact format:

```
Project: <project_slug>
Created: <created_at>  GenAI: <yes/no>  PM-OS version: <pm_os_version>

Stages:
  01 Brief              [<status>]  <hash_summary>  <approval_age>
  02 Scope              [<status>]
  03 PRD                [<status>]
  04 Design Spec        [<status>]
  05 Prototype Brief    [<status>]
  06 QA Plan            [<status>]
  07 Metrics Plan       [<status>]

Recent events:
  <last 5 telemetry events, human-formatted>

Feedback captured: <count of lines in feedback.jsonl>
Telemetry events:  <count of lines in telemetry.jsonl>
```

4. **For each stage row**, include:
   - Status in brackets: `[approved]`, `[draft]`, `[edited]`, `[stale]`, `[pending]`
   - If `approved`: show `approved <N>h ago` or `approved <N>m ago` based on `approved_at`
   - If `edited`: show `edited since approval`
   - If `stale`: show `stale — upstream changed`
   - If `draft`: show `draft — awaiting approval`
   - If `pending`: no extra detail

5. **Recent events** — read the last 5 lines from `telemetry.jsonl`, parse each JSON line, and print:
   ```
   <timestamp_short>  <event_type>  stage=<stage>  <key payload field if relevant>
   ```

6. **Count lines** in `feedback.jsonl` (skip blank lines) for the feedback count.

# Implementation

Run this Python block to gather all data, then format and print:

```bash
python3 -c "
import sys, json
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, '$HOME/.pm-os/lib')
from project import resolve_project, load_meta, STAGE_NAMES

root = resolve_project()
meta = load_meta(root)

print('Project:', meta['project_slug'])
genai = 'yes' if meta.get('genai_flag') else 'no'
print(f'Created: {meta[\"created_at\"]}  GenAI: {genai}  PM-OS version: {meta[\"pm_os_version\"]}')
print()
print('Stages:')

stage_labels = {
    '01': 'Brief', '02': 'Scope', '03': 'PRD',
    '04': 'Design Spec', '05': 'Prototype Brief',
    '06': 'QA Plan', '07': 'Metrics Plan',
}
now = datetime.now(timezone.utc)
for s in meta['stages']:
    label = stage_labels[s['id']].ljust(18)
    status = s['status']
    detail = ''
    if status == 'approved' and s.get('approved_at'):
        try:
            t = datetime.fromisoformat(s['approved_at'])
            diff = int((now - t).total_seconds())
            age = f'{diff // 3600}h ago' if diff >= 3600 else f'{diff // 60}m ago'
            detail = f'  approved {age}'
        except Exception:
            pass
    elif status == 'edited':
        detail = '  edited since approval'
    elif status == 'stale':
        detail = '  upstream changed'
    elif status == 'draft':
        detail = '  awaiting approval'
    print(f'  {s[\"id\"]} {label} [{status}]{detail}')

# Recent events
tpath = root / 'telemetry.jsonl'
events = []
if tpath.exists():
    lines = [l.strip() for l in tpath.read_text().splitlines() if l.strip()]
    events = lines[-5:]
print()
print('Recent events:')
for ev in events:
    try:
        e = json.loads(ev)
        ts = e['timestamp'][:16].replace('T', ' ')
        stage = e.get('stage') or '-'
        print(f'  {ts}  {e[\"event_type\"]}  stage={stage}')
    except Exception:
        pass
if not events:
    print('  (none)')

# Counts
fpath = root / 'feedback.jsonl'
fc = len([l for l in fpath.read_text().splitlines() if l.strip()]) if fpath.exists() else 0
tc = len(events)
if tpath.exists():
    tc = len([l for l in tpath.read_text().splitlines() if l.strip()])
print()
print(f'Feedback captured: {fc} entries')
print(f'Telemetry events:  {tc}')
"
```
