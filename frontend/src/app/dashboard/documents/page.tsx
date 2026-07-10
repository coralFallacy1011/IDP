"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FolderOpen, FileText, Search, Trash2, Eye, Brain, ScanText,
  RefreshCw, ChevronLeft, ChevronRight, AlertTriangle, X, Calendar,
  Languages, Loader2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  listOcrDocuments, deleteOcrDocument, type OcrDocumentSummary,
} from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";
import { cn, formatDateTime, getRiskBadgeColor } from "@/lib/utils";
import Link from "next/link";

const PAGE_SIZE = 20;

export default function DocumentsPage() {
  const { removeDocument } = useAppStore();
  const [docs, setDocs] = useState<OcrDocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [langFilter, setLangFilter] = useState("all");
  const [selected, setSelected] = useState<OcrDocumentSummary | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listOcrDocuments({
        limit: PAGE_SIZE,
        skip: page * PAGE_SIZE,
        lang: langFilter === "all" ? undefined : langFilter,
      });
      setDocs(res.data);
      setTotal(res.total);
    } catch {
      setError("Could not load documents. Make sure the backend is running.");
    } finally {
      setLoading(false);
    }
  }, [page, langFilter]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document permanently?")) return;
    setDeleting(id);
    try {
      await deleteOcrDocument(id);
      removeDocument(id);
      if (selected?.id === id) setSelected(null);
      load();
    } catch {
      alert("Delete failed.");
    } finally {
      setDeleting(null);
    }
  };

  const filtered = search
    ? docs.filter((d) => d.filename.toLowerCase().includes(search.toLowerCase()))
    : docs;

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const riskBadge = (doc: OcrDocumentSummary) => {
    const level = doc.nlp?.risk?.risk_level;
    if (!level) return null;
    return (
      <span className={cn("text-xs px-1.5 py-0.5 rounded-full font-medium", getRiskBadgeColor(level))}>
        {level}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FolderOpen className="h-6 w-6 text-blue-600" /> Documents
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            All OCR-processed documents. Click a row to inspect details.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="gap-2" onClick={load}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
          <Link href="/dashboard/ocr">
            <Button size="sm" className="gap-2">
              <ScanText className="h-3.5 w-3.5" /> New OCR
            </Button>
          </Link>
        </div>
      </motion.div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-400">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      <div className="grid lg:grid-cols-5 gap-6">
        {/* Left — list */}
        <div className="lg:col-span-3 space-y-3">
          {/* Filters */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Filter by filename..."
                className="pl-9 text-sm"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Select value={langFilter} onValueChange={(v) => { setLangFilter(v); setPage(0); }}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Language" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Languages</SelectItem>
                <SelectItem value="eng">English</SelectItem>
                <SelectItem value="hin">Hindi</SelectItem>
                <SelectItem value="tam">Tamil</SelectItem>
                <SelectItem value="tel">Telugu</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Table */}
          <Card>
            <CardContent className="p-0">
              {loading ? (
                <div className="divide-y divide-border">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="flex items-center gap-3 p-3">
                      <Skeleton className="h-8 w-8 rounded-lg" />
                      <div className="flex-1 space-y-1.5">
                        <Skeleton className="h-3.5 w-48" />
                        <Skeleton className="h-3 w-32" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : filtered.length === 0 ? (
                <div className="text-center py-12">
                  <FileText className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                  <p className="text-muted-foreground text-sm">No documents found.</p>
                  <Link href="/dashboard/ocr">
                    <Button variant="outline" size="sm" className="mt-3 gap-2">
                      <ScanText className="h-3.5 w-3.5" /> Upload a document
                    </Button>
                  </Link>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {filtered.map((doc, i) => (
                    <motion.div
                      key={doc.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.03 }}
                      onClick={() => setSelected(selected?.id === doc.id ? null : doc)}
                      className={cn(
                        "flex items-center gap-3 p-3 cursor-pointer transition-colors hover:bg-muted/50",
                        selected?.id === doc.id && "bg-blue-50 dark:bg-blue-900/20"
                      )}
                    >
                      <div className="h-9 w-9 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
                        <FileText className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{doc.filename}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <Calendar className="h-3 w-3 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground">
                            {formatDateTime(doc.created_at)}
                          </span>
                          <Languages className="h-3 w-3 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground">{doc.lang_detected || doc.lang}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {riskBadge(doc)}
                        {doc.nlp?.classification && (
                          <Badge variant="outline" className="text-xs">
                            {doc.nlp.classification.doc_type}
                          </Badge>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-red-500"
                          onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }}
                          disabled={deleting === doc.id}
                        >
                          {deleting === doc.id
                            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            : <Trash2 className="h-3.5 w-3.5" />}
                        </Button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>{total} documents total</span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </Button>
                <span className="text-xs">Page {page + 1} of {totalPages}</span>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Right — detail panel */}
        <div className="lg:col-span-2">
          <AnimatePresence mode="wait">
            {selected ? (
              <motion.div
                key={selected.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="space-y-3"
              >
                <Card>
                  <CardHeader className="pb-3 flex flex-row items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <CardTitle className="text-sm truncate">{selected.filename}</CardTitle>
                      <p className="text-xs text-muted-foreground mt-0.5">{selected.id}</p>
                    </div>
                    <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={() => setSelected(null)}>
                      <X className="h-4 w-4" />
                    </Button>
                  </CardHeader>
                  <CardContent className="space-y-3 text-xs">
                    <div className="grid grid-cols-2 gap-2">
                      <div className="p-2 rounded-lg bg-muted/50 border border-border">
                        <p className="text-muted-foreground">Language</p>
                        <p className="font-medium mt-0.5">{selected.lang_detected || selected.lang}</p>
                      </div>
                      <div className="p-2 rounded-lg bg-muted/50 border border-border">
                        <p className="text-muted-foreground">Doc Type</p>
                        <p className="font-medium mt-0.5">{selected.nlp?.classification?.doc_type ?? "—"}</p>
                      </div>
                      <div className="p-2 rounded-lg bg-muted/50 border border-border">
                        <p className="text-muted-foreground">Risk Level</p>
                        <p className="font-medium mt-0.5 capitalize">{selected.nlp?.risk?.risk_level ?? "—"}</p>
                      </div>
                      <div className="p-2 rounded-lg bg-muted/50 border border-border">
                        <p className="text-muted-foreground">NLP Analyses</p>
                        <p className="font-medium mt-0.5">
                          {Object.keys(selected.nlp ?? {}).length} / 4
                        </p>
                      </div>
                    </div>

                    {selected.clean_text && (
                      <>
                        <Separator />
                        <div>
                          <p className="text-muted-foreground mb-1.5">Text preview</p>
                          <div className="rounded-lg bg-muted/50 p-3 max-h-36 overflow-y-auto">
                            <p className="font-mono text-xs leading-relaxed line-clamp-6">
                              {selected.clean_text.slice(0, 400)}…
                            </p>
                          </div>
                        </div>
                      </>
                    )}

                    {selected.nlp?.summary && (
                      <>
                        <Separator />
                        <div>
                          <p className="text-muted-foreground mb-1.5">Summary</p>
                          <p className="leading-relaxed">{selected.nlp.summary.summary}</p>
                        </div>
                      </>
                    )}

                    <Separator />
                    <div className="flex gap-2 pt-1">
                      <Link href="/dashboard/analysis" className="flex-1">
                        <Button variant="outline" size="sm" className="w-full gap-1.5 text-xs">
                          <Brain className="h-3.5 w-3.5" /> Analyse
                        </Button>
                      </Link>
                      <Link href="/dashboard/chat" className="flex-1">
                        <Button size="sm" className="w-full gap-1.5 text-xs">
                          <Eye className="h-3.5 w-3.5" /> Chat
                        </Button>
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ) : (
              <Card className="border-dashed h-full min-h-60 flex items-center justify-center">
                <CardContent className="text-center">
                  <Eye className="h-8 w-8 mx-auto mb-2 text-muted-foreground/40" />
                  <p className="text-sm text-muted-foreground">Select a document to preview details.</p>
                </CardContent>
              </Card>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
