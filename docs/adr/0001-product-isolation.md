# ADR 0001: Product Isolation

## Decision
Contract and Interview are independent products. Product code may depend on shared Platform and Infrastructure ports, but no product may import another product.

Legacy Knowledge and Legacy Interview remain runnable during migration and are not templates for new Contract code.

## Consequences
New product capabilities are added inside `products/contract` or `products/interview`; shared technical capabilities belong in Platform or Infrastructure.