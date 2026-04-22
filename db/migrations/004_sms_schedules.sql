ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ;
ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMPTZ;
ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE sms_message_recipients ADD COLUMN IF NOT EXISTS sms_agree BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE sms_message_recipients ADD COLUMN IF NOT EXISTS source_labels JSONB;

CREATE INDEX IF NOT EXISTS ix_sms_messages_scheduled_at ON sms_messages (scheduled_at);
CREATE INDEX IF NOT EXISTS ix_sms_messages_scheduled_status ON sms_messages (scheduled_at, status);
