#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
신규 탭 보상 vs 히스토리 비교 리포트

동작:
  1. reward_by_event.json  (소스 xlsx 히스토리 보상 패턴)
  2. reward_new_tabs.json  (신규 탭 보상)
  를 비교해서 이벤트 유형별 보상 변경/유지/이탈 항목을 분석한다.

출력:
  - reward_comparison.json (상세 비교 결과)
  콘솔에는 탭·이벤트별 요약 출력

사용:
  python scripts/compare_rewards.py
  python scripts/compare_rewards.py --source-scan path/to/reward_by_event.json \
                                    --new-scan   path/to/reward_new_tabs.json \
                                    --out        path/to/reward_comparison.json
"""
import argparse
import io
import json
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _project_config import load_project_paths

_paths = load_project_paths()


# ─── 유틸 ──────────────────────────────────────────────────────────────────

def _qty(reward_row: dict) -> int | None:
    """reward_row 에서 수량 정수값 추출."""
    q = reward_row.get("quantity_in_cell") or (
        reward_row["nearest_quantity"]["quantity"]
        if reward_row.get("nearest_quantity") else None
    )
    if q and isinstance(q.get("value"), (int, float)):
        return int(q["value"])
    return None


def _event_key(title: str) -> str:
    """제목에서 시즌 키워드를 제거한 정규화 키 (이벤트 유형 매칭용)."""
    import re
    # "N월의", "한여름의", "전반기의" 등 시즌 접두어 제거
    title = re.sub(r'\d+월\s*이달의\s*', '', title)
    title = re.sub(r'\d+월의?\s*', '', title)
    title = re.sub(
        r'(얼리썸머|초여름|한여름|늦여름|봄|여름|가을|겨울|전반기|후반기|포스트시즌|올스타|크리스마스|추석|설날)(의)?\s*',
        '', title
    )
    return title.strip()


def _reward_key(name: str) -> str:
    """보상 이름 정규화 — 세부 등급(A/S/B) 차이는 무시하고 유형만 비교."""
    import re
    name = re.sub(r'\s*\([^)]*\)', '', name)   # 괄호 제거
    name = re.sub(r'\s+', ' ', name).strip()
    return name


# ─── 비교 핵심 ─────────────────────────────────────────────────────────────

def compare_sections(hist_sections: list, new_sections: list) -> list:
    """
    히스토리 탭들의 섹션 목록과 신규 탭 섹션 목록을 비교.
    이벤트 유형(event_type)을 기준으로 매칭해서 보상 아이템별 변화를 분석한다.

    반환: [
      {
        event_title, event_type,
        rewards: [{name, qty_new, qty_hist_avg, qty_hist_range, status, diff_pct}, ...]
      }
    ]
    """
    # 히스토리: event_type → 최근 구성 (compositions[-1]) + 전체 qty_samples
    hist_by_type: dict[str, dict] = {}
    for sec in hist_sections:
        etype = sec["event_type"]
        if etype not in hist_by_type:
            hist_by_type[etype] = {"rows": [], "titles": []}
        hist_by_type[etype]["rows"].extend(sec.get("reward_rows", []))
        hist_by_type[etype]["titles"].append(sec.get("title", ""))

    # 히스토리 보상 집계: {event_type: {norm_name: [qty, ...]}}
    hist_qty_map: dict[str, dict[str, list]] = {}
    for etype, data in hist_by_type.items():
        qty_by_name: dict[str, list] = {}
        for rr in data["rows"]:
            key = _reward_key(rr.get("reward_name", ""))
            q = _qty(rr)
            if key and q is not None:
                qty_by_name.setdefault(key, []).append(q)
        hist_qty_map[etype] = qty_by_name

    results = []
    for sec in new_sections:
        etype = sec["event_type"]
        title = sec.get("title", "")
        hist_qty = hist_qty_map.get(etype, {})

        reward_report = []
        for rr in sec.get("reward_rows", []):
            name = rr.get("reward_name", "")
            key  = _reward_key(name)
            qty_new = _qty(rr)

            hist_vals = hist_qty.get(key, [])
            if hist_vals:
                hist_avg = round(sum(hist_vals) / len(hist_vals))
                hist_min = min(hist_vals)
                hist_max = max(hist_vals)
                if qty_new is not None:
                    diff_pct = round((qty_new - hist_avg) / hist_avg * 100) if hist_avg else 0
                    if abs(diff_pct) <= 5:
                        status = "유지"
                    elif diff_pct > 5:
                        status = "증가"
                    else:
                        status = "감소"
                else:
                    diff_pct = None
                    status = "수량미상"
            else:
                hist_avg = hist_min = hist_max = None
                diff_pct = None
                status = "신규"

            reward_report.append({
                "name":           name,
                "qty_new":        qty_new,
                "qty_hist_avg":   hist_avg,
                "qty_hist_range": [hist_min, hist_max] if hist_avg is not None else None,
                "status":         status,
                "diff_pct":       diff_pct,
            })

        # 히스토리에만 있고 신규 탭에 없는 보상 (제거된 보상)
        new_keys = {_reward_key(rr.get("reward_name", "")) for rr in sec.get("reward_rows", [])}
        for hist_name, hist_vals in hist_qty.items():
            if hist_name and hist_name not in new_keys:
                reward_report.append({
                    "name":           hist_name,
                    "qty_new":        None,
                    "qty_hist_avg":   round(sum(hist_vals) / len(hist_vals)),
                    "qty_hist_range": [min(hist_vals), max(hist_vals)],
                    "status":         "제거",
                    "diff_pct":       None,
                })

        results.append({
            "event_title": title,
            "event_type":  etype,
            "rewards":     reward_report,
        })

    return results


def _print_report(tab: str, sections: list) -> None:
    """콘솔 출력용 요약."""
    STATUS_ICON = {"유지": "✓", "증가": "↑", "감소": "↓", "신규": "★", "제거": "✗", "수량미상": "?"}
    print(f"\n  ▶ 탭: {tab}")
    for sec in sections:
        print(f"\n    [{sec['event_type']}] {sec['event_title']}")
        for r in sec["rewards"]:
            icon = STATUS_ICON.get(r["status"], "?")
            qty_str = str(r["qty_new"]) if r["qty_new"] is not None else "—"
            hist_str = f"  (히스토리 평균 {r['qty_hist_avg']})" if r["qty_hist_avg"] is not None else ""
            diff_str = f"  {r['diff_pct']:+d}%" if r.get("diff_pct") is not None else ""
            print(f"      {icon} {r['name']}  x {qty_str}{hist_str}{diff_str}")


# ─── 메인 ──────────────────────────────────────────────────────────────────

def main(source_scan_path: str, new_scan_path: str, out_path: str | None = None) -> dict:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    source_data = json.loads(Path(source_scan_path).read_text(encoding="utf-8"))
    new_data    = json.loads(Path(new_scan_path).read_text(encoding="utf-8"))

    # 히스토리 전체 섹션 (모든 탭 합산)
    hist_sections_all: list = []
    for tab, sections in source_data.get("per_tab_sections", {}).items():
        hist_sections_all.extend(sections)

    # 신규 탭별 비교
    comparison: dict[str, list] = {}
    for tab, sections in new_data.get("per_tab_sections", {}).items():
        result = compare_sections(hist_sections_all, sections)
        comparison[tab] = result
        _print_report(tab, result)

    # 요약 통계
    summary: dict[str, dict] = {}
    for tab, sections in comparison.items():
        counts = {"유지": 0, "증가": 0, "감소": 0, "신규": 0, "제거": 0, "수량미상": 0}
        for sec in sections:
            for r in sec["rewards"]:
                counts[r["status"]] = counts.get(r["status"], 0) + 1
        summary[tab] = counts

    output = {
        "source_scan": source_scan_path,
        "new_scan":    new_scan_path,
        "comparison":  comparison,
        "summary":     summary,
    }

    if out_path is None:
        out_path = str((_paths.work_dir if _paths else _BASE_DIR / "output" / "json") / "reward_comparison.json")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[저장] {out_path}")

    print("\n[탭별 요약]")
    STATUS_LABEL = {"유지": "유지", "증가": "↑증가", "감소": "↓감소", "신규": "★신규", "제거": "✗제거"}
    for tab, counts in summary.items():
        parts = [f"{STATUS_LABEL.get(k,k)} {v}개" for k, v in counts.items() if v > 0]
        print(f"  {tab}: {', '.join(parts)}")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="신규 탭 보상 vs 히스토리 비교")
    parser.add_argument("--source-scan", default=None)
    parser.add_argument("--new-scan",    default=None)
    parser.add_argument("--out",         default=None)
    args = parser.parse_args()

    work = _paths.work_dir if _paths else (_BASE_DIR / "output" / "projects" / "event-planner" / "work")
    src_scan = args.source_scan or str(work / "reward_by_event.json")
    new_scan = args.new_scan    or str(work / "reward_new_tabs.json")

    main(src_scan, new_scan, args.out)
