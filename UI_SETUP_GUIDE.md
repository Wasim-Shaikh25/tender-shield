# TenderShield UI Development Tools Setup

## Summary of Installations

This document outlines all UI/UX tools installed for the TenderShield redesign.

### ✅ Completed Installations

#### 1. **shadcn/ui** (Component Library)
- **Package**: `shadcn-ui`
- **Status**: ✅ Installed in `frontend/`
- **Config**: `frontend/components.json` created and configured
- **Usage**: Import pre-built, accessible React components
- **Docs**: https://ui.shadcn.com
- **Next Step**: Run `npx shadcn@latest add [component-name]` to add components

**Common components for TenderShield:**
```bash
npx shadcn@latest add button
npx shadcn@latest add card
npx shadcn@latest add input
npx shadcn@latest add select
npx shadcn@latest add tabs
npx shadcn@latest add table
npx shadcn@latest add alert
npx shadcn@latest add badge
```

#### 2. **Framer Motion** (Animation Library)
- **Package**: `framer-motion`
- **Status**: ✅ Installed in `frontend/package.json`
- **Version**: Latest
- **Usage**: Micro-interactions, smooth animations, gesture handling
- **Docs**: https://www.framer.com/motion/
- **Example**:
```tsx
import { motion } from "framer-motion";

export function AnimatedButton() {
  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      transition={{ type: "spring", stiffness: 400, damping: 17 }}
    >
      Click me
    </motion.button>
  );
}
```

#### 3. **UI/UX Pro Max Skill** (Design Intelligence)
- **Tool**: AI-powered design system generator
- **Status**: ✅ Installed in `.claude/skills/`
- **Features**:
  - 84 UI styles reference
  - 192 color palettes
  - 74 font pairings
  - 98 UX guidelines
  - 25 chart types across 22 tech stacks
  - Design system generation engine

**Sub-skills installed:**
- `design-system` — Token generation and system design
- `brand` — Brand guidelines and consistency
- `ui-styling` — Tailwind + shadcn integration
- `design` — Logo, icon, and CIP design
- `slides` — Presentation design
- `banner-design` — Marketing banner creation
- `ui-ux-pro-max` — Master skill with all capabilities

**How to use:**
```
In Claude Code, ask: "Generate a design system for TenderShield"
Or: "Design a professional landing page for our bid analysis tool"
Or: "Create a color palette for financial/legal product"
```

### ⏳ Pending: 21st.dev MCP

**Status**: Not yet configured (requires manual setup)

**What is 21st.dev MCP?**
- High-quality UI component patterns and inspiration library
- Can be used to reference production-grade UI patterns
- Available as an MCP (Model Context Protocol) server

**How to connect 21st.dev MCP (Manual Setup):**

Option 1: **Via Claude Code Settings**
```json
// .claude/settings.json
{
  "mcpServers": [
    {
      "name": "21st-dev",
      "command": "npx",
      "args": ["@21st-dev/mcp"]
    }
  ]
}
```

Option 2: **Check for official MCP at:**
- https://github.com/21st-dev (official repository)
- https://21st.dev (main website)

Option 3: **Use Magic Patterns MCP** (available alternative):
Can search and iterate on design patterns from Magic Patterns instead.

---

## Project Structure After Setup

```
tender-shield/
├── frontend/
│   ├── package.json (updated with shadcn-ui, framer-motion)
│   ├── components.json (new - shadcn configuration)
│   ├── app/ (Next.js app directory)
│   └── ...
├── .claude/
│   └── skills/
│       ├── ui-ux-pro-max/ (master skill)
│       ├── design-system/
│       ├── brand/
│       ├── ui-styling/
│       ├── design/
│       ├── slides/
│       └── banner-design/
└── UI_SETUP_GUIDE.md (this file)
```

---

## Next Steps for Full Redesign

1. **Review Design System Guidelines**
   ```bash
   cat .claude/skills/design-system/SKILL.md
   ```

2. **Start UI Component Redesign**
   - Use shadcn/ui for component primitives
   - Leverage framer-motion for interactions
   - Follow UI/UX Pro Max guidelines for consistency

3. **Install Additional shadcn Components as Needed**
   ```bash
   cd frontend
   npx shadcn@latest add [component-name]
   ```

4. **Build Design System Tokens** (optional)
   - Use UI/UX Pro Max design-system skill
   - Generate Tailwind config with semantic tokens
   - Ensures brand consistency across app

5. **Test Accessibility**
   - Run existing a11y tests
   - shadcn components are WCAG AA compliant by default
   - Always test keyboard navigation

6. **Document Component Patterns**
   - Keep `specs/modules/` updated with UI changes
   - Document any custom components beyond shadcn

---

## Useful Commands

```bash
# Start dev server
cd frontend && npm run dev

# Add new shadcn components
npx shadcn@latest add button card input select

# Run type checking
npm run typecheck

# Run linting
npm run lint

# Run accessibility tests
npm run a11y

# Run E2E tests
npm run test:e2e

# View shadcn component catalog
# Visit: https://ui.shadcn.com/docs/components/
```

---

## References & Resources

### Component Libraries
- **shadcn/ui**: https://ui.shadcn.com
- **Radix UI** (under shadcn): https://radix-ui.com
- **Tailwind CSS**: https://tailwindcss.com

### Animation & Motion
- **Framer Motion Docs**: https://www.framer.com/motion/
- **Framer Motion Examples**: https://www.framer.com/motion/examples/

### Design Tools & Skills
- **UI/UX Pro Max**: https://uupm.cc
- **21st.dev**: https://21st.dev

### Accessibility
- **Tailwind A11y**: https://tailwindcss.com/docs/accessibility
- **shadcn A11y**: https://ui.shadcn.com/docs/accessibility
- **WCAG 2.1 Guidelines**: https://www.w3.org/WAI/WCAG21/quickref/

### TenderShield Specific
- **Build Doc**: See `docs/TenderShield_Full_Build_Doc.md`
- **Frontend Specs**: See `specs/modules/`
- **Style Guide**: Will be defined in design-system outputs

---

## Troubleshooting

**shadcn components not appearing?**
```bash
# Ensure components.json is correct
cat frontend/components.json

# Clear node_modules and reinstall
rm -rf frontend/node_modules frontend/package-lock.json
cd frontend && npm install
```

**Framer Motion not importing?**
```bash
# Verify installation
npm list framer-motion

# Reinstall if needed
npm install framer-motion
```

**Claude Code skills not loading?**
- Restart Claude Code session
- Check `.claude/skills/` directory exists
- Run: `uipro init --ai claude` to reinstall

---

**Last Updated**: 2026-08-06  
**Setup by**: Claude Code  
**Branch**: `claude/ui-dev-tools-setup-r3sxpg`
