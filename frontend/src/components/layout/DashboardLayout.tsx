"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { Navbar } from "./Navbar";
import { useAppStore } from "@/store/useAppStore";

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { sidebarOpen } = useAppStore();
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // Only check on client after hydration
    const token = localStorage.getItem("auth_token");
    if (!token) {
      router.replace("/auth/login");
    } else {
      setChecked(true);
    }
  }, [router]);

  // Don't render dashboard content until auth is confirmed
  if (!checked) return null;

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <Navbar />
      <main
        className="transition-all duration-300 pt-16 min-h-screen"
        style={{ marginLeft: sidebarOpen ? 256 : 72 }}
      >
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
