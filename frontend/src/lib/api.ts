import { z } from "zod";
import { config } from "./config";

/** Consistent error envelope returned by the backend (see ARCHITECTURE.md). */
export const ApiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.unknown().optional(),
  }),
});

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Thrown when the backend did not answer at all (cold start, network, timeout). */
export class ApiUnreachableError extends Error {
  constructor(message = "The analytics server did not respond") {
    super(message);
    this.name = "ApiUnreachableError";
  }
}

const DEFAULT_TIMEOUT_MS = 20_000;

type RequestOptions = { timeoutMs?: number; signal?: AbortSignal };

async function request<T>(
  method: "GET" | "POST",
  path: string,
  schema: z.ZodType<T>,
  body: unknown,
  { timeoutMs = DEFAULT_TIMEOUT_MS, signal }: RequestOptions,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  signal?.addEventListener("abort", () => controller.abort());

  let res: Response;
  try {
    res = await fetch(`${config.apiUrl}${path}`, {
      method,
      signal: controller.signal,
      headers:
        method === "POST"
          ? { Accept: "application/json", "Content-Type": "application/json" }
          : { Accept: "application/json" },
      body: method === "POST" ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiUnreachableError();
  } finally {
    clearTimeout(timer);
  }

  const json: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    // Render returns 502/503 while a sleeping service boots.
    if (res.status === 502 || res.status === 503 || res.status === 504) {
      throw new ApiUnreachableError();
    }
    const parsed = ApiErrorSchema.safeParse(json);
    if (parsed.success) {
      throw new ApiError(parsed.data.error.code, parsed.data.error.message, res.status);
    }
    throw new ApiError("http_error", `Request failed with status ${res.status}`, res.status);
  }
  return schema.parse(json);
}

export function apiGet<T>(path: string, schema: z.ZodType<T>, options: RequestOptions = {}) {
  return request("GET", path, schema, undefined, options);
}

export function apiPost<T>(
  path: string,
  body: unknown,
  schema: z.ZodType<T>,
  options: RequestOptions = {},
) {
  return request("POST", path, schema, body, options);
}

/** Query string from defined values only. */
export function qs(params: Record<string, string | number | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const HealthSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  version: z.string(),
  environment: z.string(),
  server_time: z.string(),
  database: z.object({
    status: z.enum(["ok", "unavailable", "not_configured"]),
    latency_ms: z.number().nullable(),
  }),
});
export type Health = z.infer<typeof HealthSchema>;
