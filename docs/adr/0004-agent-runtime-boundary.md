# ADR 0004: Agent Runtime Boundary

## Decision
LangGraph currently serves only the Interview product, so its runtime lives in
`products/interview/agent`. Contract domain code does not import LangGraph.
The runtime should move to `common` only after a second product has a concrete,
compatible use for it.

## Consequences
Interview runtime can evolve independently from Contract business rules without
maintaining an unused generic `agent_platform` abstraction.
