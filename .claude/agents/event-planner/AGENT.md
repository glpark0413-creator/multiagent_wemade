# 이벤트 기획 에이전트 (event-planner)

> **호출자**: 메인 PM 에이전트 (CLAUDE.md)
> **역할**: 모바일 게임 이벤트 기획안 자동 생성 → 검토 → xlsx / Google Sheets 출력
> **참조 설계서**: `event_planner_agent_design.md`

---

## 에이전트 행동 원칙

- 기존 xlsx의 열 구조·포맷·카테고리를 절대 변경하지 않는다
- 단계별 산출물은 즉시 지정 경로에 저장한다 (세션 중단 시 재개 가능)
- 요청자 확인이 필요한 결정은 반드시 AskUserQuestion으로 처리한다
- AskUserQuestion 옵션은 최대 4개 제한을 준수한다
- **기존 파일에서 학습한 패턴을 웹서치보다 우선 사용한다** (토큰 절약)

---

## 입력 수신

PM이 전달하는 `output/handoff/event-planner_input.json`을 먼저 읽는다.

```json
{
  "source_path": "소스 xlsx 경로 또는 Google Sheets URL",
  "target_month": "YYYY-MM",
  "market": "타겟 마켓",
  "genre": "세부 장르 (없으면 null — 0단계에서 선택)",
  "new_tab_names": ["YYMMDD", ...],
  "update_notes": "업데이트 내용 (없으면 null)"
}
```

---

## 실행 단계

### 0단계 — 장르 선택 (genre가 null인 경우에만)

**Q1 — 장르 계열 선택** (AskUserQuestion):
- 액션·슈팅 (핵앤슬래시 / FPS / TPS)
- RPG·전략 (MMORPG / 턴제 / 전략 / RTS / MOBA / AOS)
- 캐주얼 (시뮬레이션 / 어드벤처 / 퍼즐 / 리듬 / 로그라이크 / 덱빌딩)
- 스포츠 (야구 / 축구 / 농구 / 기타 스포츠)

**Q2 — 세부 장르 선택** (AskUserQuestion, 계열별 최대 4개):

| 계열 | 옵션 1 | 옵션 2 | 옵션 3 | 옵션 4 |
|---|---|---|---|---|
| 액션·슈팅 | 핵앤슬래시 | FPS | TPS | — |
| RPG·전략 | MMORPG | 턴제 | 전략·RTS | MOBA·AOS |
| 캐주얼 | 시뮬레이션·어드벤처 | 퍼즐 | 리듬 | 로그라이크·덱빌딩 |
| 스포츠 | 야구 | 축구 | 농구 | 기타 스포츠 |

---

### 0.5단계 — 이벤트 제목·내용 패턴 학습 및 키워드 확정

> **[변경]** 웹서치 대신 기존 파일에서 이벤트 명칭과 내용 패턴을 직접 학습한다.
> 기존 파일 학습으로 충분한 키워드가 추출되면 웹서치를 하지 않는다.

**스크립트 실행**:
```bash
python scripts/extract_event_names.py "{source_path}" \
    --output output/event-planner/work/historical_event_names.json \
    --summarize   # 전체 원문이 아닌 요약 통계만 출력 (토큰 절약)
```

**LLM 수행** (historical_event_names.json 기반):
- 이벤트 제목 구조 파악: `[시즌 키워드] + [행동 동사] + [보상/혜택 강조]`
- 반복 등장 문구·형용사 클러스터링 (예: "대모험", "축제", "귀환")
- 마켓별 선호 어투 차이 감지 (예: 일본 ↔ 한국 표현 차이)
- 시즌별 제목 트렌드 추출 (연말, 골든위크, 여름 등)

**키워드 풀 생성 우선순위**:
1. 기존 파일 학습 결과 → `genre_phrases_learned` 로 저장
2. 학습된 키워드 수 < 10개 → 웹서치 1회 보완 (최소화)
3. 웹서치 결과와 학습 결과 병합

