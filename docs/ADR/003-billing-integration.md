# ADR-003: Stripe Billing Integration

## Status
Accepted

## Context
JobHunter needs a billing system to monetize the platform with three tiers: Free, Pro ($29/mo), and Enterprise ($99/mo). Each tier has different quota limits for emails, company research, and other AI operations.

## Decision
Integrate Stripe for payment processing:
- **Checkout Sessions** for subscription creation
- **Customer Portal** for self-service billing management
- **Webhooks** for subscription lifecycle events (created, updated, deleted)
- **Plan-aware quotas** - the existing quota service reads the candidate's `subscription_tier` to determine limits

Billing state is stored on the `Candidate` model: `stripe_customer_id`, `subscription_tier`, `subscription_status`.

## Consequences
- **Positive:** Industry-standard payment processing. Self-service billing management via Stripe Portal. Webhook-driven state updates ensure consistency.
- **Negative:** Dependency on Stripe. Webhook delivery is eventually consistent (short delay between payment and tier update).
- **Mitigation:** Stripe webhook retry policy (up to 3 days). Manual tier override in admin panel for edge cases.
