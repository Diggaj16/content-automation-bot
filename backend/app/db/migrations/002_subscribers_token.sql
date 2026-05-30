-- backend/app/db/migrations/002_subscribers_token.sql
ALTER TABLE email_subscribers
ADD COLUMN IF NOT EXISTS unsubscribe_token TEXT UNIQUE DEFAULT gen_random_uuid()::TEXT;

UPDATE email_subscribers
SET unsubscribe_token = gen_random_uuid()::TEXT
WHERE unsubscribe_token IS NULL;
