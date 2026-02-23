# Pipeline: Specialized Agents & Artifacts (캐스케이드)

## 원칙

- **각 단계는 전문 에이전트**가 담당한다 (Fetch agent, Extract agent, Ingest agent).
- **중간 결과**는 잘 정리되어 보관되고, **다음 단계**가 그 결과를 가져가 **캐스케이드** 형태로 처리한다.
- **RUN_ID**로 한 번의 파이프라인 실행을 묶어, 해당 실행의 모든 manifest·산출물을 추적한다.
- **새 과정 추가·개선**이 쉽도록, 초기부터 **입력/출력 계약**과 **manifest**를 표준화해 둔다.

---

## Agent 역할과 입·출력

| Agent | 역할 | 입력 (이전 단계 산출물) | 출력 (산출물 + manifest) |
|-------|------|-------------------------|---------------------------|
| **Fetch** | PMC에서 논문 검색·다운로드 | (없음; config + PMC API) | `raw_papers/PMC*.json` + **fetch manifest** (pmcids_fetched, file_paths, raw_papers_dir) |
| **Extract** | ontology 기반 triple 추출 | `raw_papers/` (또는 fetch manifest의 file_paths) | `extracted_triples/*_triples.json`, `master_graph.json` + **extract manifest** (papers_processed, total_triples, master_graph_path) |
| **Ingest** | Neo4j에 KG 적재 | `master_graph.json` (config 또는 **extract manifest**의 master_graph_path) | Neo4j 그래프 + **ingest manifest** (triples_ingested, status) |

각 에이전트는 **종료 시 자신의 manifest**를 `data/manifests/{agent}_{RUN_ID}.json`에 기록한다. 다음 에이전트는 **같은 RUN_ID**로 이전 에이전트의 manifest를 읽어, 필요한 경로·목록을 사용할 수 있다.

---

## Manifest와 보관 위치

- **경로**: `config.paths.manifests` (기본 `data/manifests/`).
- **파일명**: `{agent}_{RUN_ID}.json` (예: `fetch_20250222_120000.json`).
- **내용**: 에이전트별 메타데이터 + `_agent`, `_run_id`, `_ts` (기록 시각).
- **읽기**: `artifacts.read_manifest(agent, run_id)`. `run_id`를 생략하면 **가장 최근** manifest를 반환.

이렇게 하면 **중간 결과가 잘 정리되어 보관**되고, 재실행·디버깅·새 단계 추가 시 “어떤 실행의 어떤 산출물을 쓸지”를 RUN_ID와 manifest로 일관되게 선택할 수 있다.

---

## 캐스케이드 실행

1. **run_pipeline.py**가 RUN_ID를 정한다 (env `RUN_ID`가 없으면 타임스탬프로 생성).
2. **Fetch** 실행 → raw papers 저장 → **fetch manifest** 기록.
3. **Extract** 실행 → raw_papers 기준 추출 → triples·master_graph 저장 → **extract manifest** 기록.
4. **Ingest** 실행 → (선택) extract manifest에서 master_graph_path 취득 → Neo4j 적재 → **ingest manifest** 기록.

같은 RUN_ID를 유지하려면 `RUN_ID=20250222_120000 python run_pipeline.py`처럼 설정하거나, 특정 단계만 다시 돌릴 때 `RUN_ID=... python src/ingest_to_neo4j.py`처럼 이전 실행의 RUN_ID를 넘기면, ingest는 해당 RUN_ID의 extract manifest를 참고할 수 있다.

---

## 새 과정 추가·개선이 쉽도록

- **새 에이전트 추가**:  
  1. `artifacts.py`에 상수 추가 (예: `AGENT_NORMALIZE = "normalize"`).  
  2. 새 스크립트는 **이전 에이전트 manifest**를 `read_manifest(prev_agent, run_id)` 또는 `read_previous_manifest(CASCADE_ORDER, my_agent, run_id)`로 읽고, 필요한 경로·목록만 사용.  
  3. 처리 후 **write_manifest(my_agent, run_id, payload)** 로 자신의 산출물 요약 기록.  
  4. `run_pipeline.py`의 `steps`와 `CASCADE_ORDER`에 새 에이전트를 순서대로 추가.

- **입력/출력 계약**:  
  - 각 에이전트는 “입력은 config + (선택) 이전 manifest”, “출력은 특정 디렉터리/파일 + manifest”로 고정.  
  - 새 단계는 “이전 manifest에 어떤 키를 쓰는지”만 정하면, 기존 에이전트 코드 변경을 최소화할 수 있다.

- **개선**:  
  - 기존 에이전트의 **내부 로직만** 수정하고, **manifest에 기록하는 키**를 유지하면 다음 단계는 그대로 동작.  
  - manifest에 **새 키**를 추가해도 하위 호환 가능 (다음 에이전트는 필요한 키만 읽음).

이 구조로 **각각의 전문적인 에이전트**가 담당하고, **중간 결과가 잘 정리·보관**되며, **캐스케이드**로 이어지고, **새 과정 추가·개선**이 쉬워진다.
