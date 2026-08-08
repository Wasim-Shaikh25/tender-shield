# PHASE 7 QA Checklist — Visual, Functional, & Performance

**Status**: In Progress  
**Last Updated**: 2026-08-06  
**Task Reference**: TS-364 (PHASE 7 Part 2)

---

## Visual QA Checklist

### Color & Contrast (WCAG AA)
- [ ] All text has sufficient contrast (4.5:1 normal, 3:1 large)
- [ ] Status badges are distinguishable (not color-alone)
- [ ] Buttons have clear hover/active states
- [ ] Links are underlined or have color + icon
- [ ] Error states use error color + icon
- [ ] Success states use success color + icon
- [ ] Verify on light and dark (if dark mode in scope)

### Spacing & Alignment
- [ ] Padding consistent across cards (16px)
- [ ] Gaps between elements consistent (8px, 12px, 16px, 24px)
- [ ] Text line-height readable (1.5 for body, 1.2 for headings)
- [ ] Lists have proper indentation and spacing
- [ ] Form fields properly aligned and spaced
- [ ] Modal content properly padded (24px)
- [ ] Sidebar navigation properly spaced

### Typography
- [ ] Heading hierarchy (h1 > h2 > h3 > p)
- [ ] Font sizes follow scale (12px, 14px, 16px, 18px, 20px, 24px, 30px, 36px)
- [ ] Font weights appropriate (400, 500, 600, 700)
- [ ] Letter-spacing consistent for caps/small-caps
- [ ] Line-height appropriate per element type

### Component Styling
- [ ] **Buttons**: Proper padding, consistent sizing, clear variants
  - [ ] Primary button styling correct
  - [ ] Secondary button styling correct
  - [ ] Ghost button styling correct
  - [ ] Destructive button styling correct
  - [ ] Loading states show spinner
  - [ ] Disabled state is visually distinct

- [ ] **Input fields**: Labels, help text, error states
  - [ ] Label clearly associated with input
  - [ ] Placeholder text sufficient contrast
  - [ ] Focus ring visible
  - [ ] Error text appears below field
  - [ ] Success checkmark visible when valid
  - [ ] Required marker visible

- [ ] **Cards**: Consistent elevation, borders, spacing
  - [ ] Card shadow consistent
  - [ ] Card border color consistent
  - [ ] Card padding (24px) consistent
  - [ ] Header/footer border visible
  - [ ] Hover effect subtle but noticeable

- [ ] **Badges**: Color, size, positioning
  - [ ] Color matches status
  - [ ] Size appropriate for context
  - [ ] Text contrast sufficient
  - [ ] Icon/text alignment proper

- [ ] **Modal**: Backdrop, animation, focus
  - [ ] Backdrop color (black 50%) correct
  - [ ] Modal animation smooth
  - [ ] Close button positioned top-right
  - [ ] Close button accessible
  - [ ] Focus trap working
  - [ ] Padding/spacing inside modal

- [ ] **Tabs**: Border, hover, active states
  - [ ] Active tab border visible
  - [ ] Hover effect on inactive tabs
  - [ ] Tab text color changes on active
  - [ ] Content fade-in animation smooth
  - [ ] Focus ring on tab triggers

- [ ] **Dropdown**: Position, shadow, arrow
  - [ ] Dropdown appears below trigger
  - [ ] Shadow and border visible
  - [ ] Items properly spaced
  - [ ] Hover state on items
  - [ ] Align options (left/right) working

- [ ] **Table**: Headers, rows, alignment
  - [ ] Header background distinct
  - [ ] Row hover effect subtle
  - [ ] Borders between rows visible
  - [ ] Striped variant works
  - [ ] Alignment (left/center/right) correct
  - [ ] Scrollable on mobile

- [ ] **Tooltip**: Position, arrow, timing
  - [ ] Positioning correct (top/bottom/left/right)
  - [ ] Arrow points to trigger
  - [ ] Text contrast sufficient
  - [ ] Fade-in timing appropriate
  - [ ] Visible only on hover

- [ ] **Breadcrumb**: Links, separators, active
  - [ ] Links underlined or colored
  - [ ] Separators visible between items
  - [ ] Active item not clickable
  - [ ] Proper navigation hierarchy

- [ ] **Toast**: Position, animation, dismiss
  - [ ] Toasts appear bottom-right
  - [ ] Animation smooth
  - [ ] Type icon visible
  - [ ] Dismiss button accessible
  - [ ] Auto-dismiss timing correct (5s)

---

## Component Integration Checklist

### Modal Integration
- [x] Settings delete account confirmation
- [ ] Confirm dialogs on other destructive actions
- [ ] Multi-step modal flows (if needed)

### Dropdown Integration
- [x] Admin users page (suspend/unsuspend/delete actions)
- [x] Settings integrations page (test/poll/edit/delete connector actions)
- [ ] API keys page (revoke actions)
- [ ] Support page (ticket actions)
- [ ] Other multi-action lists

### Tabs Integration
- [ ] Opportunities detail page (documents, analysis, risk clauses)
- [ ] Projects detail page (different project views)
- [ ] Settings pages (group related settings)
- [ ] Admin workspace page (members, settings, plan)

