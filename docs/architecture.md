# 시스템 아키텍처 및 데이터 흐름

## 시스템 아키텍처

### 전체 구조

```
Multi_agent/
├── server.py                    # Flask 백엔드 (PM 오케스트레이터)
├── CLAUDE.md                    # PM 에이전트 행동 지침
├── templates/index.html         # 메인 UI (Jinja2)
├── static/
│   ├── app.js                   # 프론트엔드 로직
│   └── style.css                # 스타일
├── scripts/
│   ├── create_tabs.py           # 핵심: xlsx 탭 복사 + 날짜/제목 치환
│   ├── generate_event_names.py  # 이벤트 제목 자동 생성 (season keyword 치환)
│   ├── _project_config.py       # 프로젝트 경로 관리
│   ├── scan_rewards_by_event.py # 보상 스캔
│   ├── recommend_rewards.py     # 보상 추천
│   └── apply_reward_changes.py  # 보상 변경 적용
├── .claude/agents/
│   ├── event-planner/AGENT.md   # 이벤트 기획 에이전트 지침
│   └── game-localizer/AGENT.md  # 현지화 번역 에이전트 지침
└── output/
    ├── gdrive_cache/            # Google Drive 다운로드 캐시
    ├── projects/
    │   └── event-planner/
    │       ├── work/            # 세션별 임시 파일
    │       │   ├── event_names_config.json   # 제목 치환 브릿지 파일
    │       │   ├── historical_event_names.json
    │       │   ├── reward_by_event.json
    │       │   └── ...
    │       └── file/            # 최종 xlsx 출력
    ├── json/
    │   └── current_project.json # 활성 프로젝트 설정
    └── handoff/                 # PM ↔ 에이전트 데이터
```

---

### 탭 생성 파이프라인 (핵심 흐름)

```
사용자 요청
    │
    ▼
server.py (_run_event_pipeline 또는 event_create_tabs)
    │
    ├─ [1단계] write_current_project() → current_project.json 갱신
    │
    ├─ [2단계] generate_event_names.py 호출
    │          --source xlsx경로
    │          --new-tabs 260625,260709
    │          --ref-tabs 260611,260625
    │          --target-month 2026-07
    │          --genre 야구
    │          --work-dir output/projects/event-planner/work
    │          → event_names_config.json 생성
    │
    └─ [3단계] create_tabs.py 호출
               source output new_tabs ref_tabs
               → 소스 xlsx에서 참조 탭 복사
               → apply_replacements() 실행
               → 최종 xlsx 저장
```

---

### generate_event_names.py 동작 원리

1. 소스 xlsx의 참조 탭(ref_tab)에서 B열 섹션 제목 추출
2. `SEASON_PATTERNS` regex로 시즌 키워드 감지:
   - `r"\d+월\s*이달의"` → `"6월 이달의"`
   - `r"(얼리썸머|초여름|쿨\s*서머|한여름|늦여름)(의)?"` → `"한여름의"`
   - `r"(봄|여름|가을|겨울)(의)"` 등
3. 대상 월에 맞는 새 키워드 선택 (`MONTH_SEASON_FALLBACK` 또는 `genre_phrases` 기반)
4. `(old_title, new_title)` 쌍 생성 → `event_names_config.json`에 저장

---

### 섹션 제목 파싱 패턴 (`parse_section_title`) — 2026-06-09 수정

B열 셀 값이 섹션 경계인지 판단하는 패턴 우선순위 (두 파일 공통 적용):

| 우선순위 | 패턴 변수 | 정규식 | 예시 | 비고 |
|---|---|---|---|---|
| 1 | `TAB_HEADER_RE` | `^\d{1,2}[./-]\d{1,2}[._\s]` | `"06.25_ Event"` | 탭 헤더 — **제외** |
| 2 | `SECTION_RE` | `^\d+[.)]` | `"6. 승부 예측 이벤트!"`, `"6) 이벤트"` | 숫자+점/괄호 형식 |
| 3 | `TITLE_RE` | `^이벤트\s*제목\s*:\s*(.+)$` | `"이벤트 제목 : 출석 이벤트!"` | 콜론 이후 제목 추출 |
| 4 | `COUPON_TITLE_RE` | `^\d+월\s+이달의\s+쿠폰` | `"5월 이달의 쿠폰"` | 매월 쿠폰 헤더 |
| 5 | `CUSTOM_COUPON_RE` | `^(?!■\|∎)[가-힣A-Za-z0-9]+\s+쿠폰$` | `"폴리볼 쿠폰"`, `"KBO 쿠폰"` | 커스텀 쿠폰 헤더 |

**주요 변경 내용 (2026-06-09):**

- `SECTION_RE`: `^\d+\.` → `^\d+[.)]` — 숫자+닫는괄호(`6)`) 형식도 지원
- `CUSTOM_COUPON_RE` 신규 추가 — `"폴리볼 쿠폰"` 같은 비표준 쿠폰 섹션 헤더 인식
- `analyze_event_patterns.py`에 동일 패턴 적용 + `EVENT_TYPE_KEYWORDS`에 `"쿠폰"` → `"쿠폰_이벤트"` 추가

**수정 전 미인식 사례 (버그 → 수정으로 해결):**

