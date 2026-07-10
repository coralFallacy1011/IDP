"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, useInView } from "framer-motion";
import {
  Scale,
  ScanText,
  Brain,
  Search,
  MessageSquare,
  FileEdit,
  Shield,
  Zap,
  Users,
  Clock,
  FileText,
  ChevronRight,
  ArrowRight,
  CheckCircle,
  Star,
  BarChart3,
  Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";

function AnimatedCounter({ end, suffix = "", duration = 2 }: { end: number; suffix?: string; duration?: number }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (!inView) return;
    const startTime = Date.now();
    const animate = () => {
      const elapsed = (Date.now() - startTime) / 1000;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(eased * end));
      if (progress < 1) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }, [inView, end, duration]);

  return <span ref={ref}>{count.toLocaleString()}{suffix}</span>;
}

const features = [
  {
    icon: ScanText,
    title: "OCR Processing",
    description: "Extract text from PDFs, images, and scanned documents with 97%+ accuracy using advanced Tesseract OCR.",
    color: "from-blue-500 to-blue-600",
    bg: "bg-blue-50 dark:bg-blue-900/20",
  },
  {
    icon: Brain,
    title: "AI Classification",
    description: "Automatically classify legal documents using InLegalBERT — FIRs, contracts, affidavits, and more.",
    color: "from-purple-500 to-purple-600",
    bg: "bg-purple-50 dark:bg-purple-900/20",
  },
  {
    icon: Layers,
    title: "Entity Extraction",
    description: "Identify persons, organizations, dates, monetary values, and legal case numbers automatically.",
    color: "from-emerald-500 to-emerald-600",
    bg: "bg-emerald-50 dark:bg-emerald-900/20",
  },
  {
    icon: FileText,
    title: "AI Summarization",
    description: "Generate concise summaries of lengthy legal documents using BART-large-CNN with map-reduce support.",
    color: "from-amber-500 to-amber-600",
    bg: "bg-amber-50 dark:bg-amber-900/20",
  },
  {
    icon: Shield,
    title: "Risk Analysis",
    description: "Detect missing clauses, date inconsistencies, unusual terms, and compliance risks automatically.",
    color: "from-red-500 to-red-600",
    bg: "bg-red-50 dark:bg-red-900/20",
  },
  {
    icon: Search,
    title: "Semantic Search",
    description: "Find relevant legal clauses and obligations using FAISS vector embeddings across your document library.",
    color: "from-cyan-500 to-cyan-600",
    bg: "bg-cyan-50 dark:bg-cyan-900/20",
  },
  {
    icon: MessageSquare,
    title: "Legal Chatbot",
    description: "Ask questions about your documents in natural language. Powered by RAG with TinyLlama and contextual retrieval.",
    color: "from-indigo-500 to-indigo-600",
    bg: "bg-indigo-50 dark:bg-indigo-900/20",
  },
  {
    icon: FileEdit,
    title: "Document Generation",
    description: "Generate professional legal documents — FIRs, contracts, affidavits, POAs — from intelligent templates.",
    color: "from-pink-500 to-pink-600",
    bg: "bg-pink-50 dark:bg-pink-900/20",
  },
];

const stats = [
  { value: 50000, suffix: "+", label: "Documents Processed", icon: FileText },
  { value: 97, suffix: "%", label: "OCR Accuracy", icon: Zap },
  { value: 2500, suffix: "+", label: "Active Users", icon: Users },
  { value: 85, suffix: "%", label: "Time Saved", icon: Clock },
];

