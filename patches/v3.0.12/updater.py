"""
자동 업데이트 모듈
- Supabase DB에서 최신 버전 정보 조회
- 새 버전 있으면 알림 표시
- 클릭 한 번에 다운로드 + 설치
"""
import os
import sys
import json
import subprocess
import tempfile
import urllib.request
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox, QTextEdit,
)

# 현재 버전 (빌드마다 갱신; VERSION.txt 우선, 못 찾을 때 폴백)
CURRENT_VERSION = "3.0.12"

# Supabase Storage URLs
ZIP_URL = "https://nziqdobyuuhvkknyjusq.supabase.co/storage/v1/object/public/JWSteel/accounting_final.zip"
VERSION_INFO_URL = "https://nziqdobyuuhvkknyjusq.supabase.co/storage/v1/object/public/JWSteel/version.json"


def get_current_version() -> str:
    """현재 설치된 버전 — frozen / dev 환경 모두에서 VERSION.txt 정상 탐색"""
    candidates = []
    if getattr(sys, 'frozen', False):
        # PyInstaller --onedir: VERSION.txt 는 _internal/ 안에 datas 로 들어감
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidates.append(Path(meipass) / "VERSION.txt")
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "_internal" / "VERSION.txt")
        candidates.append(exe_dir / "VERSION.txt")
    else:
        # 개발 환경 — updater.py 가 프로젝트 루트에 있음
        candidates.append(Path(__file__).resolve().parent / "VERSION.txt")

    for c in candidates:
        try:
            if c.exists():
                return c.read_text(encoding='utf-8').strip()
        except Exception:
            continue
    return CURRENT_VERSION


