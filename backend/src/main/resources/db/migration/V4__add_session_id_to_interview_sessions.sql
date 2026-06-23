-- =============================================================================
-- V4 — Add Python session_id to interview_sessions
-- =============================================================================
ALTER TABLE interview_sessions
    ADD COLUMN session_id VARCHAR(100) UNIQUE;

CREATE INDEX idx_interview_sessions_session_id ON interview_sessions(session_id);
