#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
멀티 에이전트 PM 오케스트레이터 — Streamlit 웹 앱

PM이 요청을 분류하고 적절한 에이전트로 라우팅한다.
  - event-planner : 모바일 게임 이벤트 기획안 자동 생성
  - game-localizer: 게임 텍스트 다국어 현지화 번역
"""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

# ── 기본 경로 ─────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
SCRIPTS_DIR = BASE_DIR / "scripts"
OUTPUT_DIR  = BASE_DIR / "output"
CURRENT_PROJECT_FILE = OUTPUT_DIR / "json" / "current_project.json"

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="멀티 에이전트 PM",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── 유틸 함수 ─────────────────────────────────────────────────────────────────

def run_script(cmd: list, label: str, cwd: str | None = None) -> tuple[bool, str, str]:
    """스크립트 실행 후 (성공여부, stdout, stderr) 반환."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        cwd=cwd or str(BASE_DIR),
    )
    return result.returncode == 0, result.stdout, result.stderr


def save_current_project(source_xlsx: str, project_id: str = "event-planner") -> Path:
    """
    current_project.json 저장.
    모든 스크립트가 이 파일에서 소스 경로와 project_id를 읽는다.
    """
    CURRENT_PROJECT_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "project_id":  project_id,
        "source_xlsx": source_xlsx,
        "title":       Path(source_xlsx).stem if source_xlsx else "",
        "updated_at":  datetime.now().isoformat(timespec="seconds"),
    }
    CURRENT_PROJECT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 프로젝트 디렉터리 구조도 생성
    proj_base = OUTPUT_DIR / "projects" / project_id
    for sub in ["learning", "work", "file"]:
        (proj_base / sub).mkdir(parents=True, exist_ok=True)
    return proj_base


def get_work_dir(project_id: str = "event-planner") -> Path:
    """프로젝트 작업 디렉터리 반환."""
    return OUTPUT_DIR / "projects" / project_id / "work"


def get_file_dir(project_id: str = "event-planner") -> Path:
    return OUTPUT_DIR / "projects" / project_id / "file"


