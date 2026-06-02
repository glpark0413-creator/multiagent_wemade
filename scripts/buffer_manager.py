"""
buffer_manager.py
세션 번역 버퍼(session_buffer.json) 관리.

사용법:
    python buffer_manager.py add     # translate_result.json → 버퍼에 추가
    python buffer_manager.py list    # 버퍼 목록 출력
    python buffer_manager.py stats   # 통계 출력
    python buffer_manager.py clear   # 버퍼 초기화
"""

import json
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Windows 콘솔 UTF-8 출력 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR   = ROOT / "output" / "game-localizer"
BUFFER_PATH  = OUTPUT_DIR / "session_buffer.json"
RESULT_PATH  = OUTPUT_DIR / "translate_result.json"
REQUEST_PATH = OUTPUT_DIR / "translate_request.json"

KST = timezone(timedelta(hours=9))


def load_buffer() -> dict:
    """버퍼 파일 로드, 없으면 초기 구조 반환"""
    if not BUFFER_PATH.exists():
        return {
            "session_id": str(uuid.uuid4()),
            "created_at": datetime.now(KST).isoformat(),
            "entries": []
        }
    with open(BUFFER_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_buffer(buffer: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    buffer["updated_at"] = datetime.now(KST).isoformat()
    with open(BUFFER_PATH, "w", encoding="utf-8") as f:
        json.dump(buffer, f, ensure_ascii=False, indent=2)


def load_json(path: Path) -> dict:
    if not path.exists():
        print(f"❌ 파일 없음: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_add():
    """translate_result.json + translate_request.json → 버퍼에 추가"""
    result = load_json(RESULT_PATH)
    request = load_json(REQUEST_PATH)

    buffer = load_buffer()
    entries = buffer.get("entries", [])

    new_id = len(entries) + 1
    entry = {
        "id": new_id,
        "timestamp": datetime.now(KST).isoformat(),
        "source_text": request.get("source_text", ""),
        "text_type": result.get("text_type", "unknown"),
        "translations": result.get("translations", {}),
        "unregistered_terms": result.get("unregistered_terms", []),
        "validation_status": result.get("validation_status", "unknown"),
        "matched_term_count": len(request.get("matched_terms", {}))
    }

    entries.append(entry)
    buffer["entries"] = entries
    save_buffer(buffer)

    print(f"✅ 버퍼 추가 완료 (#{new_id}): {entry['source_text'][:40]}...")
    print(f"   세션 누적: {len(entries)}건")


def cmd_list():
    """버퍼 항목 목록 출력"""
    buffer = load_buffer()
    entries = buffer.get("entries", [])

    if not entries:
        print("📭 세션 버퍼가 비어 있습니다.")
        return

    print(f"📋 세션 버퍼 ({len(entries)}건) | 세션 ID: {buffer.get('session_id', '-')}")
    print("─" * 60)
    for e in entries:
        langs = list(e.get("translations", {}).keys())
        unregistered = e.get("unregistered_terms", [])
        warn = " ⚠️" if unregistered else ""
        print(f"  #{e['id']:3d} [{e['text_type']:10s}] {e['source_text'][:35]:<35}{warn}")
        print(f"       언어: {langs} | {e['timestamp'][:19]}")
    print("─" * 60)


def cmd_stats():
    """버퍼 통계 출력"""
    buffer = load_buffer()
    entries = buffer.get("entries", [])

    if not entries:
        print("📭 세션 버퍼가 비어 있습니다.")
        return

    type_count = {}
    total_unregistered = set()
    validation_issues = 0

    for e in entries:
        t = e.get("text_type", "unknown")
        type_count[t] = type_count.get(t, 0) + 1
        total_unregistered.update(e.get("unregistered_terms", []))
        if e.get("validation_status") not in ("pass", "pass_with_warnings"):
            validation_issues += 1

    print(f"📊 세션 통계")
    print(f"   총 번역 건수: {len(entries)}건")
    print(f"   유형별 분포: {type_count}")
    print(f"   누적 미지정 용어: {len(total_unregistered)}개 {sorted(total_unregistered) if total_unregistered else ''}")
    print(f"   품질 이슈 건수: {validation_issues}건")
    print(f"   세션 시작: {buffer.get('created_at', '-')[:19]}")


def cmd_clear():
    """버퍼 초기화"""
    buffer = load_buffer()
    count = len(buffer.get("entries", []))

    if count == 0:
        print("📭 버퍼가 이미 비어 있습니다.")
        return

    # 새 세션으로 초기화
    new_buffer = {
        "session_id": str(uuid.uuid4()),
        "created_at": datetime.now(KST).isoformat(),
        "entries": []
    }
    save_buffer(new_buffer)
    print(f"🗑️  버퍼 초기화 완료 ({count}건 삭제)")


COMMANDS = {
    "add": cmd_add,
    "list": cmd_list,
    "stats": cmd_stats,
    "clear": cmd_clear,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"사용법: python buffer_manager.py [{' | '.join(COMMANDS.keys())}]")
        sys.exit(1)

    COMMANDS[sys.argv[1]]()
