# ADR 0003: Workflow First

## Decision
Deterministic operations use Domain, Application Services, or ordinary infrastructure services. LangGraph Agents are used only at decision points requiring reasoning, planning, risk analysis, or adaptive questioning.

## Consequences
Upload, version creation, parsing, diff, export, email, and CRUD are not Agents.