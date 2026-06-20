---
name: sobench-repair
description: Diagnose a failing smoke attempt and make a targeted fix to driver.py. Use when smoke final_status is a failure.
---

# repair

Fix the driver to meet the output contract. Never relax the contract.

## Steps

1. Read `methods/<M>/driver_record.json`: `attempts[-1].stderr` and
   `attempts[-1].validation_failures`.
2. Read the relevant method repo source to understand the specific API failure
   (wrong function name, a missing preprocessing call, a shape/key mismatch).
3. Make a **targeted edit** to `driver.py` addressing that failure — not a rewrite.
4. Re-run the **smoke** skill; read the updated `driver_record.json`.
5. If `repair_count >= 3` and still failing: write `methods/<M>/blocked.md`
   explaining the failure (last stderr + what you tried), and move to the next
   method. The 3-attempt limit is yours to enforce; sobench always records.

Never edit the 7-check contract, `run_benchmark.py`, or any sobench module to make
a driver pass. Fix the driver.
