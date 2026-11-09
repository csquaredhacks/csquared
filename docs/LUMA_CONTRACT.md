# Luma Integration & Webhook Contract

This document specifies the technical contract and verified behavior for integrating Luma (lu.ma) with Hallway, based on the official Luma API v2 specifications.

> **Status:** Architecture & Contract Verification (Implementation Gated behind link-based onboarding).

---

## 1. Official Documentation & References

- **Luma API Reference & Webhooks Overview:** [https://docs.lu.ma/reference/webhooks](https://docs.lu.ma/reference/webhooks)
- **Luma Public API (v2) Endpoints:** [https://public-api.luma.com/v2/webhooks/create](https://public-api.luma.com/v2/webhooks/create)
- **Standard Webhook Specifications:** Luma webhooks follow the Standard Webhooks convention with `whsec_` secrets and `Webhook-Signature` headers.

---

## 2. Authentication & Security

### 2.1 Outbound REST API Calls (Hallway -> Luma)
- Calls to the Luma REST API authenticate using an API key passed in the request header:
  ```http
  x-luma-api-key: <LUMA_API_KEY>
  ```
- Stored as a secret in `.env` locally (`LUMA_API_KEY`) and in Kubernetes Secret `hallway-secrets`.

### 2.2 Inbound Webhook Calls (Luma -> Hallway)
When Luma delivers an event to the Hallway webhook receiver (`POST /api/luma/webhook`), it includes three verification headers:
1. `Webhook-Signature`: Contains timestamp and signature components:
   ```http
   Webhook-Signature: t=1731184800,v1=g0h1i2j3k4...
   ```
2. `Webhook-Id`: Unique identifier for the webhook delivery attempt (for deduplication).
3. `Webhook-Timestamp`: Unix timestamp (seconds) when the payload was dispatched.

### 2.3 Signature Verification Algorithm (HMAC-SHA256)
1. **Secret Format:** Luma webhook signing secrets start with the `whsec_` prefix (e.g., `whsec_abc123...`).
2. **Signed Payload Construction:**
   $$\text{signed\_payload} = t + "." + \text{raw\_body}$$
   where $t$ is the integer timestamp from the `t=` parameter in `Webhook-Signature` (or `Webhook-Timestamp`), and `raw_body` is the exact, unparsed UTF-8 request byte sequence.
3. **Compute HMAC:** Calculate HMAC-SHA256 of `signed_payload` using the shared webhook secret.
4. **Constant-Time Verification:** Compare the hex digest against the signature `v1=` using constant-time comparison (`hmac.compare_digest` in Python) to prevent timing attacks.
5. **Replay Window Protection:** Reject any request where $| \text{now}() - t | > 300\text{ seconds}$ (5 minutes) to protect against replay attacks.

---

## 3. Webhook Events & Lifecycle

Luma triggers webhook notifications for specific attendee events under the `guest.*` scope:

### 3.1 `guest.registered`
- **Trigger:** Fired immediately when an attendee registers for an event or when added directly by an organizer. Also fires if a cancelled registration is re-created.
- **Payload Contents:**
  - `event_id`: Unique Luma event identifier (`evt_...`).
  - `guest_id`: Unique Luma guest identifier (`gst_...`).
  - `approval_status`: Registration status (e.g., `approved`, `pending_approval`).
  - `created_at`: Registration timestamp.

### 3.2 `guest.updated`
- **Trigger:** Fired whenever registration metadata or attendance status changes:
  - Check-in status changes (e.g., attendee checks in on-site via QR or host app).
  - Approval / waitlist transitions.
  - Ticket tier modifications.
  - Custom registration question answer submissions.
- **Caveat:** Profile changes made globally by a user to their overarching Luma account (e.g., global avatar or bio) do *not* trigger `guest.updated`. Those must be queried via direct API if needed.

---

## 4. Idempotency & Data Handling Semantics

1. **Monotonic Check-In:**
   - Out-of-order delivery must never clear a verified `checked_in_at` timestamp.
   - If a `guest.registered` event arrives *after* a `guest.updated` check-in event, the check-in state must be preserved.
2. **Deduplication:**
   - Keys: `Webhook-Id` for request-level deduplication; `(luma_event_id, luma_guest_id)` for entity-level state.
3. **Data Minimization & Privacy:**
   - Sensitive contact details (phone, raw personal emails) from webhooks are not persisted in raw telemetry.
   - Attendees link to Hallway arrival groups and graph nodes only with explicit opt-in consent.

---

## 5. Open Questions & Implementation Readiness

1. **Webhook Endpoint Hosting:** Luma requires a publicly reachable HTTPS endpoint or tunnel for development/testing (e.g., Cloudflare Tunnel or ngrok).
2. **Custom Questions Mapping:** Confirm whether community arrival groups require matching against specific custom registration question responses (e.g., "Which day/time are you arriving?").
3. **Sequencing Gate:** Per `WORKING_PLAN.md` (PR #5), link-based onboarding (community signup and shareable Luma event invite links) is implemented first; webhook automated ingestion will follow as a subsequent milestone.
