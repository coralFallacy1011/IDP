"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileEdit, Loader2, Download, Copy, CheckCircle2, AlertTriangle,
  ChevronRight, Eye, RefreshCw, Sparkles,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { generateDocument } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";
import { cn, downloadText, copyToClipboard, TEMPLATE_TYPES } from "@/lib/utils";

// Field definitions per doc type
const FIELD_DEFINITIONS: Record<string, Array<{ key: string; label: string; required: boolean; multiline?: boolean }>> = {
  fir: [
    { key: "complainant_name", label: "Complainant Name", required: true },
    { key: "address", label: "Address", required: true },
    { key: "police_station", label: "Police Station", required: true },
    { key: "incident_type", label: "Incident Type", required: true },
    { key: "incident_date", label: "Date of Incident", required: true },
    { key: "incident_time", label: "Time of Incident", required: false },
    { key: "incident_location", label: "Incident Location", required: true },
    { key: "incident_details", label: "Incident Details", required: true, multiline: true },
    { key: "phone", label: "Phone Number", required: false },
    { key: "date", label: "Date of Filing", required: false },
    { key: "city", label: "City", required: false },
  ],
  affidavit: [
    { key: "name", label: "Deponent Name", required: true },
    { key: "age", label: "Age", required: false },
    { key: "address", label: "Address", required: true },
    { key: "purpose", label: "Purpose of Affidavit", required: true, multiline: true },
    { key: "city", label: "City", required: false },
    { key: "date", label: "Date", required: false },
  ],
  affidavit_general: [
    { key: "name", label: "Deponent Name", required: true },
    { key: "age", label: "Age", required: false },
    { key: "address", label: "Address", required: true },
    { key: "purpose", label: "Purpose", required: true, multiline: true },
    { key: "city", label: "City", required: false },
    { key: "date", label: "Date", required: false },
  ],
  rental_agreement: [
    { key: "landlord_name", label: "Landlord Name", required: true },
    { key: "landlord_address", label: "Landlord Address", required: false },
    { key: "tenant_name", label: "Tenant Name", required: true },
    { key: "tenant_address", label: "Tenant Address", required: false },
    { key: "property_address", label: "Property Address", required: true },
    { key: "rent", label: "Monthly Rent (₹)", required: true },
    { key: "deposit", label: "Security Deposit (₹)", required: false },
    { key: "duration", label: "Lease Duration (months)", required: false },
    { key: "notice_period", label: "Notice Period (days)", required: false },
    { key: "charges_by", label: "Maintenance Charges By", required: false },
    { key: "city", label: "City", required: false },
    { key: "date", label: "Date", required: false },
  ],
  employment_contract: [
    { key: "employee_name", label: "Employee Name", required: true },
    { key: "employee_address", label: "Employee Address", required: false },
    { key: "company_name", label: "Company Name", required: true },
    { key: "company_address", label: "Company Address", required: false },
    { key: "designation", label: "Designation / Role", required: false },
    { key: "salary", label: "Monthly Salary (₹)", required: true },
    { key: "joining_date", label: "Joining Date", required: false },
    { key: "notice_period", label: "Notice Period (days)", required: false },
    { key: "date", label: "Agreement Date", required: false },
  ],
  legal_notice: [
    { key: "sender_name", label: "Sender / Client Name", required: true },
    { key: "sender_address", label: "Sender Address", required: false },
    { key: "recipient_name", label: "Recipient Name", required: true },
    { key: "recipient_address", label: "Recipient Address", required: false },
    { key: "subject", label: "Subject", required: true },
    { key: "facts", label: "Facts of the Matter", required: false, multiline: true },
    { key: "demand", label: "Demand / Relief Sought", required: true },
    { key: "days", label: "Days to Comply", required: false },
    { key: "date", label: "Date", required: false },
  ],
  power_of_attorney: [
    { key: "principal_name", label: "Principal Name", required: true },
    { key: "principal_address", label: "Principal Address", required: false },
    { key: "agent_name", label: "Attorney / Agent Name", required: true },
    { key: "agent_address", label: "Agent Address", required: false },
    { key: "city", label: "City", required: false },
    { key: "date", label: "Date", required: false },
  ],
};

