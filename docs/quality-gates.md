# Quality Gates

Quality gates control whether an agent's output is good enough to proceed to the next
agent in the pipeline.

## Gate Evaluation Rules

Gates are evaluated in strict priority order. The first matching condition wins.

```
1. needs_human == true
   → FAIL — escalate to human immediately

2. status == "stop"
   → FAIL — pipeline halted, stop_reason logged

3. status == "blocked" AND fail_on_blocked == true
   → FAIL — blocked in strict mode

4. quality_score < effective_threshold
   → FAIL — quality insufficient

5. no next agent defined (non-terminal agent)
   → FAIL — orchestrator configuration error

6. Otherwise
   → PASS — advance to next_agent
```

## Effective Quality Threshold

```
effective_threshold = max(orchestrator.quality_threshold, config.min_quality)
```

The `--min-quality` CLI flag raises (but cannot lower) the orchestrator's built-in threshold.

**Default:** `8/10` — meaning scores of 8, 9, and 10 pass; 7 and below require revision.

## Next Agent Resolution

When a gate passes, the next agent is determined by:

1. `outcome.recommended_next_agent` — if it's in the `allowed_handoffs` for the current agent
2. First entry in `allowed_handoffs[current_agent]` — default fallback
3. `None` — if the current agent is a terminal agent

## Stopping Criteria

| Condition | Trigger | Final Status |
|-----------|---------|--------------|
| Terminal agent passed | Gate passes for a terminal agent | `success` |
| Max rounds | `round_number > max_rounds` | `failed` |
| No progress | Quality unchanged for `max_no_progress` rounds | `failed` |
| Repeated block | `status == blocked` for ≥2 rounds | `blocked` |
| Human required | `needs_human == true` | `blocked` |
| Stop signal | `status == stop` | `failed` |
| Validation failure | Invalid JSON output × 2 | `failed` |

## CLI Overrides

```bash
vguild orchestrators run hotfix --task "..." \
  --min-quality 9 \        # Raise quality bar (default: 8)
  --max-rounds 5 \         # Limit total rounds (default: 10)
  --max-no-progress 1 \    # Fail faster on stall (default: 2)
  --fail-on-blocked        # Treat blocked as hard failure
```

## Examples

### Gate Pass

```json
{
  "passed": true,
  "reason": "Quality score 9/10 meets threshold 8/10",
  "quality_score": 9,
  "confidence_score": 8,
  "next_agent": "implementer",
  "override_applied": false
}
```

### Gate Fail — Quality

```json
{
  "passed": false,
  "reason": "Quality score 6/10 is below threshold 8/10",
  "quality_score": 6,
  "confidence_score": 5,
  "next_agent": null,
  "override_applied": false
}
```

### Gate Fail — Human Required

```json
{
  "passed": false,
  "reason": "Agent requires human intervention",
  "quality_score": 10,
  "confidence_score": 9,
  "next_agent": null,
  "override_applied": false
}
```
