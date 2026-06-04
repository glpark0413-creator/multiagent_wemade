# 이벤트 기획 에이전트 (event-planner)

> **호출자**: 메인 PM 에이전트 (CLAUDE.md)
> **역할**: 모바일 게임 이벤트 기획안 자동 생성 → 보상 패턴 적용 → 이벤트 구성 추천 → xlsx 출력
> **서버**: Flask SSE 스트리밍 서버 (`server.py`) — `http://0.0.0.0:5050`
> **최종 업데이트**: 2026-06-04 (이벤트 섹션 B열 매칭 버그 수정)

---

## 에이전트 행동 원칙

- 기존 xlsx의 열 구조·포맷·카테고리를 절대 변경하지 않는다
- 단계별 산출물은 즉시 지정 경로에 저장한다 (세션 중단 시 재개 가능)
- **LLM은 키워드 생성 1회만 사용** — 나머지 판단은 규칙 기반(서버 상태 머신)으로 처리
- **기존 파일에서 학습한 패턴을 우선 사용** (토큰 절약)
- 이벤트 제목에 블랙리스트 키워드가 포함되지 않도록 반드시 필터링한다

---

## 입력 수신

PM이 전달하는 `output/handoff/event-planner_input.json`을 먼저 읽는다.

```json
{
  "source_path": "소스 xlsx 경로 또는 Google Sheets URL",
  "target_month": "YYYY-MM",
  "market": "타겟 마켓",
  "genre": "세부 장르 (없으면 null — STEP 1에서 선택)",
  "new_tab_names": ["YYMMDD", ...],
  "ref_tab_names": ["YYMMDD", ...],
  "update_notes": "업데이트 내용 (없으면 null)"
}
```

---

## 서버 상태 머신 (5단계)

대화 흐름 전체를 LLM 없이 서버가 직접 관리한다. 각 단계는 `context["_agent_step"]`으로 추적된다.

```
start
  │
  ▼
STEP 1: wait_genre
  - agent_config.json에 default_genre 있으면 자동 스킵
  - 없으면 사용자에게 장르 선택 요청
  │
  ▼
STEP 2: wait_keywords
  - Claude CLI로 장르·시즌 키워드 생성 (JSON 강제 모드)
  - 블랙리스트 필터링 후 사용자에게 확인
  │
  ▼
STEP 3: wait_ref_tabs
  - 생성할 탭명과 참조 탭명 수집
  - "나머지도 동일?" 단축 질문으로 최소화
  │
  ▼
STEP 4: wait_event_composition
  - 이벤트 구성 패턴 분석 실행 (_analyze_event_composition)
  - 필수/선택적/추가가능 이벤트 분류 후 사용자 답변 수신
  - 사용자 선택 파싱 → events_to_remove / events_to_add 결정
  │
  ▼
STEP 5: done
  - 파이프라인 실행 (_run_event_pipeline)
```

---

## LLM 연동 (Claude CLI)

### 우선순위 탐색 순서
1. `%APPDATA%\npm\claude.cmd` → Claude CLI (최우선)
2. Anthropic API 키 존재 시 → Anthropic SDK
3. Ollama 서버 응답 시 → Ollama
4. 없으면 → 규칙 기반 폴백 (키워드 하드코딩 풀 사용)

### Claude CLI 호출 방식
```python
cmd = ["cmd", "/c", r"%APPDATA%\npm\claude.cmd"]
result = subprocess.run(cmd + ["-p", prompt], capture_output=True, text=True, timeout=60)
```

### 키워드 생성 프롬프트 구조
```
{genre} 게임의 이벤트 기획 키워드를 생성하세요.
반드시 JSON 형식으로만 응답하세요:
{
  "genre_keywords": ["키워드1", ...],  // 15개
  "season_keywords": ["키워드1", ...]   // 7개
}
```

---

## 키워드 블랙리스트 필터링

`scripts/generate_event_names.py`의 `_is_valid_keyword()` 함수가 모든 키워드를 검증한다.

