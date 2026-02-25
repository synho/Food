"use client";

import { useState } from "react";
import Link from "next/link";
import { BiomarkerTab } from "@/components/clinical/BiomarkerTab";
import { MechanismTab } from "@/components/clinical/MechanismTab";
import { DrugInteractionTab } from "@/components/clinical/DrugInteractionTab";
import { useLocale } from "@/contexts/LocaleContext";

type Tab = "biomarkers" | "mechanisms" | "drugInteractions";

const TABS: { key: Tab; i18nKey: string; color: string; activeColor: string }[] = [
  { key: "biomarkers",       i18nKey: "clinical.tabBiomarkers",       color: "text-teal-600",   activeColor: "bg-teal-50 border-teal-500" },
  { key: "mechanisms",       i18nKey: "clinical.tabMechanisms",       color: "text-rose-600",   activeColor: "bg-rose-50 border-rose-500" },
  { key: "drugInteractions", i18nKey: "clinical.tabDrugInteractions", color: "text-purple-600", activeColor: "bg-purple-50 border-purple-500" },
];

export default function ClinicalExplorerPage() {
  const [activeTab, setActiveTab] = useState<Tab>("biomarkers");
  const { t } = useLocale();

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-slate-500 transition hover:text-slate-800">← Home</Link>
            <span className="text-slate-300">|</span>
            <Link href="/kg" className="text-slate-500 transition hover:text-slate-800">KG Status</Link>
            <span className="text-slate-300">|</span>
            <Link href="/map" className="text-slate-500 transition hover:text-slate-800">Health Map</Link>
            <h1 className="text-xl font-semibold text-slate-800">{t("clinical.title")}</h1>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <p className="text-sm text-slate-500 mb-6">{t("clinical.subtitle")}</p>

        {/* Tabs */}
        <div className="flex gap-2 mb-8 border-b border-slate-200">
          {TABS.map((tab) => {
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  isActive
                    ? `${tab.activeColor} ${tab.color}`
                    : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
                }`}
              >
                {t(tab.i18nKey)}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        {activeTab === "biomarkers" && <BiomarkerTab />}
        {activeTab === "mechanisms" && <MechanismTab />}
        {activeTab === "drugInteractions" && <DrugInteractionTab />}

        {/* Disclaimer */}
        <p className="mt-8 text-center text-xs text-slate-400">
          {t("clinical.disclaimer")}
        </p>
      </main>
    </div>
  );
}
