"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Menu, Search, Bell, Sun, Moon, User, LogOut, Settings, ChevronDown,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";
import { getAuthUser, clearAuth } from "@/lib/api";

export function Navbar() {
  const { setSidebarOpen, sidebarOpen } = useAppStore();
  const { theme, setTheme } = useTheme();
  const router = useRouter();
  const [profileOpen, setProfileOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [authUser, setAuthUser] = useState<{ name: string; role: string } | null>(null);

  useEffect(() => {
    setAuthUser(getAuthUser());
  }, []);

  const handleLogout = () => {
    clearAuth();
    router.push("/auth/login");
  };

  const initials = authUser?.name
    ? authUser.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()
    : "LA";

  return (
    <header className="fixed top-0 right-0 z-20 flex h-16 items-center gap-4 border-b border-border bg-background/80 backdrop-blur-sm px-4 transition-all duration-300"
      style={{ left: sidebarOpen ? 256 : 72 }}
    >
      {/* Hamburger */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="text-muted-foreground"
      >
        <Menu className="h-5 w-5" />
      </Button>

      {/* Search */}
      <div className="flex-1 max-w-md relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search documents, analyses..."
          className="pl-9 bg-muted/50 border-0 focus-visible:ring-1"
        />
      </div>

      <div className="flex items-center gap-2 ml-auto">
        {/* Dark mode toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="text-muted-foreground"
        >
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
        </Button>

        {/* Notifications */}
        <div className="relative">
          <Button
            variant="ghost"
            size="icon"
            className="text-muted-foreground relative"
            onClick={() => setNotifOpen(!notifOpen)}
          >
            <Bell className="h-4 w-4" />
            <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-blue-600" />
          </Button>
          {notifOpen && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="absolute right-0 top-full mt-2 w-80 rounded-xl border border-border bg-card shadow-xl z-50 overflow-hidden"
            >
              <div className="p-4 border-b border-border">
                <h3 className="font-semibold text-sm">Notifications</h3>
              </div>
              {[
                { title: "OCR Processing Complete", desc: "Document analyzed successfully", time: "2m ago", type: "success" },
                { title: "Risk Alert Detected", desc: "High risk identified in contract", time: "15m ago", type: "warning" },
                { title: "New Document Uploaded", desc: "FIR_2024_001.pdf processed", time: "1h ago", type: "info" },
              ].map((n, i) => (
                <div key={i} className="flex gap-3 p-4 hover:bg-muted/50 cursor-pointer transition-colors">
                  <div className={cn(
                    "h-2 w-2 rounded-full mt-1.5 shrink-0",
                    n.type === "success" ? "bg-emerald-500" :
                    n.type === "warning" ? "bg-amber-500" : "bg-blue-500"
                  )} />
                  <div>
                    <p className="text-sm font-medium">{n.title}</p>
                    <p className="text-xs text-muted-foreground">{n.desc}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{n.time}</p>
                  </div>
                </div>
              ))}
            </motion.div>
          )}
        </div>

        {/* Profile */}
        <div className="relative">
          <button
            onClick={() => setProfileOpen(!profileOpen)}
            className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-muted/50 transition-colors"
          >
            <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
              <span className="text-xs font-bold text-white">{initials}</span>
            </div>
            <div className="hidden md:block text-left">
              <p className="text-xs font-medium">{authUser?.name ?? "User"}</p>
              <p className="text-xs text-muted-foreground capitalize">{authUser?.role ?? ""}</p>
            </div>
            <ChevronDown className="h-3 w-3 text-muted-foreground hidden md:block" />
          </button>
          {profileOpen && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="absolute right-0 top-full mt-2 w-48 rounded-xl border border-border bg-card shadow-xl z-50 overflow-hidden py-1"
            >
              {[
                { icon: User, label: "Profile", href: "/dashboard/settings" },
                { icon: Settings, label: "Settings", href: "/dashboard/settings" },
              ].map(({ icon: Icon, label, href }) => (
                <a
                  key={label}
                  href={href}
                  className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-muted/50 transition-colors"
                >
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  {label}
                </a>
              ))}
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-4 py-2 text-sm hover:bg-muted/50 transition-colors text-red-500"
              >
                <LogOut className="h-4 w-4" />
                Sign Out
              </button>
            </motion.div>
          )}
        </div>
      </div>
    </header>
  );
}
