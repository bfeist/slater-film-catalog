# LMOTM LTO.xls Integration Plan

## Executive Summary

The **LMOTM LTO.xls** file contains metadata for the "Last Month of Mission" Apollo 17 footage, stored in LTO tape format. Analysis shows:

- **43,271 total rows** (same as ApolloReelsMaster.xlsx Master List)
- **16,419 FR- identifiers** (nearly identical to Apollo database)
- **26,850 non-FR identifiers** (JSCmSTS*, JSCm*, BRF\*, etc.)
- **Only 1 unique FR** not in Apollo database: `FR-0319-A`
- **11,424 rows with VideoFile references** (L-number patterns)
- **Dates stored as Excel serial numbers** (e.g., 32569.0 = 1989-04-18)

**Key Finding**: LMOTM and ApolloReelsMaster.xlsx contain **nearly identical FR datasets** with different metadata columns. This is NOT additional content but rather a **different view/index of the same content**.

---

## Data Structure Comparison

### LMOTM LTO.xls Columns

| Column     | Type         | Description                               |
| ---------- | ------------ | ----------------------------------------- |
| Identifier | Text         | FR-XXXX, AK-XXX, JSCmSTS\*, etc.          |
| Title      | Text         | Content description/title                 |
| Date       | Excel Serial | Excel date serial (e.g., 32569.0)         |
| VideoFile  | Text         | L-number reference (e.g., L000881/AK-001) |

### ApolloReelsMaster.xlsx Master List Columns (relevant)

| Column       | Type | Description                  |
| ------------ | ---- | ---------------------------- |
| Identifier   | Text | FR-XXXX, AK-XXX, etc.        |
| Concat Title | Text | Combined title               |
| Orig Title   | Text | Original catalog title       |
| Date         | Date | ISO date format              |
| VideoFile    | Text | L-number reference           |
| MOCR LTO#    | Text | LTO tape number              |
| Description  | Text | Content description          |
| Feet         | Text | Film length                  |
| Minutes      | Text | Duration                     |
| Audio        | Text | Recording type (SOF/SIL/MOS) |

---

## Integration Strategy

### Approach: **Non-Destructive Merge with LMOTM as Source**

Since LMOTM has **different metadata** (not just duplicates), we should:

1. **Keep existing Apollo data intact** (no overwrites)
2. **Add LMOTM-specific columns** to existing tables
3. **Track data provenance** with source_tab field
4. **Use COALESCE logic** to prefer Apollo data (more complete) but fill gaps with LMOTM

### Why This Approach?

- ✅ **Non-destructive**: Apollo data remains unchanged
- ✅ **Comprehensive**: Combines best of both sources
- ✅ **Traceable**: Can query which source provided which data
- ✅ **Scalable**: Easy to add more source files later

---

## Database Schema Changes

### Option A: Extend Existing Tables (Recommended)

Add LMOTM-specific columns to existing tables:

#### film_rolls table - Add columns:

```sql
ALTER TABLE film_rolls ADD COLUMN lmotm_title TEXT;
ALTER TABLE film_rolls ADD COLUMN lmotm_date_serial TEXT;
ALTER TABLE film_rolls ADD COLUMN lmotm_source_tab TEXT DEFAULT 'lmotm_lto';
```

#### transfers table - Already has source_tab, just use new value:

```sql
-- No schema change needed
-- Just insert with source_tab='lmotm_lto'
```

### Option B: Create LMOTM-Specific Table

Create a new table for LMOTM-only data:

```sql
CREATE TABLE IF NOT EXISTS lmotm_lto (
    identifier      TEXT PRIMARY KEY,
    title           TEXT,
    date_serial     TEXT,
    video_file_ref  TEXT,
    FOREIGN KEY (identifier) REFERENCES film_rolls(identifier)
);
```

**Recommendation**: Use **Option A** for simplicity and better query performance.

---

## Implementation Plan

### Phase 1: Create New Ingestion Script

Create `scripts/1d_ingest_lmotm.py`:

