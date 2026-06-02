"""
merge_glossary.py
Google Sheets + Excel 용어집을 우선순위 기반으로 병합하여 glossary_cache.json 저장.

우선순위: Google Sheets > Excel
동일 키 충돌 시 Google Sheets 값 적용 + conflicts_log 기록

사용법:
    python merge_glossary.py              # 양쪽 모두 로드
    python merge_glossary.py --skip-gsheet  # Excel만
    python merge_glossary.py --skip-excel   # Google Sheets만
"""

import json
import sys
import os

# Windows 콘솔 UTF-8 출력 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "output" / "game-localizer" / "glossary_config.json"
CACHE_PATH = ROOT / "output" / "game-localizer" / "glossary_cache.json"
OUTPUT_DIR = ROOT / "output" / "game-localizer"

KST = timezone(timedelta(hours=9))


def load_config() -> dict:
    """설정 파일 로드, 없으면 기본 설정 파일 생성"""
    if not CONFIG_PATH.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        default_config = {
            "gsheet_url": "",
            "gsheet_worksheet": "Sheet1",
            "excel_path": "docs/glossary.xlsx",
            "credentials_path": "docs/gsheet_credentials.json",
            "source_lang": "ko",
            "target_langs": ["ja", "en", "zh"]
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        print(f"📄 설정 파일 생성됨: {CONFIG_PATH}")
        print("   gsheet_url, credentials_path, excel_path 를 설정 후 다시 실행하세요.")
        sys.exit(0)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def merge_terms(gsheet_terms: dict, excel_terms: dict) -> tuple[dict, list]:
    """
    두 용어집을 병합한다.
    Returns: (merged_terms, conflicts_log)
    """
    merged = {}
    conflicts_log = []

    # Excel 먼저 로드
    for key, entry in excel_terms.items():
        merged[key] = dict(entry)
        merged[key]["_source"] = "excel"

    # Google Sheets로 덮어쓰기 (우선순위 높음)
    for key, gsheet_entry in gsheet_terms.items():
        if key in merged:
            excel_entry = merged[key]
            # 언어별로 충돌 검사
            conflict_langs = {}
            for lang, gval in gsheet_entry.items():
                if lang.startswith("_"):
                    continue
                excel_val = excel_entry.get(lang, "")
                if excel_val and excel_val != gval:
                    conflict_langs[lang] = {"gsheet": gval, "excel": excel_val}

            if conflict_langs:
                conflicts_log.append({
                    "key": key,
                    "conflicts": conflict_langs,
                    "applied": "gsheet"
                })

        new_entry = dict(gsheet_entry)
        new_entry["_source"] = "gsheet"
        merged[key] = new_entry

    return merged, conflicts_log


def save_cache(merged: dict, conflicts_log: list, sources_used: list):
    """병합 결과를 glossary_cache.json으로 저장"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cache = {
        "generated_at": datetime.now(KST).isoformat(),
        "source_priority": ["gsheet", "excel"],
        "sources_loaded": sources_used,
        "term_count": len(merged),
        "conflict_count": len(conflicts_log),
        "terms": merged,
        "conflicts_log": conflicts_log
    }

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"💾 용어집 캐시 저장: {CACHE_PATH}")
    print(f"   총 용어 수: {len(merged)}개")
    if conflicts_log:
        print(f"   충돌 처리: {len(conflicts_log)}건 (Google Sheets 우선 적용)")


def main():
    skip_gsheet = "--skip-gsheet" in sys.argv
    skip_excel = "--skip-excel" in sys.argv

    config = load_config()

    gsheet_terms = {}
    excel_terms = {}
    sources_used = []

    # Google Sheets 로드
    if not skip_gsheet:
        gsheet_url = config.get("gsheet_url", "").strip()
        if not gsheet_url:
            print("⚠️  gsheet_url 이 설정되지 않았습니다. Google Sheets 로드 건너뜀.")
        else:
            try:
                # 동적 임포트 (같은 패키지 내)
                sys.path.insert(0, str(Path(__file__).parent))
                from fetch_gsheet import fetch_from_gsheet
                gsheet_terms = fetch_from_gsheet(config)
                sources_used.append("gsheet")
            except FileNotFoundError as e:
                print(f"⚠️  Google Sheets 로드 실패: {e}")
                print("   Excel 단독 사용으로 전환합니다.")
            except Exception as e:
                print(f"⚠️  Google Sheets 로드 오류: {e}")
                print("   Excel 단독 사용으로 전환합니다.")

    # Excel 로드
    if not skip_excel:
        excel_path = ROOT / config.get("excel_path", "docs/glossary.xlsx")
        if not excel_path.exists():
            print(f"⚠️  Excel 파일이 없습니다: {excel_path}")
        else:
            try:
                sys.path.insert(0, str(Path(__file__).parent))
                from read_excel import read_from_excel
                excel_terms = read_from_excel(config)
                sources_used.append("excel")
            except Exception as e:
                print(f"⚠️  Excel 로드 오류: {e}")

    # 둘 다 실패 시
    if not gsheet_terms and not excel_terms:
        print("❌ 모든 용어집 소스 로드 실패.")
        print("   빈 용어집으로 진행하시겠습니까? 번역은 용어집 없이 진행됩니다.")
        # 빈 캐시 저장 (에이전트가 판단할 수 있도록)
        save_cache({}, [], [])
        sys.exit(1)

    # 병합
    merged, conflicts_log = merge_terms(gsheet_terms, excel_terms)

    # 저장
    save_cache(merged, conflicts_log, sources_used)

    if conflicts_log:
        print("\n📋 충돌 처리 내역 (상위 5건):")
        for c in conflicts_log[:5]:
            print(f"  - '{c['key']}': {c['conflicts']} → gsheet 값 적용")


if __name__ == "__main__":
    main()
