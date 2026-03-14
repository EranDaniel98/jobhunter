# ADR-001: In-Process Event Bus

## Status
Accepted

## Context
Services in JobHunter were tightly coupled - company approval directly triggered analytics updates, email sending required direct quota service calls, and resume parsing had inline notification logic. This coupling made the codebase harder to test and extend.

## Decision
Implement an in-process async event bus (`app/events/bus.py`) using a publish/subscribe pattern. Domain events (`company_approved`, `outreach_sent`, `resume_parsed`) are published by services and handled by decoupled subscribers.

## Consequences
- **Positive:** Services are decoupled; adding new event handlers doesn't require modifying publishers. Testing is simpler (mock the bus). Clear audit trail via log_event handler.
- **Negative:** In-process only - events are lost if the process crashes mid-handling. No guaranteed delivery.
- **Migration path:** Replace with Redis Pub/Sub or a message queue (RabbitMQ/SQS) for multi-worker deployments. The `EventBus` interface remains the same.
