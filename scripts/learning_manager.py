#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
자기학습 관리자 — 에이전트 요청/결과를 학습하고 개선 인사이트를 누적한다.

사용:
  from learning_manager import LearningManager
  lm = LearningManager()
  lm.record_session(session_data)
  insights = lm.get_insights(genre="야구")
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

_BASE_DIR = Path(__file__).resolve().parent.parent
_LEARN_DIR = _BASE_DIR / "output" / "learnings"
_LEARN_DIR.mkdir(parents=True, exist_ok=True)

LEARNINGS_FILE  = _LEARN_DIR / "learnings.json"
INSIGHTS_FILE   = _LEARN_DIR / "insights.md"
IMPROVEMENT_LOG = _LEARN_DIR / "improvement_log.jsonl"


def _load_learnings() -> dict:
    if LEARNINGS_FILE.exists():
        try:
            return json.loads(LEARNINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "version": 1,
        "created": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "session_count": 0,
        "patterns": {
            "genre_keywords": {},
            "ref_tab_patterns": [],
            "successful_configs": [],
            "common_errors": [],
            "reward_baselines": {},
            "event_title_seasons": {},
            "pipeline_durations": []
        },
        "improvements": [],
        "sessions": []
    }


def _save_learnings(data: dict) -> None:
    data["last_updated"] = datetime.now().isoformat()
    LEARNINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


