# -*- coding: utf-8 -*-
"""
upload_to_gsheets.py
--------------------
xlsx 파일을 Google Drive API를 통해 Google Sheets로 업로드합니다.
mimeType 변환 방식을 사용하므로 포맷(셀 스타일, 수식 등)이 최대한 보존됩니다.

[설치 방법]
    pip install google-auth google-auth-oauthlib google-api-python-client

[인증 방법 - 우선순위]
  1. credentials/service_account.json (서비스 계정 키 파일)
     - Google Cloud Console > IAM > 서비스 계정 > 키 생성 (JSON) 후 저장
     - 해당 서비스 계정 이메일에 Drive 공유 권한 필요
  2. credentials/oauth_client.json + credentials/oauth_token.json (OAuth2)
     - Google Cloud Console > API 및 서비스 > OAuth 2.0 클라이언트 ID 생성 후
       credentials/oauth_client.json 으로 저장
     - 최초 실행 시 브라우저 인증 후 credentials/oauth_token.json 에 토큰 캐시

[환경변수 대안]
    GOOGLE_SERVICE_ACCOUNT_JSON — Base64로 인코딩된 서비스 계정 JSON 전체 내용
    예) export GOOGLE_SERVICE_ACCOUNT_JSON=$(base64 -w0 credentials/service_account.json)
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows UTF-8 호환성
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# 경로 상수
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_JSON_DIR = OUTPUT_DIR / "json"

SERVICE_ACCOUNT_FILE = CREDENTIALS_DIR / "service_account.json"
OAUTH_CLIENT_FILE = CREDENTIALS_DIR / "oauth_client.json"
OAUTH_TOKEN_FILE = CREDENTIALS_DIR / "oauth_token.json"
RESULT_FILE = OUTPUT_JSON_DIR / "last_gsheets_upload.json"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GSHEETS_MIME = "application/vnd.google-apps.spreadsheet"


# ---------------------------------------------------------------------------
# 인증 헬퍼
# ---------------------------------------------------------------------------

def _build_credentials_from_env():
    """환경변수 GOOGLE_SERVICE_ACCOUNT_JSON (Base64)에서 서비스 계정 인증 생성."""
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return None
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        info = json.loads(decoded)
    except Exception as exc:
        print(
            f"[경고] GOOGLE_SERVICE_ACCOUNT_JSON 파싱 실패: {exc}",
            file=sys.stderr,
        )
        return None

    try:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception as exc:
        print(f"[경고] 환경변수 서비스 계정 인증 실패: {exc}", file=sys.stderr)
        return None


def _build_credentials_from_service_account():
    """credentials/service_account.json 파일에서 서비스 계정 인증 생성."""
    if not SERVICE_ACCOUNT_FILE.exists():
        return None
    try:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(
            str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
        )
    except Exception as exc:
        print(
            f"[경고] 서비스 계정 파일 인증 실패 ({SERVICE_ACCOUNT_FILE}): {exc}",
            file=sys.stderr,
        )
        return None


def _build_credentials_from_oauth():
    """credentials/oauth_client.json + oauth_token.json (캐시) 로 OAuth2 인증 생성."""
    if not OAUTH_CLIENT_FILE.exists():
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError as exc:
        print(f"[오류] OAuth 라이브러리 임포트 실패: {exc}", file=sys.stderr)
        return None

    creds = None
    if OAUTH_TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(OAUTH_TOKEN_FILE), SCOPES)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:
            print(f"[경고] 토큰 갱신 실패, 재인증을 진행합니다: {exc}", file=sys.stderr)
            creds = None

    if not creds or not creds.valid:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(OAUTH_CLIENT_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        except Exception as exc:
            print(f"[오류] OAuth 인증 플로우 실패: {exc}", file=sys.stderr)
            return None

        # 토큰 캐시 저장
        try:
            OAUTH_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            OAUTH_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            print(f"[정보] OAuth 토큰이 저장되었습니다: {OAUTH_TOKEN_FILE}", file=sys.stderr)
        except Exception as exc:
            print(f"[경고] 토큰 캐시 저장 실패: {exc}", file=sys.stderr)

    return creds


def get_credentials():
    """
    우선순위에 따라 Google API 인증 정보를 반환합니다.
      1. 환경변수 GOOGLE_SERVICE_ACCOUNT_JSON
      2. credentials/service_account.json
      3. credentials/oauth_client.json (OAuth2 대화형)
    """
    creds = _build_credentials_from_env()
    if creds:
        print("[인증] 환경변수(GOOGLE_SERVICE_ACCOUNT_JSON) 서비스 계정 사용", file=sys.stderr)
        return creds

    creds = _build_credentials_from_service_account()
    if creds:
        print(f"[인증] 서비스 계정 파일 사용: {SERVICE_ACCOUNT_FILE}", file=sys.stderr)
        return creds

    creds = _build_credentials_from_oauth()
    if creds:
        print("[인증] OAuth2 사용자 인증 사용", file=sys.stderr)
        return creds

    raise RuntimeError(
        "Google 인증 정보를 찾을 수 없습니다.\n"
        "다음 중 하나를 준비해주세요:\n"
        "  1. credentials/service_account.json  (서비스 계정 키)\n"
        "  2. credentials/oauth_client.json     (OAuth2 클라이언트)\n"
        "  3. 환경변수 GOOGLE_SERVICE_ACCOUNT_JSON (Base64 인코딩 JSON)"
    )


# ---------------------------------------------------------------------------
# 업로드 로직
# ---------------------------------------------------------------------------

def upload_xlsx_as_gsheets(
    xlsx_path: Path,
    title: str,
    folder_id: str | None,
    share_email: str | None,
) -> dict:
    """
    xlsx 파일을 Google Sheets로 변환 업로드합니다.

    Returns:
        dict with keys: url, spreadsheet_id, title, uploaded_at
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise RuntimeError(
            f"google-api-python-client 임포트 실패: {exc}\n"
            "pip install google-auth google-auth-oauthlib google-api-python-client"
        ) from exc

    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)

    # --- 파일 메타데이터 ---
    file_metadata: dict = {
        "name": title,
        "mimeType": GSHEETS_MIME,  # 업로드 시 Google Sheets로 변환
    }
    if folder_id:
        file_metadata["parents"] = [folder_id]

    # --- 업로드 ---
    media = MediaFileUpload(str(xlsx_path), mimetype=XLSX_MIME, resumable=True)
    print(f"[정보] 업로드 중: {xlsx_path.name} → Google Sheets '{title}'", file=sys.stderr)

    uploaded = (
        drive_service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id,name,webViewLink",
        )
        .execute()
    )

    file_id = uploaded["id"]
    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{file_id}/edit"

    print(f"[정보] 업로드 완료. 파일 ID: {file_id}", file=sys.stderr)

    # --- 누구나 링크로 볼 수 있도록 권한 설정 ---
    _set_anyone_can_view(drive_service, file_id)

    # --- 특정 이메일에 편집 권한 공유 ---
    if share_email:
        _share_with_email(drive_service, file_id, share_email)

    return {
        "url": spreadsheet_url,
        "spreadsheet_id": file_id,
        "title": title,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }


