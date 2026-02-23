# 개발 플랜 및 아키텍처 요약

지금까지 논의한 **비전**, **아키텍처**, **파이프라인**, **로드맵**을 한 문서로 요약한 것입니다. 세부 내용은 각 전용 문서를 참조하세요.

---

## 1. 비전·미션

| 항목 | 내용 |
|------|------|
| **목표** | 사용자가 **헬스맵에서 자신의 위치**를 예측하고, **가까운 질병·사망을 피해 안전한 경로로 대피**해 **안전한 곳에서 삶을 유지**하도록 돕는 플랫폼. **항노화·감노화**를 명시적 목표로 함. |
| **핵심 수단** | **음식**: 예방·회복을 위한 **추천 음식**과 **제한 음식**, 항상 **인용 가능한 증거**와 함께 제공 (zero-error tolerance). |
| **지식 기반** | 고영향 의학 문헌 + **신뢰 데이터 소스**(FDA, 제약사/약물 라벨)를 **Knowledge Graph**에 저장. 정확하고 다양한 **지식 맵** 구축이 필수. |

---

## 2. DIKW 흐름

| 계층 | 의미 |
|------|------|
| **Data** | 고영향 의학 저널·PMC 등 **원시 논문/데이터**. |
| **Information** | 구조화된 추출: 엔티티(질병, 음식, 영양소, 약물, 생활요인)와 관계(PREVENTS, TREATS, CAUSES 등). |
| **Knowledge** | **KG**: 정규화·중복 제거·버전·출처(source, date, journal)를 가진 단일 진실 공급원. |
| **Wisdom** | KG + 사용자 맥락에서 도출한 **추론·추천**: 헬스맵 위치, 안전 경로, 추천/제한 음식, 증거 추적. |

- **Knowledge**는 파이프라인으로 **Data**에서 추출·정리.
- **Wisdom**은 서버가 **Knowledge**와 사용자 입력을 조합해 생성.

---

## 3. 헬스맵 (다층·Google Maps 스타일)

- **한 장의 맵**, **여러 레이어**. 레이어마다 **다른 정보**를 담고, **사용자 기준**으로 정렬·오버레이.
- **한 덩어리 KG가 아님** → **여러 개의 잘 정의된 레이어**로 구성 (core, aging, 향후 genetics, place, wearables 등).
- **위치 예측** → **주변 위험** 표시 → **안전 경로(대피)** 제시. 항노화·감노화는 그 경로의 일부.

**레이어 개요**

| 레이어 | 내용 | 목적 |
|--------|------|------|
| **Core** | 질병, 증상, 음식, 영양소, 약물, 생활요인 + 관계 + early signals + 증거 | 추천/제한, 안전 경로, 초기 신호 기반 대비 |
| **Aging & Biology** | 신체 시스템, 연령 관련 변화, 생애 단계, “왜 주의할지” | 연령별 일반 가이드, 식이·운동의 이유 |
| **Place & context** (예정) | 거주지, 계절, 지역 식품 | 현실 가능한 추천 |
| **Preferences** (예정) | 생활 방식, 문화, 특수 식이 | 필터·정렬 |
| **Wearables** (예정) | Apple Watch 등, 동의 기반 | 위치·추천 정교화 |

---

## 4. 사용자 입력·맥락

- **입력**: 연령, 성별, 민족, **거주지**, **생활 방식**, **문화**, 현재 질병/증상, 복용 약, 목표 등. **강요하지 않고** 더 많이 넣기 쉽게 설계.
- **동의 기반 자동 수집**: 위치, 시간대 등 가능한 정보는 **동의 후** 자동 수집. 투명·선택 가능.
- **맥락 반영**: 거주지·생활방식·연령·문화를 반영할수록 **더 정확하고 안전한** 정보 제공.

---

## 5. 서버가 제공하는 것 (출력)

| 출력 | 설명 |
|------|------|
| **위치 예측** | 사용자가 맵상 **어디에 있는지**; **주변 위험**(질병, 초기 신호). |
| **안전 경로(대피)** | 가까운 질병/사망을 피하는 **실행 단계**; 항노화·감노화 포함. |
| **추천 음식** | 무엇을 먹을지, **이유** + **증거**(source_id, source_type, context, journal, date). |
| **제한 음식** | 무엇을 피할지, **이유** + **증거**. |
| **일반 가이드** | 연령·생애 단계에 맞는 식이·운동 **“왜 주의할지”** + 증거. |
| **초기 신호 가이드** | 질병별 초기 신호, **줄이는 음식** / **피할 음식** (의사 전 미리 대비). |
| **약물 대체·보완 음식·성분** | 특정 약에 대해 **대체·보완**할 수 있는 음식·성분 + 증거(FDA, 라벨, 문헌). |

