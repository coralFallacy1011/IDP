import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(date: string | Date): string {
  return new Date(date).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + "...";
}

export function getRiskColor(level: string): string {
  switch (level?.toLowerCase()) {
    case "low":
      return "text-emerald-600 bg-emerald-50 border-emerald-200 dark:text-emerald-400 dark:bg-emerald-900/20 dark:border-emerald-800";
    case "medium":
      return "text-amber-600 bg-amber-50 border-amber-200 dark:text-amber-400 dark:bg-amber-900/20 dark:border-amber-800";
    case "high":
      return "text-red-600 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-900/20 dark:border-red-800";
    default:
      return "text-slate-600 bg-slate-50 border-slate-200 dark:text-slate-400 dark:bg-slate-800 dark:border-slate-700";
  }
}

export function getRiskBadgeColor(level: string): string {
  switch (level?.toLowerCase()) {
    case "low":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400";
    case "medium":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400";
    case "high":
      return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
    default:
      return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-400";
  }
}

export function getConfidenceColor(score: number): string {
  if (score >= 0.8) return "text-emerald-600";
  if (score >= 0.6) return "text-amber-600";
  return "text-red-600";
}

export function formatConfidence(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export function downloadText(text: string, filename: string): void {
  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function copyToClipboard(text: string): Promise<void> {
  return navigator.clipboard.writeText(text);
}

export const DOCUMENT_TYPES = [
  "FIR",
  "Affidavit",
  "Rental Agreement",
  "Employment Contract",
  "Legal Notice",
  "Power of Attorney",
  "Contract",
  "Invoice",
  "Report",
  "Other",
] as const;

export const LANGUAGES = [
  { code: "eng", label: "English" },
  { code: "hin", label: "Hindi" },
  { code: "kan", label: "Kannada" },
  { code: "tam", label: "Tamil" },
  { code: "tel", label: "Telugu" },
  { code: "mar", label: "Marathi" },
  { code: "ben", label: "Bengali" },
  { code: "urd", label: "Urdu" },
  { code: "ara", label: "Arabic" },
] as const;

export const TEMPLATE_TYPES = [
  { id: "fir", label: "FIR (First Information Report)", icon: "⚖️" },
  { id: "affidavit", label: "Affidavit", icon: "📜" },
  { id: "rental_agreement", label: "Rental Agreement", icon: "🏠" },
  { id: "employment_contract", label: "Employment Contract", icon: "💼" },
  { id: "legal_notice", label: "Legal Notice", icon: "📋" },
  { id: "power_of_attorney", label: "Power of Attorney", icon: "✍️" },
] as const;