### Table Integration
- [ ] Admin users list (tabular user data)
- [ ] Audit log (events table)
- [ ] Integration sources (sync jobs table)
- [ ] Support tickets list (ticket history table)

### Other Components (Status)
- [x] Skeleton loading states (created, ready for integration)
- [x] Tooltip (created, ready for integration)
- [x] Breadcrumb (created, ready for integration)
- [x] Toast (created, ready for integration)

---

## Responsive Design Checklist

### Mobile (320px - 640px)
- [ ] Text readable without zooming
- [ ] Buttons are at least 44px tall (touchable)
- [ ] Modals/drawers fit screen
- [ ] Tables scroll horizontally if needed
- [ ] Sidebar collapses to hamburger menu
- [ ] Forms stack vertically
- [ ] Images scale correctly
- [ ] No horizontal overflow

**Pages to verify**:
- [ ] `/` (Landing)
- [ ] `/login`
- [ ] `/opportunities`
- [ ] `/projects`
- [ ] `/settings`
- [ ] `/admin`
- [ ] `/billing`

### Tablet (640px - 1024px)
- [ ] Layout adjusts properly
- [ ] Sidebar visible or togglable
- [ ] Grid columns adjust (2-3 cols)
- [ ] Tables readable
- [ ] Forms have proper width
- [ ] Modals center correctly
- [ ] Spacing adjusts (not cramped)

**Pages to verify**:
- [ ] `/dashboard/state`
- [ ] `/opportunities/[id]`
- [ ] `/plan`
- [ ] All settings pages

### Desktop (1024px+)
- [ ] Full layout visible
- [ ] Sidebar always visible
- [ ] Grid columns optimal (3-4 cols)
- [ ] Tables display properly
- [ ] Modals centered and sized
- [ ] Spacing optimal
- [ ] No excessive whitespace

**Pages to verify**:
- All pages at 1920px resolution

---

## Functional QA Checklist

### Authentication Flow
- [ ] Login page loads
- [ ] Email/password inputs work
- [ ] Submit button works
- [ ] Error messages display
- [ ] Link to signup works
- [ ] Link to forgot password works
- [ ] Remember me functionality (if implemented)
- [ ] MFA flow works
- [ ] Signup creates account
- [ ] Verification email flow works

### Navigation
- [ ] Sidebar navigation links work
- [ ] Active nav item highlighted
- [ ] Logo links to home
- [ ] Workspace selector works
- [ ] Profile menu works
- [ ] Sign out works
- [ ] Breadcrumbs navigate correctly
- [ ] Back buttons work

### Opportunities Workflow
- [ ] Create opportunity works
- [ ] Opportunity list displays
- [ ] Filter opportunities works
- [ ] Deadline colors correct (red/amber/green)
- [ ] View opportunity detail works
- [ ] Tabs in detail page work
- [ ] Upload document works
- [ ] Risk detection works (if async)
- [ ] Export works
- [ ] Delete opportunity works

### Projects Workflow
- [ ] List projects displays
- [ ] Filter/sort projects works
- [ ] View project state works
- [ ] Project metrics display
- [ ] Blocker warnings display
- [ ] Gate status shows
- [ ] Create project works

### Settings Workflow
- [ ] Load settings displays data
- [ ] Update profile works
- [ ] Change email works (two-step)
- [ ] Change password works
- [ ] API key management works
- [ ] Integrations setup works
- [ ] Delete account modal opens
- [ ] Delete account works

### Admin Workflow
- [ ] Admin dashboard loads
- [ ] User search works
- [ ] User filtering works
- [ ] Suspend/unsuspend users works
- [ ] Delete user works
- [ ] View user detail works
- [ ] Workspace management works
- [ ] Plan change works
- [ ] Audit log filters work
- [ ] Coupon creation works
- [ ] Coupon management works

### Component Interactions
- [ ] Modal opens and closes
- [ ] Modal ESC closes
- [ ] Modal backdrop click closes
- [ ] Modal focus trap works
- [ ] Tabs switch content
- [ ] Tab arrow keys work
- [ ] Dropdown opens/closes
- [ ] Dropdown arrow keys work
- [ ] Dropdown ESC closes
- [ ] Tooltips appear on hover
- [ ] Toast notifications appear
- [ ] Toast auto-dismiss works

### Forms
- [ ] Form validation works
- [ ] Error messages appear below fields
- [ ] Error messages clear on input
- [ ] Submit button disables when loading
- [ ] Loading spinner appears
- [ ] Success message displays
- [ ] Form resets after success
- [ ] Required fields marked

### Tables
- [ ] Table renders data
- [ ] Columns align correctly
- [ ] Header stands out
- [ ] Rows hover on mouse over
- [ ] Striped variant works
- [ ] Mobile scroll works
- [ ] Actions buttons work

---

## Accessibility Verification Checklist

### Keyboard Navigation
- [ ] Tab key navigates through all interactive elements
- [ ] Shift+Tab navigates backward
- [ ] Enter activates buttons
- [ ] Space activates checkboxes/toggles
- [ ] Arrow keys work in tabs
- [ ] Arrow keys work in dropdowns
- [ ] ESC closes modals
- [ ] ESC closes dropdowns

