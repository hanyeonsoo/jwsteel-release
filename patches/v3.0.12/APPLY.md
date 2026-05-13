# v3.0.12 패치 적용 가이드

## 변경 요약

**기능**: 재고 현황 / 재고 픽커 화면에 **인라인 컬럼 필터(노란 입력행)** 추가

기존 v3.0.11에는 두 재고 화면에 헤더 우클릭 팝업 필터만 있었음.
v3.0.12에서는 다른 메뉴와 동일하게 헤더 바로 아래 노란 입력행이 보이며,
기존 팝업 필터와도 AND 결합되어 함께 동작.

### 변경 파일 (5개)

| 파일 | 변경 |
|---|---|
| `ui/widgets/_filter_bar.py` | `apply_all_filters` 추가, 인라인+팝업 충돌 해결 |
| `ui/widgets/inventory.py` | 인라인 필터 명시 설치, 힌트 갱신, 통계 즉시 갱신 |
| `ui/widgets/inventory_picker.py` | 픽커 다이얼로그에 인라인 필터 설치 |
| `updater.py` | 폴백 상수 `CURRENT_VERSION` → `"3.0.12"` |
| `VERSION.txt` | `3.0.12` |

## 적용 절차

### 1. 소스 폴더로 이동
v3.0.11 소스가 있는 폴더 (집 PC 기준 예시):
```
cd C:\Users\hysoo\jwsteel-src
```

### 2. 패치 파일을 같은 경로 구조로 복사

이 폴더(`patches/v3.0.12/`) 안 파일을 소스 폴더에 그대로 덮어쓰기:

| 패치 경로 | 소스 폴더 내 대상 경로 |
|---|---|
| `ui/widgets/_filter_bar.py` | `ui/widgets/_filter_bar.py` |
| `ui/widgets/inventory.py` | `ui/widgets/inventory.py` |
| `ui/widgets/inventory_picker.py` | `ui/widgets/inventory_picker.py` |
| `updater.py` | `updater.py` |
| `VERSION.txt` | `VERSION.txt` |

CMD 한 줄로 (예시 경로 조정 필요):
```cmd
xcopy /Y patches\v3.0.12\ui\widgets\*.py C:\Users\hysoo\jwsteel-src\ui\widgets\
xcopy /Y patches\v3.0.12\updater.py C:\Users\hysoo\jwsteel-src\
xcopy /Y patches\v3.0.12\VERSION.txt C:\Users\hysoo\jwsteel-src\
```

### 3. `installer.iss` 버전 수정
소스 폴더의 `installer.iss` 열기, 한 줄만 변경:
```diff
- #define MyAppVersion "3.0.11"
+ #define MyAppVersion "3.0.12"
```

### 4. 빌드

**방법 A — 로컬 빌드 (Windows에서)**:
```cmd
BUILD_INSTALLER.bat
```
출력물: `Output\JWSteel_Setup_v3.0.12.exe`

**방법 B — GitHub Actions 빌드**:
- 소스가 GitHub 저장소에 있으면 `.github/workflows/build-installer.yml` 워크플로우가 자동 실행
- 워크플로우 자세히는 이 저장소의 `.github/workflows/build-installer.yml` 참고

### 5. 빌드 결과를 jwsteel-release 에 업로드
- `Output\JWSteel_Setup_v3.0.12.exe` 를 새 GitHub Release 자산으로 추가
- Tag: `v3.0.12`
- Title: `JWSteel 통합전산 v3.0.12 (재고 화면 인라인 컬럼 필터)`

## 동작 확인 체크리스트

설치 후 다음을 확인:

- [ ] 재고 현황 화면 진입 → 헤더 바로 아래 **노란색 띠 입력칸**이 컬럼마다 표시됨
- [ ] 노란 입력칸에 텍스트 입력 → 즉시 행 필터링
- [ ] 입력칸 우클릭 → 연산자 메뉴 (포함/제외/같음/시작/끝/크다/작다 등) 표시
- [ ] 헤더 우클릭(또는 좌클릭) → 기존 팝업 필터도 그대로 동작
- [ ] 인라인 + 팝업 동시 사용 → AND 결합 (둘 다 만족하는 행만 표시)
- [ ] "컬럼 필터 모두 초기화" 버튼 → 인라인·팝업 둘 다 초기화
- [ ] 매출 등록에서 "재고 픽커" 열기 → 같은 노란 띠 필터가 동일하게 표시
- [ ] 새로고침/재임포트 후에도 입력해둔 필터 유지
- [ ] 통합 대시보드(이전과 동일하게 필터 없음 유지)

## 참고

### Supabase 보안 주의

`updater.py` 안 Supabase Storage URL은 **public bucket**의 URL이라 그대로 노출되어 있어도
키 노출은 아니지만(서비스 키 ❌, 익명 키 ❌), 소스를 공개 저장소에 올리지는 마세요.
**비공개 저장소(private repo)** 에서만 작업하세요.

### 인라인 + 팝업 충돌 해결 방식

`_filter_bar.py`에 새로 추가한 `apply_all_filters(table)`는 두 필터를 단일 패스에서
AND 결합하여 적용합니다. `InlineFilterBar.apply`와 팝업의 `_apply_filters`도
서로의 존재를 감지하면 자동으로 통합 함수를 호출하도록 수정되었습니다.
기존 v3.0.11에서는 두 필터가 따로 `setRowHidden`을 호출해 마지막 실행이 이전 결과를
덮어쓰는 버그가 있었는데, 그 부분도 함께 해결됩니다.
