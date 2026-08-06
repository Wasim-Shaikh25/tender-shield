# TenderShield UI/UX Redesign — Complete Inventory & Audit

**Status**: PHASE 1 AUDIT COMPLETE - STARTING PHASE 2-3
**Last Updated**: 2026-08-06
**Branch**: `claude/ui-dev-tools-setup-r3sxpg`

---

## CURRENT STATE ASSESSMENT

### Existing Design System

**Typography**
- Font family: Inter (with cv02, cv03, cv04, cv11 feature settings)
- No defined type scale
- Sizes scattered across components (text-xs, text-sm, text-lg, text-2xl, text-4xl, text-5xl)

**Colors**
- Primary: #0F172A (ink - brand slate)
- Grays: slate palette (50, 100, 200, 400, 500, 600, 700, 900)
- Status colors: red-50, red-700 (error only)
- No semantic color system
- No dark mode support

**Spacing**
- Tailwind defaults used (4, 6, 8, 12, 16, etc.)
- No consistent scale
- Random padding/margins

**Components**
- No shadcn/ui components currently integrated
- Basic HTML inputs with Tailwind styling
- Simple links and buttons
- Inline error states

---

## COMPLETE ROUTE INVENTORY

### Authentication (Public)
- [ ] `/login` — Login + Signup form (multi-step, 4 substeps)
- [ ] `/forgot-password` — Password reset request
- [ ] `/reset-password` — Password reset confirmation
- [ ] `/` — Landing page (when not authenticated)

### Dashboard & Core
- [ ] `/dashboard/state` — Main dashboard (TBD: content structure)
- [ ] `/opportunities` — Opportunity board (card grid layout)
- [ ] `/opportunities/[id]` — Opportunity detail view
- [ ] `/projects` — Projects list (TBD)
- [ ] `/projects/[id]` — Project detail (TBD)
- [ ] `/projects/[id]/state` — Project state view (TBD)
- [ ] `/analytics` — Analytics dashboard (TBD)

### Features
- [ ] `/controltower` — Control Tower (TBD)
- [ ] `/assistant` — AI Assistant interface (TBD)
- [ ] `/rulepacks` — Rule packs management (TBD)
- [ ] `/standards` — Standards reference (TBD)
- [ ] `/help` — Help / Support (TBD)
- [ ] `/advisor` — Advisor tool (TBD)

### Account & Settings
- [ ] `/team` — Team management (TBD)
- [ ] `/settings` — Account settings (TBD)
- [ ] `/settings/notifications` — Notification settings (TBD)
- [ ] `/settings/api-keys` — API keys management (TBD)
- [ ] `/settings/integrations` — Integrations (TBD)
- [ ] `/plan` — Plan/Subscription view (TBD)
- [ ] `/billing` — Billing dashboard (TBD)
- [ ] `/billing/settings` — Billing settings (TBD)

### Support
- [ ] `/support/tickets` — Support tickets list (TBD)
- [ ] `/support/tickets/[id]` — Support ticket detail (TBD)

### Admin (Superadmin only)
- [ ] `/admin` — Admin dashboard (TBD)
- [ ] `/admin/users` — User management (TBD)
- [ ] `/admin/users/[id]` — User detail (TBD)
- [ ] `/admin/workspaces` — Workspace management (TBD)
- [ ] `/admin/workspaces/[id]` — Workspace detail (TBD)
- [ ] `/admin/audit-log` — Audit log (TBD)
- [ ] `/admin/support` — Support management (TBD)
- [ ] `/admin/coupons` — Coupon management (TBD)

---

## COMPONENT INVENTORY

### Existing Components
1. **AppShell** (`components/app-shell.tsx`)
   - Sidebar navigation (fixed desktop, drawer mobile)
   - Main header with workspace selector
   - Mobile header with menu toggle
   - Navigation items (10+ main nav, 3 account nav, admin)

2. **Session** (`components/session.tsx`)
   - Session/auth context provider

3. **AuthGate** (`components/auth-gate.tsx`)
   - Protected route wrapper

4. **Badges** (`components/badges.tsx`)
   - CountdownBadge (for submission deadlines)
   - Other status badges

5. **HeaderActions** (`components/header-actions.tsx`)
   - Header actions/user menu (TBD implementation)

6. **PlanDashboard** (`components/plan-dashboard.tsx`)
   - Subscription/plan display (TBD implementation)

7. **Markdown** (`components/markdown.tsx`)
   - Markdown renderer

---

## SHARED UI PATTERNS TO STANDARDIZE

