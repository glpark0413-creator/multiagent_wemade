"""
gdrive_utils.py
Google Drive / Google Sheets 공개 링크 공통 유틸리티

지원 URL 형식:
  - https://docs.google.com/spreadsheets/d/{ID}/...  → Sheets CSV 다운로드
  - https://drive.google.com/file/d/{ID}/view        → Drive 파일(xlsx 등) 다운로드
  - https://drive.google.com/open?id={ID}             → Drive 파일 다운로드
"""

import re
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# ── URL 패턴 인식 ─────────────────────────────────────────────────────────────

def is_sheets_url(url: str) -> bool:
    return "docs.google.com/spreadsheets" in url

def is_drive_url(url: str) -> bool:
    return "drive.google.com" in url and "spreadsheets" not in url

def is_google_url(url: str) -> bool:
    return is_sheets_url(url) or is_drive_url(url)

def extract_sheet_id(url: str) -> str:
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
    if m:
        return m.group(1)
    raise ValueError(f"Sheets ID를 찾을 수 없습니다: {url}")

def build_sheets_xlsx_url(sheet_id: str) -> str:
    """Google Sheets → xlsx 다운로드 URL"""
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"

def extract_drive_file_id(url: str) -> str:
    """
    Drive 파일 공유 링크에서 file ID 추출.
    형식: /file/d/{ID}/ 또는 ?id={ID}
    """
    m = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if m:
        return m.group(1)
    raise ValueError(f"Drive 파일 ID를 추출할 수 없습니다: {url}")

def build_drive_download_url(file_id: str) -> str:
    """공개 Drive 파일의 직접 다운로드 URL 생성."""
    return f"https://drive.google.com/uc?id={file_id}&export=download&confirm=t"

# ── 다운로드 ──────────────────────────────────────────────────────────────────

_HEADERS = {"User-Agent": "Mozilla/5.0"}

def _fetch_bytes(url: str, timeout: int = 30) -> bytes:
    req = Request(url, headers=_HEADERS)
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.read()
    except HTTPError as e:
        if e.code in (401, 403):
            raise PermissionError(
                f"접근 거부 (HTTP {e.code}). "
                "공유 설정을 '링크가 있는 모든 사용자 — 뷰어'로 변경하세요."
            )
        raise RuntimeError(f"HTTP 오류 {e.code}: {e.reason}")
    except URLError as e:
        raise RuntimeError(f"네트워크 오류: {e.reason}")

def download_drive_file(url: str, dest_dir: Path = None, suffix: str = ".xlsx") -> Path:
    """
    Google Drive 공개 링크에서 파일을 다운로드해 로컬 임시 경로로 저장.
    Returns: 다운로드된 로컬 파일 Path
    """
    file_id  = extract_drive_file_id(url)
    dl_url   = build_drive_download_url(file_id)
    data     = _fetch_bytes(dl_url)

    # 내용으로 형식 추정 (PK = zip/xlsx, 기타 = xls)
    if data[:2] == b'PK':
        suffix = ".xlsx"
    elif data[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        suffix = ".xls"

    if dest_dir is None:
        dest_dir = Path(tempfile.gettempdir())
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"gdrive_{file_id}{suffix}"
    dest.write_bytes(data)
    print(f"Drive 파일 다운로드 완료: {dest.name} ({len(data)//1024} KB)")
    return dest

# ── 통합 진입점 ───────────────────────────────────────────────────────────────

def download_sheets_as_xlsx(url: str, dest_dir: Path = None) -> Path:
    """
    Google Sheets 공개 링크를 xlsx로 다운로드.
    """
    sheet_id = extract_sheet_id(url)
    dl_url   = build_sheets_xlsx_url(sheet_id)
    data     = _fetch_bytes(dl_url)

    if dest_dir is None:
        dest_dir = Path(tempfile.gettempdir())
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"sheets_{sheet_id}.xlsx"
    dest.write_bytes(data)
    print(f"Sheets xlsx 다운로드 완료: {dest.name} ({len(data)//1024} KB)")
    return dest


def resolve_to_local_file(url_or_path: str, dest_dir: Path = None) -> Path:
    """
    URL 또는 로컬 경로를 받아 항상 로컬 파일 Path를 반환.
    - 로컬 경로          → 그대로 반환
    - Google Sheets URL  → xlsx로 다운로드
    - Google Drive URL   → 파일 다운로드
    """
    p = Path(url_or_path)
    if p.exists():
        return p

    if is_sheets_url(url_or_path):
        return download_sheets_as_xlsx(url_or_path, dest_dir=dest_dir)

    if is_drive_url(url_or_path):
        return download_drive_file(url_or_path, dest_dir=dest_dir)

    raise FileNotFoundError(
        f"파일을 찾을 수 없습니다: {url_or_path}\n"
        "로컬 경로 또는 Google Sheets/Drive 공개 링크를 입력하세요."
    )