### 블랙리스트 (정확 매칭)
```python
_KW_BLACKLIST = {
    "이벤트", "시즌", "보상", "미션", "대회", "경기", "대결",
    "선수", "챌린지", "클럽", "모임", "대전", "단전", "경기대회", "선수상"
}
```

### 블랙리스트 접미사 (suffix 매칭)
```python
_KW_BLACKLIST_SUFFIX = ("대회", "경기", "대결", "대전", "단전", "클럽", "모임")
```

### 유효 키워드 조건
- 영문자만 포함된 단어 제외
- 블랙리스트 정확 매칭 제외
- 블랙리스트 접미사로 끝나는 단어 제외
- 최소 2글자 이상
- 조건 통과한 키워드만 이벤트 제목에 사용

### 폴백 하드코딩 풀

| 장르 | 대표 키워드 |
|------|-------------|
| 야구 | 올스타, 전반기 결산, 순위 경쟁, 우승 도전, 끝내기 홈런, 퍼펙트게임 ... |
| 축구 | 이적 시장, 챔피언스리그, 골든부트, 베스트 11 ... |
| MMORPG | 신규 클래스, 레이드, 장비 강화, 길드전 ... |
| 캐주얼 | 신규 스테이지, 협동 이벤트, 한정 스킨 ... |

---

## 탭 생성 파이프라인 (`scripts/create_tabs.py`)

### 실행 흐름
```
1. 참조 탭(ref_tab) 복사 → 신규 탭(ws_new) 생성
2. apply_replacements() — 날짜/텍스트 치환 (하이라이트 없음)
3. _find_all_prev_same_type_ws() — 동일 타입 이력 탭 전체 수집
4. apply_balanced_rewards() — 보상 패턴 분석 및 자동 변경
5. highlight_reward_diffs() — 변경된 보상 셀 하이라이트 (연주황 FFD966)
6. _remove_event_sections() — 사용자가 제거 요청한 이벤트 섹션 삭제
7. _add_event_sections() — 사용자가 추가 요청한 이벤트 섹션 이력에서 복사
```

### CLI 호출 형식
```bash
python scripts/create_tabs.py \
    {source} {output} {new_tabs} [{ref_tabs}] \
    [--remove-events "이벤트명1,이벤트명2"] \
    [--add-events "이벤트명1,이벤트명2"]
```

---

## 보상 자동 변경 패턴

### A타입 / B타입 탭 구분

| 구분 | 판별 기준 | 예시 이벤트 |
|---|---|---|
| A타입 | 보상 아이템 열(ic) ≤ 4 또는 포인트레이스·룰렛이벤트·빙고이벤트 포함 | 포인트레이스, 룰렛이벤트, 빙고이벤트 |
| B타입 | 보상 컬럼 쌍 겹침 ≥ 3개 | 출석이벤트, 미션이벤트, 응모권이벤트 |

### 동일 타입 이력 탭 수집 (`_find_all_prev_same_type_ws`)
- B타입: 참조 탭과 컬럼 시그니처 3개 이상 겹치는 이전 탭
- A타입 폴백: A타입 컬럼 쌍(ic≤4) 1개 이상 겹치는 이전 탭

### 보상 변경 로직 (`apply_balanced_rewards`)

섹션 단위로 nth 동일 컬럼 쌍을 매핑하여 비교한다 (섹션 오염 방지).

| 상황 | 처리 |
|---|---|
| 이전 탭과 아이템이 다름 | 이전 탭 아이템으로 교체 + 이전 수량 적용 |
| 이전 탭과 아이템이 같음 | 이전 수량 방향으로 ±5% 소폭 조정 |
| 변경량 = 0 (동일 수량) | ±3% 결정적 조정 (짝수행 +3%, 홀수행 -3%) |
| 이력 없는 신규 섹션(갭) | ±3% 결정적 조정 |
| 최솟값 보장 | 모든 수량 `max(1, new_q)` |

```python
# 섹션 정렬 비교 예시
col_pair_counter = {}  # (ic, qc) → nth 등장 횟수
# 참조 탭에서 nth번 등장하는 (ic, qc) 쌍 → 이전 탭에서도 nth번 쌍과 매핑
```

