"""
read_excel.py
Excel 파일에서 용어집 데이터를 읽는다.
"""

import json
import sys
from pathlib import Path

# Windows 콘솔 UTF-8 출력 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "output" / "game-localizer" / "glossary_config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"❌ 설정 파일이 없습니다: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def read_from_excel(config: dict) -> dict:
    """
    Excel 파일에서 용어집 데이터 로드
    Returns: {source_term: {lang_code: translation, ...}, ...}
    """
    try:
        import openpyxl
    except ImportError:
        print("❌ openpyxl 패키지가 없습니다. 설치: pip install openpyxl")
        sys.exit(1)

    excel_path = ROOT / config.get("excel_path", "docs/glossary.xlsx")
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel 파일 없음: {excel_path}")

    wb = openpyxl.load_workbook(str(excel_path), read_only=True, data_only=True)
    ws = wb.active  # 첫 번째 시트 사용

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        print("⚠️  Excel 파일이 비어 있습니다.")
        return {}

    # 첫 행을 헤더로 처리
    headers = [str(h).strip().lower() if h else "" for h in rows[0]]

    source_lang = config.get("source_lang", "ko")
    target_langs = config.get("target_langs", ["ja", "en", "zh"])
    all_langs = [source_lang] + target_langs

    # 컬럼 인덱스 매핑
    lang_indices = {}
    source_idx = None

    for i, h in enumerate(headers):
        if h == "source":
            source_idx = i
        elif h in all_langs:
            lang_indices[h] = i

    if source_idx is None:
        # "source" 컬럼 없으면 source_lang 컬럼을 source로 사용
        if source_lang in [h for h in headers]:
            source_idx = headers.index(source_lang)
        else:
            print("❌ Excel에 'source' 컬럼이 없습니다.")
            return {}

    terms = {}
    for row in rows[1:]:
        if not row or not row[source_idx]:
            continue
        source_key = str(row[source_idx]).strip()
        if not source_key:
            continue

        entry = {"_source": "excel"}
        for lang, idx in lang_indices.items():
            if idx < len(row) and row[idx]:
                val = str(row[idx]).strip()
                if val:
                    entry[lang] = val
        # source_lang 도 추가
        entry[source_lang] = source_key

        if len(entry) > 2:  # _source + source_lang 외에 데이터 있으면 추가
            terms[source_key] = entry

    wb.close()
    print(f"✅ Excel: {len(terms)}개 용어 로드 완료")
    return terms


if __name__ == "__main__":
    config = load_config()
    terms = read_from_excel(config)
    print(json.dumps(terms, ensure_ascii=False, indent=2))
