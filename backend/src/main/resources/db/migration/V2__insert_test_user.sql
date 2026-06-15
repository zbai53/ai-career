-- Insert a default test user for development (id=1).
-- Reset the sequence so subsequent inserts start at 2 and avoid PK conflicts.
INSERT INTO users (id, email, password_hash, name)
VALUES (1, 'test@example.com', 'not-a-real-hash', 'Test User')
ON CONFLICT (id) DO NOTHING;

SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));