### 보상 셀 하이라이트 (`highlight_reward_diffs`)
- 기준: 신규 탭을 참조 탭(ref_snap)과 비교
- 변경된 보상 셀에만 연주황(FFD966) 배경색 적용
- 날짜·텍스트 변경 셀에는 하이라이트 없음

```python
FILL_REWARD = PatternFill(start_color="FFD966", end_color="FFD966", fill_type="solid")
```

---

## 이벤트 구성 패턴 분석 (`server.py`)

### `_analyze_event_composition()` 동작
1. 참조 탭의 이벤트 타입 목록 추출 (B열 기준)
2. 동일 타입 이력 탭 2개 이상 수집 (부족 시 분석 스킵)
3. 전체 등장 빈도 계산

### 이벤트 분류 기준

| 분류 | 기준 | 화면 표시 |
|---|---|---|
| 필수 이벤트 | 100% 등장 | 📋 매 주기 포함 |
| 선택적 이벤트 | 등장률 < 100%, 현재 참조 탭에 있음 | ⚠️ 가끔 빠짐 |
| 추가 가능 이벤트 | 과거 등장, 현재 참조 탭에 없음 | 💡 추가 여부 질문 |

### STEP 4 사용자 답변 파싱 규칙

| 사용자 입력 예시 | 처리 결과 |
|---|---|
| "모두 진행" / "그대로" / "그대로 진행" | 선택적 이벤트 전부 유지 |
| "pvp 이벤트만 진행" | PvP 제외 나머지 선택적 이벤트 제거 |
| "모두 적용" / "전부 추가" | 추가 가능 이벤트 전부 추가 |
| 특정 이벤트명 언급 | 해당 이벤트만 추가 |

### 이벤트 섹션 조작

#### `_b_val_to_etype(val)` — B열 값 → 이벤트 유형 변환 헬퍼

B열에는 `"이벤트 제목 : 얼리썸머의 오더 경쟁 이벤트!"` 같은 전체 텍스트가 저장된다.
이를 `"오더경쟁이벤트"` 같은 유형명으로 변환하는 헬퍼 함수.

```python
# 변환 예시
"이벤트 제목 : 얼리썸머의 오더 경쟁 이벤트!" → 오더경쟁이벤트
"이벤트 제목 : 시즌 쿠폰 이벤트"           → 쿠폰이벤트
"이벤트 제목 : PvP 핫타임 이벤트"          → PvP이벤트
"06.25_ Event"                          → 기타 (탭 헤더 — 섹션 아님)
"∎ 진행 기간 : ..."                       → 기타 (섹션 내용 — 섹션 시작 아님)

# 내부 처리 순서
parse_section_title(val)   # "이벤트 제목 :" 파싱 → 제목 텍스트 추출
    → detect_event_type()  # EVENT_TYPE_MAP 키워드 매칭 → 유형명 반환
```

> ⚠️ **주의**: 이전 코드는 B열 raw 값을 유형명(`"오더경쟁이벤트"`)과 직접 비교했기 때문에 항상 매칭 실패 → 제거/추가가 동작하지 않았음. 반드시 `_b_val_to_etype()` 변환 후 비교해야 한다.

**제거** (`_remove_event_sections`):
- B열 값을 `_b_val_to_etype()`으로 변환 → 이벤트 유형명 비교
- `"기타"` 반환 행은 섹션 시작이 아님 (진행기간, 내용 등)
- 역순으로 행 블록 삭제 (행 번호 밀림 방지)
- 섹션 탐지 결과 및 삭제 행 범위를 콘솔에 출력

**추가** (`_add_event_sections` + `_find_event_section_in_history`):
- 이력 탭을 최신순으로 탐색하여 해당 이벤트 유형 섹션 탐색
- 이력 탭 B열도 `_b_val_to_etype()`으로 변환 후 비교
- 발견 시 스타일(font, fill, border, alignment) 포함 복사 → 신규 탭 끝에 추가
- 탐색 결과(성공/실패)를 콘솔에 출력

---

## 이벤트 명칭 자동 갱신 (`scripts/generate_event_names.py`)

### STABLE / CHANGEABLE 기반 처리

