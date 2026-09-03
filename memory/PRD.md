# CORZAAR (IMS) — Product Requirements

## Problem statement
Full-stack Institute Management System: students discover + buy courses, merchants list + sell + track batches, admins govern everything. Refined ocean-navy + mint design.

## Personas
- **Student** — discovers, enrolls, pays (Stripe), applies coupons/referrals, uses wallet balance, rates, self-marks curriculum, downloads/shares certificate, requests refunds, withdraws to UPI
- **Merchant / Institute** — lists courses, creates batches with auto-sessions + Zoom/Meet URLs, per-session attendance, creates coupons, sees rating trend + drop-off insights + earnings/payouts
- **Admin** — approves institutes/courses/coupons, handles refunds, records payouts, approves/pays student cashouts, reviews full audit log

## Core capabilities
### Payments (Stripe)
- Hosted checkout via `emergentintegrations` adapter (INR); server computes `fees − coupon − wallet` before charging
- Webhook + status polling reconcile enrollment as `active` with receipt

### Coupons / Referrals / Wallet
- Merchant creates coupon → admin approves → student applies at checkout
- Every student gets a `REF...` code → friend 10% off + referrer ₹200 wallet credit on paid enrollment
- Wallet spendable at checkout via `use_wallet` toggle
- **Cashout to UPI**: min ₹500, amount held instantly, admin approves/pays/rejects (reject refunds wallet), notifications + audit for every state

### Curriculum + Certificates + Share
- Student self-marks curriculum items on Profile
- 100% completion auto-issues `certificate_id`, notification, and unlocks:
  - HTML certificate (browser-viewable)
  - Landscape PDF certificate (reportlab, native download)
  - LinkedIn / Twitter / WhatsApp share links pre-filled

### Batches with auto-sessions
- On create, sessions auto-generate from schedule days (Mon Wed…) between start/end (cap 60)
- Merchant adds/removes individual sessions
- Attendance per session per student (present/absent) with session picker UI

### Course reminders
- `/api/me/notifications` merges dynamic reminders: "Class today" (with meet link) + "Class tomorrow" for any active enrollment whose batch has a session on those dates

### Ratings
- Only active-enrolled students can rate courses/institutes; averages auto-recalc

### Merchant Insights
- Weekly rating trend
- Top 5 courses by rating × log(reviews)
- Curriculum drop-off %% per item per course

### Admin oversight
- Institutes / Courses / Coupons / Refunds / Payouts / Cashouts / Audit tabs
- Instructor payouts (manual ledger + record → upgrade to Stripe Connect after deploy)
- Full audit trail on every state change

## Design
- Ocean navy `#1E3A5F` + mint `#0EA5A0` accent; refined & minimal; 12–16px radii; StyleSheet only; mobile-first RN Web-compatible

## Key endpoints
Student: `/enrollments`, `/payments/checkout`, `/payments/status`, `/reviews`, `/refunds`, `/coupons/validate`, `/me/{referrals,cashouts,enrollments/{id}/progress|certificate|certificate.pdf|share}`
Merchant: `/merchant/{dashboard,courses,batches,coupons,payouts,insights}`, `/merchant/batches/{id}/sessions/{sid}/attendance`
Admin: `/admin/{dashboard,institutes,courses,coupons,refunds,payouts,cashouts,audit-logs}` + POST status endpoints

## Test credentials
`/app/memory/test_credentials.md` — Stripe test key already in env.

## Backlog
- Real SMS/email provider (dev-adapter today)
- Stripe Connect for automated instructor payouts (needs live keys + KYC)
- Deep-linked certificate share (LinkedIn Add-to-Profile)
- Certificate customization per institute (logo, signatures)
- Auto-send session reminders via email/SMS a day before (needs provider)
