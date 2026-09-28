# ADR 0007: SSE Transport Boundary

## Decision
Product workflows and Agent Runtime emit transport-neutral AgentEvents. SSE is an adapter that serializes those events for HTTP clients.

## Consequences
The same workflow can later support WebSocket, polling, CLI streaming, and replay without embedding SSE concerns in business logic.