#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
프로젝트별 경로 설정 유틸리티

모든 스크립트가 이 모듈을 import해서 경로를 얻는다.
current_project.json 에서 활성 프로젝트를 읽어 경로를 반환한다.
"""
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
CURRENT_PROJECT_FILE  = BASE_DIR / "output" / "json" / "current_project.json"
PROJECT_REGISTRY_FILE = BASE_DIR / "output" / "json" / "project_registry.json"


class ProjectPaths:
    """프로젝트별 경로 모음."""

    def __init__(self, project_id: str, source_xlsx: str = "", title: str = ""):
        self.project_id  = project_id
        self.source_xlsx = Path(source_xlsx) if source_xlsx else None
        self.title       = title

        base = BASE_DIR / "output" / "projects" / project_id
        self.project_dir  = base
        self.learning_dir = base / "learning"   # 크롤링 + save_learning 결과 (세션 간 유지)
        self.work_dir     = base / "work"        # 세션별 임시 파일
        self.file_dir     = base / "file"        # 최종 xlsx 출력

        # ── Learning (크롤링 → 세션 간 유지) ────────────────────────────
        self.agent_learning         = self.learning_dir / "agent_learning.json"
        self.hist_event_names_learn = self.learning_dir / "historical_event_names.json"
        self.reward_by_event_learn  = self.learning_dir / "reward_by_event.json"
        self.event_pattern_learn    = self.learning_dir / "event_pattern_analysis.json"

        # ── Work (매 세션 재생성) ─────────────────────────────────────────
        self.event_names_config     = self.work_dir / "event_names_config.json"
        self.last_run_result        = self.work_dir / "last_run_result.json"
        self.reward_by_event        = self.work_dir / "reward_by_event.json"
        self.reward_new_tabs        = self.work_dir / "reward_new_tabs.json"
        self.event_pattern_analysis = self.work_dir / "event_pattern_analysis.json"
        self.hist_event_names       = self.work_dir / "historical_event_names.json"
        self.draft_events           = self.work_dir / "draft_events.json"
        self.confirmed_events       = self.work_dir / "confirmed_events.json"
        self.reward_scan_result     = self.work_dir / "reward_scan_result.json"
        self.last_gsheets_upload    = self.work_dir / "last_gsheets_upload.json"

    def ensure_dirs(self) -> None:
        """필요한 디렉터리를 모두 생성한다."""
        for d in [self.learning_dir, self.work_dir, self.file_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return f"ProjectPaths(project_id={self.project_id!r}, file_dir={self.file_dir})"


def load_project_paths(project_id: str | None = None) -> "ProjectPaths | None":
    """
    current_project.json 에서 ProjectPaths 반환.
    project_id 가 명시되면 그 ID 사용 (current_project.json 무시).
    """
    if project_id:
        # project_id 직접 지정 → source_xlsx 는 learning/agent_learning.json 에서 추출 시도
        learn_file = BASE_DIR / "output" / "projects" / project_id / "learning" / "agent_learning.json"
        source = ""
        title  = ""
        if learn_file.exists():
            try:
                d = json.loads(learn_file.read_text(encoding="utf-8"))
                source = d.get("source_xlsx", "")
                title  = d.get("spreadsheet_title", "")
            except Exception:
                pass
        return ProjectPaths(project_id=project_id, source_xlsx=source, title=title)

    if not CURRENT_PROJECT_FILE.exists():
        return None
    try:
        cfg = json.loads(CURRENT_PROJECT_FILE.read_text(encoding="utf-8"))
        pid = cfg.get("project_id", "")
        if not pid:
            return None
        return ProjectPaths(
            project_id  = pid,
            source_xlsx = cfg.get("source_xlsx", ""),
            title       = cfg.get("title", ""),
        )
    except Exception:
        return None


def save_current_project(project_id: str, source_xlsx: str = "", title: str = "") -> "ProjectPaths":
    """current_project.json 에 활성 프로젝트 저장 후 ProjectPaths 반환."""
    CURRENT_PROJECT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURRENT_PROJECT_FILE.write_text(
        json.dumps({
            "project_id":  project_id,
            "source_xlsx": str(source_xlsx),
            "title":       title,
            "updated_at":  datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths = ProjectPaths(project_id=project_id, source_xlsx=str(source_xlsx), title=title)
    paths.ensure_dirs()
    return paths


def _load_registry() -> list[dict]:
    """project_registry.json 에서 등록된 프로젝트 목록 반환."""
    if not PROJECT_REGISTRY_FILE.exists():
        return []
    try:
        data = json.loads(PROJECT_REGISTRY_FILE.read_text(encoding="utf-8"))
        return data.get("projects", [])
    except Exception:
        return []


def register_project(project_id: str, description: str = "", source_url: str = "") -> None:
    """
    project_registry.json 에 프로젝트 추가.
    이미 등록된 project_id 는 무시 (중복 없음).
    """
    registry = {"projects": _load_registry()}
    existing_ids = {p["project_id"] for p in registry["projects"]}
    if project_id not in existing_ids:
        registry["projects"].append({
            "project_id":    project_id,
            "description":   description,
            "source_url":    source_url,
            "registered_at": datetime.now().strftime("%Y-%m-%d"),
        })
        PROJECT_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROJECT_REGISTRY_FILE.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 폴더 구조도 함께 생성
        ProjectPaths(project_id=project_id).ensure_dirs()


def update_project_source_url(project_id: str, source_url: str) -> None:
    """
    project_registry.json 에 등록된 프로젝트의 source_url 갱신.
    크롤링 완료 후 URL을 레지스트리에 저장할 때 사용한다.
    """
    registry_data = {"projects": _load_registry()}
    updated = False
    for p in registry_data["projects"]:
        if p["project_id"] == project_id:
            p["source_url"] = source_url
            updated = True
            break
    if updated:
        PROJECT_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROJECT_REGISTRY_FILE.write_text(
            json.dumps(registry_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def list_projects() -> list[dict]:
    """
    등록된 전체 프로젝트 목록 반환.
    - project_registry.json 에 등록된 모든 프로젝트 포함 (크롤링 전도 표시)
    - 크롤링 완료된 프로젝트는 학습 데이터 통계 포함
    - 크롤링 전 프로젝트는 crawled=False, 통계 없음
    """
    results: dict[str, dict] = {}

    # ── Step 1: 레지스트리 기반 전체 프로젝트 (크롤링 전도 포함) ────────────
    for reg in _load_registry():
        pid = reg.get("project_id", "")
        if not pid:
            continue
        results[pid] = {
            "project_id":   pid,
            "title":        reg.get("description", pid),
            "source_url":   reg.get("source_url", ""),  # 레지스트리에 저장된 URL 사용
            "last_crawled": None,
            "version":      0,
            "tab_count":    0,
            "event_types":  0,
            "reward_types": 0,
            "crawled":      False,
        }

    # ── Step 2: 크롤링 완료된 프로젝트 — 학습 데이터로 보강 ─────────────────
    def _scan_dir(projects_dir: Path, learning_subdir: bool) -> None:
        if not projects_dir.exists():
            return
        for d in sorted(projects_dir.iterdir()):
            if not d.is_dir():
                continue
            lf = (d / "learning" / "agent_learning.json") if learning_subdir \
                 else (d / "agent_learning.json")
            if not lf.exists():
                continue
            pid = d.name
            try:
                data = json.loads(lf.read_text(encoding="utf-8"))
                acc  = data.get("accumulated_learnings", {})
                # source_url: agent_learning.json 우선, 없으면 레지스트리 URL 사용
                _registry_url = results.get(pid, {}).get("source_url", "")
                entry = {
                    "project_id":   pid,
                    "title":        data.get("spreadsheet_title", results.get(pid, {}).get("title", pid)),
                    "source_url":   data.get("source_url", "") or _registry_url,
                    "last_crawled": data.get("last_crawled", "?"),
                    "version":      data.get("version", 1),
                    "tab_count":    len(acc.get("event_name_patterns", {})),
                    "event_types":  len(acc.get("event_frequency_patterns", {})),
                    "reward_types": len(acc.get("event_reward_patterns", {})),
                    "crawled":      True,
                }
                # 새 구조 우선 (이미 있으면 덮어쓰지 않음)
                if pid not in results or not results[pid].get("crawled"):
                    results[pid] = entry
            except (json.JSONDecodeError, KeyError):
                pass

    _scan_dir(BASE_DIR / "output" / "projects",          learning_subdir=True)
    _scan_dir(BASE_DIR / "output" / "json" / "projects", learning_subdir=False)

    # 레지스트리 순서대로 정렬, 레지스트리에 없는 항목은 뒤에 추가
    reg_order = [p["project_id"] for p in _load_registry()]
    ordered = [results[pid] for pid in reg_order if pid in results]
    extras  = [v for pid, v in results.items() if pid not in reg_order]
    return ordered + extras


# ─────────────────────────────────────────────────────────────────────────────
# Game Localizer 경로 설정
# ─────────────────────────────────────────────────────────────────────────────

class LocalizerPaths:
    """현지화 번역 에이전트 경로 모음."""

    def __init__(self, session_id: str | None = None):
        from datetime import datetime
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")

        base = BASE_DIR / "output" / "game-localizer"
        self.base_dir = base
        self.glossary_cache    = base / "glossary_cache.json"
        self.translate_request = base / "translate_request.json"
        self.translate_result  = base / "translate_result.json"
        self.session_buffer    = base / "session_buffer.json"
        self.export_dir        = base

    def ensure_dirs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def export_path(self, timestamp: str | None = None) -> Path:
        from datetime import datetime
        ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.base_dir / f"translation_export_{ts}.xlsx"


def get_localizer_paths(session_id: str | None = None) -> "LocalizerPaths":
    """LocalizerPaths 인스턴스 반환 후 디렉터리 생성."""
    lp = LocalizerPaths(session_id)
    lp.ensure_dirs()
    return lp