```
"폴리볼 쿠폰"      → parse_section_title() = None → "기타" 분류 → 섹션 탐색 불가 ❌
                   → (수정 후) CUSTOM_COUPON_RE 매칭 → "쿠폰이벤트" ✓

"5월 이달의 쿠폰"  → analyze_event_patterns.py에서 None 반환 → "기타" 집계 ❌
                   → (수정 후) COUPON_TITLE_PATTERN 매칭 → "쿠폰_이벤트" 집계 ✓
```

**연속 동일 유형 섹션 병합 규칙 (기존 유지):**

```
"5월 이달의 쿠폰"           (row 190) → 쿠폰이벤트 → 섹션 시작
"1. 5월 이달의 쿠폰 보상"   (row 193) → 쿠폰이벤트 → 동일 유형 연속 → 병합(스킵)
```

→ 섹션 시작은 row 190, 끝은 다음 이종 섹션 시작 전 행.

---

### create_tabs.py → _cli_main() 동작 원리

1. 소스 xlsx 열기 (read_only)
2. 날짜형 탭 목록 추출 (6자리 숫자 패턴)
3. ref_tabs 미지정 시 `_best_ref_tab()`으로 자동 선택
4. `_auto_date_map(ref, new_tab)`으로 날짜 시프트 맵 생성
5. 워크북 열기 (full)
6. `event_names_config.json` 로드 (`load_event_names_config()`)
7. 각 new_tab별:
   - 참조 탭 `copy_worksheet()`
   - `apply_replacements()` 실행 (date_map + 제목 치환 쌍)
8. 불필요 탭 제거 후 저장

---

### apply_replacements() 상세 (2026-06-01 수정 후)

```
셀 순회
    │
    ├─ datetime/date 객체
    │       date_map[MM/DD] → 날짜 직접 교체
    │
    └─ 문자열
            1) all_str_replacements 순차 적용 (이벤트 제목 쌍)
            2) date_map → 슬래시 형식 단일패스 regex (06/11 → 06/25)
            3) date_map → 점 형식 단일패스 regex (06.11 → 06.25)
```

**단일패스 regex를 쓰는 이유:**

- date_map의 키가 값으로 등장할 수 있음
- 예: `"06/11"` → `"06/25"`, `"06/25"` → `"07/09"`
- 순차 적용 시 `"06/11"`이 `"06/25"`로 바뀐 뒤 다시 `"07/09"`로 이중 치환됨
- `re.sub()`은 이미 치환된 위치를 재방문하지 않으므로 안전

---

### _auto_date_map() 알고리즘

```python
delta = new_date - ref_date  # 예: +14일
for i in range(-7, 61):
    src = ref_date + timedelta(days=i)
    dst = src + delta
    date_map["MM/DD(src)"] = "MM/DD(dst)"
```

- ref_date-7부터 ref_date+60 범위를 커버
- 결과: 68개 날짜 매핑 쌍 생성

---

### ProjectPaths 경로 구조

`project_id = "event-planner"`의 경우:

| 경로 키 | 실제 경로 |
|---|---|
| `work_dir` | `output/projects/event-planner/work/` |
| `file_dir` | `output/projects/event-planner/file/` |
| `event_names_config` | `work_dir/event_names_config.json` |

`server.py`의 `EP_WORK = output/projects/event-planner/work/` 와 동일하며,
`generate_event_names.py`의 `--work-dir` 인자로 `EP_WORK`를 전달하여 경로 일치를 보장한다.

---

### UI 탭 선택기 흐름

```
사용자: 소스 경로 입력
    │
    ▼
"탭 목록 불러오기" 클릭
    → POST /api/event/tabs
    → 서버: xlsx 열어 all_tabs + date_tabs 반환
    → UI: 탭 목록 표시 (날짜형=파란색, 기타=회색)
    │
    ▼
새 탭명 입력 + "탭 추가" 클릭
    → _bestRefTab()으로 직전 날짜 탭 자동 추천
    → 드롭다운에서 참조 탭 선택 가능
    │
    ▼
"탭 생성 실행"
    → epGetTabsFromSelector()로 new_tabs/ref_tabs 수집
    → POST /api/event/create-tabs
    → 서버 파이프라인 실행
```

---

## 데이터 흐름 요약

```
[사용자 브라우저]
        │  HTTP (POST /api/event/create-tabs)
        ▼
[server.py — Flask]
        │  subprocess 호출
        ├──► generate_event_names.py
        │         │  읽기: 소스 xlsx (ref_tab B열)
        │         └► 쓰기: event_names_config.json
        │
        └──► create_tabs.py
                  │  읽기: 소스 xlsx + event_names_config.json
                  └► 쓰기: 최종 xlsx (output/projects/event-planner/file/)
```

---

## 에이전트 구조

PM 오케스트레이터(`CLAUDE.md`)는 두 전문 에이전트를 관리한다.

| 에이전트 | 트리거 | 산출물 |
|---|---|---|
| `event-planner` | 이벤트 기획, xlsx 탭 생성, 보상 추천 요청 | xlsx 파일 (`output/projects/event-planner/file/`) |
| `game-localizer` | 번역, 현지화, 다국어 변환 요청 | 번역 결과 (`output/game-localizer/`) |

복합 요청의 경우 비중이 큰 에이전트를 먼저 실행하고 순차적으로 보조 에이전트를 실행한다.
