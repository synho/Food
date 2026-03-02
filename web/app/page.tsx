"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import type { UserContext } from "@/lib/types";
import {
  fetchRecommendations,
  fetchPosition,
  fetchSafestPath,
  fetchEarlySignals,
  fetchGeneralGuidance,
  fetchDrugSubstitution,
  saveContext,
  restoreContext,
  fetchContextFromText,
} from "@/lib/api";
import { UserContextForm } from "@/components/UserContextForm";
import { EvidenceBlock } from "@/components/EvidenceBlock";
import { EvidenceLegend } from "@/components/EvidenceBadge";
import { SectionSkeleton } from "@/components/Skeleton";
import { SelfIntroBlock } from "@/components/SelfIntroBlock";
import { EditableContextSummary } from "@/components/EditableContextSummary";
import { ClinicalInsights } from "@/components/ClinicalInsights";
import { useLocale } from "@/contexts/LocaleContext";
import { useTheme } from "@/contexts/ThemeContext";

/** Derive which parts of context the user provided, for labels and ordering. */
function getContextSummary(ctx: UserContext | null) {
  if (!ctx) return { hasAge: false, hasConditions: false, hasSymptoms: false, hasMedications: false, hasGoals: false, labels: {} as Record<string, string> };
  const hasAge = ctx.age != null && ctx.age > 0;
  const hasConditions = Array.isArray(ctx.conditions) && ctx.conditions.length > 0;
  const hasSymptoms = Array.isArray(ctx.symptoms) && ctx.symptoms.length > 0;
  const hasMedications = Array.isArray(ctx.medications) && ctx.medications.length > 0;
  const hasGoals = Array.isArray(ctx.goals) && ctx.goals.length > 0;
  const labels: Record<string, string> = {};
  if (hasAge) labels.general = "Based on your age";
  if (hasConditions || hasGoals) labels.recommendations = hasConditions && hasGoals ? "Based on your conditions & goals" : hasConditions ? "Based on your conditions" : "Based on your goals";
  if (hasConditions || hasSymptoms) labels.position = hasConditions && hasSymptoms ? "Based on your conditions & symptoms" : hasConditions ? "Based on your conditions" : "Based on your symptoms";
  if (hasConditions) labels.safestPath = "Based on your conditions";
  if (hasSymptoms) labels.earlySignals = "Based on your symptoms";
  if (hasMedications) labels.drugSubstitution = "Based on your medications";
  return { hasAge, hasConditions, hasSymptoms, hasMedications, hasGoals, labels };
}

/** Short summary line for "What we're using" card. */
function getInputSummaryLine(ctx: UserContext, t: (key: string) => string): string[] {
  const parts: string[] = [];
  if (ctx.age != null && ctx.age > 0) parts.push(`${t("age")} ${ctx.age}`);
  if (ctx.gender?.trim()) parts.push(`${t("gender")}: ${ctx.gender.trim()}`);
  if (Array.isArray(ctx.conditions) && ctx.conditions.length) parts.push(`${t("conditionsLabel")}: ${ctx.conditions.join(", ")}`);
  if (Array.isArray(ctx.symptoms) && ctx.symptoms.length) parts.push(`${t("symptomsLabel")}: ${ctx.symptoms.join(", ")}`);
  if (Array.isArray(ctx.medications) && ctx.medications.length) parts.push(`${t("medicationsLabel")}: ${ctx.medications.join(", ")}`);
  if (Array.isArray(ctx.goals) && ctx.goals.length) parts.push(`${t("goalsLabel")}: ${ctx.goals.join(", ")}`);
  return parts;
}

