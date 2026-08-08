# Frontend UI/UX Redesign — Specification

**Requirement ref:** Master UI/UX Redesign Prompt (User request, 2026-08-06)  
**Task IDs:** TS-357 (parent), TS-358–TS-365  
**Status:** Phase 1-4 complete, Phase 5 in progress, Phase 6-7 pending  
**Branch:** `claude/ui-dev-tools-setup-r3sxpg`

---

## Purpose

Transform TenderShield from a functional MVP into a premium, cohesive, highly usable modern SaaS product. All business logic is **preserved**; only presentation and UX are redesigned. The redesign spans 7 phases covering design system establishment, global shell modernization, core/advanced page redesigns, admin pages, and final polish.

---

## Requirements

- **Master UI/UX Redesign Prompt** — Complete end-to-end SaaS transformation specification provided by product owner
- **Build Doc §9** — Frontend architecture guidance
- **CLAUDE.md §1** — Workflow loop: task → spec → implement → commit → changelog

---

## Public Interface

### 1. Design System

**Semantic Tokens** (40+ tokens across 6 categories):
- **Colors:** Primary (ink), Secondary, Status (success/warning/error/info), Grays (slate palette)
- **Typography:** Display (lg/md), Headings (lg–sm), Body (lg/base/sm), Label (lg–sm)
- **Spacing:** xs (4px) → 4xl (64px) — 8 incremental sizes
- **Shadows:** xs–2xl for depth hierarchy
- **Border Radius:** xs–2xl for consistency
- **Transitions:** fast/base/slow/slower for smooth animations

**Global CSS:**
- CSS variables for all tokens in `frontend/app/globals.css`
- Focus states (ring-2, ring-offset-2) for WCAG AA
- Form base styles for inputs, textareas, selects
- Selection and placeholder styling
- Semantic link and accessibility enhancements

### 2. Component Library

**Created Components** (6 core):
1. **Button** — 5 variants (primary, secondary, ghost, destructive, outline), 3 sizes (sm, md, lg), loading state
2. **Input** — Text/email/password with labels, help text, error states, required indicators
3. **Card** — 3 variants (elevated, outlined, flat), sub-components (Header, Title, Description, Content, Footer)
4. **Badge** — 6 variants (primary, secondary, success, warning, error, info), 2 sizes
5. **Alert** — 4 variants (success, warning, error, info), optional title, left border accent
6. **Utils** — `cn()` utility for conditional Tailwind class merging

**Needed Components** (for remaining phases):
- Modal/Dialog
- Dropdown Menu
- Select (form select)
- Table (data-dense pages)
- Tabs
- Toast/Notification
- Skeleton (loading placeholder)
- Tooltip
- Popover
- Breadcrumb

### 3. Page Coverage

**PHASE 1-2: Foundation (Complete)**
- Global AppShell redesign
- Workspace selector dropdown
- Mobile drawer navigation
- Improved visual hierarchy

**PHASE 3: Core Pages (Complete)** — 6 pages
- `/login` — Card-based multi-step form
- `/` — Modern hero section with cards
- `/opportunities` — Improved card grid + create form
- `/dashboard/state` — Metrics cards + deadline list with urgency colors
- `/projects` — Filter UI + state summary cards + project list
- `/team` — Invite form + member card rows + pending invitations

**PHASE 4: Advanced Pages (Complete)** — 3 pages
- `/opportunities/[id]` — Professional card layout with tabs + risk review + deadline wall + BOQ checker + artifacts + handover + audit trail
- `/billing` — Billing status + plans + invoices/payments/history tables + coupon input
- `/plan` — Form-based dashboard generation + save/load snapshots + export to PDF/PPTX

**PHASE 5: Additional Pages (In Progress)** — 8 pages
- `/settings` — Account settings (complex, many sections)
- `/settings/notifications` — Notification preferences
- `/settings/api-keys` — API key management
- `/settings/integrations` — Integration management
- `/billing/settings` — Billing preferences
- `/projects/[id]/state` — Project state detail
- `/support/tickets` — Support tickets list
- `/support/tickets/[id]` — Support ticket detail

**PHASE 6: Admin Pages (Pending)** — 7 pages
- `/admin` — Admin dashboard
- `/admin/users` — User management
- `/admin/users/[id]` — User detail
- `/admin/workspaces` — Workspace management
- `/admin/audit-log` — Audit log viewer
- `/admin/support` — Support management
- `/admin/coupons` — Coupon management

---

## Data Owned

- **Design tokens** — Tailwind configuration + CSS variables
- **UI components** — React component library
- **Page layouts** — Next.js page implementations
- **Styling** — Tailwind classes (no external CSS files)

**No database changes.** All redesign is presentation-layer only; no business logic modifications.

---

## Behavior

### Design System Principles
1. **Semantic tokens**, not arbitrary hex values
2. **Consistent spacing scale** — no random gaps
3. **Unified typography** — predictable hierarchy
4. **Accessible focus states** — WCAG AA compliance
5. **Smooth transitions** — velocity and easing consistency

