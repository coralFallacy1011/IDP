"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Scale, Fingerprint, Loader2, AlertTriangle, CheckCircle2,
  ChevronDown, Lock, Wifi, WifiOff, Camera, ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authenticateFingerprint, getDemoUsers, saveAuth, clearAuth, api, type DemoUser } from "@/lib/api";
import WebcamCapture, { type WebcamCaptureHandle } from "@/components/WebcamCapture";

// ── Types ─────────────────────────────────────────────────────────────────────

/** After a fingerprint matches, the backend returns the user info so we can
 *  move to the face verification step. We hold this in state. */
interface PendingUser {
  user_id: string;
  name: string;
  role: string;
  face_enrolled: boolean;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LoginPage() {
  const router = useRouter();

  // ── Fingerprint step state ─────────────────────────────────────────────────
  const [fingerprintId, setFingerprintId] = useState("");
  const [activeTab, setActiveTab] = useState<"sensor" | "manual">("sensor");
  const [sensorConnected, setSensorConnected] = useState(false);
  const [verifyingId, setVerifyingId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>([]);
  const [showDemo, setShowDemo] = useState(false);

  // ── Face 2FA step state ────────────────────────────────────────────────────
  /** null = fingerprint step not yet passed. Set when fingerprint matches. */
  const [pendingUser, setPendingUser] = useState<PendingUser | null>(null);
  const webcamRef = useRef<WebcamCaptureHandle>(null);
  const [faceLoading, setFaceLoading] = useState(false);

  // ── Shared UI state ────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // ── Init ───────────────────────────────────────────────────────────────────
  useEffect(() => { clearAuth(); }, []);

  useEffect(() => {
    getDemoUsers()
      .then((users) => { setDemoUsers(users); setSensorConnected(true); })
      .catch(() => {
        setDemoUsers([
          { name: "Shriyansh",      role: "judge",  fingerprint_id: 1 },
          { name: "JatSahab",       role: "police", fingerprint_id: 2 },
          { name: "Aditya",         role: "lawyer", fingerprint_id: 3 },
        ]);
        setSensorConnected(false);
      });
  }, []);

  // ── Fingerprint sensor polling ─────────────────────────────────────────────
  useEffect(() => {
    // Only poll during the fingerprint step and when sensor tab is active or
    // we're waiting for the physical confirmation of a manual ID
    if (pendingUser !== null) return; // already past fingerprint step
    if (activeTab !== "sensor" && verifyingId === null) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }

    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get("/api/biometric/poll");
        if (res.status === 200 && res.data?.token) {
          const scannedId = res.data.fingerprint_id;

          if (verifyingId !== null) {
            // Manual flow: sensor must match the typed ID
            if (scannedId !== verifyingId) {
              clearInterval(pollRef.current!); pollRef.current = null;
              setError(`✗ Sensor scanned ID ${scannedId}, but expected ID ${verifyingId}.`);
              setVerifyingId(null); setLoading(false);
              return;
            }
          }

          clearInterval(pollRef.current!); pollRef.current = null;
          setSensorConnected(true);
          setVerifyingId(null); setLoading(false);
          handleFingerprintMatch(res.data);
        }
      } catch {
        setSensorConnected(false);
      }
    }, 1200);

    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [activeTab, verifyingId, pendingUser, router]);

  // ── Called whenever a fingerprint is confirmed (sensor or manual bypass) ───
  function handleFingerprintMatch(data: {
    token: string; name: string; role: string; user_id: string; fingerprint_id?: number; face_enrolled?: boolean;
  }) {
    // Check if this user has face enrolled by querying /api/face/status with the temp token
    // We use the token briefly to check enrollment, then discard it until face is verified
    const faceEnrolled = data.face_enrolled ?? false; // backend sends this flag

    setError(null);
    setSuccess(null);

    if (!faceEnrolled) {
      // First time: save the auth token temporarily so /face/status can work,
      // then redirect to enroll page. After enrollment, user comes back to login.
      saveAuth(data);
      router.push("/auth/face-enroll?after_enroll=1");
      return;
    }

    // Face is enrolled — move to face verification step
    setPendingUser({
      user_id: data.user_id,
      name: data.name,
      role: data.role,
      face_enrolled: true,
    });
    setSuccess(`✓ Fingerprint matched: ${data.name}. Now verify your face.`);
  }

  // ── Manual form submit ─────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = fingerprintId.trim();
    if (!trimmed) { setError("Please enter a fingerprint ID."); return; }
    const id = parseInt(trimmed, 10);
    if (isNaN(id) || id < 1 || String(id) !== trimmed) {
      setError("Fingerprint ID must be a positive whole number (1, 2, 3 …).");
      return;
    }

    setLoading(true); setError(null); setSuccess(null);

    // Bypass ID 999 — skip face 2FA entirely
    if (id === 999) {
      try {
        const data = await authenticateFingerprint(id);
        saveAuth(data);
        setSuccess(`✓ Bypass login: Welcome ${data.name}.`);
        setTimeout(() => router.push("/dashboard"), 800);
      } catch (err: unknown) {
        const axiosErr = err as { response?: { data?: { error?: string } } };
        setError(axiosErr.response?.data?.error || "Bypass login failed.");
        setLoading(false);
      }
      return;
    }

    setVerifyingId(id);
  };

  // ── Face 2FA submit ────────────────────────────────────────────────────────
  const handleFaceVerify = async () => {
    if (!pendingUser) return;
    setFaceLoading(true); setError(null);

    try {
      const blob = await webcamRef.current!.captureFrame();
      const formData = new FormData();
      formData.append("file", blob, "face.jpg");
      formData.append("user_id", pendingUser.user_id);

      const res = await api.post("/api/face/verify-login", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      saveAuth(res.data);
      setSuccess(`✓ Face verified. Welcome ${res.data.name}!`);
      setTimeout(() => router.push("/dashboard"), 800);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: { error?: string } } };
      if (axiosErr.response?.status === 401) {
        setError("Face not recognised. Please try again or contact admin.");
      } else if (axiosErr.response?.status === 422) {
        setError(axiosErr.response.data?.error || "No face detected. Please look at the camera.");
      } else if (axiosErr.response?.status === 404) {
        // No face enrolled yet — shouldn't normally happen, but handle gracefully
        saveAuth({ token: "", name: pendingUser.name, role: pendingUser.role } as never);
        router.push("/auth/face-enroll?after_enroll=1");
      } else {
        setError("Unable to reach server. Please try again.");
      }
      setFaceLoading(false);
    }
  };

  const handleDemoSelect = (index: number) => {
    const user = demoUsers[index];
    if (user) setFingerprintId(String(user.fingerprint_id));
    setShowDemo(false); setError(null); setSuccess(null);
    setVerifyingId(null); setLoading(false);
    setActiveTab("manual");
  };

  const resetToFingerprint = () => {
    setPendingUser(null); setError(null); setSuccess(null);
    setFaceLoading(false); setLoading(false); setVerifyingId(null);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  const isFaceStep = pendingUser !== null;

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
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/landing" className="inline-flex items-center gap-2.5 mb-4">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-lg">
              <Scale className="h-5 w-5 text-white" />
            </div>
            <span className="text-2xl font-bold text-white">LexAI</span>
          </Link>
          <h1 className="text-2xl font-bold text-white">
            {isFaceStep ? "Face Verification" : "Biometric Authentication"}
          </h1>
          <p className="text-slate-400 mt-1">
            {isFaceStep
              ? `Step 2 of 2 — Verify your face, ${pendingUser!.name}`
              : "Step 1 of 2 — Verify your fingerprint"
            }
          </p>

          {/* 2-step progress indicator */}
          <div className="flex items-center justify-center gap-3 mt-3">
            <div className="flex items-center gap-1.5">
              <div className={`h-6 w-6 rounded-full flex items-center justify-center text-xs font-bold ${
                isFaceStep ? "bg-emerald-600 text-white" : "bg-blue-600 text-white"
              }`}>
                {isFaceStep ? <CheckCircle2 className="h-3.5 w-3.5" /> : "1"}
              </div>
              <span className={`text-xs ${isFaceStep ? "text-emerald-400" : "text-blue-300"}`}>
                Fingerprint
              </span>
            </div>
            <div className={`h-px w-8 ${isFaceStep ? "bg-emerald-600" : "bg-white/20"}`} />
            <div className="flex items-center gap-1.5">
              <div className={`h-6 w-6 rounded-full flex items-center justify-center text-xs font-bold ${
                isFaceStep ? "bg-blue-600 text-white" : "bg-white/10 text-slate-500"
              }`}>
                {isFaceStep ? "2" : "2"}
              </div>
              <span className={`text-xs ${isFaceStep ? "text-blue-300" : "text-slate-600"}`}>
                Face ID
              </span>
            </div>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md p-8 shadow-2xl">

          <AnimatePresence mode="wait">

            {/* ── STEP 1: FINGERPRINT ─────────────────────────────────────── */}
            {!isFaceStep && (
              <motion.div
                key="fingerprint"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
              >
                {/* Tab toggle */}
                <div className="flex gap-2 mb-6 p-1 rounded-lg bg-white/5 border border-white/10">
                  <button
                    type="button"
                    onClick={() => { setActiveTab("sensor"); setError(null); setVerifyingId(null); setLoading(false); }}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-sm font-medium transition-all ${
                      activeTab === "sensor" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:text-white"
                    }`}
                  >
                    <Fingerprint className="h-4 w-4" />
                    Sensor
                  </button>
                  <button
                    type="button"
                    onClick={() => { setActiveTab("manual"); setError(null); setVerifyingId(null); setLoading(false); }}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-sm font-medium transition-all ${
                      activeTab === "manual" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:text-white"
                    }`}
                  >
                    <Lock className="h-4 w-4" />
                    Manual ID
                  </button>
                </div>

                {/* Sensor panel */}
                {activeTab === "sensor" && (
                  <div className="text-center space-y-5">
                    <div className="flex justify-center">
                      <motion.div
                        animate={{ scale: [1, 1.05, 1], opacity: [0.8, 1, 0.8] }}
                        transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
                        className="h-28 w-28 rounded-full bg-blue-600/20 border-2 border-blue-500/40 flex items-center justify-center"
                      >
                        <Fingerprint className="h-14 w-14 text-blue-400" />
                      </motion.div>
                    </div>
                    <div>
                      <p className="text-white font-medium">Waiting for fingerprint...</p>
                      <p className="text-slate-400 text-sm mt-1">Place your enrolled finger on the ESP32 sensor</p>
                    </div>
                    <div className={`inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-full border ${
                      sensorConnected
                        ? "border-emerald-700/50 bg-emerald-900/20 text-emerald-400"
                        : "border-red-700/50 bg-red-900/20 text-red-400"
                    }`}>
                      {sensorConnected
                        ? <><Wifi className="h-3 w-3" /> Backend connected — sensor active</>
                        : <><WifiOff className="h-3 w-3" /> Backend not reachable</>
                      }
                    </div>
                    <div className="flex items-center justify-center gap-1.5 text-xs text-slate-500">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Polling sensor...
                    </div>
                  </div>
                )}

                {/* Manual panel */}
                {activeTab === "manual" && (
                  <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="space-y-2">
                      <Label htmlFor="fingerprintId" className="text-slate-300 flex items-center gap-1.5">
                        <Lock className="h-3.5 w-3.5" /> Fingerprint ID
                      </Label>
                      <Input
                        id="fingerprintId"
                        type="number"
                        min="1"
                        step="1"
                        value={fingerprintId}
                        onChange={(e) => { setFingerprintId(e.target.value); setError(null); setSuccess(null); }}
                        placeholder="Enter enrolled fingerprint ID (e.g. 1)"
                        className="bg-white/5 border-white/10 text-white placeholder:text-slate-500 focus-visible:ring-blue-500 text-center text-lg font-mono"
                        autoComplete="off"
                      />
                      <p className="text-xs text-slate-500 text-center">Only registered IDs are accepted</p>
                    </div>
                    <Button
                      type="submit"
                      disabled={!fingerprintId.trim() || loading}
                      className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 h-11 gap-2"
                    >
                      {verifyingId !== null
                        ? <><Loader2 className="h-4 w-4 animate-spin" /> Place finger on sensor...</>
                        : loading
                          ? <><Loader2 className="h-4 w-4 animate-spin" /> Verifying...</>
                          : <><Fingerprint className="h-4 w-4" /> Authenticate</>
                      }
                    </Button>
                    {verifyingId !== null && (
                      <motion.div
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-4 flex items-start gap-2.5 p-3 rounded-lg bg-blue-900/30 border border-blue-700/50"
                      >
                        <Fingerprint className="h-4 w-4 text-blue-400 shrink-0 mt-0.5 animate-pulse" />
                        <p className="text-xs text-blue-300">
                          Place your enrolled finger on the ESP32 sensor to verify ID {verifyingId}.
                        </p>
                      </motion.div>
                    )}
                  </form>
                )}

                {/* Demo users */}
                <div className="mt-5 border-t border-white/10 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowDemo(!showDemo)}
                    className="w-full flex items-center justify-between text-xs text-slate-400 hover:text-slate-200 transition-colors py-1"
                  >
                    <span>Demo users (for testing)</span>
                    <ChevronDown className={`h-4 w-4 transition-transform ${showDemo ? "rotate-180" : ""}`} />
                  </button>
                  {showDemo && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="space-y-2 mt-3"
                    >
                      {demoUsers.map((u, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => handleDemoSelect(i)}
                          className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 hover:border-blue-500/40 transition-all text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <Fingerprint className="h-3.5 w-3.5 text-blue-400" />
                            <span className="text-white font-medium">{u.name}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-400 capitalize bg-slate-700/50 px-2 py-0.5 rounded-full">{u.role}</span>
                            <span className="text-xs font-mono text-blue-400 bg-blue-900/30 px-2 py-0.5 rounded-full">ID {i + 1}</span>
                          </div>
                        </button>
                      ))}
                      <p className="text-xs text-slate-600 text-center pt-1">Selects the ID — click Authenticate to proceed</p>
                    </motion.div>
                  )}
                </div>
              </motion.div>
            )}

            {/* ── STEP 2: FACE VERIFICATION ───────────────────────────────── */}
            {isFaceStep && (
              <motion.div
                key="face"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.3 }}
                className="space-y-4"
              >
                <div className="flex items-center gap-2 mb-2">
                  <ShieldCheck className="h-4 w-4 text-blue-400" />
                  <p className="text-sm text-slate-300">
                    Fingerprint verified. Now scan your face to complete login.
                  </p>
                </div>

                <WebcamCapture ref={webcamRef} className="rounded-lg overflow-hidden border border-white/10" />

                <Button
                  type="button"
                  onClick={handleFaceVerify}
                  disabled={faceLoading}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 h-11 gap-2"
                >
                  {faceLoading
                    ? <><Loader2 className="h-4 w-4 animate-spin" /> Verifying face...</>
                    : <><Camera className="h-4 w-4" /> Scan Face</>
                  }
                </Button>

                <button
                  type="button"
                  onClick={resetToFingerprint}
                  className="w-full text-xs text-slate-500 hover:text-slate-300 transition-colors py-1"
                >
                  ← Back to fingerprint
                </button>
              </motion.div>
            )}

          </AnimatePresence>

          {/* Error / success banners */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-red-900/30 border border-red-700/50"
            >
              <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
              <p className="text-xs text-red-300">{error}</p>
            </motion.div>
          )}
          {success && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-emerald-900/30 border border-emerald-700/50"
            >
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
              <p className="text-xs text-emerald-300">{success}</p>
            </motion.div>
          )}
        </div>

        <div className="mt-4 text-center space-y-2">
          <Link href="/auth/register" className="text-xs text-slate-500 hover:text-slate-300 transition-colors">
            Register a new fingerprint user →
          </Link>
        </div>
      </motion.div>
    </div>
  );
}