### Forms
- ❌ No standard form layout
- ❌ No standard field styling
- ❌ No standard validation UI
- ❌ Need: required indicators, help text, grouped fields

### Tables
- ❌ No tables implemented yet
- ⚠️ Likely needed for: admin pages, lists, audit logs

### Modals/Dialogs
- ❌ No modal system
- ⚠️ Need for: confirmations, forms, details

### Loading States
- ❌ Basic "Loading..." text only
- ⚠️ Need: skeletons, progress indicators

### Empty States
- ✅ EmptyState component exists (opportunities page)
- ⚠️ Needs refinement: consistent styling, icon support

### Error/Success Feedback
- ❌ Error state: inline red box (not accessible)
- ❌ Success feedback: probably missing
- ⚠️ Need: toast notifications

### Notifications
- ❌ No toast/notification system

---

## DESIGN SYSTEM TO BUILD

### Phase 2: Design System Foundation

**Typography Scale**
```
display-lg: 36px/44px (hero titles)
display-md: 30px/36px (page titles)
heading-lg: 24px/32px (section titles)
heading-md: 20px/28px (subsection titles)
heading-sm: 16px/24px (card titles)
body-lg: 16px/24px (body text, default)
body-md: 14px/20px (secondary text)
body-sm: 12px/16px (captions, labels)
mono-sm: 12px/16px (code, timestamps)
```

**Color Tokens**

Semantic:
- background: #F8FAFC (current slate-50)
- surface: #FFFFFF
- surface-secondary: #F1F5F9 (slate-100)
- border: #E2E8F0 (slate-200)
- border-dark: #CBD5E1 (slate-300)
- text-primary: #0F172A (ink)
- text-secondary: #475569 (slate-600)
- text-tertiary: #94A3B8 (slate-400)
- text-muted: #A1A1A1
- interactive-primary: #0F172A (ink)
- interactive-hover: #1E293B (slate-800)
- success: #10B981
- success-background: #ECFDF5
- warning: #F59E0B
- warning-background: #FFFBEB
- error: #EF4444
- error-background: #FEE2E2
- info: #3B82F6
- info-background: #EFF6FF

**Spacing Scale**
- xs: 4px
- sm: 8px
- md: 12px
- lg: 16px
- xl: 24px
- 2xl: 32px
- 3xl: 48px
- 4xl: 64px

**Radius Scale**
- sm: 4px (inputs, small elements)
- md: 8px (buttons, cards)
- lg: 12px (dialogs, large containers)
- xl: 16px (hero sections)
- full: 9999px (pills)

**Shadows**
- sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05)
- md: 0 4px 6px -1px rgba(0, 0, 0, 0.1)
- lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1)
- xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1)

**Focus State**
- All interactive elements: 2px solid ink, offset 2px

---

## PHASE 3: GLOBAL SHELL REDESIGN

### Current AppShell Issues
- ❌ Workspace selector is a basic `<select>` (poor UX)
- ❌ Mobile navigation is OK but could be smoother
- ❌ No user profile menu/dropdown
- ❌ No notifications icon/system
- ❌ No search/command palette
- ❌ Sidebar lacks visual hierarchy
- ❌ No breadcrumbs for deep pages

### Redesign Plan
1. **Header Improvements**
   - Add workspace/org selector (custom dropdown, not `<select>`)
   - Add search/command palette icon
   - Add notifications bell
   - Add user profile menu dropdown
   - Add help/support icon

2. **Sidebar Improvements**
   - Visual hierarchy: primary nav vs account nav
   - Current page indicator (more prominent)
   - Collapse/expand state memory
   - Better visual separation sections
   - Icon + label for nav items (shadcn icons)
   - Active state styling

3. **Mobile Navigation**
   - Smooth drawer transitions (Framer Motion)
   - Better visual feedback
   - Reduced cognitive load

4. **Breadcrumbs**
   - Add breadcrumb trail for deep pages
   - Auto-generate from route

---

## PHASE 4: PRIORITY PAGE REDESIGNS

### TIER 1 (Critical User Journeys)
1. **Login/Signup** (`/login`)
   - Multi-step form needs refinement
   - Error states, loading states
   - Password strength indicator
   - "Remember me" checkbox
   - Social login placeholder (if planned)

2. **Opportunities Board** (`/opportunities`)
   - Currently: 3-column card grid
   - Could add: filtering, search, sorting
   - Card design needs improvement
   - Status badges need refinement
   - CTA clarity ("Open workbench" unclear)

