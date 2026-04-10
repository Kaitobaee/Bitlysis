"use client";

import { useEffect, useRef } from "react";

const FIRST_START_TIME = 0;
const LOOP_START_TIME = 3;
const LOOP_CUTOFF_SECONDS = 0.35;
const PROCESS_FPS = 30;
const PROCESS_INTERVAL_MS = 1000 / PROCESS_FPS;

export function HeroLottie() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) {
      return;
    }

    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) {
      return;
    }

    let rafId = 0;
    let lastProcessAt = 0;

    const getSafeStartTime = (target: number) => {
      if (!Number.isFinite(video.duration) || video.duration <= 0.1) {
        return 0;
      }
      return Math.max(0, Math.min(target, video.duration - 0.05));
    };

    const render = (now: number) => {
      if (now - lastProcessAt < PROCESS_INTERVAL_MS) {
        rafId = window.requestAnimationFrame(render);
        return;
      }

      lastProcessAt = now;

      if (video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0) {
        if (
          Number.isFinite(video.duration) &&
          video.duration > LOOP_START_TIME + 0.1 &&
          video.duration - video.currentTime <= LOOP_CUTOFF_SECONDS
        ) {
          video.currentTime = getSafeStartTime(LOOP_START_TIME);
          if (video.paused) {
            void video.play().catch(() => {
              // Ignore transient play failures while seeking.
            });
          }
        }

        // Keep the previous frame while seeking so the canvas never flashes blank.
        if (video.seeking) {
          rafId = window.requestAnimationFrame(render);
          return;
        }

        if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
        }

        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const frame = context.getImageData(0, 0, canvas.width, canvas.height);
        const data = frame.data;

        // Key out near-black and near-gray backdrop while preserving colored subject.
        for (let i = 0; i < data.length; i += 4) {
          const r = data[i];
          const g = data[i + 1];
          const b = data[i + 2];
          const max = Math.max(r, g, b);
          const min = Math.min(r, g, b);
          const spread = max - min;

          if (max < 40 && spread < 20) {
            data[i + 3] = 0;
            continue;
          }

          if (max < 65 && spread < 24) {
            data[i + 3] = Math.min(data[i + 3], 110);
            continue;
          }

          if (max > 170 && spread < 20) {
            data[i + 3] = 0;
            continue;
          }

          if (max > 155 && spread < 30) {
            data[i + 3] = Math.min(data[i + 3], 110);
          }
        }

        context.putImageData(frame, 0, 0);
      }

      rafId = window.requestAnimationFrame(render);
    };

    const handleCanPlay = () => {
      void video.play().catch(() => {
        // Ignore autoplay restrictions; muted+playsInline usually passes.
      });
      if (!rafId) {
        lastProcessAt = 0;
        rafId = window.requestAnimationFrame(render);
      }
    };

    const handleLoadedMetadata = () => {
      video.currentTime = getSafeStartTime(FIRST_START_TIME);
      handleCanPlay();
    };

    video.addEventListener("loadedmetadata", handleLoadedMetadata);
    video.addEventListener("canplay", handleCanPlay);

    if (video.readyState >= 1) {
      handleLoadedMetadata();
    }

    return () => {
      video.removeEventListener("loadedmetadata", handleLoadedMetadata);
      video.removeEventListener("canplay", handleCanPlay);
      if (rafId) {
        window.cancelAnimationFrame(rafId);
      }
    };
  }, []);

  return (
    <div className="relative h-104 w-104 md:h-128 md:w-lg">
      <video
        ref={videoRef}
        className="hidden"
        src="/animations/foxcdong-2.mp4"
        muted
        playsInline
        preload="auto"
      />
      <canvas ref={canvasRef} className="h-full w-full rounded-3xl" aria-label="Hero video" />
    </div>
  );
}
