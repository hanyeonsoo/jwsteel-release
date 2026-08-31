import { useState } from 'react'
import { api } from '@/data/api'
import { useAsync } from '@/lib/hooks'
import { kg, mm } from '@/lib/format'
import { Empty, Modal } from './ui'
import type { Coil } from '@/lib/types'

/** 코일번호 팝업 검색 — 옛 MES 의 w_jw_coil_no_popup 대응 */
export function CoilPicker({ onPick, onClose }: {
  onPick: (coil: Coil) => void
  onClose: () => void
}) {
  const [keyword, setKeyword] = useState('')
  const { data: coils, loading } = useAsync(() => api.listCoils(keyword), [keyword], [])

  return (
    <Modal title="코일 검색" wide onClose={onClose}>
      <input
        autoFocus
        placeholder="코일번호 · 롯트 · 재질로 검색"
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        style={{ marginBottom: 12 }}
      />
      <div className="table-wrap" style={{ maxHeight: 380 }}>
        <table className="grid">
          <thead>
            <tr>
              <th>코일번호</th><th>롯트</th><th>재질</th>
              <th className="num">두께</th><th className="num">폭</th><th className="num">중량</th>
              <th>위치</th>
            </tr>
          </thead>
          <tbody>
            {coils.map((c) => (
              <tr key={c.id} className="is-clickable" onClick={() => { onPick(c); onClose() }}>
                <td className="mono strong">{c.coil_no}</td>
                <td className="muted">{c.lot_no ?? '-'}</td>
                <td>{c.material_name ?? '-'}</td>
                <td className="num">{mm(c.thickness_mm, 2)}</td>
                <td className="num">{mm(c.width_mm, 0)}</td>
                <td className="num">{kg(c.weight_kg, 0)}</td>
                <td className="muted">{c.location ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && coils.length === 0 && <Empty>검색 결과가 없습니다</Empty>}
      </div>
    </Modal>
  )
}
