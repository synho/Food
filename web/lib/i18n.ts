/**
 * Simple i18n: EN / KO. Locale stored in localStorage, default from navigator or "en".
 */
export type Locale = "en" | "ko";

export const messages: Record<Locale, Record<string, string>> = {
  en: {
    "home.title": "Health Navigation",
    "home.intro": "We're glad you're here. Share a little about yourself in your own words—as if you were chatting with a new friend. Type or use your voice; whatever feels easy. We'll use it only to offer guidance that fits you, and you can add or change anything whenever you like.",
    "intro.title": "Introduce yourself—like to a new friend",
    "intro.desc": "Imagine you're meeting someone on a trip or having a relaxed chat with a friendly advisor. Share whatever feels right: your age, how you're doing, any conditions or medications, or what you'd like to focus on. Type or tap the mic and speak—we'll only use it to tailor things for you, and you can add or change anything anytime.",
    "intro.placeholder": "For example: \"I'm 53 and have prediabetes. I take Mounjaro and try to stay active—I'd love to keep my blood sugar in check and have less shoulder pain.\"\n\nOr something short: \"Hi, I'm 45 and just looking for gentle tips on eating well.\"",
    "intro.useVoice": "Use voice",
    "intro.stop": "Stop",
    "intro.continue": "Continue",
    "intro.loading": "Reading what you shared…",
    "intro.voiceUnsupported": "Voice input isn't available in this browser. Chrome or Edge work well if you'd like to try it.",
    "intro.voiceError": "We couldn't start the mic—you may need to allow microphone access.",
    "preferShort": "Prefer to fill in a few fields?",
    "useShortForm": "Use the short form",
    "rewriteIntro": "Rewrite your intro in your own words",
    "orOwnWords": "Or tell us in your own words instead",
    "extractError": "We couldn't read that just yet. No worries—try again or use the short form below.",
    "extractErrorServer": "Couldn't reach the API server. Start it from the repo root: ./run.sh start or uvicorn server.main:app --reload --port 8001",
    "understood.title": "Here's what we picked up",
    "understood.desc": "Feel free to change or add anything below—then we'll put together your guidance.",
    "understood.minimal": "If you'd like, you can add your age or something you'd like to focus on—it helps us tailor things a little more. Or you can skip and we'll give you gentle, general guidance.",
    "getGuidance": "Get my guidance",
    "getGuidanceLoading": "Getting your guidance…",
    "age": "Age",
    "gender": "Gender",
    "genderPlaceholder": "e.g. female, male, non-binary — optional",
    "conditions": "Conditions",
    "symptoms": "Symptoms",
    "medications": "Medications",
    "goals": "Goals",
    "add": "Add",
    "cancel": "Cancel",
    "optional": "Optional",
    "privacy.title": "Your privacy & secure storage",
    "privacy.desc": "We don't save anything unless you ask us to. When you do save, your info is encrypted and can only be brought back with a one-time code. Feel free to try things out with just a little info first; when you're comfortable, you can add more and save if you'd like.",
    "saveButton": "Save my info securely",
    "saving": "Saving…",
    "savedMessage": "All set. Your restore code is",
    "savedHint": "copy it somewhere safe so you can bring your info back later.",
    "restorePlaceholder": "Paste restore code",
    "restoreButton": "Restore my saved info",
    "saveFirst": "Share a bit about yourself above and get your guidance first—then you can save it here.",
    "saveFailed": "Saving isn't available right now. Your data is still only on your device.",
    "restoreFailed": "That code didn't work—it may be wrong or already used. Try saving again to get a new code.",
    "inputSummary.title": "What we used to tailor this for you",
    "inputSummary.hint": "Whenever you're ready, you can add more above and we'll refine the guidance. Nothing is saved unless you choose to save it below.",
    "noRecs": "We don't have any recommendations to show yet. If you're running this yourself, the knowledge base may still be empty—try running the pipeline first.",
    "drugSection.title": "Foods that may support your medications",
    "drugSection.desc": "Here you can look up foods or ingredients that might substitute or complement a medication, based on our knowledge base. This isn't medical advice—your doctor or pharmacist is the best person to talk to about your meds.",
    "drugSearch": "Search",
    "drugSearching": "Searching…",
    "drugEmpty": "We don't have any matches for that medication in our knowledge base yet. You can try another name or check back later.",
    "form.title": "A little about you",
    "form.desc": "Start with just age and gender if you like—that's enough to begin. You can add conditions or medications whenever you're comfortable, and we'll tailor things a bit more.",
    "form.basicInfo": "Basic info",
    "form.optionalSection": "Optional — when you're ready for more tailored guidance",
    "conditionsLabel": "Conditions",
    "symptomsLabel": "Symptoms",
    "medicationsLabel": "Medications",
    "goalsLabel": "Goals",
  },
  ko: {
    "home.title": "건강 내비게이션",
    "home.intro": "방문해 주셔서 감사해요. 새로 만난 친구에게 말하듯, 편하게 자기 소개를 적어 주세요. 글로 써도 좋고, 마이크로 말해도 돼요. 입력한 내용은 오직 맞춤 안내를 위해만 쓰이며, 언제든 더 넣거나 고칠 수 있어요.",
    "intro.title": "자기 소개—친구에게 말하듯",
    "intro.desc": "여행에서 만난 사람이랑 대화하거나, 친근한 상담자와 편하게 수다 나누는 느낌으로 적어 주세요. 나이, 요즘 컨디션, 갖고 계신 질환이나 복용 약, 그리고 신경 쓰이는 걸 아무거나 괜찮아요. 글을 써도 되고 마이크를 눌러 말해도 되고요. 여기서만 쓰고, 나중에 마음 바꿔서 고치거나 더 적어도 돼요.",
    "intro.placeholder": "예: \"저는 53살이고 전당뇨가 있어요. 몬자로 먹고 있고, 혈당 관리랑 어깨 통증 줄이는 게 목표예요.\"\n\n짧게: \"안녕하세요, 45세이고 건강하게 먹고 싶어요.\"",
    "intro.useVoice": "음성으로 입력",
    "intro.stop": "끄기",
    "intro.continue": "다음",
    "intro.loading": "적어 주신 내용을 읽고 있어요…",
    "intro.voiceUnsupported": "이 브라우저에서는 음성 입력이 지원되지 않아요. Chrome이나 Edge에서 사용해 보세요.",
    "intro.voiceError": "마이크를 켜지 못했어요. 마이크 권한을 허용해 주세요.",
    "preferShort": "항목을 직접 채우는 게 편하시다면",
    "useShortForm": "짧은 폼 사용",
    "rewriteIntro": "자기 소개를 다시 쓰기",
    "orOwnWords": "말로 풀어서 소개하기",
    "extractError": "아직 잘 읽지 못했어요. 다시 적어 주시거나 아래 짧은 폼을 이용해 주세요.",
    "extractErrorServer": "API 서버에 연결되지 않았어요. 터미널에서 서버를 켜 주세요: ./run.sh start 또는 uvicorn server.main:app --reload --port 8001",
    "understood.title": "이렇게 이해했어요",
    "understood.desc": "아래 내용을 마음대로 고치거나 추가한 뒤, 안내받기를 눌러 주세요.",
    "understood.minimal": "원하시면 나이나 신경 쓰이는 걸 적어 주시면 더 맞춤으로 안내해 드려요. 건너뛰셔도 되고, 그냥 일반적인 안내를 드릴게요.",
    "getGuidance": "안내받기",
    "getGuidanceLoading": "안내를 준비하고 있어요…",
    "age": "나이",
    "gender": "성별",
    "genderPlaceholder": "예: 여성, 남성 — 선택",
    "conditions": "질환",
    "symptoms": "증상",
    "medications": "복용 약",
    "goals": "목표",
    "add": "추가",
    "cancel": "취소",
    "optional": "선택",
    "privacy.title": "개인정보와 안전한 저장",
    "privacy.desc": "저장하기를 누르기 전까지는 아무것도 저장하지 않아요. 저장하면 암호화되어, 한 번만 쓰는 복원 코드로만 다시 불러올 수 있어요. 조금만 넣고 써 보시다가, 편하실 때 더 적고 저장하시면 돼요.",
    "saveButton": "내 정보 안전하게 저장",
    "saving": "저장 중…",
    "savedMessage": "저장됐어요. 복원 코드는",
    "savedHint": "—나중에 다시 불러올 수 있게 안전한 곳에 적어 두세요.",
    "restorePlaceholder": "복원 코드 붙여넣기",
    "restoreButton": "저장한 정보 불러오기",
    "saveFirst": "위에서 자기 소개를 적고 안내를 받은 뒤, 여기서 저장할 수 있어요.",
    "saveFailed": "지금은 저장이 되지 않아요. 입력한 내용은 지금 이 기기에만 있어요.",
    "restoreFailed": "코드가 맞지 않거나 이미 사용된 것 같아요. 다시 저장해서 새 코드를 받아 보세요.",
    "inputSummary.title": "이 정보로 맞춤 안내를 만들었어요",
    "inputSummary.hint": "원하실 때 위에서 더 적어 주시면 안내를 더 맞춤으로 바꿀 수 있어요. 저장하지 않으면 아무것도 저장되지 않아요.",
    "noRecs": "아직 보여드릴 추천이 없어요. 직접 실행 중이라면 지식 DB가 비어 있을 수 있으니, 파이프라인을 먼저 실행해 보세요.",
    "drugSection.title": "약과 함께 고려할 수 있는 음식",
    "drugSection.desc": "복용 중인 약을 대체하거나 보완할 수 있는 음식·성분을 지식 DB 기준으로 찾아볼 수 있어요. 의료 상담이 아니에요. 약은 의사나 약사에게 문의해 주세요.",
    "drugSearch": "검색",
    "drugSearching": "검색 중…",
    "drugEmpty": "해당 약에 대한 자료가 아직 없어요. 다른 이름으로 검색하거나 나중에 다시 확인해 보세요.",
    "form.title": "간단히 소개해 주세요",
    "form.desc": "나이와 성별만 적어도 돼요. 나중에 편하실 때 질환이나 복용 약을 더 적어 주시면 더 맞춤 안내를 드려요.",
    "form.basicInfo": "기본 정보",
    "form.optionalSection": "선택 — 맞춤 안내를 원하실 때",
    "conditionsLabel": "질환",
    "symptomsLabel": "증상",
    "medicationsLabel": "복용 약",
    "goalsLabel": "목표",
  },
};

const STORAGE_KEY = "health-nav-locale";

function getStoredLocale(): Locale {
  if (typeof window === "undefined") return "en";
  const s = localStorage.getItem(STORAGE_KEY);
  if (s === "ko" || s === "en") return s;
  const lang = navigator.language?.toLowerCase();
  if (lang.startsWith("ko")) return "ko";
  return "en";
}

export function getDefaultLocale(): Locale {
  return getStoredLocale();
}

export function setStoredLocale(locale: Locale): void {
  if (typeof window !== "undefined") localStorage.setItem(STORAGE_KEY, locale);
}

export function t(locale: Locale, key: string): string {
  const m = messages[locale];
  return m?.[key] ?? messages.en[key] ?? key;
}
