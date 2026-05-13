# PPT Entry Dynamic Recommendation Prefill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the teacher-side PPT entry modal fetch dynamic recommendation cards, auto-select the best card on open, and fully prefill the PPT form from backend-provided configuration.

**Architecture:** Extend the `/api/chat/v2/ppt/cards` contract so every PPT card can carry a normalized `prefill_config` and the response can nominate `default_selected_card_id`. Implement the recommendation intelligence on the backend in one place, then keep the frontend thin by mapping `prefill_config` into form values and reusing the same helper for auto-select and click-switch behavior.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, TypeScript, React, Ant Design, existing `app.chat` v2 services, Node test runner

---

## File Structure

### Create

- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/ppt_entry_recommendation_generator.py`
  Purpose: generate PPT recommendation cards with full `prefill_config` from document summaries and supported recommendation types.
- `D:/Edu_AI_1/Edu_AI/tests/frontend/pptEntry.prefill.helpers.test.ts`
  Purpose: verify frontend card-selection and prefill-mapping helpers using real exported functions.

### Modify

- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
  Purpose: add `PptPrefillConfigV2`, extend `PptEntryCardV2`, and extend `ChatPptCardsResponseV2`.
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/ppt_entry_cards_service_v2.py`
  Purpose: switch from rule-only cards to LLM-first recommendations with fallback, `prefill_config`, and `default_selected_card_id`.
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`
  Purpose: lock the new schema contract.
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`
  Purpose: lock the `/api/chat/v2/ppt/cards` route response shape.
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_ppt_entry_cards_service_v2.py`
  Purpose: cover generated cards, fallback cards, supported themes, and default-card selection.
- `D:/Edu_AI_1/Edu_AI/src/services/teacher/chatV2.ts`
  Purpose: expose new response and card fields to the frontend.
- `D:/Edu_AI_1/Edu_AI/src/services/teacher/pptEntry.helpers.ts`
  Purpose: add reusable helpers for resolving the initial card and mapping `prefill_config` into panel form values.
- `D:/Edu_AI_1/Edu_AI/tests/frontend/pptEntry.helpers.test.ts`
  Purpose: keep direct outline payload tests green after new hidden `targetSlideCount` support.
- `D:/Edu_AI_1/Edu_AI/src/components/teacher/PptEntryPanel.tsx`
  Purpose: auto-select default cards on load, preserve `targetSlideCount`, and reuse one prefill pathway for load and click.
- `D:/Edu_AI_1/Edu_AI/tests/frontend/pptEntryPanel.test.ts`
  Purpose: assert the panel uses the new helper flow and default-card response fields.

---

### Task 1: Extend The PPT Cards API Contract

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`

- [ ] **Step 1: Write the failing schema and route tests**

```python
def test_chat_ppt_cards_response_supports_prefill_config_and_default_selected_card():
    payload = ChatPptCardsResponseV2(
        entry_mode="knowledge_base_ppt",
        default_selected_card_id="rec-concept-focus",
        cards=[
            {
                "card_id": "rec-concept-focus",
                "card_type": "recommended",
                "title": "核心概念梳理",
                "description": "适合做概念讲解",
                "objective_hint": "课堂讲解",
                "length_option": "medium",
                "recommendation_type": "concept_focus",
                "prefill_config": {
                    "deck_title": "AI Agent 核心概念",
                    "theme_id": "heu_academic_elegant",
                    "length_option": "medium",
                    "target_slide_count": 16,
                    "key_points": ["定义", "机制"],
                },
            }
        ],
        trace={"selected_doc_count": 1},
    )

    assert payload.default_selected_card_id == "rec-concept-focus"
    assert payload.cards[0].prefill_config.deck_title == "AI Agent 核心概念"
    assert payload.cards[0].prefill_config.target_slide_count == 16


def test_ppt_cards_v2_route_returns_default_selected_card_and_prefill_config(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def get_cards(self, payload):
            return {
                "entry_mode": "knowledge_base_ppt",
                "default_selected_card_id": "rec-concept-focus",
                "cards": [
                    {
                        "card_id": "rec-concept-focus",
                        "card_type": "recommended",
                        "title": "核心概念梳理",
                        "description": "适合做概念讲解",
                        "objective_hint": "课堂讲解",
                        "length_option": "medium",
                        "recommendation_type": "concept_focus",
                        "prefill_config": {
                            "deck_title": "AI Agent 核心概念",
                            "theme_id": "heu_academic_elegant",
                            "length_option": "medium",
                            "target_slide_count": 16,
                            "key_points": ["定义", "机制"],
                        },
                    }
                ],
                "trace": {"selected_doc_count": 1},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_ppt_entry_cards_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/ppt/cards", json={"selected_doc_ids": ["doc-1"]})

    assert response.status_code == 200
    assert response.json()["default_selected_card_id"] == "rec-concept-focus"
    assert response.json()["cards"][0]["prefill_config"]["target_slide_count"] == 16
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_schemas_v2.py D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_v2.py -q
```

