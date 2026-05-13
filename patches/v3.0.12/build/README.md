# v3.0.12 원클릭 빌드

## 사전 조건
- `C:\jwsteel-v311-temp\` 에 v3.0.11 이 설치되어 있어야 함 (이미 한 상태)
- Python 3.12 + Inno Setup 6 설치됨 (이미 확인됨)

## 사용법

1. 이 폴더(`patches/v3.0.12/`)를 통째로 PC 어딘가에 두기
   - 예: `C:\Users\hysoo\Downloads\jwsteel-v3.0.12-patch\`
2. `build\BUILD_v3.0.12.bat` 더블클릭
3. 1~2분 후 완료, 자동으로 결과 폴더(`C:\jwsteel-v3.0.12-build\output\`) 열림
4. `JWSteel_Setup_v3.0.12.exe` 가 생성됨

## 배치가 하는 일

1. 빌드 폴더 `C:\jwsteel-v3.0.12-build\` 정리
2. `C:\jwsteel-v311-temp\` → `dist\JWSteel\` 로 복사 (사용자 데이터/설정/구 인스톨러는 제외)
3. 패치 5개 덮어쓰기:
   - `ui/widgets/_filter_bar.py`
   - `ui/widgets/inventory.py`
   - `ui/widgets/inventory_picker.py`
   - `updater.py`
   - `VERSION.txt`
4. `installer.iss` 배치 (AppId 유지, 버전만 3.0.12로 갱신)
5. Inno Setup 컴파일러(ISCC.exe) 실행

## PyInstaller 안 돌리는 이유

v3.0.11 설치 폴더 자체가 PyInstaller 빌드 결과(`dist\JWSteel\`)와 동일 구조입니다.
새로 PyInstaller 돌리지 않고 그 결과물에 패치 5개만 덮어써서 다시 묶으면 충분합니다.
- 빠름 (1~2분)
- 의존성 버전이 v3.0.11과 100% 동일하므로 호환 문제 없음
- v3.0.12 의 변경은 순수 Python 코드 5개라 재컴파일 불필요

## 배포

생성된 `JWSteel_Setup_v3.0.12.exe`를 jwsteel-release 에 새 릴리스로 업로드:

1. https://github.com/hanyeonsoo/jwsteel-release/releases/new
2. **Tag**: `v3.0.12`
3. **Title**: `JWSteel 통합전산 v3.0.12 (재고 화면 인라인 컬럼 필터)`
4. **Body** (예시):
   ```markdown
   ## v3.0.12 — 재고 화면 인라인 컬럼 필터

   ### 추가
   - 재고 현황 / 재고 픽커 화면에 헤더 바로 아래 노란색 인라인 입력행 추가
   - 다른 메뉴와 동일한 UX: 입력 즉시 필터, 우클릭으로 연산자 변경
   - 기존 헤더 우클릭 팝업 필터와 AND 결합

   ### 수정
   - 두 필터가 setRowHidden 을 두고 다투던 충돌 해결

   ### 설치
   - 이전 버전이 있으면 자동 업데이트 (프로그램 내 [업데이트])
   - 처음이면 JWSteel_Setup_v3.0.12.exe 다운로드 후 설치
   ```
5. **Attach**: `JWSteel_Setup_v3.0.12.exe` 드래그
6. **Publish release**

업로드 후 사용자들은 자동 업데이트 알림을 받게 됩니다 (`updater.py`가
`version.json`에서 최신 버전 감지). 단 `version.json`도 Supabase Storage에
별도로 갱신해야 자동 알림이 동작합니다.
