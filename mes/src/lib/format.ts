/** 숫자 3자리 구분 */
export function num(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-'
  return Number(v).toLocaleString('ko-KR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function kg(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return '-'
  return `${num(v, digits)} kg`
}

export function mm(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return '-'
  return `${num(v, digits)} mm`
}

export function pct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-'
  return `${num(v, digits)}%`
}

const p2 = (n: number) => String(n).padStart(2, '0')

/** 로컬 기준 YYYY-MM-DD */
export function todayStr(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`
}

/** ISO → 'MM/DD HH:mm' */
export function dt(iso: string | null | undefined): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${p2(d.getMonth() + 1)}/${p2(d.getDate())} ${p2(d.getHours())}:${p2(d.getMinutes())}`
}

/** ISO → 'HH:mm' */
export function hm(iso: string | null | undefined): string {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${p2(d.getHours())}:${p2(d.getMinutes())}`
}

/** 'HHMM' → 'HH:mm' */
export function hhmm(v: string | null | undefined): string {
  if (!v || v.length !== 4) return v || '-'
  return `${v.slice(0, 2)}:${v.slice(2)}`
}

/** 현재시각을 HHMM 으로 */
export function nowHHMM(): string {
  const d = new Date()
  return `${p2(d.getHours())}${p2(d.getMinutes())}`
}

/** HHMM 두 개의 차이(분). 종료가 시작보다 작으면 익일로 본다. */
export function workMinutes(start: string | null, end: string | null): number | null {
  if (!start || !end || start.length !== 4 || end.length !== 4) return null
  const s = Number(start.slice(0, 2)) * 60 + Number(start.slice(2))
  const e = Number(end.slice(0, 2)) * 60 + Number(end.slice(2))
  return e >= s ? e - s : e + 1440 - s
}

/** 분 → '3시간 12분' */
export function dur(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '-'
  const m = Math.max(0, Math.round(minutes))
  const h = Math.floor(m / 60)
  return h > 0 ? `${h}시간 ${m % 60}분` : `${m}분`
}

/** 남은 일수 (마이너스면 지연) */
export function dday(date: string | null | undefined): number | null {
  if (!date) return null
  const a = new Date(date + 'T00:00:00').getTime()
  const b = new Date(todayStr() + 'T00:00:00').getTime()
  return Math.round((a - b) / 86400000)
}
