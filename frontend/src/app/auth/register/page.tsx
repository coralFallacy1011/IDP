"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Scale, ArrowRight, Fingerprint, User, Shield, Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { registerFingerprint } from "@/lib/api";

const ROLES = ["judge", "police", "lawyer", "clerk", "admin"];

export default function RegisterPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [fingerprintId, setFingerprintId] = useState("");
  const [role, setRole] = useState("lawyer");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    const id = parseInt(fingerprintId, 10);
    if (isNaN(id) || id < 1) {
      setError("Fingerprint ID must be a positive integer.");
      setLoading(false);
      return;
    }

    try {
      const result = await registerFingerprint({ name: name.trim(), fingerprint_id: id, role });
      setSuccess(`Registered successfully! User ID: ${result.user_id}`);
      setTimeout(() => router.push("/auth/login"), 1500);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setError("Fingerprint ID already registered. Choose a different ID.");
      } else {
        setError("Registration failed. Make sure the backend is running on port 5000.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center p-4">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 h-[500px] w-[500px] rounded-full bg-blue-600/20 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 h-[400px] w-[400px] rounded-full bg-blue-800/20 blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative w-full max-w-md"
      >
        <div className="text-center mb-8">
          <Link href="/landing" className="inline-flex items-center gap-2.5 mb-4">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-lg">
              <Scale className="h-5 w-5 text-white" />
            </div>
            <span className="text-2xl font-bold text-white">LexAI</span>
          </Link>
          <h1 className="text-2xl font-bold text-white">Register Fingerprint</h1>
          <p className="text-slate-400 mt-1">Associate your fingerprint ID with a user account</p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md p-8 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-4">

            <div className="space-y-2">
              <Label htmlFor="name" className="text-slate-300 flex items-center gap-1.5">
                <User className="h-3.5 w-3.5" /> Full Name
              </Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Judge Sharma"
                className="bg-white/5 border-white/10 text-white placeholder:text-slate-500"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="fid" className="text-slate-300 flex items-center gap-1.5">
                <Fingerprint className="h-3.5 w-3.5" /> Fingerprint ID
              </Label>
              <Input
                id="fid"
                type="number"
                min="1"
                value={fingerprintId}
                onChange={(e) => setFingerprintId(e.target.value)}
                placeholder="Sensor slot number (e.g. 4)"
                className="bg-white/5 border-white/10 text-white placeholder:text-slate-500 font-mono"
                required
              />
              <p className="text-xs text-slate-500">
                Enroll fingerprint on the sensor first, then enter its slot ID.
              </p>
            </div>

            <div className="space-y-2">
              <Label className="text-slate-300 flex items-center gap-1.5">
                <Shield className="h-3.5 w-3.5" /> Role
              </Label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger className="bg-white/5 border-white/10 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => (
                    <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-red-900/30 border border-red-700/50">
                <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
                <p className="text-xs text-red-300">{error}</p>
              </div>
            )}

            {success && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-900/30 border border-emerald-700/50">
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                <p className="text-xs text-emerald-300">{success}</p>
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 h-11 gap-2 mt-2"
            >
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Registering...</>
              ) : (
                <>Register User <ArrowRight className="h-4 w-4" /></>
              )}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-slate-400">
              Already registered?{" "}
              <Link href="/auth/login" className="text-blue-400 hover:text-blue-300 font-medium">
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
