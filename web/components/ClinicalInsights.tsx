"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { fetchBiomarkers, fetchDrugInteractions } from "@/lib/api";
import type { BiomarkerResponse, DrugInteractionResponse } from "@/lib/types";
import { useLocale } from "@/contexts/LocaleContext";

interface ClinicalInsightsProps {
  conditions: string[];
  medications: string[];
}

export function ClinicalInsights({ conditions, medications }: ClinicalInsightsProps) {
  const { t } = useLocale();
  const [biomarkers, setBiomarkers] = useState<BiomarkerResponse | null>(null);
  const [interactions, setInteractions] = useState<DrugInteractionResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (conditions.length === 0 && medications.length === 0) {
      setLoading(false);
      return;
    }

    setLoading(true);
    const promises: Promise<void>[] = [];

    if (conditions.length > 0) {
      promises.push(
        fetchBiomarkers(conditions)
          .then(setBiomarkers)
          .catch(() => {})
      );
    }

    if (medications.length > 0) {
      promises.push(
        fetchDrugInteractions(medications)
          .then(setInteractions)
          .catch(() => {})
      );
    }

    Promise.all(promises).finally(() => setLoading(false));
  }, [conditions, medications]);

  // Don't render if no data to show
  if (conditions.length === 0 && medications.length === 0) return null;

  if (loading) {
    return (
      <section className="mb-8 rounded-lg border border-teal-200 bg-teal-50/50 p-4 shadow-sm">
        <div className="flex items-center gap-2 text-sm text-teal-700">
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-teal-400 border-t-transparent" />
          {t("insights.loading")}
        </div>
      </section>
    );
  }

  const topBiomarkers = biomarkers?.biomarkers?.slice(0, 5) ?? [];
  const allContra = interactions?.interactions?.flatMap((d) =>
    d.contraindications.map((c) => ({ drug: d.drug, ...c }))
  ) ?? [];
  const topContra = allContra.slice(0, 3);

  if (topBiomarkers.length === 0 && topContra.length === 0) return null;

  return (
    <section className="mb-8 rounded-lg border border-teal-200 bg-gradient-to-br from-teal-50/80 to-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold text-teal-900">{t("insights.title")}</h2>

      {/* Biomarkers */}
      {topBiomarkers.length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-teal-600 mb-2">
            {t("insights.biomarkers")}
          </h3>
          <div className="space-y-1.5">
            {topBiomarkers.map((bm, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="inline-block h-2 w-2 rounded-full bg-teal-500 flex-shrink-0" />
                <span className="font-medium text-slate-800">{bm.biomarker}</span>
                <span className="text-slate-400">for</span>
                <span className="text-red-700">{bm.disease}</span>
                {bm.food_recommendations.length > 0 && (
                  <span className="text-xs text-slate-400 ml-1">
                    ({bm.food_recommendations.length} food rec{bm.food_recommendations.length === 1 ? "" : "s"})
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Drug interactions */}
      {topContra.length > 0 && (
        <div className="mb-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-red-600 mb-2">
            {t("insights.interactions")}
          </h3>
          <div className="space-y-1.5">
            {topContra.map((item, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <span className="mt-0.5 text-red-500 font-bold text-xs">!</span>
                <div>
                  <span className="font-medium text-red-800">{item.nutrient}</span>
                  <span className="text-slate-400 mx-1">+</span>
                  <span className="font-medium text-slate-800">{item.drug}</span>
                  <p className="text-xs text-slate-500 line-clamp-1">{item.context}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <Link
        href="/clinical"
        className="inline-block text-sm font-medium text-teal-700 hover:text-teal-900 hover:underline"
      >
        {t("insights.exploreMore")}
      </Link>
    </section>
  );
}