class LearningManager:
    """요청-결과 사이클에서 학습하고 인사이트를 누적하는 매니저."""

    def __init__(self):
        self.data = _load_learnings()

    # ─── 세션 기록 ────────────────────────────────────────────────────────
    def record_session(self, session: dict) -> None:
        """
        파이프라인 완료 후 세션 정보를 기록한다.

        session = {
          "agent": "event-planner" | "game-localizer",
          "genre": str,
          "market": str,
          "new_tabs": list,
          "ref_tabs": list,
          "keywords": list,
          "success": bool,
          "error_message": str | None,
          "duration_seconds": float,
          "reward_stats": dict,        # 선택: 보상 비교 요약
          "output_path": str,
          "user_feedback": str | None  # 사용자가 제공한 경우
        }
        """
        ts = datetime.now().isoformat()
        session["timestamp"] = ts
        self.data["sessions"].append(session)
        self.data["session_count"] += 1

        # 패턴 학습
        self._learn_keywords(session)
        self._learn_ref_tab_pattern(session)
        self._learn_errors(session)
        self._learn_reward_baseline(session)
        self._learn_pipeline_duration(session)

        if session.get("success"):
            self._record_successful_config(session)

        # 개선점 도출
        improvement = self._derive_improvement(session)
        if improvement:
            self.data["improvements"].append({
                "timestamp": ts,
                "source_session": len(self.data["sessions"]) - 1,
                "insight": improvement,
                "applied": False
            })

        _save_learnings(self.data)
        self._update_insights_md()
        self._append_improvement_log(session, improvement)

    # ─── 내부 학습 메서드 ─────────────────────────────────────────────────
    def _learn_keywords(self, session: dict) -> None:
        genre = session.get("genre", "")
        keywords = session.get("keywords", [])
        if not genre or not keywords:
            return
        existing = self.data["patterns"]["genre_keywords"].get(genre, [])
        merged = list(dict.fromkeys(existing + keywords))  # 순서 유지 dedup
        self.data["patterns"]["genre_keywords"][genre] = merged

    def _learn_ref_tab_pattern(self, session: dict) -> None:
        new_tabs = session.get("new_tabs", [])
        ref_tabs = session.get("ref_tabs", [])
        if len(new_tabs) == len(ref_tabs):
            for new, ref in zip(new_tabs, ref_tabs):
                try:
                    diff = int(new) - int(ref)
                    entry = {"new": new, "ref": ref, "diff_days": diff // 1}
                    if entry not in self.data["patterns"]["ref_tab_patterns"][-20:]:
                        self.data["patterns"]["ref_tab_patterns"].append(entry)
                except ValueError:
                    pass

    def _learn_errors(self, session: dict) -> None:
        if not session.get("success") and session.get("error_message"):
            err = session["error_message"]
            errors = self.data["patterns"]["common_errors"]
            # 유사 오류가 이미 있으면 카운트 증가
            for e in errors:
                if e["message"][:80] == err[:80]:
                    e["count"] = e.get("count", 1) + 1
                    e["last_seen"] = session["timestamp"]
                    return
            errors.append({"message": err[:200], "count": 1, "last_seen": session["timestamp"]})

    def _learn_reward_baseline(self, session: dict) -> None:
        stats = session.get("reward_stats", {})
        if not stats:
            return
        genre = session.get("genre", "unknown")
        if genre not in self.data["patterns"]["reward_baselines"]:
            self.data["patterns"]["reward_baselines"][genre] = []
        self.data["patterns"]["reward_baselines"][genre].append({
            "timestamp": session.get("timestamp"),
            "stats": stats
        })

    def _learn_pipeline_duration(self, session: dict) -> None:
        dur = session.get("duration_seconds")
        if dur and isinstance(dur, (int, float)):
            self.data["patterns"]["pipeline_durations"].append({
                "timestamp": session.get("timestamp"),
                "seconds": dur,
                "agent": session.get("agent", "unknown"),
                "success": session.get("success", False)
            })

    def _record_successful_config(self, session: dict) -> None:
        config = {
            "timestamp": session.get("timestamp"),
            "agent": session.get("agent"),
            "genre": session.get("genre"),
            "market": session.get("market"),
            "keywords_count": len(session.get("keywords", [])),
            "tabs_count": len(session.get("new_tabs", []))
        }
        self.data["patterns"]["successful_configs"].append(config)

    def _derive_improvement(self, session: dict) -> Optional[str]:
        """세션 데이터에서 개선 제안을 자동 도출."""
        suggestions = []

        # 오류 발생 시
        if not session.get("success"):
            err = session.get("error_message", "")
            if "ref_tabs" in err.lower() or "참조" in err:
                suggestions.append("참조 탭 자동 추천 로직 강화 필요")
            if "source" in err.lower() or "파일" in err:
                suggestions.append("소스 파일 경로 검증 단계 추가 필요")

        # 키워드 패턴 분석
        genre = session.get("genre", "")
        if genre:
            kw_history = self.data["patterns"]["genre_keywords"].get(genre, [])
            if len(kw_history) > 20:
                suggestions.append(f"장르 '{genre}' 키워드 풀이 {len(kw_history)}개로 충분히 누적됨 — 자동 추천 활성화 가능")

        # 실행 시간 패턴
        durations = [d["seconds"] for d in self.data["patterns"]["pipeline_durations"][-10:] if d.get("seconds")]
        if durations and len(durations) >= 3:
            avg = sum(durations) / len(durations)
            if avg > 120:
                suggestions.append(f"파이프라인 평균 실행시간 {avg:.0f}초 — 병렬 처리 최적화 검토")

        return "; ".join(suggestions) if suggestions else None

    # ─── 인사이트 조회 ────────────────────────────────────────────────────
    def get_insights(self, genre: str = "", agent: str = "event-planner") -> dict:
        """
        특정 장르/에이전트에 맞는 누적 인사이트 반환.
        server.py에서 에이전트 프롬프트에 주입할 때 사용.
        """
        result = {
            "session_count": self.data["session_count"],
            "suggested_keywords": [],
            "common_errors": self.data["patterns"]["common_errors"][-3:],
            "recent_improvements": [
                i["insight"] for i in self.data["improvements"][-5:] if not i.get("applied")
            ],
            "avg_pipeline_seconds": None,
        }

        if genre:
            result["suggested_keywords"] = self.data["patterns"]["genre_keywords"].get(genre, [])[:20]

        durations = [d["seconds"] for d in self.data["patterns"]["pipeline_durations"][-10:]
                     if d.get("success") and d.get("agent") == agent]
        if durations:
            result["avg_pipeline_seconds"] = round(sum(durations) / len(durations), 1)

        return result

    def get_keyword_suggestions(self, genre: str) -> list:
        """장르에 대한 누적 키워드 추천."""
        return self.data["patterns"]["genre_keywords"].get(genre, [])

    def get_successful_configs(self, genre: str = "") -> list:
        """성공한 설정 패턴 조회."""
        configs = self.data["patterns"]["successful_configs"]
        if genre:
            configs = [c for c in configs if c.get("genre") == genre]
        return configs[-5:]

    def mark_improvement_applied(self, index: int) -> None:
        """특정 개선 사항을 '적용됨'으로 마킹."""
        improvements = self.data.get("improvements", [])
        if 0 <= index < len(improvements):
            improvements[index]["applied"] = True
            _save_learnings(self.data)

    # ─── 마크다운 리포트 ──────────────────────────────────────────────────
    def _update_insights_md(self) -> None:
        lines = [
            "# 자기학습 인사이트 리포트",
            f"마지막 업데이트: {self.data['last_updated']}",
            f"총 세션 수: {self.data['session_count']}",
            "",
            "## 장르별 누적 키워드",
        ]
        for genre, kws in self.data["patterns"]["genre_keywords"].items():
            lines.append(f"### {genre} ({len(kws)}개)")
            lines.append(", ".join(kws[:30]))
            lines.append("")

        lines += ["## 최근 개선 제안"]
        for imp in self.data["improvements"][-10:]:
            status = "✅ 적용" if imp.get("applied") else "🔲 미적용"
            lines.append(f"- [{status}] {imp['timestamp'][:10]}: {imp['insight']}")

        lines += ["", "## 자주 발생하는 오류"]
        for err in self.data["patterns"]["common_errors"][-5:]:
            lines.append(f"- ({err.get('count', 1)}회) {err['message'][:100]}")

        lines += ["", "## 성공 설정 패턴"]
        for cfg in self.data["patterns"]["successful_configs"][-5:]:
            lines.append(f"- {cfg.get('timestamp','')[:10]} | {cfg.get('genre','')} | {cfg.get('market','')} | 키워드 {cfg.get('keywords_count',0)}개 | 탭 {cfg.get('tabs_count',0)}개")

        INSIGHTS_FILE.write_text("\n".join(lines), encoding="utf-8")

    def _append_improvement_log(self, session: dict, improvement: Optional[str]) -> None:
        entry = {
            "timestamp": session.get("timestamp"),
            "agent": session.get("agent"),
            "genre": session.get("genre"),
            "success": session.get("success"),
            "improvement": improvement
        }
        with open(IMPROVEMENT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
