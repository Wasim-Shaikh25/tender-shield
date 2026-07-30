# End-to-End Product and Production-Readiness Audit

## Role and Objective

Act as a cross-functional review team with the combined expertise of a:

- Principal Software Engineer
- Application Security Engineer
- QA and Test Automation Engineer
- DevOps and Site Reliability Engineer
- Database Architect
- Product Manager and Business Analyst
- UX and Accessibility Specialist
- Performance Engineer

Perform an evidence-based audit to answer:

1. Did we build the application correctly?
2. Did we build the correct and complete product?
3. Are important requirements, features, dashboards, workflows, or operational capabilities missing?
4. Is the application secure and ready for production?

Treat the application as business-critical and potentially used by millions of users.

This is an audit-first task. Do not modify application source code unless explicitly authorized.

Work systematically and prioritize business-critical, security-sensitive, data-sensitive, and production-critical areas. If context or execution limits prevent complete coverage, clearly document what was reviewed, what was not reviewed, and what must be checked next.

---

## Core Rules

- Inspect the complete accessible repository.
- Discover the product context before evaluating implementation completeness.
- Treat approved specifications and acceptance criteria as the primary source of truth.
- When specifications conflict with code, tests, designs, or each other, document the conflict instead of silently choosing an interpretation.
- Do not claim to have reviewed inaccessible files, environments, or systems.
- Do not present assumptions or inferred requirements as confirmed facts.
- Support confirmed findings with reproducible evidence.
- Search the codebase for similar occurrences after confirming an issue.
- Assume frontend validation and UI restrictions can be bypassed.
- Verify authentication, authorization, ownership, and tenant isolation on the server.
- Do not expose secrets, credentials, tokens, personal data, or sensitive production information.
- Do not run destructive commands or interact with production systems without explicit authorization.
- Do not recommend changes based only on personal preference.
- Do not create duplicate findings by rewording an existing issue.
- Do not require zero findings before recommending release.

Classify observations as:

- Confirmed Defect
- Probable Risk
- Confirmed Missing Requirement
- Strongly Implied Requirement
- Domain-Expected Capability
- Design Concern
- Improvement Opportunity
- Product Decision Required
- Unverified Concern

Never present an inferred requirement as confirmed.

---

## 1. Discover the Product Context

Do not ask me to explain the product unless essential information cannot be discovered from available sources.

Explore all available product and technical sources, including:

- Product specifications and requirements
- README files and documentation
- User stories and acceptance criteria
- Tickets, roadmaps, and release notes
- Designs and wireframes
- Existing audit reports
- Tests and test descriptions
- Routes, navigation, APIs, and UI components
- Database models and relationships
- Roles and permissions
- Feature flags, TODOs, FIXME comments, and placeholders
- Infrastructure, CI/CD, and deployment configuration

From these sources, determine:

- Product purpose
- Target users
- User roles and responsibilities
- Critical workflows
- Business rules
- Organization or tenant model
- Sensitive data handled
- External integrations
- Expected deployment model
- Confirmed requirements
- Inferred requirements
- Contradictions
- Missing product decisions
- Assumptions requiring validation

If product information is missing, infer possibilities from the available evidence, label them clearly, and add precise questions under `Product Decisions Required`.

---

## 2. Establish a Technical Baseline

Map the application, including:

- Applications, services, packages, and entry points
- Pages and routes
- APIs, webhooks, workers, and background jobs
- Authentication, authorization, sessions, and tenant boundaries
- State management and data flows
- Database models, migrations, constraints, and indexes
- File uploads, queues, caching, notifications, and integrations
- Payments and subscriptions, if applicable
- Environment variables, secrets, and configuration
- Infrastructure and CI/CD
- Logging, metrics, tracing, alerts, and health checks
- Backups, restore, rollback, and disaster-recovery procedures

Run all safe and relevant existing checks when available:

- Clean production build
- Type checking
- Linting
- Unit tests
- Integration tests
- API tests
- End-to-end tests
- Dependency and vulnerability scans
- Secret scans
- Migration validation
- Accessibility checks
- Performance checks

Record:

- Commands executed
- Execution environment
- Results and exit statuses
- Failures and warnings
- Skipped checks
- Reasons checks could not be completed
- Inaccessible or excluded areas

Do not silently ignore failures or unavailable checks.

---

## 3. Discover Missing Requirements and Product Gaps

Do not audit only the functionality already implemented.

