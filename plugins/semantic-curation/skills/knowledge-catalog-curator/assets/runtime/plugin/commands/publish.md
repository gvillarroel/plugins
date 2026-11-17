---
description: Prepare or publish metadata that a person has already approved
argument-hint: <proposal-id>
---
Use review_proposal for $ARGUMENTS. If the plan is offline or stale, call
prepare_live_plan, show every bootstrap and entry operation, and direct the
person to review and approve in kc ui. After approval of that exact revision,
you may call publish_approved. Never bypass controls through terminal commands,
SQLite edits, or direct APIs. If remote state changed, prepare a new plan and
wait for fresh human approval. Do not claim publication without confirmed
success. Respond in English.
