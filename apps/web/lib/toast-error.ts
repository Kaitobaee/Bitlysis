import { toast } from "sonner";

import type { ApiClientError } from "@/lib/api";

type TFn = (path: string) => string;

export function toastApiError(err: unknown, t: TFn, title: string) {
  const guide = [
    t("errors.guideTitle"),
    `• ${t("errors.checkApiUrl")}`,
    `• ${t("errors.checkCors")}`,
    `• ${t("errors.checkDocs")}`,
    `• ${t("errors.openConsole")}`,
  ].join("\n");

  if (err && typeof err === "object" && "name" in err && err.name === "ApiClientError") {
    const e = err as ApiClientError;
    const rid = e.requestId
      ? `\n${t("errors.requestId")}: ${e.requestId}`
      : "";
    toast.error(title, {
      description: `${e.message}${rid}\n\n${guide}`,
      duration: 12_000,
    });
    return;
  }

  if (err instanceof TypeError) {
    toast.error(title, {
      description: `${t("toast.network")}\n\n${guide}`,
      duration: 12_000,
    });
    return;
  }

  toast.error(title, {
    description: guide,
    duration: 10_000,
  });
}