### Focus Management
- [ ] Focus visible on all elements
- [ ] Focus ring consistent color
- [ ] Focus order logical (top-left to bottom-right)
- [ ] Modal focus trap works
- [ ] Focus restored after modal closes
- [ ] Skip links present (if applicable)

### Screen Reader
- [ ] Page titles announced
- [ ] Headings have proper hierarchy
- [ ] Links are descriptive
- [ ] Buttons are descriptive
- [ ] Form labels associated with inputs
- [ ] Error messages announced
- [ ] Status messages announced
- [ ] Alt text on images (if any)

### ARIA Attributes
- [ ] Buttons have role="button" or are `<button>` elements
- [ ] Links have role="link" or are `<a>` elements
- [ ] Tabs have role="tab", role="tablist", role="tabpanel"
- [ ] Modal has role="dialog" and aria-modal="true"
- [ ] Dropdown has role="menu" and role="menuitem"
- [ ] Form inputs have associated labels
- [ ] Error messages have aria-describedby
- [ ] Live regions have aria-live

---

## Performance Checklist

### Lighthouse Scores (Target: 85+)
- [ ] Run Lighthouse on home page
- [ ] Run Lighthouse on opportunities list
- [ ] Run Lighthouse on opportunity detail
- [ ] Run Lighthouse on settings page
- [ ] Run Lighthouse on admin dashboard

**Targets**:
- Performance: 85+
- Accessibility: 90+
- Best Practices: 85+
- SEO: 80+

### Bundle Size
- [ ] Check React bundle size
- [ ] Check Framer Motion size (~35KB gzipped)
- [ ] Check total CSS size
- [ ] Check images are optimized
- [ ] No unused dependencies

### Load Time
- [ ] Homepage loads in <2s
- [ ] Opportunities list in <2s
- [ ] Opportunity detail in <3s (complex page)
- [ ] Settings page in <2s

### Rendering
- [ ] No layout shifts (CLS)
- [ ] No jumpy animations
- [ ] Modals animate smoothly
- [ ] Tabs fade-in smoothly
- [ ] Page transitions smooth

---

## Browser Compatibility Checklist

### Chrome/Edge (Chromium-based)
- [ ] All pages load
- [ ] All interactions work
- [ ] No console errors
- [ ] Animations smooth
- [ ] Forms work
- [ ] Modals work

### Firefox
- [ ] All pages load
- [ ] All interactions work
- [ ] No console errors
- [ ] Focus rings visible
- [ ] Forms work
- [ ] CSS variables work

### Safari (macOS)
- [ ] All pages load
- [ ] Animations smooth
- [ ] Forms work
- [ ] No webkit-specific issues
- [ ] Touch interactions work

### Mobile Browsers
- [ ] iPhone Safari works
- [ ] Android Chrome works
- [ ] Touch gestures work
- [ ] Modals dismiss with swipe (if implemented)
- [ ] Keyboard appearance correct

---

## Regression Testing Checklist

### Critical Paths (Test First)
- [ ] Authentication (login → workspace → project)
- [ ] Opportunity workflow (create → view → review → export)
- [ ] Project state dashboard
- [ ] Settings update
- [ ] Admin user management
- [ ] Billing/subscription

### Component Integration
- [ ] Modal in settings (delete account) ✅ (Done)
- [ ] Tabs in complex layouts
- [ ] Dropdown in action menus
- [ ] Table in admin views
- [ ] Toast notifications
- [ ] Skeleton loading states

### Data Integrity
- [ ] Form submissions preserve data
- [ ] Deletions work correctly
- [ ] Updates don't lose data
- [ ] No duplicate entries
- [ ] API calls complete successfully

---

## Sign-Off Criteria

All of the following must be TRUE:
- [ ] All visual QA items checked
- [ ] All responsive design items verified (3 breakpoints)
- [ ] All functional workflows tested
- [ ] All accessibility checks pass
- [ ] Lighthouse scores 85+
- [ ] No console errors on critical pages
- [ ] All browser compatibility verified
- [ ] No regression issues found
- [ ] Performance acceptable (<2s load time)

---

## Testing Methodology

1. **Visual QA** (30 min): Walk through each page, verify colors, spacing, typography
2. **Responsive QA** (45 min): Test at 320px, 768px, 1920px on desktop and real mobile
3. **Functional QA** (60 min): Test critical workflows, forms, interactions
4. **Accessibility QA** (30 min): Keyboard navigation, screen reader spot-check, focus management
5. **Performance** (15 min): Run Lighthouse on key pages
6. **Browser Testing** (30 min): Spot-check Chrome, Firefox, Safari
7. **Regression Testing** (30 min): Verify no breaking changes to existing functionality

**Total Time**: ~3.5 hours for comprehensive QA

---

## Notes

- Take screenshots at each breakpoint for comparison
- Use browser DevTools to verify spacing/sizing
- Test with real data, not just empty states
- Test with slow network (throttle to 3G)
- Test with reduced motion enabled
- Test with high zoom (200%)
- Test with screen reader (VoiceOver on macOS)
