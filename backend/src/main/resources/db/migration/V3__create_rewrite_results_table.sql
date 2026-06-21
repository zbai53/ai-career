-- =============================================================================
-- V3 — Rewrite results table
-- =============================================================================

CREATE TABLE rewrite_results (
    id               BIGSERIAL     PRIMARY KEY,
    user_id          BIGINT        REFERENCES users(id) ON DELETE SET NULL,
    resume_id        BIGINT        REFERENCES resumes(id) ON DELETE CASCADE,
    jd_id            BIGINT        REFERENCES job_descriptions(id) ON DELETE CASCADE,
    match_result_id  BIGINT        REFERENCES match_results(id) ON DELETE SET NULL,
    rewrite_data     JSONB         NOT NULL,
    fidelity_score   DECIMAL(4, 3),
    rewrite_attempts INT,
    fidelity_status  VARCHAR(20),
    created_at       TIMESTAMP     DEFAULT NOW()
);

CREATE INDEX idx_rewrite_results_user_id   ON rewrite_results(user_id);
CREATE INDEX idx_rewrite_results_resume_id ON rewrite_results(resume_id);
CREATE INDEX idx_rewrite_results_jd_id     ON rewrite_results(jd_id);
