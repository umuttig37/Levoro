# GitHub Copilot Instructions

## Required Context Files

Before responding to any request, always read and consider the following files:

1. **CLAUDE.md** - Contains comprehensive application overview, architecture, development commands, and guidelines
2. **issues.md** - Contains current open issues, bug reports, and pending tasks

These files provide essential context about:
- Application structure and architecture
- Current known issues and priorities
- Development patterns and best practices
- Database models and workflows
- Testing and deployment procedures

## Workflow

1. Read `CLAUDE.md` to understand the application architecture and patterns
2. Read `issues.md` to check for any related open issues before making suggestions
3. Follow the architectural patterns and conventions described in `CLAUDE.md`
4. Cross-reference any proposed changes with known issues in `issues.md`
5. Ensure changes align with the established codebase structure (models/, routes/, services/, utils/)

## Key Principles

- Follow the service layer pattern (business logic in services/, thin controllers in routes/)
- Use the established database access patterns (BaseModel, CounterManager)
- Maintain role-based access control (customer, driver, admin)
- Follow the order status workflow strictly
- Consider both development and production environment differences
- Ensure email notifications follow the current specification in issues.md

## UI/UX Guidelines

### Icon System - NO EMOJIS
- **NEVER use emojis in production code** (❌, ✅, 🚗, etc.)
- **ALWAYS use a proper icon system** instead:
  - Font Awesome (preferred for web)
  - Material Icons
  - Bootstrap Icons
  - SVG icons from a design system
- Use semantic HTML with icon classes: `<i class="fas fa-check"></i>` or `<svg>...</svg>`
- Icons should be accessible with proper aria-labels
- Emojis are acceptable ONLY in:
  - README files and documentation
  - Development/testing comments
  - Internal notes in issues.md

### Typography
- Important pricing information should be prominently displayed
- Use appropriate font sizes and weights for hierarchy
- Ensure readability across all device sizes