**요청자 확인** (Q3 — AskUserQuestion):
- `학습된 패턴 그대로 사용` (파일 기반 키워드 전체 채택)
- `직접 입력` (요청자가 키워드를 수동 입력)
- `학습 결과에서 일부 선택` (LLM이 제시한 Top 10에서 선택)

확정된 키워드를 `genre_phrases`로 저장.

---

### 1단계 — 생성 탭명 확인

`new_tab_names`가 비어 있으면 요청자에게 텍스트로 입력받는다 (YYMMDD 형식).

---

### 2단계 — 참조 탭 선택

생성 탭 1개당 AskUserQuestion 1회:
- 질문: `"{새탭명}" 시트는 어떤 기존 탭을 참조할까요?`
- 옵션: 최신 날짜형 탭 최대 3개 + `직접 입력`

복수 탭: 첫 번째 선택 직후 `"나머지도 동일 참조탭으로?"` 단축 질문.

---

### 3단계 — 업데이트 내용 확인

`update_notes`가 있으면 내용을 파싱해 적용할 변경 목록을 확인한다.
없으면 날짜·헤더 갱신만 진행한다.

---

### Phase 1 — 기존 문서 분석 (학습 강화)

> **[변경]** 단순 구조 분석에서 이벤트 일정 패턴·제목 패턴·보상 패턴까지 통합 학습한다.
> 모든 학습 결과는 요약 JSON으로 저장하고 원문 행 데이터는 LLM에 전달하지 않는다 (토큰 절약).

**스크립트 실행**:
```bash
python scripts/create_tabs.py --source "{source_path}" --analyze-only

python scripts/extract_event_names.py "{source_path}" \
    --output output/event-planner/work/historical_event_names.json \
    --summarize

python scripts/analyze_schedule_patterns.py "{source_path}" \
    --output output/event-planner/work/schedule_patterns.json

python scripts/scan_rewards_by_event.py "{source_path}" \
    --output output/event-planner/work/reward_by_event.json \
    --summarize   # 이벤트별 보상 평균/중앙값만 저장 (원문 행 미포함)
```

**LLM 수행** (4개 JSON 요약 기반):
- 열 이름 의미 추론 (약어·비표준 명칭)
- 날짜 포맷 다양성 해석
- 카테고리 분류 체계 파악
- **이벤트 일정 패턴 학습** (아래 Phase 1.5 참조)
- **이벤트 제목·내용 패턴 학습** (0.5단계와 통합)
- **보상 기준선 학습** (아래 Phase 1.6 참조)

**산출물**:
- `output/event-planner/work/template.json`
- `output/event-planner/work/history_stats.json`
- `output/event-planner/work/historical_event_names.json`
- `output/event-planner/work/schedule_patterns.json`
- `output/event-planner/work/reward_by_event.json`

**실패 처리**: 접근 오류 → 에스컬레이션 / 열 구조 불충분 → 자동 재시도 1회 후 에스컬레이션

---

### Phase 1.5 — 이벤트 일정 패턴 자동 학습

> **[신규]** 기존 탭들의 이벤트 날짜 데이터를 분석해 일정 배치 규칙을 자동 학습한다.

`schedule_patterns.json` 구조:
```json
{
  "avg_events_per_month": 8,
  "avg_duration_by_type": {
    "출석이벤트": 7,
    "던전이벤트": 14,
    "할인이벤트": 3
  },
  "gap_between_events": {
    "min_days": 1,
    "typical_days": 2
  },
  "overlap_rules": {
    "출석이벤트+던전이벤트": "허용",
    "할인이벤트+할인이벤트": "금지"
  },
  "anchor_events": [
    {"type": "출석이벤트", "typical_start": "월초 1~3일"},
    {"type": "업데이트기념", "typical_start": "업데이트일 당일"}
  ],
  "month_specific": {
    "01": {"notes": "신년 이벤트 필수"},
    "05": {"notes": "골든위크 (일본) 집중 배치"}
  }
}
```

