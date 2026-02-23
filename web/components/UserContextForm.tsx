"use client";

import { useState, useEffect } from "react";
import type { UserContext } from "@/lib/types";
import { SuggestInput } from "@/components/SuggestInput";
import { useLocale } from "@/contexts/LocaleContext";

const defaultContext: UserContext = {
  age: undefined,
  conditions: [],
  symptoms: [],
  medications: [],
  goals: [],
};

function fromContext(ctx: UserContext | null | undefined) {
  if (!ctx) return { age: "", gender: "", conditions: "", symptoms: "", medications: "", goals: "" };
  return {
    age: ctx.age != null ? String(ctx.age) : "",
    gender: ctx.gender ?? "",
    conditions: Array.isArray(ctx.conditions) ? ctx.conditions.join(", ") : "",
    symptoms: Array.isArray(ctx.symptoms) ? ctx.symptoms.join(", ") : "",
    medications: Array.isArray(ctx.medications) ? ctx.medications.join(", ") : "",
    goals: Array.isArray(ctx.goals) ? ctx.goals.join(", ") : "",
  };
}

export function UserContextForm({
  onSubmit,
  loading,
  initialContext,
}: {
  onSubmit: (ctx: UserContext) => void;
  loading: boolean;
  initialContext?: UserContext | null;
}) {
  const [age, setAge] = useState<string>("");
  const [gender, setGender] = useState<string>("");
  const [conditions, setConditions] = useState<string>("");
  const [symptoms, setSymptoms] = useState<string>("");
  const [medications, setMedications] = useState<string>("");
  const [goals, setGoals] = useState<string>("");
  const { t } = useLocale();

  useEffect(() => {
    if (initialContext == null) return;
    const v = fromContext(initialContext);
    setAge(v.age);
    setGender(v.gender);
    setConditions(v.conditions);
    setSymptoms(v.symptoms);
    setMedications(v.medications);
    setGoals(v.goals);
  }, [initialContext]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const ctx: UserContext = {
      ...defaultContext,
      age: age ? parseInt(age, 10) : undefined,
      gender: gender.trim() || undefined,
      conditions: conditions ? conditions.split(/[,;]/).map((s) => s.trim()).filter(Boolean) : [],
      symptoms: symptoms ? symptoms.split(/[,;]/).map((s) => s.trim()).filter(Boolean) : [],
      medications: medications ? medications.split(/[,;]/).map((s) => s.trim()).filter(Boolean) : [],
      goals: goals ? goals.split(/[,;]/).map((s) => s.trim()).filter(Boolean) : [],
    };
    onSubmit(ctx);
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="mb-2 text-lg font-semibold text-gray-800">{t("form.title")}</h2>
      <p className="mb-4 text-sm text-gray-600 leading-relaxed">{t("form.desc")}</p>
      <div className="space-y-4">
        <div className="rounded-md border border-gray-100 bg-gray-50/50 p-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">{t("form.basicInfo")}</p>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">{t("age")}</label>
              <input
                type="number"
                min={1}
                max={120}
                value={age}
                onChange={(e) => setAge(e.target.value)}
                className="mt-1 w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
                placeholder="e.g. 45"
                aria-label="Age"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">{t("gender")}</label>
              <input
                type="text"
                value={gender}
                onChange={(e) => setGender(e.target.value)}
                className="mt-1 w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
                placeholder={t("genderPlaceholder")}
                aria-label="Gender"
              />
            </div>
          </div>
        </div>
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">{t("form.optionalSection")}</p>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">{t("goalsLabel")}</label>
              <SuggestInput
                value={goals}
                onChange={setGoals}
                field="goals"
                placeholder="e.g. longevity, weight management"
                aria-label="Goals"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">{t("conditionsLabel")}</label>
              <SuggestInput
                value={conditions}
                onChange={setConditions}
                field="conditions"
                placeholder="e.g. Hypertension, Type 2 diabetes"
                aria-label="Conditions"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">{t("symptomsLabel")}</label>
              <SuggestInput
                value={symptoms}
                onChange={setSymptoms}
                field="symptoms"
                placeholder="e.g. fatigue, joint pain"
                aria-label="Symptoms"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">{t("medicationsLabel")}</label>
              <SuggestInput
                value={medications}
                onChange={setMedications}
                field="medications"
                placeholder="e.g. Metformin, Aspirin"
                aria-label="Medications"
              />
            </div>
          </div>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? t("getGuidanceLoading") : t("getGuidance")}
        </button>
      </div>
    </form>
  );
}