const testimonials = [
  {
    name: "Priya Sharma",
    role: "Senior Partner, Sharma & Associates",
    content: "LexAI transformed how we handle document review. What used to take hours now takes minutes.",
    rating: 5,
  },
  {
    name: "Rajesh Kumar",
    role: "Legal Head, TechCorp India",
    content: "The risk detection feature alone has saved us from multiple contractual oversights. Incredible platform.",
    rating: 5,
  },
  {
    name: "Ananya Iyer",
    role: "Compliance Officer, State Bank",
    content: "Multi-language OCR support is a game-changer for processing regional language documents.",
    rating: 5,
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950 overflow-x-hidden">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 border-b border-white/10 bg-slate-900/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto flex items-center justify-between h-16 px-4 md:px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
              <Scale className="h-4 w-4 text-white" />
            </div>
            <span className="text-white font-bold text-lg">LexAI</span>
          </Link>
          <div className="hidden md:flex items-center gap-8">
            {["Features", "Pricing", "Docs", "About"].map((item) => (
              <a key={item} href={`#${item.toLowerCase()}`} className="text-slate-300 hover:text-white text-sm transition-colors">
                {item}
              </a>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <Link href="/auth/login">
              <Button variant="ghost" size="sm" className="text-slate-300 hover:text-white hover:bg-white/10">
                Sign In
              </Button>
            </Link>
            <Link href="/auth/register">
              <Button size="sm" className="bg-blue-600 hover:bg-blue-700 text-white">
                Get Started
              </Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 overflow-hidden pt-16">
        {/* Animated background orbs */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 h-[600px] w-[600px] rounded-full bg-blue-600/20 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 h-[400px] w-[400px] rounded-full bg-blue-800/20 blur-3xl" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[800px] w-[800px] rounded-full bg-blue-900/10 blur-3xl" />
        </div>

        {/* Grid pattern */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: "linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />

        <div className="relative max-w-7xl mx-auto px-4 md:px-6 py-24">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            {/* Left content */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8 }}
            >
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-sm text-blue-300 mb-6">
                <Zap className="h-3.5 w-3.5" />
                AI-Powered Legal Intelligence Platform
              </div>

              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-white leading-tight mb-6">
                AI-Powered Legal{" "}
                <span className="bg-gradient-to-r from-blue-400 to-blue-200 bg-clip-text text-transparent">
                  Document Intelligence
                </span>{" "}
                Platform
              </h1>

              <p className="text-lg text-slate-300 mb-8 leading-relaxed">
                Automate OCR, legal analysis, information extraction, risk detection,
                and intelligent search with cutting-edge AI. Built for law firms, corporate
                legal teams, and compliance officers.
              </p>

              <div className="flex flex-wrap gap-4 mb-12">
                <Link href="/dashboard">
                  <Button size="lg" className="bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-600/30 gap-2">
                    Get Started Free
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
                <Link href="/dashboard/ocr">
                  <Button size="lg" variant="outline" className="border-white/20 text-white hover:bg-white/10 hover:text-white gap-2">
                    <ScanText className="h-4 w-4" />
                    Upload Document
                  </Button>
                </Link>
              </div>

              <div className="flex flex-wrap items-center gap-6 text-sm text-slate-400">
                {["No credit card required", "Multi-language support", "Enterprise-grade security"].map((item) => (
                  <div key={item} className="flex items-center gap-1.5">
                    <CheckCircle className="h-4 w-4 text-emerald-400" />
                    {item}
                  </div>
                ))}
              </div>
            </motion.div>

            {/* Right: Dashboard preview */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="relative"
            >
              <div className="relative rounded-2xl border border-white/10 bg-slate-800/50 backdrop-blur-sm p-6 shadow-2xl">
                <div className="flex items-center gap-2 mb-4">
                  <div className="h-3 w-3 rounded-full bg-red-400" />
                  <div className="h-3 w-3 rounded-full bg-yellow-400" />
                  <div className="h-3 w-3 rounded-full bg-green-400" />
                  <div className="ml-2 text-xs text-slate-400 font-mono">LexAI Dashboard</div>
                </div>

                {/* Mock stats */}
                <div className="grid grid-cols-2 gap-3 mb-4">
                  {[
                    { label: "Docs Processed", value: "1,247", trend: "+12%", color: "blue" },
                    { label: "OCR Accuracy", value: "97.3%", trend: "+0.2%", color: "emerald" },
                    { label: "Risk Alerts", value: "23", trend: "-8%", color: "amber" },
                    { label: "Time Saved", value: "340h", trend: "+25%", color: "purple" },
                  ].map((stat) => (
                    <div key={stat.label} className="rounded-lg bg-slate-700/50 p-3">
                      <p className="text-xs text-slate-400">{stat.label}</p>
                      <p className="text-xl font-bold text-white mt-1">{stat.value}</p>
                      <p className={`text-xs mt-0.5 text-${stat.color}-400`}>{stat.trend}</p>
                    </div>
                  ))}
                </div>

                {/* Mock chart bars */}
                <div className="rounded-lg bg-slate-700/50 p-3">
                  <p className="text-xs text-slate-400 mb-3">Weekly Processing</p>
                  <div className="flex items-end gap-1.5 h-16">
                    {[40, 65, 45, 80, 55, 90, 70].map((h, i) => (
                      <motion.div
                        key={i}
                        initial={{ height: 0 }}
                        animate={{ height: `${h}%` }}
                        transition={{ duration: 0.8, delay: 0.5 + i * 0.1 }}
                        className="flex-1 rounded-sm bg-gradient-to-t from-blue-600 to-blue-400"
                      />
                    ))}
                  </div>
                  <div className="flex justify-between mt-1">
                    {["M", "T", "W", "T", "F", "S", "S"].map((d) => (
                      <span key={d} className="text-xs text-slate-500">{d}</span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Floating badges */}
              <motion.div
                animate={{ y: [0, -8, 0] }}
                transition={{ duration: 3, repeat: Infinity }}
                className="absolute -top-4 -right-4 rounded-xl border border-emerald-500/30 bg-slate-800/90 backdrop-blur-sm px-4 py-2 shadow-lg"
              >
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-xs font-medium text-white">97.3% OCR Accuracy</span>
                </div>
              </motion.div>

              <motion.div
                animate={{ y: [0, 8, 0] }}
                transition={{ duration: 3, repeat: Infinity, delay: 1.5 }}
                className="absolute -bottom-4 -left-4 rounded-xl border border-blue-500/30 bg-slate-800/90 backdrop-blur-sm px-4 py-2 shadow-lg"
              >
                <div className="flex items-center gap-2">
                  <Shield className="h-3.5 w-3.5 text-blue-400" />
                  <span className="text-xs font-medium text-white">Risk Analysis Active</span>
                </div>
              </motion.div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 bg-slate-900 border-y border-slate-800">
        <div className="max-w-7xl mx-auto px-4 md:px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {stats.map(({ value, suffix, label, icon: Icon }, i) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="text-center"
              >
                <Icon className="h-6 w-6 text-blue-400 mx-auto mb-3" />
                <div className="text-3xl md:text-4xl font-bold text-white">
                  <AnimatedCounter end={value} suffix={suffix} />
                </div>
                <div className="text-sm text-slate-400 mt-1">{label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 bg-slate-50 dark:bg-slate-900">
        <div className="max-w-7xl mx-auto px-4 md:px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20 px-4 py-1.5 text-sm text-blue-600 dark:text-blue-400 mb-4">
              <BarChart3 className="h-3.5 w-3.5" />
              Platform Capabilities
            </div>
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-white mb-4">
              Everything you need for legal document intelligence
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
              From raw scans to actionable insights — our AI handles every step of the legal document workflow.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map(({ icon: Icon, title, description, color, bg }, i) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="group rounded-2xl border border-border bg-white dark:bg-slate-800/50 p-6 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 cursor-pointer"
              >
                <div className={`inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${color} mb-4 shadow-md`}>
                  <Icon className="h-6 w-6 text-white" />
                </div>
                <h3 className="font-semibold text-slate-900 dark:text-white mb-2">{title}</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">{description}</p>
                <div className="mt-4 flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity">
                  Learn more <ChevronRight className="h-4 w-4" />
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-24 bg-white dark:bg-slate-950">
        <div className="max-w-7xl mx-auto px-4 md:px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-white mb-4">
              Trusted by legal professionals
            </h2>
          </motion.div>
          <div className="grid md:grid-cols-3 gap-8">
            {testimonials.map((t, i) => (
              <motion.div
                key={t.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-2xl border border-border bg-slate-50 dark:bg-slate-800/50 p-6"
              >
                <div className="flex gap-1 mb-4">
                  {Array.from({ length: t.rating }).map((_, i) => (
                    <Star key={i} className="h-4 w-4 fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <p className="text-slate-700 dark:text-slate-300 mb-4 italic">&quot;{t.content}&quot;</p>
                <div>
                  <p className="font-semibold text-slate-900 dark:text-white">{t.name}</p>
                  <p className="text-sm text-slate-500">{t.role}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900">
        <div className="max-w-4xl mx-auto text-center px-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
              Ready to transform your legal workflow?
            </h2>
            <p className="text-lg text-slate-300 mb-8">
              Join thousands of legal professionals using LexAI to process documents faster, smarter, and more accurately.
            </p>
            <Link href="/dashboard">
              <Button size="xl" className="bg-blue-600 hover:bg-blue-700 text-white shadow-2xl shadow-blue-600/40 gap-2">
                Start for Free
                <ArrowRight className="h-5 w-5" />
              </Button>
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 border-t border-slate-800 py-12">
        <div className="max-w-7xl mx-auto px-4 md:px-6">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center gap-2.5 mb-4">
                <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
                  <Scale className="h-4 w-4 text-white" />
                </div>
                <span className="text-white font-bold">LexAI</span>
              </div>
              <p className="text-sm text-slate-400">Enterprise-grade AI for legal document intelligence.</p>
            </div>
            {[
              { title: "Product", links: ["Features", "Pricing", "Changelog", "Roadmap"] },
              { title: "Company", links: ["About", "Blog", "Careers", "Press"] },
              { title: "Legal", links: ["Privacy Policy", "Terms of Service", "Cookie Policy", "GDPR"] },
            ].map((col) => (
              <div key={col.title}>
                <h4 className="text-sm font-semibold text-white mb-4">{col.title}</h4>
                <ul className="space-y-2">
                  {col.links.map((link) => (
                    <li key={link}>
                      <a href="#" className="text-sm text-slate-400 hover:text-white transition-colors">{link}</a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="border-t border-slate-800 pt-8 text-center text-sm text-slate-500">
            © 2025 LexAI. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
