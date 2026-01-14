# Database Migrations

This directory contains database migration scripts for Portfolio Manager.

## Available Migrations

### migrate_add_exchange_rate_ai_fields.py
Adds AI tracking fields to the `exchange_rates` table:
- `confidence`: String - 'high', 'medium', 'low'
- `ai_used`: Boolean - Whether AI was used to resolve this rate
- `ai_sources`: JSON - List of URLs for AI results
- `needs_manual_review`: Boolean - Whether this rate needs manual review
- `manual_review_reason`: String - Reason for manual review

**Status**: ✅ Applied (2026-01-14)

**Usage**:
```bash
cd backend
python scripts/migrations/migrate_add_exchange_rate_ai_fields.py
```

### migrate_add_multi_currency.py
Adds multi-currency support to transactions:
- Creates `exchange_rates` table
- Adds currency columns to `transactions` and `transaction_history` tables
- Backfills historical exchange rates

**Status**: ✅ Applied (previous)

### Other Migrations
- `migrate_add_version.py` - Adds version tracking
- `migrate_add_stock_enrichment.py` - Adds stock enrichment fields
- `migrate_add_skip_price_flags.py` - Adds skip price flags
- `migrate_add_import_tracking.py` - Adds import tracking
- `migrate_add_kpi_snapshots.py` - Adds KPI snapshots
- `migrate_fix_transaction_signs.py` - Fixes transaction sign issues

## Running Migrations

All migrations support dry-run mode:

```bash
# Preview changes without applying
python migrate_<name>.py --dry-run

# Apply migration
python migrate_<name>.py
```

## Database Backups

Each migration automatically creates a timestamped backup:
- Format: `portfolio.db.backup_YYYYMMDD_HHMMSS`
- Location: `backend/` directory

## Troubleshooting

### Missing Columns Error
If you see errors like `no such column: exchange_rates.confidence`, run the appropriate migration script.

### Database Schema Mismatch
1. Stop all services: `.\stop.ps1`
2. Run the required migration
3. Restart services: `.\start.ps1`

### Migration Already Applied
Migrations check if columns already exist and skip them gracefully.