```python
"""
Stage 1d: Ingest LMOTM LTO.xls into existing database.

Merges LMOTM data non-destructively with Apollo data.
"""

import argparse
import sqlite3
import xlrd
from datetime import datetime

DB_PATH = "database/catalog.db"
LMOTM_PATH = "input_indexes/LMOTM LTO.xls"

def convert_excel_serial_date(serial_str: str) -> str | None:
    """Convert Excel serial date to ISO format."""
    if not serial_str:
        return None
    try:
        serial = float(serial_str)
        # Excel epoch is Dec 30, 1899
        dt = datetime(1899, 12, 30) + datetime.timedelta(days=serial)
        return dt.strftime("%Y-%m-%d")
    except:
        return None

def ingest_lmotm(db: sqlite3.Connection):
    """Ingest LMOTM data non-destructively."""
    wb = xlrd.open_workbook(LMOTM_PATH)
    ws = wb.sheet_by_name("LMOTM_LTO")

    updated = 0
    inserted = 0

    for row_idx in range(1, ws.nrows):
        row = ws.row_values(row_idx)
        if not row or not row[0]:
            continue

        identifier = str(row[0]).strip()
        title = str(row[1]).strip() if row[1] else None
        date_serial = str(row[2]).strip() if row[2] else None
        video_file = str(row[3]).strip() if row[3] else None

        # Convert date
        date_iso = convert_excel_serial_date(date_serial)

        # Update film_rolls with LMOTM data (non-destructive)
        # Use COALESCE to prefer existing Apollo data
        db.execute("""
            UPDATE film_rolls SET
                lmotm_title = COALESCE(lmotm_title, ?),
                lmotm_date_serial = COALESCE(lmotm_date_serial, ?),
                lmotm_source_tab = 'lmotm_lto'
            WHERE identifier = ?
        """, (title, date_serial, identifier))

        if db.execute("SELECT changes()").fetchone()[0] > 0:
            updated += 1

        # Insert new FRs not in Apollo
        if db.execute("SELECT 1 FROM film_rolls WHERE identifier = ?", (identifier,)).fetchone() is None:
            db.execute("""
                INSERT INTO film_rolls (
                    identifier, id_prefix, title, lmotm_title,
                    lmotm_date_serial, lmotm_source_tab, rowid_excel
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                identifier,
                extract_id_prefix(identifier),
                None,  # title (Apollo doesn't have this)
                title,
                date_serial,
                'lmotm_lto',
                row_idx
            ))
            inserted += 1

        # Add VideoFile as transfer if present
        if video_file:
            # Extract L-number and reel identifier
            l_number = video_file.split('/')[0] if '/' in video_file else video_file

            # Check if transfer already exists
            existing = db.execute("""
                SELECT 1 FROM transfers
                WHERE reel_identifier = ?
                AND source_tab = 'lmotm_lto'
                AND video_file_ref = ?
            """, (identifier, video_file)).fetchone()

            if not existing:
                db.execute("""
                    INSERT INTO transfers (
                        reel_identifier, transfer_type, source_tab,
                        video_file_ref, lto_number
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    identifier,
                    'lmotm_lto',
                    'lmotm_lto',
                    video_file,
                    l_number if l_number.startswith('L') else None
                ))

    db.commit()
    return updated, inserted

def main():
    parser = argparse.ArgumentParser(description="Ingest LMOTM LTO.xls")
    parser.add_argument("--stats", action="store_true", help="Print stats only")
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH)

    if args.stats:
        # Print current stats
        print(f"LMOTM rows: {db.execute('SELECT COUNT(*) FROM film_rolls WHERE lmotm_source_tab = ?').fetchone()[0]}")
        print(f"LMOTM transfers: {db.execute('SELECT COUNT(*) FROM transfers WHERE source_tab = ?').fetchone()[0]}")
        return

    # Ingest
    updated, inserted = ingest_lmotm(db)
    print(f"Updated: {updated}, Inserted: {inserted}")

    db.close()

if __name__ == "__main__":
    main()
```

### Phase 2: Add Schema Migration

Create `scripts/migrate_add_lmotm_columns.py`:

```python
"""
Add LMOTM-specific columns to existing database.
"""

import sqlite3

DB_PATH = "database/catalog.db"

def migrate():
    db = sqlite3.connect(DB_PATH)

    # Add columns to film_rolls
    db.execute("""
        ALTER TABLE film_rolls ADD COLUMN lmotm_title TEXT;
        ALTER TABLE film_rolls ADD COLUMN lmotm_date_serial TEXT;
        ALTER TABLE film_rolls ADD COLUMN lmotm_source_tab TEXT DEFAULT 'lmotm_lto';
    """)

    # Add manifest entry
    db.execute("""
        INSERT OR REPLACE INTO _manifest (key, value) VALUES ('lmotm_schema_version', '1')
    """)

    db.commit()
    db.close()
    print("Migration complete")

if __name__ == "__main__":
    migrate()
```

### Phase 3: Update Verification Script

Update `scripts/1c_verify_transfers.py` to include LMOTM transfers in verification.

---

## Data Quality Notes

### Date Format

- LMOTM uses **Excel serial dates** (e.g., 32569.0)
- Apollo uses **ISO dates** (e.g., 1969-07-20)
- Need conversion: `datetime(1899, 12, 30) + timedelta(days=serial)`

