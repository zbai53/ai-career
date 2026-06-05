CREATE TABLE IF NOT EXISTS app_health_check (
    id         SERIAL PRIMARY KEY,
    checked_at TIMESTAMP DEFAULT NOW()
);
