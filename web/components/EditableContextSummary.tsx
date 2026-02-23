"use client";

import { useState } from "react";
import type { UserContext, FollowUpQuestion } from "@/lib/types";
import { useLocale } from "@/contexts/LocaleContext";

type Section = "conditions" | "symptoms" | "medications" | "goals";

const SECTION_KEYS: Record<Section, string> = {
  conditions: "conditionsLabel",
  symptoms: "symptomsLabel",
  medications: "medicationsLabel",
  goals: "goalsLabel",
};

function ensureArray(v: string[] | undefined | null): string[] {
  return Array.isArray(v) ? v : [];
}

/** Amber "Our guess" badge shown on inferred field values. */
function GuessBadge() {
  return (
    <span className="ml-1.5 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
      our guess
    </span>
  );
}

/** Inline follow-up question card for a single field. */
function FollowUpCard({
  q,
  onConfirm,
  onEdit,
  onDismiss,
}: {
  q: FollowUpQuestion;
  onConfirm?: (value: string) => void;
  onEdit?: (value: string) => void;
  onDismiss?: () => void;
}) {
  const [editMode, setEditMode] = useState(false);
  const [inputVal, setInputVal] = useState(q.value ?? "");

  if (q.type === "confirm") {
    return (
      <div className="flex flex-wrap items-start gap-2 rounded-lg bg-white border border-amber-200 px-3 py-2 text-sm">
        <span className="text-gray-700 flex-1">{q.question}</span>
        {!editMode ? (
          <span className="flex gap-1.5">
            <button
              type="button"
              onClick={() => { onConfirm?.(q.value!); onDismiss?.(); }}
              className="rounded bg-amber-500 px-2.5 py-1 text-xs font-medium text-white hover:bg-amber-600"
            >
              Yes, that&apos;s right
            </button>
            <button
              type="button"
              onClick={() => setEditMode(true)}
              className="rounded bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
            >
              No, let me fix it
            </button>
          </span>
        ) : (
          <span className="flex flex-wrap items-center gap-1.5">
            <input
              type={q.field === "age" ? "number" : "text"}
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder={q.hint ?? ""}
              className="min-w-[80px] rounded border border-gray-300 px-2 py-1 text-sm"
              autoFocus
            />
            <button
              type="button"
              onClick={() => { if (inputVal.trim()) { onEdit?.(inputVal.trim()); onDismiss?.(); } }}
              className="rounded bg-blue-600 px-2.5 py-1 text-xs text-white hover:bg-blue-700"
            >
              Save
            </button>
            <button type="button" onClick={() => { setEditMode(false); onDismiss?.(); }} className="text-xs text-gray-500 hover:underline">
              Skip
            </button>
          </span>
        )}
      </div>
    );
  }

  if (q.type === "number" || q.type === "text") {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-lg bg-white border border-amber-200 px-3 py-2 text-sm">
        <span className="text-gray-700 flex-1">{q.question}</span>
        <input
          type={q.type === "number" ? "number" : "text"}
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder={q.hint ?? ""}
          className="min-w-[100px] max-w-[180px] rounded border border-gray-300 px-2 py-1 text-sm"
          onKeyDown={(e) => {
            if (e.key === "Enter" && inputVal.trim()) {
              onEdit?.(inputVal.trim());
              onDismiss?.();
            }
          }}
        />
        <button
          type="button"
          onClick={() => { if (inputVal.trim()) { onEdit?.(inputVal.trim()); onDismiss?.(); } }}
          className="rounded bg-blue-600 px-2.5 py-1 text-xs text-white hover:bg-blue-700"
        >
          Add
        </button>
        <button type="button" onClick={onDismiss} className="text-xs text-gray-400 hover:underline">
          Skip
        </button>
      </div>
    );
  }

  if (q.type === "select" && q.options) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-lg bg-white border border-amber-200 px-3 py-2 text-sm">
        <span className="text-gray-700">{q.question}</span>
        <span className="flex gap-1.5 flex-wrap">
          {q.options.map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => { onEdit?.(opt === "prefer not to say" ? "" : opt); onDismiss?.(); }}
              className="rounded bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-amber-100 hover:text-amber-800"
            >
              {opt}
            </button>
          ))}
        </span>
      </div>
    );
  }

  return null;
}

