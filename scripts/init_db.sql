CREATE TABLE feature_snapshots(
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    snapshot_ts BIGINT NOT NULL,
    days_since_last_active REAL NOT NULL,
    days_since_last_purchase REAL NOT NULL,
    days_since_last_support_ticket REAL NOT NULL,
    days_since_last_email_open REAL NOT NULL,
    days_since_last_discount REAL NOT NULL,
    days_since_last_feedback REAL NOT NULL,
    days_since_trial_end REAL NOT NULL,
    page_views_last_7d INT NOT NULL,
    page_views_last_30d INT NOT NULL,
    support_tickets_last_30d INT NOT NULL,
    email_opens_last_30d INT NOT NULL,
    total_purchases INT NOT NULL,
    total_support_tickets INT NOT NULL,
    total_discounts_used INT NOT NULL,
    total_feedback_submitted INT NOT NULL,
    total_password_resets INT NOT NULL,
    is_trial_user SMALLINT NOT NULL,
    avg_session_duration_mins REAL NOT NULL,
    label SMALLINT,
    labeled_at BIGINT,
    created_at TIMESTAMPZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_snapshot UNIQUE (user_id, snapshot_ts),
    CONSTRAINT chk_label CHECK (label IN (0, 1))
);

CREATE INDEX idx_unlabeled_ready
    ON feature_snapshots (snapshot_ts)
    WHERE label IS NULL;