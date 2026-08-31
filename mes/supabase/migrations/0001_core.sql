-- =============================================================
-- 정원철강 통합전산 MES — 1단계 스키마
--   근거 : 인피니티21 P-MES 회수 스키마 (IPLN_JW_WORK_ORDER_HEAD /
--          IPLN_JW_WORK_ORDER_SPEC / IPLN_WORK_ORDER_MASTER / JW_*)
--   범위 : 작업지시 등록 · 작업지시서 출력 · 실적 입력 (수기)
--   원칙 : 계산식 하드코딩 금지 / attribute 범용컬럼 금지 / MAX+1 채번 금지
-- =============================================================

create schema if not exists mes;

-- ---------- 열거형 -------------------------------------------
do $$ begin
  -- 작업구분 : SL 슬리팅 / SH 시어링(절단)
  create type mes.order_div as enum ('SL', 'SH');
exception when duplicate_object then null; end $$;

do $$ begin
  create type mes.wo_status as enum ('PLANNED', 'RELEASED', 'IN_PROGRESS', 'DONE', 'CANCELED');
exception when duplicate_object then null; end $$;

do $$ begin
  -- 실적 출처. 2단계(PLC 자동수집) 전환 시 화면 변경 없이 AUTO 가 들어온다.
  create type mes.actual_source as enum ('MANUAL', 'AUTO');
exception when duplicate_object then null; end $$;

do $$ begin
  -- TOP/END 와 스크랩은 옛 MES 와 동일하게 한 테이블에서 구분자로 관리
  create type mes.topend_div as enum ('T', 'S');
exception when duplicate_object then null; end $$;

-- =============================================================
-- 기준정보
-- =============================================================

-- 설비 (ICOM_MACHINE 축약)
create table if not exists mes.machines (
  id          uuid primary key default gen_random_uuid(),
  code        text not null unique,                -- MACHINE_CODE
  name        text not null,                       -- MACHINE_NAME
  order_div   mes.order_div not null,              -- 이 설비가 처리하는 작업구분
  spec        text,                                -- MACHINE_SPEC
  sort_order  int  not null default 0,
  use_yn      boolean not null default true,
  created_at  timestamptz not null default now()
);

-- 고객사 (JW_CUST_MASTER)
create table if not exists mes.customers (
  id          uuid primary key default gen_random_uuid(),
  code        text not null unique,
  name        text not null,
  busin_no    text,
  repre_nm    text,
  tel_no      text,
  use_yn      boolean not null default true
);

-- 철판종류 : 옛 MES 는 품목마스터 attribute05 에 넣어 썼다. 정식 테이블로 승격.
create table if not exists mes.plate_types (
  id          uuid primary key default gen_random_uuid(),
  code        text not null unique,                -- HR / CR / GI / EGI / PO ...
  name        text not null,
  density     numeric(6,3) not null default 7.85,  -- 비중 (중량계산 입력값)
  sort_order  int not null default 0,
  use_yn      boolean not null default true
);

-- 품목 (제품 / 스크랩 / 코일)
create table if not exists mes.items (
  id             uuid primary key default gen_random_uuid(),
  code           text not null unique,
  name           text not null,
  spec           text,
  item_class     text not null default 'PRODUCT',  -- PRODUCT / SCRAP / COIL
  plate_type_id  uuid references mes.plate_types(id),
  unit           text not null default 'EA',
  use_yn         boolean not null default true,
  constraint items_class_chk check (item_class in ('PRODUCT', 'SCRAP', 'COIL'))
);

-- 코일 마스터 (JW_COIL_MASTER)
create table if not exists mes.coils (
  id             uuid primary key default gen_random_uuid(),
  coil_no        text not null unique,
  lot_no         text,
  item_id        uuid references mes.items(id),
  plate_type_id  uuid references mes.plate_types(id),
  material_name  text,                              -- 재질 (SS400, SPHC ...)
  thickness_mm   numeric(8,2) not null,
  width_mm       numeric(8,2) not null,
  weight_kg      numeric(12,2) not null,
  remain_kg      numeric(12,2),                     -- 잔량 (되감기/부분투입 대응)
  location       text,                              -- COIL_LOCATION
  stock_div_nm   text,                              -- 재고구분
  received_on    date,
  use_yn         boolean not null default true,
  created_at     timestamptz not null default now()
);
create index if not exists idx_coils_no on mes.coils(coil_no);

