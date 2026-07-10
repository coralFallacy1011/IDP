"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  ScanText,
  FolderOpen,
  Brain,
  Search,
  MessageSquare,
  FileEdit,
  Settings,
  ChevronLeft,
  Scale,
  Shield,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/useAppStore";
import { getAuthUser } from "@/lib/api";

const navItems = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/dashboard/ocr", icon: ScanText, label: "OCR Processing" },
  { href: "/dashboard/documents", icon: FolderOpen, label: "Documents" },
  { href: "/dashboard/analysis", icon: Brain, label: "AI Analysis" },
  { href: "/dashboard/search", icon: Search, label: "Semantic Search" },
  { href: "/dashboard/chat", icon: MessageSquare, label: "Legal Chatbot" },
  { href: "/dashboard/generate", icon: FileEdit, label: "Doc Generator" },
  { href: "/dashboard/blockchain", icon: Shield, label: "Blockchain" },
  { href: "/dashboard/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, setSidebarOpen } = useAppStore();

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-20 bg-black/50 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ width: sidebarOpen ? 256 : 72 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
        className="fixed left-0 top-0 z-30 flex h-full flex-col bg-slate-900 overflow-hidden border-r border-slate-800 shadow-xl"
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-slate-800">
          <Link href="/dashboard" className="flex items-center gap-3 min-w-0">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 shadow-md shadow-blue-900/50">
              <Scale className="h-5 w-5 text-white" />
            </div>
            <AnimatePresence>
              {sidebarOpen && (
                <motion.div
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <p className="text-sm font-bold text-white whitespace-nowrap">LexAI</p>
                  <p className="text-xs text-slate-400 whitespace-nowrap">Legal Intelligence</p>
                </motion.div>
              )}
            </AnimatePresence>
          </Link>
          {sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(false)}
              className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors lg:flex hidden"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => setSidebarOpen(false)}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto overflow-x-hidden py-4 px-3">
          <div className="space-y-1">
            {navItems.map(({ href, icon: Icon, label }) => {
              const isActive = pathname === href || pathname.startsWith(href + "/");
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "sidebar-item group relative",
                    isActive ? "sidebar-item-active" : "sidebar-item-inactive"
                  )}
                >
                  <Icon className="h-5 w-5 shrink-0" />
                  <AnimatePresence>
                    {sidebarOpen && (
                      <motion.span
                        initial={{ opacity: 0, x: -5 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -5 }}
                        transition={{ duration: 0.15 }}
                        className="whitespace-nowrap overflow-hidden"
                      >
                        {label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                  {/* Tooltip for collapsed state */}
                  {!sidebarOpen && (
                    <div className="absolute left-full ml-2 px-2 py-1 rounded-md bg-slate-800 text-white text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 shadow-lg">
                      {label}
                    </div>
                  )}
                  {isActive && (
                    <motion.div
                      layoutId="active-indicator"
                      className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-white rounded-full"
                    />
                  )}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* Bottom section */}
        <div className="border-t border-slate-800 p-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 shrink-0 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center">
              <span className="text-xs font-bold text-white">
                {getAuthUser()?.name?.charAt(0) ?? "U"}
              </span>
            </div>
            <AnimatePresence>
              {sidebarOpen && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="min-w-0"
                >
                  <p className="text-xs font-medium text-white truncate">
                    {getAuthUser()?.name ?? "User"}
                  </p>
                  <p className="text-xs text-slate-400 capitalize truncate">
                    {getAuthUser()?.role ?? ""}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </motion.aside>
    </>
  );
}
