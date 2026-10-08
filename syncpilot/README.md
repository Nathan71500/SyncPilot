# SyncPilot 0.6.5 source package

This community source snapshot provides six skills and standard-library Python helpers. It does not assert an installed release or native end-to-end reception.

- syncpilot-init: qualify a project's sources, domains, transport and destination.
- syncpilot-codex: prepare an exact Git package and check destination evidence.
- syncpilot-work: independently receive and verify a package.
- syncpilot-dc: manage the operation, transport, mission bridge and source qualification.
- syncpilot-decisions: track validated decisions and conflicts in either direction.
- syncpilot-persistence: check durable destination access independently of transport.

Start with [the transport protocol](skills/syncpilot-dc/references/PROTOCOL.md), [routing](skills/syncpilot-dc/references/FLOW.md), [technical missions](skills/syncpilot-dc/references/MISSION.md) and [current source identity](skills/syncpilot-dc/references/SOURCE.md).

Contract examples in skills/syncpilot-init/references use placeholders. Replace them only in an adopter's private project configuration. The apps manifest contains no provider bindings; use the host's supported connection workflow for your own adapters.

Python 3.10+ and Git are required for local checks. Live dispatch additionally requires supported authenticated tools, a qualified project, current authority and an independently verified destination. No perpetual service or automatic canonical Git integration is supplied.