Expected: FAIL because `ChatPptCardsResponseV2` and `PptEntryCardV2` do not yet accept `default_selected_card_id` or `prefill_config`.

- [ ] **Step 3: Write the minimal schema implementation**

```python
class PptPrefillConfigV2(BaseModel):
    deck_title: str = ""
    deck_subtitle: Optional[str] = None
    audience: str = ""
    objective: str = ""
    theme_id: str = "heu_academic_elegant"
    length_option: PptLengthOption = "medium"
    target_slide_count: int = 0
    key_points: List[str] = Field(default_factory=list)
    style_hint: Optional[str] = None
    general_requirements: Optional[str] = None
    special_requirements: Optional[str] = None


class PptEntryCardV2(BaseModel):
    card_id: str
    card_type: ReportEntryCardType
    title: str
    description: str
    objective_hint: str
    length_option: PptLengthOption
    preset_key: Optional[PptPresetKey] = None
    recommendation_type: Optional[PptRecommendationType] = None
    recommendation_source: Optional[Literal["doc_summaries"]] = None
    fit_score: Optional[FitScore] = None
    deck_title_hint: Optional[str] = None
    audience_hint: Optional[str] = None
    key_points_hint: List[str] = Field(default_factory=list)
    style_hint: Optional[str] = None
    prefill_config: Optional[PptPrefillConfigV2] = None


class ChatPptCardsResponseV2(BaseModel):
    entry_mode: PptEntryMode
    cards: List[PptEntryCardV2] = Field(default_factory=list)
    default_selected_card_id: Optional[str] = None
    trace: Dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_schemas_v2.py D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_v2.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py
git commit -m "feat: extend PPT cards response contract"
```

---

### Task 2: Add Dynamic PPT Recommendation Generation With Fallback

**Files:**
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/ppt_entry_recommendation_generator.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/ppt_entry_cards_service_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_ppt_entry_cards_service_v2.py`

- [ ] **Step 1: Write the failing backend recommendation tests**

```python
def test_ppt_entry_cards_service_returns_prefill_config_for_generated_cards():
    class DummyGenerator:
        def generate_recommendations(self, *, documents, recommendation_types):
            return {
                "default_selected_card_id": "rec-concept-focus",
                "cards": [
                    {
                        "recommendation_type": "concept_focus",
                        "title": "核心概念梳理",
                        "description": "适合做概念讲解",
                        "fit_score": "high",
                        "prefill_config": {
                            "deck_title": "AI Agent 核心概念",
                            "deck_subtitle": "基于 1 份资料生成",
                            "audience": "本科生",
                            "objective": "课堂讲解",
                            "theme_id": "heu_academic_elegant",
                            "length_option": "medium",
                            "target_slide_count": 16,
                            "key_points": ["定义", "机制"],
                            "style_hint": "讲解清晰",
                            "general_requirements": "用于课堂投屏",
                            "special_requirements": "结尾保留总结页",
                        },
                    }
                ],
            }

    service = PptEntryCardsServiceV2(
        summary_provider=DummySummaryProvider({"documents": [{"title": "AI Agent", "summary": "介绍定义与机制"}], "fallback_used": False}),
        recommendation_generator=DummyGenerator(),
    )

    result = service.get_cards(type("Payload", (), {"selected_doc_ids": ["doc-1"], "owner": "tester"})())

    assert result["default_selected_card_id"] == "rec-concept-focus"
    assert result["cards"][-1]["prefill_config"]["deck_title"] == "AI Agent 核心概念"
    assert result["cards"][-1]["prefill_config"]["theme_id"] == "heu_academic_elegant"


