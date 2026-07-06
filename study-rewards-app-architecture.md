# Study rewards app — system architecture (v1 draft)

## 1. Product summary

A mobile-first app where university/SHS students pay a small monthly subscription (~10 GHS) to join a study rewards program. Verified study sessions earn points, which convert into airtime, cash-out, or partner vouchers (restaurants, etc. — phase 2). No user-deposited money is held or refunded, which avoids Bank of Ghana custodial/deposit-taking regulatory territory.

## 2. High-level architecture

```
┌─────────────────┐
│   Student app     │  (mobile client — React Native / Flutter, or web-first PWA)
└─────────┬─────────┘
          │ HTTPS / REST (JWT auth)
          ▼
┌─────────────────────────────────────┐
│           Backend API (FastAPI)        │
│  ┌───────────┐  ┌──────────────────┐  │
│  │   Auth    │  │  Study sessions   │  │
│  │           │  │  (timer + anti-   │  │
│  │           │  │   cheat checks)   │  │
│  └───────────┘  └──────────────────┘  │
│  ┌───────────┐  ┌──────────────────┐  │
│  │  Rewards  │  │  Subscriptions &  │  │
│  │  engine   │  │    payments       │  │
│  └───────────┘  └──────────────────┘  │
└──────────┬───────────────┬────────────┘
           │                │
           ▼                ▼
   ┌───────────────┐  ┌──────────────────────────┐
   │  PostgreSQL   │  │   External services       │
   │  (core data)  │  │  Paystack / MTN MoMo API   │
   └───────────────┘  │  Airtime API (e.g. Hubtel) │
                       │  Ad network (AdMob)        │
                       └──────────────────────────┘
```

## 3. Core backend modules

### 3.1 Auth service
- Standard email/phone + password or OTP-based signup, JWT access + refresh tokens (you've already built this pattern for the attendance system).
- Roles: `student`, `admin` (for you to manage the platform/reward budget).
- Ghana-specific: phone-number-based signup is likely more natural than email for SHS students — worth considering as primary identifier.

### 3.2 Study session service (the risky, important part)
Responsible for starting/pausing/ending a study session and running anti-cheat checks concurrently.

**Suggested v1 verification stack (combine, don't rely on one signal):**
1. **App-foreground lock** — timer pauses automatically if the app goes to background or the screen locks.
2. **Random attention checks** — every 5–10 min (randomized so it can't be predicted), a prompt appears requiring a tap within ~15 seconds, or a 1-question recall check about the material.
3. **End-of-session proof** — a short typed summary of what was studied, or a photo of notes/textbook. (Optional: quick LLM check that a summary plausibly relates to a stated subject — nice-to-have, not required for v1.)
4. **Session data logged** as a full audit trail (start time, pause events, check-response times) — this also gives you real usage data to tune the anti-cheat logic later.

Leave out camera-based monitoring for v1 — it's a heavier lift, raises real privacy concerns for a youth-focused app, and the combination above already covers most gaming vectors.

### 3.3 Rewards engine
- Verified session minutes convert to points via a configurable rate (e.g. 1 point / verified minute).
- Daily/weekly caps to control payout costs and discourage burnout-style abuse.
- Streak bonuses (multiplier for consecutive days hitting a personal goal) — this is a strong dopamine lever and costs you nothing extra to build on top of the ledger.
- Points redemption: airtime (via aggregator API), cash-out (mobile money payout), or vouchers (phase 2 partnerships). Avoid random/chance-based payouts (raffles, lucky draws) since that edges into lottery regulation — keep rewards merit-based.

### 3.4 Subscriptions & payments
- Monthly subscription (~10 GHS) via Paystack or MTN MoMo API — handles recurring billing.
- Ad-supported free tier: 30-second ad required to start a session (AdMob rewarded ads are a natural fit).
- This module is also where reward payouts go out (airtime top-up API, MoMo disbursement).

## 4. Data model (draft)

```
users
  id, phone, email, password_hash, role, created_at

subscriptions
  id, user_id (FK), status, plan, started_at, expires_at, provider_ref

study_sessions
  id, user_id (FK), started_at, ended_at, status (active/completed/flagged),
  verified_minutes, subject_tag

session_checks
  id, session_id (FK), check_type (attention/photo/summary), triggered_at,
  responded_at, passed (bool)

reward_ledger
  id, user_id (FK), session_id (FK, nullable), points, reason, created_at

redemptions
  id, user_id (FK), points_spent, reward_type (airtime/cash/voucher),
  status, provider_ref, created_at
```

This maps cleanly to SQLAlchemy models — same pattern you used for the attendance system (users, tokens, audit log) and the invoice project (Alembic migrations).

## 5. Suggested tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI + SQLAlchemy + Alembic | Matches your existing stack and experience |
| DB | PostgreSQL | Handles concurrent writes (session checks) better than SQLite at scale |
| Auth | JWT (access + refresh) | You've already built this |
| Payments | Paystack or MTN MoMo API | Both have Ghana-ready sandbox APIs |
| Airtime payout | Hubtel or similar aggregator | Single API for multi-network airtime top-up |
| Ads | Google AdMob (rewarded ads) | Standard for mobile, works well with a "watch to unlock" flow |
| Mobile client | Flutter or React Native | Cross-platform, single codebase for Android-first Ghanaian market |
| Hosting | Railway/Render (MVP) → AWS/GCP later | Cheap to start, easy to scale later |

## 6. Phased roadmap

**Phase 1 (MVP):**
- Auth, study session tracking with anti-cheat v1 (app-lock + attention checks), points ledger, airtime redemption only.
- Free tier with ads; no subscription yet — validate the core loop first.

**Phase 2:**
- Subscription billing, ad-free tier, streak bonuses, admin dashboard for monitoring reward budget.

**Phase 3:**
- Restaurant/partner vouchers, cash-out via MoMo, richer anti-cheat (ML-based session-summary validation), leaderboards (non-cash, bragging rights only).

## 7. Open questions to resolve before building
- Android-only for v1, or web-first PWA to move faster given your backend-heavy skill set?
- What's the minimum viable "verified minute" — do all four anti-cheat signals apply from day one, or start with 2 and layer in more?
- Reward budget model — fix a per-user monthly reward cap so payouts never exceed subscription + ad revenue?