- 모든 추천/제한/경로는 **KG 증거**와 연결 (zero-error tolerance). **source_type**(FDA, PMC, drug_label 등)으로 **신뢰도 구분** 가능.

---

## 6. 초기 신호·안전 대피

- **초기 신호**: 각 질병의 **초기 증상/징후**를 KG에 정리 (Symptom –EARLY_SIGNAL_OF→ Disease).
- **줄이는 음식** = 해당 증상에 **ALLEVIATES**; **피할 음식** = **AGGRAVATES**.
- **목표**: 약을 쓰기 **전**이든 **동안**이든, **의사가 꼭 필요해지기 전**에 미리 대비해 **안전 경로로 대피**.

---

## 7. 연령·인간 생물학

- **연령에 따른 신체 변화**(무엇이, 언제, 왜)를 수집·구조화.
- **“왜 식이·운동을 신경 써야 하는지”** 설명 + 증거. 연령대별 **일반 가이드** 제공.

---

## 8. 신뢰 데이터 소스·약물 대체 음식·성분

- **추가 소스**: **FDA**, **제약사/약물 라벨** 등 믿을 수 있는 출처 포함.
- **관계**: SUBSTITUTES_FOR, COMPLEMENTS_DRUG (Food/Nutrient → Drug). **증거**는 source_id, source_type(FDA, drug_label, PMC 등)으로 구분.
- **목표**: **약물을 대체·보완할 수 있는 음식·성분**을 성분 단위로, 증거와 함께 제시.

---

## 9. 시각화·신뢰도

- **시각화**로 **정보·지식·지혜**를 효과적으로 **선별**하고, **신뢰도를 구분**해 전달.
- **정보** vs **지식** vs **지혜**를 UI에서 레이블·레이아웃으로 구분.
- **신뢰도**: **source_type**(FDA, PMC, drug_label)을 뱃지/아이콘/색으로 표시; evidence 개수·evidence_type(RCT, 메타분석 등)으로 강도 전달.
- API 응답에 **source_type**, (선택) **evidence_count**·**source_types** 포함해 클라이언트가 trust-aware UI 구성.

---

## 10. 파이프라인 아키텍처

### 10.1 전문 에이전트·캐스케이드

- **각 단계 = 전문 에이전트** (Fetch → Extract → Ingest).
- **중간 결과**는 **manifest**로 정리·보관 (`data/manifests/{agent}_{RUN_ID}.json`).
- **다음 단계**는 이전 에이전트 manifest를 읽어 **캐스케이드**로 처리. **RUN_ID**로 한 실행 단위 묶음.
- **새 과정 추가·개선**: 새 에이전트 추가 시 입·출력 계약과 manifest만 맞추면 됨.

### 10.2 Fetch 에이전트

- **역할**: PMC에서 논문 검색·다운로드.
- **제약**: **한 번에 과다 수집 금지**; **키워드를 단계적으로 확장** (topic_keywords: 좁게 시작 → 점진적 확대). **인간 연구만** (humans_only, 동물 모델 제외).
- **설정**: days_back, max_results, journals, topic_keywords, humans_only, skip_existing(증분 수집).
- **산출**: `raw_papers/PMC*.json` + **fetch manifest**.

### 10.3 Extract 에이전트

- **역할**: **Ontology 기반** triple 추출 (엔티티 타입·관계 타입은 스키마에 맞춤).
- **모델 전략**: **저비용 모델 우선**(예: gemini-2.0-flash-lite); **정확도 확인 후** 비용·정확도 균형 맞춰 상위 모델 검토.
- **산출**: `*_triples.json`, `master_graph.json` + **extract manifest**. 관계에 journal, pub_date, source_type 부여.

### 10.4 Ingest 에이전트

- **역할**: master_graph를 **Neo4j**에 적재. Ontology로 노드 라벨·관계 타입 정규화.
- **입력**: config 또는 **extract manifest**의 master_graph_path (캐스케이드).
- **산출**: Neo4j KG + **ingest manifest**.

### 10.5 Ontology·KG 스키마

