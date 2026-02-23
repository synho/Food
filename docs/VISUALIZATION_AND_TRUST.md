# Visualization & Trust (시각화와 신뢰도)

## Why Visualization Matters

**시각화**는 정보·지식·지혜를 사용자가 **효과적으로 선별**하고, **신뢰도를 구분**해서 받아들일 수 있게 하는 데 필수입니다. 잘 설계된 시각화로:

- **정보(Information)** vs **지식(Knowledge)** vs **지혜(Wisdom)** 가 구분되어 보이고,
- **출처와 증거**가 항상 함께 전달되며,
- **신뢰도(trust)** 가 한눈에 구분 가능해 사용자가 무엇을 얼마나 믿을지 판단할 수 있습니다.

---

## Differentiating Information, Knowledge, Wisdom (선별)

| Layer | UI/시각화에서의 표현 |
|-------|----------------------|
| **Information** | 구조화된 사실 한 조각 (예: “논문 A에서 Nutrient X가 Disease Y를 PREVENTS”). 리스트·카드에 “근거 문헌”으로 표시. |
| **Knowledge** | KG에서 온 관계 + 출처 묶음. “이 관계는 N개 출처에서 지원됨”처럼 **지식**임을 레이블하고, 클릭 시 증거 목록 노출. |
| **Wisdom** | 추천·제한·안전 경로 등 **결론/행동**. “추천 음식”, “피할 음식”, “가장 안전한 경로”로 명확히 구분하고, 각 항목에 **왜**와 **근거(지식/정보)** 링크를 붙임. |

**원칙**: 화면에서 “이건 **근거(정보/지식)** 이고, 이건 **우리 플랫폼의 추천(지혜)** 다”가 명확히 보이도록 레이블·레이아웃·색/아이콘을 통일합니다.

---

## Trust / Credibility (신뢰도 구분)

사용자가 **어떤 근거를 얼마나 믿을지** 판단할 수 있도록, 다음을 **시각적으로 구분**해서 전달합니다.

### 1. Source type (출처 유형)

| source_type | 의미 | 시각화 예 |
|-------------|------|-----------|
| **FDA** | 미국 FDA 등 공적 기관 | 뱃지/아이콘 “FDA”, 높은 신뢰도 톤 |
| **drug_label** | 제약사·공식 약물 라벨 | “공식 라벨”, 중·높은 신뢰도 |
| **PMC** | PubMed Central 논문 | “연구 논문”, 저널명·연도와 함께 표시 |
| **pharma** | 제약사 공식 정보 | “제약사 정보” 뱃지 |

API 응답의 각 evidence에 **source_type**을 포함하고, 클라이언트는 이를 **뱃지·아이콘·색**으로 구분해 표시합니다.

### 2. Evidence strength (증거 강도)

- **evidence_type** (RCT, meta-analysis, cohort, review 등)이 있으면 표시 (예: “메타분석”, “RCT”).
- **동일 주장에 대한 evidence 개수**: “3편의 연구에서 지원”처럼 **N개 출처**를 보여 주어 신뢰도 직관을 돕습니다.
- (선택) **recency**: pub_date 기준 “최근 근거” 강조.

### 3. Display rules (표시 원칙)

- **모든 추천/제한/경로**에는 최소 1개의 evidence가 연결되고, 사용자 화면에는 “근거 보기”로 **출처(source_id, source_type, journal, date, context)** 를 펼쳐 볼 수 있게 합니다.
- **신뢰도 높은 출처**(FDA, 공식 라벨)는 상단 또는 별도 강조로 “믿을 수 있는 근거”임을 전달합니다.

---

## What to Visualize (시각화 대상)

| 대상 | 목적 | 신뢰도 반영 |
|------|------|-------------|
| **Health map** | 사용자 위치, 주변 위험, 안전 경로 | 경로·위험에 연결된 evidence 수·출처 타입 표시 |
| **Recommended / restricted foods** | 무엇을 먹을지/피할지 | 항목별 evidence 리스트 + source_type 뱃지 |
| **Evidence list** | “왜 이렇게 말하는가” | source_type, journal, date, context; 클릭 시 상세 |
| **KG 스니펫** (선택) | 관계 한 줄 요약 (예: Food –PREVENTS→ Disease) | 관계당 evidence 수·출처 타입 |
| **Safest path** | 단계별 행동 | 각 단계별 evidence 링크 + 신뢰도 표시 |
| **Drug-substituting foods** | 약물 대체·보완 음식·성분 | FDA/라벨 vs 논문 구분 표시 |

---

## API Contract for Trust-Aware Visualization

서버는 클라이언트가 **신뢰도를 구분해 시각화**할 수 있도록, 응답에 다음을 포함합니다.

- **evidence** 배열의 각 항목:
  - `source_id`, `source_type`, `context`, `journal`, `pub_date`
  - (선택) `evidence_type` (RCT, meta-analysis 등)
- **집계** (선택):
  - `evidence_count`: 해당 추천/제한/경로를 지원하는 evidence 개수
  - `source_types`: 해당 항목에 포함된 출처 유형 목록 (예: `["PMC", "FDA"]`)

클라이언트는 **source_type**으로 뱃지/색을 정하고, **evidence_count**로 “N개 연구/출처” 문구를 만들며, **evidence_type**이 있으면 “RCT”, “메타분석” 등을 표시합니다.

---

## UX Principles (요약)

1. **정보·지식·지혜 구분**: “근거(정보/지식)” vs “추천/경로(지혜)”가 레이블·레이아웃으로 명확히 구분된다.
2. **신뢰도 구분**: source_type(FDA, 라벨, PMC 등)과 evidence 개수·evidence_type을 뱃지/아이콘/색으로 전달한다.
3. **항상 근거 노출**: 모든 추천·제한·경로에 “근거 보기”로 출처와 인용을 펼쳐 볼 수 있게 한다.
4. **일관된 시각 언어**: 출처 유형별 시각 표현을 웹·앱 전반에 통일한다.

이 원칙에 따라 시각화를 설계·구현하면, 사용자가 **효과적으로 정보와 지식, 지혜를 선별**하고 **신뢰도를 구분**해서 받아들일 수 있습니다.
