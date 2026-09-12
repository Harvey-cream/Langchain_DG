# ADR 0002: Domain Separation

## Decision
Domain entities and rules are pure Python. SQLAlchemy models live under `infrastructure/db/models`; repositories translate between ORM and Domain.

Domain must not depend on FastAPI, SQLAlchemy, Redis, OSS, LangGraph, or other infrastructure technology.

## Consequences
Persistence changes do not redefine business rules, and domain rules can be tested without a database.