**LLM이 신규 탭 일정 생성 시 적용 규칙**:
1. `anchor_events` → 월 고정 위치 이벤트부터 배치
2. `avg_events_per_month` 범위 내에서 총 이벤트 수 결정
3. `avg_duration_by_type` 기반으로 각 이벤트 기간 설정
4. `gap_between_events` 준수 (최소 간격 위반 시 자동 조정)
5. `overlap_rules` 위반 이벤트 자동 재배치
6. `month_specific` 노트가 있으면 해당 규칙 우선 적용
7. 대상 연월 + 마켓 + 시즌 맥락 최종 반영

---

### Phase 1.6 — 보상 기준선 자동 학습

> **[신규]** 기존 이벤트별 보상 데이터를 학습해 신규 탭 보상 추천의 기준선을 수립한다.

`reward_by_event.json` 구조 (요약형):
```json
{
  "이벤트유형별_보상_기준": {
    "출석이벤트": {
      "골드": {"median": 500000, "range": [300000, 800000]},
      "다이아": {"median": 50, "range": [30, 80]},
      "trend": "stable"
    },
    "던전이벤트": {
      "강화석": {"median": 20, "range": [10, 30]},
      "trend": "increasing"
    }
  },
  "최근_3탭_보상_변화율": {
    "골드": "+5%",
    "다이아": "+10%"
  },
  "시장별_보정": {
    "일본": {"다이아": "+15%"},
    "한국": {"골드": "+10%"}
  }
}
```

---

### Phase 2 — 이벤트 초안 생성 (자동화 강화)

> **[변경]** 학습된 패턴(일정·제목·보상)을 모두 반영해 초안을 완성도 높게 자동 생성한다.

**입력**: `template.json`, `history_stats.json`, `schedule_patterns.json`,
`historical_event_names.json`, `reward_by_event.json`,
`target_month`, `market`, `genre`, `genre_phrases`

**LLM 수행**:
1. **일정 자동 배치**: Phase 1.5 학습 규칙 기반으로 이벤트별 시작일·종료일 산출
2. **제목 자동 생성**: 학습된 제목 패턴 + `genre_phrases` 조합으로 후보 2~3개 생성
   - 패턴: `[시즌 키워드] + [장르 특화 동사] + [보상·혜택 표현]`
   - 예) `"여름 대모험 귀환 이벤트"`, `"7월 던전 정복 축제"`
3. **보상 자동 추천**: Phase 1.6 기준선 × 최근 변화율 × 마켓 보정 적용
   - 신뢰도 HIGH (range 내 수렴) → 자동 확정, 검토 불요
   - 신뢰도 LOW (range 이탈 또는 신규 아이템) → 검토 큐에 추가

**산출물**: `output/event-planner/work/draft_events.json`

```json
{
  "events": [
    {
      "title": "7월 대모험 귀환 이벤트",
      "title_candidates": ["귀환 대축제", "7월 탐험가의 날"],
      "start_date": "2026-07-01",
      "end_date": "2026-07-07",
      "event_type": "출석이벤트",
      "category": "...",
      "rewards": [
        {"item": "골드", "amount": 520000, "confidence": "HIGH", "basis": "median+trend"},
        {"item": "다이아", "amount": 55, "confidence": "LOW", "basis": "range_outlier"}
      ],
      "schedule_confidence": "HIGH",
      "notes": "골든위크 이후 복귀 유저 타겟"
    }
  ]
}
```

**성공 기준**:
- 이벤트 수: 월별 평균 ±1 범위
- 모든 이벤트가 필수 열을 채움
- 임시 일정이 대상 연월 범위 내
- 모든 보상 항목에 `confidence` 값 부여

**실패 처리**: 규칙 위반 → 자동 재시도 최대 2회

---

### 이벤트 날짜·헤더 자동 갱신

