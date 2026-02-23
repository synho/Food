# Health Navigation — 간편 실행 및 모니터링 (레포 루트에서 실행)

.PHONY: neo4j-up neo4j-down neo4j-console pipeline validate check check-skip-web check-skip-server-web ports server server-8001 web kg-status docker-up docker-down help start stop start-step1 start-step2 start-step3 stop-step1 stop-step2 stop-step3 test-start-stop check-sync test

help:
	@echo "사용법: make [대상]"
	@echo ""
	@echo "  === 한 번에 켜기/끄기 (로컬) ==="
	@echo "  start          전체 기동 (Neo4j → Server → Web), 백그라운드"
	@echo "  stop           전체 중지 (Web → Server → Neo4j)"
	@echo "  start-step1    ㅡ 1단계: Neo4j만 기동"
	@echo "  start-step2    ㅡ 2단계: API 서버만 기동"
	@echo "  start-step3    ㅡ 3단계: 웹만 기동"
	@echo "  stop-step1     ㅡ 1단계: 웹만 중지"
	@echo "  stop-step2     ㅡ 2단계: API 서버만 중지"
	@echo "  stop-step3     ㅡ 3단계: Neo4j만 중지"
	@echo "  test-start-stop  전체 start → check → stop 테스트 (포트 8010/3010, neo4j/pipeline 제외)"
	@echo ""
	@echo "  === 포트·개별 서비스 ==="
	@echo "  ports         사용 중인 포트 확인 (7474, 7687, 8000, 3000)"
	@echo "  neo4j-up      Neo4j 기동 (Docker)"
	@echo "  neo4j-console Neo4j 포그라운드 (Homebrew)"
	@echo "  neo4j-down    Neo4j 중지 (Docker)"
	@echo "  server        API 서버 포그라운드 (8000)"
	@echo "  server-8001   API 서버 8001 포트"
	@echo "  web           웹 포그라운드 (3000)"
	@echo ""
	@echo "  pipeline      파이프라인 1회 (Fetch→Extract→Ingest)"
	@echo "  validate      파이프라인 검증"
	@echo "  check         모듈별 상태 확인"
	@echo "  kg-status     KG 상태 상세"
	@echo "  check-skip-web / check-skip-server-web  일부만 확인"

neo4j-up:
	cd kg_pipeline && docker-compose up -d
	@echo "Neo4j 기동. 확인: make check"

neo4j-down:
	cd kg_pipeline && docker-compose down

# --- Start/Stop full stack (local, step by step) ---
start:
	@chmod +x scripts/start_local.sh scripts/stop_local.sh 2>/dev/null || true
	@./scripts/start_local.sh

stop:
	@chmod +x scripts/stop_local.sh 2>/dev/null || true
	@./scripts/stop_local.sh

start-step1:
	@chmod +x scripts/start_local.sh 2>/dev/null || true
	@./scripts/start_local.sh --only=2

start-step2:
	@chmod +x scripts/start_local.sh 2>/dev/null || true
	@./scripts/start_local.sh --only=3

start-step3:
	@chmod +x scripts/start_local.sh 2>/dev/null || true
	@./scripts/start_local.sh --only=4

stop-step1:
	@chmod +x scripts/stop_local.sh 2>/dev/null || true
	@./scripts/stop_local.sh --only=1

stop-step2:
	@chmod +x scripts/stop_local.sh 2>/dev/null || true
	@./scripts/stop_local.sh --only=2

stop-step3:
	@chmod +x scripts/stop_local.sh 2>/dev/null || true
	@./scripts/stop_local.sh --only=3

# Test: stop → start → check (exit 0) → stop. Uses ports 8010/3010 to avoid conflict with 8000/3000.
test-start-stop:
	@echo "=== Test: stop → start → check → stop (ports 8010, 3010) ==="
	@make stop
	@sleep 2
	@SERVER_PORT=8010 WEB_PORT=3010 make start
	@echo "Waiting 8s for services..."
	@sleep 8
	@SERVER_URL=http://127.0.0.1:8010 WEB_URL=http://localhost:3010 SKIP_CHECKS=neo4j,pipeline make check || (echo "make check failed"; make stop; exit 1)
	@make stop
	@echo "=== test-start-stop OK ==="

# Homebrew Neo4j: brew services 실패 시 포그라운드 실행 (이 터미널에서 Ctrl+C로 중지)
neo4j-console:
	@echo "Neo4j 포그라운드 실행. 중지: Ctrl+C"
	neo4j console

pipeline:
	cd kg_pipeline && (venv/bin/python run_pipeline.py || ( . venv/bin/activate && python run_pipeline.py ))
	@echo "파이프라인 완료. 확인: make validate 또는 make check"

validate:
	cd kg_pipeline && (venv/bin/python src/validate_run.py --neo4j || ( . venv/bin/activate && python src/validate_run.py --neo4j ))

check:
	python3 scripts/monitor.py

kg-status:
	@if [ -f .venv/bin/python3 ]; then .venv/bin/python3 scripts/kg_status.py; else python3 scripts/kg_status.py --no-neo4j; fi

# Uses .venv Python when present (neo4j driver). May need a few seconds after starting Neo4j.
debug-neo4j:
	@if [ -f .venv/bin/python3 ]; then .venv/bin/python3 scripts/debug_neo4j.py; else python3 scripts/debug_neo4j.py; fi

# 다른 앱이 3000/8000 포트를 쓰는 경우: 제외하고 확인
# 예: make check-skip-web (Web 제외), make check-skip-server-web (Server·Web 제외)
check-skip-web:
	SKIP_CHECKS=web python3 scripts/monitor.py
check-skip-server-web:
	SKIP_CHECKS=server,web python3 scripts/monitor.py

ports:
	@python3 scripts/ports_check.py

server:
	uvicorn server.main:app --reload --host 0.0.0.0

server-8001:
	uvicorn server.main:app --reload --host 0.0.0.0 --port 8001

web:
	cd web && npm run dev

docker-up:
	docker compose up -d
	@echo "웹: http://localhost:3001  API: http://localhost:8000  Neo4j: http://localhost:7474"

docker-down:
	docker compose down

check-sync:
	python3 kg_pipeline/src/check_ontology_sync.py

test:
	cd kg_pipeline && (venv/bin/python -m pytest tests/ -v || ( . venv/bin/activate && python -m pytest tests/ -v ))
	python3 -m pytest server/tests/ -v
