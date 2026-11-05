import type { paths } from "@orchestra/contracts";
import createClient from "openapi-fetch";

// Same-origin: Vite dev proxy (browser) or the backend itself (Electron). ADR-0001/0009.
export const api = createClient<paths>({ baseUrl: "" });

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Return data or throw a structured error. Never pretend a failed call succeeded. */
export function unwrap<T>(result: Result<T>): T {
  if (result.error !== undefined || !result.response.ok) {
    throw toApiError(result.response.status, result.error);
  }
  return result.data as T;
}

export function toApiError(status: number, body: unknown): ApiRequestError {
  const err = (body as { error?: { code?: string; message?: string; details?: unknown } })?.error;
  if (err?.code) return new ApiRequestError(status, err.code, err.message ?? err.code, err.details);
  if (status === 0 || status === 502 || status === 504) {
    return new ApiRequestError(status, "backend_unreachable", "Không kết nối được backend");
  }
  return new ApiRequestError(status, "http_error", `HTTP ${status}`);
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiRequestError) return `${e.message} (${e.code})`;
  if (e instanceof Error) return e.message;
  return String(e);
}
