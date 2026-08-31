import type {
  ActualTopend, CalcFormula, Coil, Customer, DowntimeReason, Item, Machine,
  MachineDaily, MachineState, MachineStatusLog, MachineStatusView, OrderDiv,
  PlateType, WorkOrderFull, WorkOrderHead, WorkOrderHeadView, WorkOrderLine,
  WorkOrderSpec, WoStatus,
} from '@/lib/types'

/** 작업지시 저장 입력 */
export interface WorkOrderInput {
  head: Omit<WorkOrderHead,
    | 'id' | 'wo_no' | 'created_at' | 'updated_at' | 'created_by'
    | 'plan_qty' | 'actual_qty' | 'good_qty' | 'bad_qty' | 'bad_weight_kg'
    | 'printed_at' | 'print_count'>
  specs: Array<Omit<WorkOrderSpec, 'id' | 'head_id'>>
  lines: Array<Omit<WorkOrderLine, 'id' | 'head_id'>>
}

export interface HeadFilter {
  from?: string
  to?: string
  machineId?: string
  orderDiv?: OrderDiv
  status?: WoStatus
  keyword?: string
}

/** 실적 입력 패치 */
export type ActualPatch = Partial<Pick<WorkOrderLine,
  | 'actual_qty' | 'good_qty' | 'bad_qty' | 'bad_weight_kg' | 'good_weight_kg'
  | 'grade' | 'bad_reason' | 'banding_qty' | 'work_date'
  | 'start_time' | 'end_time' | 'completion' | 'note' | 'actual_source'>>

export interface MesApi {
  // 기준정보
  listMachines(): Promise<Machine[]>
  listCustomers(): Promise<Customer[]>
  listPlateTypes(): Promise<PlateType[]>
  listItems(itemClass?: Item['item_class']): Promise<Item[]>
  listCoils(keyword?: string): Promise<Coil[]>
  listFormulas(): Promise<CalcFormula[]>
  listReasons(): Promise<DowntimeReason[]>

  // 작업지시
  listHeads(filter: HeadFilter): Promise<WorkOrderHeadView[]>
  getWorkOrder(id: string): Promise<WorkOrderFull | null>
  nextWoNo(date: string, div: OrderDiv): Promise<string>
  createWorkOrder(input: WorkOrderInput): Promise<string>
  updateWorkOrder(id: string, input: WorkOrderInput): Promise<void>
  deleteWorkOrder(id: string): Promise<void>
  setStatus(id: string, status: WoStatus): Promise<void>
  markPrinted(id: string): Promise<void>

  // 실적
  saveActual(lineId: string, patch: ActualPatch): Promise<void>
  saveTopend(headId: string, row: Omit<ActualTopend, 'id' | 'head_id' | 'actual_seq'> & { id?: string }): Promise<void>
  deleteTopend(id: string): Promise<void>

  // 설비 가동
  machineStatuses(): Promise<MachineStatusView[]>
  changeMachineState(
    machineId: string, state: MachineState,
    opts?: { reasonId?: string | null; headId?: string | null; workerId?: string | null; note?: string | null },
  ): Promise<void>
  listMachineLogs(machineId: string, date: string): Promise<MachineStatusLog[]>
  machineDaily(from: string, to: string): Promise<MachineDaily[]>
}
