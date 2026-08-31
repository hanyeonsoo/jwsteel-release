import { supabase } from '@/lib/supabase'
import type {
  ActualTopend, CalcFormula, Coil, Customer, DowntimeReason, Item, Machine,
  MachineDaily, MachineState, MachineStatusLog, MachineStatusView, OrderDiv,
  PlateType, WorkOrderFull, WorkOrderHead, WorkOrderHeadView, WorkOrderLine,
  WorkOrderSpec, WoStatus,
} from '@/lib/types'
import type { ActualPatch, HeadFilter, MesApi, WorkOrderInput } from './types'

function sb() {
  if (!supabase) throw new Error('Supabase 접속 정보가 없습니다')
  return supabase
}

/** PostgREST 오류를 사용자 문구로 바꾼다 (DB 트리거의 raise exception 메시지 포함) */
function fail(error: { message: string } | null): never | void {
  if (!error) return
  throw new Error(error.message)
}

export const supabaseApi: MesApi = {
  async listMachines() {
    const { data, error } = await sb().from('machines').select('*')
      .eq('use_yn', true).order('sort_order')
    fail(error)
    return (data ?? []) as Machine[]
  },

  async listCustomers() {
    const { data, error } = await sb().from('customers').select('*')
      .eq('use_yn', true).order('name')
    fail(error)
    return (data ?? []) as Customer[]
  },

  async listPlateTypes() {
    const { data, error } = await sb().from('plate_types').select('*')
      .eq('use_yn', true).order('sort_order')
    fail(error)
    return (data ?? []) as PlateType[]
  },

  async listItems(itemClass?: Item['item_class']) {
    let q = sb().from('items').select('*').eq('use_yn', true).order('code')
    if (itemClass) q = q.eq('item_class', itemClass)
    const { data, error } = await q
    fail(error)
    return (data ?? []) as Item[]
  },

  async listCoils(keyword?: string) {
    let q = sb().from('coils').select('*').eq('use_yn', true).order('coil_no', { ascending: false })
    const k = (keyword ?? '').trim()
    if (k) q = q.or(`coil_no.ilike.%${k}%,lot_no.ilike.%${k}%,material_name.ilike.%${k}%`)
    const { data, error } = await q.limit(200)
    fail(error)
    return (data ?? []) as Coil[]
  },

  async listFormulas() {
    const { data, error } = await sb().from('calc_formulas').select('*').eq('use_yn', true).order('code')
    fail(error)
    return (data ?? []) as CalcFormula[]
  },

  async listReasons() {
    const { data, error } = await sb().from('downtime_reasons').select('*')
      .eq('use_yn', true).order('sort_order')
    fail(error)
    return (data ?? []) as DowntimeReason[]
  },

  async listHeads(f: HeadFilter) {
    let q = sb().from('v_work_order_head').select('*')
      .order('work_order_date', { ascending: false })
      .order('wo_no')
    if (f.from) q = q.gte('work_order_date', f.from)
    if (f.to) q = q.lte('work_order_date', f.to)
    if (f.machineId) q = q.eq('machine_id', f.machineId)
    if (f.orderDiv) q = q.eq('order_div', f.orderDiv)
    if (f.status) q = q.eq('status', f.status)
    const k = (f.keyword ?? '').trim()
    if (k) q = q.or(`wo_no.ilike.%${k}%,coil_no.ilike.%${k}%,customer_name.ilike.%${k}%`)
    const { data, error } = await q.limit(500)
    fail(error)
    return (data ?? []) as WorkOrderHeadView[]
  },

  async getWorkOrder(id: string) {
    const [head, specs, lines, topends] = await Promise.all([
      sb().from('work_order_heads').select('*').eq('id', id).maybeSingle(),
      sb().from('work_order_specs').select('*').eq('head_id', id).order('proc_seq'),
      sb().from('work_order_lines').select('*').eq('head_id', id).order('line_seq'),
      sb().from('actual_topends').select('*').eq('head_id', id).order('actual_seq'),
    ])
    fail(head.error); fail(specs.error); fail(lines.error); fail(topends.error)
    if (!head.data) return null
    return {
      head: head.data as WorkOrderHead,
      specs: (specs.data ?? []) as WorkOrderSpec[],
      lines: (lines.data ?? []) as WorkOrderLine[],
      topends: (topends.data ?? []) as ActualTopend[],
    } satisfies WorkOrderFull
  },

  async nextWoNo(date: string, div: OrderDiv) {
    // 미리보기용 — 실제 채번은 저장 시 next_wo_no() 가 수행한다.
    const { count, error } = await sb().from('work_order_heads')
      .select('id', { count: 'exact', head: true })
      .eq('work_order_date', date).eq('order_div', div)
    fail(error)
    return date.slice(2).replace(/-/g, '') + div + String((count ?? 0) + 1).padStart(3, '0')
  },

  async createWorkOrder(input: WorkOrderInput) {
    const client = sb()
    const { data: woNo, error: seqErr } = await client.rpc('next_wo_no', {
      p_date: input.head.work_order_date,
      p_div: input.head.order_div,
    })
    fail(seqErr)

    const { data: head, error } = await client.from('work_order_heads')
      .insert({ ...input.head, wo_no: woNo }).select('id').single()
    fail(error)
    const headId = (head as { id: string }).id

    const specIds = await insertSpecs(headId, input.specs)
    await insertLines(headId, input.lines, specIds)
    return headId
  },

  async updateWorkOrder(id: string, input: WorkOrderInput) {
    const client = sb()
    fail((await client.from('work_order_heads').update(input.head).eq('id', id)).error)

    // 실적 보존 : 기존 행의 실적 값을 읽어 line_seq 기준으로 되돌려 넣는다.
    const { data: prev, error: prevErr } = await client.from('work_order_lines')
      .select('*').eq('head_id', id)
    fail(prevErr)
    const prevBySeq = new Map<number, WorkOrderLine>(
      ((prev ?? []) as WorkOrderLine[]).map((l) => [l.line_seq, l]))

    fail((await client.from('work_order_lines').delete().eq('head_id', id)).error)
    fail((await client.from('work_order_specs').delete().eq('head_id', id)).error)

    const specIds = await insertSpecs(id, input.specs)
    const merged = input.lines.map((l) => {
      const keep = prevBySeq.get(l.line_seq)
      return keep
        ? {
            ...l,
            actual_qty: keep.actual_qty, good_qty: keep.good_qty, bad_qty: keep.bad_qty,
            bad_weight_kg: keep.bad_weight_kg, good_weight_kg: keep.good_weight_kg,
            grade: keep.grade, bad_reason: keep.bad_reason, work_date: keep.work_date,
            start_time: keep.start_time, end_time: keep.end_time, completion: keep.completion,
          }
        : l
    })
    await insertLines(id, merged, specIds)
  },

  async deleteWorkOrder(id: string) {
    fail((await sb().from('work_order_heads').delete().eq('id', id)).error)
  },

  async setStatus(id: string, status: WoStatus) {
    fail((await sb().from('work_order_heads').update({ status }).eq('id', id)).error)
  },

  async markPrinted(id: string) {
    const client = sb()
    const { data, error } = await client.from('work_order_heads')
      .select('print_count, status').eq('id', id).single()
    fail(error)
    const row = data as { print_count: number; status: WoStatus }
    fail((await client.from('work_order_heads').update({
      printed_at: new Date().toISOString(),
      print_count: row.print_count + 1,
      ...(row.status === 'PLANNED' ? { status: 'RELEASED' as WoStatus } : {}),
    }).eq('id', id)).error)
  },

  async saveActual(lineId: string, patch: ActualPatch) {
    const client = sb()
    const { data, error } = await client.from('work_order_lines')
      .select('head_id, unit_weight_kg, good_qty, bad_qty').eq('id', lineId).single()
    fail(error)
    const cur = data as { head_id: string; unit_weight_kg: number | null; good_qty: number; bad_qty: number }
    const unit = Number(cur.unit_weight_kg ?? 0)
    const good = Number(patch.good_qty ?? cur.good_qty)
    const bad = Number(patch.bad_qty ?? cur.bad_qty)

    fail((await client.from('work_order_lines').update({
      ...patch,
      good_weight_kg: Math.round(unit * good * 10) / 10,
      bad_weight_kg: Math.round(unit * bad * 10) / 10,
    }).eq('id', lineId)).error)

    // 헤드 상태 자동 전이 (롤업 자체는 DB 트리거가 처리)
    const { data: lines, error: lerr } = await client.from('work_order_lines')
      .select('completion, actual_qty').eq('head_id', cur.head_id)
    fail(lerr)
    const rows = (lines ?? []) as Array<{ completion: boolean; actual_qty: number }>
    const next: WoStatus | null = rows.length && rows.every((r) => r.completion)
      ? 'DONE'
      : rows.some((r) => Number(r.actual_qty) > 0) ? 'IN_PROGRESS' : null
    if (next) {
      fail((await client.from('work_order_heads').update({ status: next })
        .eq('id', cur.head_id).neq('status', 'CANCELED')).error)
    }
  },

  async saveTopend(headId, row) {
    const client = sb()
    if (row.id) {
      fail((await client.from('actual_topends').update(row).eq('id', row.id)).error)
    } else {
      const { count, error } = await client.from('actual_topends')
        .select('id', { count: 'exact', head: true }).eq('head_id', headId)
      fail(error)
      fail((await client.from('actual_topends')
        .insert({ ...row, head_id: headId, actual_seq: (count ?? 0) + 1 })).error)
    }
    const { data, error: sumErr } = await client.from('actual_topends')
      .select('weight_kg').eq('head_id', headId).eq('topend_div', 'T')
    fail(sumErr)
    const total = ((data ?? []) as Array<{ weight_kg: number }>)
      .reduce((a, r) => a + Number(r.weight_kg || 0), 0)
    fail((await client.from('work_order_heads')
      .update({ top_end_weight_kg: total }).eq('id', headId)).error)
  },

  async deleteTopend(id: string) {
    fail((await sb().from('actual_topends').delete().eq('id', id)).error)
  },

  async machineStatuses() {
    const client = sb()
    const [machines, logs, reasons] = await Promise.all([
      client.from('machines').select('*').eq('use_yn', true).order('sort_order'),
      client.from('machine_status_logs').select('*').is('ended_at', null),
      client.from('downtime_reasons').select('*'),
    ])
    fail(machines.error); fail(logs.error); fail(reasons.error)

    const openLogs = (logs.data ?? []) as MachineStatusLog[]
    const headIds = openLogs.map((l) => l.head_id).filter((v): v is string => !!v)
    let heads: WorkOrderHead[] = []
    if (headIds.length) {
      const { data, error } = await client.from('work_order_heads').select('*').in('id', headIds)
      fail(error)
      heads = (data ?? []) as WorkOrderHead[]
    }

    return ((machines.data ?? []) as Machine[]).map((machine) => {
      const current = openLogs.find((l) => l.machine_id === machine.id) ?? null
      return {
        machine,
        current,
        reason: current?.reason_id
          ? ((reasons.data ?? []) as DowntimeReason[]).find((r) => r.id === current.reason_id) ?? null
          : null,
        head: current?.head_id ? heads.find((h) => h.id === current.head_id) ?? null : null,
        elapsed_min: current
          ? Math.round((Date.now() - new Date(current.started_at).getTime()) / 60000)
          : 0,
      } satisfies MachineStatusView
    })
  },

  async changeMachineState(machineId: string, state: MachineState, opts) {
    const { error } = await sb().rpc('change_machine_state', {
      p_machine_id: machineId,
      p_state: state,
      p_reason_id: opts?.reasonId ?? null,
      p_head_id: opts?.headId ?? null,
      p_worker_id: opts?.workerId ?? null,
      p_note: opts?.note ?? null,
    })
    fail(error)
  },

  async listMachineLogs(machineId: string, date: string) {
    const { data, error } = await sb().from('machine_status_logs').select('*')
      .eq('machine_id', machineId)
      .gte('started_at', `${date}T00:00:00`)
      .lte('started_at', `${date}T23:59:59`)
      .order('started_at', { ascending: false })
    fail(error)
    return (data ?? []) as MachineStatusLog[]
  },

  async machineDaily(from: string, to: string) {
    const { data, error } = await sb().from('v_machine_daily').select('*')
      .gte('work_date', from).lte('work_date', to)
    fail(error)
    return ((data ?? []) as MachineDaily[]).map((r) => ({
      ...r,
      run_h: Number(r.run_h ?? 0), setup_h: Number(r.setup_h ?? 0),
      idle_h: Number(r.idle_h ?? 0), down_h: Number(r.down_h ?? 0),
      planned_stop_h: Number(r.planned_stop_h ?? 0),
    }))
  },
}

async function insertSpecs(headId: string, specs: WorkOrderInput['specs']): Promise<string[]> {
  if (!specs.length) return []
  const { data, error } = await sb().from('work_order_specs')
    .insert(specs.map((s) => ({ ...s, head_id: headId })))
    .select('id, proc_seq')
  fail(error)
  return ((data ?? []) as Array<{ id: string; proc_seq: number }>)
    .sort((a, b) => a.proc_seq - b.proc_seq)
    .map((r) => r.id)
}

async function insertLines(
  headId: string, lines: WorkOrderInput['lines'], specIds: string[],
): Promise<void> {
  if (!lines.length) return
  fail((await sb().from('work_order_lines').insert(
    lines.map((l, i) => ({ ...l, head_id: headId, spec_id: specIds[i] ?? null })),
  )).error)
}
