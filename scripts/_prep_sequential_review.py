#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reward_recommendation.json 을 읽어 이벤트별 순차 리뷰용 요약 JSON 을 생성한다.
output: output/projects/FB_GL/work/reward_review_queue.json

옵션:
  --low-confidence-only   변경 권장 항목(LOW 신뢰도)이 있는 섹션만 큐에 포함.
                          HIGH 신뢰도(action=유지) 섹션은 자동 확정으로 처리해 생략.
                          검토 건수를 최소화해 대화 횟수를 줄인다.
"""
import sys, json, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from _project_config import load_project_paths
    _paths = load_project_paths()
    WORK = _paths.work_dir if _paths else BASE / "output" / "projects" / "event-planner" / "work"
except Exception:
    WORK = BASE / "output" / "projects" / "event-planner" / "work"

_parser = argparse.ArgumentParser(description="보상 순차 리뷰 큐 생성")
_parser.add_argument(
    "--low-confidence-only", action="store_true",
    help="변경 권장(LOW 신뢰도) 섹션만 큐에 포함. HIGH 신뢰도 섹션은 자동 확정 처리.",
)
_args = _parser.parse_args()

_LOW_ACTIONS = frozenset({"상향_권장", "하향_검토", "명칭_검토", "명칭_변경_권장", "수동_확인"})

rec_path = WORK / "reward_recommendation.json"
out_path  = WORK / "reward_review_queue.json"

data = json.loads(rec_path.read_text(encoding="utf-8"))

queue = []
auto_confirmed = []   # --low-confidence-only 시 자동 확정 섹션 기록
global_idx = 0

for tab_name, sections in data["tabs"].items():
    source_tab = data["source_map"].get(tab_name, "?")
    for sec in sections:
        global_idx += 1

        # 수량이 있는 보상만 (is_pack=False, qty_cell != null)
        qty_rewards = [r for r in sec["rewards"] if not r["is_pack"] and r["qty_cell"]]
        # 팩형 보상
        pack_rewards = [r for r in sec["rewards"] if r["is_pack"]]
        # 명칭 검토 필요 (명칭_검토 + 명칭_변경_권장 모두)
        name_review = [r for r in sec["rewards"]
                       if r["recommendation"]["action"] in ("명칭_검토", "명칭_변경_권장")]
        # 변경 권장 (상향/하향)
        change_recs  = [r for r in sec["rewards"]
                        if r["recommendation"]["action"] in ("상향_권장", "하향_검토")]

        # --low-confidence-only: 변경 권장 없는 섹션은 자동 확정 처리
        has_low = bool(change_recs or name_review)
        if _args.low_confidence_only and not has_low:
            auto_confirmed.append({
                "tab":          tab_name,
                "event_index":  sec["index"],
                "event_title":  sec["event_title"],
                "reward_count": len(sec["rewards"]),
            })
            continue

        # 수량 보상 요약 (현재 vs 추천)
        reward_summary = []
        for r in sec["rewards"]:
            entry = {
                "reward_name": r["reward_name"],
                "is_pack": r["is_pack"],
                "item_cell": r["item_cell"],
                "qty_cell": r["qty_cell"],
                "current_qty": r["current_qty"],
                "suggested_qty": r["recommendation"]["suggested_qty"],
                "suggested_name": r["recommendation"].get("suggested_name"),   # ← 아이템명 추천
                "action": r["recommendation"]["action"],
                "icon": r["recommendation"]["icon"],
                "reason": r["recommendation"]["reason"],
                "source_qty": r.get("source_qty"),
                "sim_avg": r["recommendation"]["sim_stats"]["avg"] if r["recommendation"].get("sim_stats") else None,
                "sim_samples": r["recommendation"]["sim_stats"]["samples"] if r["recommendation"].get("sim_stats") else None,
                "hist_avg": r.get("hist_avg"),
            }
            reward_summary.append(entry)

        queue.append({
            "global_idx": global_idx,
            "tab": tab_name,
            "source_tab": source_tab,
            "event_index": sec["index"],
            "event_title": sec["event_title"],
            "event_type": sec["event_type"],
            "similar_tabs": sec.get("similar_tabs", []),
            "title_cell": sec["title_cell"],
            "start_row": sec["start_row"],
            "end_row": sec["end_row"],
            "rewards": reward_summary,
            "has_change": len(change_recs) > 0 or len(name_review) > 0,
            "change_count": len(change_recs),
            "name_review_count": len(name_review),
            "approved": False,           # 리뷰 완료 여부
            "approved_changes": [],      # 승인된 변경 [(qty_cell, new_qty), ...]
        })

total = len(queue)
changes_pending = sum(1 for q in queue if q["has_change"])

result = {
    "total_sections":       total,
    "sections_with_changes": changes_pending,
    "reviewed":             0,
    "low_confidence_only":  _args.low_confidence_only,
    "auto_confirmed_count": len(auto_confirmed),
    "auto_confirmed":       auto_confirmed,
    "queue":                queue,
}

out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

if _args.low_confidence_only:
    print(f"[LOW 신뢰도 전용 모드]")
    print(f"  자동 확정 섹션: {len(auto_confirmed)}개  (검토 생략)")
    print(f"  검토 필요 섹션: {total}개")
else:
    print(f"총 섹션: {total}개  (변경권장: {changes_pending}개)")
print(f"저장: {out_path}")

# 큐 목록 출력
for q in queue:
    icon = "📝" if q["has_change"] else "✅"
    print(f"  [{q['tab']}] 섹션{q['event_index']}: {q['event_title'][:30]}  {icon}")
