#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
에이전트 학습 저장 스크립트

각 실행 결과를 output/agent_learning.json 에 누적 저장.
다음 실행 시 에이전트가 이 파일을 읽어 장르 키워드·보상 수량·이벤트 명칭 패턴을 재활용한다.

입력 (output/ 디렉터리 내):
  - event_names_config.json  : 장르·키워드·명칭 치환 규칙
  - last_run_result.json     : 실행 결과 (탭·변경 내역)
  - reward_scan_result.json  : 보상 수량 스캔 결과
  - reward_by_event.json     : 이벤트 섹션별 보상 패턴 (있으면 반영)

출력:
  - output/agent_learning.json : 누적 학습 데이터
"""
import io
import json
import sys
from datetime import date, datetime
from pathlib import Path

OUTPUT_DIR = Path("output")
OUTPUT_JSON_DIR = OUTPUT_DIR / "json"
LEGACY_LEARNING_FILE = OUTPUT_JSON_DIR / "agent_learning.json"  # 하위 호환용

# ─── 현재 프로젝트 설정 로드 ──────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_CURRENT_PROJECT_FILE = _BASE_DIR / "output" / "json" / "current_project.json"

def _resolve_learning_path(project_id: str) -> Path:
    """프로젝트별 학습 파일 경로 반환. 새 구조(output/projects/) 우선."""
    if project_id:
        # 새 구조 우선
        new_dir = _BASE_DIR / "output" / "projects" / project_id / "learning"
        new_dir.mkdir(parents=True, exist_ok=True)
        return new_dir / "agent_learning.json"
    return LEGACY_LEARNING_FILE


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def extract_reward_qty_summary(reward_scan: dict) -> dict:
    """reward_scan_result.json summary_by_type → 보상명별 수량 요약."""
    summary: dict[str, dict] = {}
    for rtype, info in reward_scan.get("summary_by_type", {}).items():
        qty_range = info.get("quantity_range")
        for name in info.get("unique_names", []):
            summary[name] = {
                "type": rtype,
                "avg_quantity": qty_range["avg"] if qty_range else None,
                "min_quantity": qty_range["min"] if qty_range else None,
                "max_quantity": qty_range["max"] if qty_range else None,
                "unit": "",
                "has_quantity": qty_range is not None,
                "note": info.get("note", ""),
            }
    return summary


def update_accumulated(acc: dict, run: dict) -> dict:
    """누적 학습 데이터에 이번 실행 결과 병합."""

    # ── 장르 키워드 누적 ─────────────────────────────────────────────
    genre = run.get("genre", "")
    phrases = run.get("genre_phrases", [])
    if genre and phrases:
        existing = acc.setdefault("genre_keywords", {}).setdefault(genre, [])
        merged = list(dict.fromkeys(existing + phrases))  # 순서 유지 중복 제거
        acc["genre_keywords"][genre] = merged

    # ── 이벤트 명칭 패턴 누적 ────────────────────────────────────────
    for tab, repls in run.get("event_name_replacements", {}).items():
        bucket = acc.setdefault("event_name_patterns", {}).setdefault(tab, [])
        for pair in repls:
            if pair not in bucket:
                bucket.append(pair)

    # ── 보상 수량 패턴 누적 ──────────────────────────────────────────
    for name, info in run.get("reward_qty_summary", {}).items():
        bucket = acc.setdefault("reward_patterns", {})
        if name not in bucket:
            bucket[name] = {
                "type": info["type"],
                "has_quantity": info["has_quantity"],
                "quantity_samples": [],
                "note": info["note"],
                "occurrences": 0,
            }
        bucket[name]["occurrences"] += 1
        avg = info.get("avg_quantity")
        if avg is not None:
            bucket[name]["quantity_samples"].append(avg)

    # ── 확정 보상 치환 패턴 누적 (명칭 → 신규명) ─────────────────────
    for tab, repls in run.get("reward_replacements_applied", {}).items():
        bucket = acc.setdefault("reward_replacement_patterns", {}).setdefault(tab, [])
        for pair in repls:
            if pair not in bucket:
                bucket.append(pair)

    # ── 이벤트 유형별 보상 구성 패턴 누적 ────────────────────────────
    for etype, info in run.get("event_reward_patterns", {}).items():
        bucket = acc.setdefault("event_reward_patterns", {})
        if etype not in bucket:
            bucket[etype] = {
                "seen_count": 0,
                "top_reward_names": [],
                "quantity_stats": {},
            }

        bucket[etype]["seen_count"] = max(
            bucket[etype]["seen_count"],
            info.get("seen_count", 0),
        )

        # top_reward_names 병합 (중복 제거·순서 유지)
        existing_names = bucket[etype]["top_reward_names"]
        for name in info.get("top_reward_names", []):
            if name not in existing_names:
                existing_names.append(name)
        bucket[etype]["top_reward_names"] = existing_names[:10]  # 최대 10개

        # 수량 통계: 기존 샘플 수가 더 많으면 덮어쓰기
        for rtype, stats in info.get("quantity_stats", {}).items():
            existing_stat = bucket[etype]["quantity_stats"].get(rtype)
            if not existing_stat or stats.get("samples", 0) > existing_stat.get("samples", 0):
                bucket[etype]["quantity_stats"][rtype] = stats

    # ── 이벤트 유형 빈도 패턴 누적 ──────────────────────────────────────
    # analyze_event_patterns.py 결과에서 이벤트 유형별 등장률·우선순위 병합.
    # 샘플 수(total_tabs)가 더 많은 쪽의 데이터로 갱신한다.
    for etype, info in run.get("event_frequency_patterns", {}).items():
        bucket = acc.setdefault("event_frequency_patterns", {})
        existing = bucket.get(etype)
        incoming_total = info.get("total_tabs", 0)
        if not existing or incoming_total > existing.get("total_tabs", 0):
            bucket[etype] = {
                "count":          info.get("count", 0),
                "total_tabs":     incoming_total,
                "rate":           info.get("rate", 0.0),
                "rate_pct":       info.get("rate_pct", "0%"),
                "priority":       info.get("priority", "rare"),
                "title_examples": info.get("title_examples", []),
                "updated_at":     run.get("run_date", ""),
            }

    return acc


def _append_schedule_to_learning(learning: dict, schedule_path: Path) -> dict:
    """
    schedule_patterns.json 결과를 누적 학습에 병합.
    이벤트 유형별 등장률·지속기간·순서 패턴을 업데이트한다.
    """
    if not schedule_path.exists():
        return learning

    sched = json.loads(schedule_path.read_text(encoding="utf-8"))
    bucket = learning.setdefault("schedule_patterns", {})

    # 탭 간격 (더 많은 탭 분석 결과 우선)
    new_total = sched.get("total_tabs_analyzed", 0)
    old_total = bucket.get("total_tabs_analyzed", 0)
    if new_total >= old_total:
        bucket["total_tabs_analyzed"]  = new_total
        bucket["tab_interval_days"]    = sched.get("tab_interval_days", 7)
        bucket["avg_events_per_tab"]   = sched.get("avg_events_per_tab", 0)
        bucket["anchor_events"]        = sched.get("anchor_events", [])
        bucket["avg_duration_by_type"] = sched.get("avg_duration_by_type", {})
        bucket["section_order_pattern"] = sched.get("section_order_pattern", {})
        bucket["cooccurrence_rules"]   = sched.get("cooccurrence_rules", {})
        bucket["updated_at"]           = sched.get("analyzed_at", "")

    # 월별 특이사항 병합 (기존 + 신규)
    month_existing = bucket.setdefault("month_specific", {})
    for month, info in sched.get("month_specific", {}).items():
        if month not in month_existing:
            month_existing[month] = info

    # 이벤트 유형 빈도 패턴 업데이트 (기존 update_accumulated 와 중복 방지)
    freq_bucket = learning.setdefault("event_frequency_patterns", {})
    for etype, info in sched.get("event_type_stats", {}).items():
        existing = freq_bucket.get(etype)
        if not existing or info.get("total_tabs", 0) > existing.get("total_tabs", 0):
            freq_bucket[etype] = {
                "count":          info.get("seen_tabs", 0),
                "total_tabs":     info.get("total_tabs", 0),
                "rate":           info.get("rate", 0.0),
                "rate_pct":       info.get("rate_pct", "0%"),
                "priority":       info.get("priority", "rare"),
                "title_examples": info.get("title_examples", []),
                "updated_at":     sched.get("analyzed_at", ""),
            }

    return learning


def _append_names_to_learning(learning: dict, names_path: Path) -> dict:
    """
    confirmed_events.json 또는 historical_event_names.json 에서
    확정된 이벤트 제목 패턴을 누적 학습에 추가한다.
    """
    if not names_path.exists():
        return learning

    data = json.loads(names_path.read_text(encoding="utf-8"))
    bucket = learning.setdefault("event_name_patterns_learned", {})

    # confirmed_events.json 형식: { "events": [{"title": ..., "event_type": ...}] }
    events = data.get("events", [])
    if events:
        for ev in events:
            etype = ev.get("event_type", "기타")
            title = ev.get("title", "")
            candidates = ev.get("title_candidates", [])
            if title:
                bucket.setdefault(etype, [])
                entry = {"title": title, "candidates": candidates}
                if entry not in bucket[etype]:
                    bucket[etype].append(entry)
        return learning

    # historical_event_names.json 형식: { "tabs": [...], "season_keywords_by_month": {...} }
    tabs = data.get("tabs", [])
    for tab in tabs:
        for sec in tab.get("event_sections", []):
            # 섹션 제목을 장르 없는 일반 패턴으로 저장
            title = sec.get("title", "")
            if title:
                bucket.setdefault("all", [])
                if title not in bucket["all"]:
                    bucket["all"].append(title)

    # 시즌 키워드도 병합
    kw_bucket = learning.setdefault("season_keywords_by_month", {})
    for month, kws in data.get("season_keywords_by_month", {}).items():
        existing = set(kw_bucket.get(month, []))
        existing.update(kws)
        kw_bucket[month] = sorted(existing)

    return learning


def _append_rewards_to_learning(learning: dict, rewards_path: Path) -> dict:
    """
    reward_new_tabs.json (신규 탭 보상 스캔 결과)에서
    이번 탭의 실제 확정 보상 패턴을 누적 학습에 추가한다.
    """
    if not rewards_path.exists():
        return learning

    data = json.loads(rewards_path.read_text(encoding="utf-8"))
    patterns = data.get("event_type_patterns", {})
    if not patterns:
        # per_tab_sections 형식이면 build_event_type_patterns 로직을 재적용
        per_tab = data.get("per_tab_sections", {})
        if not per_tab:
            return learning
        # 간단한 집계 (reward_type 빈도만)
        for tab, sections in per_tab.items():
            for sec in sections:
                etype = sec.get("event_type", "기타")
                bucket = learning.setdefault("event_reward_patterns", {})
                bucket.setdefault(etype, {"seen_count": 0, "top_reward_names": [], "quantity_stats": {}})
                bucket[etype]["seen_count"] += 1
        return learning

    # event_type_patterns 형식
    bucket = learning.setdefault("event_reward_patterns", {})
    for etype, info in patterns.items():
        if etype not in bucket:
            bucket[etype] = {
                "seen_count":      0,
                "top_reward_names": [],
                "quantity_stats":  {},
            }
        bucket[etype]["seen_count"] = max(
            bucket[etype]["seen_count"],
            info.get("seen_count", 0),
        )
        existing_names = bucket[etype]["top_reward_names"]
        for name in info.get("top_reward_names", []):
            if name not in existing_names:
                existing_names.append(name)
        bucket[etype]["top_reward_names"] = existing_names[:10]

        for rtype, stats in info.get("quantity_stats", {}).items():
            existing_stat = bucket[etype]["quantity_stats"].get(rtype)
            if not existing_stat or stats.get("samples", 0) > existing_stat.get("samples", 0):
                bucket[etype]["quantity_stats"][rtype] = stats

    return learning


def main():
    # ── 프로젝트 경로 결정 ────────────────────────────────────────────────────
    import sys as _sys_sl
    _sys_sl.path.insert(0, str(Path(__file__).resolve().parent))
    from _project_config import load_project_paths as _lpp
    _proj_paths = _lpp()

    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_JSON_DIR.mkdir(exist_ok=True)

    if _proj_paths:
        _proj_paths.ensure_dirs()
        json_dir = _proj_paths.work_dir      # 세션 작업 파일 위치
    else:
        json_dir = OUTPUT_JSON_DIR

    cfg = load_json(json_dir / "event_names_config.json")
    last_run = load_json(json_dir / "last_run_result.json")
    reward_scan = load_json(json_dir / "reward_scan_result.json")
    reward_by_event = load_json(json_dir / "reward_by_event.json")
    event_pattern_analysis = load_json(json_dir / "event_pattern_analysis.json")

    reward_qty_summary = extract_reward_qty_summary(reward_scan)
    event_reward_patterns = reward_by_event.get("event_type_patterns", {})
    # analyze_event_patterns.py 결과에서 이벤트 유형 빈도 통계 추출
    event_frequency_patterns = event_pattern_analysis.get("event_type_frequency", {})

    # 보상 치환 규칙에서 "보상 명칭 치환" 항목 분리
    # event_name_replacements 중 팩·다이아·골드 등 보상 키워드 포함 항목을 보상 치환으로 분류
    REWARD_KEYS = ["팩", "다이아", "골드", "박스", "코인", "쿠폰", "뽑기"]
    reward_repls: dict[str, list] = {}
    event_repls: dict[str, list] = {}
    for tab, repls in cfg.get("event_name_replacements", {}).items():
        r_list, e_list = [], []
        for pair in repls:
            old_name = pair[0] if pair else ""
            if any(k in old_name for k in REWARD_KEYS):
                r_list.append(pair)
            else:
                e_list.append(pair)
        if r_list:
            reward_repls[tab] = r_list
        if e_list:
            event_repls[tab] = e_list

    run_entry = {
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "run_date": date.today().isoformat(),
        "genre": cfg.get("genre", ""),
        "target_month": cfg.get("target_month", ""),
        "genre_phrases": cfg.get("genre_phrases", []),
        "tabs_created": last_run.get("tabs", []),
        "event_name_replacements": event_repls,
        "reward_replacements_applied": reward_repls,
        "reward_qty_summary": reward_qty_summary,
        "event_reward_patterns": event_reward_patterns,
        "event_frequency_patterns": event_frequency_patterns,
        "changes_count": {tab: len(chgs) for tab, chgs in last_run.get("changes", {}).items()},
    }

    # ── 저장 경로 결정 (프로젝트별 우선, 레거시 폴백) ─────────────────────────
    if _proj_paths:
        project_id = _proj_paths.project_id
        LEARNING_FILE = _proj_paths.agent_learning
        LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)
    else:
        project_id = ""
        if _CURRENT_PROJECT_FILE.exists():
            try:
                _cp = json.loads(_CURRENT_PROJECT_FILE.read_text(encoding="utf-8"))
                project_id = _cp.get("project_id", "")
            except Exception:
                pass
        LEARNING_FILE = _resolve_learning_path(project_id)

    # 누적 파일 로드
    if LEARNING_FILE.exists():
        with open(LEARNING_FILE, encoding="utf-8") as f:
            learning = json.load(f)
    else:
        learning = {
            "version": 1,
            "runs": [],
            "accumulated_learnings": {
                "genre_keywords": {},
                "event_name_patterns": {},
                "reward_patterns": {},
                "reward_replacement_patterns": {},
                "event_reward_patterns": {},
                "event_frequency_patterns": {},
            },
        }

    # 크롤링으로 생성된 파일에는 'runs' 키가 없을 수 있으므로 초기화
    if "runs" not in learning:
        learning["runs"] = []
    learning["runs"].append(run_entry)
    learning["last_updated"] = datetime.now().isoformat(timespec="seconds")
    learning["accumulated_learnings"] = update_accumulated(
        learning.get("accumulated_learnings", {}), run_entry
    )

    with open(LEARNING_FILE, "w", encoding="utf-8") as f:
        json.dump(learning, f, ensure_ascii=False, indent=2)

    # ── 레거시 파일에도 동일 내용 동기화 (하위 호환) ────────────────────────
    if project_id and LEARNING_FILE != LEGACY_LEARNING_FILE:
        with open(LEGACY_LEARNING_FILE, "w", encoding="utf-8") as f:
            json.dump(learning, f, ensure_ascii=False, indent=2)

    total_runs = len(learning["runs"])
    acc = learning["accumulated_learnings"]
    genre_count = sum(len(v) for v in acc.get("genre_keywords", {}).values())
    reward_count = len(acc.get("reward_patterns", {}))
    event_reward_count = len(acc.get("event_reward_patterns", {}))
    event_freq_count = len(acc.get("event_frequency_patterns", {}))

    if _proj_paths:
        dest_display = str(LEARNING_FILE)
    else:
        dest_str = f"projects/{project_id}/" if project_id else ""
        dest_display = f"output/json/{dest_str}agent_learning.json"
    print(f"학습 저장 완료: {dest_display}")
    if project_id:
        print(f"  프로젝트: {project_id}")
    print(f"  누적 실행: {total_runs}회")
    print(f"  장르 키워드 누적:        {genre_count}개")
    print(f"  보상 패턴 누적:          {reward_count}종")
    print(f"  이벤트 유형 보상 패턴:   {event_reward_count}종")
    print(f"  이벤트 유형 빈도 패턴:   {event_freq_count}종")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    import argparse as _ap_sl
    _parser_sl = _ap_sl.ArgumentParser(description="에이전트 학습 저장")
    _parser_sl.add_argument(
        "--append-names", metavar="PATH",
        help="이벤트 제목 패턴 누적 저장. "
             "confirmed_events.json 또는 historical_event_names.json 경로.",
    )
    _parser_sl.add_argument(
        "--append-rewards", metavar="PATH",
        help="보상 패턴 누적 저장. "
             "reward_new_tabs.json 경로.",
    )
    _parser_sl.add_argument(
        "--append-schedule", metavar="PATH",
        help="일정 패턴 누적 저장. "
             "schedule_patterns.json 경로.",
    )
    _sl_args = _parser_sl.parse_args()

    main()

    # ── --append-* 플래그 처리 (main() 내 학습 파일 저장 후 추가 병합) ──────
    if any([_sl_args.append_names, _sl_args.append_rewards, _sl_args.append_schedule]):
        import sys as _sys_ap
        _sys_ap.path.insert(0, str(Path(__file__).resolve().parent))
        from _project_config import load_project_paths as _lpp_ap
        _proj_ap = _lpp_ap()

        if _proj_ap:
            _learn_path = _proj_ap.agent_learning
        else:
            _learn_path = Path("output") / "json" / "agent_learning.json"

        if _learn_path.exists():
            _learning = json.loads(_learn_path.read_text(encoding="utf-8"))
        else:
            _learning = {"version": 1, "runs": [], "accumulated_learnings": {}}

        _changed = False
        _acc = _learning.setdefault("accumulated_learnings", {})

        if _sl_args.append_names:
            _acc = _append_names_to_learning(_acc, Path(_sl_args.append_names))
            print(f"[append-names] 병합 완료: {_sl_args.append_names}")
            _changed = True

        if _sl_args.append_rewards:
            _acc = _append_rewards_to_learning(_acc, Path(_sl_args.append_rewards))
            print(f"[append-rewards] 병합 완료: {_sl_args.append_rewards}")
            _changed = True

        if _sl_args.append_schedule:
            _acc = _append_schedule_to_learning(_acc, Path(_sl_args.append_schedule))
            print(f"[append-schedule] 병합 완료: {_sl_args.append_schedule}")
            _changed = True

        if _changed:
            _learning["accumulated_learnings"] = _acc
            _learning["last_updated"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
            _learn_path.write_text(
                json.dumps(_learning, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"누적 학습 저장: {_learn_path}")
