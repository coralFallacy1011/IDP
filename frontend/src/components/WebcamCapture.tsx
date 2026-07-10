"use client";

import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface WebcamCaptureHandle {
  /** Capture the current video frame and return it as a Blob (image/jpeg). */
  captureFrame(): Promise<Blob>;
}

export interface WebcamCaptureProps {
  /** Called when the webcam stream starts successfully. */
  onReady?: () => void;
  /** Called when the stream cannot be started (permission denied, no camera). */
  onError?: (error: string) => void;
  className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const WebcamCapture = forwardRef<WebcamCaptureHandle, WebcamCaptureProps>(
  function WebcamCapture({ onReady, onError, className }, ref) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const streamRef = useRef<MediaStream | null>(null);

    const [status, setStatus] = useState<"initializing" | "ready" | "error">(
      "initializing"
    );
    const [errorMessage, setErrorMessage] = useState<string>("");
    const [retryCount, setRetryCount] = useState(0);

    // ------------------------------------------------------------------
    // Expose captureFrame imperatively
    // ------------------------------------------------------------------
    useImperativeHandle(
      ref,
      () => ({
        captureFrame(): Promise<Blob> {
          return new Promise((resolve, reject) => {
            const video = videoRef.current;
            const canvas = canvasRef.current;

            if (!video || !canvas) {
              reject(new Error("Video or canvas element is not available."));
              return;
            }

            if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
              reject(new Error("Video stream is not ready yet."));
              return;
            }

            // Size the canvas to match the current video dimensions.
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;

            const ctx = canvas.getContext("2d");
            if (!ctx) {
              reject(new Error("Could not get 2D canvas context."));
              return;
            }

            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

            canvas.toBlob(
              (blob) => {
                if (blob) {
                  resolve(blob);
                } else {
                  reject(new Error("Failed to capture frame from canvas."));
                }
              },
              "image/jpeg",
              0.92
            );
          });
        },
      }),
      []
    );

    // ------------------------------------------------------------------
    // Camera lifecycle — start on mount, stop on unmount
    // ------------------------------------------------------------------
    useEffect(() => {
      let cancelled = false;

      async function startCamera() {
        // SSR safety: navigator.mediaDevices may not exist in Node/SSR.
        if (
          typeof navigator === "undefined" ||
          !navigator.mediaDevices ||
          typeof navigator.mediaDevices.getUserMedia !== "function"
        ) {
          const msg = "Camera access is not supported in this environment.";
          if (!cancelled) {
            setStatus("error");
            setErrorMessage(msg);
            onError?.(msg);
          }
          return;
        }

        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            video: true,
          });

          if (cancelled) {
            // Component unmounted while awaiting — release immediately.
            stream.getTracks().forEach((t) => t.stop());
            return;
          }

          streamRef.current = stream;

          if (videoRef.current) {
            videoRef.current.srcObject = stream;
          }

          setStatus("ready");
          onReady?.();
        } catch (err) {
          if (cancelled) return;

          let msg = "Unable to access the camera.";
          if (err instanceof DOMException) {
            if (
              err.name === "NotAllowedError" ||
              err.name === "PermissionDeniedError"
            ) {
              msg =
                "Camera permission was denied. Please allow camera access and try again.";
            } else if (
              err.name === "NotFoundError" ||
              err.name === "DevicesNotFoundError"
            ) {
              msg = "No camera device was found on this system.";
            } else if (err.name === "NotReadableError") {
              msg =
                "The camera is already in use by another application. Please close it and try again.";
            } else if (err.name === "OverconstrainedError") {
              msg = "The requested camera constraints could not be satisfied.";
            }
          }

          setStatus("error");
          setErrorMessage(msg);
          onError?.(msg);
        }
      }

      startCamera();

      return () => {
        cancelled = true;
        // Release camera hardware on unmount.
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
        }
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [retryCount]);

    // ------------------------------------------------------------------
    // Render
    // ------------------------------------------------------------------
    return (
      <div className={cn("relative w-full overflow-hidden rounded-lg", className)}>
        {/* Hidden canvas used only for frame capture */}
        <canvas ref={canvasRef} className="hidden" aria-hidden="true" />

        {/* Initialising spinner */}
        {status === "initializing" && (
          <div
            className="flex flex-col items-center justify-center gap-3 rounded-lg
              bg-slate-900 text-slate-400 aspect-video w-full"
            role="status"
            aria-label="Initialising camera"
          >
            <svg
              className="h-8 w-8 animate-spin text-blue-500"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z
                   m2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span className="text-sm">Initialising camera&hellip;</span>
          </div>
        )}

        {/* Error state */}
        {status === "error" && (
          <div
            className="flex flex-col items-center justify-center gap-3 rounded-lg
              bg-slate-900 text-red-400 aspect-video w-full px-6 text-center"
            role="alert"
            aria-live="assertive"
          >
            {/* Camera-off icon */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-10 w-10 text-red-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9A2.25 2.25 0 004.5 18.75z"
              />
              <line
                x1="3"
                y1="3"
                x2="21"
                y2="21"
                stroke="currentColor"
                strokeWidth={1.5}
                strokeLinecap="round"
              />
            </svg>

            <p className="text-sm font-medium text-red-400">{errorMessage}</p>
            <p className="text-xs text-slate-500">
              Click the camera icon in your browser address bar to allow access, then retry.
            </p>
            <button
              type="button"
              onClick={() => {
                setStatus("initializing");
                setErrorMessage("");
                setRetryCount((c) => c + 1);
              }}
              className="mt-1 text-xs text-blue-400 hover:text-blue-300 underline underline-offset-2 transition-colors"
            >
              Retry camera
            </button>
          </div>
        )}

        {/* Live video feed */}
        {/* Always rendered so the ref is stable; hidden while not ready */}
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className={cn(
            "w-full rounded-lg object-cover aspect-video bg-black",
            status !== "ready" && "hidden"
          )}
          aria-label="Webcam live feed"
        />
      </div>
    );
  }
);

WebcamCapture.displayName = "WebcamCapture";

export default WebcamCapture;
