-- =============================================================
-- 설비 가동 관리 (수기 기록)
--   ※ 1단계는 수기 입력만. PLC 태그맵(ICOM_PLC_ADDRESS_MAP) 미회수로
--     자동수집은 2단계. source 컬럼으로 전환 대비만 해 둔다.
-- =============================================================

do $$ begin
  -- RUN 가동 / SETUP 준비 / IDLE 대기 / DOWN 고장 / PLANNED_STOP 계획정지
  create type mes.machine_state as enum ('RUN', 'SETUP', 'IDLE', 'DOWN', 'PLANNED_STOP');
exception when duplicate_object then null; end $$;

-- 비가동 사유
create table if not exists mes.downtime_reasons (
  id          uuid primary key default gen_random_uuid(),
  code        text not null unique,
  name        text not null,
  category    text not null,                      -- 고장 / 준비 / 자재대기 / 품질 / 계획정지 / 기타
  is_planned  boolean not null default false,     -- 계획정지 = 가동률 분모에서 제외
  sort_order  int not null default 0,
  use_yn      boolean not null default true
);

-- 설비 상태 구간 로그
create table if not exists mes.machine_status_logs (
  id            uuid primary key default gen_random_uuid(),
  machine_id    uuid not null references mes.machines(id) on delete cascade,
  state         mes.machine_state not null,
  started_at    timestamptz not null default now(),
  ended_at      timestamptz,                      -- null = 현재 진행중
  reason_id     uuid references mes.downtime_reasons(id),
  head_id       uuid references mes.work_order_heads(id) on delete set null,
  worker_id     text,
  source        mes.actual_source not null default 'MANUAL',
  note          text,
  created_at    timestamptz not null default now(),
  constraint msl_period_chk check (ended_at is null or ended_at > started_at)
);

create index if not exists idx_msl_machine on mes.machine_status_logs(machine_id, started_at desc);
-- 설비당 진행중 구간은 1개만
create unique index if not exists uq_msl_open
  on mes.machine_status_logs(machine_id) where ended_at is null;

-- 상태 전환 : 진행중 구간을 닫고 새 구간을 연다 (한 트랜잭션)
create or replace function mes.change_machine_state(
  p_machine_id uuid,
  p_state      mes.machine_state,
  p_reason_id  uuid default null,
  p_head_id    uuid default null,
  p_worker_id  text default null,
  p_note       text default null
) returns uuid
language plpgsql as $$
declare
  v_now timestamptz := now();
  v_id  uuid;
begin
  update mes.machine_status_logs
     set ended_at = v_now
   where machine_id = p_machine_id and ended_at is null;

  insert into mes.machine_status_logs
    (machine_id, state, started_at, reason_id, head_id, worker_id, note)
  values
    (p_machine_id, p_state, v_now, p_reason_id, p_head_id, p_worker_id, p_note)
  returning id into v_id;

  return v_id;
end $$;

-- 설비별 일자 가동 집계 (가동률 = 가동 / (총시간 − 계획정지))
create or replace view mes.v_machine_daily as
select
  l.machine_id,
  (l.started_at at time zone 'Asia/Seoul')::date as work_date,
  round(sum(extract(epoch from (coalesce(l.ended_at, now()) - l.started_at)) / 3600.0)
        filter (where l.state = 'RUN')::numeric, 2)          as run_h,
  round(sum(extract(epoch from (coalesce(l.ended_at, now()) - l.started_at)) / 3600.0)
        filter (where l.state = 'SETUP')::numeric, 2)        as setup_h,
  round(sum(extract(epoch from (coalesce(l.ended_at, now()) - l.started_at)) / 3600.0)
        filter (where l.state = 'IDLE')::numeric, 2)         as idle_h,
  round(sum(extract(epoch from (coalesce(l.ended_at, now()) - l.started_at)) / 3600.0)
        filter (where l.state = 'DOWN')::numeric, 2)         as down_h,
  round(sum(extract(epoch from (coalesce(l.ended_at, now()) - l.started_at)) / 3600.0)
        filter (where l.state = 'PLANNED_STOP')::numeric, 2) as planned_stop_h
from mes.machine_status_logs l
group by 1, 2;

do $$
declare t text;
begin
  foreach t in array array['downtime_reasons', 'machine_status_logs'] loop
    execute format('alter table mes.%I enable row level security', t);
    execute format('drop policy if exists %I on mes.%I', t || '_auth_all', t);
    execute format(
      'create policy %I on mes.%I for all to authenticated using (true) with check (true)',
      t || '_auth_all', t);
  end loop;
end $$;

grant all on mes.downtime_reasons, mes.machine_status_logs to authenticated;
grant select on mes.v_machine_daily to authenticated;
grant execute on function mes.change_machine_state(uuid, mes.machine_state, uuid, uuid, text, text)
  to authenticated;