### Identifier Formats

LMOTM contains:

- **FR-XXXX** (numeric): 9,820 rows
- **FR-XXX** (alpha): 6,344 rows
- **FR-XXX** (mixed): 255 rows
- **JSCmSTS\***: Many rows (Shuttle program)
- **JSCm\***: Many rows (various programs)
- **BRF\***: Some rows
- **S\***: Some rows

**Note**: LMOTM contains **Shuttle program data** (JSCmSTS\*) which is outside Apollo scope. These should be filtered or handled separately.

### VideoFile References

- **11,424 rows** have VideoFile references
- Format: `L######/REEL-ID` (e.g., L000881/AK-001)
- Maps to MPEG-2 files on `/o/MPEG-2/`
- Same format as Apollo Master List

---

## Testing & Validation

### Pre-Migration Checks

```sql
-- Check current counts
SELECT COUNT(*) FROM film_rolls;
SELECT COUNT(*) FROM transfers;

-- Check for FR-0319-A (unique LMOTM FR)
SELECT * FROM film_rolls WHERE identifier = 'FR-0319-A';
```

### Post-Migration Validation

```sql
-- Check LMOTM data was added
SELECT COUNT(*) FROM film_rolls WHERE lmotm_source_tab = 'lmotm_lto';
SELECT COUNT(*) FROM transfers WHERE source_tab = 'lmotm_lto';

-- Check unique FR was added
SELECT * FROM film_rolls WHERE identifier = 'FR-0319-A';

-- Verify no Apollo data was overwritten
SELECT COUNT(*) FROM film_rolls WHERE lmotm_title IS NOT NULL AND title IS NULL;
-- Should be 0 (no Apollo data lost)

-- Check date conversion
SELECT identifier, lmotm_date_serial,
       datetime(lmotm_date_serial + 25569, 'unixepoch') as converted_date
FROM film_rolls
WHERE lmotm_date_serial IS NOT NULL
LIMIT 10;
```

---

## Rollback Plan

If issues arise:

```sql
-- Remove LMOTM data
UPDATE film_rolls SET
    lmotm_title = NULL,
    lmotm_date_serial = NULL,
    lmotm_source_tab = NULL;

DELETE FROM transfers WHERE source_tab = 'lmotm_lto';

-- Drop columns (SQLite requires recreate table - see migration guide)
```

---

## Next Steps

1. ✅ **Analysis complete** - LMOTM and Apollo are nearly identical FR sets
2. ⏳ **Create migration script** - Add LMOTM columns to schema
3. ⏳ **Create ingestion script** - `1d_ingest_lmotm.py`
4. ⏳ **Test on backup** - Run on copy of database first
5. ⏳ **Run full migration** - Apply to production database
6. ⏳ **Validate results** - Run verification queries
7. ⏳ **Update documentation** - Document new schema and data sources

---

## Files to Create/Modify

### New Files

- `scripts/1d_ingest_lmotm.py` - Main ingestion script
- `scripts/migrate_add_lmotm_columns.py` - Schema migration
- `docs/lmotm-integration-plan.md` - This document

### Modified Files

- `scripts/1b_ingest_excel.py` - Add LMOTM to manifest/stats
- `scripts/1c_verify_transfers.py` - Include LMOTM in verification
- `database/catalog.db` - Updated schema + data

---

## Timeline Estimate

- **Schema migration**: 30 minutes
- **Ingestion script**: 2 hours
- **Testing**: 1 hour
- **Full migration**: 5 minutes (43k rows is small)
- **Validation**: 30 minutes

**Total**: ~4 hours including testing

---

## Risks & Mitigations

| Risk                       | Impact          | Mitigation                      |
| -------------------------- | --------------- | ------------------------------- |
| Date conversion errors     | Incorrect dates | Test conversion on sample first |
| Overwriting Apollo data    | Data loss       | Use COALESCE, test on backup    |
| Shuttle data contamination | Scope creep     | Filter JSCmSTS\* rows if needed |
| Performance issues         | Slow migration  | Use transactions, batch inserts |

---

## Appendix: Sample Data

### LMOTM Sample Rows

```
Identifier    | Title                                          | Date      | VideoFile
--------------|------------------------------------------------|-----------|------------------
0-8903-01     | OV-105 Update: Mid Fuselage...                 | 32569.0   |
0-8904-01     | Main landing gear door installation...         | 32599.0   |
FR-1524       | [Apollo content]                               | [date]    | L000881/AK-001
```

### Date Conversion Examples

```
32569.0 → 1989-04-18 (Shuttle OV-105)
32599.0 → 1989-05-18
33256.0 → 1991-01-15
```
