# Docker로 전체 스택 실행

Neo4j, API 서버, 웹 클라이언트를 Docker Compose로 한 번에 띄우는 방법입니다.

## 요구 사항

- Docker 및 Docker Compose (v2 이상)
- 포트 3001, 7474, 7687, 8000 사용 가능

## 한 번에 실행

**레포 루트**에서:

```bash
docker compose up -d
```

- **웹**: http://localhost:3001  
- **API**: http://localhost:8000 (문서: http://localhost:8000/docs)  
- **Neo4j Browser**: http://localhost:7474 (로그인: foodnot4self / foodnot4self)

첫 실행 시 이미지 빌드와 Neo4j 기동으로 1–2분 걸릴 수 있습니다. 서버는 Neo4j가 준비된 뒤에 시작됩니다.

## 로그·재시작

```bash
# 로그 보기 (전체)
docker compose logs -f

# 서비스별
docker compose logs -f server
docker compose logs -f web
docker compose logs -f neo4j

# 중지 후 재시작
docker compose down
docker compose up -d
```

## 데이터 유지

Neo4j 데이터는 Docker **named volume** (`neo4j_data`, `neo4j_logs`)에 저장됩니다.  
`docker compose down`만 하면 볼륨은 그대로라서 다음에 `up` 시 데이터가 유지됩니다.  
완전 삭제(데이터까지 제거)하려면:

```bash
docker compose down -v
```

## 기존 kg_pipeline Neo4j 데이터 사용

이미 `kg_pipeline/docker-compose.yml`로 Neo4j를 쓰고 있다면, 같은 데이터 디렉터리를 쓰도록 루트 `docker-compose`의 `neo4j` 서비스에 볼륨을 맞출 수 있습니다:

```yaml
volumes:
  - ./kg_pipeline/neo4j/data:/data
  - ./kg_pipeline/neo4j/logs:/logs
```

이 경우 루트 compose와 kg_pipeline compose를 **동시에** 띄우지 말고, 둘 중 하나만 사용하세요.

## 파이프라인(KG 구축)은 Docker 밖에서

KG 파이프라인(Fetch → Extract → Ingest)은 **로컬에서** 실행하는 것을 권장합니다.  
GEMINI_API_KEY가 필요하고, Neo4j는 Docker로 띄운 뒤 로컬에서 접속하면 됩니다.

1. `docker compose up -d` 로 Neo4j·서버·웹만 기동
2. `kg_pipeline`에서 venv 활성화 후 `python run_pipeline.py` 실행  
   (Neo4j URI는 `bolt://localhost:7687`, 인증 foodnot4self/foodnot4self)

파이프라인까지 Docker로 돌리려면 `kg_pipeline`용 Dockerfile과 별도 서비스/작업을 두면 됩니다.

## 문제 해결

- **웹에서 API 연결 안 됨**: `docker compose logs server`로 서버가 8000에서 떠 있는지 확인. 브라우저는 웹(3001)으로만 요청하고, 웹 컨테이너가 `BACKEND_URL=http://server:8000`로 서버에 프록시합니다.
- **Neo4j healthcheck 실패**: Neo4j 이미지에 `curl`이 없으면 healthcheck가 실패할 수 있습니다.  
  `docker-compose.yml`의 `neo4j` 서비스에서 `healthcheck` 블록을 제거하고, `server`의 `depends_on`을 `condition: service_healthy` 없이 `depends_on: [neo4j]`만 두면 서버는 Neo4j와 무관하게 기동합니다(기동 직후 쿼리는 실패할 수 있음).
- **포트 충돌**: 3001/8000/7474/7687을 쓰는 다른 프로세스가 있으면 `docker compose up`이 실패합니다.  
  `make ports` 또는 `lsof -i :3001 -i :8000 -i :7474 -i :7687`로 확인 후 프로세스를 끄거나, compose에서 `ports`를 다른 포트로 바꾸세요.
