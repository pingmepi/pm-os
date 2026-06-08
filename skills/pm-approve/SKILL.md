---
name: pm-approve
description: Approve the current draft for a given stage, compute content hash, update state, and cascade staleness.
args:
  - name: stage_id
    description: Two-digit stage number (e.g. "01", "02")
---

# Role and goal

You are approving a PM-OS stage artifact. This locks the content hash, transitions the stage to `approved`, cascades staleness to downstream stages, and pushes telemetry.

# Steps

1. **Resolve project root** — find the nearest parent directory containing `.meta.yaml` from CWD. If not found, error.

2. **Determine artifact path** from stage ID:
   | Stage | File |
   |-------|------|
   | 01 | `01-brief.md` |
   | 02 | `02-scope.md` |
   | 03 | `03-prd.md` |
   | 04 | `04-design-spec.md` |
   | 05 | `05-prototype-brief.md` |
   | 06 | `06-qa-plan.md` |
   | 07 | `07-metrics-plan.md` |

3. **Read current status** from artifact frontmatter. If status is already `approved`, print "Stage <NN> is already approved. No action taken." and stop.

4. **If status is `pending`**, print "Stage <NN> has not been generated yet. Run /pm-stage-<NN>-<name> first." and stop.

5. **Compute content hash and approval metadata** by running:
   ```bash
   python3 -c "
   import sys, json
   from datetime import datetime, timezone
   sys.path.insert(0, '$HOME/.pm-os/lib')
   from hashing import hash_artifact_body
   from pathlib import Path
   h = hash_artifact_body('<artifact_path>')
   ts = datetime.now(timezone.utc).isoformat()
   print(json.dumps({'hash': h, 'ts': ts}))
   "
   ```

6. **Update artifact frontmatter** — set:
   - `status: approved`
   - `approved_at: <timestamp>`
   - `approved_by: <PM_OS_USER>`
   - `content_hash: <computed hash>`

   Use the Python lib:
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from frontmatter import update_status
   import os
   update_status('<artifact_path>', 'approved',
       approved_at='<timestamp>',
       approved_by=os.environ.get('PM_OS_USER', 'unknown'),
       content_hash='<hash>')
   "
   ```

7. **Update `.meta.yaml`** — for the approved stage:
   - Set `status: approved`
   - Set `approved_at: <timestamp>`
   - Set `content_hash: <hash>`
   - Set `upstream_hashes_at_approval` to a map of all upstream stage IDs → their current `content_hash` values from `.meta.yaml`

   Run:
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from pathlib import Path
   from project import load_meta, save_meta, get_stage, upstream_stage_ids
   root = Path('.')
   meta = load_meta(root)
   stage = get_stage(meta, '<stage_id>')
   stage['status'] = 'approved'
   stage['approved_at'] = '<timestamp>'
   stage['content_hash'] = '<hash>'
   upstream = {uid: get_stage(meta, uid)['content_hash'] for uid in upstream_stage_ids('<stage_id>')}
   stage['upstream_hashes_at_approval'] = upstream
   save_meta(meta, root)
   "
   ```

8. **Log `stage_approved` event:**
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.pm-os/lib')
   from pathlib import Path
   from telemetry import log
   log('stage_approved', Path('.'), '<stage_id>', {
       'approved_hash': '<hash>',
       'generated_hash': '<generated_hash from frontmatter>',
       'char_edit_distance': None,
       'normalized_edit_distance': None,
       'semantic_distance': None,
       'time_to_approve_seconds': None,
       'regeneration_count': <regeneration_count from meta>,
       'implicit_reapproval': False,
   })
   "
   ```

9. **Run post-approve hook:**
   ```bash
   PM_OS_STAGE=<stage_id> python3 ~/.pm-os/hooks/post-approve.py
   ```

10. **Ask PM:** "Capture feedback for stage <NN>? [y/n]" — if yes, invoke `/pm-feedback <stage_id>`.

11. **Print confirmation:**
    ```
    Stage <NN> approved.
    Content hash: <hash>
    Downstream stages that are now stale: <list or "none">
    ```

# Notes

- If `PM_OS_USER` is not set, use "unknown".
- If the post-approve hook fails, warn but do not block — approval is complete.
- Skip distance metrics for Phase 1 (set to null in telemetry).
