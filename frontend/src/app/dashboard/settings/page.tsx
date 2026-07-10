"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Settings, User, Palette, Server, Bell, Shield,
  Save, CheckCircle2, Sun, Moon, Monitor, Eye, EyeOff,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { useTheme } from "next-themes";
import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";
import { getAuthUser } from "@/lib/api";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { stats } = useAppStore();

  const [profile, setProfile] = useState({ name: "Legal Admin", email: "admin@lexai.com", role: "Administrator" });
  const [api, setApi] = useState({ url: "http://localhost:5000", timeout: "120" });

  useEffect(() => {
    const user = getAuthUser();
    if (user) {
      setProfile({
        name: user.name,
        email: `${user.name.toLowerCase().replace(/\s+/g, "")}@lexai.com`,
        role: user.role
      });
    }
  }, []);

  const [showApiUrl, setShowApiUrl] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  const handleSave = (section: string) => {
    // In a real app: persist to backend/localStorage
    setSaved(section);
    setTimeout(() => setSaved(null), 2500);
  };

  const SaveButton = ({ section }: { section: string }) => (
    <Button size="sm" className="gap-2" onClick={() => handleSave(section)}>
      {saved === section ? (
        <><CheckCircle2 className="h-3.5 w-3.5" /> Saved</>
      ) : (
        <><Save className="h-3.5 w-3.5" /> Save</>
      )}
    </Button>
  );

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Settings className="h-6 w-6 text-muted-foreground" /> Settings
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Configure your profile, appearance, and backend connection.
        </p>
      </motion.div>

      {/* Profile */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <User className="h-4 w-4 text-blue-600" /> Profile
            </CardTitle>
            <SaveButton section="profile" />
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="h-16 w-16 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shrink-0">
                <span className="text-xl font-bold text-white">
                  {profile.name.slice(0, 2).toUpperCase()}
                </span>
              </div>
              <div>
                <p className="font-semibold">{profile.name}</p>
                <p className="text-sm text-muted-foreground">{profile.email}</p>
                <Badge variant="outline" className="text-xs mt-1 capitalize">{profile.role}</Badge>
              </div>
            </div>
            <Separator />
            <div className="grid gap-3">
              {[
                { key: "name", label: "Display Name" },
                { key: "email", label: "Email" },
                { key: "role", label: "Role / Designation" },
              ].map(({ key, label }) => (
                <div key={key} className="space-y-1.5">
                  <Label className="text-xs">{label}</Label>
                  <Input
                    value={profile[key as keyof typeof profile]}
                    onChange={(e) => setProfile((prev) => ({ ...prev, [key]: e.target.value }))}
                    className="text-sm"
                  />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Appearance */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <Palette className="h-4 w-4 text-purple-600" /> Appearance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              <Label className="text-xs">Theme</Label>
              <div className="grid grid-cols-3 gap-2 mt-1">
                {[
                  { value: "light", label: "Light", icon: Sun },
                  { value: "dark", label: "Dark", icon: Moon },
                  { value: "system", label: "System", icon: Monitor },
                ].map(({ value, label, icon: Icon }) => (
                  <button
                    key={value}
                    onClick={() => setTheme(value)}
                    className={cn(
                      "flex flex-col items-center gap-2 p-4 rounded-xl border text-sm font-medium transition-all",
                      theme === value
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400"
                        : "border-border hover:bg-muted/50 text-muted-foreground"
                    )}
                  >
                    <Icon className="h-5 w-5" />
                    {label}
                    {theme === value && (
                      <CheckCircle2 className="h-3.5 w-3.5 text-blue-600" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* API Config */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <Server className="h-4 w-4 text-emerald-600" /> Backend API
            </CardTitle>
            <SaveButton section="api" />
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1.5">
              <Label className="text-xs">API Base URL</Label>
              <div className="relative">
                <Input
                  type={showApiUrl ? "text" : "password"}
                  value={api.url}
                  onChange={(e) => setApi((prev) => ({ ...prev, url: e.target.value }))}
                  className="text-sm pr-10 font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowApiUrl(!showApiUrl)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showApiUrl ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">
                Set via <code className="font-mono bg-muted px-1 rounded">NEXT_PUBLIC_API_URL</code> env var, or override here.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Request Timeout (seconds)</Label>
              <Input
                type="number"
                value={api.timeout}
                onChange={(e) => setApi((prev) => ({ ...prev, timeout: e.target.value }))}
                className="text-sm w-32"
              />
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Usage Stats */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <Shield className="h-4 w-4 text-amber-600" /> Platform Stats
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "Documents Processed", value: stats.documentsProcessed.toLocaleString() },
                { label: "OCR Accuracy", value: `${stats.ocrAccuracy}%` },
                { label: "AI Analyses Run", value: stats.analysesCompleted.toLocaleString() },
                { label: "Documents Generated", value: stats.generatedDocs.toLocaleString() },
              ].map(({ label, value }) => (
                <div key={label} className="p-3 rounded-xl bg-muted/50 border border-border">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="text-lg font-bold mt-0.5">{value}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Notifications placeholder */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <Bell className="h-4 w-4 text-blue-600" /> Notifications
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              "OCR completion alerts",
              "High-risk document warnings",
              "AI analysis notifications",
            ].map((label) => (
              <div key={label} className="flex items-center justify-between py-2">
                <span className="text-sm">{label}</span>
                <Badge variant="outline" className="text-xs">Coming soon</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
