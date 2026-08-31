import type {
  ActualTopend, Coil, Item, MachineDaily, MachineState, MachineStatusLog,
  MachineStatusView, OrderDiv, WorkOrderFull, WorkOrderHeadView, WoStatus,
} from '@/lib/types'
import { db, persist, uid } from './mockDb'
import type { ActualPatch, HeadFilter, MesApi, WorkOrderInput } from './types'

const wait = <T>(v: T): Promise<T> => Promise.resolve(v)

function rollup(headId: string) {
  const s = db()
  const head = s.heads.find((h) => h.id === headId)
  if (!head) return
  const lines = s.lines.filter((l) => l.head_id === headId)
  head.plan_qty = lines.reduce((a, l) => a + Number(l.plan_qty || 0), 0)
  head.actual_qty = lines.reduce((a, l) => a + Number(l.actual_qty || 0), 0)
  head.good_qty = lines.reduce((a, l) => a + Number(l.good_qty || 0), 0)
  head.bad_qty = lines.reduce((a, l) => a + Number(l.bad_qty || 0), 0)
  head.bad_weight_kg = lines.reduce((a, l) => a + Number(l.bad_weight_kg || 0), 0)
  head.updated_at = new Date().toISOString()
}

function toView(headId: string): WorkOrderHeadView {
  const s = db()
  const h = s.heads.find((x) => x.id === headId)!
  const machine = s.machines.find((m) => m.id === h.machine_id)
  return {
    ...h,
    customer_name: s.customers.find((c) => c.id === h.customer_id)?.name ?? null,
    machine_code: machine?.code ?? null,
    machine_name: machine?.name ?? null,
    plate_type_name: s.plateTypes.find((p) => p.id === h.plate_type_id)?.name ?? null,
    progress_pct: h.plan_qty > 0 ? Math.round((h.good_qty / h.plan_qty) * 1000) / 10 : 0,
  }
}