-- =============================================================
-- 계산공식 설정  ★ 계산식을 코드에 하드코딩하지 않기 위한 테이블
--   method : 배분 알고리즘 종류 (앱의 계산 엔진에 등록된 키)
--   params : 비중·반올림 자리수 등 파라미터. 현장 확인 후 값만 교체 가능.
-- =============================================================
create table if not exists mes.calc_formulas (
  id          uuid primary key default gen_random_uuid(),
  code        text not null unique,                 -- IPLN_JW_WORK_ORDER_HEAD.FORMULA 대응
  name        text not null,
  order_div   mes.order_div,                        -- null = 공통
  method      text not null,                        -- WIDTH_PRORATA / EQUAL_WEIGHT
  params      jsonb not null default '{}'::jsonb,
  is_default  boolean not null default false,
  description text,
  use_yn      boolean not null default true
);
comment on table mes.calc_formulas is
  '단중/로스/스크랩 계산 파라미터. 옛 MES 의 UF_JW_*_WEIGHT_NEW 계열 함수는 회수하지 못했으므로 현장 확인 후 값을 확정한다.';

-- =============================================================
-- 작업지시 채번  ★ MAX+1 금지 — 날짜/구분별 카운터 행 잠금
--   형식 : YYMMDD + 구분(2) + 순번(3)   예) 260831SL001
-- =============================================================
create table if not exists mes.wo_no_counters (
  wo_date    date not null,
  order_div  mes.order_div not null,
  last_seq   int not null default 0,
  primary key (wo_date, order_div)
);

create or replace function mes.next_wo_no(p_date date, p_div mes.order_div)
returns text
language plpgsql
as $$
declare
  v_seq int;
begin
  insert into mes.wo_no_counters (wo_date, order_div, last_seq)
       values (p_date, p_div, 1)
  on conflict (wo_date, order_div)
       do update set last_seq = mes.wo_no_counters.last_seq + 1
    returning last_seq into v_seq;

  return to_char(p_date, 'YYMMDD') || p_div::text || lpad(v_seq::text, 3, '0');
end $$;

-- =============================================================
-- 작업지시 — 헤드 (코일 단위)   ← IPLN_JW_WORK_ORDER_HEAD
-- =============================================================
create table if not exists mes.work_order_heads (
  id                uuid primary key default gen_random_uuid(),
  wo_no             text not null unique,
  order_div         mes.order_div not null,
  status            mes.wo_status not null default 'PLANNED',
  work_order_date   date not null,                  -- 작업지시일 (필수)

  -- 코일 / 원소재 (등록 시점 스냅샷 — 마스터가 바뀌어도 지시는 불변)
  coil_id           uuid references mes.coils(id),
  coil_no           text not null,                  -- 필수
  lot_no            text,
  plate_type_id     uuid references mes.plate_types(id),
  material_name     text,
  coil_width_mm     numeric(8,2) not null,
  coil_thickness_mm numeric(8,2) not null,
  coil_weight_kg    numeric(12,2) not null,
  coil_location     text,

  customer_id       uuid not null references mes.customers(id),   -- 필수
  machine_id        uuid not null references mes.machines(id),    -- 필수
  work_shift        text not null,                                -- 필수 (1 주간 / 2 야간)
  worker_id         text,

  formula_id        uuid references mes.calc_formulas(id),

  -- 자동 계산 결과 (조회 성능용 스냅샷 — 계산 원본은 명세/행)
  product_width_sum numeric(10,2),                  -- Σ(제품폭 × 절수)
  loss_mm           numeric(10,2),                  -- 코일폭 − 제품폭합계
  height_mm         numeric(12,2),                  -- 길이(세로)
  scrap_weight_kg   numeric(12,2),
  top_end_weight_kg numeric(12,2),

  -- 실적 롤업
  plan_qty          numeric(14,2) not null default 0,
  actual_qty        numeric(14,2) not null default 0,
  good_qty          numeric(14,2) not null default 0,
  bad_qty           numeric(14,2) not null default 0,
  bad_weight_kg     numeric(14,2) not null default 0,

  -- 되감기(소재환원)
  rewind_date       date,
  rewind_width_mm   numeric(8,2),
  rewind_weight_kg  numeric(12,2),

  special_note      text,                           -- 작업지시서 특기사항
  bigo              text,
  printed_at        timestamptz,
  print_count       int not null default 0,

  created_by        text,
  created_at        timestamptz not null default now(),
  updated_by        text,
  updated_at        timestamptz not null default now(),

  constraint wo_shift_chk check (work_shift in ('1', '2'))
);