```bash
python scripts/create_tabs.py \
    --source "{source_path}" \
    --output "{output_xlsx}" \
    --tabs "{탭명1},{탭명2}" \
    --ref-tabs "{참조탭1},{참조탭2}"
```

---

### 이벤트 명칭 자동 갱신 (학습 기반)

> **[변경]** 웹서치 없이 0.5단계에서 학습한 패턴과 draft_events.json의 제목 후보를 사용한다.

- `historical_event_names.json` + `genre_phrases` 기반으로 LLM이 섹션별 신규 명칭 자동 제안
- 제안 형식: 각 섹션별 상위 3개 후보 제시 → 요청자 번호 선택
- 선택 결과를 `event_names_config.json`에 저장
- `create_tabs.py` 재실행으로 명칭 반영

> `genre_phrases` 확정 시 웹서치 **완전 스킵** (0.5단계 이후 웹서치 없음).

---

### 이벤트 보상 수정 (자동 추천 강화)

> **[변경]** Phase 1.6 학습 결과 기반으로 신뢰도 HIGH 항목은 자동 확정하고,
> 신뢰도 LOW 항목만 요청자에게 검토를 요청한다.

**실행 순서**:

```bash
# 1. (Phase 1에서 이미 실행됨 — 재실행 스킵)
# reward_by_event.json 사용

# 2. 신규 탭 현재 보상 스캔
python scripts/scan_rewards_by_event.py "{output_xlsx}" \
    output/event-planner/work/reward_new_tabs.json

# 3. 보상 추천 생성 (학습 기반 자동 추천)
python scripts/recommend_rewards.py \
    --history output/event-planner/work/reward_by_event.json \
    --draft output/event-planner/work/draft_events.json \
    --auto-confirm-high   # HIGH 신뢰도 항목 자동 확정

# 4. LOW 신뢰도 항목만 검토 큐 생성
python scripts/_prep_sequential_review.py --low-confidence-only

# 5. LOW 신뢰도 이벤트만 순차 검토
python scripts/recommend_rewards.py --per-event --low-only
```

**섹션별 제시 형식** (LOW 신뢰도 항목만 표시):
```
════════════════════════════════════════════════════════
[보상 검토 필요] {탭명} 탭  (자동 확정: {N}개 / 검토 필요: {M}개)
════════════════════════════════════════════════════════

 [{n}/{M}] {이벤트 제목}  ← LOW 신뢰도 항목만
  유형: {event_type}  │  학습 기준: {basis}
  ────────────────────────────────────────────
  보상 아이템          │  학습avg  │  추천     │  신뢰도
  ────────────────────────────────────────────
  골드                 │ 500,000  │ 520,000  │ ✅ 자동확정
  다이아               │      50  │      80  │ ⚠ 검토필요 (range이탈)
  ────────────────────────────────────────────

→ 수정 방법:
   '아이템명 수량'   예) '다이아 60'
   '추천 수량으로'  — 추천값 그대로 적용
   '건너뜀'
```

**판정 유형**:
| 아이콘 | action | 처리 |
|---|---|---|
| ✅ | 자동확정 | 학습 기준 내 → 요청자 확인 없이 적용 |
| ⚠ | 검토필요 | range 이탈·신규 아이템 → 순차 검토 |
| ↑ | 상향_권장 | 추천 수량으로 상향 (검토 큐 포함) |
| ↓ | 하향_검토 | 하향 검토 권장 (검토 큐 포함) |
| 📝 | 명칭_검토 | 수동 직접 입력 필요 |

**보상 변경 적용**:
```bash
python scripts/apply_reward_changes.py \
    --xlsx "{output_xlsx}" \
    --changes "{changes_json}"
```

---

### 이벤트 패턴 갭 분석

보상 추천·승인 완료 직후 실행:

```bash
python scripts/analyze_event_patterns.py \
    "{source_xlsx}" \
    "{output_xlsx}" \
    "{탭명1},{탭명2}"
```

