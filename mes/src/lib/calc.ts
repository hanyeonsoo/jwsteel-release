// ---------------------------------------------------------------
// 단중 / 로스 / 스크랩 계산 엔진
//
// ⚠ 옛 MES 의 실제 계산은 Oracle 함수(UF_JW_SL_WEIGHT_NEW 등 26개)에 있었고
//   회수하지 못했다. 소스에 주석으로 남아있던 공식이 아래 WIDTH_PRORATA 이며,
//   `_NEW` / `_TOT` 변형이 존재했다는 것은 공식이 개정됐다는 뜻이다.
//
//   따라서 계산식은 코드에 고정하지 않는다.
//   - 배분 방식 = calc_formulas.method (아래 METHODS 레지스트리 키)
//   - 비중·반올림 등 = calc_formulas.params (DB 에서 값만 교체 가능)
//   현장 확인(§6-1, §6-2) 후 params 또는 method 행만 바꾸면 된다.
// ---------------------------------------------------------------

import type { CalcFormula, CalcMethod, CalcParams } from './types'

export interface CalcCoil {
  width_mm: number
  thickness_mm: number
  weight_kg: number
}

export interface CalcRowInput {
  width_mm: number
  /** 절수 — 코일 폭 방향으로 몇 가닥 */
  cut: number
  /** 분할 — 길이 방향 몇 등분 */
  divide: number
  /** 계획수량. 미지정 시 절수 × 분할 */
  plan_qty?: number | null
}

export interface CalcRowResult {
  /** 절수 × 분할 */
  qty: number
  /** 실제 적용된 계획수량 */
  plan_qty: number
  /** 단중 (kg/EA) */
  unit_weight_kg: number
  /** 제품중량 = 단중 × 계획수량 */
  plan_weight_kg: number
}

export interface CalcResult {
  rows: CalcRowResult[]
  /** Σ(제품폭 × 절수) */
  product_width_sum: number
  /** 코일폭 − 제품폭합계 (트림 보정 반영) */
  loss_mm: number
  /** 길이(세로) mm */
  height_mm: number
  /** Σ 제품중량 */
  total_weight_kg: number
  /** 코일중량 − Σ제품중량 */
  scrap_weight_kg: number
  /** 계산 불가 사유 (있으면 결과는 0) */
  warning: string | null
}

const DEFAULTS: Required<Pick<CalcParams, 'density' | 'unit_weight_round' | 'height_round' | 'weight_round' | 'trim_mm'>> = {
  density: 7.85,
  unit_weight_round: 3,
  height_round: 0,
  weight_round: 1,
  trim_mm: 0,
}

function round(v: number, digits: number): number {
  const f = 10 ** digits
  return Math.round(v * f) / f
}

type MethodFn = (coil: CalcCoil, rows: CalcRowInput[], p: typeof DEFAULTS) => number[]

/**
 * 배분 방식 레지스트리.
 * 새 방식이 확인되면 여기에 함수를 추가하고 calc_formulas 에 행만 넣으면 된다.
 */
const METHODS: Record<CalcMethod, MethodFn> = {
  /**
   * 폭 비례배분 — 회수한 옛 공식
   *   단중 = ((코일중량 ÷ 제품폭합계) × 제품폭) ÷ 분할 ÷ 절수
   */
  WIDTH_PRORATA: (coil, rows, p) => {
    const widthSum = rows.reduce((s, r) => s + r.width_mm * r.cut, 0)
    if (widthSum <= 0) return rows.map(() => 0)
    return rows.map((r) => {
      const w = ((coil.weight_kg / widthSum) * r.width_mm) / r.divide / r.cut
      return round(w, p.unit_weight_round)
    })
  },

  /**
   * 중량동일 배분 — 옛 화면의 "계산방식(중량동일)계산" 근거
   *   단중 = 코일중량 ÷ Σ(절수 × 분할)
   */
  EQUAL_WEIGHT: (coil, rows, p) => {
    const qtySum = rows.reduce((s, r) => s + r.cut * r.divide, 0)
    if (qtySum <= 0) return rows.map(() => 0)
    const unit = round(coil.weight_kg / qtySum, p.unit_weight_round)
    return rows.map(() => unit)
  },
}

export function methodLabel(m: CalcMethod): string {
  return m === 'WIDTH_PRORATA' ? '폭 비례배분' : '중량동일 배분'
}

export function isKnownMethod(m: string): m is CalcMethod {
  return m in METHODS
}

/**
 * 작업지시 명세 계산.
 * @param densityOverride 철판종류 마스터의 비중 (지정 시 params.density 보다 우선)
 */
export function calcWorkOrder(
  coil: CalcCoil,
  rows: CalcRowInput[],
  formula: CalcFormula | null,
  densityOverride?: number | null,
): CalcResult {
  const p = { ...DEFAULTS, ...(formula?.params ?? {}) }
  if (densityOverride && densityOverride > 0) p.density = densityOverride

  const empty: CalcResult = {
    rows: rows.map((r) => ({
      qty: r.cut * r.divide,
      plan_qty: r.plan_qty ?? r.cut * r.divide,
      unit_weight_kg: 0,
      plan_weight_kg: 0,
    })),
    product_width_sum: 0, loss_mm: 0, height_mm: 0,
    total_weight_kg: 0, scrap_weight_kg: 0,
    warning: null,
  }

  if (!rows.length) return { ...empty, warning: '가공 명세를 입력하세요' }
  if (coil.weight_kg <= 0 || coil.width_mm <= 0 || coil.thickness_mm <= 0) {
    return { ...empty, warning: '원소재 폭 / 두께 / 중량을 입력하세요' }
  }

  const methodKey = formula?.method ?? 'WIDTH_PRORATA'
  const fn = METHODS[methodKey]
  if (!fn) return { ...empty, warning: `등록되지 않은 계산방식입니다: ${methodKey}` }

  const units = fn(coil, rows, p)

  const outRows: CalcRowResult[] = rows.map((r, i) => {
    const qty = r.cut * r.divide
    const planQty = r.plan_qty ?? qty
    return {
      qty,
      plan_qty: planQty,
      unit_weight_kg: units[i],
      plan_weight_kg: round(units[i] * planQty, p.weight_round),
    }
  })

  const productWidthSum = round(rows.reduce((s, r) => s + r.width_mm * r.cut, 0), 2)
  const usableWidth = coil.width_mm - p.trim_mm
  const totalWeight = round(outRows.reduce((s, r) => s + r.plan_weight_kg, 0), p.weight_round)

  // 길이(세로) = (코일중량 ÷ 코일폭 ÷ 코일두께 ÷ 비중) × 1000
  const height = round(
    (coil.weight_kg / coil.width_mm / coil.thickness_mm / p.density) * 1000,
    p.height_round,
  )

  let warning: string | null = null
  if (productWidthSum > usableWidth) {
    warning = `제품폭 합계(${productWidthSum}mm)가 코일폭(${usableWidth}mm)을 초과합니다`
  }

  return {
    rows: outRows,
    product_width_sum: productWidthSum,
    loss_mm: round(usableWidth - productWidthSum, 2),
    height_mm: height,
    total_weight_kg: totalWeight,
    scrap_weight_kg: round(coil.weight_kg - totalWeight, p.weight_round),
    warning,
  }
}
