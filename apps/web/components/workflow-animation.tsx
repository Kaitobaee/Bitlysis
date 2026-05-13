"use client";

import { useEffect, useRef } from "react";
import lottie, { type AnimationItem } from "lottie-web";

export function WorkflowAnimation() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const animationRef = useRef<AnimationItem | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    animationRef.current = lottie.loadAnimation({
      container: containerRef.current,
      renderer: "svg",
      loop: true,
      autoplay: true,
      path: "/animations/json/sayhi.json",
    });

    return () => {
      animationRef.current?.destroy();
    };
  }, []);

  return <div ref={containerRef} className="h-96 w-96" />;
}
