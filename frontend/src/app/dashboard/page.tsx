"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  FileText,
  ScanText,
  Brain,
  FileEdit,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowRight,
  BarChart3,
  PieChart,
  Activity,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart as RePieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/store/useAppStore";
import { formatDate } from "@/lib/utils";

const weeklyData = [
  { day: "Mon", documents: 42, analyses: 28 },
  { day: "Tue", documents: 65, analyses: 45 },
  { day: "Wed", documents: 48, analyses: 32 },
  { day: "Thu", documents: 80, analyses: 58 },
  { day: "Fri", documents: 58, analyses: 40 },
  { day: "Sat", documents: 35, analyses: 22 },
  { day: "Sun", documents: 28, analyses: 15 },
];

const docTypeData = [
  { name: "Contracts", value: 35, color: "#2563EB" },
  { name: "FIRs", value: 25, color: "#7C3AED" },
  { name: "Affidavits", value: 20, color: "#10B981" },
  { name: "Rental Agr.", value: 12, color: "#F59E0B" },
  { name: "Other", value: 8, color: "#6B7280" },
];

const recentActivities = [
  { icon: ScanText, action: "OCR Completed", doc: "Contract_2024_001.pdf", time: "2 min ago", status: "success" },
  { icon: Brain, action: "Risk Analysis", doc: "FIR_Delhi_2024.pdf", time: "15 min ago", status: "warning" },
  { icon: FileEdit, action: "Doc Generated", doc: "Rental_Agreement_Draft.pdf", time: "32 min ago", status: "success" },
  { icon: Brain, action: "NER Extraction", doc: "Affidavit_Sharma.pdf", time: "1h ago", status: "success" },
  { icon: ScanText, action: "OCR Failed", doc: "lowres_scan.jpg", time: "2h ago", status: "error" },
];

