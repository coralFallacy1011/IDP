"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain, Sparkles, FileText, Tag, AlignLeft, ShieldAlert,
  Loader2, RefreshCw, CheckCircle2, AlertTriangle, ChevronRight,
  BarChart2, Users, Building, CalendarDays, DollarSign, MapPin,
  Hash, Lightbulb,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
  classifyDocument, extractEntities, summarizeDocument, checkRisk,
  type ClassificationData, type EntityData, type SummarizationData, type RiskData,
} from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";
import {
  cn, getRiskColor, getRiskBadgeColor, formatConfidence, getConfidenceColor, formatDateTime,
} from "@/lib/utils";

type AnalysisType = "classify" | "extract" | "summarize" | "risk";

const ENTITY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  persons: Users,
  organisations: Building,
  dates: CalendarDays,
  money: DollarSign,
  locations: MapPin,
  case_numbers: Hash,
};

export default function AnalysisPage() {
  const { documents, updateDocument } = useAppStore();
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [loading, setLoading] = useState<Record<AnalysisType, boolean>>({
    classify: false, extract: false, summarize: false, risk: false,
  });

  const doc = documents.find((d) => d.id === selectedDocId);

  const run = async (type: AnalysisType, force = false) => {
    if (!selectedDocId) return;
    setLoading((prev) => ({ ...prev, [type]: true }));
    try {
      if (type === "classify") {
        const res = await classifyDocument(selectedDocId, force);
        if (res.ok) updateDocument(selectedDocId, { classification: res.data });
      } else if (type === "extract") {
        const res = await extractEntities(selectedDocId, force);
        if (res.ok) updateDocument(selectedDocId, { entities: res.data as EntityData });
      } else if (type === "summarize") {
        const res = await summarizeDocument(selectedDocId, force);
        if (res.ok) updateDocument(selectedDocId, { summary: res.data });
      } else if (type === "risk") {
        const res = await checkRisk(selectedDocId, force);
        if (res.ok) updateDocument(selectedDocId, { risk: res.data });
      }
    } catch {
      // error handled per-tab
    } finally {
      setLoading((prev) => ({ ...prev, [type]: false }));
    }
  };

  const AnalyseButton = ({ type, label }: { type: AnalysisType; label: string }) => (
    <div className="flex gap-2">
      <Button
        size="sm"
        className="gap-2"
        disabled={!selectedDocId || loading[type]}
        onClick={() => run(type)}
      >
        {loading[type] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
        {loading[type] ? "Processing…" : label}
      </Button>
      {doc?.[type === "classify" ? "classification" : type === "extract" ? "entities" : type === "summarize" ? "summary" : "risk"] && (
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          disabled={loading[type]}
          onClick={() => run(type, true)}
        >
          <RefreshCw className="h-3.5 w-3.5" /> Re-run
        </Button>
      )}
    </div>
  );

  const EntityGroup = ({ label, items, icon: Icon }: { label: string; items: string[]; icon: React.ComponentType<{ className?: string }> }) => {
    if (!items?.length) return null;
    return (
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{label}</span>
          <Badge variant="outline" className="text-xs h-4 px-1">{items.length}</Badge>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {items.map((item, i) => (
            <span
              key={i}
              className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border border-blue-200 dark:border-blue-800"
            >
              {item}
            </span>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Brain className="h-6 w-6 text-purple-600" /> AI Analysis
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Run NLP pipelines on your documents — classify, extract entities, summarize, and assess risk.
        </p>
      </motion.div>

      {/* Document selector */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Select Document</CardTitle>
        </CardHeader>
        <CardContent>
          {documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">No documents yet. <a href="/dashboard/ocr" className="text-blue-600 underline underline-offset-2">Upload one first.</a></p>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-48 overflow-y-auto pr-1">
              {documents.map((d) => (
                <button
                  key={d.id}
                  onClick={() => setSelectedDocId(d.id === selectedDocId ? "" : d.id)}
                  className={cn(
                    "flex items-center gap-3 p-2.5 rounded-lg border text-left text-sm transition-all",
                    d.id === selectedDocId
                      ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                      : "border-border hover:bg-muted/50"
                  )}
                >
                  <FileText className="h-4 w-4 text-blue-600 shrink-0" />
                  <span className="truncate text-xs">{d.filename}</span>
                  {d.id === selectedDocId && <CheckCircle2 className="h-3.5 w-3.5 text-blue-600 ml-auto shrink-0" />}
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Analysis tabs */}
      <Tabs defaultValue="classify">
        <TabsList className="mb-4">
          <TabsTrigger value="classify" className="gap-2">
            <Tag className="h-3.5 w-3.5" /> Classify
          </TabsTrigger>
          <TabsTrigger value="extract" className="gap-2">
            <Users className="h-3.5 w-3.5" /> Extract
          </TabsTrigger>
          <TabsTrigger value="summarize" className="gap-2">
            <AlignLeft className="h-3.5 w-3.5" /> Summarize
          </TabsTrigger>
          <TabsTrigger value="risk" className="gap-2">
            <ShieldAlert className="h-3.5 w-3.5" /> Risk Check
          </TabsTrigger>
        </TabsList>

        {/* ── Classify ── */}
        <TabsContent value="classify">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Tag className="h-4 w-4 text-blue-600" /> Document Classification
                </CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Identifies the legal document type using InLegalBERT.
                </p>
              </div>
              <AnalyseButton type="classify" label="Classify" />
            </CardHeader>
            <CardContent>
              <AnimatePresence>
                {doc?.classification ? (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                    <div className="flex items-center gap-4 p-4 rounded-xl bg-muted/50 border border-border">
                      <div className="h-14 w-14 rounded-xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                        <Tag className="h-6 w-6 text-blue-600" />
                      </div>
                      <div className="flex-1">
                        <p className="text-lg font-bold capitalize">{doc.classification.doc_type}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={cn("text-sm font-medium", getConfidenceColor(doc.classification.confidence))}>
                            {formatConfidence(doc.classification.confidence)} confidence
                          </span>
                          <Badge variant="outline" className="text-xs">{doc.classification.model || "InLegalBERT"}</Badge>
                        </div>
                      </div>
                    </div>

                    {doc.classification.all_scores && (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Score Distribution</p>
                        {Object.entries(doc.classification.all_scores)
                          .sort(([, a], [, b]) => b - a)
                          .map(([type, score]) => (
                            <div key={type} className="flex items-center gap-3">
                              <span className="text-xs w-32 capitalize truncate">{type}</span>
                              <Progress value={score * 100} className="flex-1 h-1.5" />
                              <span className={cn("text-xs w-10 text-right font-mono", getConfidenceColor(score))}>
                                {formatConfidence(score)}
                              </span>
                            </div>
                          ))}
                      </div>
                    )}
                  </motion.div>
                ) : (
                  <div className="text-center py-10">
                    <Tag className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
                    <p className="text-sm text-muted-foreground">No classification yet.</p>
                  </div>
                )}
              </AnimatePresence>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Extract ── */}
        <TabsContent value="extract">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Users className="h-4 w-4 text-emerald-600" /> Entity & Clause Extraction
                </CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Named entity recognition + legal clause detection.
                </p>
              </div>
              <AnalyseButton type="extract" label="Extract" />
            </CardHeader>
            <CardContent>
              {doc?.entities ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
                  <div className="space-y-4">
                    {Object.entries(ENTITY_ICONS).map(([key, Icon]) => (
                      <EntityGroup
                        key={key}
                        label={key}
                        items={(doc.entities as EntityData)?.[key as keyof EntityData] as string[] ?? []}
                        icon={Icon}
                      />
                    ))}
                  </div>

                  {(doc.entities as EntityData)?.clauses?.clauses_found?.length ? (
                    <>
                      <Separator />
                      <div>
                        <div className="flex items-center gap-1.5 mb-2">
                          <Lightbulb className="h-3.5 w-3.5 text-amber-500" />
                          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                            Detected Clauses
                          </span>
                        </div>
                        <div className="space-y-1.5">
                          {(doc.entities as EntityData).clauses!.clauses_found.map((clause, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                              <ChevronRight className="h-3 w-3 text-amber-600 shrink-0" />
                              <span className="text-amber-800 dark:text-amber-300">{clause}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  ) : null}
                </motion.div>
              ) : (
                <div className="text-center py-10">
                  <Users className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
                  <p className="text-sm text-muted-foreground">No entity data yet.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Summarize ── */}
        <TabsContent value="summarize">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div>
                <CardTitle className="text-sm flex items-center gap-2">
                  <AlignLeft className="h-4 w-4 text-cyan-600" /> Abstractive Summary
                </CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  BART-large-CNN map-reduce summarization.
                </p>
              </div>
              <AnalyseButton type="summarize" label="Summarize" />
            </CardHeader>
            <CardContent>
              {doc?.summary ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: "Word Count", value: doc.summary.word_count },
                      { label: "Compression", value: `${(doc.summary.compression_ratio * 100).toFixed(0)}%` },
                      { label: "Model", value: "BART" },
                    ].map(({ label, value }) => (
                      <div key={label} className="p-3 rounded-xl bg-muted/50 border border-border text-center">
                        <p className="text-xs text-muted-foreground">{label}</p>
                        <p className="text-sm font-bold mt-0.5">{value}</p>
                      </div>
                    ))}
                  </div>
                  <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                    <p className="text-sm leading-relaxed prose-legal">{doc.summary.summary}</p>
                  </div>
                  {doc.summary.processed_at && (
                    <p className="text-xs text-muted-foreground">
                      Processed {formatDateTime(doc.summary.processed_at)}
                    </p>
                  )}
                </motion.div>
              ) : (
                <div className="text-center py-10">
                  <AlignLeft className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
                  <p className="text-sm text-muted-foreground">No summary yet.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Risk Check ── */}
        <TabsContent value="risk">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div>
                <CardTitle className="text-sm flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-red-600" /> Risk Assessment
                </CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Rule-based risk and anomaly detection across legal clause types.
                </p>
              </div>
              <AnalyseButton type="risk" label="Check Risk" />
            </CardHeader>
            <CardContent>
              {doc?.risk ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                  {/* Risk level banner */}
                  <div className={cn("flex items-center gap-4 p-4 rounded-xl border", getRiskColor(doc.risk.risk_level))}>
                    <ShieldAlert className="h-8 w-8 shrink-0" />
                    <div>
                      <p className="text-lg font-bold capitalize">{doc.risk.risk_level} Risk</p>
                      <p className="text-sm mt-0.5">Score: {(doc.risk.score * 100).toFixed(0)} / 100</p>
                    </div>
                    <div className="ml-auto">
                      <Progress value={doc.risk.score * 100} className="w-24 h-2" />
                    </div>
                  </div>

                  {/* Risk flags */}
                  {doc.risk.flags.length > 0 ? (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        Risk Flags ({doc.risk.flags.length})
                      </p>
                      {doc.risk.flags.map((flag, i) => (
                        <div
                          key={i}
                          className={cn(
                            "flex items-start gap-3 p-3 rounded-lg border text-sm",
                            flag.severity === "high"
                              ? "bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800"
                              : flag.severity === "medium"
                              ? "bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800"
                              : "bg-muted/50 border-border"
                          )}
                        >
                          <AlertTriangle className={cn(
                            "h-4 w-4 mt-0.5 shrink-0",
                            flag.severity === "high" ? "text-red-600" :
                            flag.severity === "medium" ? "text-amber-600" : "text-muted-foreground"
                          )} />
                          <div>
                            <div className="flex items-center gap-2 mb-0.5">
                              <span className="font-semibold text-xs">{flag.category}</span>
                              <span className={cn("text-xs px-1.5 py-0.5 rounded-full font-medium", getRiskBadgeColor(flag.severity))}>
                                {flag.severity}
                              </span>
                            </div>
                            <p className="text-xs text-muted-foreground">{flag.description}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <p className="text-sm text-emerald-700 dark:text-emerald-400">No risk flags detected.</p>
                    </div>
                  )}
                </motion.div>
              ) : (
                <div className="text-center py-10">
                  <ShieldAlert className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
                  <p className="text-sm text-muted-foreground">No risk assessment yet.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
