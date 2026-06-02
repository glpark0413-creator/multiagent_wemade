# 세션 로그 — 2026-06-01

---

## 1. 세션 개요

| 항목 | 내용 |
|---|---|
| 날짜 | 2026-06-01 |
| 목적 | 이벤트 기획 멀티에이전트 시스템의 날짜/이벤트 제목 치환 버그 수정 |
| 작업 범위 | `scripts/create_tabs.py` 핵심 버그 수정 |
| 담당자 | glpark0413@wemadeplus.com |

---

## 2. 발견된 버그 목록 (상세)

### 버그 1: date_map이 문자열 셀에 미적용

- **위치**: `scripts/create_tabs.py` → `apply_replacements()` 함수
- **증상**: 생성된 xlsx 파일에서 날짜가 전혀 바뀌지 않음
- **원인**: `date_map`이 `datetime`/`date` 객체에만 적용되고, 문자열 셀(`"06/11(목) 09:00 ~ 06/24(수) 23:59"` 등)에는 적용되지 않음
- **영향 셀 예시**: B8, B30, C73, B128, C158, B218, B262 등

---

### 버그 2: 순차 치환 시 키 충돌

- **위치**: 버그 1 수정 과정에서 발견
- **증상**: `"06/11"→"06/25"` 치환 후 `"06/25"→"07/09"`가 또 적용되어 이중 치환 발생
- **예시**:
  - 원본: `"06/11(목) ~ 06/25(목)"`
  - 첫 번째 pass 후: `"06/25(목) ~ 06/25(목)"`
  - 두 번째 pass 후: `"07/09(목) ~ 07/09(목)"` ← 잘못된 결과
- **해결**: 단일 패스 regex substitution 사용 (`re.sub` with compiled pattern)

---

### 버그 3 (이전 세션 수정): _cli_main 이중 파싱

- **위치**: `scripts/create_tabs.py` → `_cli_main()`
- **원인**: `load_event_names_config()`가 이미 `{tab: [(old,new),...]}` 형태로 반환하는데, 코드가 `.get("event_name_replacements", {})`를 한 번 더 호출하여 항상 `{}` 반환
- **수정**: `enr = load_event_names_config() or {}` 로 직접 사용

---

### 버그 4 (이전 세션 수정): generate_event_names.py 미호출

- **위치**: `server.py` → `event_create_tabs()` (수동 UI 엔드포인트)
- **원인**: `event_names_config.json`을 생성하는 `generate_event_names.py`가 수동 탭 생성 경로에서 호출되지 않아 제목 치환 목록이 항상 비어 있음

---

## 3. 수정 내용 상세

### 3-1. import 추가 (create_tabs.py)

**수정 전**

```python
import io
import json
import sys
```

**수정 후**

```python
import io
import json
import re   # ← 추가
import sys
```

---

### 3-2. apply_replacements() 수정 (create_tabs.py)

**수정 전**

```python
if not isinstance(cell.value, str):
    continue

new_val = cell.value
for old, new in all_str_replacements:
    new_val = new_val.replace(old, new)
if new_val != cell.value:
    changed.append((cell.coordinate, cell.value, new_val))
    cell.value = new_val
```

**수정 후**

```python
if not isinstance(cell.value, str):
    continue

new_val = cell.value
for old, new in all_str_replacements:
    new_val = new_val.replace(old, new)
# date_map 을 문자열 셀에도 적용 — 단일 패스 regex 로 순서 충돌 방지
if date_map:
    # 슬래시 형식 (06/11 → 06/25)
    _slash_map = {k: v for k, v in date_map.items()}
    _slash_pat = re.compile("|".join(re.escape(k) for k in sorted(_slash_map, key=len, reverse=True)))
    new_val = _slash_pat.sub(lambda m: _slash_map[m.group(0)], new_val)
    # 점 형식 (06.11 → 06.25) — 헤더 셀 등
    _dot_map = {k.replace("/", "."): v.replace("/", ".") for k, v in date_map.items()}
    _dot_pat = re.compile("|".join(re.escape(k) for k in sorted(_dot_map, key=len, reverse=True)))
    new_val = _dot_pat.sub(lambda m: _dot_map[m.group(0)], new_val)
if new_val != cell.value:
    changed.append((cell.coordinate, cell.value, new_val))
    cell.value = new_val
```

