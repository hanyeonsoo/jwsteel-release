// ---------------------------------------------------------------
// MES 도메인 타입 — DB 컬럼명과 1:1 (snake_case 유지)
// ---------------------------------------------------------------

export type OrderDiv = 'SL' | 'SH'
export type WoStatus = 'PLANNED' | 'RELEASED' | 'IN_PROGRESS' | 'DONE' | 'CANCELED'
export type ActualSource = 'MANUAL' | 'AUTO'
export type TopendDiv = 'T' | 'S'
export type MachineState = 'RUN' | 'SETUP' | 'IDLE' | 'DOWN' | 'PLANNED_STOP'

// ---------- 기준정보 -------------------------------------------

export interface Machine {
  id: string
  code: string
  name: string
  order_div: OrderDiv
  spec: string | null
  sort_order: number
  use_yn: boolean
}

export interface Customer {
  id: string
  code: string
  name: string
  busin_no: string | null
  repre_nm: string | null
  tel_no: string | null
  use_yn: boolean
}

export interface PlateType {
  id: string
  code: string
  name: string
  density: number
  sort_order: number
  use_yn: boolean
}

export interface Item {
  id: string
  code: string
  name: string
  spec: string | null
  item_class: 'PRODUCT' | 'SCRAP' | 'COIL'
  plate_type_id: string | null
  unit: string
  use_yn: boolean
}

export interface Coil {
  id: string
  coil_no: string
  lot_no: string | null
  item_id: string | null
  plate_type_id: string | null
  material_name: string | null
  thickness_mm: number
  width_mm: number
  weight_kg: number
  remain_kg: number | null
  location: string | null
  stock_div_nm: string | null
  received_on: string | null
  use_yn: boolean
}

/** 계산공식 설정 — 계산식을 코드에 고정하지 않기 위한 설정 행 */
export interface CalcFormula {
  id: string
  code: string
  name: string
  order_div: OrderDiv | null
  method: CalcMethod
  params: CalcParams
  is_default: boolean
  description: string | null
  use_yn: boolean
}

export type CalcMethod = 'WIDTH_PRORATA' | 'EQUAL_WEIGHT'

export interface CalcParams {
  /** 비중 (g/cm³) */
  density?: number
  /** 단중 반올림 자리수 */
  unit_weight_round?: number
  /** 길이(세로) 반올림 자리수 */
  height_round?: number
  /** 중량 반올림 자리수 */
  weight_round?: number
  /** 사이드 트림 등 폭 손실 보정 (mm) */
  trim_mm?: number
}

// ---------- 작업지시 -------------------------------------------

export interface WorkOrderHead {
  id: string
  wo_no: string
  order_div: OrderDiv
  status: WoStatus
  work_order_date: string

  coil_id: string | null
  coil_no: string
  lot_no: string | null
  plate_type_id: string | null
  material_name: string | null
  coil_width_mm: number
  coil_thickness_mm: number
  coil_weight_kg: number
  coil_location: string | null

  customer_id: string
  machine_id: string
  work_shift: '1' | '2'
  worker_id: string | null

  formula_id: string | null

  product_width_sum: number | null
  loss_mm: number | null
  height_mm: number | null
  scrap_weight_kg: number | null
  top_end_weight_kg: number | null

  plan_qty: number
  actual_qty: number
  good_qty: number
  bad_qty: number
  bad_weight_kg: number

  rewind_date: string | null
  rewind_width_mm: number | null
  rewind_weight_kg: number | null

  special_note: string | null
  bigo: string | null
  printed_at: string | null
  print_count: number

  created_by: string | null
  created_at: string
  updated_at: string
}

/** 가공 명세 — 어떻게 자를지 */
export interface WorkOrderSpec {
  id: string
  head_id: string
  proc_seq: number
  width_mm: number
  cut: number
  divide: number
}

/** 지시 행 — 제품별 지시 + 실적 */
export interface WorkOrderLine {
  id: string
  head_id: string
  spec_id: string | null
  line_seq: number

  item_id: string | null
  item_code: string | null
  item_name: string | null
  item_spec: string | null

  width_mm: number
  cut: number
  divide: number

  plan_qty: number
  unit_weight_kg: number | null
  plan_weight_kg: number | null
  height_mm: number | null

  actual_qty: number
  good_qty: number
  bad_qty: number
  bad_weight_kg: number
  good_weight_kg: number
  grade: string | null
  bad_reason: string | null
  banding_qty: number | null
  work_date: string | null
  start_time: string | null
  end_time: string | null
  actual_source: ActualSource
  completion: boolean
  note: string | null
}

/** TOP/END · 스크랩 실적 */
export interface ActualTopend {
  id: string
  head_id: string
  actual_seq: number
  topend_div: TopendDiv
  item_id: string | null
  thickness_mm: number | null
  height_mm: number | null
  qty: number
  weight_kg: number
  actual_source: ActualSource
  note: string | null
}

// ---------- 설비 가동 -------------------------------------------

export interface DowntimeReason {
  id: string
  code: string
  name: string
  category: string
  is_planned: boolean
  sort_order: number
  use_yn: boolean
}

export interface MachineStatusLog {
  id: string
  machine_id: string
  state: MachineState
  started_at: string
  ended_at: string | null
  reason_id: string | null
  head_id: string | null
  worker_id: string | null
  source: ActualSource
  note: string | null
}

// ---------- 조합 뷰 ---------------------------------------------

export interface WorkOrderHeadView extends WorkOrderHead {
  customer_name: string | null
  machine_code: string | null
  machine_name: string | null
  plate_type_name: string | null
  progress_pct: number
}

/** 작업지시 1건 전체 (등록/출력/실적 화면 공통) */
export interface WorkOrderFull {
  head: WorkOrderHead
  specs: WorkOrderSpec[]
  lines: WorkOrderLine[]
  topends: ActualTopend[]
}

export interface MachineStatusView {
  machine: Machine
  current: MachineStatusLog | null
  reason: DowntimeReason | null
  head: WorkOrderHead | null
  elapsed_min: number
}

export interface MachineDaily {
  machine_id: string
  work_date: string
  run_h: number
  setup_h: number
  idle_h: number
  down_h: number
  planned_stop_h: number
}