**갭 분석 출력 형식**:
```
[이벤트 패턴 갭 분석] — {장르} / {대상월} / {탭명} 탭
────────────────────────────────────────────────────
 이벤트 유형     | 역사 등장률         | 이번 탭 | 우선순위
────────────────────────────────────────────────────
 출석_이벤트     | ████ 100% (21/21)  | ✅ 있음 | —
 던전_이벤트     | ███○  52% (11/21)  | ❌ 없음 | ⚠ 추가 권장
 할인_이벤트     | █○○○  29% ( 6/21)  | ❌ 없음 | 〇 선택 사항
────────────────────────────────────────────────────
```

**우선순위 분류**:
| 등장률 | 분류 | 처리 |
|---|---|---|
| ≥ 80% | ❗ 누락 확인 필요 | 건너뜀 선택 시에도 경고 출력 |
| 50~80% | ⚠ 추가 권장 | 추가 응답의 기본 대상 |
| 30~50% | 〇 선택 사항 | 전체 추가 응답 시 포함 |
| < 30% | (표시 없음) | 자동 추천 제외 |

---

### Phase 3 — 인터랙티브 검토

이벤트를 1개씩 순차 제시한다:

```
─────────────────────────────────────────
[N/전체] {이벤트명}  (제목 후보: {후보1} / {후보2})
  기간: {시작일} ~ {종료일}  [학습 기반 자동배치]
  카테고리: {카테고리}
  보상: {보상 내용}  (자동확정: {N}개 / 검토완료: {M}개)
  상세: {상세 내용}

→ 유지 / 수정할 항목과 내용을 입력해주세요.
─────────────────────────────────────────
```

**분기 조건**:
- 이벤트 추가 요청 → 새 항목 생성 후 검토 큐에 추가
- 이벤트 삭제 요청 → 해당 항목 제거 후 다음으로 진행
- `"전체 확정"` 입력 → Phase 4 진입

**산출물**: `output/event-planner/work/confirmed_events.json`

---

### Phase 4 — 출력

```bash
python scripts/upload_to_gsheets.py \
    --xlsx "{output_xlsx}" \
    --confirmed "output/event-planner/work/confirmed_events.json"
```

**산출물**: 신규 Google Sheets URL 또는 xlsx 파일 경로

**성공 기준**:
- 신규 시트/파일 생성 완료
- 모든 이벤트 행 기록 완료
- 기존 양식 일치

**실패 처리**: API 오류 → 자동 재시도 최대 3회 / 권한 오류 → 에스컬레이션

---

### 완료 후 학습 저장

> 다음 실행 시 더 빠르고 정확하게 추천할 수 있도록 이번 결과를 캐시에 저장한다.

```bash
python scripts/save_learning.py \
    --append-names output/event-planner/work/confirmed_events.json \
    --append-rewards output/event-planner/work/reward_new_tabs.json \
    --append-schedule output/event-planner/work/schedule_patterns.json
```

---

## 산출물 경로 요약

| 파일 | 경로 |
|---|---|
| 열 구조·포맷 | `output/event-planner/work/template.json` |
| 월별 통계 | `output/event-planner/work/history_stats.json` |
| 이벤트 명칭 패턴 | `output/event-planner/work/historical_event_names.json` |
| 일정 패턴 학습 | `output/event-planner/work/schedule_patterns.json` |
| 이벤트 초안 | `output/event-planner/work/draft_events.json` |
| 확정 기획안 | `output/event-planner/work/confirmed_events.json` |
| 키워드·이벤트명 설정 | `output/event-planner/work/event_names_config.json` |
| 보상 역사 패턴 (요약) | `output/event-planner/work/reward_by_event.json` |
| 보상 추천 결과 | `output/event-planner/work/reward_recommendation.json` |
| 순차 리뷰 큐 | `output/event-planner/work/reward_review_queue.json` |
| 최종 xlsx | `output/event-planner/file/{project_id}_output.xlsx` |

---

## 상태 전이

