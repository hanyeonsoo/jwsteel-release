import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

/** Supabase 접속정보가 없으면 데모(목업) 모드로 동작한다. */
export const isMockMode = !url || !key

export const supabase: SupabaseClient | null = isMockMode
  ? null
  : createClient(url!, key!, {
      db: { schema: 'mes' },
      auth: { persistSession: true, autoRefreshToken: true },
    })
