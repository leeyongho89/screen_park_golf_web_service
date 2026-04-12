CREATE TABLE IF NOT EXISTS sms_groups (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    operator_name VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sms_groups_name UNIQUE (name)
);

CREATE INDEX IF NOT EXISTS ix_sms_groups_name ON sms_groups (name);

CREATE TABLE IF NOT EXISTS sms_group_members (
    id BIGSERIAL PRIMARY KEY,
    sms_group_id BIGINT NOT NULL REFERENCES sms_groups(id) ON DELETE CASCADE,
    member_id BIGINT NOT NULL REFERENCES members(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sms_group_members_group_member UNIQUE (sms_group_id, member_id)
);

CREATE INDEX IF NOT EXISTS ix_sms_group_members_group ON sms_group_members (sms_group_id);
CREATE INDEX IF NOT EXISTS ix_sms_group_members_member ON sms_group_members (member_id);

ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS content_type VARCHAR(10) NOT NULL DEFAULT 'COMM';
ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(10) NOT NULL DEFAULT 'SMS';
ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS template_id BIGINT REFERENCES sms_templates(id);
ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS provider_name VARCHAR(40);
ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS target_summary JSONB;
ALTER TABLE sms_messages ADD COLUMN IF NOT EXISTS sync_completed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_sms_templates_is_active ON sms_templates (is_active);
CREATE INDEX IF NOT EXISTS ix_sms_messages_created_at ON sms_messages (created_at);
CREATE INDEX IF NOT EXISTS ix_sms_messages_status ON sms_messages (status);
CREATE INDEX IF NOT EXISTS ix_sms_message_recipients_message ON sms_message_recipients (sms_message_id);
CREATE INDEX IF NOT EXISTS ix_sms_message_recipients_phone ON sms_message_recipients (phone);