function StatCard({
  title,
  value,
  change,
  icon: Icon,
  color,
  href,
}: {
  title: string;
  value: string | number;
  change: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  href: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.3 }}
    >
      <Link href={href}>
        <Card className="cursor-pointer hover:shadow-md transition-all duration-200 border-border">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className={`h-10 w-10 rounded-xl ${color} flex items-center justify-center`}>
                <Icon className="h-5 w-5 text-white" />
              </div>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                change.startsWith("+") ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
              }`}>
                {change}
              </span>
            </div>
            <div className="text-2xl font-bold text-foreground">{value}</div>
            <div className="text-sm text-muted-foreground mt-0.5">{title}</div>
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
}

export default function DashboardPage() {
  const { stats, documents } = useAppStore();

  const statCards = [
    {
      title: "Documents Processed",
      value: stats.documentsProcessed.toLocaleString(),
      change: "+12%",
      icon: FileText,
      color: "bg-blue-600",
      href: "/dashboard/documents",
    },
    {
      title: "OCR Accuracy",
      value: `${stats.ocrAccuracy}%`,
      change: "+0.2%",
      icon: ScanText,
      color: "bg-emerald-600",
      href: "/dashboard/ocr",
    },
    {
      title: "AI Analyses Completed",
      value: stats.analysesCompleted.toLocaleString(),
      change: "+18%",
      icon: Brain,
      color: "bg-purple-600",
      href: "/dashboard/analysis",
    },
    {
      title: "Generated Documents",
      value: stats.generatedDocs.toLocaleString(),
      change: "+25%",
      icon: FileEdit,
      color: "bg-amber-600",
      href: "/dashboard/generate",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            Welcome back, Legal Admin. Here&apos;s your platform overview.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/dashboard/ocr">
            <Button className="gap-2">
              <ScanText className="h-4 w-4" />
              New OCR Scan
            </Button>
          </Link>
        </div>
      </motion.div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, i) => (
          <motion.div
            key={card.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <StatCard {...card} />
          </motion.div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Weekly Trend */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-2"
        >
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="h-4 w-4 text-blue-600" />
                Weekly Processing Trend
              </CardTitle>
              <Badge variant="default">Last 7 days</Badge>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={weeklyData}>
                  <defs>
                    <linearGradient id="gradDocs" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2563EB" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradAnalyses" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#7C3AED" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#7C3AED" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                  <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "8px",
                      boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)",
                    }}
                  />
                  <Area type="monotone" dataKey="documents" stroke="#2563EB" strokeWidth={2} fill="url(#gradDocs)" name="Documents" />
                  <Area type="monotone" dataKey="analyses" stroke="#7C3AED" strokeWidth={2} fill="url(#gradAnalyses)" name="Analyses" />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>

        {/* Doc Type Distribution */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.25 }}
        >
          <Card className="h-full">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <PieChart className="h-4 w-4 text-purple-600" />
                Document Types
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={200}>
                <RePieChart>
                  <Pie
                    data={docTypeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {docTypeData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                </RePieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Recent Activity + Quick Actions */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4 text-blue-600" />
                Recent Activity
              </CardTitle>
              <Link href="/dashboard/documents">
                <Button variant="ghost" size="sm" className="gap-1 text-xs">
                  View All <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
            </CardHeader>
            <CardContent className="space-y-3">
              {recentActivities.map((item, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.35 + i * 0.05 }}
                  className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-muted/50 transition-colors"
                >
                  <div className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                    item.status === "success" ? "bg-emerald-100 dark:bg-emerald-900/30" :
                    item.status === "warning" ? "bg-amber-100 dark:bg-amber-900/30" :
                    "bg-red-100 dark:bg-red-900/30"
                  }`}>
                    <item.icon className={`h-4 w-4 ${
                      item.status === "success" ? "text-emerald-600 dark:text-emerald-400" :
                      item.status === "warning" ? "text-amber-600 dark:text-amber-400" :
                      "text-red-600 dark:text-red-400"
                    }`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.action}</p>
                    <p className="text-xs text-muted-foreground truncate">{item.doc}</p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {item.status === "success" ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    ) : item.status === "warning" ? (
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                    ) : (
                      <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
                    )}
                    <span className="text-xs text-muted-foreground">{item.time}</span>
                  </div>
                </motion.div>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        {/* Quick Actions + Recent Documents */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="space-y-4"
        >
          {/* Quick Actions */}
          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <BarChart3 className="h-4 w-4 text-blue-600" />
                Quick Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              {[
                { label: "New OCR Scan", href: "/dashboard/ocr", icon: ScanText, color: "bg-blue-600" },
                { label: "AI Analysis", href: "/dashboard/analysis", icon: Brain, color: "bg-purple-600" },
                { label: "Semantic Search", href: "/dashboard/search", icon: BarChart3, color: "bg-cyan-600" },
                { label: "Generate Doc", href: "/dashboard/generate", icon: FileEdit, color: "bg-amber-600" },
              ].map(({ label, href, icon: Icon, color }) => (
                <Link key={label} href={href}>
                  <div className="flex items-center gap-3 p-3 rounded-xl border border-border hover:bg-muted/50 hover:border-blue-200 dark:hover:border-blue-800 transition-all duration-200 cursor-pointer group">
                    <div className={`h-8 w-8 rounded-lg ${color} flex items-center justify-center shrink-0`}>
                      <Icon className="h-4 w-4 text-white" />
                    </div>
                    <span className="text-sm font-medium group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{label}</span>
                  </div>
                </Link>
              ))}
            </CardContent>
          </Card>

          {/* Recent Documents */}
          {documents.length > 0 ? (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Recent Documents</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {documents.slice(0, 3).map((doc) => (
                  <Link key={doc.id} href="/dashboard/documents">
                    <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
                      <div className="h-8 w-8 rounded bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
                        <FileText className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{doc.filename}</p>
                        <p className="text-xs text-muted-foreground">{formatDate(doc.uploadDate)}</p>
                      </div>
                      <Badge variant="success" className="shrink-0 text-xs">
                        {doc.status}
                      </Badge>
                    </div>
                  </Link>
                ))}
              </CardContent>
            </Card>
          ) : (
            <Card className="border-dashed">
              <CardContent className="p-6 text-center">
                <Clock className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No documents yet.</p>
                <Link href="/dashboard/ocr">
                  <Button variant="outline" size="sm" className="mt-3 gap-2">
                    <ScanText className="h-3.5 w-3.5" />
                    Upload your first document
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}
        </motion.div>
      </div>
    </div>
  );
}
