"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, FileText, Loader2, SlidersHorizontal, Layers,
  AlertTriangle, Info, Hash, ChevronDown, ChevronUp,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { semanticSearch, crossSearch, type ChunkResult } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";

export default function SearchPage() {
  const { documents } = useAppStore();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"single" | "cross">("single");
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<ChunkResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    if (mode === "single" && !selectedDocId) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      if (mode === "single") {
        const res = await semanticSearch(selectedDocId, query, topK);
        if (res.ok) setResults(res.data);
      } else {
        const res = await crossSearch(query, documents.map((d) => d.id));
        if (res.ok) setResults(res.data.slice(0, topK * 2));
      }
    } catch {
      setError("Search failed. Make sure the document has been indexed (run OCR first).");
    } finally {
      setLoading(false);
    }
  };

  const scoreColor = (s: number) =>
    s >= 0.8 ? "text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800" :
    s >= 0.6 ? "text-amber-600 bg-amber-50 dark:bg-amber-900/20 dark:text-amber-400 border-amber-200 dark:border-amber-800" :
    "text-slate-600 bg-slate-50 dark:bg-slate-800 dark:text-slate-400 border-slate-200 dark:border-slate-700";

  const docName = (id: string) =>
    documents.find((d) => d.id === id)?.filename ?? id;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Search className="h-6 w-6 text-cyan-600" /> Semantic Search
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Find relevant passages using vector similarity — search within one document or across all.
        </p>
      </motion.div>

      <div className="grid lg:grid-cols-4 gap-6">
        {/* Controls */}
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
          className="lg:col-span-1 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <SlidersHorizontal className="h-4 w-4 text-cyan-600" /> Options
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Mode toggle */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Search Mode</label>
                <div className="grid grid-cols-2 gap-1.5 p-1 rounded-lg bg-muted">
                  {(["single", "cross"] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={cn(
                        "py-1.5 px-2 rounded-md text-xs font-medium transition-all",
                        mode === m
                          ? "bg-background shadow text-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {m === "single" ? "Single Doc" : "Cross-Doc"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Doc selector (single mode) */}
              {mode === "single" && (
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Document</label>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {documents.length === 0 ? (
                      <p className="text-xs text-muted-foreground p-2">No documents. Upload one first.</p>
                    ) : (
                      documents.map((d) => (
                        <button
                          key={d.id}
                          onClick={() => setSelectedDocId(d.id === selectedDocId ? "" : d.id)}
                          className={cn(
                            "w-full flex items-center gap-2 p-2 rounded-lg border text-left text-xs transition-all",
                            d.id === selectedDocId
                              ? "border-cyan-500 bg-cyan-50 dark:bg-cyan-900/20"
                              : "border-border hover:bg-muted/50"
                          )}
                        >
                          <FileText className="h-3.5 w-3.5 text-cyan-600 shrink-0" />
                          <span className="truncate">{d.filename}</span>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}

              {mode === "cross" && (
                <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 flex items-start gap-2">
                  <Layers className="h-3.5 w-3.5 text-blue-600 mt-0.5 shrink-0" />
                  <p className="text-xs text-blue-700 dark:text-blue-400">
                    Searching across {documents.length} document{documents.length !== 1 ? "s" : ""}.
                  </p>
                </div>
              )}

              {/* Top-K */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Results (top-K)</label>
                <div className="flex gap-1.5">
                  {[3, 5, 8, 10].map((k) => (
                    <button
                      key={k}
                      onClick={() => setTopK(k)}
                      className={cn(
                        "flex-1 py-1 rounded-md text-xs font-medium border transition-all",
                        topK === k
                          ? "bg-cyan-600 text-white border-cyan-600"
                          : "border-border hover:bg-muted/50"
                      )}
                    >
                      {k}
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Search + Results */}
        <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
          className="lg:col-span-3 space-y-4">
          {/* Query input */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Enter a legal question or phrase to search…"
                className="pl-10 text-sm"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>
            <Button
              className="gap-2"
              disabled={loading || !query.trim() || (mode === "single" && !selectedDocId)}
              onClick={handleSearch}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Search
            </Button>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-400">
              <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
            </div>
          )}

          {/* Results */}
          <AnimatePresence mode="wait">
            {results !== null && (
              <motion.div
                key="results"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{results.length} result{results.length !== 1 ? "s" : ""}</span>
                  {results.length === 0 && (
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Info className="h-3.5 w-3.5" />
                      Try rephrasing or ensure the document has FAISS embeddings.
                    </div>
                  )}
                </div>

                {results.map((r, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                  >
                    <Card className="overflow-hidden">
                      <div
                        className="flex items-start gap-3 p-4 cursor-pointer hover:bg-muted/30 transition-colors"
                        onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
                      >
                        <div className="h-7 w-7 rounded-lg bg-cyan-100 dark:bg-cyan-900/30 flex items-center justify-center shrink-0 mt-0.5">
                          <Hash className="h-3.5 w-3.5 text-cyan-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1.5">
                            <Badge variant="outline" className="text-xs">
                              Chunk #{r.chunk_index}
                            </Badge>
                            {mode === "cross" && (
                              <Badge variant="secondary" className="text-xs max-w-32 truncate">
                                {docName(r.doc_id)}
                              </Badge>
                            )}
                          </div>
                          <p className={cn("text-sm leading-relaxed", expandedIdx === i ? "" : "line-clamp-3")}>
                            {r.chunk_text}
                          </p>
                        </div>
                        <div className="flex flex-col items-end gap-2 shrink-0 ml-2">
                          <span className={cn("text-xs px-2 py-0.5 rounded-full font-mono font-medium border", scoreColor(r.score))}>
                            {(r.score * 100).toFixed(1)}%
                          </span>
                          {expandedIdx === i
                            ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                            : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
                        </div>
                      </div>
                    </Card>
                  </motion.div>
                ))}
              </motion.div>
            )}

            {results === null && !loading && (
              <Card className="border-dashed min-h-60 flex items-center justify-center">
                <CardContent className="text-center">
                  <Search className="h-12 w-12 mx-auto mb-3 text-muted-foreground/30" />
                  <p className="text-sm text-muted-foreground font-medium">Enter a query to begin searching.</p>
                  <p className="text-xs text-muted-foreground mt-1">Results are ranked by semantic similarity score.</p>
                </CardContent>
              </Card>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </div>
  );
}