def fetch_latest_version() -> dict:
    """Supabase에서 최신 버전 정보 가져오기"""
    try:
        with urllib.request.urlopen(VERSION_INFO_URL, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data
    except Exception:
        # 폴백: 빈 정보 반환
        return {
            "version": CURRENT_VERSION,
            "release_date": "",
            "release_notes": "",
            "zip_url": ZIP_URL,
        }


def compare_versions(current: str, latest: str) -> int:
    """버전 비교: latest > current 면 1, 같으면 0, current > latest 면 -1"""
    def parse(v):
        return [int(x) for x in v.strip().lstrip('v').split('.')]
    try:
        c = parse(current)
        l = parse(latest)
        # 길이 맞추기
        while len(c) < len(l): c.append(0)
        while len(l) < len(c): l.append(0)
        for a, b in zip(c, l):
            if b > a: return 1
            if a > b: return -1
        return 0
    except Exception:
        return 0


class UpdateDownloader(QThread):
    progress = pyqtSignal(int)  # 0~100
    finished_ok = pyqtSignal(str)  # 다운로드 파일 경로
    failed = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            tmp_dir = tempfile.gettempdir()
            # URL 확장자 보고 .exe / .zip 둘 다 지원
            url_lower = self.url.lower().split("?")[0]
            ext = ".exe" if url_lower.endswith(".exe") else ".zip"
            target = os.path.join(tmp_dir, f"jwsteel_update{ext}")

            def reporthook(count, block_size, total_size):
                if total_size > 0:
                    pct = int(count * block_size * 100 / total_size)
                    self.progress.emit(min(pct, 100))

            urllib.request.urlretrieve(self.url, target, reporthook)
            self.finished_ok.emit(target)
        except Exception as e:
            self.failed.emit(str(e))


class UpdateAvailableDialog(QDialog):
    """업데이트 알림 다이얼로그"""

    def __init__(self, parent, version_info: dict):
        super().__init__(parent)
        self.version_info = version_info
        self.setWindowTitle("🎉 새 버전이 있습니다")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 헤더
        title = QLabel("🎉 새 버전이 출시되었습니다")
        title.setStyleSheet(
            "font-size: 16pt; font-weight: bold; color: #2563eb; padding: 8px;")
        layout.addWidget(title)

        # 버전 정보
        current = get_current_version()
        latest = self.version_info.get('version', '?')
        info = QLabel(
            f"  현재 버전: <b>v{current}</b><br/>"
            f"  최신 버전: <b style='color:#16a34a'>v{latest}</b><br/>"
            f"  출시일: {self.version_info.get('release_date', '-')}"
        )
        info.setStyleSheet(
            "background: #f9fafb; padding: 14px; border-radius: 6px; "
            "border: 1px solid #e5e7eb; font-size: 11pt;")
        layout.addWidget(info)

        # 릴리스 노트
        notes = self.version_info.get('release_notes', '').strip()
        if notes:
            notes_label = QLabel("📝 변경 사항:")
            notes_label.setStyleSheet(
                "font-weight: bold; margin-top: 12px; padding: 4px;")
            layout.addWidget(notes_label)

            notes_box = QTextEdit()
            notes_box.setPlainText(notes)
            notes_box.setReadOnly(True)
            notes_box.setMaximumHeight(150)
            notes_box.setStyleSheet(
                "background: white; border: 1px solid #e5e7eb; padding: 10px;")
            layout.addWidget(notes_box)

        # 안내
        guide = QLabel(
            "💡 업데이트 진행:\n"
            "  1. [업데이트] 클릭 → ZIP 다운로드 (5MB, 약 30초)\n"
            "  2. 다운로드 완료 후 안내에 따라 설치\n"
            "  3. 데이터는 모두 보존됩니다 (클라우드 DB)"
        )
        guide.setStyleSheet(
            "background: #dbeafe; color: #1e3a8a; padding: 12px; "
            "border-radius: 6px; margin: 10px 0;")
        layout.addWidget(guide)

        # 진행률
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #6b7280; padding: 4px;")
        layout.addWidget(self.status_label)

        # 버튼
        btns = QHBoxLayout()
        btns.addStretch()

        self.later_btn = QPushButton("나중에")
        self.later_btn.setStyleSheet(
            "background: white; color: #374151; padding: 10px 20px; "
            "border: 1px solid #d1d5db; border-radius: 4px;")
        self.later_btn.clicked.connect(self.reject)
        btns.addWidget(self.later_btn)

        self.update_btn = QPushButton("🚀 지금 업데이트")
        self.update_btn.setStyleSheet(
            "background: #16a34a; color: white; padding: 10px 24px; "
            "font-weight: bold; border-radius: 4px;")
        self.update_btn.clicked.connect(self._start_download)
        btns.addWidget(self.update_btn)

        layout.addLayout(btns)

    def _start_download(self):
        self.update_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.status_label.setText("⏳ 다운로드 중...")

        # 신규(setup_url, .exe 인스톨러) 우선, 폴백 zip_url
        url = (self.version_info.get('setup_url')
               or self.version_info.get('zip_url')
               or ZIP_URL)
        self.downloader = UpdateDownloader(url)
        self.downloader.progress.connect(self.progress.setValue)
        self.downloader.finished_ok.connect(self._on_download_done)
        self.downloader.failed.connect(self._on_download_failed)
        self.downloader.start()

    def _on_download_done(self, path):
        self.status_label.setText(f"✅ 다운로드 완료: {path}")
        self.progress.setValue(100)

        # 자동 설치 옵션
        reply = QMessageBox.question(
            self, "설치",
            f"다운로드 완료되었습니다.\n\n"
            f"  경로: {path}\n\n"
            "지금 설치를 진행할까요?\n"
            "(현재 프로그램이 종료되고 새 버전이 설치됩니다)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._install_and_restart(path)
        else:
            QMessageBox.information(
                self, "수동 설치",
                f"다운로드 파일을 직접 압축 해제해 주세요:\n{path}\n\n"
                "압축 해제 후 INSTALL.bat 또는 RUN.bat 을 실행하세요."
            )
            self.accept()

    def _on_download_failed(self, msg):
        self.status_label.setText(f"❌ 다운로드 실패: {msg}")
        QMessageBox.critical(self, "오류", f"다운로드 실패:\n{msg}")
        self.update_btn.setEnabled(True)
        self.later_btn.setEnabled(True)

    def _install_and_restart(self, downloaded_path):
        """다운로드 받은 파일 종류에 따라 업그레이드 실행
        - .exe : Inno Setup 인스톨러 사일런트 실행 (권장 신규 방식)
        - .zip : 레거시 ZIP 덮어쓰기 (Python 소스 배포 호환)
        """
        try:
            ext = os.path.splitext(downloaded_path)[1].lower()

            if ext == ".exe":
                # Inno Setup 사일런트 설치
                #   /SILENT             : 진행 화면만 표시, 질문 없음
                #   /CLOSEAPPLICATIONS  : 실행 중인 JWSteel 자동 종료/재시작
                #   /RESTARTAPPLICATIONS: 설치 후 자동 재실행
                #   /NORESTART          : OS 재부팅 안 함
                #   /SUPPRESSMSGBOXES   : 메시지 박스 자동 처리
                if sys.platform == "win32":
                    subprocess.Popen(
                        [downloaded_path,
                         "/SILENT",
                         "/CLOSEAPPLICATIONS",
                         "/RESTARTAPPLICATIONS",
                         "/NORESTART",
                         "/SUPPRESSMSGBOXES"],
                        creationflags=(
                            subprocess.CREATE_NEW_PROCESS_GROUP |
                            subprocess.DETACHED_PROCESS
                        ),
                        close_fds=True,
                    )

                QMessageBox.information(
                    self, "업데이트",
                    "업데이트 설치가 시작됩니다.\n\n"
                    "현재 프로그램이 자동 종료되고\n"
                    "새 버전이 설치된 후 자동으로 재실행됩니다.\n\n"
                    "(설치는 1~2분 소요)"
                )
                self.accept()
                QTimer.singleShot(500, sys.exit)
                return

            # 레거시 ZIP 경로 (소스 배포용)
            install_dir = Path(__file__).resolve().parent.parent.parent
            updater_script = install_dir / "_apply_update.bat"
            bat_content = f"""@echo off
echo Updating JWSteel...
timeout /t 2 /nobreak >nul
powershell -command "Expand-Archive -Path '{downloaded_path}' -DestinationPath '%TEMP%\\jwsteel_update' -Force"
xcopy /E /Y /Q "%TEMP%\\jwsteel_update\\accounting_final\\*" "{install_dir}\\"
rmdir /S /Q "%TEMP%\\jwsteel_update"
del "{downloaded_path}"
echo Update complete!
start "" "{install_dir}\\RUN.bat"
del "%~f0"
"""
            updater_script.write_text(bat_content, encoding='utf-8')

            if sys.platform == "win32":
                subprocess.Popen(
                    ["cmd", "/c", "start", "/min", "", str(updater_script)],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )

            QMessageBox.information(
                self, "재시작",
                "업데이트가 진행됩니다.\n"
                "프로그램이 종료된 후 새 버전이 자동으로 시작됩니다."
            )
            self.accept()
            QTimer.singleShot(500, sys.exit)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"설치 실패:\n{e}")


class UpdateChecker(QThread):
    """백그라운드에서 버전 체크"""
    update_available = pyqtSignal(dict)
    no_update = pyqtSignal()

    def run(self):
        latest_info = fetch_latest_version()
        latest_version = latest_info.get('version', CURRENT_VERSION)
        current = get_current_version()

        if compare_versions(current, latest_version) > 0:
            self.update_available.emit(latest_info)
        else:
            self.no_update.emit()


def check_for_updates(parent_window, silent=True):
    """
    업데이트 체크 (앱 시작 시 호출)
    silent=True: 새 버전 있을 때만 알림
    silent=False: 항상 결과 알림 (메뉴에서 수동 체크 시)
    """
    checker = UpdateChecker()

    def on_update(info):
        dlg = UpdateAvailableDialog(parent_window, info)
        dlg.exec()

    def on_no_update():
        if not silent:
            QMessageBox.information(
                parent_window, "업데이트 확인",
                f"최신 버전입니다.\n현재 버전: v{get_current_version()}"
            )

    checker.update_available.connect(on_update)
    checker.no_update.connect(on_no_update)
    checker.start()

    # 참조 유지 (가비지 컬렉션 방지)
    parent_window._update_checker = checker
