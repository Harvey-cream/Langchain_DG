# ADR 0002: Domain Separation

## Decision
Domain entities and rules are pure Python. Contract SQLAlchemy models are
collected in `products/contract/models.py`; Interview SQLAlchemy models are
collected in `products/interview/models.py`. Simple HTTP-only persistence code
may live directly beside the product API. Complex persistence shared by a
product's API and background jobs lives in that product's `db.py`.

Domain must not depend on FastAPI, SQLAlchemy, Redis, OSS, LangGraph, or other infrastructure technology.

## Consequences
Persistence changes do not redefine business rules, and domain rules can be
tested without a database. This keeps useful domain boundaries without creating
one file or adapter per entity.