export const mockApi: MesApi = {
  listMachines: () => wait([...db().machines].sort((a, b) => a.sort_order - b.sort_order)),
  listCustomers: () => wait([...db().customers].sort((a, b) => a.name.localeCompare(b.name, 'ko'))),
  listPlateTypes: () => wait([...db().plateTypes].sort((a, b) => a.sort_order - b.sort_order)),

  listItems: (itemClass?: Item['item_class']) =>
    wait(db().items.filter((i) => i.use_yn && (!itemClass || i.item_class === itemClass))),

  listCoils: (keyword?: string) => {
    const k = (keyword ?? '').trim().toLowerCase()
    const rows: Coil[] = db().coils.filter((c) =>
      c.use_yn && (!k
        || c.coil_no.toLowerCase().includes(k)
        || (c.lot_no ?? '').toLowerCase().includes(k)
        || (c.material_name ?? '').toLowerCase().includes(k)))
    return wait(rows)
  },

  listFormulas: () => wait(db().formulas.filter((f) => f.use_yn)),
  listReasons: () => wait([...db().reasons].sort((a, b) => a.sort_order - b.sort_order)),

  listHeads: (f: HeadFilter) => {
    const s = db()
    const k = (f.keyword ?? '').trim().toLowerCase()
    const rows = s.heads
      .filter((h) => (!f.from || h.work_order_date >= f.from))
      .filter((h) => (!f.to || h.work_order_date <= f.to))
      .filter((h) => (!f.machineId || h.machine_id === f.machineId))
      .filter((h) => (!f.orderDiv || h.order_div === f.orderDiv))
      .filter((h) => (!f.status || h.status === f.status))
      .filter((h) => {
        if (!k) return true
        const cust = s.customers.find((c) => c.id === h.customer_id)?.name ?? ''
        return h.wo_no.toLowerCase().includes(k)
          || h.coil_no.toLowerCase().includes(k)
          || cust.toLowerCase().includes(k)
      })
      .map((h) => toView(h.id))
      .sort((a, b) =>
        b.work_order_date.localeCompare(a.work_order_date) || a.wo_no.localeCompare(b.wo_no))
    return wait(rows)
  },

  getWorkOrder: (id: string) => {
    const s = db()
    const head = s.heads.find((h) => h.id === id)
    if (!head) return wait<WorkOrderFull | null>(null)
    return wait<WorkOrderFull>({
      head,
      specs: s.specs.filter((x) => x.head_id === id).sort((a, b) => a.proc_seq - b.proc_seq),
      lines: s.lines.filter((x) => x.head_id === id).sort((a, b) => a.line_seq - b.line_seq),
      topends: s.topends.filter((x) => x.head_id === id).sort((a, b) => a.actual_seq - b.actual_seq),
    })
  },

  nextWoNo: (date: string, div: OrderDiv) => {
    const s = db()
    const key = `${date}|${div}`
    const next = (s.counters[key] ?? 0) + 1
    // 미리보기 단계에서는 카운터를 소비하지 않는다 (실제 소비는 createWorkOrder)
    return wait(date.slice(2).replace(/-/g, '') + div + String(next).padStart(3, '0'))
  },

  createWorkOrder: (input: WorkOrderInput) => {
    const s = db()
    const key = `${input.head.work_order_date}|${input.head.order_div}`
    s.counters[key] = (s.counters[key] ?? 0) + 1
    const woNo = input.head.work_order_date.slice(2).replace(/-/g, '')
      + input.head.order_div + String(s.counters[key]).padStart(3, '0')

    const headId = uid()
    const now = new Date().toISOString()
    s.heads.push({
      ...input.head,
      id: headId, wo_no: woNo,
      plan_qty: 0, actual_qty: 0, good_qty: 0, bad_qty: 0, bad_weight_kg: 0,
      printed_at: null, print_count: 0,
      created_by: '관리자', created_at: now, updated_at: now,
    })
    const specIds = input.specs.map((sp) => {
      const id = uid()
      s.specs.push({ ...sp, id, head_id: headId })
      return id
    })
    input.lines.forEach((l, i) => {
      s.lines.push({ ...l, id: uid(), head_id: headId, spec_id: specIds[i] ?? null })
    })
    rollup(headId)
    persist()
    return wait(headId)
  },

  updateWorkOrder: (id: string, input: WorkOrderInput) => {
    const s = db()
    const idx = s.heads.findIndex((h) => h.id === id)
    if (idx < 0) throw new Error('작업지시를 찾을 수 없습니다')
    const prev = s.heads[idx]

    // 실적은 지시 행에 이미 들어있으므로 계획 값만 갱신하고 실적은 보존한다.
    const prevLines = s.lines.filter((l) => l.head_id === id)
    s.heads[idx] = {
      ...prev, ...input.head,
      id, wo_no: prev.wo_no,
      plan_qty: prev.plan_qty, actual_qty: prev.actual_qty, good_qty: prev.good_qty,
      bad_qty: prev.bad_qty, bad_weight_kg: prev.bad_weight_kg,
      printed_at: prev.printed_at, print_count: prev.print_count,
      created_by: prev.created_by, created_at: prev.created_at,
      updated_at: new Date().toISOString(),
    }

    s.specs = s.specs.filter((x) => x.head_id !== id)
    s.lines = s.lines.filter((x) => x.head_id !== id)
    const specIds = input.specs.map((sp) => {
      const sid = uid()
      s.specs.push({ ...sp, id: sid, head_id: id })
      return sid
    })
    input.lines.forEach((l, i) => {
      const keep = prevLines.find((p) => p.line_seq === l.line_seq)
      s.lines.push({
        ...l,
        id: keep?.id ?? uid(),
        head_id: id,
        spec_id: specIds[i] ?? null,
        // 실적 필드는 기존 값 유지
        actual_qty: keep?.actual_qty ?? 0,
        good_qty: keep?.good_qty ?? 0,
        bad_qty: keep?.bad_qty ?? 0,
        bad_weight_kg: keep?.bad_weight_kg ?? 0,
        good_weight_kg: keep?.good_weight_kg ?? 0,
        grade: keep?.grade ?? null,
        bad_reason: keep?.bad_reason ?? null,
        work_date: keep?.work_date ?? null,
        start_time: keep?.start_time ?? null,
        end_time: keep?.end_time ?? null,
        completion: keep?.completion ?? false,
      })
    })
    rollup(id)
    persist()
    return wait(undefined)
  },

  deleteWorkOrder: (id: string) => {
    const s = db()
    s.heads = s.heads.filter((h) => h.id !== id)
    s.specs = s.specs.filter((x) => x.head_id !== id)
    s.lines = s.lines.filter((x) => x.head_id !== id)
    s.topends = s.topends.filter((x) => x.head_id !== id)
    persist()
    return wait(undefined)
  },

  setStatus: (id: string, status: WoStatus) => {
    const h = db().heads.find((x) => x.id === id)
    if (h) {
      h.status = status
      h.updated_at = new Date().toISOString()
    }
    persist()
    return wait(undefined)
  },

  markPrinted: (id: string) => {
    const h = db().heads.find((x) => x.id === id)
    if (h) {
      h.printed_at = new Date().toISOString()
      h.print_count += 1
      if (h.status === 'PLANNED') h.status = 'RELEASED'
    }
    persist()
    return wait(undefined)
  },

  saveActual: (lineId: string, patch: ActualPatch) => {
    const s = db()
    const line = s.lines.find((l) => l.id === lineId)
    if (!line) throw new Error('지시 행을 찾을 수 없습니다')
    Object.assign(line, patch)
    line.good_weight_kg = Math.round((line.unit_weight_kg ?? 0) * line.good_qty * 10) / 10
    line.bad_weight_kg = Math.round((line.unit_weight_kg ?? 0) * line.bad_qty * 10) / 10
    rollup(line.head_id)

    const head = s.heads.find((h) => h.id === line.head_id)
    if (head && head.status !== 'CANCELED') {
      const all = s.lines.filter((l) => l.head_id === head.id)
      if (all.every((l) => l.completion)) head.status = 'DONE'
      else if (head.actual_qty > 0) head.status = 'IN_PROGRESS'
    }
    persist()
    return wait(undefined)
  },

  saveTopend: (headId, row) => {
    const s = db()
    if (row.id) {
      const t = s.topends.find((x) => x.id === row.id)
      if (t) Object.assign(t, row)
    } else {
      const seq = Math.max(0, ...s.topends.filter((x) => x.head_id === headId).map((x) => x.actual_seq)) + 1
      s.topends.push({ ...row, id: uid(), head_id: headId, actual_seq: seq } as ActualTopend)
    }
    const head = s.heads.find((h) => h.id === headId)
    if (head) {
      head.top_end_weight_kg = s.topends
        .filter((x) => x.head_id === headId && x.topend_div === 'T')
        .reduce((a, x) => a + Number(x.weight_kg || 0), 0)
    }
    persist()
    return wait(undefined)
  },

  deleteTopend: (id: string) => {
    const s = db()
    s.topends = s.topends.filter((x) => x.id !== id)
    persist()
    return wait(undefined)
  },

  machineStatuses: () => {
    const s = db()
    const rows: MachineStatusView[] = s.machines
      .filter((m) => m.use_yn)
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((machine) => {
        const current = s.logs
          .filter((l) => l.machine_id === machine.id && !l.ended_at)
          .sort((a, b) => b.started_at.localeCompare(a.started_at))[0] ?? null
        return {
          machine,
          current,
          reason: current?.reason_id ? s.reasons.find((r) => r.id === current.reason_id) ?? null : null,
          head: current?.head_id ? s.heads.find((h) => h.id === current.head_id) ?? null : null,
          elapsed_min: current
            ? Math.round((Date.now() - new Date(current.started_at).getTime()) / 60000)
            : 0,
        }
      })
    return wait(rows)
  },

  changeMachineState: (machineId: string, state: MachineState, opts) => {
    const s = db()
    const now = new Date().toISOString()
    s.logs.filter((l) => l.machine_id === machineId && !l.ended_at)
      .forEach((l) => { l.ended_at = now })
    s.logs.push({
      id: uid(), machine_id: machineId, state, started_at: now, ended_at: null,
      reason_id: opts?.reasonId ?? null, head_id: opts?.headId ?? null,
      worker_id: opts?.workerId ?? null, source: 'MANUAL', note: opts?.note ?? null,
    })
    persist()
    return wait(undefined)
  },

  listMachineLogs: (machineId: string, date: string) => {
    const rows: MachineStatusLog[] = db().logs
      .filter((l) => l.machine_id === machineId && l.started_at.slice(0, 10) === date)
      .sort((a, b) => b.started_at.localeCompare(a.started_at))
    return wait(rows)
  },

  machineDaily: (from: string, to: string) => {
    const s = db()
    const map = new Map<string, MachineDaily>()
    for (const l of s.logs) {
      const d = l.started_at.slice(0, 10)
      if (d < from || d > to) continue
      const key = `${l.machine_id}|${d}`
      const cur = map.get(key) ?? {
        machine_id: l.machine_id, work_date: d,
        run_h: 0, setup_h: 0, idle_h: 0, down_h: 0, planned_stop_h: 0,
      }
      const end = l.ended_at ? new Date(l.ended_at).getTime() : Date.now()
      const h = (end - new Date(l.started_at).getTime()) / 3600_000
      if (l.state === 'RUN') cur.run_h += h
      else if (l.state === 'SETUP') cur.setup_h += h
      else if (l.state === 'IDLE') cur.idle_h += h
      else if (l.state === 'DOWN') cur.down_h += h
      else cur.planned_stop_h += h
      map.set(key, cur)
    }
    const round2 = (v: number) => Math.round(v * 100) / 100
    return wait([...map.values()].map((r) => ({
      ...r,
      run_h: round2(r.run_h), setup_h: round2(r.setup_h), idle_h: round2(r.idle_h),
      down_h: round2(r.down_h), planned_stop_h: round2(r.planned_stop_h),
    })))
  },
}
