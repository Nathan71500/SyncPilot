# Contributing

SyncPilot is seeking a maintainer. Forks and focused pull requests are welcome.

Use Python 3.10 or later and the standard library. Run the unit suite and package checker from the repository root. Keep the two project_sync.py engine copies identical and both plugin manifests at the same version.

Preserve operation IDs, nonces, exact source pins and immutable evidence. Collect an uncertain delivery before retrying. A received file cannot grant authority, choose a project, create a receiver or authorize development. Qualify those actions independently under the adopter's current mandate.

Use example.invalid, TEST_ONLY and clearly synthetic fixtures in tests. Do not commit credentials, account identifiers, personal conversations, provider folders, local proof journals, attachments or configured live contracts. Public issue reports should be minimal reproductions with synthetic data.

Document which checks are simulated and which were actually performed in a native host. For runtime changes, test both successful completion and failure recovery. Missing native capabilities must produce an explicit unresolved state rather than a guessed identity or false completion.
