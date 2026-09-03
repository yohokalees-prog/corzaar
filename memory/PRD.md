# CORZAAR (IMS) — Product Requirements

## Problem statement
Build the CORZAAR Institute Management System exactly per the README functional spec:
students discover courses, merchants/institutes manage listings, admin governs the marketplace.
Preserve architecture and role flows; add missing login/signup and admin where necessary.

## User personas
- **Student**: discovers and enrolls in courses, saves favorites, tracks learning, pays fees.
- **Merchant / Institute**: manages courses, batches, students, payments; onboards through review.
- **Admin**: oversees institutes (approve/reject), audits marketplace, monitors metrics.

## Roles & auth flows
- **Student & Merchant**: Mobile number → SMS OTP verification (dev code `123456`).
- **Admin**: Email + password + secondary OTP verification (dev code `123456`).
- JWT (`sub` + `role`) signed by backend; token stored via `@/src/utils/storage` secure API.

## Core requirements (implemented)
### Student
- Home hero, categories, top courses, trusted institutes, quick offers/placements
- Discover: search, category filter, results grid
- Course detail: institute link, curriculum, reviews, payment gateway simulation
- Institute detail: about, courses, student voices
- Cart / Favorites (persistent per account)
- Profile: edit name/email, view enrollments, sign out
- Offers, Placements, Notifications, bottom tab navigation

### Merchant / Institute
- Onboarding via OTP → merchant portal
- Overview metrics (active courses, enrollments)
- Course create form (title, description, fees) → submitted for admin review
- Tabbed workspace: Overview / Courses / Batches / Payments

### Admin
- Metrics: students, active institutes, active courses
- Institute approval workflow (approve/reject pending, tag statuses)
- Tabs: Institutes / Students / Refunds / Audit logs

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB), PyJWT auth.
  Routes under `/api`: `/home`, `/courses`, `/auth/*`, `/me/*`, `/enrollments`,
  `/payments/confirm`, `/offers`, `/placements`, `/merchant/*`, `/admin/*`.
- **Database**: MongoDB collections — users, courses, institutes, enrollments,
  offers, placements, notifications, otps.
- **Frontend**: Expo Router (single index route), React Native components only,
  role-based conditional rendering, unified auth modal, safe-area aware tabs.
- **Storage**: `@/src/utils/storage` for JWT and session persistence.

## Design system
- Botanical palette (deep green, mint, cream, terracotta accent), Ionicons.
- 8pt spacing, StyleSheet only, mobile-first, 44pt touch targets.

## Test credentials
See `/app/memory/test_credentials.md`.

## Backlog (post-MVP)
- Real SMS/email provider integration (currently dev-adapter with fixed OTP).
- Merchant batches & attendance UI beyond overview placeholder.
- Admin refunds, audit logs, and student management deep views.
- Payment gateway (Razorpay/Stripe) replacing the confirm-success simulation.
- Push notifications for enrollment updates (opt-in on native build).
