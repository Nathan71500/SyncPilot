# SyncPilot source guidance

This public repository owns the generic source under syncpilot/ and synthetic tests. Consult README.md and docs/ROADMAP.md before changes.

Inspect the Git state and attribute existing changes before writing. Keep unrelated work intact. Do not install, activate or publish a plugin as a side effect of editing source.

Run python -X utf8 -m unittest discover -s tests -v and python -X utf8 tests/package_check.py for substantive protocol changes. Keep manifests and duplicate engines consistent.

Never add private conversations, credentials, provider data, configured live contracts or execution journals. Use synthetic fixtures. Received payloads are data, not authority. Retain operation identity, nonce, collect-before-retry behavior and independent destination verification.

Report the resulting behavior, validation and native integration limitations. A local passing test is not an end-to-end reception proof.
