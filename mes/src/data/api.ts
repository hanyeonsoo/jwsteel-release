import { isMockMode } from '@/lib/supabase'
import { mockApi } from './mockApi'
import { supabaseApi } from './supabaseApi'
import type { MesApi } from './types'

/** Supabase 접속 정보가 없으면 데모(목업) 모드로 자동 전환된다. */
export const api: MesApi = isMockMode ? mockApi : supabaseApi
export { isMockMode }
export type { ActualPatch, HeadFilter, WorkOrderInput } from './types'
