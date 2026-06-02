#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
프로젝트 학습 데이터 로더

CLAUDE.md의 '세션 시작 시 학습 데이터 로드' 단계에서 사용.
크롤링된 프로젝트의 학습 데이터를 읽어 요약 출력하거나 전체 JSON을 반환한다.

사용:
  # 등록된 프로젝트 목록 확인
  python scripts/load_project_learning.py --list

  # 특정 프로젝트 요약 출력 (Claude 읽기용)
  python scripts/load_project_learning.py --project-id NC_KR --summary

  # 전체 JSON 출력 (파이프 처리용)
  python scripts/load_project_learning.py --project-id NC_KR

  # 레거시 단일 프로젝트 파일 로드 (기존 agent_learning.json)
  python scripts/load_project_learning.py --legacy

사전 조건:
  python scripts/crawl_gdrive_project.py <Google Sheets URL> 실행 필요
"""
import io
import json
import sys
import argparse
from pathlib import Path

BASE_DIR             = Path(__file__).resolve().parent.parent
_NEW_PROJECTS_DIR    = BASE_DIR / "output" / "projects"
_LEGACY_PROJECTS_DIR = BASE_DIR / "output" / "json" / "projects"
PROJECTS_DIR         = _NEW_PROJECTS_DIR if _NEW_PROJECTS_DIR.exists() else _LEGACY_PROJECTS_DIR
LEGACY_LEARNING      = BASE_DIR / "output" / "json" / "agent_learning.json"

# _project_config.list_projects() 위임 (레지스트리 + 크롤링 데이터 통합)
sys.path.insert(0, str(BASE_DIR / "scripts"))
try:
    from _project_config import list_projects as _list_projects_cfg
    def list_projects() -> list[dict]:
        return _list_projects_cfg()
except ImportError:
    # fallback: 직접 스캔 (레거시)
    def list_projects() -> list[dict]:  # type: ignore[misc]
        results: dict = {}
        def _scan(d: Path, sub: bool) -> None:
            if not d.exists(): return
            for p in sorted(d.iterdir()):
                if not p.is_dir(): continue
                lf = (p/"learning"/"agent_learning.json") if sub else (p/"agent_learning.json")
                if not lf.exists(): continue
                pid = p.name
                if pid in results: return
                try:
                    data = json.loads(lf.read_text(encoding="utf-8"))
                    acc  = data.get("accumulated_learnings", {})
                    results[pid] = {"project_id": pid, "title": data.get("spreadsheet_title","?"),
                        "source_url": data.get("source_url",""), "last_crawled": data.get("last_crawled","?"),
                        "version": data.get("version",1), "tab_count": len(acc.get("event_name_patterns",{})),
                        "event_types": len(acc.get("event_frequency_patterns",{})),
                        "reward_types": len(acc.get("event_reward_patterns",{})), "crawled": True}
                except Exception: pass
        _scan(_NEW_PROJECTS_DIR, True); _scan(_LEGACY_PROJECTS_DIR, False)
        return list(results.values())

# 등장률 시각화용 막대
def _rate_bar(rate: float, width: int = 4) -> str:
    filled = round(rate * width)
    return "█" * filled + "○" * (width - filled)


def load_project(project_id: str) -> dict:
    """특정 프로젝트의 agent_learning.json 로드."""
    # 새 구조 우선
    path = _NEW_PROJECTS_DIR / project_id / "learning" / "agent_learning.json"
    if not path.exists():
        # 레거시 구조 폴백
        path = _LEGACY_PROJECTS_DIR / project_id / "agent_learning.json"
    if not path.exists():
        raise FileNotFoundError(
            f"프로젝트 '{project_id}' 학습 데이터 없음\n"
            f"먼저 실행: python scripts/crawl_gdrive_project.py <Sheets URL> --project-id {project_id}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_legacy() -> dict:
    """기존 단일 프로젝트 agent_learning.json 로드 (backward compatibility)."""
    if not LEGACY_LEARNING.exists():
        raise FileNotFoundError(f"레거시 학습 파일 없음: {LEGACY_LEARNING}")
    return json.loads(LEGACY_LEARNING.read_text(encoding="utf-8"))


def print_summary(project_id: str, data: dict) -> None:
    """Claude가 읽기 좋은 요약 형식으로 학습 데이터 출력."""
    acc        = data.get("accumulated_learnings", {})
    freq       = acc.get("event_frequency_patterns", {})
    rewards    = acc.get("event_reward_patterns", {})
    tabs       = list(acc.get("event_name_patterns", {}).keys())
    tab_stats  = data.get("tab_count_stats", {})

    print(f"\n{'='*60}")
    print(f"[프로젝트 학습 데이터] — {project_id}")
    print(f"{'='*60}")
    print(f"  제목          : {data.get('spreadsheet_title', '?')}")
    print(f"  마지막 크롤링 : {data.get('last_crawled', '?')[:19]}")
    print(f"  분석 탭 수    : {len(tabs)}개")
    if tabs:
        preview = ", ".join(tabs[:6]) + ("..." if len(tabs) > 6 else "")
        print(f"  탭 목록       : {preview}")

    # 탭당 이벤트 수 통계
    if tab_stats:
        print(f"\n  [탭당 이벤트 수]")
        print(f"    평균 {tab_stats.get('avg', '?')}개  "
              f"(범위 {tab_stats.get('min', '?')}~{tab_stats.get('max', '?')}개)")

    # 이벤트 유형 빈도
    if freq:
        print(f"\n  [이벤트 유형 등장률]  ({len(freq)}종)")
        sorted_freq = sorted(freq.items(), key=lambda x: -x[1].get("rate", 0))
        print(f"    {'이벤트 유형':<24} | 막대 | {'등장률':>5} | 횟수     | 우선순위")
        print("    " + "─" * 60)
        icon_map = {"required": "❗", "recommended": "⚠", "optional": "〇", "rare": " "}
        for etype, info in sorted_freq:
            bar  = _rate_bar(info.get("rate", 0))
            icon = icon_map.get(info.get("priority", "rare"), " ")
            print(
                f"    {etype:<24} | {bar} | {info.get('rate_pct', '?'):>5} | "
                f"{info.get('count', 0):>3}/{info.get('total_tabs', 0):<3} | "
                f"{icon} {info.get('priority', '')}"
            )

    # 이벤트 유형별 보상 패턴
    if rewards:
        print(f"\n  [이벤트 유형별 주요 보상]  ({len(rewards)}종)")
        for etype, info in list(rewards.items())[:8]:
            seen = info.get("seen_count", "?")
            qty_str = ", ".join(
                f"{rt} 평균 {s['avg']}개 ({s['samples']}샘플)"
                for rt, s in info.get("quantity_stats", {}).items()
            )
            if not qty_str:
                top = ", ".join(info.get("top_reward_names", [])[:2])
                qty_str = f"수량 없음 (팩형) — {top}" if top else "수량 데이터 없음"
            print(f"    {etype:<24} | {seen}탭 | {qty_str}")

    # 장르 키워드
    genre_kw = acc.get("genre_keywords", {})
    if genre_kw:
        print(f"\n  [장르 키워드]")
        for genre, kws in genre_kw.items():
            print(f"    {genre}: {', '.join(kws[:10])}")

    # 새 구조 경로 우선, 없으면 레거시
    _lf_new = _NEW_PROJECTS_DIR / project_id / "learning" / "agent_learning.json"
    _lf_leg = _LEGACY_PROJECTS_DIR / project_id / "agent_learning.json"
    _lf_display = _lf_new if _lf_new.exists() else _lf_leg
    print(f"\n  학습 파일: {_lf_display}")
    print(f"{'='*60}\n")


def print_list(projects: list[dict]) -> None:
    """등록된 프로젝트 목록 출력 (크롤링 전 프로젝트 포함)."""
    if not projects:
        print("등록된 프로젝트 없음.")
        print("실행: python scripts/crawl_gdrive_project.py <Google Sheets URL>")
        return

    crawled   = [p for p in projects if p.get("crawled", True)]
    uncrawled = [p for p in projects if not p.get("crawled", True)]

    print(f"\n등록된 프로젝트 ({len(projects)}개 — 크롤링 완료 {len(crawled)}개 / 미크롤링 {len(uncrawled)}개):")
    print(f"  {'ID':<16} {'제목/설명':<30} {'상태':<20}  마지막 크롤링")
    print("  " + "─" * 78)
    for p in projects:
        if p.get("crawled", True):
            last = (p.get("last_crawled") or "")[:10]
            status = f"{p['tab_count']:>3}탭  {p['event_types']:>3}종  v{p['version']}"
        else:
            last   = "—"
            status = "⚠ 크롤링 필요"
        print(
            f"  {p['project_id']:<16} {p['title']:<30} {status:<20}  {last}"
        )
        # 저장된 Google Sheets URL이 있으면 표시 (재크롤링 참조용)
        src_url = p.get("source_url", "")
        if src_url:
            print(f"  {'':>16} └─ URL: {src_url}")

    if uncrawled:
        print(f"\n  ⚠ 크롤링 필요 프로젝트는 Google Sheets URL을 입력해 학습 데이터를 수집하세요:")
        print(f"    python scripts/crawl_gdrive_project.py \"<URL>\" --project-id <ID>")

    legacy_exists = LEGACY_LEARNING.exists()
    if legacy_exists:
        print(f"\n  ※ 레거시 파일도 존재: output/json/agent_learning.json")
        print(f"     로드: python scripts/load_project_learning.py --legacy --summary")
    print()


# ─── 메인 ────────────────────────────────────────────────────────────────────

def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="프로젝트 학습 데이터 로더")
    parser.add_argument("--project-id", help="로드할 project_id")
    parser.add_argument("--list",    action="store_true", help="등록된 프로젝트 목록")
    parser.add_argument("--summary", action="store_true", help="요약 형식 출력 (기본: 전체 JSON)")
    parser.add_argument("--legacy",  action="store_true", help="레거시 agent_learning.json 로드")
    args = parser.parse_args()

    if args.list:
        print_list(list_projects())
        return

    if args.legacy:
        data = load_legacy()
        if args.summary:
            print_summary("legacy", data)
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not args.project_id:
        projects = list_projects()
        if not projects:
            print("[안내] 등록된 프로젝트 없음.")
            print("실행: python scripts/crawl_gdrive_project.py <Google Sheets URL>")
        else:
            print_list(projects)
            print("사용법: python scripts/load_project_learning.py --project-id <ID> [--summary]")
        return

    data = load_project(args.project_id)
    if args.summary:
        print_summary(args.project_id, data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
