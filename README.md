# SyncPilot community

Experimental Python tooling for document and mission handoffs between ChatGPT Work and Codex. The original maintainer has stopped active development; contributors are welcome to fork or continue the project under the MIT license.

This is a standalone source snapshot, version 0.6.5. It is not an official OpenAI product or a hosted synchronization service. The package contains offline validators and an optional bridge using an already installed, authenticated Codex CLI.

## What it does

- Defines project-specific contracts, exact Git snapshots and independent receipts.
- Routes authorized Work ↔ Codex operations, with no redundant Work → Work or Codex → Codex handoff.
- Separates local commits from mission transfers; a synchronization request does not grant arbitrary development or Git permissions.
- Collects existing operations before retries, retaining the same operation and nonce.
- Qualifies a necessary project receiver, respecting busy actors and scoped creation authority.
- Keeps source identity, delivery, execution, document persistence and final confirmation distinct.

Desktop Commander is the primary transport. Optional provider adapters, including a Drive fallback, require the adopter's own project configuration and authenticated tools. Provider connections are deliberately unbound in this source package.

## Current conversation and branches

Version 0.6.5 adds a source qualification helper. A unique current-request marker is checked against native application inventory and the latest source turn. A copied parent turn, arbitrary title, historical URL or ambiguous marker does not qualify a conversation branch.

The external pilot authenticates those native observations. Hashes verify bytes; they do not authenticate an application or a human mandate. Work cannot discover its current chat automatically if its runtime exposes no identity tool and no authorized external pilot is running. The new helper does not create that missing capability. See [source qualification](syncpilot/skills/syncpilot-dc/references/SOURCE.md).

## Run locally

Requirements: Python 3.10+, Git, standard library only. Tests use synthetic projects and fake application observations.

    git clone https://github.com/Nathan71500/SyncPilot-community.git
    cd SyncPilot-community
    python -X utf8 -m unittest discover -s tests -v
    python -X utf8 tests/package_check.py
    python -X utf8 tools/build_package.py

The build writes a new ZIP into dist/ and refuses to replace an existing archive. Running tests or building a package does not install a plugin, connect a provider or send a mission.

The six skill entry points live under [syncpilot/skills](syncpilot/skills). Start with [the package guide](syncpilot/README.md) and the generic example contracts. Configuring live operation requires a project-specific contract, qualified access, an authorized pilot and independent destination checks.

## Status and contribution

The local Windows source suite passes 234 tests. These are simulations; they do not prove live Work → Codex reception. Windows runtime sandbox failures, native writer ownership and missing current-chat APIs remain integration dependencies. Do not remove locks, loosen permissions or invent source IDs to bypass them.

See [architecture](docs/ARCHITECTURE.md), [the roadmap](docs/ROADMAP.md) and [contribution guidance](CONTRIBUTING.md). Pull requests should include focused validation and a clear statement of any unverified native behavior.

[MIT license](LICENSE).
