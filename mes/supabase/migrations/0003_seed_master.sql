-- =============================================================
-- 기준정보 초기값
--   ※ 계산공식 파라미터는 "현장 확인 전 잠정값"이다. §6-1,2 확인 후 갱신할 것.
-- =============================================================

-- 철판종류 (옛 MES attribute05 대체)
insert into mes.plate_types (code, name, density, sort_order) values
  ('HR',  '열연 (HR)',        7.85, 10),
  ('CR',  '냉연 (CR)',        7.85, 20),
  ('GI',  '용융아연도금 (GI)', 7.85, 30),
  ('EGI', '전기아연도금 (EGI)',7.85, 40),
  ('PO',  '산세 (PO)',        7.85, 50),
  ('STS', '스테인리스 (STS)',  7.93, 60)
on conflict (code) do nothing;

-- 설비
insert into mes.machines (code, name, order_div, spec, sort_order) values
  ('SL01', '1호 슬리터', 'SL', '최대폭 1250 / 최대두께 6.0T', 10),
  ('SL02', '2호 슬리터', 'SL', '최대폭 1000 / 최대두께 3.2T', 20),
  ('SH01', '1호 시어링', 'SH', '최대폭 1500 / 최대두께 12.0T', 30),
  ('SH02', '2호 시어링', 'SH', '최대폭 1250 / 최대두께 6.0T', 40)
on conflict (code) do nothing;

-- 계산공식  ★ 초기값은 회수한 옛 공식(주석 처리되어 있던 버전)
insert into mes.calc_formulas (code, name, order_div, method, params, is_default, description) values
  ('SL01', '슬리팅 표준 (폭 비례배분)', 'SL', 'WIDTH_PRORATA',
   '{"density":7.85,"unit_weight_round":3,"height_round":0,"weight_round":1}'::jsonb,
   true,
   '단중 = ((코일중량 ÷ 제품폭합계) × 제품폭) ÷ 분할 ÷ 절수. 회수한 옛 소스의 주석 공식이며 현행 여부 미확인(UF_JW_SL_WEIGHT_NEW 미회수).'),
  ('SH01', '절단 표준 (폭 비례배분)', 'SH', 'WIDTH_PRORATA',
   '{"density":7.85,"unit_weight_round":3,"height_round":0,"weight_round":1}'::jsonb,
   true,
   '슬리팅과 동일 배분식. UF_JW_SH_WEIGHT_NEW 미회수로 현장 확인 필요.'),
  ('EQ01', '중량동일 배분', null, 'EQUAL_WEIGHT',
   '{"density":7.85,"unit_weight_round":3,"height_round":0,"weight_round":1}'::jsonb,
   false,
   '옛 MES 화면의 "계산방식(중량동일)계산" 문구 근거. 총중량을 행 수량으로 균등 배분.')
on conflict (code) do nothing;

-- 비가동 사유
insert into mes.downtime_reasons (code, name, category, is_planned, sort_order) values
  ('D-BRK', '설비 고장',      '고장',     false, 10),
  ('D-KNF', '나이프 교체',    '준비',     false, 20),
  ('D-SET', '코일 교체/세팅', '준비',     false, 30),
  ('D-MAT', '자재 대기',      '자재대기', false, 40),
  ('D-QLT', '품질 이상 조치', '품질',     false, 50),
  ('D-PWR', '정전',           '기타',     false, 60),
  ('P-PM',  '정기 보전(PM)',  '계획정지', true,  70),
  ('P-BRK', '휴게/식사',      '계획정지', true,  80),
  ('P-NOP', '무작업(계획)',   '계획정지', true,  90)
on conflict (code) do nothing;

-- 스크랩 품목 (스크랩 실적 입력 시 필수)
insert into mes.items (code, name, spec, item_class, unit) values
  ('SCR-SIDE', '사이드 트림',  '슬리팅 사이드 스크랩', 'SCRAP', 'KG'),
  ('SCR-TOP',  'TOP/END 스크랩','선후단재',            'SCRAP', 'KG'),
  ('SCR-ETC',  '기타 스크랩',   null,                  'SCRAP', 'KG')
on conflict (code) do nothing;
