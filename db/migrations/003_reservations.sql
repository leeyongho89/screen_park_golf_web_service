CREATE TABLE IF NOT EXISTS reservations (
    id BIGSERIAL PRIMARY KEY,
    bay_number INTEGER NOT NULL,
    member_id BIGINT REFERENCES members(id),
    customer_name VARCHAR(80) NOT NULL,
    customer_phone VARCHAR(30) NOT NULL,
    reservation_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT '예약',
    note TEXT,
    operator_name VARCHAR(80),
    canceled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_reservations_bay_number ON reservations (bay_number);
CREATE INDEX IF NOT EXISTS ix_reservations_member_id ON reservations (member_id);
CREATE INDEX IF NOT EXISTS ix_reservations_reservation_date ON reservations (reservation_date);
CREATE INDEX IF NOT EXISTS ix_reservations_status ON reservations (status);
CREATE INDEX IF NOT EXISTS ix_reservations_date_bay ON reservations (reservation_date, bay_number);
CREATE INDEX IF NOT EXISTS ix_reservations_date_status ON reservations (reservation_date, status);

UPDATE reservations SET status = '예약' WHERE status NOT IN ('예약', '취소');
