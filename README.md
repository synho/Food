# Health Navigation Platform (Food)

Evidence-based **health navigation** using a **Knowledge Graph** built from high-impact medical literature. Goal: help users find the **safest path to longevity or a disease-free life** through **food** — with every recommendation and restriction backed by **citable evidence** (zero-error tolerance).

## Quick links

- **요약 (한글)**: [docs/SUMMARY_PLAN_AND_ARCHITECTURE.md](docs/SUMMARY_PLAN_AND_ARCHITECTURE.md) — 개발 플랜·아키텍처 전체 요약.
- **Phase 단일 소스**: [.cursor/plans/roadmap.md](.cursor/plans/roadmap.md) — 현재 단계·체크리스트 (Cursor Agent 참조).
- **Cursor 세팅**: [docs/CURSOR_SETUP_2026.md](docs/CURSOR_SETUP_2026.md) — 에이전트·YOLO·규칙 가이드.
- **Vision & design**: [docs/VISION.md](docs/VISION.md) — DIKW flow, health map, user inputs, web→app strategy.
- **Roadmap (상세)**: [docs/ROADMAP.md](docs/ROADMAP.md) — Phased plan: pipeline → server → web → expansion → app.
- **KG schema & evidence**: [docs/KG_SCHEMA_AND_EVIDENCE.md](docs/KG_SCHEMA_AND_EVIDENCE.md).
- **Pipeline strategy**: [docs/PIPELINE_STRATEGY.md](docs/PIPELINE_STRATEGY.md) — Recent-first, iterative expansion.
- **Server API**: [docs/API_AND_SERVER.md](docs/API_AND_SERVER.md) — Food recommendations, evidence, health map, safest path.
- **Docker**: [docs/DOCKER.md](docs/DOCKER.md) — Neo4j + API + 웹을 Docker Compose로 한 번에 실행.

**Project credentials**: Where this project needs an id/password (e.g. Neo4j), we use **foodnot4self** / **foodnot4self**. Override via `.env` if needed.

## Repo structure

| Path | Purpose |
|------|--------|
| `kg_pipeline/` | Fetch papers (PMC) → extract triples (Gemini) → ingest into Neo4j. [kg_pipeline/RUN.md](kg_pipeline/RUN.md) |
| `server/` | FastAPI API: recommendations, position, safest path, early-signal & general guidance. [server/README.md](server/README.md) |
| `web/` | Next.js (App Router) client; calls server APIs. [web/README.md](web/README.md) |
| `mobile/` | Placeholder for future mobile app (same APIs). [docs/MOBILE_APP.md](docs/MOBILE_APP.md) |
| `docs/` | Vision, schema, pipeline strategy, API contract, roadmap. |
| `.cursor/plans/roadmap.md` | Single source for current phase; Cursor Agent reads before tasks. |

## 간편 실행

**한 스크립트로 전부:** `./run.sh <command>`

```bash
./run.sh start      # 전체 기동 (Neo4j → Server → Web)
./run.sh stop       # 전체 중지
./run.sh check      # 상태 확인
./run.sh ports      # 포트 사용 현황
./run.sh pipeline   # 파이프라인 1회 실행
./run.sh help       # 사용 가능한 명령 전체
```

(레포 루트에서 실행. 다른 디렉터리에서 호출해도 스크립트가 자동으로 루트로 이동.)

---

## Makefile (레포 루트)

### 한 번에 켜기/끄기 (로컬, 단계별)

| 명령 | 설명 |
|------|------|
| **`make start`** | **전체 기동** — Neo4j → API 서버 → 웹 (백그라운드). 포트 확인 후 순서대로 기동. |
| **`make stop`** | **전체 중지** — 웹 → API 서버 → Neo4j 순으로 중지. |
| `make start-step1` | 1단계: Neo4j만 기동 (Homebrew 또는 Docker) |
| `make start-step2` | 2단계: API 서버만 기동 (8000) |
| `make start-step3` | 3단계: 웹만 기동 (3000) |
| `make stop-step1` | 1단계: 웹만 중지 |
| `make stop-step2` | 2단계: API 서버만 중지 |
| `make stop-step3` | 3단계: Neo4j만 중지 (Homebrew 서비스) |

로그·PID: `.run/server.log`, `.run/web.log`, `.run/*.pid`. 상태 확인: **`make check`**.  
서버 기동에는 `uvicorn` 필요 (`.venv` 또는 `pip install uvicorn`). `make check`에서 Pipeline은 triples가 있을 때만 OK.  
**테스트**: `make test-start-stop` — stop → start(8010/3010) → check(server·web) → stop. Neo4j/Pipeline은 검사 제외.

### 개별 명령