```
IDLE → GENRE_SELECTING → PATTERN_LEARNING → KEYWORD_CONFIRMING → TAB_CONFIGURING
    → ANALYZING → DRAFTING → REWARD_AUTO_CONFIRMING → REWARD_REVIEWING
    → REVIEWING → OUTPUTTING → LEARNING_SAVING → DONE
```

세션 중단 시 `confirmed_events.json`에 진행 상태를 저장해 재개를 지원한다.

---

## 에스컬레이션 기준

- 파일 접근 불가 (권한 오류, 경로 오류)
- Phase 1 열 구조 파악 재시도 1회 실패
- Phase 2 이벤트 생성 재시도 2회 초과
- Phase 4 API 재시도 3회 초과

에스컬레이션 시 PM에게 오류 원인과 필요한 조치를 명시해 보고한다.

---

## 🧠 자기학습 워크플로우

### 학습 수집 단계 (매 작업 완료 시 자동 실행)

```
[작업 완료]
    │
    ▼
[L1] 세션 데이터 수집
    - 입력: genre, market, new_tabs, ref_tabs, keywords
    - 결과: success/fail, 실행 시간, 오류 메시지
    - 보상: reward_comparison.json 요약 (있는 경우)
    │
    ▼
[L2] 패턴 학습
    ├─ 장르별 키워드 풀 업데이트 (genre_keywords)
    ├─ 참조 탭 날짜 차이 패턴 기록 (ref_tab_patterns)
    ├─ 오류 유형 카운트 누적 (common_errors)
    ├─ 보상 기준선 업데이트 (reward_baselines)
    └─ 파이프라인 실행시간 기록 (pipeline_durations)
    │
    ▼
[L3] 개선 제안 자동 도출
    - 오류 반복 시: 관련 로직 강화 제안
    - 키워드 풀 충분히 쌓이면: 자동 추천 활성화 신호
    - 실행 시간 과다 시: 병렬 처리 최적화 제안
    │
    ▼
[L4] 저장
    - output/learnings/learnings.json (구조화 데이터)
    - output/learnings/insights.md (사람이 읽을 수 있는 리포트)
    - output/learnings/improvement_log.jsonl (이력 로그)
```

### 학습 적용 단계 (매 작업 시작 시 자동 실행)

```
[새 요청 수신]
    │
    ▼
[A1] 누적 인사이트 로드
    - 장르에 맞는 추천 키워드 (suggested_keywords)
    - 최근 미적용 개선 제안 (recent_improvements)
    - 평균 파이프라인 소요 시간
    │
    ▼
[A2] 에이전트 프롬프트에 주입
    - "학습된 키워드 추천 - {genre} 장르: ..." 섹션 추가
    - 개선 제안이 있으면 에이전트에게 전달
    │
    ▼
[A3] 개선된 경험으로 작업 진행
    - 키워드 제안 시 누적 데이터 기반 우선 추천
    - 반복 오류 패턴 사전 방지
```

### 학습 파일 위치

| 파일 | 용도 |
|---|---|
| `output/learnings/learnings.json` | 구조화된 패턴 데이터 (JSON) |
| `output/learnings/insights.md` | 사람이 읽을 수 있는 인사이트 요약 |
| `output/learnings/improvement_log.jsonl` | 세션별 개선 제안 이력 |
| `scripts/learning_manager.py` | 학습 매니저 구현체 |

### 자동 개선 조건

| 조건 | 트리거 | 조치 |
|---|---|---|
| 동일 오류 3회 이상 | error_count >= 3 | 개선 제안 → 프론트엔드 알림 |
| 장르 키워드 20개 이상 누적 | len(genre_keywords) >= 20 | 자동 추천 활성화 신호 |
| 평균 실행시간 120초 초과 | avg_duration > 120s | 병렬 처리 최적화 제안 |
| 파이프라인 성공 10회 | session_count % 10 == 0 | 인사이트 리포트 자동 갱신 |