export default function GeneratePage() {
  const { incrementGeneratedDocs } = useAppStore();
  const [selectedType, setSelectedType] = useState<string>("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ id: string; content: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [preview, setPreview] = useState(false);

  const fieldDefs = selectedType ? FIELD_DEFINITIONS[selectedType] ?? [] : [];

  const handleTypeSelect = (type: string) => {
    setSelectedType(type);
    setFields({});
    setResult(null);
    setError(null);
  };

  const handleGenerate = async () => {
    if (!selectedType) return;
    setLoading(true);
    setError(null);
    try {
      const res = await generateDocument({ doc_type: selectedType, fields });
      setResult({ id: res.id, content: res.content });
      incrementGeneratedDocs();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Generation failed.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!result) return;
    await copyToClipboard(result.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const requiredMissing = fieldDefs
    .filter((f) => f.required && !fields[f.key]?.trim())
    .map((f) => f.label);

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <FileEdit className="h-6 w-6 text-amber-600" /> Document Generator
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Fill in the fields and generate a legal document from a template.
        </p>
      </motion.div>

      <div className="grid lg:grid-cols-5 gap-6">
        {/* Left — type selector + form */}
        <div className="lg:col-span-2 space-y-4">
          {/* Type selector */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Document Type</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-2">
              {TEMPLATE_TYPES.map(({ id, label, icon }) => (
                <button
                  key={id}
                  onClick={() => handleTypeSelect(id)}
                  className={cn(
                    "flex items-center gap-3 p-3 rounded-xl border text-left text-sm transition-all",
                    selectedType === id
                      ? "border-amber-500 bg-amber-50 dark:bg-amber-900/20"
                      : "border-border hover:bg-muted/50"
                  )}
                >
                  <span className="text-lg">{icon}</span>
                  <span className="flex-1 text-sm font-medium">{label}</span>
                  {selectedType === id
                    ? <CheckCircle2 className="h-4 w-4 text-amber-600 shrink-0" />
                    : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
                </button>
              ))}
            </CardContent>
          </Card>

          {/* Field form */}
          <AnimatePresence>
            {selectedType && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">Fill Details</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
                    {fieldDefs.map((fd) => (
                      <div key={fd.key} className="space-y-1.5">
                        <Label className="text-xs font-medium">
                          {fd.label}
                          {fd.required && <span className="text-red-500 ml-0.5">*</span>}
                        </Label>
                        {fd.multiline ? (
                          <Textarea
                            placeholder={fd.label}
                            value={fields[fd.key] ?? ""}
                            onChange={(e) => setFields((prev) => ({ ...prev, [fd.key]: e.target.value }))}
                            rows={3}
                            className="text-sm resize-none"
                          />
                        ) : (
                          <Input
                            placeholder={fd.label}
                            value={fields[fd.key] ?? ""}
                            onChange={(e) => setFields((prev) => ({ ...prev, [fd.key]: e.target.value }))}
                            className="text-sm"
                          />
                        )}
                      </div>
                    ))}

                    {requiredMissing.length > 0 && (
                      <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-xs text-amber-700 dark:text-amber-400">
                        <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                        <span>Required: {requiredMissing.join(", ")}</span>
                      </div>
                    )}

                    {error && (
                      <div className="flex items-start gap-2 p-2.5 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-400">
                        <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" /> {error}
                      </div>
                    )}

                    <Button
                      className="w-full gap-2"
                      disabled={loading || requiredMissing.length > 0}
                      onClick={handleGenerate}
                    >
                      {loading
                        ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
                        : <><Sparkles className="h-4 w-4" /> Generate Document</>}
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right — preview */}
        <div className="lg:col-span-3">
          <AnimatePresence mode="wait">
            {result ? (
              <motion.div
                key="result"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    <span className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
                      Document Generated
                    </span>
                    <Badge variant="outline" className="text-xs font-mono">{result.id.slice(0, 12)}…</Badge>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5 text-xs"
                      onClick={() => setPreview(!preview)}
                    >
                      <Eye className="h-3.5 w-3.5" />
                      {preview ? "Raw" : "Preview"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5 text-xs"
                      onClick={handleCopy}
                    >
                      <Copy className="h-3.5 w-3.5" />
                      {copied ? "Copied!" : "Copy"}
                    </Button>
                    <Button
                      size="sm"
                      className="gap-1.5 text-xs"
                      onClick={() => downloadText(result.content, `${selectedType}_${result.id}.txt`)}
                    >
                      <Download className="h-3.5 w-3.5" /> Download
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="gap-1.5 text-xs"
                      onClick={() => setResult(null)}
                    >
                      <RefreshCw className="h-3.5 w-3.5" /> New
                    </Button>
                  </div>
                </div>

                <Card>
                  <CardContent className="p-0">
                    <div className={cn(
                      "p-6 min-h-96 max-h-[600px] overflow-y-auto rounded-xl",
                      preview
                        ? "bg-white dark:bg-card font-serif text-sm leading-8"
                        : "bg-muted/50"
                    )}>
                      {preview ? (
                        <div className="whitespace-pre-wrap text-foreground">{result.content}</div>
                      ) : (
                        <pre className="text-xs font-mono text-foreground whitespace-pre-wrap leading-relaxed">
                          {result.content}
                        </pre>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ) : (
              <Card className="border-dashed h-full min-h-[400px] flex items-center justify-center">
                <CardContent className="text-center">
                  <FileEdit className="h-14 w-14 mx-auto mb-4 text-muted-foreground/30" />
                  <p className="text-muted-foreground font-medium">Document preview will appear here.</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Select a type on the left and fill in the required fields.
                  </p>
                </CardContent>
              </Card>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
