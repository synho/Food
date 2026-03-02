"use client";

import Link from "next/link";
import { KgGraphExplorer } from "@/components/kg/KgGraphExplorer";

export default function KgExplorePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-4">
            <Link href="/kg" className="text-slate-500 transition hover:text-slate-800">← KG Dashboard</Link>
            <span className="text-slate-300">|</span>
            <Link href="/" className="text-slate-500 transition hover:text-slate-800">Home</Link>
            <span className="text-slate-300">|</span>
            <Link href="/clinical" className="text-slate-500 transition hover:text-slate-800">Clinical Explorer</Link>
          </div>
          <div>
            <h1 className="text-xl font-semibold text-slate-800">Knowledge Graph — Explorer</h1>
            <p className="text-xs text-slate-400 text-right">Interactive neighborhood visualization</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-slate-800">Explore the Knowledge Graph</h2>
          <p className="mt-1 text-sm text-slate-500">
            Search any entity — food, disease, nutrient, drug, biomarker or mechanism — and visualize its
            connections in the KG. Click a node to re-center the graph on that entity.
          </p>
        </div>
        <KgGraphExplorer />
      </main>
    </div>
  );
}
