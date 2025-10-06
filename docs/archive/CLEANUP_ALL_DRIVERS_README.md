# Complete Driver Cleanup Script Documentation

## Overview

The `cleanup_all_drivers.py` script removes **ALL** driver-related records from the database. This includes:

- ✅ All driver applications (pending, approved, denied)
- ✅ All user accounts with role="driver"
- ✅ Duplicate customer accounts with emails matching driver applications

**⚠️ WARNING:** This is a destructive operation. Always create a backup first!

---

## Prerequisites

### 1. MongoDB Database Tools

The script uses `mongodump` for backups. Install if not already installed:

**Windows:**
```bash
# Download from: https://www.mongodb.com/try/download/database-tools
# Or use chocolatey:
choco install mongodb-database-tools
```

**Mac:**
```bash
brew install mongodb/brew/mongodb-database-tools
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install mongodb-database-tools

# Fedora/RHEL
sudo dnf install mongodb-database-tools
```

### 2. Python Environment

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux
```

---

## Usage

### 1. Dry-Run (Recommended First Step)

See what would be deleted without making changes:

```bash
python cleanup_all_drivers.py
```

**What it does:**
- ✅ Creates database backup
- ✅ Shows all records that would be deleted
- ✅ Shows statistics
- ❌ Does NOT delete anything

---

### 2. Backup Only

Create a backup without running cleanup:

```bash
python cleanup_all_drivers.py --backup-only
```

---

### 3. Live Mode (Actually Delete)

Delete all driver records **with backup**:

```bash
python cleanup_all_drivers.py --live
```

**What happens:**
1. Creates database backup
2. Shows all records to be deleted
3. Prompts for confirmation (must type: `DELETE ALL DRIVERS`)
4. Deletes all records
5. Shows detailed results
6. Provides restore instructions

---

### 4. Delete Without Backup (⚠️ NOT RECOMMENDED)

```bash
python cleanup_all_drivers.py --live --no-backup
```

---

## Restoring from Backup

If you need to restore the database:

### 1. Find Your Backup

```bash
ls -la backups/
```

### 2. Get MongoDB URI

From your `.env` file

### 3. Restore

```bash
mongorestore --uri="mongodb+srv://user:password@cluster.mongodb.net/carrental" backups/mongodb_backup_20251005_143530/
```

**⚠️ WARNING:** This will **overwrite** your current database with the backup!

---

## What Gets Deleted

### Driver Applications
- All records from `driver_applications` collection

### Driver Users
- All users with `role: "driver"`

### Duplicate Customers
- Customer accounts that have the same email as a driver application

---

## Command Reference

| Command | Description |
|---------|-------------|
| `python cleanup_all_drivers.py` | Dry-run (safe, shows what would be deleted) |
| `python cleanup_all_drivers.py --backup-only` | Create backup only |
| `python cleanup_all_drivers.py --live` | Delete with backup (requires confirmation) |
| `python cleanup_all_drivers.py --live --no-backup` | Delete without backup ⚠️ |