def test_ppt_entry_cards_service_falls_back_to_rule_based_prefill_when_generator_fails():
    class FailingGenerator:
        def generate_recommendations(self, *, documents, recommendation_types):
            raise RuntimeError("generator unavailable")

    service = PptEntryCardsServiceV2(
        summary_provider=DummySummaryProvider({"documents": [{"title": "流程设计", "summary": "介绍流程与步骤"}], "fallback_used": False}),
        recommendation_generator=FailingGenerator(),
    )

    result = service.get_cards(type("Payload", (), {"selected_doc_ids": ["doc-1"], "owner": "tester"})())

    recommended = [card for card in result["cards"] if card["card_type"] == "recommended"]
    assert result["default_selected_card_id"] == recommended[0]["card_id"]
    assert recommended[0]["prefill_config"]["theme_id"] in {"heu_academic_elegant", "heu_academic_basic"}
    assert recommended[0]["prefill_config"]["target_slide_count"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_entry_cards_service_v2.py -q
```

Expected: FAIL because the service has no generator injection, no `prefill_config`, and no `default_selected_card_id`.

- [ ] **Step 3: Write the minimal recommendation generator and service implementation**

```python
class PptEntryRecommendationGenerator:
    SUPPORTED_THEMES = {"heu_academic_elegant", "heu_academic_basic"}

    def __init__(self, *, llm=None):
        self.llm = llm or get_fallback_llm()

    def generate_recommendations(self, *, documents, recommendation_types):
        # Mirror report-entry structured output flow:
        # 1. build prompt from document titles/summaries
        # 2. request structured card bundle
        # 3. normalize each card into required recommendation type order
        # 4. normalize theme_id into SUPPORTED_THEMES
        ...


class PptEntryCardsServiceV2:
    def __init__(self, *, summary_provider=None, recommendation_generator=None):
        self.summary_provider = summary_provider or KnowledgeBaseSummaryProvider()
        self.recommendation_generator = recommendation_generator or build_default_ppt_entry_recommendation_generator()

    def get_cards(self, payload):
        ...
        recommended_cards, default_selected_card_id, generation_mode, generation_error = self._build_recommended_cards(...)
        return {
            "entry_mode": "knowledge_base_ppt",
            "cards": [*_build_preset_cards(), *recommended_cards],
            "default_selected_card_id": default_selected_card_id,
            "trace": {
                "selected_doc_count": len(selected_doc_ids),
                "summary_doc_count": len(documents),
                "fallback_used": bool(summary_result.get("fallback_used")),
                "recommendation_generation_mode": generation_mode,
            },
        }

    def _build_rule_based_prefill(self, *, recommendation_type, documents):
        return {
            "deck_title": self._build_deck_title(recommendation_type=recommendation_type, documents=documents),
            "deck_subtitle": self._build_deck_subtitle(documents=documents),
            "audience": self._infer_audience(documents=documents),
            "objective": self._infer_objective(recommendation_type=recommendation_type),
            "theme_id": "heu_academic_elegant",
            "length_option": self._infer_length_option(recommendation_type=recommendation_type),
            "target_slide_count": self._resolve_target_slide_count(recommendation_type=recommendation_type),
            "key_points": self._infer_key_points(documents=documents, recommendation_type=recommendation_type),
            "style_hint": self._infer_style_hint(recommendation_type=recommendation_type),
            "general_requirements": self._infer_general_requirements(documents=documents, recommendation_type=recommendation_type),
            "special_requirements": "",
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_entry_cards_service_v2.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/ppt_entry_recommendation_generator.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/ppt_entry_cards_service_v2.py D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_ppt_entry_cards_service_v2.py
git commit -m "feat: add dynamic PPT entry recommendations"
```

---

### Task 3: Add Frontend Prefill Helpers And Preserve Hidden Slide Count

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/src/services/teacher/chatV2.ts`
- Modify: `D:/Edu_AI_1/Edu_AI/src/services/teacher/pptEntry.helpers.ts`
- Create: `D:/Edu_AI_1/Edu_AI/tests/frontend/pptEntry.prefill.helpers.test.ts`
- Modify: `D:/Edu_AI_1/Edu_AI/tests/frontend/pptEntry.helpers.test.ts`

- [ ] **Step 1: Write the failing frontend helper tests**

```ts
import assert from 'node:assert/strict';

import {
  buildDirectPptOutlineRequest,
  buildPptEntryFormValuesFromCard,
  pickInitialPptEntryCard,
} from '../../src/services/teacher/pptEntry.helpers.ts';

const cards = [
  {
    card_id: 'preset-knowledge-lecture',
    card_type: 'preset',
    title: '知识讲解型',
    description: '适合课堂讲解',
    objective_hint: '课堂讲解',
    length_option: 'medium',
    preset_key: 'knowledge_lecture',
  },
  {
    card_id: 'rec-concept-focus',
    card_type: 'recommended',
    title: '核心概念梳理',
    description: '适合概念讲解',
    objective_hint: '课堂讲解',
    length_option: 'medium',
    recommendation_type: 'concept_focus',
    prefill_config: {
      deck_title: 'AI Agent 核心概念',
      deck_subtitle: '基于 2 份资料生成',
      audience: '本科生',
      objective: '课堂讲解',
      theme_id: 'heu_academic_elegant',
      length_option: 'medium',
      target_slide_count: 16,
      key_points: ['定义', '机制'],
      style_hint: '讲解清晰',
      general_requirements: '用于课堂投屏',
      special_requirements: '结尾保留总结页',
    },
  },
];

assert.equal(pickInitialPptEntryCard(cards as any, 'rec-concept-focus')?.card_id, 'rec-concept-focus');

const formValues = buildPptEntryFormValuesFromCard(cards[1] as any);
assert.equal(formValues.deckTitle, 'AI Agent 核心概念');
assert.equal(formValues.targetSlideCount, 16);
assert.match(formValues.keyPointsText ?? '', /定义/);

const outlinePayload = buildDirectPptOutlineRequest({
  courseId: 'course-1',
  selectedDocIds: ['doc-1'],
  config: {
    ...formValues,
    keyPoints: ['定义', '机制'],
  },
});

assert.equal(outlinePayload.ppt_config.target_slide_count, 16);
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\pptEntry.helpers.test.ts D:\Edu_AI_1\Edu_AI\tests\frontend\pptEntry.prefill.helpers.test.ts
```

Expected: FAIL because helper exports and `targetSlideCount` plumbing do not exist yet.

- [ ] **Step 3: Write the minimal helper implementation**

```ts
export interface DirectPptEntryConfigInput {
  deckTitle: string;
  deckSubtitle?: string;
  audience?: string;
  objective?: string;
  themeId: 'heu_academic_elegant' | 'heu_academic_basic';
  lengthOption: 'short' | 'medium' | 'long';
  targetSlideCount?: number;
  keyPoints: string[];
  styleHint?: string;
  specialRequirements?: string;
  generalRequirements?: string;
  selectedCard?: PptEntryCardSelection | null;
}

export function pickInitialPptEntryCard(cards: PptEntryCard[], defaultSelectedCardId?: string | null): PptEntryCard | null {
  return (
    cards.find((card) => card.card_id === defaultSelectedCardId) ||
    cards.find((card) => card.card_type === 'recommended') ||
    cards[0] ||
    null
  );
}

export function buildPptEntryFormValuesFromCard(card: PptEntryCard) {
  const prefill = card.prefill_config || {};
  return {
    deckTitle: prefill.deck_title || '',
    deckSubtitle: prefill.deck_subtitle || '',
    audience: prefill.audience || '',
    objective: prefill.objective || card.objective_hint || '',
    themeId: prefill.theme_id || 'heu_academic_elegant',
    lengthOption: prefill.length_option || card.length_option || 'medium',
    targetSlideCount: prefill.target_slide_count || 0,
    keyPointsText: Array.isArray(prefill.key_points) ? prefill.key_points.join('\n') : '',
    styleHint: prefill.style_hint || card.style_hint || '',
    generalRequirements: prefill.general_requirements || '',
    specialRequirements: prefill.special_requirements || '',
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\pptEntry.helpers.test.ts D:\Edu_AI_1\Edu_AI\tests\frontend\pptEntry.prefill.helpers.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add D:/Edu_AI_1/Edu_AI/src/services/teacher/chatV2.ts D:/Edu_AI_1/Edu_AI/src/services/teacher/pptEntry.helpers.ts D:/Edu_AI_1/Edu_AI/tests/frontend/pptEntry.helpers.test.ts D:/Edu_AI_1/Edu_AI/tests/frontend/pptEntry.prefill.helpers.test.ts
git commit -m "feat: add PPT entry prefill helpers"
```

---

### Task 4: Wire PptEntryPanel To Auto-Select And Refill The Form

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/src/components/teacher/PptEntryPanel.tsx`
- Modify: `D:/Edu_AI_1/Edu_AI/tests/frontend/pptEntryPanel.test.ts`

- [ ] **Step 1: Write the failing panel test**

```ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const file = readFileSync(new URL('../../src/components/teacher/PptEntryPanel.tsx', import.meta.url), 'utf8');

assert.match(file, /default_selected_card_id/, 'PptEntryPanel should read the backend default card');
assert.match(file, /pickInitialPptEntryCard\(/, 'PptEntryPanel should use the shared initial-card helper');
assert.match(file, /buildPptEntryFormValuesFromCard\(/, 'PptEntryPanel should map card prefill into form values');
assert.match(file, /targetSlideCount/, 'PptEntryPanel should preserve hidden target slide count');
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\pptEntryPanel.test.ts
```

Expected: FAIL because the panel still hardcodes `applyCardDefaults` and ignores `default_selected_card_id`.

- [ ] **Step 3: Write the minimal panel implementation**

```tsx
type DirectPptEntryFormValue = {
  deckTitle: string;
  deckSubtitle?: string;
  audience?: string;
  objective?: string;
  themeId: 'heu_academic_elegant' | 'heu_academic_basic';
  lengthOption: LengthOption;
  targetSlideCount?: number;
  keyPointsText?: string;
  generalRequirements?: string;
  styleHint?: string;
  specialRequirements?: string;
};

const applyCardPrefill = (card: PptEntryCard) => {
  setSelectedCard(card);
  form.setFieldsValue(buildPptEntryFormValuesFromCard(card));
};

fetchPptEntryCardsV2({ course_id: courseId, selected_doc_ids: selectedDocIds }).then((response) => {
  const nextCards = Array.isArray(response.cards) && response.cards.length > 0 ? response.cards : DEFAULT_PPT_CARDS;
  setCards(nextCards);
  const initialCard = pickInitialPptEntryCard(nextCards, response.default_selected_card_id);
  if (initialCard) {
    applyCardPrefill(initialCard);
  }
  setEntryState('cards_ready');
});

const response = await onSubmitOutline({
  config: {
    deckTitle: values.deckTitle,
    deckSubtitle: values.deckSubtitle,
    audience: values.audience?.trim(),
    objective: values.objective?.trim() || selectedCard?.objective_hint || '',
    themeId: values.themeId,
    lengthOption: values.lengthOption || selectedCard?.length_option || 'medium',
    targetSlideCount: values.targetSlideCount,
    keyPoints: normalizeKeyPoints(values.keyPointsText || ''),
    ...
  },
});
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
node --test D:\Edu_AI_1\Edu_AI\tests\frontend\pptEntryPanel.test.ts D:\Edu_AI_1\Edu_AI\tests\frontend\pptEntry.helpers.test.ts D:\Edu_AI_1\Edu_AI\tests\frontend\pptEntry.prefill.helpers.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add D:/Edu_AI_1/Edu_AI/src/components/teacher/PptEntryPanel.tsx D:/Edu_AI_1/Edu_AI/tests/frontend/pptEntryPanel.test.ts
git commit -m "feat: auto-prefill PPT entry form from recommendation cards"
```

---

## Self-Review

### Spec coverage

- Dynamic generation via explicit `/api/chat/v2/ppt/cards`: covered in Task 2.
- `prefill_config` field on each card: covered in Tasks 1 and 2.
- `default_selected_card_id`: covered in Tasks 1 and 2.
- Auto-select on modal open: covered in Task 4.
- Click-card full overwrite: covered in Task 4.
- Preserve `target_slide_count` into outline request: covered in Tasks 3 and 4.
- Fallback behavior when LLM fails: covered in Task 2.

### Placeholder scan

- No `TODO`, `TBD`, “similar to above”, or “add tests later” placeholders remain.
- Every implementation task shows the exact files, commands, and the code shape expected.

### Type consistency

- Backend uses `prefill_config` and `default_selected_card_id` consistently across schema, route, and service tasks.
- Frontend uses `targetSlideCount` in form state and `target_slide_count` in API payload consistently.
- Card selection helper names match the panel task: `pickInitialPptEntryCard`, `buildPptEntryFormValuesFromCard`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-12-ppt-entry-dynamic-recommendation-prefill-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
