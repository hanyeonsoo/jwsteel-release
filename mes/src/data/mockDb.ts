import type {
  ActualTopend, CalcFormula, Coil, Customer, DowntimeReason, Item, Machine,
  MachineStatusLog, PlateType, WorkOrderHead, WorkOrderLine, WorkOrderSpec,
} from '@/lib/types'
import { calcWorkOrder } from '@/lib/calc'
import { DEFAULT_SPECIAL_NOTES } from '@/lib/labels'
import { todayStr } from '@/lib/format'

export interface MockState {
  machines: Machine[]
  customers: Customer[]
  plateTypes: PlateType[]
  items: Item[]
  coils: Coil[]
  formulas: CalcFormula[]
  reasons: DowntimeReason[]
  heads: WorkOrderHead[]
  specs: WorkOrderSpec[]
  lines: WorkOrderLine[]
  topends: ActualTopend[]
  logs: MachineStatusLog[]
  counters: Record<string, number>
}

const KEY = 'jwsteel-mes-demo-v2'
export const uid = () => crypto.randomUUID()
const hoursAgo = (h: number) => new Date(Date.now() - h * 3600_000).toISOString()

function seed(): MockState {
  // ---------- 기준정보 ----------
  const plateTypes: PlateType[] = [
    ['HR', '열연 (HR)', 7.85], ['CR', '냉연 (CR)', 7.85],
    ['GI', '용융아연도금 (GI)', 7.85], ['EGI', '전기아연도금 (EGI)', 7.85],
    ['PO', '산세 (PO)', 7.85], ['STS', '스테인리스 (STS)', 7.93],
  ].map(([code, name, density], i) => ({
    id: uid(), code: code as string, name: name as string,
    density: density as number, sort_order: (i + 1) * 10, use_yn: true,
  }))

  const machines: Machine[] = [
    ['SL01', '1호 슬리터', 'SL', '최대폭 1250 / 최대두께 6.0T'],
    ['SL02', '2호 슬리터', 'SL', '최대폭 1000 / 최대두께 3.2T'],
    ['SH01', '1호 시어링', 'SH', '최대폭 1500 / 최대두께 12.0T'],
    ['SH02', '2호 시어링', 'SH', '최대폭 1250 / 최대두께 6.0T'],
  ].map(([code, name, div, spec], i) => ({
    id: uid(), code: code as string, name: name as string,
    order_div: div as Machine['order_div'], spec: spec as string,
    sort_order: (i + 1) * 10, use_yn: true,
  }))

  const customers: Customer[] = [
    ['C001', '대성산업'], ['C002', '한일기공'], ['C003', '금성테크'],
    ['C004', '우진스틸'], ['C005', '삼호정밀'], ['C006', '동양산업'],
  ].map(([code, name]) => ({
    id: uid(), code, name, busin_no: null, repre_nm: null, tel_no: null, use_yn: true,
  }))

  const items: Item[] = [
    ...['SL-COIL-A', 'SL-COIL-B', 'SH-PLATE-A', 'SH-PLATE-B'].map((code, i) => ({
      id: uid(), code,
      name: i < 2 ? '슬리팅 코일' : '절단 판재',
      spec: null as string | null,
      item_class: 'PRODUCT' as const,
      plate_type_id: plateTypes[0].id, unit: i < 2 ? 'EA' : 'EA', use_yn: true,
    })),
    ...[['SCR-SIDE', '사이드 트림'], ['SCR-TOP', 'TOP/END 스크랩'], ['SCR-ETC', '기타 스크랩']]
      .map(([code, name]) => ({
        id: uid(), code, name, spec: null as string | null,
        item_class: 'SCRAP' as const, plate_type_id: null, unit: 'KG', use_yn: true,
      })),
  ]

  const coils: Coil[] = [
    ['CL-26083101', 'SS400', 3.2, 1219, 12_400, 'A-1'],
    ['CL-26083102', 'SS400', 4.5, 1219, 14_800, 'A-2'],
    ['CL-26083103', 'SPHC', 2.3, 1000, 9_600, 'A-3'],
    ['CL-26083104', 'SPHC', 1.6, 1000, 8_200, 'B-1'],
    ['CL-26083105', 'SPCC', 1.2, 914, 6_500, 'B-2'],
    ['CL-26083106', 'SS400', 6.0, 1524, 18_200, 'C-1'],
    ['CL-26083107', 'SM490', 9.0, 1524, 21_000, 'C-2'],
    ['CL-26083108', 'SPHC', 3.2, 1219, 11_900, 'A-4'],
  ].map(([coil, mat, t, w, kg, loc], i) => ({
    id: uid(), coil_no: coil as string, lot_no: `LOT-${String(i + 1).padStart(4, '0')}`,
    item_id: null, plate_type_id: plateTypes[i % 2].id, material_name: mat as string,
    thickness_mm: t as number, width_mm: w as number, weight_kg: kg as number,
    remain_kg: kg as number, location: loc as string, stock_div_nm: '정상',
    received_on: todayStr(-7), use_yn: true,
  }))

  const formulas: CalcFormula[] = [
    {
      id: uid(), code: 'SL01', name: '슬리팅 표준 (폭 비례배분)', order_div: 'SL',
      method: 'WIDTH_PRORATA',
      params: { density: 7.85, unit_weight_round: 3, height_round: 0, weight_round: 1 },
      is_default: true, use_yn: true,
      description: '단중 = ((코일중량 ÷ 제품폭합계) × 제품폭) ÷ 분할 ÷ 절수. 회수한 옛 소스의 주석 공식이며 현행 여부 미확인.',
    },
    {
      id: uid(), code: 'SH01', name: '절단 표준 (폭 비례배분)', order_div: 'SH',
      method: 'WIDTH_PRORATA',
      params: { density: 7.85, unit_weight_round: 3, height_round: 0, weight_round: 1 },
      is_default: true, use_yn: true,
      description: 'UF_JW_SH_WEIGHT_NEW 미회수로 현장 확인 필요.',
    },
    {
      id: uid(), code: 'EQ01', name: '중량동일 배분', order_div: null,
      method: 'EQUAL_WEIGHT',
      params: { density: 7.85, unit_weight_round: 3, height_round: 0, weight_round: 1 },
      is_default: false, use_yn: true,
      description: '옛 MES 화면의 "계산방식(중량동일)계산" 문구 근거.',
    },
  ]

  const reasons: DowntimeReason[] = [
    ['D-BRK', '설비 고장', '고장', false], ['D-KNF', '나이프 교체', '준비', false],
    ['D-SET', '코일 교체/세팅', '준비', false], ['D-MAT', '자재 대기', '자재대기', false],
    ['D-QLT', '품질 이상 조치', '품질', false], ['D-PWR', '정전', '기타', false],
    ['P-PM', '정기 보전(PM)', '계획정지', true], ['P-BRK', '휴게/식사', '계획정지', true],
    ['P-NOP', '무작업(계획)', '계획정지', true],
  ].map(([code, name, cat, planned], i) => ({
    id: uid(), code: code as string, name: name as string, category: cat as string,
    is_planned: planned as boolean, sort_order: (i + 1) * 10, use_yn: true,
  }))

  // ---------- 작업지시 ----------
  const heads: WorkOrderHead[] = []
  const specs: WorkOrderSpec[] = []
  const lines: WorkOrderLine[] = []
  const topends: ActualTopend[] = []
  const counters: Record<string, number> = {}

  const woNo = (date: string, div: 'SL' | 'SH') => {
    const key = `${date}|${div}`
    counters[key] = (counters[key] ?? 0) + 1
    return date.slice(2).replace(/-/g, '') + div + String(counters[key]).padStart(3, '0')
  }

  interface Plan {
    div: 'SL' | 'SH'
    coil: number
    machine: number
    cust: number
    dateOffset: number
    status: WorkOrderHead['status']
    rows: Array<{ width: number; cut: number; divide: number; item: number }>
    /** 실적 진척률 */
    ratio: number
  }

  const plans: Plan[] = [
    {
      div: 'SL', coil: 0, machine: 0, cust: 0, dateOffset: 0, status: 'IN_PROGRESS', ratio: 0.5,
      rows: [{ width: 300, cut: 4, divide: 1, item: 0 }, { width: 19, cut: 1, divide: 1, item: 1 }],
    },
    {
      div: 'SL', coil: 2, machine: 1, cust: 1, dateOffset: 0, status: 'RELEASED', ratio: 0,
      rows: [{ width: 245, cut: 4, divide: 2, item: 0 }],
    },
    {
      div: 'SH', coil: 5, machine: 2, cust: 2, dateOffset: 0, status: 'IN_PROGRESS', ratio: 0.35,
      rows: [{ width: 1500, cut: 1, divide: 6, item: 2 }],
    },
    {
      div: 'SH', coil: 6, machine: 2, cust: 3, dateOffset: 0, status: 'PLANNED', ratio: 0,
      rows: [{ width: 1500, cut: 1, divide: 8, item: 3 }],
    },
    {
      div: 'SL', coil: 1, machine: 0, cust: 4, dateOffset: -1, status: 'DONE', ratio: 1,
      rows: [{ width: 400, cut: 3, divide: 1, item: 0 }],
    },
    {
      div: 'SL', coil: 3, machine: 1, cust: 5, dateOffset: 1, status: 'PLANNED', ratio: 0,
      rows: [{ width: 197, cut: 5, divide: 1, item: 1 }],
    },
  ]

  plans.forEach((plan) => {
    const coil = coils[plan.coil]
    const machine = machines[plan.machine]
    const date = todayStr(plan.dateOffset)
    const formula = formulas.find((f) => f.order_div === plan.div)!
    const plateType = plateTypes.find((p) => p.id === coil.plate_type_id) ?? null

    const calcRows = plan.rows.map((r) => ({ width_mm: r.width, cut: r.cut, divide: r.divide }))
    const result = calcWorkOrder(
      { width_mm: coil.width_mm, thickness_mm: coil.thickness_mm, weight_kg: coil.weight_kg },
      calcRows, formula, plateType?.density,
    )

    const headId = uid()
    const planQtySum = result.rows.reduce((s, r) => s + r.plan_qty, 0)
    const goodQty = Math.round(planQtySum * plan.ratio)
    const badQty = plan.ratio > 0 && plan.ratio < 1 ? 1 : 0

    heads.push({
      id: headId,
      wo_no: woNo(date, plan.div),
      order_div: plan.div,
      status: plan.status,
      work_order_date: date,
      coil_id: coil.id, coil_no: coil.coil_no, lot_no: coil.lot_no,
      plate_type_id: coil.plate_type_id, material_name: coil.material_name,
      coil_width_mm: coil.width_mm, coil_thickness_mm: coil.thickness_mm,
      coil_weight_kg: coil.weight_kg, coil_location: coil.location,
      customer_id: customers[plan.cust].id,
      machine_id: machine.id,
      work_shift: '1', worker_id: ['김철수', '이영호', '박민준'][plan.coil % 3],
      formula_id: formula.id,
      product_width_sum: result.product_width_sum,
      loss_mm: result.loss_mm,
      height_mm: result.height_mm,
      scrap_weight_kg: result.scrap_weight_kg,
      top_end_weight_kg: null,
      plan_qty: planQtySum,
      actual_qty: goodQty + badQty,
      good_qty: goodQty,
      bad_qty: badQty,
      bad_weight_kg: 0,
      rewind_date: null, rewind_width_mm: null, rewind_weight_kg: null,
      special_note: DEFAULT_SPECIAL_NOTES,
      bigo: null,
      printed_at: plan.status === 'PLANNED' ? null : hoursAgo(20),
      print_count: plan.status === 'PLANNED' ? 0 : 1,
      created_by: '관리자',
      created_at: hoursAgo(26),
      updated_at: hoursAgo(3),
    })

    plan.rows.forEach((r, i) => {
      const specId = uid()
      specs.push({
        id: specId, head_id: headId, proc_seq: i + 1,
        width_mm: r.width, cut: r.cut, divide: r.divide,
      })
      const cr = result.rows[i]
      const lineGood = Math.round(cr.plan_qty * plan.ratio)
      const lineBad = i === 0 ? badQty : 0
      lines.push({
        id: uid(), head_id: headId, spec_id: specId, line_seq: i + 1,
        item_id: items[r.item].id, item_code: items[r.item].code,
        item_name: items[r.item].name, item_spec: `${r.width}W × ${coil.thickness_mm}T`,
        width_mm: r.width, cut: r.cut, divide: r.divide,
        plan_qty: cr.plan_qty,
        unit_weight_kg: cr.unit_weight_kg,
        plan_weight_kg: cr.plan_weight_kg,
        height_mm: result.height_mm,
        actual_qty: lineGood + lineBad,
        good_qty: lineGood,
        bad_qty: lineBad,
        bad_weight_kg: lineBad ? Math.round(cr.unit_weight_kg * lineBad * 10) / 10 : 0,
        good_weight_kg: Math.round(cr.unit_weight_kg * lineGood * 10) / 10,
        grade: plan.ratio > 0 ? 'A' : null,
        bad_reason: lineBad ? '에지 크랙' : null,
        banding_qty: null,
        work_date: plan.ratio > 0 ? date : null,
        start_time: plan.ratio > 0 ? '0830' : null,
        end_time: plan.ratio >= 1 ? '1640' : null,
        actual_source: 'MANUAL',
        completion: plan.ratio >= 1,
        note: null,
      })
    })

    if (plan.ratio > 0) {
      topends.push({
        id: uid(), head_id: headId, actual_seq: 1, topend_div: 'T',
        item_id: items.find((it) => it.code === 'SCR-TOP')!.id,
        thickness_mm: coil.thickness_mm, height_mm: null,
        qty: 2, weight_kg: Math.round(coil.weight_kg * 0.004 * 10) / 10,
        actual_source: 'MANUAL', note: null,
      })
      topends.push({
        id: uid(), head_id: headId, actual_seq: 2, topend_div: 'S',
        item_id: items.find((it) => it.code === 'SCR-SIDE')!.id,
        thickness_mm: coil.thickness_mm, height_mm: null,
        qty: 0, weight_kg: Math.round(Math.max(0, result.scrap_weight_kg) * 10) / 10,
        actual_source: 'MANUAL', note: null,
      })
    }
  })

  // ---------- 설비 가동 로그 ----------
  const logs: MachineStatusLog[] = []
  const push = (
    m: Machine, state: MachineStatusLog['state'], from: number, to: number | null,
    reason?: DowntimeReason, headId?: string,
  ) => logs.push({
    id: uid(), machine_id: m.id, state,
    started_at: hoursAgo(from), ended_at: to === null ? null : hoursAgo(to),
    reason_id: reason?.id ?? null, head_id: headId ?? null,
    worker_id: '김철수', source: 'MANUAL', note: null,
  })

  const headOn = (mid: string) => heads.find((h) => h.machine_id === mid && h.status === 'IN_PROGRESS')?.id

  push(machines[0], 'SETUP', 11, 10, reasons[2])
  push(machines[0], 'RUN', 10, 6.5, undefined, headOn(machines[0].id))
  push(machines[0], 'DOWN', 6.5, 5.8, reasons[1])
  push(machines[0], 'RUN', 5.8, null, undefined, headOn(machines[0].id))

  push(machines[1], 'PLANNED_STOP', 11, 8, reasons[6])
  push(machines[1], 'IDLE', 8, null, reasons[3])

  push(machines[2], 'RUN', 11, 7, undefined, headOn(machines[2].id))
  push(machines[2], 'PLANNED_STOP', 7, 6, reasons[7])
  push(machines[2], 'RUN', 6, null, undefined, headOn(machines[2].id))

  push(machines[3], 'IDLE', 11, 9)
  push(machines[3], 'DOWN', 9, null, reasons[0])

  return {
    machines, customers, plateTypes, items, coils, formulas, reasons,
    heads, specs, lines, topends, logs, counters,
  }
}

let cache: MockState | null = null

export function db(): MockState {
  if (cache) return cache
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) {
      cache = JSON.parse(raw) as MockState
      return cache
    }
  } catch { /* 파싱 실패 시 재시드 */ }
  cache = seed()
  persist()
  return cache
}

export function persist() {
  if (!cache) return
  try {
    localStorage.setItem(KEY, JSON.stringify(cache))
  } catch { /* 데모 모드이므로 저장 실패는 무시 */ }
}

export function resetDb() {
  cache = seed()
  persist()
}
