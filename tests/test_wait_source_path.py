"""
wait_source_path 상태 머신 테스트
- CASE 1: available_tabs 없을 때 wait_keywords → wait_source_path 분기
- CASE 2: 존재하지 않는 경로 입력 → 재질문
- CASE 3: 날짜 탭 없는 xlsx → 재질문
- CASE 4: 유효한 경로 → tab_selector emit + wait_ref_tabs 전환
"""

import sys
import queue
import shutil
import tempfile
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import openpyxl
from server import _event_planner_agent

# ─────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────

def drain(q: queue.Queue) -> list:
    """큐에 쌓인 이벤트를 리스트로 반환."""
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    return events

def make_context(source_path: str = "", step: str = "wait_keywords") -> dict:
    return {
        "genre": "야구",
        "market": "일본",
        "new_tabs": ["260709"],
        "source_path": source_path,
        "keywords": [],
        "_agent_step": step,
        "_suggested_keywords": ["야구대회", "홈런레이스", "타격왕경쟁"],
    }

def make_xlsx(tab_names: list) -> str:
    """임시 xlsx 생성 후 경로 반환."""
    tmp = tempfile.mktemp(suffix=".xlsx")
    wb = openpyxl.Workbook()
    wb.active.title = tab_names[0] if tab_names else "Sheet1"
    for name in tab_names[1:]:
        wb.create_sheet(name)
    wb.save(tmp)
    return tmp

VALID_SOURCE = str(ROOT / "output" / "gdrive_cache" /
                   "sheets_16K4odWS3WamR36s3lakcUhsWZxlZxjr9mPeX9Xk0RRw.xlsx")

# ─────────────────────────────────────────────
# CASE 1: available_tabs 없을 때 wait_source_path로 분기
# ─────────────────────────────────────────────
def test_case1_no_available_tabs_asks_source():
    print("\n[CASE 1] available_tabs 없음 → 소스 경로 질문")
    q = queue.Queue()
    ctx = make_context(source_path="")  # 소스 없음 → available_tabs = []
    _event_planner_agent("모두 사용", [], ctx, q)
    events = drain(q)

    types = [e["type"] for e in events]
    assert "message" in types, "message 이벤트 없음"
    msg_ev = next(e for e in events if e["type"] == "message")
    assert "소스 파일 경로" in msg_ev["content"], f"경로 질문 없음: {msg_ev['content']}"
    assert ctx["_agent_step"] == "wait_source_path", f"step 불일치: {ctx['_agent_step']}"
    # tab_selector가 emit되면 안 된다
    assert "tab_selector" not in types, "tab_selector가 조기 emit됨"
    print("  ✅ PASS — wait_source_path로 전환, 소스 경로 질문 확인")


# ─────────────────────────────────────────────
# CASE 2: 존재하지 않는 경로 입력 → 재질문
# ─────────────────────────────────────────────
def test_case2_invalid_path():
    print("\n[CASE 2] 존재하지 않는 경로 입력 → 재질문")
    q = queue.Queue()
    ctx = make_context(step="wait_source_path")
    _event_planner_agent(r"C:\존재하지않는\파일.xlsx", [], ctx, q)
    events = drain(q)

    types = [e["type"] for e in events]
    assert "message" in types
    msg_ev = next(e for e in events if e["type"] == "message")
    assert "찾을 수 없습니다" in msg_ev["content"], f"오류 메시지 없음: {msg_ev['content']}"
    assert ctx["_agent_step"] == "wait_source_path", "step이 바뀌면 안 됨"
    assert "tab_selector" not in types, "tab_selector가 emit되면 안 됨"
    print("  ✅ PASS — 파일 없음 오류 메시지 + wait_source_path 유지")


# ─────────────────────────────────────────────
# CASE 3: 날짜 탭 없는 xlsx → 재질문
# ─────────────────────────────────────────────
def test_case3_xlsx_no_date_tabs():
    print("\n[CASE 3] 날짜 탭 없는 xlsx → 재질문")
    tmp_path = make_xlsx(["Sheet1", "이벤트정보", "보상"])
    try:
        q = queue.Queue()
        ctx = make_context(step="wait_source_path")
        _event_planner_agent(tmp_path, [], ctx, q)
        events = drain(q)

        types = [e["type"] for e in events]
        assert "message" in types
        msg_ev = next(e for e in events if e["type"] == "message")
        assert "찾을 수 없습니다" in msg_ev["content"], f"오류 메시지 없음: {msg_ev['content']}"
        assert ctx["_agent_step"] == "wait_source_path", "step이 바뀌면 안 됨"
        assert "tab_selector" not in types
        print("  ✅ PASS — 날짜 탭 없음 오류 메시지 + wait_source_path 유지")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ─────────────────────────────────────────────
# CASE 4: 유효한 경로 → tab_selector emit + wait_ref_tabs 전환
# ─────────────────────────────────────────────
def test_case4_valid_path_shows_tab_selector():
    print("\n[CASE 4] 유효한 경로 입력 → tab_selector emit + wait_ref_tabs 전환")
    tmp_path = make_xlsx(["260611", "260625", "260702", "메모"])
    try:
        q = queue.Queue()
        ctx = make_context(step="wait_source_path")
        _event_planner_agent(tmp_path, [], ctx, q)
        events = drain(q)

        types = [e["type"] for e in events]
        assert "tab_selector" in types, f"tab_selector 없음, events: {types}"

        sel_ev = next(e for e in events if e["type"] == "tab_selector")
        assert "260611" in sel_ev["available_tabs"], f"탭 목록 이상: {sel_ev['available_tabs']}"
        assert ctx["_agent_step"] == "wait_ref_tabs", f"step 불일치: {ctx['_agent_step']}"
        assert ctx["source_path"] == tmp_path, "source_path 미갱신"

        msg_ev = next(e for e in events if e["type"] == "message")
        assert "소스 파일을 확인했습니다" in msg_ev["content"]
        print(f"  ✅ PASS — available_tabs: {sel_ev['available_tabs']}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ─────────────────────────────────────────────
# CASE 5: 실제 gdrive_cache 소스로 검증 (파일 있을 때만)
# ─────────────────────────────────────────────
def test_case5_real_source_file():
    print("\n[CASE 5] 실제 소스 파일로 검증")
    if not Path(VALID_SOURCE).exists():
        print("  ⏭ SKIP — 소스 파일 없음")
        return

    q = queue.Queue()
    ctx = make_context(step="wait_source_path")
    _event_planner_agent(VALID_SOURCE, [], ctx, q)
    events = drain(q)

    types = [e["type"] for e in events]
    assert "tab_selector" in types, f"tab_selector 없음, events: {types}"
    sel_ev = next(e for e in events if e["type"] == "tab_selector")
    assert len(sel_ev["available_tabs"]) > 0
    assert ctx["_agent_step"] == "wait_ref_tabs"
    print(f"  ✅ PASS — 탭 {len(sel_ev['available_tabs'])}개 확인: {sel_ev['available_tabs'][:3]}...")


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_case1_no_available_tabs_asks_source,
        test_case2_invalid_path,
        test_case3_xlsx_no_date_tabs,
        test_case4_valid_path_shows_tab_selector,
        test_case5_real_source_file,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAIL — {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ ERROR — {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"결과: {passed}개 통과 / {failed}개 실패 (총 {len(tests)}개)")
    sys.exit(0 if failed == 0 else 1)
