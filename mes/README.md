# 정원철강 MES — 1단계

옛 인피니티21 P-MES(PowerBuilder + Oracle)를 대체하는 웹 MES.
1단계 목적은 완성된 MES가 아니라 **현장의 종이 수기를 없애는 것**이다.

- 대상 공정: 슬리팅(SL) / 절단·시어링(SH)
- 스택: React + TypeScript + Vite + Supabase(PostgreSQL)

## 설치

```bash
npm install
cp .env.example .env    # 값 채우기
npm run dev
```

`.env` 를 만들지 않으면 **데모(목업) 모드**로 뜬다. 브라우저 localStorage 에
샘플 데이터를 심어 Supabase 없이 전체 화면을 그대로 써 볼 수 있다.

## Supabase 설정

1. **SQL Editor** 에서 `supabase/migrations/` 의 SQL 을 번호 순서대로 실행

   | 파일 | 내용 |
   |---|---|
   | `0001_core.sql` | 기준정보 · 작업지시 3단 구조 · 채번 · 검증 트리거 |
   | `0002_machine_status.sql` | 설비 가동 로그 (수기) |
   | `0003_seed_master.sql` | 설비 · 철판종류 · 계산공식 · 비가동사유 초기값 |

2. **Settings → Data API → Exposed schemas** 에 `mes` 추가
   (이 앱은 `public` 이 아니라 `mes` 스키마를 쓴다. 누락하면 전부 404)

3. **Settings → API Keys** 에서 키 복사 → `.env`

   ```
   VITE_SUPABASE_URL=https://<프로젝트>.supabase.co
   VITE_SUPABASE_ANON_KEY=<anon 또는 publishable 키>
   ```

RLS 는 로그인(authenticated) 사용자에게만 전체 권한을 준다. 익명 접근은 차단된다.

## 데이터 모델 — 3단 구조

옛 MES 구조를 그대로 가져왔다. 코일 한 본이 제품 여러 개로 갈라지는 것을
표현하는 최소 구조다.

```
work_order_heads   작업지시 헤드 (코일 단위)   ← IPLN_JW_WORK_ORDER_HEAD
  └ work_order_specs   가공 명세 (어떻게 자를지) ← IPLN_JW_WORK_ORDER_SPEC
      └ work_order_lines   지시 행 (제품별 지시 + 실적) ← IPLN_WORK_ORDER_MASTER
```

부수 테이블: `actual_topends` (TOP/END·스크랩, `topend_div` = `T`/`S`),
`coils`, `customers`, `items`, `machines`, `plate_types`, `calc_formulas`.

### 옛 MES 에서 의도적으로 바꾼 것

| 항목 | 옛 MES | 여기 |
|---|---|---|
| 작업지시 채번 | `SUBSTR(...) MAX + 1` | `wo_no_counters` + 행 잠금 (`next_wo_no()`) — 동시 입력 충돌 방지 |
| 철판종류 | 품목마스터 `attribute05` | 정식 테이블 `plate_types` (비중 포함) |
| 계산식 | Oracle 함수에 하드코딩 | `calc_formulas` 설정 행 + `src/lib/calc.ts` 엔진 |
| 지시 행 컬럼 | 84개 | 1단계에 필요한 것만. 나머지는 필요할 때 추가 |

## ⚠ 계산식 — 확정 전이다

옛 MES 의 실제 계산은 Oracle 전용 함수(`UF_JW_SL_WEIGHT_NEW` 등 26개)에 있었고
**회수하지 못했다.** 소스에 주석으로 남아 있던 공식만 확보했으며,
`_NEW` / `_TOT` 변형이 있었다는 것은 공식이 개정됐다는 뜻이다.

그래서 계산식을 코드에 고정하지 않았다.

- **배분 방식** = `calc_formulas.method` → `src/lib/calc.ts` 의 `METHODS` 레지스트리
  - `WIDTH_PRORATA` 폭 비례배분 (회수한 옛 공식, 기본값)
  - `EQUAL_WEIGHT` 중량동일 배분 (옛 화면의 "계산방식(중량동일)계산" 근거)
- **파라미터** = `calc_formulas.params` (비중, 반올림 자리수, 트림 보정)
  → DB 에서 값만 바꾸면 된다

현재 초기값(폭 비례배분):

```
제품폭합계 = Σ(제품폭 × 절수)
수량       = 절수 × 분할
단중       = ((코일중량 ÷ 제품폭합계) × 제품폭) ÷ 분할 ÷ 절수
제품중량   = 단중 × 계획수량
로스       = 코일폭 − 제품폭합계
스크랩중량 = 코일중량 − Σ(제품중량)
길이(세로) = (코일중량 ÷ 코일폭 ÷ 코일두께 ÷ 비중) × 1000
```

**현장 확인 후 값을 확정할 것.**

## 검증 규칙

옛 MES 소스에서 그대로 옮겼다. 메시지 문구도 현장이 쓰던 표현을 유지한다.
`src/lib/validate.ts` (화면) + `0001_core.sql` 트리거·제약 (DB) 양쪽에 건다.

- 계획수량 ≥ 1 / 계획수량 ≥ 실적수량
- 당일 이전 계획 수정 불가, 설비 이동은 당일분만
- 실적 존재 시 삭제 불가, 생산 진행중 지시 삭제 불가
- 작업시간 4자리 HHMM (시 00~23 / 분 00~59)
- 필수: 작업지시일 · 코일번호 · 고객사 · 설비 · 품목 · 교대조 · 계획수량
- 실적 입력 시 등급 필수 / 스크랩 입력 시 스크랩 품목 필수

## 2단계 이후

- **설비 PLC 자동 수집** — 태그맵(`ICOM_PLC_ADDRESS_MAP`)을 회수하지 못해 1단계에서는 불가.
  대비만 해 뒀다: 실적·가동로그에 `actual_source` (`MANUAL` / `AUTO`) 컬럼이 이미 있어
  화면 변경 없이 전환된다.
- 품질검사 · 설비보전 · 금형관리 · 재고/출하 연계

## 현장 확인 필요 항목

1. 단중 계산을 실제로 어떻게 하는가 (회수 못 한 공식의 정답)
2. "계산공식구분"에 어떤 방식들이 있었고 언제 무엇을 쓰는가
3. 로스와 스크랩의 관리 기준
4. TOP/END 중량은 실측인가 추정인가
5. 소재환원(되감기) 빈도
6. 작업지시서에서 실제로 보는 항목
7. 등급 값의 종류 (`src/lib/labels.ts` 의 `GRADE_OPTIONS` 는 임시값)
8. 교대조 운영 방식
9. 불량 분류 체계
10. 종이로 하면서 제일 불편한 것