export default function Home() {
  const [loading, setLoading] = useState(false);
  type SectionKey = "general" | "position" | "recommendations" | "safestPath" | "earlySignals";
  const [sectionErrors, setSectionErrors] = useState<Partial<Record<SectionKey, string>>>({});
  const [sectionRetrying, setSectionRetrying] = useState<SectionKey | null>(null);
  const [lastContext, setLastContext] = useState<UserContext | null>(null);
  const [restoredContext, setRestoredContext] = useState<UserContext | null>(null);
  const [drugInput, setDrugInput] = useState("");
  const [saveRestoreError, setSaveRestoreError] = useState<string | null>(null);
  const [restoreToken, setRestoreToken] = useState("");
  const [savedToken, setSavedToken] = useState<string | null>(null);
  const [saveRestoreLoading, setSaveRestoreLoading] = useState(false);
  const [drugSubstitutionLoading, setDrugSubstitutionLoading] = useState(false);
  const [drugSubstitutionError, setDrugSubstitutionError] = useState<string | null>(null);
  const [drugSubstitution, setDrugSubstitution] = useState<Awaited<ReturnType<typeof fetchDrugSubstitution>> | null>(null);
  const [results, setResults] = useState<{
    recommendations: Awaited<ReturnType<typeof fetchRecommendations>> | null;
    position: Awaited<ReturnType<typeof fetchPosition>> | null;
    safestPath: Awaited<ReturnType<typeof fetchSafestPath>> | null;
    earlySignals: Awaited<ReturnType<typeof fetchEarlySignals>> | null;
    general: Awaited<ReturnType<typeof fetchGeneralGuidance>> | null;
  }>({
    recommendations: null,
    position: null,
    safestPath: null,
    earlySignals: null,
    general: null,
  });
  const [introText, setIntroText] = useState("");
  const [extractedContext, setExtractedContext] = useState<UserContext | null>(null);
  const [inferredFields, setInferredFields] = useState<string[]>([]);
  const [followUpQuestions, setFollowUpQuestions] = useState<import("@/lib/types").FollowUpQuestion[]>([]);
  const [extractLoading, setExtractLoading] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [showShortForm, setShowShortForm] = useState(false);

  const { locale, setLocale, t } = useLocale();
  const { theme, toggleTheme } = useTheme();

  // Draft autosave: restore intro text + extracted context on mount
  useEffect(() => {
    try {
      const savedIntro = localStorage.getItem("health_nav_draft_intro");
      if (savedIntro) setIntroText(savedIntro);
      const savedCtx = localStorage.getItem("health_nav_draft_context");
      if (savedCtx) setExtractedContext(JSON.parse(savedCtx));
    } catch { /* ignore */ }
  }, []);

  // Persist intro text as user types
  useEffect(() => {
    if (introText) {
      try { localStorage.setItem("health_nav_draft_intro", introText); } catch { /* ignore */ }
    }
  }, [introText]);

  // Persist extracted context when it changes
  useEffect(() => {
    if (extractedContext) {
      try { localStorage.setItem("health_nav_draft_context", JSON.stringify(extractedContext)); } catch { /* ignore */ }
    }
  }, [extractedContext]);

  const summary = getContextSummary(lastContext);
  const inputSummaryLines = lastContext ? getInputSummaryLine(lastContext, t) : [];
  const didAutoFetchDrug = useRef(false);

  const handleContinueIntro = async (text: string) => {
    setIntroText(text);
    setExtractLoading(true);
    setExtractError(null);
    try {
      const result = await fetchContextFromText(text);
      setExtractedContext(result.context);
      setInferredFields(result.inferred ?? []);
      setFollowUpQuestions(result.follow_up ?? []);
    } catch (e) {
      const msg = e instanceof Error ? e.message : t("extractError");
      const isNotFound = /Not Found|404/i.test(msg);
      setExtractError(isNotFound ? t("extractErrorServer") : msg);
    } finally {
      setExtractLoading(false);
    }
  };

  const minimalInfo =
    extractedContext &&
    (extractedContext.age == null || extractedContext.age <= 0) &&
    (!Array.isArray(extractedContext.conditions) || extractedContext.conditions.length === 0);

  const handleSubmit = async (ctx: UserContext) => {
    setLoading(true);
    setLastContext(ctx);
    setSectionErrors({});
    didAutoFetchDrug.current = false;
    try { localStorage.setItem("health_context", JSON.stringify(ctx)); } catch { /* ignore */ }
    setResults({ recommendations: null, position: null, safestPath: null, earlySignals: null, general: null });

    const [recR, posR, pathR, earlyR, genR] = await Promise.allSettled([
      fetchRecommendations(ctx),
      fetchPosition(ctx),
      fetchSafestPath(ctx),
      fetchEarlySignals(ctx),
      fetchGeneralGuidance(ctx),
    ]);

    const toErr = (r: PromiseRejectedResult): string => {
      const msg = r.reason instanceof Error ? r.reason.message : "Request failed";
      return /failed to fetch|network error|load failed/i.test(msg) ? t("extractErrorServer") : msg;
    };

    setResults({
      recommendations: recR.status === "fulfilled" ? recR.value : null,
      position:        posR.status === "fulfilled" ? posR.value : null,
      safestPath:      pathR.status === "fulfilled" ? pathR.value : null,
      earlySignals:    earlyR.status === "fulfilled" ? earlyR.value : null,
      general:         genR.status === "fulfilled" ? genR.value : null,
    });
    setSectionErrors({
      recommendations: recR.status === "rejected" ? toErr(recR) : undefined,
      position:        posR.status === "rejected" ? toErr(posR) : undefined,
      safestPath:      pathR.status === "rejected" ? toErr(pathR) : undefined,
      earlySignals:    earlyR.status === "rejected" ? toErr(earlyR) : undefined,
      general:         genR.status === "rejected" ? toErr(genR) : undefined,
    });

    if (Array.isArray(ctx.medications) && ctx.medications.length > 0) {
      setDrugInput(ctx.medications.join(", "));
    }
    // Clear draft once guidance has been fetched
    try {
      localStorage.removeItem("health_nav_draft_intro");
      localStorage.removeItem("health_nav_draft_context");
    } catch { /* ignore */ }
    setLoading(false);
  };

  const retrySection = async (key: SectionKey, fetchFn: (ctx: UserContext) => Promise<unknown>) => {
    if (!lastContext) return;
    setSectionRetrying(key);
    setSectionErrors(prev => ({ ...prev, [key]: undefined }));
    try {
      const result = await fetchFn(lastContext);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setResults(prev => ({ ...prev, [key]: result as any }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Request failed";
      setSectionErrors(prev => ({
        ...prev,
        [key]: /failed to fetch|network error|load failed/i.test(msg) ? t("extractErrorServer") : msg,
      }));
    } finally {
      setSectionRetrying(null);
    }
  };

  // When we have results and medications in context, auto-fetch drug substitution once so guidance feels more specific.
  useEffect(() => {
    if (!lastContext || !results.recommendations || didAutoFetchDrug.current) return;
    const meds = lastContext.medications;
    if (!Array.isArray(meds) || meds.length === 0) return;
    didAutoFetchDrug.current = true;
    setDrugSubstitutionLoading(true);
    setDrugSubstitutionError(null);
    fetchDrugSubstitution(meds)
      .then(setDrugSubstitution)
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Request failed";
        const isNetworkError = /failed to fetch|network error|load failed/i.test(msg);
        setDrugSubstitutionError(isNetworkError ? t("extractErrorServer") : msg);
      })
      .finally(() => setDrugSubstitutionLoading(false));
  }, [lastContext, results.recommendations]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-50 sm:text-2xl">{t("home.title")}</h1>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="rounded-lg border border-gray-200 bg-white p-1.5 text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          </button>
          <div className="flex rounded-lg border border-gray-200 bg-white p-0.5 text-sm dark:border-gray-700 dark:bg-gray-800">
            <button type="button" onClick={() => setLocale("en")} className={"rounded-md px-3 py-1.5 " + (locale === "en" ? "bg-gray-100 font-medium dark:bg-gray-700" : "text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-700")}>EN</button>
            <button type="button" onClick={() => setLocale("ko")} className={"rounded-md px-3 py-1.5 " + (locale === "ko" ? "bg-gray-100 font-medium dark:bg-gray-700" : "text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-700")}>한글</button>
          </div>
        </div>
      </div>
      <p className="mb-8 text-gray-600 leading-relaxed">{t("home.intro")}</p>

      {!showShortForm && extractedContext == null && (
        <div className="mb-8">
          <SelfIntroBlock
            onContinue={handleContinueIntro}
            loading={extractLoading}
            initialText={introText}
          />
          {extractError && (
            <p className="mt-2 text-sm text-red-600">{extractError}</p>
          )}
          <p className="mt-4 text-center text-sm text-gray-500">
            {t("preferShort")}{" "}
            <button type="button" onClick={() => setShowShortForm(true)} className="text-blue-600 hover:underline">{t("useShortForm")}</button>
          </p>
        </div>
      )}

      {!showShortForm && extractedContext != null && (
        <div className="mb-8">
          <EditableContextSummary
            context={extractedContext}
            onChange={setExtractedContext}
            onGetGuidance={() => handleSubmit(extractedContext)}
            loading={loading}
            minimal={!!minimalInfo}
            inferred={inferredFields}
            followUp={followUpQuestions}
            onFollowUpResolved={(updatedCtx, resolvedQuestions) => {
              setExtractedContext(updatedCtx);
              setFollowUpQuestions((prev) => prev.filter((q) => !resolvedQuestions.includes(q.field)));
              setInferredFields((prev) => prev.filter((f) => !resolvedQuestions.includes(f)));
            }}
          />
          <p className="mt-3 text-center text-sm text-gray-500">
            <button
              type="button"
              onClick={() => setExtractedContext(null)}
              className="text-blue-600 hover:underline"
            >
              {t("rewriteIntro")}
            </button>
          </p>
        </div>
      )}

      {showShortForm && (
        <div className="mb-8">
          <UserContextForm onSubmit={handleSubmit} loading={loading} initialContext={restoredContext} />
          <p className="mt-3 text-center text-sm text-gray-500">
            <button type="button" onClick={() => setShowShortForm(false)} className="text-blue-600 hover:underline">
              {t("orOwnWords")}
            </button>
          </p>
        </div>
      )}

      <section className="mb-8 rounded-lg border border-slate-200 bg-slate-50 p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800/60">
        <h2 className="mb-2 text-base font-semibold text-slate-800">{t("privacy.title")}</h2>
        <p className="mb-3 text-sm text-slate-600 leading-relaxed">{t("privacy.desc")}</p>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end sm:gap-3">
          <button
            type="button"
            onClick={async () => {
              const ctx = lastContext;
              if (!ctx) {
                setSaveRestoreError(t("saveFirst"));
                return;
              }
              setSaveRestoreLoading(true);
              setSaveRestoreError(null);
              setSavedToken(null);
              try {
                const { restore_token } = await saveContext(ctx);
                setSavedToken(restore_token);
              } catch (e) {
                setSaveRestoreError(e instanceof Error ? e.message : "Saving isn’t available right now. Your data is still only on your device.");
              } finally {
                setSaveRestoreLoading(false);
              }
            }}
            disabled={saveRestoreLoading || !lastContext}
            className="rounded bg-slate-700 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {saveRestoreLoading ? t("saving") : t("saveButton")}
          </button>
          {savedToken && (
            <div className="rounded bg-green-100 px-3 py-2 text-sm text-green-800">
              {t("savedMessage")} <strong className="font-mono">{savedToken}</strong> {t("savedHint")}
            </div>
          )}
        </div>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end sm:gap-2">
          <input
            type="text"
            placeholder={t("restorePlaceholder")}
            value={restoreToken}
            onChange={(e) => setRestoreToken(e.target.value)}
            className="w-full rounded border border-gray-300 bg-white px-2 py-1.5 text-sm font-mono dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 sm:w-auto sm:min-w-[140px]"
          />
          <button
            type="button"
            onClick={async () => {
              if (!restoreToken.trim()) return;
              setSaveRestoreLoading(true);
              setSaveRestoreError(null);
              try {
                const ctx = await restoreContext(restoreToken);
                setRestoredContext(ctx);
                setRestoreToken("");
                setSavedToken(null);
              } catch (e) {
                setSaveRestoreError(e instanceof Error ? e.message : t("restoreFailed"));
              } finally {
                setSaveRestoreLoading(false);
              }
            }}
            disabled={saveRestoreLoading}
            className="rounded bg-slate-700 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {t("restoreButton")}
          </button>
        </div>
        {saveRestoreError && (
          <p className="mt-2 text-sm text-red-600">{saveRestoreError}</p>
        )}
      </section>

      {(loading || Object.values(results).some(Boolean)) && (
        <div className="mb-4">
          <EvidenceLegend />
        </div>
      )}

      {results.recommendations && inputSummaryLines.length > 0 && (
        <section className="mb-6 rounded-lg border border-slate-200 bg-slate-50 p-3 shadow-sm dark:border-gray-700 dark:bg-gray-800/60">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">{t("inputSummary.title")}</h2>
          <ul className="space-y-1 text-sm text-slate-600">
            {inputSummaryLines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-500">{t("inputSummary.hint")}</p>
        </section>
      )}

      {(loading || sectionErrors.general || results.general) && (
        <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          {summary.labels.general && <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">{summary.labels.general}</p>}
          <h2 className="mb-3 text-lg font-semibold text-gray-800 dark:text-gray-100">General guidance (why pay attention)</h2>
          {loading && !results.general && !sectionErrors.general && <SectionSkeleton lines={3} />}
          {sectionErrors.general && (
            <div className="flex items-center justify-between rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <span>{sectionErrors.general}</span>
              <button onClick={() => retrySection("general", fetchGeneralGuidance)} disabled={sectionRetrying === "general"} className="ml-3 rounded bg-red-100 px-2 py-1 text-xs font-medium hover:bg-red-200 disabled:opacity-50">
                {sectionRetrying === "general" ? "Retrying…" : "Retry"}
              </button>
            </div>
          )}
          {results.general && (
            <>
              {results.general.food_guidance_summary && (
                <p className="mb-3 text-sm text-gray-700">{results.general.food_guidance_summary}</p>
              )}
              {results.general.age_related_changes.length > 0 && (
                <ul className="space-y-2">
                  {results.general.age_related_changes.map((a, i) => (
                    <li key={i} className="rounded border border-gray-100 p-2 dark:border-gray-700">
                      <span className="font-medium">{a.change}</span>
                      {a.life_stage && <span className="ml-2 text-xs text-gray-500">({a.life_stage})</span>}
                      <p className="text-sm text-gray-600">{a.why_pay_attention}</p>
                      <EvidenceBlock evidenceList={a.evidence} variant="knowledge" />
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      )}

      {(loading || sectionErrors.position || results.position) && (
        <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          {summary.labels.position && <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">{summary.labels.position}</p>}
          <h2 className="mb-3 text-lg font-semibold text-gray-800 dark:text-gray-100">Your position &amp; nearby risks</h2>
          {loading && !results.position && !sectionErrors.position && <SectionSkeleton lines={3} />}
          {sectionErrors.position && (
            <div className="flex items-center justify-between rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <span>{sectionErrors.position}</span>
              <button onClick={() => retrySection("position", fetchPosition)} disabled={sectionRetrying === "position"} className="ml-3 rounded bg-red-100 px-2 py-1 text-xs font-medium hover:bg-red-200 disabled:opacity-50">
                {sectionRetrying === "position" ? "Retrying…" : "Retry"}
              </button>
            </div>
          )}
          {results.position && (results.position.nearby_risks.length > 0 || (results.position.active_conditions?.length ?? 0) > 0 || (results.position.active_symptoms?.length ?? 0) > 0) && (
            <>
              {results.position.active_conditions?.length > 0 && (
                <p className="text-sm text-gray-600">Conditions: {results.position.active_conditions.join(", ")}</p>
              )}
              {results.position.active_symptoms?.length > 0 && (
                <p className="text-sm text-gray-600">Symptoms: {results.position.active_symptoms.join(", ")}</p>
              )}
              {results.position.nearby_risks.length > 0 && (
                <ul className="mt-2 space-y-2">
                  {results.position.nearby_risks.map((risk, i) => (
                    <li key={i} className="rounded border border-gray-100 p-2 dark:border-gray-700">
                      <span className="font-medium">{risk.name}</span>
                      <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-800">{risk.kind}</span>
                      <p className="text-sm text-gray-600">{risk.reason}</p>
                      {risk.evidence?.length > 0 && <EvidenceBlock evidenceList={risk.evidence} variant="info" />}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      )}

      {(loading || sectionErrors.recommendations || results.recommendations) && (
        <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          {summary.labels.recommendations && <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">{summary.labels.recommendations}</p>}
          <h2 className="mb-3 text-lg font-semibold text-gray-800 dark:text-gray-100">Recommended foods</h2>
          {loading && !results.recommendations && !sectionErrors.recommendations && <SectionSkeleton lines={4} />}
          {sectionErrors.recommendations && (
            <div className="flex items-center justify-between rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <span>{sectionErrors.recommendations}</span>
              <button onClick={() => retrySection("recommendations", fetchRecommendations)} disabled={sectionRetrying === "recommendations"} className="ml-3 rounded bg-red-100 px-2 py-1 text-xs font-medium hover:bg-red-200 disabled:opacity-50">
                {sectionRetrying === "recommendations" ? "Retrying…" : "Retry"}
              </button>
            </div>
          )}
          {results.recommendations && (
            <>
              <ul className="space-y-3">
                {results.recommendations.recommended.map((r, i) => (
                  <li key={i} className="rounded border border-green-100 bg-green-50/50 p-2 dark:border-green-900 dark:bg-green-900/20">
                    <span className="font-medium text-green-800">{r.food}</span>
                    <p className="text-sm text-gray-700">{r.reason}</p>
                    <EvidenceBlock evidenceList={r.evidence} variant="knowledge" />
                  </li>
                ))}
              </ul>
              <h2 className="mb-3 mt-4 text-lg font-semibold text-gray-800">Foods to limit</h2>
              <ul className="space-y-3">
                {results.recommendations.restricted.map((r, i) => (
                  <li key={i} className="rounded border border-amber-100 bg-amber-50/50 p-2 dark:border-amber-900 dark:bg-amber-900/20">
                    <span className="font-medium text-amber-800">{r.food}</span>
                    <p className="text-sm text-gray-700">{r.reason}</p>
                    <EvidenceBlock evidenceList={r.evidence} variant="knowledge" />
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {results.recommendations && lastContext && (
        <ClinicalInsights
          conditions={lastContext.conditions ?? []}
          medications={lastContext.medications ?? []}
        />
      )}

      {(loading || sectionErrors.safestPath || results.safestPath) && (
        <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          {summary.labels.safestPath && <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">{summary.labels.safestPath}</p>}
          <h2 className="mb-3 text-lg font-semibold text-gray-800 dark:text-gray-100">Safest path (evacuation to safety)</h2>
          {loading && !results.safestPath && !sectionErrors.safestPath && <SectionSkeleton lines={3} />}
          {sectionErrors.safestPath && (
            <div className="flex items-center justify-between rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <span>{sectionErrors.safestPath}</span>
              <button onClick={() => retrySection("safestPath", fetchSafestPath)} disabled={sectionRetrying === "safestPath"} className="ml-3 rounded bg-red-100 px-2 py-1 text-xs font-medium hover:bg-red-200 disabled:opacity-50">
                {sectionRetrying === "safestPath" ? "Retrying…" : "Retry"}
              </button>
            </div>
          )}
          {results.safestPath && results.safestPath.steps.length > 0 && (
            <ul className="space-y-3">
              {results.safestPath.steps.map((step, i) => (
                <li key={i} className="rounded border border-amber-200 bg-amber-50/30 p-2 dark:border-amber-800 dark:bg-amber-900/20">
                  <p className="font-medium text-amber-900">{step.action}</p>
                  <p className="text-sm text-gray-700">{step.reason}</p>
                  <EvidenceBlock evidenceList={step.evidence} variant="wisdom" />
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {(loading || sectionErrors.earlySignals || results.earlySignals) && (
        <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          {summary.labels.earlySignals && <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">{summary.labels.earlySignals}</p>}
          <h2 className="mb-3 text-lg font-semibold text-gray-800 dark:text-gray-100">Early signals (prepare in advance)</h2>
          {loading && !results.earlySignals && !sectionErrors.earlySignals && <SectionSkeleton lines={3} />}
          {sectionErrors.earlySignals && (
            <div className="flex items-center justify-between rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <span>{sectionErrors.earlySignals}</span>
              <button onClick={() => retrySection("earlySignals", fetchEarlySignals)} disabled={sectionRetrying === "earlySignals"} className="ml-3 rounded bg-red-100 px-2 py-1 text-xs font-medium hover:bg-red-200 disabled:opacity-50">
                {sectionRetrying === "earlySignals" ? "Retrying…" : "Retry"}
              </button>
            </div>
          )}
          {results.earlySignals && (results.earlySignals.early_signals.length > 0 || results.earlySignals.foods_that_reduce.length > 0 || results.earlySignals.foods_to_avoid.length > 0) && (
            <>
              {results.earlySignals.early_signals.length > 0 && (
                <>
                  <h3 className="text-sm font-medium text-gray-700">Signals to watch</h3>
                  <ul className="mb-3 space-y-2">
                    {results.earlySignals.early_signals.map((s, i) => (
                      <li key={i} className="text-sm">
                        <span className="font-medium">{s.symptom}</span> → <span className="font-medium">{s.disease}</span>
                        <EvidenceBlock evidenceList={s.evidence} variant="info" />
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {results.earlySignals.foods_that_reduce.length > 0 && (
                <>
                  <h3 className="text-sm font-medium text-gray-700">Foods that may reduce</h3>
                  <ul className="mb-3 space-y-1">
                    {results.earlySignals.foods_that_reduce.map((r, i) => (
                      <li key={i} className="text-sm text-green-700">{r.food} — {r.reason}</li>
                    ))}
                  </ul>
                </>
              )}
              {results.earlySignals.foods_to_avoid.length > 0 && (
                <>
                  <h3 className="text-sm font-medium text-gray-700">Foods to avoid</h3>
                  <ul className="space-y-1">
                    {results.earlySignals.foods_to_avoid.map((r, i) => (
                      <li key={i} className="text-sm text-amber-700">{r.food} — {r.reason}</li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </section>
      )}

      {!loading && !sectionErrors.recommendations && results.recommendations && results.recommendations.recommended.length === 0 && results.recommendations.restricted.length === 0 && (
        <p className="text-sm text-gray-500">{t("noRecs")}</p>
      )}

      <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
        {summary.labels.drugSubstitution && <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">{summary.labels.drugSubstitution}</p>}
        <h2 className="mb-3 text-lg font-semibold text-gray-800 dark:text-gray-100">{t("drugSection.title")}</h2>
        <p className="mb-3 text-sm text-gray-600 leading-relaxed">
          {t("drugSection.desc")}
        </p>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <input
            type="text"
            placeholder="e.g. Metformin (comma-separated for multiple)"
            value={drugInput}
            onChange={(e) => setDrugInput(e.target.value)}
            className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 sm:w-auto sm:min-w-[200px]"
          />
          <button
            type="button"
            onClick={async () => {
              const drugs = drugInput.split(",").map((d) => d.trim()).filter(Boolean);
              if (!drugs.length) return;
              setDrugSubstitutionLoading(true);
              setDrugSubstitutionError(null);
              setDrugSubstitution(null);
              try {
                const res = await fetchDrugSubstitution(drugs);
                setDrugSubstitution(res);
              } catch (e) {
                const msg = e instanceof Error ? e.message : "Request failed";
                const isNetworkError = /failed to fetch|network error|load failed/i.test(msg);
                setDrugSubstitutionError(isNetworkError ? t("extractErrorServer") : msg);
              } finally {
                setDrugSubstitutionLoading(false);
              }
            }}
            disabled={drugSubstitutionLoading}
            className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {drugSubstitutionLoading ? t("drugSearching") : t("drugSearch")}
          </button>
        </div>
        {drugSubstitutionError && (
          <div className="mb-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-800">{drugSubstitutionError}</div>
        )}
        {drugSubstitution && (
          <>
            {drugSubstitution.by_drug.length === 0 ? (
              <p className="text-sm text-gray-500">{t("drugEmpty")}</p>
            ) : (
              <ul className="space-y-4">
                {drugSubstitution.by_drug.map((item, i) => (
                  <li key={i} className="rounded border border-gray-100 p-3">
                    <h3 className="mb-2 font-medium text-gray-800">{item.drug}</h3>
                    {item.substitutes.length > 0 && (
                      <div className="mb-2">
                        <h4 className="text-xs font-medium uppercase text-green-700">Substitutes</h4>
                        <ul className="mt-1 space-y-1">
                          {item.substitutes.map((s, j) => (
                            <li key={j} className="rounded border border-green-100 bg-green-50/50 p-2 text-sm">
                              <span className="font-medium text-green-800">{s.food_or_ingredient}</span>
                              <p className="text-gray-700">{s.reason}</p>
                              <EvidenceBlock evidenceList={s.evidence} variant="knowledge" />
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {item.complements.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium uppercase text-blue-700">Complements</h4>
                        <ul className="mt-1 space-y-1">
                          {item.complements.map((c, j) => (
                            <li key={j} className="rounded border border-blue-100 bg-blue-50/50 p-2 text-sm">
                              <span className="font-medium text-blue-800">{c.food_or_ingredient}</span>
                              <p className="text-gray-700">{c.reason}</p>
                              <EvidenceBlock evidenceList={c.evidence} variant="info" />
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {drugSubstitution.disclaimer && (
              <p className="mt-3 text-xs text-gray-500">{drugSubstitution.disclaimer}</p>
            )}
          </>
        )}
      </section>

      <footer className="mt-10 border-t border-gray-200 pt-4 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
        <Link href="/kg" className="text-blue-600 hover:underline">
          Knowledge Graph — Status
        </Link>
        {" · "}
        <Link href="/clinical" className="text-blue-600 hover:underline">
          Clinical Explorer
        </Link>
        {" · "}
        <Link href="/map" className="text-blue-600 hover:underline">
          Health Map
        </Link>
      </footer>
    </main>
  );
}

function MoonIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
    </svg>
  );
}
