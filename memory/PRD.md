# CORZAAR (IMS) — Product Requirements

## Problem statement
Complete Institute Management System per README: students discover + buy courses, merchants list + sell + track batches, admins govern everything with a refined ocean-navy + mint design.

## Personas
- **Student** — discovers, enrolls, pays (Stripe), applies coupons/referral codes, uses wallet balance, rates, self-marks curriculum, downloads certificate, requests refunds
- **Merchant / Institute** — lists courses, creates batches with auto-generated sessions + Zoom/Meet URLs, marks per-session attendance, creates coupons (admin approves), sees earnings + payout history
- **Admin** — approves institutes/courses/coupons, handles refunds, records payouts, reviews audit log of every action

## Core features
### Payments (Stripe)
- Hosted Stripe checkout via Emergent `emergentintegrations` adapter (INR, cards; UPI when dashboard enables it)
- Server-computed final amount = fees − coupon discount − wallet credit
- Webhook + status polling reconcile enrollment as `active` on paid

### Coupons + Referrals + Wallet
- Merchant creates coupon → admin approves → student applies at checkout
- Every student gets a unique referral code; friend uses it → 10% off + referrer earns ₹200 wallet credit on paid enrollment
- Wallet balance spendable at checkout via `use_wallet` toggle

### Curriculum progress + Certificates
- Student self-marks each curriculum item done
- On 100% complete → certificate auto-issued with unique ID + notification
- HTML certificate served at `/api/me/enrollments/{id}/certificate` (Bearer header or `?auth=` query for browser download)

### Batches with auto-sessions
- On batch create, sessions auto-generate from weekly schedule between start/end dates (capped 60)
- Merchant can add/remove individual sessions
- Attendance marked per session per student (present/absent); UI shows a session picker + per-student toggles

### Ratings
- Only enrolled+active students can rate courses/institutes; ratings + reviews_count auto-recalculate

### Refunds
- Student requests from Profile; admin approves/rejects → enrollment marked `refunded`

### Instructor payouts (manual tracking preview)
- Admin sees per-merchant gross/paid/pending ledger
- Records manual payouts (bank_transfer, UTR reference) → written to audit log
- Merchant sees own earnings + history
- Path to Stripe Connect after deploy with live keys

### Admin oversight
- Institutes / Courses / Coupons / Refunds / Payouts / Audit tabs
- Full audit trail for every state change

## Design
- **Ocean navy** primary `#1E3A5F` with mint accent `#0EA5A0`
- Refined & minimal: 12–16px radii, thin 1px borders, restrained shadows, more whitespace
- Ionicons, StyleSheet only, mobile-first with RN Web support

## Key endpoints
Student: `/enrollments`, `/payments/checkout`, `/payments/status`, `/reviews`, `/refunds`, `/coupons/validate`, `/me/referrals`, `/me/enrollments/{id}/progress|certificate`
Merchant: `/merchant/{courses,batches,coupons,payouts}`, `/merchant/batches/{id}/sessions/{sid}/attendance`
Admin: `/admin/{dashboard,institutes,courses,coupons,refunds,payouts,audit-logs}`, POST `/admin/{resource}/{id}/status`

## Test credentials
`/app/memory/test_credentials.md` — Stripe test key already in env, no user setup needed.

## Backlog
- Real SMS/email provider (dev-adapter today)
- Stripe Connect for automated splits (needs live keys + merchant KYC)
- Merchant-mode certificate customization + PDF download
- Push notifications for cert-ready / referral-reward events
- Course completion badges + gamified streaks
