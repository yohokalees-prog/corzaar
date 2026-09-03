# CORZAAR (IMS) — Product Requirements

## Problem statement
Build the CORZAAR Institute Management System per the README functional spec — a marketplace where students discover and buy courses, merchants/institutes list and sell them, and admins govern the platform end-to-end.

## User personas
- **Student**: discovers, enrolls, pays (Stripe), rates, requests refunds
- **Merchant / Institute**: lists courses, creates batches (with Zoom/Meet links) and coupons, tracks attendance and revenue
- **Admin**: approves institutes, courses and coupons, handles refunds, audits all activity

## Auth flows
- Student & Merchant → mobile OTP (dev code `123456`)
- Admin → email + password + OTP (dev code `123456`)
- JWT (`sub` + `role`) stored via `@/src/utils/storage`

## Core features
### Marketplace
- Home hero, category chips, top courses, trusted institutes
- Discover with search + category filter
- Course detail with curriculum, batches, ratings, reviews, coupon input
- Institute detail with rating, courses, student voices
- Cart / Favorites persistent per student

### Payments (Stripe)
- Real Stripe hosted checkout via Emergent `emergentintegrations` adapter (INR)
- Coupon applied server-side; final amount charged after discount
- Webhook + polling reconciliation → enrollment marked active with receipt

### Ratings
- Only students with active enrollments can rate a course or its institute
- Ratings recalculated on every submit; unique per (target, student)

### Coupons
- Merchant creates code → status `pending`
- Admin approves → status `approved`; students can then apply
- Coupons appear on `/api/offers` after approval

### Course listing approval
- Merchant-created courses start `under_review`
- Admin approves (`published`) or rejects — only published courses appear in discovery

### Batches
- Merchant creates batches per course: schedule, dates, seats, coordinator, Zoom/Meet URL
- Attendance mark (present/absent) per learner per batch
- Live class link opens in browser

### Admin Insights
- Metrics: students, institutes, courses, pending items, revenue
- Tabs: Institutes, Courses, Coupons, Refunds, Audit
- Refunds: students request → admin approves/rejects; approved refund marks enrollment `refunded`
- Audit logs: every state change (institute/course/coupon/refund + batch/course create) is logged with actor and timestamp

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB), PyJWT auth, Emergent Stripe adapter
- **Frontend**: Expo Router (mobile-first, RN Web supported), single index route + role-based screens, `expo-web-browser` for Stripe checkout
- **Storage**: `@/src/utils/storage` for tokens
- **Design**: botanical palette (deep green + terracotta), Ionicons, 8pt grid, StyleSheet only

## Key API endpoints (all `/api` prefixed)
Auth: `POST /auth/send-otp`, `/auth/verify-otp`, `/auth/admin-login`, `/auth/admin-verify`
Discovery: `GET /home`, `/courses`, `/courses/{id}`, `/institutes/{id}`
Student: `POST /enrollments`, `POST /payments/checkout`, `GET /payments/status/{sid}`, `POST /reviews`, `POST /refunds`, `POST /coupons/validate`
Merchant: `GET/POST /merchant/courses`, `/merchant/batches`, `/merchant/coupons`, `/merchant/batches/{id}/attendance`
Admin: `GET /admin/dashboard`, `/admin/institutes|courses|coupons|refunds|audit-logs`, `POST /admin/{resource}/{id}/status`
Webhook: `POST /webhooks/stripe`

## Test credentials
See `/app/memory/test_credentials.md`. Uses Emergent-managed Stripe test key — no setup needed.

## Backlog
- Real SMS/email provider (dev-adapter today)
- Native Stripe PaymentSheet path (requires publishable key)
- Batch scheduler with per-session attendance dates
- Certificate generation on course completion
- Instructor payout via Stripe Connect
