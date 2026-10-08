# Current source conversation and forks

The source is the conversation emitting the current request. A fork has its own
ID. A parent URL, copied transcript, title or latest updated chat is insufficient.

When the source cannot introspect its identity, use the external pilot's native
application inventory/readback. Do not ask for a human URL by default when the
authorized running pilot already has that capability.

## Public offline helper

Issue one challenge for the current request under the qualified project's
transport .authority directory, outside the canon and received operations:

    python SOURCE issue --contract CONTRACT --canonical-root CANON --authority-root AUTHORITY --environment work --request-sha256 REQUEST_SHA256 --output NEW_CHALLENGE

The source agent reads and emits the exact returned SYNCPILOT-SOURCE:<nonce>
marker on its own line in its current source turn. On resume, reuse the challenge.
This discovery step neither sends a mission nor authorizes a replay.

The external pilot retains actual native tool payloads in a new observation:

- format: SYNCPILOT-SOURCE-OBSERVATION; schema_version: 1.
- environment, project_id, nonce: bound to the challenge and qualified contract.
- observed_at: fresh UTC time; tool_reference: authenticated tool provenance.
- listing: actual list_threads payload with threads and pinnedThreads.
- readings: actual read_thread JSON payloads for candidate conversations.

After independent readback and SHA-256 checks of both files:

    python SOURCE qualify --contract CONTRACT --canonical-root CANON --authority-root AUTHORITY --request-sha256 REQUEST_SHA256 --challenge CHALLENGE --challenge-sha256 SHA64 --observation OBSERVATION --observation-sha256 SHA64 --authority-reference MANDATE --output NEW_SOURCE

The new source file uses the existing five actor fields. The helper matches an
exact, unique marker in the latest native agent turn, checks project/environment,
and rejects a turn predating the fork's creation. User quotes, older turns,
expired observations and ambiguous matches do not substitute for source identity.
No authority or mission format is weakened.

JSON and hashes do not authenticate the application or human mandate. The pilot
performs that external check. The helper grants no message, creation or execution
permission. It does not invoke an API or inspect credentials.

## Capability boundary

The helper cannot add a missing Work runtime tool or wake an inactive Codex
pilot. Discovery is automatic only inside an authorized running pilot with native
application access. If neither introspection nor that external capability exists,
retain SOURCE_QUALIFICATION_REQUIRED rather than inventing a parent identity.

Source identity, delivery, execution and confirmation remain separate checks.
A service quota or Windows execution failure is not source identity evidence.
Offline tests never establish end-to-end native reception.
