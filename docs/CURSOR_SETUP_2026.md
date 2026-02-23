# Cursor 2026 프로페셔널 세팅 가이드 — Health Map

헬스맵(Health Map) 아키텍처(KG 파이프라인, Neo4j, 다층 레이어 시각화)를 Cursor에서 가장 효율적으로 개발하기 위한 **에이전트 중심(Agentic Workflow)** 세팅입니다.

---

## 1. 추천 비용 및 플랜

| 옵션 | 비용 | 추천 |
|------|------|------|
| **Cursor Pro** | $20/월 | ✅ **가장 추천** |
| Claude Max | $100~$200 | 초기에는 비추천 |

**이유**: 2026년 Cursor는 **Agent Mode**와 **Parallel Agents**(최대 8개 동시 실행)를 제공하며, Pro 구독에서 가장 잘 맞습니다. 일반 채팅 위주보다 **에이전트 중심 워크플로우**가 이 규모의 프로젝트에 적합합니다.

**Max Mode**: Cursor 내 'Max Mode'는 할당량 초과 시 API 비용을 직접 지불하는 방식입니다. 초기에는 **Pro 플랜만으로 충분**합니다.

---

## 2. 핵심 파일 설정 (가장 중요)

### ① `.cursor/rules/project.mdc` (프로젝트 헌법)

이 프로젝트에는 이미 다음 내용이 반영된 **project.mdc**가 있습니다.

- **Zero-Error Tolerance**: "모든 추천은 반드시 source_id와 연결되어야 함" 명시.
- **DIKW Hierarchy**: 코드 구조는 Data(Fetch) → Information(Extract) → Knowledge(Ingest) 폴더/단계를 엄격히 따름.
- **Tech Stack**: Python, Neo4j, FastAPI, Next.js (App Router).
- **UI/UX**: Information = 파란색, Knowledge = 녹색, Wisdom = 금색 뱃지 사용.

규칙 수정이 필요하면 `.cursor/rules/project.mdc`를 직접 편집하세요.

### ② `.cursor/plans/roadmap.md` (로드맵)

개발 플랜 요약과 단계별 체크리스트가 **`.cursor/plans/roadmap.md`**에 있습니다.

**AI에게 지시 예시**:  
"모든 작업 전에 **@.cursor/plans/roadmap.md**를 읽고 현재 단계를 체크해줘."

이렇게 하면 에이전트가 항상 현재 페이즈와 다음 할 일을 기준으로 작업할 수 있습니다.

---

## 3. 기능별 최적화 세팅

### ① 지식 그래프(Neo4j) 및 파이프라인 개발

- **API/문서 연결**:  
  **Settings > Indexing**에서 Neo4j 공식 문서 URL을 **@Docs**에 추가하세요.  
  → AI가 최신 Cypher 쿼리 문법을 정확히 사용할 수 있습니다.

- **Agent Mode (Shift + Tab)**:  
  파이프라인 에이전트(Fetch, Extract, Ingest)를 만들 때 **Plan Mode**를 먼저 켜세요.  
  → manifest 구조를 먼저 설계한 뒤 코드를 작성하면 **캐스케이드 구조**가 깨지지 않습니다.

- **논문 추출 로직**:  
  추출 로직을 짤 때는 **@Files**로 `docs/PIPELINE_AGENTS.md`(또는 `docs/AGENTS_AND_ARTIFACTS.md`)를 언급하세요.

### ② 시각화 및 UI (Health Map)

- **Mermaid 활용**:  
  Cursor 2.5(2026)는 Mermaid 다이어그램을 실시간 렌더링합니다.  
  "헬스맵 레이어 구조를 Mermaid로 그려줘"라고 하면 아키텍처를 시각적으로 확인하며 코딩할 수 있습니다.

- **UI/UX 규칙**:  
  `.cursor/rules/project.mdc`에 이미 명시되어 있습니다.  
  - 정보(Info) → **파란색** 뱃지  
  - 지식(Knowledge) → **녹색** 뱃지  
  - 지혜(Wisdom) → **금색** 뱃지  

---

## 4. Composer / Agent 모드 설정 (2026년형)

**인간 개입 최소화·자율 최적화**를 위해 아래 설정을 권장합니다.

| 설정 | 권장 값 |
|------|---------|
| **Composer** (Cmd + I) | 오른쪽 하단 모델: **Claude 3.5 Sonnet** 또는 **GPT-4o** (추론·에러 분석에 유리) |
| **Agent 모드** | 반드시 **활성화**. 파이프라인 실행 → 에러 포착 → 코드 수정 → 재검증을 에이전트가 반복하도록. |
| **YOLO Mode** | **Settings → Features → YOLO Mode** 를 켜세요. 터미널 명령(파이프라인 실행, `validate_run.py --neo4j`)마다 승인 없이 실행되어 자율 루프가 빨라집니다. |

- Agent 전용 규칙: 프로젝트 루트 **`.cursorrules`** 및 **`.cursor/rules/agent-workflow.mdc`** 에 “수정 후 검증 실행”, “에러 시 즉시 수정”, “Neo4j 꺼져 있으면 docker-compose up -d” 등이 명시되어 있습니다.

## 5. 2026년형 워크플로우 팁

| 기능 | 용도 |
|------|------|
| **YOLO Mode** | 파이프라인·검증 스크립트 반복 실행 시 **Settings → Features → YOLO Mode** 로 승인 없이 실행. |
| **Context Mention (@)** | 논문 추출·파이프라인 로직 작성 시 **@Files**로 `docs/PIPELINE_AGENTS.md` 또는 `docs/AGENTS_AND_ARTIFACTS.md`를 언급하세요. |
| **Debug Mode** | Neo4j 데이터 적재 중 에러 시 **Debug Mode** 사용. AI가 로그를 심고 원인 분석·리포트 제출. |

---

## 6. 요약 체크리스트

- [ ] Cursor Pro 플랜 사용 (초기에는 Max Mode 자제)
- [ ] **Composer**: Claude 3.5 Sonnet 또는 GPT-4o, **Agent 모드** 활성화
- [ ] **Settings → Features → YOLO Mode** 켜기 (자율 파이프라인·검증용)
- [ ] `.cursor/rules/project.mdc`, `.cursorrules`, `.cursor/rules/agent-workflow.mdc` 확인
- [ ] 작업 전 "**@.cursor/plans/roadmap.md** 읽고 현재 단계 체크해줘" 지시 습관화
- [ ] Settings > Indexing에 Neo4j 공식 문서 URL 추가
- [ ] 파이프라인/에이전트 설계 시 **Plan Mode** 먼저 사용
- [ ] 필요 시 YOLO Mode / @ mention / Debug Mode 활용

이 가이드는 `docs/SUMMARY_PLAN_AND_ARCHITECTURE.md` 및 `docs/ROADMAP.md`와 함께 사용하세요.
