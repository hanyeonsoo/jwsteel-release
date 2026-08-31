// ---------------------------------------------------------------
// 검증 규칙 — 옛 MES 소스에서 그대로 이관.
// 메시지 문구도 현장이 쓰던 표현을 유지한다.
// ---------------------------------------------------------------

import type { WorkOrderHead, WorkOrderLine } from './types'
import { todayStr } from './format'

export interface ValidationError {
  field: string
  message: string
}

/** HHMM 4자리 · 시 00~23 · 분 00~59 */
export function validateWorkTime(v: string | null | undefined, field: string): ValidationError | null {
  if (!v) return null
  if (!/^\d{4}$/.test(v)) return { field, message: '작업시간은 4자리로 입력 하세요 (예: 0830)' }
  const h = Number(v.slice(0, 2))
  const m = Number(v.slice(2, 4))
  if (h > 23) return { field, message: '시간은 00과 23 사이를 입력 하세요' }
  if (m > 59) return { field, message: '분은 00과 59 사이를 입력 하세요' }
  return null
}

/** 작업지시 헤드 필수 입력 */
export function validateHead(h: Partial<WorkOrderHead>): ValidationError[] {
  const errs: ValidationError[] = []
  if (!h.work_order_date) errs.push({ field: 'work_order_date', message: '작업지시일을 입력 하세요' })
  if (!h.coil_no) errs.push({ field: 'coil_no', message: '코일번호를 입력 하세요' })
  if (!h.customer_id) errs.push({ field: 'customer_id', message: '고객사를 선택 하세요' })
  if (!h.machine_id) errs.push({ field: 'machine_id', message: '설비를 선택 하세요' })
  if (!h.work_shift) errs.push({ field: 'work_shift', message: '교대조를 선택 하세요' })
  if (!h.coil_width_mm) errs.push({ field: 'coil_width_mm', message: '원소재 폭을 입력 하세요' })
  if (!h.coil_thickness_mm) errs.push({ field: 'coil_thickness_mm', message: '원소재 두께를 입력 하세요' })
  if (!h.coil_weight_kg) errs.push({ field: 'coil_weight_kg', message: '원소재 중량을 입력 하세요' })
  return errs
}

/** 지시 행 (계획) 검증 */
export function validateLine(l: Partial<WorkOrderLine>, idx: number): ValidationError[] {
  const errs: ValidationError[] = []
  const at = `#${idx + 1}`

  if (!l.item_id && !l.item_name) {
    errs.push({ field: `lines.${idx}.item`, message: `${at} 품목을 선택 하세요` })
  }
  if (!l.width_mm || l.width_mm <= 0) {
    errs.push({ field: `lines.${idx}.width_mm`, message: `${at} 폭을 입력 하세요` })
  }
  const plan = Number(l.plan_qty ?? 0)
  if (plan < 1) {
    errs.push({ field: `lines.${idx}.plan_qty`, message: `${at} 계획수량이 1보다 적을 수는 없습니다` })
  }
  if (plan < Number(l.actual_qty ?? 0)) {
    errs.push({ field: `lines.${idx}.plan_qty`, message: `${at} 계획수량이 실적수량보다 작습니다. 수량 확인 하세요` })
  }
  return errs
}

/** 실적 입력 검증 — 등급 필수 */
export function validateActual(l: Partial<WorkOrderLine>): ValidationError[] {
  const errs: ValidationError[] = []
  const actual = Number(l.actual_qty ?? 0)
  const plan = Number(l.plan_qty ?? 0)

  if (actual > plan) {
    errs.push({ field: 'actual_qty', message: '계획수량이 실적수량보다 작습니다. 수량 확인 하세요' })
  }
  if (actual > 0 && !l.grade) {
    errs.push({ field: 'grade', message: '등급을 선택 하세요' })
  }
  if (Number(l.bad_qty ?? 0) > 0 && !l.bad_reason) {
    errs.push({ field: 'bad_reason', message: '불량 사유를 입력 하세요' })
  }
  const st = validateWorkTime(l.start_time, 'start_time')
  if (st) errs.push(st)
  const et = validateWorkTime(l.end_time, 'end_time')
  if (et) errs.push(et)
  return errs
}

/** 당일 이전 계획은 수정 불가 */
export function canEditPlan(head: Pick<WorkOrderHead, 'work_order_date' | 'status'>): ValidationError | null {
  if (head.status === 'DONE' || head.status === 'CANCELED') {
    return { field: 'status', message: '완료/취소된 작업지시는 수정할 수 없습니다' }
  }
  if (head.work_order_date < todayStr()) {
    return { field: 'work_order_date', message: '당일 이전 계획은 수정할 수 없습니다' }
  }
  return null
}

/** 설비 이동은 당일분만 */
export function canMoveMachine(head: Pick<WorkOrderHead, 'work_order_date'>): ValidationError | null {
  if (head.work_order_date !== todayStr()) {
    return { field: 'machine_id', message: '당일분 계획만 이동 가능 합니다' }
  }
  return null
}

/** 삭제 가능 여부 — 실적 존재 / 생산 진행중 */
export function canDelete(
  head: Pick<WorkOrderHead, 'status' | 'actual_qty' | 'bad_qty'>,
  machineName?: string | null,
): ValidationError | null {
  if (Number(head.actual_qty) + Number(head.bad_qty) > 0) {
    return { field: 'delete', message: '실적 수량이 존재 합니다. 삭제 불가한 작업지시 입니다' }
  }
  if (head.status === 'IN_PROGRESS') {
    return { field: 'delete', message: `${machineName ?? '설비'}에서 현재 생산진행 중입니다` }
  }
  return null
}

/** 스크랩 실적은 스크랩 품목 필수 */
export function validateTopend(
  div: 'T' | 'S',
  itemId: string | null | undefined,
): ValidationError | null {
  if (div === 'S' && !itemId) {
    return { field: 'item_id', message: '스크랩 품목을 선택 하세요' }
  }
  return null
}
