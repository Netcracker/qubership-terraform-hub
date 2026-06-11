# EC2 Stop

## Overview

Workflow [`.github/workflows/ec2-stop.yml`](../.github/workflows/ec2-stop.yml) scales down Auto Scaling Groups on a schedule (Mon–Fri at 17:00 UTC) or on manual trigger.

For EC2 **start** and shared setup, see [EC2 Start](ec2-start.md).

---

## How to use

1. Fork the repository.
2. Configure secrets and variables (same as EC2 Start — see [ec2-start.md](ec2-start.md)).
3. Set ASG names in repository variables used by the workflow:
   - `TF_VAR_Pioneer_ASG_NAME`
   - `TF_VAR_APIHUB_ONDEMAND_ASG_NAME`
   - `TF_VAR_APIHUB_SPOT_ASG_NAME`
   - `TF_VAR_ISTIO_SVT_ASG_NAME`
4. Tag ASGs to control stop behaviour:
   - **No `autostop` tag** — ASG will be stopped.
   - **`autostop=true`** — ASG will be stopped.
   - **`autostop=false`** — ASG is skipped.

---

## Manual run (dry run)

Use **Run workflow** in GitHub Actions and set **Dry run** to `true` to preview changes without scaling down ASGs.

---

## Schedule

Default cron: `0 17 * * 1-5` (17:00 UTC, Monday–Friday).
