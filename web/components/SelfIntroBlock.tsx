"use client";

import { useState, useRef, useCallback } from "react";
import { useLocale } from "@/contexts/LocaleContext";

export function SelfIntroBlock({
  onContinue,
  loading,
  initialText,
}: {
  onContinue: (text: string) => void;
  loading: boolean;
  initialText?: string;
}) {
  const [text, setText] = useState(initialText ?? "");
  const [listening, setListening] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const voiceStartTextRef = useRef("");
  const { locale, t } = useLocale();

  const startVoice = useCallback(() => {
    setVoiceError(null);
    voiceStartTextRef.current = text;
    const SpeechRecognitionAPI =
      typeof window !== "undefined" &&
      (window.SpeechRecognition || window.webkitSpeechRecognition);
    if (!SpeechRecognitionAPI) {
      setVoiceError(t("intro.voiceUnsupported"));
      return;
    }
    const rec = new SpeechRecognitionAPI();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = locale === "ko" ? "ko-KR" : "en-US";
    rec.onresult = (e: SpeechRecognitionEvent) => {
      let full = "";
      for (let i = 0; i < e.results.length; i++) {
        const segment = Array.from(e.results[i])
          .map((r) => r.transcript)
          .join("");
        if (segment) full += (full ? " " : "") + segment;
      }
      const prefix = voiceStartTextRef.current || "";
      setText(prefix ? prefix + " " + full : full);
    };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    try {
      rec.start();
      setListening(true);
      recognitionRef.current = rec;
    } catch (err) {
      setVoiceError(t("intro.voiceError"));
    }
  }, [locale, t, text]);

  const stopVoice = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (_) {}
      recognitionRef.current = null;
    }
    setListening(false);
  }, []);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h2 className="mb-2 text-xl font-semibold text-gray-900 dark:text-gray-100">{t("intro.title")}</h2>
      <p className="mb-4 text-sm text-gray-600 leading-relaxed dark:text-gray-400">{t("intro.desc")}</p>
      <div className="relative">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t("intro.placeholder")}
          rows={6}
          className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-800 placeholder:text-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:placeholder:text-gray-500"
          aria-label="Tell us about yourself"
        />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={listening ? stopVoice : startVoice}
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium ${listening ? "bg-red-100 text-red-800" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}
            aria-label={listening ? "Stop recording" : "Start voice input"}
          >
            {listening ? (
              <>{t("intro.stop")}</>
            ) : (
              <>
                <MicIcon />
                {t("intro.useVoice")}
              </>
            )}
          </button>
          {voiceError && <span className="text-xs text-amber-600">{voiceError}</span>}
        </div>
      </div>
      <button
        type="button"
        onClick={() => onContinue(text)}
        disabled={loading}
        className="mt-4 w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? t("intro.loading") : t("intro.continue")}
      </button>
    </div>
  );
}

function MicIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v3m0 0V8a5 5 0 0110 0v6z" />
    </svg>
  );
}
