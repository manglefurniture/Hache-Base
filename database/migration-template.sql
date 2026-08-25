-- Hache-Base migration template
-- File: YYYYMMDD_short_description.sql
-- Purpose: describe one small schema/data change.
-- Preconditions: document assumptions here.
-- Recovery: document whether backup restore or an inverse migration is required.

START TRANSACTION;

-- Add the smallest deterministic change possible.
-- Example only:
-- ALTER TABLE example_table ADD COLUMN example_flag TINYINT(1) NOT NULL DEFAULT 0;

-- Add post-change checks when the migration changes relationships or data.
-- If a deterministic repair cannot be guaranteed, fail and investigate instead of guessing.

COMMIT;