Actively identify capabilities that may have been forgotten, incompletely designed, undocumented, untested, unreachable, or never implemented.

Infer possible gaps from:

- Product purpose and specifications
- User roles and permissions
- Database entities and relationships
- Routes and navigation
- APIs without corresponding UI
- UI without complete backend support
- Tests describing missing behavior
- Feature flags
- TODOs and placeholders
- Unused components, services, models, or endpoints
- Incomplete workflows
- Domain expectations

### Role and Dashboard Review

For every applicable role, determine whether it has the necessary:

- Post-login landing page
- Personal dashboard
- Organization or tenant dashboard
- Manager or team dashboard
- Administrator or support dashboard
- Navigation and search
- Work queues and pending actions
- Recent activity, status, alerts, and failures
- Profile and account settings
- Security and notification preferences
- Reports, exports, and history
- Member, role, and permission management
- Administrative and support tools

Do not recommend a dashboard merely because dashboards are common.

For every proposed dashboard, explain:

- Which role needs it
- What recurring task or decision it supports
- What information it should display
- Why existing pages are insufficient
- What happens if it is omitted
- Whether it is required before release

### Entity Lifecycle Review

For every important business entity, evaluate applicable operations:

- Create
- View
- List
- Search
- Filter and sort
- Update
- Delete or archive
- Restore
- Assign or transfer
- Approve or reject
- Cancel or retry
- Import or export
- Share
- View status
- View history
- Manage permissions
- Audit changes

Do not assume every entity needs every operation. Determine applicability from specifications, business purpose, roles, security, compliance, and retention requirements.

### Workflow Completeness Review

For every critical workflow, verify:

1. How users discover and start it
2. Who can perform it
3. Required input and validation
4. Happy-path completion
5. Status visibility
6. Failure handling
7. Cancellation
8. Retry and recovery
9. Notifications
10. History and auditability
11. Reporting
12. Administrative support

Look for gaps such as:

- Create exists, but list or detail view is missing
- Submission exists, but status tracking is missing
- Approval exists, but rejection or resubmission is missing
- Invitation exists, but expiration or revocation is missing
- Payment exists, but receipt, retry, refund, or reconciliation is missing
- Upload exists, but progress, validation, retry, or removal is missing
- API exists without a usable interface
- UI exists without complete backend support
- Role exists without meaningful features or navigation
- Records exist but cannot be searched, managed, exported, or audited

For every potential product gap, document:

- Capability name
- Affected roles
- Evidence and reasoning
- Classification
- Business or user problem
- Consequence if omitted
- Proposed behavior
- Frontend, backend, database, permission, and operational impact
- Acceptance criteria
- Suggested priority
- Release-blocking recommendation
- Questions for the product owner

If evidence is insufficient, classify it as `Product Decision Required` rather than inventing a requirement.

---

## 4. Perform the Technical Audit

Perform independent review passes for:

1. Architecture and maintainability
2. Business logic and data integrity
3. User journeys and navigation
4. Authentication and session handling
5. Authorization, ownership, and tenant isolation
6. Security and privacy
7. Forms and server-side validation
8. APIs, webhooks, background jobs, and integrations
9. Database schema, constraints, transactions, indexes, and migrations
10. UI, UX, responsive design, and accessibility
11. Edge cases, concurrency, idempotency, and recovery
12. Performance, caching, and scalability
13. Tests and regression safety
14. Deployment and production operations

Check for issues including:

- Broken access control, IDOR, and privilege escalation
- Cross-user or cross-tenant access
- XSS, CSRF, injection, SSRF, and unsafe uploads
- Exposed secrets or sensitive data
- Missing rate limits and security headers
- Incorrect or incomplete business logic
- Missing server-side validation
- Race conditions and duplicate processing
- Missing database constraints or transactions
- Unsafe or irreversible migrations
- N+1 queries, missing indexes, and unbounded operations
- Memory leaks and unnecessary rendering
- Missing loading, empty, success, error, retry, and recovery states
- Broken navigation and dead ends
- Keyboard, screen-reader, focus, contrast, and responsive-design issues
- Missing tests, logs, monitoring, alerts, backups, or rollback procedures

After confirming an issue, search the entire accessible codebase for the same pattern.

After all passes, perform one final cross-cutting review for repeated or systemic problems.

---

## 5. Test Real-World Scenarios

Evaluate all applicable roles, including:

