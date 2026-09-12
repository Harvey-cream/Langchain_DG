# ADR 0004: Agent Runtime Boundary

## Decision
LangGraph is an execution implementation behind the Platform Agent Runtime. The repository package is named `agent_platform` rather than `platform` because Python's standard library already owns the top-level `platform` module. Product Domain does not import LangGraph. Product workflows depend on runtime ports or adapters rather than graph implementation details.

## Consequences
Agent runtime can evolve independently from Contract business rules.