3. **Opportunity Detail** (`/opportunities/[id]`)
   - Complete redesign needed (not viewed yet)
   - Likely: multi-tab layout
   - Document uploads section
   - Risk findings list
   - BOQ review section
   - Actions/export panel

4. **Dashboard** (`/dashboard/state`)
   - Complete redesign needed (not viewed yet)
   - KPI cards/metrics
   - Recent activity
   - Quick actions
   - Status summary

### TIER 2 (Secondary Features)
5. **Settings** (`/settings`, `/settings/*`)
   - Sidebar with settings tabs
   - Form layouts for each section
   - Connected state indicators

6. **Billing** (`/billing`)
   - Plan cards
   - Feature comparison
   - Payment method management
   - Invoice history table

7. **Team Management** (`/team`)
   - Team member list
   - Roles/permissions
   - Invite form
   - Status indicators

### TIER 3 (Admin & Support)
8. **Admin Dashboard** (`/admin`)
9. **Support** (`/support/*`)
10. **Analytics** (`/analytics`)

---

## SHARED COMPONENT PATTERNS TO CREATE

### High Priority
- [ ] Button (primary, secondary, danger, ghost, loading)
- [ ] Input (text, email, password, with error state)
- [ ] Select (single, with search)
- [ ] Checkbox & Radio
- [ ] Form Layout (label + input + help + error)
- [ ] Card (elevated, outlined, flat)
- [ ] Badge (status, category, dismissible)
- [ ] Alert (info, success, warning, error)
- [ ] Modal/Dialog (confirm, form, info)
- [ ] Dropdown Menu (user menu, actions)
- [ ] Table (with sorting, filtering, pagination)
- [ ] Toast/Notification (success, error, info)
- [ ] Skeleton/Loading state
- [ ] Tabs
- [ ] Breadcrumb

### Medium Priority
- [ ] Avatar
- [ ] Status Indicator
- [ ] Popover
- [ ] Tooltip
- [ ] Accordion
- [ ] Pagination
- [ ] Drawer/Sidebar
- [ ] Search/Command palette
- [ ] Progress indicator
- [ ] Stepper (for multi-step forms)

### Use shadcn/ui for:
- Button, Input, Select, Checkbox, Radio, Label
- Card, Badge, Alert
- Dialog, AlertDialog, Sheet, Drawer
- DropdownMenu, Popover, Tooltip
- Table, Pagination
- Tabs, Accordion
- Toast (via Sonner)
- Avatar
- Skeleton

---

## IMPLEMENTATION ROADMAP

### Step 1: Design System (Token Setup)
- [ ] Update `tailwind.config.ts` with semantic tokens
- [ ] Update `globals.css` with CSS variables
- [ ] Create reusable color/spacing utilities

### Step 2: Global Components
- [ ] AppShell redesign
- [ ] Navigation refactor
- [ ] Header improvements

### Step 3: Shared Primitives
- [ ] Install shadcn components
- [ ] Button variants
- [ ] Form field wrapper
- [ ] Card component
- [ ] Badge/Status component
- [ ] Alert component
- [ ] Modal/Dialog wrapper

### Step 4: Page Redesigns (Tier 1)
- [ ] Login/Signup redesign
- [ ] Opportunities board redesign
- [ ] Opportunity detail page
- [ ] Dashboard redesign

### Step 5: Page Redesigns (Tier 2)
- [ ] Settings pages
- [ ] Billing page
- [ ] Team management

### Step 6: Page Redesigns (Tier 3)
- [ ] Admin pages
- [ ] Support pages
- [ ] Analytics pages

### Step 7: Polish & QA
- [ ] Responsiveness audit
- [ ] Accessibility audit
- [ ] Visual QA
- [ ] Functional QA
- [ ] Motion/animation refinement

---

## SUCCESS CRITERIA

- [x] Complete application audit (all routes identified)
- [ ] Design system implemented in code
- [ ] AppShell redesigned with new navigation
- [ ] All forms styled consistently
- [ ] All data tables styled consistently
- [ ] All modal/dialog patterns implemented
- [ ] Loading/empty/error states on every page
- [ ] Responsive behavior for mobile/tablet/desktop
- [ ] Dark mode support (if in scope)
- [ ] Accessibility: WCAG AA minimum
- [ ] No existing functionality broken
- [ ] Professional, modern appearance
- [ ] Existing business logic preserved

---

**Next Action**: Move to PHASE 2 - Establish design system in tailwind.config.ts and globals.css
