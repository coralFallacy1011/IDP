"use client";

import { Suspense, useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  Scale,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Camera,
  ArrowLeft,
  UserCheck,
  UserX,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import WebcamCapture, { type WebcamCaptureHandle } from "@/components/WebcamCapture";
import { enrollFace, getFaceStatus } from "@/lib/api";

// ── Inner component that uses useSearchParams (must be inside <Suspense>) ────

function FaceEnrollInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isAfterEnroll = searchParams.get("after_enroll") === "1";
  const webcamRef = useRef<WebcamCaptureHandle>(null);

  const [enrolled, setEnrolled] = useState<boolean | null>(null);
  const [webcamReady, setWebcamReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // ── Auth guard & initial status fetch ──────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      router.push("/auth/login");
      return;
    }
    getFaceStatus()
      .then((res) => setEnrolled(res.enrolled))
      .catch(() => setEnrolled(false));
  }, [router]);

  // ── Enroll handler ──────────────────────────────────────────────────────────
  const handleEnroll = async () => {
    if (!webcamRef.current) {
      setError("Camera not ready. Please allow camera access and try again.");
      return;
    }
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      const blob = await webcamRef.current.captureFrame();
      const result = await enrollFace(blob);

      if (result.enrolled) {
        setEnrolled(true);
        setSuccess(
          isAfterEnroll
            ? "Face enrolled! Redirecting you back to login..."
            : "Face enrolled successfully! You can now use Face ID to log in."
        );
        if (isAfterEnroll) {
          // Clear the temporary token — user must complete the full 2-step login
          localStorage.removeItem("auth_token");
          localStorage.removeItem("auth_user");
          setTimeout(() => router.push("/auth/login"), 1800);
        }
      }
    } catch (err: unknown) {
      const axiosError = err as { response?: { status?: number; data?: { error?: string } } };
      const status = axiosError?.response?.status;
      if (status === 422) {
        setError(axiosError.response?.data?.error ?? "No face detected. Please look directly at the camera.");
      } else if (status === 401) {
        router.push("/auth/login");
        return;
      } else if (!axiosError?.response) {
        setError("Cannot reach the server. Make sure the backend is running on port 5000.");
      } else {
        setError(axiosError.response?.data?.error ?? "Enrollment failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center p-4">
      {/* Background blobs */}
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
          <h1 className="text-2xl font-bold text-white">Face Enrollment</h1>
          <p className="text-slate-400 mt-1">
            {isAfterEnroll
              ? "One-time setup — enroll your face to enable Face ID login"
              : "Enroll your face to enable Face ID authentication"
            }
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md p-8 shadow-2xl space-y-6">

          {/* Enrollment status badge */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-400">Enrollment status</span>
            {enrolled === null ? (
              <span className="inline-flex items-center gap-1.5 text-xs px-3 py-1 rounded-full bg-white/5 border border-white/10 text-slate-400">
                <Loader2 className="h-3 w-3 animate-spin" />
                Checking…
              </span>
            ) : enrolled ? (
              <motion.span
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="inline-flex items-center gap-1.5 text-xs px-3 py-1 rounded-full bg-emerald-900/30 border border-emerald-700/50 text-emerald-400"
              >
                <UserCheck className="h-3.5 w-3.5" />
                Enrolled
              </motion.span>
            ) : (
              <motion.span
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="inline-flex items-center gap-1.5 text-xs px-3 py-1 rounded-full bg-slate-700/40 border border-white/10 text-slate-400"
              >
                <UserX className="h-3.5 w-3.5" />
                Not enrolled
              </motion.span>
            )}
          </div>

          {/* Webcam */}
          <WebcamCapture
            ref={webcamRef}
            onReady={() => setWebcamReady(true)}
            onError={() => setWebcamReady(false)}
            className="rounded-xl overflow-hidden border border-white/10"
          />

          {/* Camera not ready hint */}
          {!webcamReady && !loading && (
            <p className="text-xs text-slate-500 text-center -mt-2">
              Allow camera access in your browser to enroll your face.
            </p>
          )}

          {/* Enroll button — disabled until webcam is ready */}
          <Button
            type="button"
            onClick={handleEnroll}
            disabled={loading || !webcamReady}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 h-11 gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Enrolling…
              </>
            ) : (
              <>
                <Camera className="h-4 w-4" />
                Enroll Face
              </>
            )}
          </Button>

          {/* Error */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-2 p-3 rounded-lg bg-red-900/30 border border-red-700/50"
            >
              <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
              <p className="text-xs text-red-300">{error}</p>
            </motion.div>
          )}

          {/* Success */}
          {success && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-2 p-3 rounded-lg bg-emerald-900/30 border border-emerald-700/50"
            >
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
              <p className="text-xs text-emerald-300">{success}</p>
            </motion.div>
          )}
        </div>

        {/* Back link */}
        <div className="mt-4 text-center">
          <Link
            href="/auth/login"
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to login
          </Link>
        </div>
      </motion.div>
    </div>
  );
}

// ── Page export wrapped in Suspense (required by Next.js 15 for useSearchParams) ─

export default function FaceEnrollPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
      </div>
    }>
      <FaceEnrollInner />
    </Suspense>
  );
}