export function EditableContextSummary({
  context,
  onChange,
  onGetGuidance,
  loading,
  minimal,
  inferred = [],
  followUp = [],
  onFollowUpResolved,
}: {
  context: UserContext;
  onChange: (ctx: UserContext) => void;
  onGetGuidance: () => void;
  loading: boolean;
  minimal: boolean;
  inferred?: string[];
  followUp?: FollowUpQuestion[];
  onFollowUpResolved?: (updatedCtx: UserContext, resolvedFields: string[]) => void;
}) {
  const [adding, setAdding] = useState<Section | null>(null);
  const [addValue, setAddValue] = useState("");
  const { t } = useLocale();

  const update = (patch: Partial<UserContext>) => {
    onChange({ ...context, ...patch });
  };

  const addItem = (section: Section) => {
    const val = addValue.trim();
    if (!val) return;
    const arr = ensureArray(context[section]);
    if (arr.includes(val)) { setAddValue(""); setAdding(null); return; }
    update({ [section]: [...arr, val] });
    setAddValue("");
    setAdding(null);
  };

  const removeItem = (section: Section, index: number) => {
    const arr = [...ensureArray(context[section])];
    arr.splice(index, 1);
    update({ [section]: arr });
  };

  const resolveFollowUp = (field: string, rawValue: string) => {
    const val = rawValue.trim();
    let patch: Partial<UserContext> = {};
    if (field === "age") {
      const n = parseInt(val, 10);
      if (!isNaN(n) && n > 0) patch = { age: n };
    } else if (field === "gender") {
      patch = { gender: val || undefined };
    } else if (field === "conditions") {
      if (val) {
        const existing = ensureArray(context.conditions);
        if (!existing.includes(val)) patch = { conditions: [...existing, val] };
      }
    } else if (field === "goals") {
      if (val) {
        const existing = ensureArray(context.goals);
        if (!existing.includes(val)) patch = { goals: [...existing, val] };
      }
    }
    const updated = { ...context, ...patch };
    onFollowUpResolved?.(updated, [field]);
    onChange(updated);
  };

  const dismissFollowUp = (field: string) => {
    onFollowUpResolved?.({ ...context }, [field]);
  };

  const sections: Section[] = ["conditions", "symptoms", "medications", "goals"];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-2 text-lg font-semibold text-gray-900">{t("understood.title")}</h2>
      <p className="mb-4 text-sm text-gray-600 leading-relaxed">{t("understood.desc")}</p>

      {/* Follow-up questions */}
      {followUp.length > 0 && (
        <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-3 space-y-2">
          <p className="text-sm font-medium text-amber-800">
            {inferred.length > 0
              ? "We made a few guesses — can you help us confirm?"
              : "A couple of quick questions to sharpen your guidance:"}
          </p>
          {followUp.map((q) => (
            <FollowUpCard
              key={q.field + q.question}
              q={q}
              onConfirm={(v) => resolveFollowUp(q.field, v)}
              onEdit={(v) => resolveFollowUp(q.field, v)}
              onDismiss={() => dismissFollowUp(q.field)}
            />
          ))}
        </div>
      )}

      <div className="space-y-4">
        {/* Age */}
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm font-medium text-gray-700">{t("age")}</label>
          <input
            type="number"
            min={1}
            max={120}
            value={context.age ?? ""}
            onChange={(e) => update({ age: e.target.value ? parseInt(e.target.value, 10) : undefined })}
            placeholder="—"
            aria-label={t("age")}
            className={`w-20 rounded border px-2 py-1.5 text-sm ${
              inferred.includes("age") ? "border-amber-300 bg-amber-50" : "border-gray-300"
            }`}
          />
          {inferred.includes("age") && <GuessBadge />}
        </div>

        {/* Gender */}
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm font-medium text-gray-700">{t("gender")}</label>
          <input
            type="text"
            value={context.gender ?? ""}
            onChange={(e) => update({ gender: e.target.value || undefined })}
            placeholder={t("optional")}
            className={`min-w-[120px] rounded border px-2 py-1.5 text-sm ${
              inferred.includes("gender") ? "border-amber-300 bg-amber-50" : "border-gray-300"
            }`}
          />
          {inferred.includes("gender") && <GuessBadge />}
        </div>

        {/* Conditions, Symptoms, Medications, Goals */}
        {sections.map((section) => (
          <div key={section}>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">
                {t(SECTION_KEYS[section])}
                {inferred.includes(section) && <GuessBadge />}
              </span>
              {adding !== section ? (
                <button
                  type="button"
                  onClick={() => setAdding(section)}
                  className="text-xs text-blue-600 hover:underline"
                >
                  + {t("add")}
                </button>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              {ensureArray(context[section]).map((item, i) => (
                <span
                  key={i}
                  className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm ${
                    inferred.includes(section)
                      ? "bg-amber-100 text-amber-900"
                      : "bg-gray-100 text-gray-800"
                  }`}
                >
                  {item}
                  <button
                    type="button"
                    onClick={() => removeItem(section, i)}
                    className="rounded-full p-0.5 hover:bg-gray-200"
                    aria-label={`Remove ${item}`}
                  >
                    ×
                  </button>
                </span>
              ))}
              {ensureArray(context[section]).length === 0 && adding !== section && (
                <span className="text-xs text-gray-400">—</span>
              )}
              {adding === section && (
                <span className="inline-flex flex-wrap items-center gap-2">
                  <input
                    type="text"
                    value={addValue}
                    onChange={(e) => setAddValue(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addItem(section)}
                    placeholder={`${t("add")} ${t(SECTION_KEYS[section])}`}
                    className="min-w-[120px] rounded border border-gray-300 px-2 py-1 text-sm"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={() => addItem(section)}
                    className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-700"
                  >
                    {t("add")}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setAdding(null); setAddValue(""); }}
                    className="text-sm text-gray-500 hover:underline"
                  >
                    {t("cancel")}
                  </button>
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {minimal && (
        <p className="mt-4 rounded-lg bg-amber-50/80 p-3 text-sm text-amber-800 leading-relaxed">
          {t("understood.minimal")}
        </p>
      )}

      <button
        type="button"
        onClick={onGetGuidance}
        disabled={loading}
        className="mt-6 w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? t("getGuidanceLoading") : t("getGuidance")}
      </button>
    </div>
  );
}
