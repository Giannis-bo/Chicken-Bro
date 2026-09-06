# SimC tools review and runtime evidence

Independent review identified and fixed missing canonical scenarios on follow-up job reads. The repository now joins owner-scoped jobs to the existing queue payload, and the application validates scenario hash plus snapshot/compiler/runtime identity. Legacy jobs without a payload remain readable with explicit missing-scenario limitations.

Final source review found no remaining must-fix. Reviewer ran 118 tests after scenario fixes, 65 final narrow tests, and 20 adapter tests for the final authorization patch, including preserving explicit prompt policies and not approving writes without a Chat context. Parent verified the source diff and exact-commit cloud backend (336 tests), control plane (62 tests), and whitespace checks.

Live validation exposed two integration details that mocks alone did not establish: MCP child environment forwarding and write-tool approval policy. Only prepare_simulation and submit_simulation receive per-tool authorization during account-scoped Chat runs; default and other tool policies are retained. Configuration reference: https://learn.chatgpt.com/docs/config-file/config-reference (mcp_servers.<id>.tools.<tool>.approval_mode).

The final native Astra/high Web Chat completed four real queue/worker jobs in 179.414 seconds. All share one public character snapshot and the logged-in owner. The model initially made four invalid scenario calls, then corrected them without creating duplicate jobs; four submissions succeeded. Each used 10,000 iterations. Actual output reports both error and provenance; the answer correctly limits inference to the tested snapshot and scenarios. Field-specific invalid-input guidance remains a possible efficiency improvement.

Manual UI verification: all four IDs appear in the existing account A SimC list; opening the five-target variant shows 546,968.139 DPS, matching Chat and persisted result. This is agent verification, not user acceptance. No production deployment, schema change, new dependency, or local SimC execution occurred.
