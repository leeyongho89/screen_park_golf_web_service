CREATE TABLE IF NOT EXISTS members (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    birth_date DATE,
    gender VARCHAR(20),
    email VARCHAR(160),
    address VARCHAR(300),
    sms_agree BOOLEAN NOT NULL DEFAULT TRUE,
    memo TEXT,
    last_visit_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_members_active_phone ON members (phone) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS ix_members_name ON members (name);
CREATE INDEX IF NOT EXISTS ix_members_phone ON members (phone);

CREATE TABLE IF NOT EXISTS membership_products (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    product_type VARCHAR(30) NOT NULL,
    duration_days INTEGER,
    total_count INTEGER,
    price NUMERIC(12, 0) NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_membership_products_name_type UNIQUE (name, product_type)
);

CREATE INDEX IF NOT EXISTS ix_membership_products_type ON membership_products (product_type);

CREATE TABLE IF NOT EXISTS member_memberships (
    id BIGSERIAL PRIMARY KEY,
    member_id BIGINT NOT NULL REFERENCES members(id),
    product_id BIGINT REFERENCES membership_products(id),
    start_date DATE NOT NULL,
    end_date DATE,
    duration_type VARCHAR(30),
    duration_days INTEGER,
    total_count INTEGER,
    remaining_count INTEGER,
    status VARCHAR(30) NOT NULL DEFAULT '사용중',
    sold_price NUMERIC(12, 0) NOT NULL DEFAULT 0,
    source_sale_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_member_memberships_member_id ON member_memberships (member_id);
CREATE INDEX IF NOT EXISTS ix_member_memberships_status ON member_memberships (status);
CREATE INDEX IF NOT EXISTS ix_member_memberships_end_date ON member_memberships (end_date);

CREATE TABLE IF NOT EXISTS sales (
    id BIGSERIAL PRIMARY KEY,
    member_id BIGINT REFERENCES members(id),
    member_name_snapshot VARCHAR(80),
    member_phone_snapshot VARCHAR(30),
    sale_type VARCHAR(120) NOT NULL,
    payment_method VARCHAR(30) NOT NULL,
    amount NUMERIC(12, 0) NOT NULL,
    sale_date DATE NOT NULL,
    related_membership_id BIGINT REFERENCES member_memberships(id),
    duration_type VARCHAR(30),
    duration_days INTEGER,
    coupon_count INTEGER,
    status VARCHAR(30) NOT NULL DEFAULT '정상',
    original_sale_id BIGINT REFERENCES sales(id),
    note TEXT,
    operator_name VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    refunded_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE member_memberships
    ADD CONSTRAINT fk_member_memberships_source_sale
    FOREIGN KEY (source_sale_id) REFERENCES sales(id);

CREATE INDEX IF NOT EXISTS ix_sales_member_id ON sales (member_id);
CREATE INDEX IF NOT EXISTS ix_sales_sale_date ON sales (sale_date);
CREATE INDEX IF NOT EXISTS ix_sales_sale_type ON sales (sale_type);
CREATE INDEX IF NOT EXISTS ix_sales_payment_method ON sales (payment_method);
CREATE INDEX IF NOT EXISTS ix_sales_status ON sales (status);

CREATE TABLE IF NOT EXISTS membership_usage_logs (
    id BIGSERIAL PRIMARY KEY,
    member_membership_id BIGINT NOT NULL REFERENCES member_memberships(id),
    member_id BIGINT NOT NULL REFERENCES members(id),
    action_type VARCHAR(30) NOT NULL,
    change_count INTEGER,
    before_remaining_count INTEGER,
    after_remaining_count INTEGER,
    note TEXT,
    operator_name VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_membership_usage_logs_membership ON membership_usage_logs (member_membership_id);
CREATE INDEX IF NOT EXISTS ix_membership_usage_logs_member ON membership_usage_logs (member_id);

CREATE TABLE IF NOT EXISTS sms_messages (
    id BIGSERIAL PRIMARY KEY,
    target_type VARCHAR(30),
    title VARCHAR(160),
    content TEXT,
    target_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT '대기',
    provider_request_id VARCHAR(160),
    sent_at TIMESTAMPTZ,
    operator_name VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sms_message_recipients (
    id BIGSERIAL PRIMARY KEY,
    sms_message_id BIGINT NOT NULL REFERENCES sms_messages(id),
    member_id BIGINT REFERENCES members(id),
    recipient_name VARCHAR(80),
    phone VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT '대기',
    provider_message_id VARCHAR(160),
    fail_code VARCHAR(80),
    fail_reason TEXT,
    sent_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sms_templates (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(160) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    operator_name VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    category VARCHAR(80),
    file_name VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(160),
    is_hidden BOOLEAN NOT NULL DEFAULT FALSE,
    hidden_at TIMESTAMPTZ,
    hidden_by_name VARCHAR(80),
    uploader_name VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_name VARCHAR(80),
    action_type VARCHAR(60) NOT NULL,
    target_type VARCHAR(60) NOT NULL,
    target_id BIGINT,
    before_data JSONB,
    after_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO membership_products (name, product_type, duration_days, total_count, price)
VALUES
    ('1개월 정기권', '기간제', 30, NULL, 0),
    ('10회 쿠폰', '횟수', 30, 10, 0),
    ('타석 이용료', '판매', NULL, NULL, 0)
ON CONFLICT (name, product_type) DO NOTHING;