```
소스 xlsx 전체 날짜형 탭 스캔
    ↓
_get_base_pattern()으로 시즌 키워드 제거 → 기본 패턴 추출
    ↓
기본 패턴별 실제 제목 변형 집계
    ↓
변형 1개 → STABLE (절대 변경 안 함)
변형 2개↑ → CHANGEABLE → 키워드 교체 or 시즌 접두어 삽입
```

| 상황 | 처리 |
|------|------|
| STABLE 제목 | 항상 유지 (포인트레이스, 빙고이벤트 등) |
| CHANGEABLE + 시즌 키워드 감지 | 키워드를 대상 월 키워드로 교체 |
| CHANGEABLE + 시즌 키워드 없음 + 월 다름 | `N. 시즌키워드 텍스트` 형식으로 접두어 삽입 |
| CHANGEABLE + 같은 달 | 변경 안 함 |

---

## 전체 파이프라인 실행 흐름

```
[STEP 1~4: 대화 수집 완료]
    │
    ▼
1. generate_event_names.py
   - 이벤트 제목 패턴 생성
   - 블랙리스트 필터링 적용
    │
    ▼
2. create_tabs.py
   - 참조 탭 복사
   - 날짜/텍스트 치환
   - 보상 패턴 자동 변경 + 하이라이트
   - 이벤트 섹션 제거/추가 적용
    │
    ▼
3. scan_rewards_by_event.py
   - 신규 탭 보상 스캔
    │
    ▼
4. recommend_rewards.py
   - 보상 추천 생성 (이력 기반)
    │
    ▼
5. save_learning.py
   - 학습 데이터 누적
```

---

## 산출물 경로 요약

| 파일 | 경로 |
|---|---|
| 에이전트 입력 | `output/handoff/event-planner_input.json` |
| 이벤트 명칭 설정 | `output/event-planner/work/event_names_config.json` |
| 보상 이력 패턴 | `output/event-planner/work/reward_by_event.json` |
| 최종 xlsx | `output/event-planner/file/이벤트기획_{YYYYMMDD}.xlsx` |
| 학습 데이터 | `output/learnings/learnings.json` |
| 인사이트 리포트 | `output/learnings/insights.md` |
| 개선 이력 | `output/learnings/improvement_log.jsonl` |

---

## 서버 접속 정보

| 환경 | 주소 |
|---|---|
| 로컬 | `http://localhost:5050` |
| 사내망 | `http://{내부IP}:5050` |
| 포트 | TCP 5050 (Windows 방화벽 인바운드 허용 설정됨) |

---

## 에스컬레이션 기준

- 소스 파일 경로 없음 또는 접근 불가
- create_tabs.py 탭 생성 실패
- Claude CLI / Anthropic / Ollama 모두 응답 없음 (키워드 폴백 사용)
- 이벤트 구성 추가 대상 섹션을 이력 탭에서 찾을 수 없음

에스컬레이션 시 PM에게 오류 원인과 필요한 조치를 명시해 보고한다.

---

## 🧠 자기학습 시스템

### 학습 수집 (매 작업 완료 시 자동 실행)

```
[작업 완료]
    │
    ▼
[L1] 세션 데이터 수집
    - 입력: genre, market, new_tabs, ref_tabs, keywords
    - 결과: success/fail, 실행 시간, 오류 메시지
    │
    ▼
[L2] 패턴 학습
    ├─ 장르별 키워드 풀 업데이트
    ├─ 참조 탭 패턴 기록
    ├─ 오류 유형 카운트 누적
    └─ 보상 기준선 업데이트
    │
    ▼
[L3] 개선 제안 자동 도출
    │
    ▼
[L4] 저장 → output/learnings/
```

### 자동 개선 조건

| 조건 | 조치 |
|---|---|
| 동일 오류 3회 이상 | 개선 제안 → 프론트엔드 알림 |
| 장르 키워드 20개 이상 누적 | 자동 추천 활성화 |
| 평균 실행 시간 120초 초과 | 최적화 제안 |
| 파이프라인 성공 10회 | 인사이트 리포트 자동 갱신 |
