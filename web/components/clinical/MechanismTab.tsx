"use client";

import { useState } from "react";
import { SuggestInput } from "@/components/SuggestInput";
import { EvidenceBlock } from "@/components/EvidenceBlock";
import { fetchMechanisms } from "@/lib/api";
import type { MechanismResponse } from "@/lib/types";
import { MechanismChainSVG } from "./MechanismChainSVG";
import { useLocale } from "@/contexts/LocaleContext";

export function MechanismTab() {
  const { t } = useLocale();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<MechanismResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    const disease = input.split(/[,;]/)[0]?.trim();
    if (!disease) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchMechanisms(disease);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch mechanisms");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h3 className="text-lg font-semibold text-slate-800 mb-1 dark:text-gray-100">{t("clinical.mechanism.heading")}</h3>
      <p className="text-sm text-slate-500 mb-4 dark:text-gray-400">{t("clinical.mechanism.desc")}</p>

      <div className="flex gap-2 mb-6">
        <div className="flex-1">
          <SuggestInput
            value={input}
            onChange={setInput}
            placeholder={t("clinical.mechanism.placeholder")}
            field="conditions"
          />
        </div>
        <button
          type="button"
          onClick={handleSearch}
          disabled={loading || !input.trim()}
          className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50 whitespace-nowrap"
        >
          {loading ? t("clinical.mechanism.searching") : t("clinical.mechanism.search")}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">{error}</div>
      )}

      {data && (
        <>
          {data.mechanism_chains.length === 0 ? (
            <p className="text-sm text-slate-500">{t("clinical.mechanism.empty")}</p>
          ) : (
            <div className="space-y-6">
              {data.mechanism_chains.map((chain, i) => (
                <div key={i} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
                  <MechanismChainSVG chain={chain} />

                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase text-slate-400 mb-1 dark:text-gray-500">
                        {chain.food} → {chain.mechanism}
                      </p>
                      <p className="text-sm text-slate-600 dark:text-gray-300">{chain.food_to_mechanism.context}</p>
                      <EvidenceBlock
                        evidenceList={[{
                          source_id: chain.food_to_mechanism.evidence.source_id,
                          source_type: chain.food_to_mechanism.evidence.source_type,
                          context: chain.food_to_mechanism.context,
                          journal: chain.food_to_mechanism.evidence.journal,
                          pub_date: chain.food_to_mechanism.evidence.pub_date,
                        }]}
                        variant="info"
                      />
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase text-slate-400 mb-1 dark:text-gray-500">
                        {chain.mechanism} → {chain.disease}
                      </p>
                      <p className="text-sm text-slate-600 dark:text-gray-300">{chain.mechanism_to_disease.context}</p>
                      <EvidenceBlock
                        evidenceList={[{
                          source_id: chain.mechanism_to_disease.evidence.source_id,
                          source_type: chain.mechanism_to_disease.evidence.source_type,
                          context: chain.mechanism_to_disease.context,
                          journal: chain.mechanism_to_disease.evidence.journal,
                          pub_date: chain.mechanism_to_disease.evidence.pub_date,
                        }]}
                        variant="knowledge"
                      />
                    </div>
                  </div>
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