create index if not exists idx_woh_date    on mes.work_order_heads(work_order_date desc);
create index if not exists idx_woh_machine on mes.work_order_heads(machine_id, work_order_date);
create index if not exists idx_woh_status  on mes.work_order_heads(status);
create index if not exists idx_woh_coil    on mes.work_order_heads(coil_no);

-- =============================================================
-- 작업지시 — 가공 명세   ← IPLN_JW_WORK_ORDER_SPEC
--   "어떻게 자를지" : 폭 / 절수 / 분할 을 proc_seq 순번으로
-- =============================================================
create table if not exists mes.work_order_specs (
  id        uuid primary key default gen_random_uuid(),
  head_id   uuid not null references mes.work_order_heads(id) on delete cascade,
  proc_seq  int not null,
  width_mm  numeric(8,2) not null,
  cut       int not null default 1,                 -- 절수
  divide    int not null default 1,                 -- 분할
  unique (head_id, proc_seq),
  constraint spec_cut_chk    check (cut >= 1),
  constraint spec_divide_chk check (divide >= 1)
);

-- =============================================================
-- 작업지시 — 지시 행 (제품별 지시 + 실적)  ← IPLN_WORK_ORDER_MASTER
--   84컬럼 중 1단계에 필요한 것만 옮겼다.
-- =============================================================
create table if not exists mes.work_order_lines (
  id              uuid primary key default gen_random_uuid(),
  head_id         uuid not null references mes.work_order_heads(id) on delete cascade,
  spec_id         uuid references mes.work_order_specs(id) on delete set null,
  line_seq        int not null,

  item_id         uuid references mes.items(id),
  item_code       text,                             -- 스냅샷
  item_name       text,
  item_spec       text,

  width_mm        numeric(8,2) not null,
  cut             int not null default 1,
  divide          int not null default 1,

  -- 계획
  plan_qty        numeric(14,2) not null,           -- 계획수량 ≥ 1
  unit_weight_kg  numeric(14,4),                    -- 단중 (자동계산)
  plan_weight_kg  numeric(14,2),                    -- 단중 × 계획수량
  height_mm       numeric(12,2),                    -- 길이(세로)

  -- 실적 (수기 입력)
  actual_qty      numeric(14,2) not null default 0,
  good_qty        numeric(14,2) not null default 0,
  bad_qty         numeric(14,2) not null default 0,
  bad_weight_kg   numeric(14,2) not null default 0,
  good_weight_kg  numeric(14,2) not null default 0,
  grade           text,                             -- 등급 (실적 입력 시 필수)
  bad_reason      text,
  banding_qty     numeric(14,2),
  work_date       date,
  start_time      char(4),                          -- HHMM
  end_time        char(4),                          -- HHMM
  actual_source   mes.actual_source not null default 'MANUAL',
  completion      boolean not null default false,
  note            text,

  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),

  unique (head_id, line_seq),
  constraint line_plan_qty_chk  check (plan_qty >= 1),
  constraint line_actual_chk    check (actual_qty <= plan_qty),
  constraint line_start_time_chk check (
    start_time is null or (start_time ~ '^([01][0-9]|2[0-3])[0-5][0-9]$')),
  constraint line_end_time_chk check (
    end_time is null or (end_time ~ '^([01][0-9]|2[0-3])[0-5][0-9]$'))
);

create index if not exists idx_wol_head on mes.work_order_lines(head_id);
create index if not exists idx_wol_date on mes.work_order_lines(work_date);

-- =============================================================
-- TOP/END · 스크랩 실적   ← JW_ACTUAL_TOPEND
-- =============================================================
create table if not exists mes.actual_topends (
  id             uuid primary key default gen_random_uuid(),
  head_id        uuid not null references mes.work_order_heads(id) on delete cascade,
  actual_seq     int not null,
  topend_div     mes.topend_div not null,           -- T: TOP/END, S: 스크랩
  item_id        uuid references mes.items(id),     -- 스크랩 입력 시 필수
  thickness_mm   numeric(8,2),
  height_mm      numeric(12,2),
  qty            numeric(14,2) not null default 0,
  weight_kg      numeric(14,2) not null default 0,
  actual_source  mes.actual_source not null default 'MANUAL',
  note           text,
  created_at     timestamptz not null default now(),
  unique (head_id, actual_seq),
  -- 스크랩(S)은 스크랩 품목이 반드시 있어야 한다
  constraint topend_scrap_item_chk check (topend_div <> 'S' or item_id is not null)
);