**핵심 변경 포인트**

| 항목 | 내용 |
|---|---|
| 슬래시 형식 처리 | `06/11` 등 `MM/DD` 포맷 문자열을 `date_map` 기준으로 치환 |
| 점 형식 처리 | `06.11` 등 헤더 셀용 포맷도 자동 변환 |
| 단일 패스 regex | `re.compile` + `re.sub`로 전체 매핑을 한 번에 처리하여 이중 치환 방지 |
| 키 정렬 | `sorted(..., key=len, reverse=True)`로 긴 패턴 우선 매칭 |

---

## 4. 테스트 결과

### 테스트 1: 날짜 치환 (260618 → 260625, +7일)

| 셀 | 수정 전 | 수정 후 | 결과 |
|---|---|---|---|
| B3 | `06.18_ Event` | `06.25_ Event` | ✓ |
| C8 | `06/18(목) 09:00 ~ 06/25(목) 08:59` | `06/25(목) 09:00 ~ 07/02(목) 08:59` | ✓ |
| C58 | 동일 패턴 | 정상 치환 | ✓ |
| C88 | 동일 패턴 | 정상 치환 | ✓ |

---

### 테스트 2: 통합 테스트 (260611 → 260625, +14일)

#### 날짜 치환

| 셀 | 수정 전 | 수정 후 | 결과 |
|---|---|---|---|
| B3 | `06.11_ Event` | `06.25_ Event` | ✓ |
| B8 | `06/11(목) 09:00 ~ 06/24(수) 23:59` | `06/25(목) 09:00 ~ 07/08(수) 23:59` | ✓ |
| C13 (datetime) | `2026-06-11` | `2026-06-25` | ✓ |
| B30 | 날짜 포함 문자열 | 정상 치환 | ✓ |
| C73 | 날짜 포함 문자열 | 정상 치환 | ✓ |
| B128 | 날짜 포함 문자열 | 정상 치환 | ✓ |
| C158 | 날짜 포함 문자열 | 정상 치환 | ✓ |
| B218 | 날짜 포함 문자열 | 정상 치환 | ✓ |
| B262 | 날짜 포함 문자열 | 정상 치환 | ✓ |

#### 이벤트 제목 치환

| 셀 | 수정 전 | 수정 후 | 결과 |
|---|---|---|---|
| B6 | `6월 이달의 14일 출석 이벤트!` | `7월 이달의 14일 출석 이벤트!` | ✓ |
| B28 | `한여름의 그라운드 응모권 이벤트!` | `전반기의 그라운드 응모권 이벤트!` | ✓ |
| B156 | `6월 이달의 야구공 찾기 이벤트!` | `7월 이달의 야구공 찾기 이벤트!` | ✓ |

총 **13개 셀** 갱신 완료

---

## 5. 소스 파일 탭 목록

실제 소스 xlsx (나이트크로우) 탭 목록 (최신순):

```
260618, 260611, 260521, 260514, 260430, 260423, 260416,
260409~, 260402~, ...
```

> 260409 이전 탭은 한글 접미사 포함 형식

---

## 6. 이전 세션에서 수정된 내용 (요약)

| 파일 | 수정 내용 |
|---|---|
| `index.html` | 에이전트 수동 제어 섹션 제거 |
| `index.html` | 최근 산출물 섹션 제거 |
| `index.html` | 동적 탭 선택기 UI 추가 |
| `style.css` | 채팅창 높이 확장 |
| `app.js` | PM→에이전트 핸드오프 시 대화 컨텍스트 이어받기 |
| `app.js` | 에이전트 자동 시작 |
| `app.js` | 동적 탭 선택기 로직 추가 |
| `server.py` | 에이전트 자동 시작 처리 |
| `server.py` | `/api/event/tabs` 엔드포인트 추가 |

---

*이 파일은 세션 기록용 문서입니다. 실제 코드 변경 사항은 각 소스 파일을 참조하세요.*
