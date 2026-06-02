CREATE EXTENSION IF NOT EXISTS vector;

SELECT 'CREATE DATABASE ai_tutor_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ai_tutor_test')\gexec

\c ai_tutor_test
CREATE EXTENSION IF NOT EXISTS vector;