-- =============================================================
-- 검증 규칙 — 옛 MES 소스에서 그대로 이관
-- =============================================================

-- 실적이 존재하면 지시 삭제 불가 / 생산 진행중 지시 삭제 불가
create or replace function mes.guard_head_delete() returns trigger
language plpgsql as $$
declare
  v_actual numeric;
  v_machine text;
begin
  select coalesce(sum(actual_qty + bad_qty), 0) into v_actual
    from mes.work_order_lines where head_id = old.id;

  if v_actual > 0 then
    raise exception '실적 수량이 존재 합니다. 삭제 불가한 작업지시 입니다 (%)', old.wo_no
      using errcode = 'P0001';
  end if;

  if old.status = 'IN_PROGRESS' then
    select m.name into v_machine from mes.machines m where m.id = old.machine_id;
    raise exception '%에서 현재 생산진행 중입니다', coalesce(v_machine, '설비')
      using errcode = 'P0001';
  end if;

  return old;
end $$;

drop trigger if exists trg_head_guard_delete on mes.work_order_heads;
create trigger trg_head_guard_delete before delete on mes.work_order_heads
  for each row execute function mes.guard_head_delete();

-- 헤드 실적 롤업 자동 갱신
create or replace function mes.rollup_head_actual() returns trigger
language plpgsql as $$
declare
  v_head uuid := coalesce(new.head_id, old.head_id);
begin
  update mes.work_order_heads h
     set plan_qty      = s.plan_qty,
         actual_qty    = s.actual_qty,
         good_qty      = s.good_qty,
         bad_qty       = s.bad_qty,
         bad_weight_kg = s.bad_weight_kg,
         updated_at    = now()
    from (
      select coalesce(sum(plan_qty), 0)      as plan_qty,
             coalesce(sum(actual_qty), 0)    as actual_qty,
             coalesce(sum(good_qty), 0)      as good_qty,
             coalesce(sum(bad_qty), 0)       as bad_qty,
             coalesce(sum(bad_weight_kg), 0) as bad_weight_kg
        from mes.work_order_lines where head_id = v_head
    ) s
   where h.id = v_head;
  return null;
end $$;

drop trigger if exists trg_line_rollup on mes.work_order_lines;
create trigger trg_line_rollup after insert or update or delete on mes.work_order_lines
  for each row execute function mes.rollup_head_actual();

-- updated_at 자동 갱신
create or replace function mes.touch_updated_at() returns trigger
language plpgsql as $$
begin new.updated_at := now(); return new; end $$;

drop trigger if exists trg_head_touch on mes.work_order_heads;
create trigger trg_head_touch before update on mes.work_order_heads
  for each row execute function mes.touch_updated_at();

drop trigger if exists trg_line_touch on mes.work_order_lines;
create trigger trg_line_touch before update on mes.work_order_lines
  for each row execute function mes.touch_updated_at();

-- =============================================================
-- 조회 뷰
-- =============================================================
create or replace view mes.v_work_order_head as
select
  h.*,
  c.name  as customer_name,
  m.code  as machine_code,
  m.name  as machine_name,
  p.name  as plate_type_name,
  f.code  as formula_code,
  case when h.plan_qty > 0
       then round(h.good_qty / h.plan_qty * 100, 1) else 0 end as progress_pct
from mes.work_order_heads h
left join mes.customers   c on c.id = h.customer_id
left join mes.machines    m on m.id = h.machine_id
left join mes.plate_types p on p.id = h.plate_type_id
left join mes.calc_formulas f on f.id = h.formula_id;

-- =============================================================
-- RLS : 로그인 사용자 전체 권한, 익명 차단
-- =============================================================
do $$
declare t text;
begin
  foreach t in array array[
    'machines','customers','plate_types','items','coils','calc_formulas',
    'wo_no_counters','work_order_heads','work_order_specs','work_order_lines','actual_topends'
  ] loop
    execute format('alter table mes.%I enable row level security', t);
    execute format('drop policy if exists %I on mes.%I', t || '_auth_all', t);
    execute format(
      'create policy %I on mes.%I for all to authenticated using (true) with check (true)',
      t || '_auth_all', t);
  end loop;
end $$;

grant usage on schema mes to authenticated, anon;
grant all on all tables in schema mes to authenticated;
grant execute on function mes.next_wo_no(date, mes.order_div) to authenticated;