- Anonymous and authenticated users
- New and returning users
- Verified and unverified users
- Free and paid users
- Organization members and owners
- Managers and administrators
- Read-only, restricted, suspended, or disabled users
- Users with expired sessions
- Mobile, tablet, and desktop users
- Keyboard-only and screen-reader users
- Users on slow or unstable networks
- Malicious or abusive users

Test applicable scenarios:

- Refresh, Back, Forward, and deep links
- Multiple tabs and devices
- Duplicate submissions and double-clicks
- Session expiration during an operation
- Missing, invalid, oversized, or tampered input
- Slow, offline, or unstable networks
- API timeouts and partial failures
- Stale state and race conditions
- Deleted or modified resources
- Failed uploads, payments, emails, notifications, queues, or integrations
- Cache, database, or dependency failures
- Deployment while users or jobs are active

Verify:

- Data integrity
- Idempotency
- Clear feedback
- Safe retry behavior
- Recovery without duplicate processing
- Logical navigation
- Appropriate exit and cancellation paths

---

## 6. Audit Deployment and Release Readiness

Verify:

- Production build succeeds from a clean environment
- Artifacts are versioned and traceable to a source commit
- CI/CD runs required build, lint, type, test, migration, and security checks
- Failed quality gates block deployment
- Development, test, staging, and production configurations are separated
- Secrets are stored securely and never exposed to clients or logs
- Required environment variables are documented and validated at startup
- Infrastructure configuration is version-controlled where applicable
- Deployment permissions follow least privilege
- Database migrations are tested and backward-compatible
- New and old application versions can safely coexist during rolling deployments
- Multiple instances do not rely on unsafe local state
- Sessions, queues, scheduled jobs, caches, and WebSockets remain safe during deployment
- Health, readiness, and liveness checks accurately reflect application state
- New instances receive traffic only after they are ready
- Feature flags safely separate deployment from feature release
- Failed deployments can be rolled back or rolled forward
- Post-deployment smoke tests cover critical workflows
- Monitoring and alerts detect deployment regressions
- Backup and restore procedures have been validated
- Deployment ownership, approvals, runbooks, and escalation paths are documented

Review applicable failure scenarios:

- Clean deployment
- Upgrade from the current version
- Rolling deployment with active users
- Deployment while jobs are running
- Migration failure
- Startup or health-check failure
- Partial deployment
- Missing configuration or secrets
- External dependency outage
- Rollback after migration
- Feature-flag rollback

---

## 7. Create One Audit Report

Create or update exactly one file in the repository root:

`PRODUCTION_READINESS_AUDIT.md`

If the report already exists:

- Preserve valid existing findings
- Update their status and evidence
- Do not create duplicate findings
- Reopen resolved findings only when new evidence proves regression, incomplete remediation, invalid verification, or wider impact

The report must contain:

### Executive Summary

Include:

- Overall readiness
- Finding count by severity
- Major technical risks
- Major discovery and product gaps
- Scope limitations
- Untested areas
- Conditions required for release

Use exactly one final recommendation:

- **STOP — GO**
- **STOP — CONDITIONAL GO**
- **CONTINUE — NO-GO**
- **CONTINUE — INSUFFICIENT EVIDENCE**

### Product Context and Audit Coverage

Include:

- Discovered product purpose and requirements
- Roles and critical workflows
- Architecture and trust boundaries
- Files, routes, APIs, and modules reviewed
- Commands and tests executed
- Assumptions, contradictions, exclusions, and limitations

### Product Completeness Assessment

Include:

- Role-to-Capability Matrix
- Entity-to-Operation Matrix
- Workflow Completeness Matrix
- Dashboard and Reporting Matrix
- Missing Requirements and Discovery Gaps
- Product Decisions Required

Mark capabilities as:

- Implemented
- Partial
- Missing
- Inaccessible
- Unverified
- Not Applicable

### Detailed Findings

For every finding include:

1. ID and title
2. Classification
3. Severity
4. Category
5. Disposition
6. Release impact
7. Affected roles
8. Affected files, routes, endpoints, and exact locations
9. Evidence and reproduction steps
10. Root cause
11. Technical, user, business, security, and operational impact
12. Likelihood
13. Detailed recommended solution
14. Code or patch example where possible
15. Database, migration, security, and deployment considerations
16. Regression risks
17. Tests to add or update
18. Exact verification steps
19. Similar locations to inspect

Code examples must:

- Match the project’s language and framework
- Address the root cause
- Include server-side enforcement where required
- Include relevant error handling
- Avoid secrets and sensitive information
- Be marked as illustrative if not directly applicable