### Component Behavior
1. **Variants and sizes** — consistent sizing across all components
2. **Disabled states** — clear visual feedback
3. **Loading states** — spinner animation in buttons
4. **Error handling** — Alert component with clear messaging
5. **Responsive design** — mobile-first with Tailwind breakpoints

### Page-Level Behavior
1. **Form layouts** — labels, help text, error states, required indicators
2. **Card designs** — improved hierarchy, spacing, hover states
3. **Navigation** — clearer structure with mobile drawer
4. **Empty states** — actionable messaging
5. **Loading states** — skeleton or spinner feedback
6. **Status indication** — badge and color-coding for urgency

---

## Acceptance Criteria

### PHASE 1-2 (Complete)
- ✅ Tailwind config with 40+ semantic tokens
- ✅ Global CSS with focus states and form base styles
- ✅ 6 core UI components created and exported
- ✅ Modern AppShell with workspace selector
- ✅ Mobile-responsive navigation drawer

### PHASE 3-4 (Complete)
- ✅ 9 pages redesigned with new components
- ✅ All business logic preserved (no functional changes)
- ✅ Form fields styled with labels, help text, errors
- ✅ Tables use Badge for status indication
- ✅ Cards with proper spacing and hover states
- ✅ Color-coded deadline urgency (red < 3d, amber < 7d, blue info)
- ✅ Improved visual hierarchy and typography
- ✅ Build succeeds (no TypeScript or ESLint errors)
- ✅ CHANGELOG.md updated with progress

### PHASE 5 (In Progress)
- [ ] 8 additional pages redesigned
- [ ] Settings pages with proper form organization
- [ ] Support tickets with card-based layout
- [ ] Billing and project detail pages
- [ ] All components follow design system

### PHASE 6 (Pending)
- [ ] 7 admin pages redesigned
- [ ] Admin dashboard with metrics and management UI
- [ ] User/workspace/coupon management pages
- [ ] Audit log viewer with search/filters

### PHASE 7 (Pending)
- [ ] Additional components created (Modal, Table, Tabs, Dropdown, Toast, Skeleton, Tooltip, Popover, Breadcrumb)
- [ ] Framer Motion animations on all transitions
- [ ] WCAG AA accessibility audit complete
- [ ] Responsive behavior tested on all breakpoints
- [ ] Visual QA pass (alignment, colors, spacing, typography)
- [ ] Functional QA pass (all workflows tested end-to-end)
- [ ] Dark mode implemented (if in scope)
- [ ] Performance optimization (bundle size, render optimization)
- [ ] Legacy styling audit and cleanup

---

## Out of Scope

- ❌ Backend modifications (APIs remain unchanged)
- ❌ Business logic changes (risk calculation, BOQ validation, etc.)
- ❌ Database schema changes
- ❌ Authentication flow changes
- ❌ File upload/processing changes
- ❌ Export format changes

---

## Implementation Notes

### Files Structure
```
frontend/
├── app/
│   ├── globals.css                 (CSS variables + focus states)
│   ├── layout.tsx                  (AppShell integration)
│   ├── page.tsx                    (Landing page)
│   ├── login/page.tsx              (Login page)
│   ├── opportunities/
│   │   ├── page.tsx                (Opportunity list)
│   │   └── [id]/page.tsx           (Opportunity detail)
│   ├── dashboard/state/page.tsx    (Dashboard)
│   ├── projects/page.tsx           (Projects list)
│   ├── team/page.tsx               (Team management)
│   ├── billing/page.tsx            (Billing)
│   ├── plan/page.tsx               (Plan dashboard)
│   ├── settings/page.tsx           (Settings — PHASE 5)
│   ├── admin/page.tsx              (Admin — PHASE 6)
│   └── ...
├── components/
│   ├── app-shell.tsx               (Global navigation)
│   ├── ui/                         (Component library)
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   ├── alert.tsx
│   │   └── ...
│   └── ...
├── lib/
│   ├── utils.ts                    (cn() utility)
│   └── ...
└── tailwind.config.ts              (Design tokens)
```

### Git History
Branch: `claude/ui-dev-tools-setup-r3sxpg`

Key commits:
- Design system establishment + component library
- AppShell redesign
- Phase 3 core page redesigns
- Phase 4 advanced page redesigns
- Phase 5 in progress (each page as a separate commit)

### Quality Gates
1. **TypeScript**: No errors (`npm run type-check`)
2. **ESLint**: Clean (`npm run lint`)
3. **Build**: Succeeds (`npm run build`)
4. **Visual**: Compare before/after screenshots
5. **Functional**: Test all workflows end-to-end

---

## Success Metrics

- **Coverage**: 20+ pages redesigned with new design system
- **Components**: 6+ reusable UI components covering all page needs
- **Consistency**: 100% adherence to semantic design tokens
- **Accessibility**: WCAG AA on all interactive elements
- **Performance**: No bundle size regression
- **Quality**: Zero build/lint errors, all tests passing

---

**Spec created by:** Claude Code  
**Date:** 2026-08-06  
**Reference:** CLAUDE.md §1 (workflow loop), §3 (specs)