| 명령 | 설명 |
|------|------|
| **`make ports`** | **사용 중인 포트 확인** (7474, 7687, 8000, 3000) — 충돌 회피 시 먼저 실행 권장 |
| `make neo4j-up` | Neo4j 기동 (Docker) |
| `make neo4j-console` | Neo4j 포그라운드 (Homebrew, `brew services` 실패 시) |
| `make pipeline` | 파이프라인 1회 실행 (Fetch→Extract→Ingest). `kg_pipeline/.env`에 GEMINI_API_KEY 필요. |
| `make validate` | 파이프라인 검증 (triples + Neo4j) |
| **`make check`** | **모듈별 상태 확인 (모니터링)** — Neo4j, Pipeline, Server, Web 정상 여부 출력 |
| **`make kg-status`** | **KG 상태 상세** — 파이프라인 triples, Neo4j 노드/관계·라벨별·타입별 (CLI) |
| **`make debug-neo4j`** | Neo4j 연결 테스트 |
| **웹 KG 대시보드** | 웹 실행 후 **http://localhost:3000/kg** (또는 3001) |
| `make server` | API 서버 포그라운드 (8000) |
| `make server-8001` | API 서버 8001 포트 |
| `make web` | 웹 포그라운드 (3000) |
| `make check-skip-web` / `make check-skip-server-web` | 일부만 확인 |
| **`make docker-up`** | **Docker로 전체 스택 기동**. [docs/DOCKER.md](docs/DOCKER.md) 참고. |

**다른 서버가 8000 사용 중일 때** (우리 API만 따로 쓸 때):  
1. 우리 서버를 8001에서 기동: `make server-8001` (또는 `.venv/bin/uvicorn server.main:app --reload --port 8001`)  
2. 웹이 8001을 쓰도록 `web/.env.local`에 `NEXT_PUBLIC_API_URL=http://127.0.0.1:8001` 설정 (이미 있음).  
3. 웹 실행: `make web` 또는 3001 사용 시 `cd web && npm run dev -- -p 3001`  
4. 모니터링: `SERVER_URL=http://127.0.0.1:8001 WEB_URL=http://127.0.0.1:3001 make check`

**포트 충돌 시**: `make ports`로 확인. Web 다른 포트: `cd web && npm run dev -- -p 3001`

**최초 1회**: `kg_pipeline`에 venv 생성 및 `pip install -r requirements.txt`, `GEMINI_API_KEY`를 `.env`에 설정. [kg_pipeline/RUN.md](kg_pipeline/RUN.md) 참고.

## Run the full stack (상세)

### Docker로 한 번에 (권장)

```bash
docker compose up -d
```

웹: http://localhost:3001 · API: http://localhost:8000 · Neo4j: http://localhost:7474  
자세한 내용은 [docs/DOCKER.md](docs/DOCKER.md) 참고.

### 로컬에서 개별 실행

1. **Neo4j** — Docker(권장): `make neo4j-up` 또는 `cd kg_pipeline && docker-compose up -d`.  
   **Local Neo4j (Homebrew, macOS)**: `brew services start neo4j`. 계정은 **foodnot4self / foodnot4self** (필요 시 auth 끄고 사용자 생성 후 auth 다시 켜기). 포트 7474(HTTP), 7687(Bolt). Connection refused 시 Neo4j 기동 후 수 초 대기 또는 `make debug-neo4j`(재시도 포함). `brew services start` 실패 시 터미널에서 `neo4j console`로 직접 실행해 보며 로그 확인.
2. **Pipeline** — `make pipeline` (또는 kg_pipeline에서 venv 활성화 후 `python run_pipeline.py`)
3. **Server** — `make server` (또는 `.venv/bin/uvicorn server.main:app --reload`). API: http://127.0.0.1:8000
4. **Web** — `make web` (또는 `cd web && npm run dev`). App: http://localhost:3000
5. **모니터링** — `make check` 또는 `python3 scripts/monitor.py`. 다른 앱이 3000/8000을 쓰면 `SKIP_CHECKS=web make check` 또는 `make check-skip-web` 로 해당 항목 제외 후 확인.

## Pipeline (KG build) — detail

1. **Fetch**: `kg_pipeline/src/fetch_papers.py` — recent, open-access papers from high-impact journals.
2. **Extract**: `kg_pipeline/src/extract_triples.py` — Gemini extracts entities and relationships; provenance (source_id, journal, pub_date, optional evidence_type) attached.
3. **Ingest**: `kg_pipeline/src/ingest_to_neo4j.py` — load triples into Neo4j. (Optional: `consolidate_graph.py` to merge per-paper triples.)

## Platform direction

- **Web first**, then **app**; same **server** and APIs for both.
- **Inputs**: age, gender, ethnicity, conditions, symptoms, goals (optional: place, way_of_living, culture).
- **Outputs**: recommended foods (why + evidence), restricted foods (why + evidence), health map position, nearby risks, safest path, early-signal guidance, general guidance — all from the KG with zero-error evidence.

See [docs/](docs/) for full vision and [.cursor/plans/roadmap.md](.cursor/plans/roadmap.md) for phase status.
