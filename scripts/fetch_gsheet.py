"""
fetch_gsheet.py
공개 Google Sheets에서 CSV export URL로 용어집 데이터를 가져온다.
서비스 계정 / API 키 불필요 (시트가 '링크 공개' 상태여야 함)

column_mapping 설정으로 시트 컬럼명 → 내부 lang 코드 매핑 지원:
  예) {"source": "KO", "ko": "KO", "en": "EN", "zh": "CT"}
"""

import csv
import io
import json
import re
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import quote

# Windows 콘솔 UTF-8 출력 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 프로젝트 루트 기준 경로
ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "output" / "game-localizer" / "glossary_config.json"


def load_config() -> dict:
    """설정 파일 로드"""
    if not CONFIG_PATH.exists():
        print(f"설정 파일이 없습니다: {CONFIG_PATH}")
        print("   output/glossary_config.json 을 생성하세요.")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def extract_sheet_id(url: str) -> str:
    """구글 시트 URL에서 Sheet ID 추출"""
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
    if not match:
        raise ValueError(f"유효하지 않은 구글 시트 URL: {url}")
    return match.group(1)


def build_csv_url(sheet_id: str, worksheet_name: str = None) -> str:
    """
    CSV 다운로드 URL 생성
    - 시트명 없음 / 기본값  → export?format=csv (첫 번째 시트)
    - 시트명 지정           → gviz/tq?tqx=out:csv&sheet=<name>
    """
    if worksheet_name and worksheet_name.strip():
        encoded = quote(worksheet_name.strip())
        return (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}"
            f"/gviz/tq?tqx=out:csv&sheet={encoded}"
        )
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv"
    )


def fetch_csv(csv_url: str, timeout: int = 15) -> str:
    """URL에서 CSV 텍스트 다운로드 (BOM 제거 포함)"""
    req = Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except HTTPError as e:
        if e.code in (401, 403):
            raise PermissionError(
                f"시트 접근 거부 (HTTP {e.code}). "
                "구글 시트 공유 설정을 '링크가 있는 모든 사용자 - 뷰어'로 변경하세요."
            )
        raise RuntimeError(f"HTTP 오류 {e.code}: {e.reason}")
    except URLError as e:
        raise RuntimeError(f"네트워크 오류: {e.reason}")

    return raw.decode("utf-8-sig")


def build_header_map(raw_fieldnames: list) -> dict:
    """
    헤더 이름의 앞뒤 공백을 제거한 매핑 반환
    반환: {stripped_name: original_name}
    예) {' KO': ' KO'} → {'KO': ' KO'}
    """
    return {h.strip(): h for h in raw_fieldnames}


def resolve_column(lang_or_col: str, header_map: dict) -> str | None:
    """
    stripped 헤더 맵에서 컬럼명 해석
    - 직접 일치 (공백 제거 후) 시 원본 헤더 반환
    - 없으면 None 반환
    """
    return header_map.get(lang_or_col.strip())


def parse_csv_to_terms(text: str, config: dict) -> dict:
    """
    CSV 텍스트를 파싱하여 {source_key: {lang: value, ...}} 형태로 반환

    column_mapping (config):
      시트 컬럼명이 표준 lang 코드와 다를 때 매핑 정의
      예) {"source": "KO", "ko": "KO", "en": "EN", "zh": "CT"}
      - source: 원문(검색 키)로 사용할 컬럼
      - 나머지 키: 내부 lang 코드 → 시트 컬럼명

    column_mapping 미설정 시:
      시트에 source, ko, ja, en, zh 컬럼이 직접 있어야 함
    """
    col_map = config.get("column_mapping", {})
    source_lang = config.get("source_lang", "ko")
    target_langs = config.get("target_langs", ["ja", "en", "zh"])
    all_langs = [source_lang] + target_langs

    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("CSV 데이터가 비어 있습니다.")

    # 헤더 공백 제거 맵 생성
    header_map = build_header_map(reader.fieldnames)
    stripped_names = list(header_map.keys())

    # source 컬럼 결정
    source_col_key = col_map.get("source", "source")
    source_col = resolve_column(source_col_key, header_map)
    if source_col is None:
        raise ValueError(
            f"source 컬럼 '{source_col_key}'을 찾을 수 없습니다.\n"
            f"   시트의 실제 컬럼: {stripped_names}\n"
            f"   output/glossary_config.json 의 column_mapping.source 값을 확인하세요."
        )

    # lang → 실제 시트 컬럼 매핑 사전 구성
    lang_to_col: dict[str, str] = {}
    for lang in all_langs:
        sheet_col_key = col_map.get(lang, lang)   # 매핑 없으면 lang 자체를 컬럼명으로
        actual_col = resolve_column(sheet_col_key, header_map)
        if actual_col:
            lang_to_col[lang] = actual_col
        # 없으면 해당 lang은 glossary에 포함되지 않음 (AI 번역으로 처리)

    print(f"  컬럼 매핑: source='{source_col}' | " +
          " | ".join(f"{l}='{c}'" for l, c in lang_to_col.items()))

    terms = {}
    for row in reader:
        source_key = str(row.get(source_col, "")).strip()
        if not source_key:
            continue

        entry = {"_source": "gsheet"}
        for lang, col in lang_to_col.items():
            val = str(row.get(col, "")).strip()
            if val:
                entry[lang] = val

        if len(entry) > 1:   # _source 외 실제 데이터가 있을 때만 추가
            terms[source_key] = entry

    return terms


def fetch_from_gsheet(config: dict) -> dict:
    """
    공개 Google Sheets에서 CSV로 용어집 로드 (인증 불필요)
    Returns: {source_term: {lang_code: translation, ...}, ...}
    """
    url = config.get("gsheet_url", "").strip()
    if not url:
        raise ValueError("gsheet_url 이 설정되지 않았습니다.")

    sheet_id = extract_sheet_id(url)
    worksheet_name = config.get("gsheet_worksheet", "")
    csv_url = build_csv_url(sheet_id, worksheet_name)

    print(f"  구글 시트 CSV 다운로드 중... (sheet_id: {sheet_id[:8]}...)")

    text = fetch_csv(csv_url)
    terms = parse_csv_to_terms(text, config)

    print(f"Google Sheets: {len(terms)}개 용어 로드 완료")
    return terms


def test_connection(config: dict) -> bool:
    """연결 테스트 (용어 3개 미리보기 포함)"""
    try:
        terms = fetch_from_gsheet(config)
        print(f"Google Sheets 연결 성공 ({len(terms)}개 용어 확인)")
        for i, (k, v) in enumerate(list(terms.items())[:3]):
            langs = {l: v[l] for l in v if not l.startswith("_")}
            print(f"  [{i+1}] {k} -> {langs}")
        return True
    except Exception as e:
        print(f"Google Sheets 연결 실패: {e}")
        return False


if __name__ == "__main__":
    config = load_config()

    if "--test" in sys.argv:
        test_connection(config)
    else:
        terms = fetch_from_gsheet(config)
        print(json.dumps(terms, ensure_ascii=False, indent=2))
