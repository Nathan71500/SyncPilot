# Roadmap for a new maintainer

## Current-chat discovery

Implement a supported adapter that observes the exact current source conversation and native turn. Preserve fork identity, reject inherited parent turns and keep ambiguity explicit. Provide a real native test for both a newly created fork and the parent. The offline source helper and its adversarial simulations are already present; automatic bootstrap from a Work runtime without identity tools is not solved.

## Native receiver lifecycle

Qualify writer ownership through supported application tools. Collect existing results before attempting a resume or replacement. Preserve active actors, previous receipts and operation history. Exercise native channel loss, stale availability and writer conflicts without removing locks or changing global permissions.

## Windows execution

Reproduce sandbox and application-server startup failures with a minimal isolated command. Record the exact host/CLI version and phase. Validate compatibility after the host issue is repaired; source validation alone cannot establish native reception.

## Performance

Measure discovery, package creation, hashing, dispatch and independent confirmation separately. Reduce repeated Git reads and provider round trips while preserving integrity checks. Use tests/benchmark_performance.py with synthetic data. An elapsed timeout never establishes delivery or completion.

## Receiver size

Measure context growth, replay cost and latency after repeated missions. Retain durable evidence outside the chat and qualify renewal only after terminal completion. Test continuity across replacement and prevent duplicate receivers during pending setup.

## Release readiness

Connect providers in the adopter's own environment, qualify the project and run independent native Work → Codex and Codex → Work recipes. Keep simulation results distinct from those native proofs. This snapshot has no active hosting or installed-release guarantee.
