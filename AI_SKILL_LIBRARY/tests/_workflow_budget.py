"""How many active workflow files this repository allows, stated once.

Two tests asserted this number independently - `test_v4_consolidation` and
`test_retired_workflow_archive_image_v2` - both with a literal `120`. I raised
one of them and CI found the other, which is the whole argument for this file:
a rule written down twice is a rule that will be half-changed.

The budget is housekeeping, not a safety property. It stops retired one-shot
lanes accumulating in the active workflow directory. Retired definitions now
live only in Git history; `.github/workflows-archive/` is a tombstone README.
It was raised from 120 to 121 to make room for
`.github/workflows/production-golden-e2e.yml`, the free ephemeral worker that
runs the canonical golden chain and is where this repository's semantically
verified golden evidence now comes from - the thing that takes a personal
computer off the production path.

Before raising it I looked for a lane to retire in exchange and found none:
every active workflow's push trigger names a branch that still exists on the
remote. Earlier in this branch I refused to raise this same number; that refusal
was right, because raising it then would have dodged a problem rather than paid
for a capability.

It was raised again, from 121 to 122, to make room for
`.github/workflows/deploy-portable-runtimes.yml`, the zero-cost portable runtime
lane added by the Railway exit. Before raising it I ran the same check as last
time - every active workflow's push trigger against the branches that actually
exist on the remote - and again found zero retirable lanes, so there was nothing
to trade. The Railway exit removed `.github/scripts/railway_deploy_latest.py`
and both Railway production jobs, but those lived inside an existing workflow
file, so they freed no slot.

To restore a hard 120: retire an active lane to Git history and set this back.
"""

ACTIVE_WORKFLOW_BUDGET = 122
