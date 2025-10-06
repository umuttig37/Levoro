# Levoro Documentation

This directory contains all project documentation organized by category.

## 📂 Directory Structure

```
docs/
├── README.md                 # This file
├── features/                 # Feature documentation and implementation guides
├── testing/                  # Testing guides and procedures
└── archive/                  # Historical documentation and completed fixes
```

## 📚 Active Documentation

### Root Level (Always Check First)
- **[CLAUDE.md](../CLAUDE.md)** - 📖 **START HERE** - Comprehensive application overview, architecture, development commands, and guidelines
- **[issues.md](../issues.md)** - 🐛 Current open issues, bug reports, and pending tasks
- **[README.md](../README.md)** - Project overview and setup instructions (if exists)

## 🎯 Features

Documentation for implemented features and system designs:

- **[DEV_EMAIL_MOCK_SYSTEM.md](features/DEV_EMAIL_MOCK_SYSTEM.md)** - Development email testing system (saves emails as HTML files)
- **[DEV_PRODUCTION_IMAGE_SEPARATION.md](features/DEV_PRODUCTION_IMAGE_SEPARATION.md)** - Image storage strategy for dev vs production
- **[DRIVER_WORKFLOW.md](features/DRIVER_WORKFLOW.md)** - Driver workflow and notification system
- **[EMAIL_TEMPLATE_REDESIGN.md](features/EMAIL_TEMPLATE_REDESIGN.md)** - Email template system architecture and usage
- **[IMAGE_STORAGE_SOLUTION.md](features/IMAGE_STORAGE_SOLUTION.md)** - Image upload and storage implementation
- **[USER_ORDER_PAGE_MOBILE_IMPROVEMENTS.md](features/USER_ORDER_PAGE_MOBILE_IMPROVEMENTS.md)** - Mobile UX improvements
- **[WORKFLOW_ANALYSIS.md](features/WORKFLOW_ANALYSIS.md)** - Complete order workflow and email notification analysis

## 🧪 Testing

Guides for testing various features:

- **[CONTACT_TESTING_GUIDE.md](testing/CONTACT_TESTING_GUIDE.md)** - Contact form testing procedures
- **[DRIVER_REWARD_SYSTEM_TESTING.md](testing/DRIVER_REWARD_SYSTEM_TESTING.md)** - Driver reward system testing guide
- **[EMAIL_NOTIFICATION_TESTING_GUIDELINES.md](testing/EMAIL_NOTIFICATION_TESTING_GUIDELINES.md)** - Email notification testing
- **[EMAIL_WORKFLOW_TEST_GUIDE.md](testing/EMAIL_WORKFLOW_TEST_GUIDE.md)** - Complete email workflow testing

## 📦 Archive

Historical documentation, completed fixes, and one-time maintenance:

- Completed feature summaries
- Fixed bugs documentation
- One-time cleanup scripts documentation
- Deprecated implementations

## 🚀 Quick Start

### For New Developers
1. Read [CLAUDE.md](../CLAUDE.md) for full application architecture
2. Check [issues.md](../issues.md) for current status
3. Review relevant feature docs in `features/` directory
4. Check testing guides before making changes

### For Testing
1. Use [EMAIL_WORKFLOW_TEST_GUIDE.md](testing/EMAIL_WORKFLOW_TEST_GUIDE.md) for email testing
2. Use [DEV_EMAIL_MOCK_SYSTEM.md](features/DEV_EMAIL_MOCK_SYSTEM.md) to set up dev email viewing
3. Check specific testing guides for feature-specific tests

### For Feature Development
1. Check [WORKFLOW_ANALYSIS.md](features/WORKFLOW_ANALYSIS.md) for order workflow
2. Check [EMAIL_TEMPLATE_REDESIGN.md](features/EMAIL_TEMPLATE_REDESIGN.md) for email templates
3. Update [issues.md](../issues.md) when completing tasks

## 📝 Documentation Guidelines

### When to Create New Documentation
- New features that require explanation
- Complex workflows or architectures
- Testing procedures for new functionality
- Migration guides or breaking changes

### Where to Put Documentation
- **Root level**: Only CLAUDE.md, issues.md, and README.md
- **docs/features/**: Feature implementations and architecture
- **docs/testing/**: Testing guides and procedures
- **docs/archive/**: Completed fixes, deprecated features, historical summaries

### Documentation Standards
- Use clear, descriptive filenames (SCREAMING_SNAKE_CASE.md)
- Include date created/updated
- Mark status (✅ Complete, ⏳ In Progress, 🚧 WIP)
- Keep CLAUDE.md and issues.md always up to date
- Archive completed fix summaries after merging

## 🔄 Maintenance

### Monthly Cleanup
- Move completed fix summaries to archive/
- Update CLAUDE.md with any architectural changes
- Review and close resolved issues in issues.md
- Remove outdated documentation

### Before Release
- Update all relevant documentation
- Move "COMPLETE" summaries to archive/
- Ensure CLAUDE.md reflects current architecture
- Clear resolved items from issues.md

---

**Last Updated**: October 6, 2025
