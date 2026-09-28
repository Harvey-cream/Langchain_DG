# ADR 0001: Product Isolation

## Decision
Contract and Interview are independent products under `products/contract` and
`products/interview`. Neither product may import the other. Code moves to
`common` only when both products actually use it; speculative shared layers are
not introduced.

Legacy Knowledge and Legacy Interview remain runnable during migration and are not templates for new Contract code.

## Consequences
New product capabilities stay inside their product directory. Shared technical
capabilities belong in `common`. `app` is only the FastAPI composition root.