def _set_anyone_can_view(drive_service, file_id: str):
    """링크를 아는 누구나 볼 수 있도록 권한을 부여합니다."""
    try:
        drive_service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
        ).execute()
        print("[정보] '링크 공유(뷰어)' 권한이 설정되었습니다.", file=sys.stderr)
    except Exception as exc:
        print(f"[경고] 링크 공유 권한 설정 실패: {exc}", file=sys.stderr)


def _share_with_email(drive_service, file_id: str, email: str):
    """지정 이메일에 편집자 권한을 부여합니다."""
    try:
        drive_service.permissions().create(
            fileId=file_id,
            body={"type": "user", "role": "writer", "emailAddress": email},
            fields="id",
            sendNotificationEmail=False,
        ).execute()
        print(f"[정보] 편집 권한 공유 완료: {email}", file=sys.stderr)
    except Exception as exc:
        print(f"[경고] 이메일 공유 실패 ({email}): {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 결과 저장
# ---------------------------------------------------------------------------

def save_result(result: dict, dest: "Path | None" = None):
    """업로드 결과를 지정 경로(또는 output/json/last_gsheets_upload.json)에 저장합니다."""
    target = dest if dest is not None else RESULT_FILE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[정보] 결과 저장 완료: {target}", file=sys.stderr)
    except Exception as exc:
        print(f"[경고] 결과 파일 저장 실패: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="xlsx 파일을 Google Sheets로 업로드합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 기본 업로드
  python scripts/upload_to_gsheets.py output/events.xlsx

  # 커스텀 제목 지정
  python scripts/upload_to_gsheets.py output/events.xlsx --title "이벤트기획_260611_260618"

  # Drive 폴더 지정 + 이메일 공유
  python scripts/upload_to_gsheets.py output/events.xlsx \\
      --folder-id 1AbCdEfGhIjKlMnOpQrStUv \\
      --share glpark0413@wemadeplus.com
""",
    )
    parser.add_argument(
        "xlsx_path",
        type=str,
        help="업로드할 xlsx 파일 경로",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Google Sheets 제목 (미지정 시 파일명에서 확장자 제거)",
    )
    parser.add_argument(
        "--folder-id",
        type=str,
        default=None,
        dest="folder_id",
        help="업로드할 Google Drive 폴더 ID",
    )
    parser.add_argument(
        "--share",
        type=str,
        default=None,
        help="편집 권한을 부여할 이메일 주소",
    )
    return parser.parse_args()


def main():
    # 프로젝트별 경로 반영
    import sys as _sys_ug
    _sys_ug.path.insert(0, str(PROJECT_ROOT / "scripts"))
    try:
        from _project_config import load_project_paths as _lpp_ug
        _pp = _lpp_ug()
        if _pp:
            result_file = _pp.last_gsheets_upload
        else:
            result_file = RESULT_FILE
    except ImportError:
        result_file = RESULT_FILE

    args = parse_args()

    xlsx_path = Path(args.xlsx_path).resolve()
    if not xlsx_path.exists():
        print(
            f"[오류] 파일을 찾을 수 없습니다: {xlsx_path}",
            file=sys.stderr,
        )
        sys.exit(1)
    if xlsx_path.suffix.lower() not in {".xlsx", ".xls"}:
        print(
            f"[경고] xlsx/xls 파일이 아닐 수 있습니다: {xlsx_path.suffix}",
            file=sys.stderr,
        )

    title = args.title or xlsx_path.stem

    try:
        result = upload_xlsx_as_gsheets(
            xlsx_path=xlsx_path,
            title=title,
            folder_id=args.folder_id,
            share_email=args.share,
        )
    except RuntimeError as exc:
        print(f"\n[오류] {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[오류] 예기치 않은 오류가 발생했습니다: {exc}", file=sys.stderr)
        sys.exit(1)

    save_result(result, result_file)

    # stdout에 URL 출력 (다른 스크립트에서 파이프로 사용 가능)
    print(f"Google Sheets URL: {result['url']}")


if __name__ == "__main__":
    main()
