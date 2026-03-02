"use client";

import { useState } from "react";
import { SuggestInput } from "@/components/SuggestInput";
import { EvidenceBlock } from "@/components/EvidenceBlock";
import { fetchBiomarkers } from "@/lib/api";
import type { BiomarkerResponse } from "@/lib/types";
import { useLocale } from "@/contexts/LocaleContext";

export function BiomarkerTab() {
  const { t } = useLocale();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<BiomarkerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    const conditions = input.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
    if (!conditions.length) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchBiomarkers(conditions);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch biomarkers");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h3 className="text-lg font-semibold text-slate-800 mb-1 dark:text-gray-100">{t("clinical.biomarker.heading")}</h3>
      <p className="text-sm text-slate-500 mb-4 dark:text-gray-400">{t("clinical.biomarker.desc")}</p>

      <div className="flex gap-2 mb-6">
        <div className="flex-1">
          <SuggestInput
            value={input}
            onChange={setInput}
            placeholder={t("clinical.biomarker.placeholder")}
            field="conditions"
          />
        </div>
        <button
          type="button"
          onClick={handleSearch}
          disabled={loading || !input.trim()}
          className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50 whitespace-nowrap"
        >
          {loading ? t("clinical.biomarker.searching") : t("clinical.biomarker.search")}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">{error}</div>
      )}

      {data && (
        <>
          {data.biomarkers.length === 0 ? (
            <p className="text-sm text-slate-500">{t("clinical.biomarker.empty")}</p>
          ) : (
            <div className="space-y-4">
              {data.biomarkers.map((bm, i) => (
                <div key={i} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="inline-block h-3 w-3 rounded-full bg-teal-500 flex-shrink-0" />
                    <h4 className="font-semibold text-slate-800 dark:text-gray-100">{bm.biomarker}</h4>
                    <span className="text-xs text-slate-400 dark:text-gray-500">for</span>
                    <span className="text-sm font-medium text-red-700 dark:text-red-400">{bm.disease}</span>
                  </div>

                  <EvidenceBlock
                    evidenceList={[{
                      source_id: bm.evidence.source_id,
                      source_type: "PMC",
                      context: bm.evidence.context,
                      journal: bm.evidence.journal,
                      pub_date: bm.evidence.pub_date,
                    }]}
                    variant="knowledge"
                  />

                  {bm.food_recommendations.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2 dark:text-gray-400">
                        {t("clinical.biomarker.foodRecs")}
                      </p>
                      <div className="space-y-1.5">
                        {bm.food_recommendations.map((fr, j) => (
                          <div key={j} className="flex items-start gap-2 text-sm">
                            <span className={`mt-0.5 text-xs font-bold ${fr.direction === "increases" ? "text-green-600" : "text-blue-600"}`}>
                              {fr.direction === "increases" ? "↑" : "↓"}
                            </span>
                            <div>
                              <span className="font-medium text-slate-800 dark:text-gray-100">{fr.food}</span>
                              <span className="text-slate-500 ml-1 dark:text-gray-400">
                                ({t(`clinical.biomarker.${fr.direction}`)})
                              </span>
                              <p className="text-xs text-slate-500 dark:text-gray-400">{fr.context}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {data.disclaimer && (
            <p className="mt-4 text-xs text-slate-400">{data.disclaimer}</p>
          )}
        </>
      )}
    </div>
  );
}
