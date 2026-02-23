# Trusted Data Sources & Drug-Substituting Foods/Ingredients

## Goal

- **믿을 수 있는 데이터 소스**를 추가로 포함한다: 제약사(약물 정보·라벨), **FDA**, 그 밖의 검증된 출처.
- 이를 바탕으로 **약물을 대체하거나 보완할 수 있는 음식·성분**을 증거와 함께 제시할 수 있도록 한다. (약을 줄이거나 보조하는 식이·영양 정보는 반드시 출처를 명시.)

---

## Trusted Data Sources (신뢰할 수 있는 출처)

| Source | 설명 | 활용 |
|--------|------|------|
| **FDA** | 미국 FDA: 약물 승인, 라벨, 경고, 식이보충제·식품 관련 공식 정보 | 약–음식 상호작용, 승인된 용도, 대체 가능 성분 근거 |
| **Drug labels (제약사/라벨)** | 공식 약물 설명서, 성분, 적응증, 주의사항, 식이 권고 | 어떤 음식/성분이 약과 상호작용하거나 보완·대체 가능한지 |
| **PubMed/PMC** | 기존 파이프라인: 고영향 저널, 인간 연구만 | TREATS, PREVENTS, 약·음식 관계의 문헌 근거 |
| **기타 검증된 출처** | 국가 약전, 공공 건강 DB 등 (추가 시 출처 명시) | 동일한 증거 모델로 KG에 통합 |

모든 주장은 **출처(source_id, source_type)** 와 필요 시 **인용 문맥(context)** 을 저장해 zero-error tolerance를 유지한다.

---

## Drug substitution (약물 대체·보완 음식/성분)

- **의미**: 특정 **약물(Drug)** 에 대해, 그 약의 효과를 일부 대체하거나 보완할 수 있는 **음식(Food)**·**성분(Nutrient)** 을 제시.
- **용도**: 사용자가 복용 중인 약이 있을 때, “이런 음식/성분이 도움이 될 수 있다”(의사와 상담 권장) 수준의 정보 제공. **약 중단·감량은 반드시 의료진 판단 하에** 이루어져야 함을 전제로 한다.
- **증거**: FDA, 약물 라벨, PMC 등 **신뢰할 수 있는 출처**에서 온 관계만 사용. 각 항목에 출처(source_id, source_type, context)를 붙여 제시.

---

## KG 확장

- **관계 타입** (Core 또는 전용 레이어):
  - **SUBSTITUTES_FOR** (Food / Nutrient → Drug): 이 음식/성분이 해당 약물의 효과를 일부 대체할 수 있다는 근거가 있을 때 (출처 필수).
  - **COMPLEMENTS_DRUG** (Food / Nutrient → Drug): 해당 약물과 함께 쓰일 때 보완적으로 도움이 된다는 근거가 있을 때 (출처 필수).
- **Evidence**  
  - `source_id`: 문서/페이지 ID (FDA NDC, PMC ID, 라벨 문서 ID 등).  
  - `source_type`: `"FDA"` | `"drug_label"` | `"PMC"` | `"pharma"` 등.  
  - `context`, `journal`(해당 시), `pub_date`(해당 시) 유지.

기존 **TREATS** (Food/Nutrient → Disease)와 병행하여, “이 질병에는 이 약을 쓰고, 이 음식/성분이 그 약을 대체·보완할 수 있다”는 식으로 서버/API에서 함께 활용할 수 있다.

---

## 파이프라인·데이터 수집

- **PMC/논문**: 기존 fetch → extract → ingest; 추출 시 SUBSTITUTES_FOR, COMPLEMENTS_DRUG 도 추출하도록 프롬프트·스키마 확장.
- **FDA·제약사 등**:  
  - 별도 **수집 스크립트/에이전트** 또는 수동 큐레이션으로 구조화된 데이터(약–성분 대응, 식이 권고 등)를 생성.  
  - 동일한 **evidence 스키마**(source_id, source_type, context)로 KG에 적재.  
  - 가능한 API: FDA Open Data, DailyMed 등 (추가 시 문서화).

---

## API·제품 동작

- **입력**: 사용자 복용 약물(또는 관심 약물).
- **출력**:  
  - 해당 약을 **대체·보완**할 수 있는 **음식·성분** 목록.  
  - 각 항목별 **이유** 및 **증거**(FDA, 라벨, 논문 등 출처 + source_type).  
- “의료 조언이 아니며, 의사·약사와 상담하세요” 안내는 유지.

---

## 요약

| 항목 | 내용 |
|------|------|
| **추가 데이터 소스** | FDA, 제약사/약물 라벨 등 믿을 수 있는 출처 포함 |
| **목적** | 약물을 대체·보완할 수 있는 음식·성분을 성분 단위로 제시 |
| **KG** | SUBSTITUTES_FOR, COMPLEMENTS_DRUG 등 관계 + source_type으로 출처 구분 |
| **증거** | 모든 관계에 source_id, source_type, context 등으로 출처 추적 (zero-error 유지) |