def load_json_safe(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# ── 사이드바 — 에이전트 선택 ──────────────────────────────────────────────────
with st.sidebar:
    st.title("🤖 멀티 에이전트 PM")
    st.caption("요청을 분석하고 적합한 에이전트를 실행합니다.")
    st.divider()

    agent = st.radio(
        "에이전트 선택",
        options=["🏠 PM 홈", "📅 이벤트 기획 에이전트", "🌐 현지화 번역 에이전트"],
        index=0,
    )
    st.divider()
    st.caption("**등록된 에이전트**")
    st.markdown("- 📅 `event-planner`\n- 🌐 `game-localizer`")

    # 현재 프로젝트 표시
    cp = load_json_safe(CURRENT_PROJECT_FILE)
    if cp.get("project_id"):
        st.divider()
        st.caption("**현재 프로젝트**")
        st.markdown(f"`{cp['project_id']}`")
        if cp.get("source_xlsx"):
            st.caption(Path(cp["source_xlsx"]).name)


# ═══════════════════════════════════════════════════════════════════════════════
# PM 홈
# ═══════════════════════════════════════════════════════════════════════════════
if agent == "🏠 PM 홈":
    st.title("🤖 멀티 에이전트 PM 오케스트레이터")
    st.markdown("""
    **PM 에이전트**는 요청자의 요청을 분석하고 적합한 전문 에이전트를 실행합니다.

    | 에이전트 | 역할 | 트리거 키워드 |
    |---|---|---|
    | 📅 이벤트 기획 | 모바일 게임 이벤트 기획안 자동 생성 → xlsx 출력 | 이벤트, 기획안, 탭 생성, 보상 추천 |
    | 🌐 현지화 번역 | 게임 텍스트 다국어 현지화 (용어집 기반) | 번역, 현지화, 일본어, 영어, 용어집 |

    👈 **왼쪽 사이드바**에서 에이전트를 선택하세요.
    """)

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📅 이벤트 기획 에이전트")
        st.markdown("""
        - 기존 xlsx 구조 분석 + **패턴 자동 학습**
        - 장르·시즌 기반 이벤트 문구 자동 생성
        - 보상 수량·명칭 이력 기반 추천
        - 이벤트 패턴 갭 분석
        - 검토 완료 후 Google Sheets 출력
        """)

    with col2:
        st.subheader("🌐 현지화 번역 에이전트")
        st.markdown("""
        - Google Sheets + Excel 용어집 로드 및 병합
        - 텍스트 유형 자동 분류 (대사/아이템/UI/시스템)
        - 용어집 우선 적용 다국어 동시 번역
        - 미지정 용어 자동 고지
        - 세션 누적 후 xlsx/csv Export
        """)

    # 산출물 현황
    st.divider()
    st.subheader("📁 최근 산출물")
    ep_files = sorted((OUTPUT_DIR / "projects" / "event-planner" / "file").glob("*.xlsx")) \
        if (OUTPUT_DIR / "projects" / "event-planner" / "file").exists() else []
    gl_files = sorted((OUTPUT_DIR / "game-localizer").glob("translation_export_*.xlsx")) \
        if (OUTPUT_DIR / "game-localizer").exists() else []

    col3, col4 = st.columns(2)
    with col3:
        st.caption("이벤트 기획 출력물")
        if ep_files:
            for f in ep_files[-3:]:
                st.markdown(f"- `{f.name}`")
        else:
            st.info("아직 생성된 파일이 없습니다.")
    with col4:
        st.caption("번역 Export 파일")
        if gl_files:
            for f in gl_files[-3:]:
                st.markdown(f"- `{f.name}`")
        else:
            st.info("아직 Export된 파일이 없습니다.")


# ═══════════════════════════════════════════════════════════════════════════════
# 이벤트 기획 에이전트
# ═══════════════════════════════════════════════════════════════════════════════
elif agent == "📅 이벤트 기획 에이전트":
    st.title("📅 이벤트 기획 에이전트")
    st.caption("기존 xlsx를 학습해 신규 이벤트 기획안을 자동 생성합니다.")

    PROJECT_ID = "event-planner"

    # ── 소스 파일 설정 (탭 바깥 — 공통) ─────────────────────────────────────
    st.subheader("📂 소스 파일 설정")
    st.caption("모든 단계에서 공통으로 사용되는 소스 xlsx를 먼저 지정하세요.")

    cp_now = load_json_safe(CURRENT_PROJECT_FILE)
    source_path = st.text_input(
        "소스 xlsx 경로",
        value=cp_now.get("source_xlsx", ""),
        placeholder="예: C:/Users/.../이벤트.xlsx",
        help="기존 이벤트 데이터가 담긴 원본 xlsx 파일. 설정하면 모든 스크립트에 자동 적용됩니다.",
        key="global_source_path",
    )

    if source_path and Path(source_path).exists():
        if source_path != cp_now.get("source_xlsx"):
            save_current_project(source_path, PROJECT_ID)
            st.success(f"✅ 프로젝트 소스 설정 완료: `{Path(source_path).name}`")
        else:
            st.info(f"📌 현재 소스: `{Path(source_path).name}`")
    elif source_path:
        st.error(f"파일을 찾을 수 없습니다: `{source_path}`")

    st.divider()

    # ── 탭 구성 ──────────────────────────────────────────────────────────────
    tab_learn, tab_main, tab_rewards, tab_patterns, tab_output = st.tabs([
        "⓪ 패턴 학습", "① 탭 생성", "② 보상 추천", "③ 패턴 갭 분석", "④ 최종 출력"
    ])

    work_dir = get_work_dir(PROJECT_ID)
    file_dir = get_file_dir(PROJECT_ID)

    # ══════════════════════════════════════════════════════════════════════════
    # ⓪ 패턴 학습 탭 (신규)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_learn:
        st.subheader("⓪ 기존 파일에서 패턴 자동 학습")
        st.markdown("""
        소스 xlsx의 **이전 탭 전체**를 분석해 세 가지 패턴을 학습합니다.
        이 단계를 실행하면 이후 탭 생성·보상 추천의 품질이 크게 향상됩니다.

        | 학습 항목 | 설명 | 저장 파일 |
        |---|---|---|
        | 이벤트 제목·문구 | 기존 제목에서 시즌 키워드·문구 구조 추출 | `historical_event_names.json` |
        | 이벤트 일정 패턴 | 탭 간격, 이벤트 유형별 등장률, anchor 이벤트 | `schedule_patterns.json` |
        | 보상 패턴 | 이벤트 유형별 보상 median/range/trend | `reward_by_event.json` |
        """)

        st.divider()

        if not source_path or not Path(source_path).exists():
            st.warning("⚠️ 먼저 위에서 소스 xlsx 경로를 설정하세요.")
        else:
            col_l1, col_l2, col_l3 = st.columns(3)

            # ── 개별 실행 버튼 ──────────────────────────────────────────────
            with col_l1:
                st.markdown("**① 이벤트 제목·문구 학습**")
                if st.button("제목 패턴 추출", use_container_width=True, key="btn_learn_names"):
                    cmd = [
                        sys.executable,
                        str(SCRIPTS_DIR / "extract_event_names.py"),
                        source_path,
                        "--output", str(work_dir / "historical_event_names.json"),
                        "--summarize",
                    ]
                    ok, out, err = run_script(cmd, "제목 패턴 추출")
                    if ok:
                        st.success("✅ 제목 패턴 추출 완료")
                        names_data = load_json_safe(work_dir / "historical_event_names.json")
                        if names_data:
                            st.metric("분석 탭 수", names_data.get("total_tabs", "?"))
                            st.metric("이벤트 섹션 수", names_data.get("total_event_sections", "?"))
                    else:
                        st.error("실패")
                        st.code(err or out)

            with col_l2:
                st.markdown("**② 이벤트 일정 패턴 학습**")
                if st.button("일정 패턴 분석", use_container_width=True, key="btn_learn_sched"):
                    cmd = [
                        sys.executable,
                        str(SCRIPTS_DIR / "analyze_schedule_patterns.py"),
                        source_path,
                        "--output", str(work_dir / "schedule_patterns.json"),
                    ]
                    ok, out, err = run_script(cmd, "일정 패턴 분석")
                    if ok:
                        st.success("✅ 일정 패턴 분석 완료")
                        sched_data = load_json_safe(work_dir / "schedule_patterns.json")
                        if sched_data:
                            st.metric("분석 탭 수", sched_data.get("total_tabs_analyzed", "?"))
                            st.metric("탭 간격(일)", sched_data.get("tab_interval_days", "?"))
                            st.metric("탭당 평균 이벤트", sched_data.get("avg_events_per_tab", "?"))
                    else:
                        st.error("실패")
                        st.code(err or out)

            with col_l3:
                st.markdown("**③ 보상 패턴 학습**")
                if st.button("보상 패턴 스캔", use_container_width=True, key="btn_learn_reward"):
                    cmd = [
                        sys.executable,
                        str(SCRIPTS_DIR / "scan_rewards_by_event.py"),
                        source_path,
                        str(work_dir / "reward_by_event.json"),
                        "--summarize",
                    ]
                    ok, out, err = run_script(cmd, "보상 패턴 스캔")
                    if ok:
                        st.success("✅ 보상 패턴 스캔 완료")
                        reward_data = load_json_safe(work_dir / "reward_by_event.json")
                        if reward_data:
                            n_types = len(reward_data.get("event_type_patterns", {}))
                            st.metric("이벤트 유형 수", n_types)
                    else:
                        st.error("실패")
                        st.code(err or out)

            st.divider()

            # ── 전체 일괄 실행 ───────────────────────────────────────────────
            if st.button(
                "🚀 패턴 학습 전체 실행 (①②③ 순서대로)",
                type="primary", use_container_width=True, key="btn_learn_all",
            ):
                save_current_project(source_path, PROJECT_ID)
                progress = st.progress(0, text="패턴 학습 시작...")
                log_area = st.empty()
                logs: list[str] = []

                steps = [
                    (
                        "① 이벤트 제목·문구 추출",
                        [sys.executable, str(SCRIPTS_DIR / "extract_event_names.py"),
                         source_path,
                         "--output", str(work_dir / "historical_event_names.json"),
                         "--summarize"],
                    ),
                    (
                        "② 이벤트 일정 패턴 분석",
                        [sys.executable, str(SCRIPTS_DIR / "analyze_schedule_patterns.py"),
                         source_path,
                         "--output", str(work_dir / "schedule_patterns.json")],
                    ),
                    (
                        "③ 보상 패턴 스캔",
                        [sys.executable, str(SCRIPTS_DIR / "scan_rewards_by_event.py"),
                         source_path,
                         str(work_dir / "reward_by_event.json"),
                         "--summarize"],
                    ),
                    (
                        "④ 학습 결과 누적 저장",
                        [sys.executable, str(SCRIPTS_DIR / "save_learning.py"),
                         "--append-names",    str(work_dir / "historical_event_names.json"),
                         "--append-schedule", str(work_dir / "schedule_patterns.json"),
                         "--append-rewards",  str(work_dir / "reward_by_event.json")],
                    ),
                ]

                all_ok = True
                for i, (label, cmd) in enumerate(steps):
                    progress.progress((i) / len(steps), text=f"{label} 중...")
                    ok, out, err = run_script(cmd, label)
                    if ok:
                        logs.append(f"✅ {label}")
                    else:
                        logs.append(f"❌ {label}\n{err or out}")
                        all_ok = False
                    log_area.code("\n".join(logs))

                progress.progress(1.0, text="완료")
                if all_ok:
                    st.success("🎉 패턴 학습 전체 완료! 학습 결과가 누적 저장되었습니다.")
                else:
                    st.warning("일부 단계에서 오류가 발생했습니다. 위 로그를 확인하세요.")

            # ── 학습 결과 현황 ────────────────────────────────────────────────
            st.divider()
            st.subheader("📊 현재 학습 결과 현황")

            col_s1, col_s2, col_s3 = st.columns(3)

            with col_s1:
                names_data = load_json_safe(work_dir / "historical_event_names.json")
                if names_data:
                    st.success("✅ 제목 패턴")
                    st.metric("총 탭 수", names_data.get("total_tabs", "?"))
                    st.metric("이벤트 섹션", names_data.get("total_event_sections", "?"))
                    kw = names_data.get("keyword_frequency", {})
                    if kw:
                        top = list(kw.items())[:3]
                        st.caption(f"키워드 Top3: {', '.join(k for k,_ in top)}")
                else:
                    st.warning("⚠️ 미학습")
                    st.caption("제목 패턴 추출을 실행하세요")

            with col_s2:
                sched_data = load_json_safe(work_dir / "schedule_patterns.json")
                if sched_data:
                    st.success("✅ 일정 패턴")
                    st.metric("탭 간격(일)", sched_data.get("tab_interval_days", "?"))
                    st.metric("평균 이벤트/탭", sched_data.get("avg_events_per_tab", "?"))
                    anchors = sched_data.get("anchor_events", [])
                    if anchors:
                        st.caption(f"Anchor: {', '.join(a['type'] for a in anchors[:2])}")
                else:
                    st.warning("⚠️ 미학습")
                    st.caption("일정 패턴 분석을 실행하세요")

            with col_s3:
                reward_data = load_json_safe(work_dir / "reward_by_event.json")
                if reward_data:
                    st.success("✅ 보상 패턴")
                    n_types = len(reward_data.get("event_type_patterns", {}))
                    st.metric("이벤트 유형 수", n_types)
                    st.caption("median/range/trend 학습 완료")
                else:
                    st.warning("⚠️ 미학습")
                    st.caption("보상 패턴 스캔을 실행하세요")

            # 누적 학습 파일 현황
            learning_file = OUTPUT_DIR / "projects" / PROJECT_ID / "learning" / "agent_learning.json"
            if learning_file.exists():
                st.divider()
                learning = load_json_safe(learning_file)
                acc = learning.get("accumulated_learnings", {})
                runs = len(learning.get("runs", []))
                st.info(
                    f"📚 누적 학습: **{runs}회 실행** | "
                    f"이벤트 유형 빈도 {len(acc.get('event_frequency_patterns', {}))}종 | "
                    f"보상 패턴 {len(acc.get('event_reward_patterns', {}))}종"
                )

            # 이벤트 유형별 상세 현황
            if sched_data and sched_data.get("event_type_stats"):
                with st.expander("이벤트 유형별 등장률 상세"):
                    import pandas as pd
                    rows = []
                    for etype, info in sorted(
                        sched_data["event_type_stats"].items(),
                        key=lambda x: -x[1].get("rate", 0),
                    ):
                        rows.append({
                            "이벤트 유형": etype,
                            "등장률": info.get("rate_pct", "?"),
                            "등장 탭 수": f"{info.get('seen_tabs', 0)}/{info.get('total_tabs', 0)}",
                            "우선순위": info.get("priority", "?"),
                            "제목 예시": info.get("title_examples", [""])[0][:30],
                        })
                    if rows:
                        st.dataframe(pd.DataFrame(rows), use_container_width=True)

            if reward_data and reward_data.get("event_type_summary"):
                with st.expander("이벤트 유형별 보상 기준선 상세"):
                    import pandas as pd
                    rows2 = []
                    for etype, info in reward_data["event_type_summary"].items():
                        for rtype, stats in info.get("reward_summary", {}).items():
                            rows2.append({
                                "이벤트 유형": etype,
                                "보상 유형": rtype,
                                "median": stats.get("median", "?"),
                                "range": f"{stats.get('range', ['?','?'])[0]} ~ {stats.get('range', ['?','?'])[1]}",
                                "샘플 수": stats.get("samples", "?"),
                                "trend": stats.get("trend", "?"),
                            })
                    if rows2:
                        st.dataframe(pd.DataFrame(rows2), use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ① 탭 생성
    # ══════════════════════════════════════════════════════════════════════════
    with tab_main:
        st.subheader("생성할 탭 설정")

        # 패턴 학습 여부 경고
        sched_check = load_json_safe(work_dir / "schedule_patterns.json")
        if not sched_check:
            st.warning("⚠️ 패턴 학습이 실행되지 않았습니다. ⓪ 패턴 학습 탭을 먼저 실행하면 더 정확한 결과를 얻을 수 있습니다.")

        output_filename = st.text_input(
            "출력 파일명",
            value=f"이벤트기획_{datetime.now().strftime('%Y%m%d')}.xlsx",
        )

        col_tabs, col_ref = st.columns(2)
        with col_tabs:
            new_tabs_input = st.text_area(
                "생성할 탭명 (줄바꿈으로 구분, YYMMDD 형식)",
                placeholder="260625\n260702\n260709",
                height=100,
            )
        with col_ref:
            ref_tabs_input = st.text_area(
                "참조 탭명 (생성 탭과 동일 순서)",
                placeholder="260611\n260618\n260618",
                height=100,
            )

        st.divider()
        st.subheader("장르 및 키워드 설정")

        GENRE_MAP = {
            "액션·슈팅": ["핵앤슬래시", "FPS", "TPS"],
            "RPG·전략":  ["MMORPG", "턴제", "전략·RTS", "MOBA·AOS"],
            "캐주얼":    ["시뮬레이션·어드벤처", "퍼즐", "리듬", "로그라이크·덱빌딩"],
            "스포츠":    ["야구", "축구", "농구", "기타 스포츠"],
        }

        col_g1, col_g2, col_g3 = st.columns(3)
        with col_g1:
            genre_family = st.selectbox("장르 계열", list(GENRE_MAP.keys()))
        with col_g2:
            genre_detail = st.selectbox("세부 장르", GENRE_MAP[genre_family])
        with col_g3:
            target_market = st.selectbox("타겟 마켓", ["글로벌", "일본", "한국", "북미"])

        # 학습된 키워드 자동 제안
        names_data = load_json_safe(work_dir / "historical_event_names.json")
        learned_kws = ""
        if names_data.get("keyword_frequency"):
            top_kws = list(names_data["keyword_frequency"].keys())[:10]
            learned_kws = ", ".join(top_kws)

        keywords_input = st.text_input(
            "이벤트 키워드 (쉼표 구분)",
            value=learned_kws,
            placeholder="예: 전반기, 올스타, 홈런, 만루, 끝내기",
            help="학습된 키워드가 자동으로 채워집니다. 필요 시 수정하세요.",
        )
        if learned_kws:
            st.caption("💡 ⓪ 패턴 학습에서 추출된 키워드가 자동 적용되었습니다.")

        update_notes = st.text_area(
            "업데이트 내용 (선택)",
            placeholder="예: 이번 달 보상에 '여름 선물 팩' 추가, 미션 이벤트 기간 3일로 단축",
            height=80,
        )

        st.divider()

        if st.button("🚀 탭 생성 실행", type="primary", use_container_width=True):
            if not source_path or not Path(source_path).exists():
                st.error("위에서 소스 xlsx 경로를 먼저 설정하세요.")
            elif not new_tabs_input:
                st.error("생성할 탭명을 입력하세요.")
            else:
                new_tabs = [t.strip() for t in new_tabs_input.strip().splitlines() if t.strip()]
                ref_tabs = [t.strip() for t in ref_tabs_input.strip().splitlines() if t.strip()]

                if ref_tabs and len(ref_tabs) != len(new_tabs):
                    st.error(f"생성 탭 수({len(new_tabs)})와 참조 탭 수({len(ref_tabs)})가 다릅니다.")
                else:
                    file_dir.mkdir(parents=True, exist_ok=True)
                    work_dir.mkdir(parents=True, exist_ok=True)
                    output_path = file_dir / output_filename

                    save_current_project(source_path, PROJECT_ID)

                    keywords = [k.strip() for k in keywords_input.split(",") if k.strip()] \
                        if keywords_input else []

                    # 대상 월 결정 (new_tabs 첫 탭 날짜 기준)
                    try:
                        _dt = datetime.strptime("20" + new_tabs[0], "%Y%m%d")
                        target_month_str = _dt.strftime("%Y-%m")
                    except Exception:
                        target_month_str = datetime.now().strftime("%Y-%m")

                    progress = st.progress(0, text="탭 생성 준비 중...")
                    logs: list[str] = []
                    log_area = st.empty()

                    # ── Step 1: 이벤트 명칭 자동 생성 (학습 데이터 적용) ──────
                    progress.progress(0.2, text="① 이벤트 제목 패턴 적용 중...")
                    names_cmd = [
                        sys.executable,
                        str(SCRIPTS_DIR / "generate_event_names.py"),
                        "--source",       source_path,
                        "--new-tabs",     ",".join(new_tabs),
                        "--ref-tabs",     ",".join(ref_tabs) if ref_tabs else ",".join(new_tabs),
                        "--target-month", target_month_str,
                        "--genre",        genre_detail,
                        "--phrases",      ",".join(keywords) if keywords else "",
                        "--work-dir",     str(work_dir),
                    ]
                    ok_names, out_names, err_names = run_script(names_cmd, "명칭 생성")
                    if ok_names:
                        logs.append(f"✅ 이벤트 제목 패턴 적용 완료\n{out_names.strip()}")
                    else:
                        logs.append(f"⚠️ 이벤트 제목 자동 변환 실패 (날짜만 적용됨)\n{err_names or out_names}")
                    log_area.code("\n".join(logs))

                    # ── Step 2: handoff JSON ──────────────────────────────────
                    handoff = {
                        "source_path":   source_path,
                        "target_month":  target_month_str,
                        "market":        target_market,
                        "genre":         genre_detail,
                        "new_tab_names": new_tabs,
                        "ref_tab_names": ref_tabs,
                        "output_path":   str(output_path),
                        "update_notes":  update_notes or None,
                        "genre_phrases": keywords,
                    }
                    handoff_dir = OUTPUT_DIR / "handoff"
                    handoff_dir.mkdir(parents=True, exist_ok=True)
                    (handoff_dir / "event-planner_input.json").write_text(
                        json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8"
                    )

                    # ── Step 3: create_tabs.py (날짜 치환 + 명칭 치환) ────────
                    progress.progress(0.6, text="② 탭 생성 및 날짜/제목 치환 중...")
                    create_cmd = [
                        sys.executable,
                        str(SCRIPTS_DIR / "create_tabs.py"),
                        source_path,
                        str(output_path),
                        ",".join(new_tabs),
                    ]
                    if ref_tabs:
                        create_cmd += ["--ref-tabs", ",".join(ref_tabs)]

                    ok_create, out_create, err_create = run_script(create_cmd, "탭 생성")
                    if ok_create:
                        logs.append(f"✅ 탭 생성 완료: {output_path.name}\n{out_create.strip()}")
                    else:
                        logs.append(f"❌ 탭 생성 실패\n{err_create or out_create}")
                    log_area.code("\n".join(logs))

                    progress.progress(1.0, text="완료")

                    if ok_create:
                        st.success(f"🎉 완료: `{output_path.name}`")
                        st.session_state["ep_output_path"] = str(output_path)
                        st.session_state["ep_source_path"] = source_path
                        st.session_state["ep_new_tabs"]    = new_tabs

                        # 생성 결과 요약
                        names_cfg = load_json_safe(work_dir / "event_names_config.json")
                        total_renamed = sum(
                            len(v) for v in names_cfg.get("event_name_replacements", {}).values()
                        )
                        col_s1, col_s2 = st.columns(2)
                        col_s1.metric("생성 탭 수", len(new_tabs))
                        col_s2.metric("제목 자동 변경 수", total_renamed)

                        if total_renamed == 0:
                            st.warning(
                                "⚠️ 이벤트 제목이 변경되지 않았습니다. "
                                "⓪ 패턴 학습 탭에서 **제목 패턴 추출**을 먼저 실행하거나 "
                                "키워드를 직접 입력하세요."
                            )
                        with st.expander("상세 로그"):
                            st.code("\n".join(logs))
                    else:
                        st.error("탭 생성 실패")
                        st.code(err_create or out_create)

    # ══════════════════════════════════════════════════════════════════════════
    # ② 보상 추천
    # ══════════════════════════════════════════════════════════════════════════
    with tab_rewards:
        st.subheader("보상 수량·명칭 추천")

        output_path_r = st.text_input(
            "output xlsx 경로",
            value=st.session_state.get("ep_output_path", ""),
            key="reward_output_path",
        )
        source_path_r = st.text_input(
            "소스 xlsx 경로",
            value=source_path or st.session_state.get("ep_source_path", ""),
            key="reward_source_path",
        )

        # 보상 패턴 학습 여부 경고
        reward_check = load_json_safe(work_dir / "reward_by_event.json")
        if reward_check:
            st.success("✅ 보상 패턴 학습 완료 — HIGH 신뢰도 항목은 자동 확정됩니다.")
        else:
            st.warning("⚠️ 보상 패턴 미학습 — ⓪ 패턴 학습 탭에서 보상 패턴을 먼저 스캔하면 자동 추천 정확도가 높아집니다.")

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("① 소스 탭 보상 스캔 (요약)", use_container_width=True):
                if not source_path_r or not Path(source_path_r).exists():
                    st.error("소스 xlsx 경로를 확인하세요.")
                else:
                    save_current_project(source_path_r, PROJECT_ID)
                    cmd = [
                        sys.executable,
                        str(SCRIPTS_DIR / "scan_rewards_by_event.py"),
                        source_path_r,
                        str(work_dir / "reward_by_event.json"),
                        "--summarize",
                    ]
                    ok, out, err = run_script(cmd, "소스 보상 스캔")
                    if ok:
                        st.success("✅ 소스 탭 보상 스캔 완료 (요약 저장)")
                        with st.expander("로그"):
                            st.code(out)
                    else:
                        st.error("스캔 실패")
                        st.code(err or out)

        with col_r2:
            if st.button("② 신규 탭 보상 스캔", use_container_width=True):
                if not output_path_r or not Path(output_path_r).exists():
                    st.error("output xlsx 경로를 확인하세요.")
                else:
                    cmd = [
                        sys.executable,
                        str(SCRIPTS_DIR / "scan_rewards_by_event.py"),
                        output_path_r,
                        str(work_dir / "reward_new_tabs.json"),
                    ]
                    ok, out, err = run_script(cmd, "신규 탭 스캔")
                    if ok:
                        st.success("✅ 신규 탭 보상 스캔 완료")
                    else:
                        st.error("스캔 실패")
                        st.code(err or out)

        st.divider()
        use_low_only = st.checkbox(
            "LOW 신뢰도 항목만 검토 (HIGH는 자동 확정)",
            value=bool(reward_check),
            help="보상 패턴 학습이 완료된 경우 권장. 검토 항목 수가 크게 줄어듭니다.",
        )

        if st.button("③ 보상 추천 생성 → 순차 리뷰 큐 준비", use_container_width=True, type="primary"):
            reward_by_event = work_dir / "reward_by_event.json"
            reward_new_tabs = work_dir / "reward_new_tabs.json"

            if not reward_by_event.exists():
                st.error("먼저 소스 탭 보상 스캔을 실행하세요.")
            elif not reward_new_tabs.exists():
                st.error("먼저 신규 탭 보상 스캔을 실행하세요.")
            else:
                # recommend_rewards.py
                recommend_cmd = [
                    sys.executable, str(SCRIPTS_DIR / "recommend_rewards.py"),
                    "--per-event",
                ]
                if use_low_only:
                    recommend_cmd += ["--auto-confirm-high", "--low-only"]

                ok, out, err = run_script(recommend_cmd, "보상 추천")
                if ok:
                    # _prep_sequential_review.py
                    review_cmd = [
                        sys.executable, str(SCRIPTS_DIR / "_prep_sequential_review.py"),
                    ]
                    if use_low_only:
                        review_cmd.append("--low-confidence-only")

                    ok2, out2, err2 = run_script(review_cmd, "리뷰 큐 생성")
                    if ok2:
                        st.success("✅ 보상 추천 및 순차 리뷰 큐 준비 완료")
                        queue_file = work_dir / "reward_review_queue.json"
                        if queue_file.exists():
                            q = load_json_safe(queue_file)
                            col_m1, col_m2, col_m3 = st.columns(3)
                            col_m1.metric("총 섹션", q.get("total_sections", "?"))
                            col_m2.metric("변경 권장", q.get("sections_with_changes", "?"))
                            col_m3.metric("자동 확정", q.get("auto_confirmed_count", 0))
                        with st.expander("추천 로그"):
                            st.code(out)
                    else:
                        st.error("리뷰 큐 생성 실패")
                        st.code(err2)
                else:
                    st.error("보상 추천 실패")
                    st.code(err or out)

        # 보상 변경 적용
        st.divider()
        st.subheader("보상 변경 적용")
        changes_input = st.text_area(
            "변경 내용 JSON",
            placeholder='[{"qty_cell":"AS12","new_qty":50},{"item_cell":"AR20","new_name":"새 아이템명"}]',
            height=120,
        )
        if st.button("변경 적용", use_container_width=True):
            if not output_path_r or not changes_input.strip():
                st.error("output xlsx 경로와 변경 내용을 입력하세요.")
            else:
                try:
                    changes_data = json.loads(changes_input)
                    changes_file = work_dir / "reward_changes_manual.json"
                    changes_file.write_text(
                        json.dumps(changes_data, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    cmd = [
                        sys.executable, str(SCRIPTS_DIR / "apply_reward_changes.py"),
                        "--xlsx", output_path_r,
                        "--changes", str(changes_file),
                    ]
                    ok, out, err = run_script(cmd, "보상 변경 적용")
                    if ok:
                        st.success("✅ 보상 변경 적용 완료")

                        # 작업 완료 → 학습 저장
                        save_cmd = [
                            sys.executable, str(SCRIPTS_DIR / "save_learning.py"),
                            "--append-rewards", str(work_dir / "reward_new_tabs.json"),
                        ]
                        run_script(save_cmd, "학습 저장")
                        st.caption("📚 보상 패턴이 누적 학습에 저장되었습니다.")
                    else:
                        st.error("적용 실패")
                        st.code(err or out)
                except json.JSONDecodeError as e:
                    st.error(f"JSON 파싱 오류: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # ③ 패턴 갭 분석
    # ══════════════════════════════════════════════════════════════════════════
    with tab_patterns:
        st.subheader("이벤트 패턴 갭 분석")
        st.caption("소스 xlsx의 역사적 이벤트 구성 패턴 대비 신규 탭에서 누락된 이벤트 유형을 분석합니다.")

        source_path_p = st.text_input(
            "소스 xlsx",
            value=source_path or st.session_state.get("ep_source_path", ""),
            key="pattern_source",
        )
        output_path_p = st.text_input(
            "output xlsx",
            value=st.session_state.get("ep_output_path", ""),
            key="pattern_output",
        )
        new_tabs_p = st.text_input(
            "분석할 탭명 (쉼표 구분)",
            value=",".join(st.session_state.get("ep_new_tabs", [])),
            key="pattern_tabs",
        )

        if st.button("🔍 갭 분석 실행", type="primary", use_container_width=True):
            if not all([source_path_p, output_path_p, new_tabs_p]):
                st.error("소스 xlsx, output xlsx, 탭명을 모두 입력하세요.")
            elif not Path(source_path_p).exists():
                st.error("소스 xlsx 파일이 없습니다.")
            elif not Path(output_path_p).exists():
                st.error("output xlsx 파일이 없습니다.")
            else:
                save_current_project(source_path_p, PROJECT_ID)
                cmd = [
                    sys.executable,
                    str(SCRIPTS_DIR / "analyze_event_patterns.py"),
                    source_path_p,
                    output_path_p,
                    new_tabs_p.replace(" ", ""),
                ]
                ok, out, err = run_script(cmd, "갭 분석")

                if ok:
                    st.success("✅ 갭 분석 완료")
                    if out:
                        st.code(out)
                    analysis_file = work_dir / "event_pattern_analysis.json"
                    if analysis_file.exists():
                        data = load_json_safe(analysis_file)
                        for tab_name, tab_data in data.get("tabs", {}).items():
                            with st.expander(f"탭: {tab_name}"):
                                patterns = tab_data.get("patterns", [])
                                if patterns:
                                    import pandas as pd
                                    rows = []
                                    for p in patterns:
                                        rows.append({
                                            "이벤트 유형": p.get("event_type", ""),
                                            "등장률": f"{p.get('rate', 0)*100:.0f}% ({p.get('count', 0)}/{p.get('total', 0)})",
                                            "이번 탭": "✅ 있음" if p.get("present") else "❌ 없음",
                                            "우선순위": p.get("priority", ""),
                                        })
                                    st.dataframe(pd.DataFrame(rows), use_container_width=True)

                    # 갭 분석 후 학습 저장
                    save_cmd = [
                        sys.executable, str(SCRIPTS_DIR / "save_learning.py"),
                        "--append-schedule", str(work_dir / "schedule_patterns.json"),
                    ]
                    run_script(save_cmd, "학습 저장")
                    st.caption("📚 일정 패턴이 누적 학습에 저장되었습니다.")
                else:
                    st.warning("갭 분석 중 오류 발생")
                    if err:
                        st.code(err)

    # ══════════════════════════════════════════════════════════════════════════
    # ④ 최종 출력
    # ══════════════════════════════════════════════════════════════════════════
    with tab_output:
        st.subheader("Google Sheets 업로드")

        output_path_o = st.text_input(
            "업로드할 xlsx 경로",
            value=st.session_state.get("ep_output_path", ""),
            key="output_xlsx",
        )
        gsheet_target = st.text_input(
            "대상 Google Sheets URL (비워두면 신규 생성)",
            placeholder="https://docs.google.com/spreadsheets/d/...",
        )

        if st.button("☁️ Google Sheets 업로드", type="primary", use_container_width=True):
            if not output_path_o or not Path(output_path_o).exists():
                st.error("업로드할 xlsx 파일이 없습니다.")
            else:
                cmd = [sys.executable, str(SCRIPTS_DIR / "upload_to_gsheets.py"), output_path_o]
                if gsheet_target:
                    cmd += ["--target-url", gsheet_target]
                ok, out, err = run_script(cmd, "GSheets 업로드")
                if ok:
                    st.success("✅ 업로드 완료")
                    if out:
                        st.code(out)

                    # 업로드 완료 → 전체 학습 저장
                    final_save_cmd = [
                        sys.executable, str(SCRIPTS_DIR / "save_learning.py"),
                        "--append-names",    str(work_dir / "historical_event_names.json"),
                        "--append-schedule", str(work_dir / "schedule_patterns.json"),
                        "--append-rewards",  str(work_dir / "reward_new_tabs.json"),
                    ]
                    ok_s, _, _ = run_script(final_save_cmd, "최종 학습 저장")
                    if ok_s:
                        st.caption("📚 이번 작업 결과가 누적 학습에 저장되었습니다.")
                else:
                    st.error("업로드 실패")
                    st.code(err or out)

        st.divider()
        st.subheader("로컬 다운로드")
        output_path_dl = st.text_input(
            "다운로드할 xlsx 경로",
            value=st.session_state.get("ep_output_path", ""),
            key="dl_xlsx",
        )
        if output_path_dl and Path(output_path_dl).exists():
            with open(output_path_dl, "rb") as f:
                st.download_button(
                    label=f"⬇️ {Path(output_path_dl).name} 다운로드",
                    data=f,
                    file_name=Path(output_path_dl).name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        # 최근 출력물 목록
        st.divider()
        st.subheader("최근 출력물")
        ep_files = sorted(file_dir.glob("*.xlsx")) if file_dir.exists() else []
        if ep_files:
            for f in ep_files[-5:]:
                col_n, col_d = st.columns([4, 1])
                with col_n:
                    st.markdown(f"`{f.name}` — {f.stat().st_size // 1024} KB")
                with col_d:
                    with open(f, "rb") as fh:
                        st.download_button(
                            "⬇️", data=fh, file_name=f.name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_ep_{f.name}",
                        )
        else:
            st.info("아직 생성된 파일이 없습니다.")


# ═══════════════════════════════════════════════════════════════════════════════
# 현지화 번역 에이전트
# ═══════════════════════════════════════════════════════════════════════════════
elif agent == "🌐 현지화 번역 에이전트":
    st.title("🌐 현지화 번역 에이전트")
    st.caption("게임 텍스트를 용어집 기반으로 다국어 현지화 번역합니다.")

    LOCALIZER_OUTPUT = OUTPUT_DIR / "game-localizer"
    LOCALIZER_OUTPUT.mkdir(parents=True, exist_ok=True)

    tab_setup, tab_translate, tab_export = st.tabs(
        ["① 용어집 설정", "② 번역", "③ Export"]
    )

    # ── ① 용어집 설정 ────────────────────────────────────────────────────────
    with tab_setup:
        st.subheader("용어집 소스 설정")

        gsheet_url = st.text_input(
            "Google Sheets 용어집 URL (마스터)",
            placeholder="https://docs.google.com/spreadsheets/d/...",
        )
        excel_path = st.text_input(
            "Excel 용어집 경로 (보조)",
            placeholder="예: C:/Users/.../glossary.xlsx",
        )

        if st.button("📂 용어집 로드", type="primary", use_container_width=True):
            if not gsheet_url and not excel_path:
                st.error("Google Sheets URL 또는 Excel 경로 중 하나 이상 입력하세요.")
            else:
                config = {
                    "gsheet_url": gsheet_url or "",
                    "excel_path": excel_path or "",
                    "column_mapping": {"source": "원어", "target_prefix": ""},
                }
                config_file = LOCALIZER_OUTPUT / "glossary_config.json"
                config_file.write_text(
                    json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
                )

                with st.spinner("용어집 로드 중..."):
                    if gsheet_url:
                        ok, _, err = run_script(
                            [sys.executable, str(SCRIPTS_DIR / "fetch_gsheet.py"), gsheet_url],
                            "GSheet 로드",
                        )
                        if not ok:
                            st.warning(f"Google Sheets 로드 실패\n{err}")

                    if excel_path and Path(excel_path).exists():
                        run_script(
                            [sys.executable, str(SCRIPTS_DIR / "read_excel.py"), excel_path],
                            "Excel 로드",
                        )

                    ok3, _, err3 = run_script(
                        [sys.executable, str(SCRIPTS_DIR / "merge_glossary.py")],
                        "용어집 병합",
                    )

                if ok3:
                    st.success("✅ 용어집 로드 및 병합 완료")
                    cache_file = LOCALIZER_OUTPUT / "glossary_cache.json"
                    if cache_file.exists():
                        cache = json.loads(cache_file.read_text(encoding="utf-8"))
                        terms = cache.get("terms", {})
                        conflicts = cache.get("conflicts_log", [])
                        st.metric("등록 용어 수", len(terms))
                        if conflicts:
                            st.warning(f"충돌 항목 {len(conflicts)}건 → Google Sheets 값 우선 적용")
                            with st.expander("충돌 로그"):
                                st.json(conflicts[:10])
                else:
                    st.error("병합 실패")
                    st.code(err3)

        cache_file = LOCALIZER_OUTPUT / "glossary_cache.json"
        if cache_file.exists():
            st.divider()
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            terms = cache.get("terms", {})
            st.success(f"✅ 용어집 캐시 활성 — {len(terms)}개 용어 ({cache.get('generated_at', '?')[:19]})")
            with st.expander("용어 미리보기 (최대 20개)"):
                preview = {k: v for k, v in list(terms.items())[:20]}
                st.json(preview)

    # ── ② 번역 ───────────────────────────────────────────────────────────────
    with tab_translate:
        st.subheader("텍스트 번역")

        cache_file = LOCALIZER_OUTPUT / "glossary_cache.json"
        if not cache_file.exists():
            st.warning("⚠️ 용어집을 먼저 로드하세요. (① 용어집 설정 탭)")
        else:
            source_text = st.text_area(
                "번역할 원문",
                placeholder="번역할 게임 텍스트를 입력하세요.",
                height=120,
            )

            col_t1, col_t2 = st.columns(2)
            with col_t1:
                text_type_hint = st.selectbox(
                    "텍스트 유형 힌트 (선택)",
                    ["자동 감지", "대사 (dialogue)", "아이템설명 (item_desc)",
                     "UI (ui)", "시스템메시지 (system_msg)"],
                )
            with col_t2:
                target_langs = st.multiselect(
                    "번역 대상 언어",
                    ["ko", "ja", "en", "zh"],
                    default=["ko", "ja", "en", "zh"],
                )

            if st.button("🌐 번역 실행", type="primary", use_container_width=True):
                if not source_text.strip():
                    st.error("번역할 텍스트를 입력하세요.")
                else:
                    type_map = {
                        "자동 감지": None,
                        "대사 (dialogue)": "dialogue",
                        "아이템설명 (item_desc)": "item_desc",
                        "UI (ui)": "ui",
                        "시스템메시지 (system_msg)": "system_msg",
                    }
                    req = {
                        "source_text": source_text,
                        "text_type_hint": type_map.get(text_type_hint),
                        "target_languages": target_langs,
                        "glossary_cache_path": str(cache_file),
                    }
                    req_file = LOCALIZER_OUTPUT / "translate_request.json"
                    req_file.write_text(
                        json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8"
                    )

                    ok, out, err = run_script(
                        [sys.executable, str(SCRIPTS_DIR / "match_terms.py")],
                        "용어집 매칭",
                    )

                    if not ok:
                        st.error("용어집 매칭 실패")
                        st.code(err)
                    else:
                        req_data = json.loads(req_file.read_text(encoding="utf-8"))
                        matched = req_data.get("matched_terms", {})
                        unreg   = req_data.get("unregistered_terms", [])

                        st.info(f"용어집 매칭: {len(matched)}개 | 미지정 용어: {len(unreg)}개")
                        if unreg:
                            st.warning(f"⚠️ 미지정 용어: {', '.join(unreg)}")

                        st.divider()
                        st.markdown("### 번역 결과 입력")
                        st.caption(
                            "Claude Code 에이전트가 번역을 수행한 후, "
                            "아래 필드에 결과를 입력하거나 `translate_result.json`을 직접 저장하세요."
                        )

                        col_ko, col_ja = st.columns(2)
                        col_en, col_zh = st.columns(2)
                        with col_ko:
                            tr_ko = st.text_area("한국어 (ko)", height=80)
                        with col_ja:
                            tr_ja = st.text_area("일본어 (ja)", height=80)
                        with col_en:
                            tr_en = st.text_area("영어 (en)", height=80)
                        with col_zh:
                            tr_zh = st.text_area("중국어 (zh)", height=80)

                        if st.button("💾 번역 결과 저장 → 버퍼에 추가"):
                            translations = {}
                            if tr_ko: translations["ko"] = tr_ko
                            if tr_ja: translations["ja"] = tr_ja
                            if tr_en: translations["en"] = tr_en
                            if tr_zh: translations["zh"] = tr_zh

                            if not translations:
                                st.error("번역 결과를 하나 이상 입력하세요.")
                            else:
                                result_data = {
                                    "text_type": type_map.get(text_type_hint) or "dialogue",
                                    "translations": translations,
                                    "unregistered_terms": unreg,
                                    "validation_status": "pass",
                                    "retry_count": 0,
                                }
                                result_file = LOCALIZER_OUTPUT / "translate_result.json"
                                result_file.write_text(
                                    json.dumps(result_data, ensure_ascii=False, indent=2),
                                    encoding="utf-8"
                                )

                                ok2, _, err2 = run_script(
                                    [sys.executable, str(SCRIPTS_DIR / "buffer_manager.py"), "add"],
                                    "버퍼 저장",
                                )
                                if ok2:
                                    st.success("✅ 번역 결과가 세션 버퍼에 추가되었습니다.")
                                else:
                                    st.error("버퍼 저장 실패")
                                    st.code(err2)

        st.divider()
        st.subheader("세션 버퍼 현황")
        col_buf1, col_buf2 = st.columns(2)
        with col_buf1:
            if st.button("📋 버퍼 목록 보기", use_container_width=True):
                ok, out, _ = run_script(
                    [sys.executable, str(SCRIPTS_DIR / "buffer_manager.py"), "list"],
                    "버퍼 목록",
                )
                st.code(out)
        with col_buf2:
            if st.button("🗑️ 버퍼 초기화", use_container_width=True):
                ok, _, err = run_script(
                    [sys.executable, str(SCRIPTS_DIR / "buffer_manager.py"), "clear"],
                    "버퍼 초기화",
                )
                if ok:
                    st.success("버퍼 초기화 완료")
                else:
                    st.error(err)

    # ── ③ Export ─────────────────────────────────────────────────────────────
    with tab_export:
        st.subheader("번역 결과 Export")

        export_format = st.radio("포맷", ["xlsx", "csv", "both"], horizontal=True)

        if st.button("📤 Export 실행", type="primary", use_container_width=True):
            buffer_file = LOCALIZER_OUTPUT / "session_buffer.json"
            if not buffer_file.exists():
                st.error("세션 버퍼가 비어 있습니다. 번역을 먼저 수행하세요.")
            else:
                buf = json.loads(buffer_file.read_text(encoding="utf-8"))
                entries = buf.get("entries", [])
                if not entries:
                    st.error("버퍼에 번역 항목이 없습니다.")
                else:
                    ok, out, err = run_script(
                        [sys.executable, str(SCRIPTS_DIR / "export_xlsx.py"), "--format", export_format],
                        "Export",
                    )
                    if ok:
                        st.success("✅ Export 완료")
                        export_files = sorted(
                            LOCALIZER_OUTPUT.glob("translation_export_*.*"),
                            key=lambda p: p.stat().st_mtime,
                        )
                        for ef in export_files[-2:]:
                            with open(ef, "rb") as f:
                                mime = (
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    if ef.suffix == ".xlsx" else "text/csv"
                                )
                                st.download_button(
                                    label=f"⬇️ {ef.name}",
                                    data=f,
                                    file_name=ef.name,
                                    mime=mime,
                                    use_container_width=True,
                                )
                    else:
                        st.error("Export 실패")
                        st.code(err or out)

        st.divider()
        st.subheader("기존 Export 파일")
        existing = sorted(
            LOCALIZER_OUTPUT.glob("translation_export_*.*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ) if LOCALIZER_OUTPUT.exists() else []

        if existing:
            for ef in existing[:10]:
                col_name, col_dl = st.columns([4, 1])
                with col_name:
                    st.markdown(f"`{ef.name}` — {ef.stat().st_size // 1024} KB")
                with col_dl:
                    with open(ef, "rb") as f:
                        mime = (
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            if ef.suffix == ".xlsx" else "text/csv"
                        )
                        st.download_button(
                            label="⬇️",
                            data=f,
                            file_name=ef.name,
                            mime=mime,
                            key=f"dl_{ef.name}",
                        )
        else:
            st.info("아직 Export된 파일이 없습니다.")
