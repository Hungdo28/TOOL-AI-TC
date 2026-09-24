-- =====================================================================
-- SCRIPT TAO BANG ai_jobs TREN SUPABASE
-- Chay script nay tren Supabase SQL Editor:
-- https://supabase.com/dashboard/project/_/sql
-- =====================================================================

-- 1. TAO BANG HANG DOI
CREATE TABLE IF NOT EXISTS public.ai_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name    TEXT NOT NULL,
    request_id   TEXT NOT NULL,
    username     TEXT NOT NULL DEFAULT '',
    mode         TEXT NOT NULL DEFAULT 'single',
    prompt_ai2   TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'queued'
                 CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_msg    TEXT
);

-- 2. INDEX DE WORKER LAY JOB NHANH (FIFO)
CREATE INDEX IF NOT EXISTS ai_jobs_status_created_at
    ON public.ai_jobs(status, created_at ASC);

-- 3. INDEX DE FE POLLING THEO requestId
CREATE INDEX IF NOT EXISTS ai_jobs_request_id
    ON public.ai_jobs(request_id);

-- 4. INDEX DE KIEM TRA TRUNG BAN (is_task_already_queued)
CREATE INDEX IF NOT EXISTS ai_jobs_task_name_status
    ON public.ai_jobs(task_name, status);

-- 5. BAT ROW LEVEL SECURITY (RLS) - BAO MAT
ALTER TABLE public.ai_jobs ENABLE ROW LEVEL SECURITY;

-- 6. POLICY: Backend (service role / anon key dung trong tool nay) duoc doc/ghi
-- Luu y: Tool nay dung anon key, nen can policy mo de backend hoat dong.
-- Neu muon bao mat hon, doi sang service_role key trong BE/.env
CREATE POLICY "allow_all_for_autotc_backend"
    ON public.ai_jobs
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- =====================================================================
-- KIEM TRA: Xem cau truc bang vua tao
-- =====================================================================
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'ai_jobs'
-- ORDER BY ordinal_position;

-- =====================================================================
-- DON DEP (neu can xoa va tao lai)
-- =====================================================================
-- DROP TABLE IF EXISTS public.ai_jobs;