- **노드**: Disease, Symptom, Food, Nutrient, Drug, LifestyleFactor (＋ BodySystem, AgeRelatedChange, LifeStage).
- **관계**: PREVENTS, CAUSES, TREATS, CONTAINS, AGGRAVATES, REDUCES_RISK_OF, ALLEVIATES, EARLY_SIGNAL_OF, SUBSTITUTES_FOR, COMPLEMENTS_DRUG (＋ aging용 PART_OF, OCCURS_AT 등).
- **증거**: 모든 관계에 source_id, context, journal, pub_date, (선택) source_type, evidence_type.

---

## 11. 가격·운영

- **초기**: 이용은 **거의 무료**.
- **이후**: **과금 앱**으로 전환 (구독 등). 설계 단계부터 **tiered access**(무료/유료) 고려.

---

## 12. 공통 계정

- 이 프로젝트에서 id/password가 필요한 곳(예: Neo4j)은 **foodnot4self** / **foodnot4self** 사용. 필요 시 `.env`로 덮어씀.

---

## 13. 개발 로드맵 (단계 요약)

| Phase | 목표 | 핵심 산출물 |
|-------|------|-------------|
| **1** | KG 파이프라인 확고 | config, ontology, 에이전트·manifest·캐스케이드, 증분 fetch, 인간만, ontology 추출·ingest |
| **2** | 서버·핵심 API | 위치·주변 위험, 추천/제한, 안전 경로, 초기 신호, 일반 가이드, 약물 대체·보완, tiered access 설계 |
| **3** | 웹 클라이언트 | 입력 플로우, 추천/제한/증거/신뢰도 표시, 헬스맵·안전 경로, 시각화·trust |
| **4** | KG 확장·품질 | 기간·저널 확대, evidence_type, 정규화·중복 제거 |
| **5** | 모바일 앱 | 동일 서버 API, 웨어러블(동의 기반) 연동 |
| **6** | 수익화 | 무료/유료 티어, 결제 연동 |

---

## 14. 전반 원칙

1. **Zero-error tolerance**: 모든 임상/추천 주장은 KG 증거와 연결.
2. **Web first, then app**: 서버·API는 한 번 설계, 웹·앱 공유.
3. **Recent, high-impact first**: 최근·고영향 저널 우선, 단계적 확장.
4. **다층 KG**: 한 덩어리가 아닌 **여러 레이어**; 사용자 기준으로 조합.
5. **거주지·생활방식·연령·문화 반영**: 더 많이 반영할수록 더 정확·안전; 강요 없이 쉽게 추가, 동의 시 자동 수집.
6. **Free at first, paid later**: 초기 무료, 이후 유료; tiered access 설계.
7. **시각화·신뢰도**: 정보·지식·지혜 구분, source_type·증거 강도로 신뢰도 구분 전달.

---

## 15. 문서 인덱스 (상세는 각 문서 참조)

| 문서 | 주제 |
|------|------|
| VISION.md | 비전, DIKW, 헬스맵, 입출력, 플랫폼 전략 |
| HEALTH_MAP_LAYERS.md | 다층 맵, 레이어 목록, 정렬 방식 |
| KG_SCHEMA_AND_EVIDENCE.md | 노드·관계 타입, 증거 모델 |
| EARLY_SIGNALS_AND_SAFETY.md | 초기 신호, 안전 대피 |
| AGING_AND_HUMAN_BIOLOGY.md | 연령·생물학, “왜 주의할지” |
| DATA_SOURCES_AND_DRUG_SUBSTITUTION.md | FDA·라벨, 약물 대체·보완 음식·성분 |
| USER_CONTEXT_AND_COLLECTION.md | 거주지·생활·문화, 동의 기반 자동 수집 |
| PIPELINE_AGENTS.md | Fetch/Extract 양·키워드·모델 전략 |
| AGENTS_AND_ARTIFACTS.md | 에이전트, manifest, 캐스케이드, RUN_ID, 확장 방법 |
| VISUALIZATION_AND_TRUST.md | 시각화, 정보/지식/지혜, 신뢰도 구분 |
| PRICING_AND_MONETIZATION.md | 무료 우선, 유료 전환, tiered access |
| PIPELINE_STRATEGY.md | 최근·고영향, 인간만, 신뢰 소스 |
| API_AND_SERVER.md | API 계약, evidence·source_type |
| ROADMAP.md | Phase 1~6 상세 체크리스트 |

이 요약과 위 문서들을 함께 보면, 현재까지의 **개발 플랜과 아키텍처 설계**를 한눈에 복기하고 공유할 수 있습니다.
