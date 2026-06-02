"""
match_terms.py
원문 텍스트에서 용어집 등록 용어를 찾아 matched_terms / unregistered_terms 분리.

실행: python match_terms.py
입력: output/translate_request.json + output/glossary_cache.json
출력: output/translate_request.json (matched_terms, unregistered_terms 필드 추가)
"""

import json
import re
import sys
from pathlib import Path

# Windows 콘솔 UTF-8 출력 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = ROOT / "output" / "game-localizer" / "translate_request.json"
CACHE_PATH = ROOT / "output" / "game-localizer" / "glossary_cache.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        print(f"❌ 파일 없음: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_matched_terms(source_text: str, glossary_terms: dict) -> dict:
    """
    원문에서 용어집 등록 용어 탐색.
    긴 용어 우선 매칭 (부분 겹침 방지).
    Returns: {term_key: {lang: translation, ...}}
    """
    matched = {}

    # 키를 길이 내림차순 정렬 (긴 용어 우선)
    sorted_keys = sorted(glossary_terms.keys(), key=len, reverse=True)

    text_lower = source_text.lower()

    for key in sorted_keys:
        key_lower = key.lower()
        if key_lower in text_lower:
            entry = {k: v for k, v in glossary_terms[key].items() if not k.startswith("_")}
            matched[key] = entry

    return matched


def find_unregistered_terms(source_text: str, matched_keys: set) -> list:
    """
    용어집에 없는 게임 고유 명사 후보 탐지.
    탐지 기준:
    - <...> 또는 [...] 로 감싸인 텍스트
    - 따옴표('...' 또는 "...") 로 감싸인 단어
    - 영어 대문자로 시작하는 2글자 이상 단어 (고유명사 패턴)
    - 한글 텍스트 내 외래어처럼 보이는 단어
    """
    unregistered = set()

    # <...> 패턴
    for m in re.finditer(r'<([^>]+)>', source_text):
        term = m.group(1).strip()
        if term and term not in matched_keys:
            unregistered.add(term)

    # [...] 패턴 (UI 변수가 아닌 경우)
    for m in re.finditer(r'\[([^\]]+)\]', source_text):
        term = m.group(1).strip()
        # 숫자만이거나 변수 패턴({0}, %s)은 제외
        if term and not re.match(r'^[\d\s%{}]+$', term) and term not in matched_keys:
            unregistered.add(term)

    # 따옴표로 감싸인 단어
    for m in re.finditer(r'["\']([^"\']{2,20})["\']', source_text):
        term = m.group(1).strip()
        if term and term not in matched_keys:
            unregistered.add(term)

    # 영어 대문자로 시작하는 고유명사 패턴 (단어 경계)
    for m in re.finditer(r'\b([A-Z][a-zA-Z]{1,})\b', source_text):
        term = m.group(1)
        # 일반 영어 단어 제외 (짧은 단어, 문장 시작 등)
        if len(term) >= 3 and term not in matched_keys and term.lower() not in {
            'the', 'and', 'or', 'but', 'for', 'not', 'you', 'are', 'was',
            'has', 'had', 'can', 'will', 'may', 'its', 'your', 'this',
            'that', 'with', 'have', 'from', 'they', 'she', 'him', 'her',
        }:
            unregistered.add(term)

    return sorted(unregistered)


def main():
    request = load_json(REQUEST_PATH)
    cache = load_json(CACHE_PATH)

    source_text = request.get("source_text", "")
    if not source_text:
        print("❌ translate_request.json 에 source_text 가 없습니다.")
        sys.exit(1)

    glossary_terms = cache.get("terms", {})

    print(f"🔍 원문: {source_text[:60]}{'...' if len(source_text) > 60 else ''}")
    print(f"📚 용어집 크기: {len(glossary_terms)}개 용어")

    # 매칭 실행
    matched = find_matched_terms(source_text, glossary_terms)
    matched_keys = set(matched.keys())
    unregistered = find_unregistered_terms(source_text, matched_keys)

    print(f"✅ 매칭된 용어: {len(matched)}개 {list(matched.keys()) if matched else '(없음)'}")
    if unregistered:
        print(f"⚠️  미지정 용어 후보: {unregistered}")

    # translate_request.json 업데이트
    request["matched_terms"] = matched
    request["unregistered_terms"] = unregistered

    save_json(REQUEST_PATH, request)
    print(f"💾 translate_request.json 업데이트 완료")


if __name__ == "__main__":
    main()
