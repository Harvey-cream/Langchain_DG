# ADR 0006: Durable Background Jobs

## Decision
PDF, email, document processing, embedding, and evaluation work must be submitted through a Queue/Worker boundary. `asyncio.create_task()` is not a durable-job mechanism for new product code.

Phase 1 defines ports, messages, status, retry metadata, and a Redis adapter boundary only.

## Consequences
Workers can be retried, observed, and resumed without coupling product code to a process lifetime.