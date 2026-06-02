# 빠른 참조 가이드 (Quick Reference)

---

## 서버 실행

```
run.bat
# 또는
python server.py
# 접속: http://localhost:5050
```

---

## 탭 생성 CLI (직접 실행)

```bash
# 기본: 소스, 출력, 새탭명, 참조탭명
python scripts/create_tabs.py [source.xlsx] [output.xlsx] [new_tab] [ref_tab]

# 예시: 260618 기반으로 260625 탭 생성
python scripts/create_tabs.py \
  output/gdrive_cache/source.xlsx \
  output/projects/event-planner/file/result.xlsx \
  "260625" \
  "260618"

# 다중 탭 (쉼표 구분)
python scripts/create_tabs.py ... "260625,260709" "260618,260625"
```

---

## 이벤트 제목 생성 CLI

```bash
python scripts/generate_event_names.py \
  --source output/gdrive_cache/source.xlsx \
  --new-tabs "260625,260709" \
  --ref-tabs "260611,260618" \
  --target-month "2026-07" \
  --genre "야구" \
  --phrases "올스타,전반기,7월의" \
  --work-dir output/projects/event-planner/work
```

---

## 파이프라인 실행 순서 (반드시 이 순서 준수)

1. `generate_event_names.py` → `event_names_config.json` 생성
2. `create_tabs.py` → 위 config를 읽어서 xlsx 생성

---

## 주요 파일 경로

| 파일 | 경로 |
|------|------|
| 활성 프로젝트 설정 | `output/json/current_project.json` |
| 이벤트 제목 설정 | `output/projects/event-planner/work/event_names_config.json` |
| 소스 xlsx 캐시 | `output/gdrive_cache/*.xlsx` |
| 최종 출력 | `output/projects/event-planner/file/*.xlsx` |

---

## SEASON_PATTERNS 감지 대상

| 패턴 | 예시 |
|------|------|
| `\d+월\s*이달의` | 6월 이달의 |
| `\d+월의` | 7월의 |
| `(얼리썸머\|초여름\|쿨서머\|한여름\|늦여름)(의)?` | 한여름의 |
| `(봄\|여름\|가을\|겨울)(의)` | 여름의 |
| `(설날\|크리스마스\|추석\|핼러윈)` | 크리스마스 |
| `(전반기\|후반기\|포스트시즌\|...)` | 전반기 |
| `\d+주년` | 1주년 |

---

## 월별 기본 시즌 키워드 (MONTH_SEASON_FALLBACK)

| 월 | 기본 키워드 |
|----|------------|
| 1월 | 1월의, 신년 |
| 2월 | 2월의, 봄의 |
| 3~4월 | 봄의 |
| 5월 | 5월의, 황금연휴 |
| 6월 | 얼리썸머, 초여름 |
| 7월 | 7월의, 여름의 |
| 8월 | 여름의, 한여름 |
| 9월 | 가을의, 추석 |
| 10월 | 10월의, 핼러윈 |
| 11~12월 | 11월의, 크리스마스 |

---

## 경고 셀 확인 방법

```python
python -c "
import openpyxl, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import re
wb = openpyxl.load_workbook('output.xlsx')
ws = wb['260625']
date_re = re.compile(r'\d{2}[./]\d{2}')
for row in ws.iter_rows():
    for cell in row:
        if isinstance(cell.value, str) and date_re.search(cell.value):
            print(f'{cell.coordinate}: {cell.value[:80]}')
"
```

---

## API 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/event/tabs` | 소스 xlsx 탭 목록 조회 |
| POST | `/api/event/create-tabs` | 탭 생성 실행 |
| GET/POST | `/api/event/scan-rewards` | 보상 스캔 |
| POST | `/api/event/recommend-rewards` | 보상 추천 |
| POST | `/api/pm/chat` | PM 에이전트 채팅 |
| POST | `/api/agent/chat` | 이벤트 플래너 에이전트 채팅 |
