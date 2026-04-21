-- Migration: 002_create_trace_tables.sql
-- Creates tables used by PostgresTraceStore (src/orchestrator_core/runtime/trace_pg.py)
-- Schema matches the exact production definition.

-- ── trace_runs ──────────────────────────────────────────────────────────────
-- One row per orchestrate() call (i.e. per conversation turn).
CREATE TABLE IF NOT EXISTS public.trace_runs (
    trace_id        TEXT        NOT NULL,
    user_id         TEXT        NULL,
    session_id      TEXT        NOT NULL,
    turn_id         TEXT        NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    request_payload JSONB       NULL,
    parsed_intent   JSONB       NULL,
    planned_tasks   JSONB       NULL,
    final_response  JSONB       NULL,
    status          TEXT        NULL DEFAULT 'started'::text,
    CONSTRAINT trace_runs_pkey PRIMARY KEY (trace_id)
);

CREATE INDEX IF NOT EXISTS idx_trace_runs_session ON public.trace_runs USING btree (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trace_runs_user    ON public.trace_runs USING btree (user_id, created_at DESC);


-- ── trace_events ─────────────────────────────────────────────────────────────
-- One row per tool/agent event within a run.
CREATE TABLE IF NOT EXISTS public.trace_events (
    id               BIGSERIAL                                       NOT NULL,
    trace_id         TEXT                                            NOT NULL,
    session_id       TEXT                                            NOT NULL,
    user_id          TEXT                                            NULL,
    turn_id          TEXT                                            NULL,
    task_id          TEXT                                            NULL,
    event_type       TEXT                                            NOT NULL,
    capability       TEXT                                            NULL,
    provider         TEXT                                            NULL,
    endpoint         TEXT                                            NULL,
    args_hash        TEXT                                            NULL,
    idempotency_key  TEXT                                            NULL,
    status           TEXT                                            NULL,
    latency_ms       INT4                                            NULL,
    request_payload  JSONB                                           NULL,
    response_payload JSONB                                           NULL,
    error            TEXT                                            NULL,
    created_at       TIMESTAMPTZ                                     NOT NULL DEFAULT now(),
    transport_type   VARCHAR(32)                                     NULL DEFAULT 'a2a_http'::character varying,
    CONSTRAINT trace_events_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_trace_events_args      ON public.trace_events USING btree (args_hash);
CREATE INDEX IF NOT EXISTS idx_trace_events_idem      ON public.trace_events USING btree (idempotency_key);
CREATE INDEX IF NOT EXISTS idx_trace_events_session   ON public.trace_events USING btree (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trace_events_trace     ON public.trace_events USING btree (trace_id, created_at);
CREATE INDEX IF NOT EXISTS idx_trace_events_transport ON public.trace_events USING btree (transport_type, capability, created_at);

-- Foreign key: trace_events → trace_runs (cascade delete)
ALTER TABLE public.trace_events
    ADD CONSTRAINT trace_events_trace_id_fkey
    FOREIGN KEY (trace_id) REFERENCES public.trace_runs(trace_id)
    ON DELETE CASCADE;

