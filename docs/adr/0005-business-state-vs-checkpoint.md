# ADR 0005: Business State vs Checkpoint

## Decision
PostgreSQL business tables store users, customers, contracts, versions, clauses, changes, policies, and jobs. LangGraph Checkpoint stores only Agent execution state.

Contract versions are never represented by or recovered from a checkpoint.

## Consequences
Business history remains queryable and durable independently of Agent execution.