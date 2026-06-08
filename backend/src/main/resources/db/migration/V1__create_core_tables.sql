-- =============================================================================
-- V1 — Core tables
-- =============================================================================

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id            BIGSERIAL     PRIMARY KEY,
    email         VARCHAR(255)  UNIQUE NOT NULL,
    password_hash VARCHAR(255)  NOT NULL,
    name          VARCHAR(100),
    created_at    TIMESTAMP     DEFAULT NOW(),
    updated_at    TIMESTAMP     DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- resumes
-- ---------------------------------------------------------------------------
CREATE TABLE resumes (
    id                 BIGSERIAL      PRIMARY KEY,
    user_id            BIGINT         REFERENCES users(id) ON DELETE CASCADE,
    original_file_name VARCHAR(255)   NOT NULL,
    file_path          VARCHAR(500),
    parsed_data        JSONB          NOT NULL,
    raw_text           TEXT,
    parse_confidence   DECIMAL(3, 2),
    created_at         TIMESTAMP      DEFAULT NOW()
);

CREATE INDEX idx_resumes_user_id ON resumes(user_id);

-- ---------------------------------------------------------------------------
-- job_descriptions
-- ---------------------------------------------------------------------------
CREATE TABLE job_descriptions (
    id               BIGSERIAL      PRIMARY KEY,
    user_id          BIGINT         REFERENCES users(id) ON DELETE CASCADE,
    title            VARCHAR(255),
    company          VARCHAR(255),
    parsed_data      JSONB          NOT NULL,
    raw_text         TEXT,
    source_url       VARCHAR(1000),
    parse_confidence DECIMAL(3, 2),
    created_at       TIMESTAMP      DEFAULT NOW()
);

CREATE INDEX idx_job_descriptions_user_id ON job_descriptions(user_id);

-- ---------------------------------------------------------------------------
-- match_results
-- ---------------------------------------------------------------------------
CREATE TABLE match_results (
    id               BIGSERIAL    PRIMARY KEY,
    user_id          BIGINT       REFERENCES users(id) ON DELETE CASCADE,
    resume_id        BIGINT       REFERENCES resumes(id) ON DELETE CASCADE,
    jd_id            BIGINT       REFERENCES job_descriptions(id) ON DELETE CASCADE,
    overall_score    DECIMAL(5, 2),
    skill_score      DECIMAL(5, 2),
    experience_score DECIMAL(5, 2),
    keyword_score    DECIMAL(5, 2),
    gap_analysis     JSONB,
    created_at       TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX idx_match_results_user_id   ON match_results(user_id);
CREATE INDEX idx_match_results_resume_id ON match_results(resume_id);
CREATE INDEX idx_match_results_jd_id     ON match_results(jd_id);

-- ---------------------------------------------------------------------------
-- interview_sessions
-- ---------------------------------------------------------------------------
CREATE TABLE interview_sessions (
    id             BIGSERIAL    PRIMARY KEY,
    user_id        BIGINT       REFERENCES users(id) ON DELETE CASCADE,
    jd_id          BIGINT       REFERENCES job_descriptions(id) ON DELETE CASCADE,
    resume_id      BIGINT       REFERENCES resumes(id) ON DELETE CASCADE,
    status         VARCHAR(20)  DEFAULT 'active',
    question_count INT          DEFAULT 0,
    conversation   JSONB,
    review         JSONB,
    started_at     TIMESTAMP    DEFAULT NOW(),
    ended_at       TIMESTAMP
);

CREATE INDEX idx_interview_sessions_user_id ON interview_sessions(user_id);

-- ---------------------------------------------------------------------------
-- agent_runs
-- ---------------------------------------------------------------------------
CREATE TABLE agent_runs (
    id             BIGSERIAL     PRIMARY KEY,
    user_id        BIGINT        REFERENCES users(id) ON DELETE SET NULL,
    agent_name     VARCHAR(50)   NOT NULL,
    input_summary  VARCHAR(500),
    output_summary VARCHAR(500),
    status         VARCHAR(20)   DEFAULT 'success',
    duration_ms    INT,
    token_count    INT,
    model_name     VARCHAR(100),
    error_message  TEXT,
    created_at     TIMESTAMP     DEFAULT NOW()
);

CREATE INDEX idx_agent_runs_user_id    ON agent_runs(user_id);
CREATE INDEX idx_agent_runs_agent_name ON agent_runs(agent_name);
CREATE INDEX idx_agent_runs_created_at ON agent_runs(created_at);
