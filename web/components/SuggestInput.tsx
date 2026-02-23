"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { fetchSuggestions } from "@/lib/api";

type Field = "conditions" | "symptoms" | "medications" | "goals";

function getLastToken(value: string): string {
  const parts = value.split(/[,;]/);
  const last = parts[parts.length - 1];
  return (last ?? "").trim();
}

function replaceLastToken(value: string, replacement: string): string {
  const trimmed = value.trim();
  const idx = Math.max(trimmed.lastIndexOf(","), trimmed.lastIndexOf(";"));
  if (idx === -1) return replacement;
  const before = trimmed.slice(0, idx).trimEnd();
  const sep = trimmed.slice(idx, idx + 1);
  return before ? `${before}${sep} ${replacement}` : replacement;
}

export function SuggestInput({
  value,
  onChange,
  placeholder,
  field,
  id,
  "aria-label": ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  field: Field;
  id?: string;
  "aria-label"?: string;
}) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const lastToken = getLastToken(value);

  const load = useCallback(
    async (q: string) => {
      if (!q) {
        setSuggestions([]);
        return;
      }
      setLoading(true);
      try {
        const list = await fetchSuggestions(q, field);
        setSuggestions(list);
        setOpen(list.length > 0);
      } finally {
        setLoading(false);
      }
    },
    [field]
  );

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!lastToken) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => load(lastToken), 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [lastToken, load]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (s: string) => {
    const newValue = replaceLastToken(value, s);
    onChange(newValue);
    setOpen(false);
    setSuggestions([]);
  };

  return (
    <div ref={wrapperRef} className="relative">
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => lastToken && suggestions.length > 0 && setOpen(true)}
        placeholder={placeholder}
        aria-label={ariaLabel}
        autoComplete="off"
        className="mt-1 w-full rounded border border-gray-300 px-2 py-1.5 text-sm"
      />
      {open && suggestions.length > 0 && (
        <ul
          className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded border border-gray-200 bg-white py-1 shadow-lg"
          role="listbox"
        >
          {suggestions.map((s, i) => (
            <li
              key={i}
              role="option"
              className="cursor-pointer px-3 py-2 text-sm text-gray-800 hover:bg-blue-50"
              onMouseDown={(e) => {
                e.preventDefault();
                handleSelect(s);
              }}
            >
              {s}
            </li>
          ))}
        </ul>
      )}
      {loading && lastToken && (
        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">…</span>
      )}
    </div>
  );
}
