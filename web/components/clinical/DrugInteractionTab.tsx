"use client";

import { useState } from "react";
import { SuggestInput } from "@/components/SuggestInput";
import { EvidenceBlock } from "@/components/EvidenceBlock";
import { fetchDrugInteractions } from "@/lib/api";
import type { DrugInteractionResponse } from "@/lib/types";
import { useLocale } from "@/contexts/LocaleContext";

export function DrugInteractionTab() {
  const { t } = useLocale();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DrugInteractionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    const meds = input.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
    if (!meds.length) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchDrugInteractions(meds);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch drug interactions");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h3 className="text-lg font-semibold text-slate-800 mb-1">{t("clinical.drug.heading")}</h3>
      <p className="text-sm text-slate-500 mb-4">{t("clinical.drug.desc")}</p>

      <div className="flex gap-2 mb-6">
        <div className="flex-1">
          <SuggestInput
            value={input}
            onChange={setInput}
            placeholder={t("clinical.drug.placeholder")}
            field="medications"
          />
        </div>
        <button
          type="button"
          onClick={handleSearch}
          disabled={loading || !input.trim()}
          className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50 whitespace-nowrap"
        >
          {loading ? t("clinical.drug.searching") : t("clinical.drug.search")}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>
      )}

      {data && (
        <>
          {data.interactions.length === 0 ? (
            <p className="text-sm text-slate-500">{t("clinical.drug.empty")}</p>
          ) : (
            <div className="space-y-6">
              {data.interactions.map((drug, i) => (
                <div key={i} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <h4 className="text-base font-semibold text-slate-800 mb-3 flex items-center gap-2">
                    <span className="inline-block h-3 w-3 rounded-full bg-purple-500" />
                    {drug.drug}
                  </h4>

                  {/* Contraindications */}
                  {drug.contraindications.length > 0 && (
                    <div className="mb-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-red-600 mb-2">
                        {t("clinical.drug.contraindications")}
                      </p>
                      <div className="space-y-2">
                        {drug.contraindications.map((item, j) => (
                          <div key={j} className="rounded-lg border border-red-200 bg-red-50/50 p-3">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-red-800">{item.nutrient}</span>
                              <span className="text-xs text-red-500">({item.nutrient_type})</span>
                            </div>
                            <p className="text-sm text-slate-700">{item.context}</p>
                            <EvidenceBlock
                              evidenceList={[{
                                source_id: item.evidence.source_id,
                                source_type: item.evidence.source_type,
                                context: item.context,
                                journal: item.evidence.journal,
                                pub_date: item.evidence.pub_date,
                              }]}
                              variant="info"
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Complements */}
                  {drug.complements.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 mb-2">
                        {t("clinical.drug.complements")}
                      </p>
                      <div className="space-y-2">
                        {drug.complements.map((item, j) => (
                          <div key={j} className="rounded-lg border border-blue-200 bg-blue-50/50 p-3">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-blue-800">{item.nutrient}</span>
                              <span className="text-xs text-blue-500">({item.nutrient_type})</span>
                            </div>
                            <p className="text-sm text-slate-700">{item.context}</p>
                            <EvidenceBlock
                              evidenceList={[{
                                source_id: item.evidence.source_id,
                                source_type: item.evidence.source_type,
                                context: item.context,
                                journal: item.evidence.journal,
                                pub_date: item.evidence.pub_date,
                              }]}
                              variant="knowledge"
                            />
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
            <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
              {data.disclaimer}
            </p>
          )}
        </>
      )}
    </div>
  );
}
