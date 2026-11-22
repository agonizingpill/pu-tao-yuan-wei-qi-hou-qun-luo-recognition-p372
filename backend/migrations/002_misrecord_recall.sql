CREATE TABLE IF NOT EXISTS sample_misrecord (
    sample_id integer PRIMARY KEY REFERENCES microclimate_sample(id),
    reason text NOT NULL,
    actor text NOT NULL REFERENCES account(username),
    recorded_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE climate_run DROP CONSTRAINT IF EXISTS climate_run_status_check;
ALTER TABLE climate_run ADD CONSTRAINT climate_run_status_check
    CHECK (status IN ('blocked', 'queued', 'effective', 'review', 'rejected', 'failed', 'recalled'));
ALTER TABLE climate_run ADD COLUMN IF NOT EXISTS recall jsonb;
ALTER TABLE climate_label DROP CONSTRAINT IF EXISTS climate_label_state_check;
ALTER TABLE climate_label ADD CONSTRAINT climate_label_state_check
    CHECK (state IN ('proposed', 'active', 'superseded', 'rejected', 'recalled'));
