import type { MachineState, OrderDiv, TopendDiv, WoStatus } from './types'

export const ORDER_DIV_LABEL: Record<OrderDiv, string> = {
  SL: '슬리팅',
  SH: '절단',
}

export const WO_STATUS_LABEL: Record<WoStatus, string> = {
  PLANNED: '계획',
  RELEASED: '지시확정',
  IN_PROGRESS: '작업중',
  DONE: '완료',
  CANCELED: '취소',
}

export const WO_STATUS_TONE: Record<WoStatus, string> = {
  PLANNED: 'slate',
  RELEASED: 'blue',
  IN_PROGRESS: 'amber',
  DONE: 'green',
  CANCELED: 'red',
}

export const SHIFT_LABEL: Record<string, string> = {
  '1': '주간',
  '2': '야간',
}

export const TOPEND_DIV_LABEL: Record<TopendDiv, string> = {
  T: 'TOP/END',
  S: '스크랩',
}

export const MACHINE_STATE_LABEL: Record<MachineState, string> = {
  RUN: '가동',
  SETUP: '준비',
  IDLE: '대기',
  DOWN: '고장',
  PLANNED_STOP: '계획정지',
}

export const MACHINE_STATE_TONE: Record<MachineState, string> = {
  RUN: 'green',
  SETUP: 'blue',
  IDLE: 'slate',
  DOWN: 'red',
  PLANNED_STOP: 'violet',
}

/**
 * 등급 — 옛 MES 의 등급 값 종류는 회수하지 못했다(§6-7).
 * 현장 확인 후 이 목록을 확정할 것. 임시로 통용 표기를 넣어 둔다.
 */
export const GRADE_OPTIONS = ['A', 'B', 'C', '재작업'] as const

/**
 * 작업지시서 특기사항 기본 문구.
 * 옛 MES 에서 현장이 실제로 쓰던 표현이므로 문구를 그대로 유지한다.
 */
export const DEFAULT_SPECIAL_NOTES = [
  '◆ 작업 내용(수정) (1다발 OO매) - 전량 B급 → 작업 요망',
  '◆ 지정 매수 밴딩 요망',
  '◆ 스크랩, 탑앤드 미상차',
  '◆ T 라벨 부착 요청',
  '◆ 대각/평탄도 중요 (대각 허용오차 1~2mm)',
  '◆ 작업 이상 발생시 중단 후 연락 요청드립니다.',
  '   (이바리 / 대각 / 평탄도 / 웨이브 등)',
].join('\n')