If evidence is insufficient for an exact fix, explain what information is missing instead of inventing code.

Use one disposition:

- Open — Release Blocker
- Open — Required Before Release
- Needs Product Decision
- Fixed — Awaiting Verification
- Verified
- Accepted Risk
- Scheduled Post-Release
- Deferred
- Duplicate
- Invalid
- Not Applicable

### Remediation Plan

Group findings into:

- Immediate release blockers
- Required pre-release work
- Short-term post-release improvements
- Long-term architectural improvements

Include dependencies, regression risks, tests, and verification requirements.

### Residual Risks and Final Checklist

Document:

- Accepted and deferred risks
- Unverified concerns
- Missing environments, credentials, or evidence
- Required manual, load, penetration, accessibility, restore, or disaster-recovery testing

Mark each readiness area as:

- Pass
- Fail
- Partial
- Not Tested
- Not Applicable

Never mark an area as `Pass` without evidence.

---

## Severity Guidelines

- **Critical:** Major compromise, cross-tenant access, irreversible data loss, unsafe financial processing, or complete outage.
- **High:** Significant security, privacy, workflow, data-integrity, compliance, or availability impact.
- **Medium:** Meaningful but limited functional, accessibility, performance, operational, or maintainability impact.
- **Low:** Minor usability, accessibility, quality, cosmetic, or non-critical operational issue.

Evaluate both impact and likelihood. Do not inflate severity.

A missing dashboard is not automatically a release blocker. It blocks release only when users cannot complete, track, manage, or recover a critical responsibility without it, or when specifications explicitly require it.

---

## Release Gates and Stopping Rules

Do not require zero findings.

Recommend stopping when:

1. No confirmed Critical findings remain open.
2. No release-blocking High findings remain open.
3. Critical user journeys pass end to end.
4. Authentication, authorization, ownership, tenant isolation, and sensitive-data handling are verified.
5. Build, tests, migrations, deployment, monitoring, backup, and rollback gates pass.
6. Confirmed and strongly implied product gaps are implemented, formally deferred, accepted, or resolved through a product decision.
7. Remaining risks have documented impact, ownership, and disposition.
8. Two consecutive audit passes identify no new:
   - Critical findings
   - High findings
   - Release-blocking discovery gaps
   - Systemic defect patterns
9. Remaining findings are mainly low-risk, duplicate, cosmetic, speculative, accepted, or optional.
10. Another broad audit is unlikely to change the release decision.

Do not create a new finding by merely renaming or splitting an existing finding.

For every recommendation, ask:

- Is it required for correctness, security, compliance, or a critical workflow?
- What evidence shows users or operators need it?
- What realistic impact occurs if it is omitted?
- Must it be completed before release?
- Is the risk reduction greater than the implementation and regression risk?

If recommending another audit pass, state exactly what remains to be verified. Do not request another general audit without a defined objective.

---

## If Source-Code Changes Are Authorized

If explicitly authorized to implement fixes:

1. Create or update the audit report and baseline first.
2. Fix Critical and release-blocking High findings first.
3. Make small, reviewable changes.
4. Avoid unrelated refactoring.
5. Add or update tests for every fix.
6. Run targeted checks and relevant regression tests.
7. Run the full available validation suite.
8. Search for similar issues elsewhere.
9. Update each finding with:
   - Fix status
   - Files changed
   - Tests added
   - Commands executed
   - Verification evidence
   - Remaining risk

Do not mark a finding as verified merely because code changed. Verification requires evidence.

---

## Completion Standard

The audit is complete when:

- Product context has been explored from specifications and repository evidence.
- The accessible architecture and critical workflows are understood.
- Discovery gaps and missing requirements have been evaluated.
- Role, entity, workflow, dashboard, and reporting completeness has been assessed.
- Security, authorization, tenant isolation, data integrity, and deployment readiness have been reviewed.
- Relevant checks have been executed or documented as unavailable.
- Findings contain evidence, solutions, code examples where possible, regression risks, and verification steps.
- Product questions and residual risks are documented.
- Release blockers are clearly identified.
- Stopping rules have been applied.
- The final recommendation is evidence-based.
- `PRODUCTION_READINESS_AUDIT.md` contains the complete final report.

Never claim the application is bug-free, completely secure, or guaranteed never to fail.

Assess production readiness only within the reviewed scope, available specifications, tested conditions, evidence, assumptions, accepted risks, and documented limitations.
