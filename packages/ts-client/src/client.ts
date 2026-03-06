import { MemLiteApiError, MemLiteClientError } from "./errors";
import type { MemLiteClientOptions } from "./types";
import { MemLiteMemoryApi } from "./memory";
import { MemLiteProjectApi } from "./projects";

export class MemLiteClient {
  readonly baseUrl: string;
  readonly projects: MemLiteProjectApi;
  readonly memory: MemLiteMemoryApi;
  private readonly retries: number;
  private readonly retryBackoffMs: number;
  private readonly fetchImpl: typeof fetch;
  private readonly headers: Record<string, string>;

  constructor(options: MemLiteClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.retries = options.retries ?? 2;
    this.retryBackoffMs = options.retryBackoffMs ?? 50;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.headers = options.headers ?? {};
    this.projects = new MemLiteProjectApi(this);
    this.memory = new MemLiteMemoryApi(this);
  }

  async request<T>(
    method: string,
    path: string,
    options: {
      query?: Record<string, string | number | null | undefined>;
      body?: unknown;
    } = {},
  ): Promise<T> {
    let lastError: Error | null = null;
    const url = new URL(`${this.baseUrl}${path}`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }

    for (let attempt = 0; attempt <= this.retries; attempt += 1) {
      try {
        const response = await this.fetchImpl(url, {
          method,
          headers: {
            "content-type": "application/json",
            ...this.headers,
          },
          body: options.body === undefined ? undefined : JSON.stringify(options.body),
        });
        const payload = await decodeResponse(response);
        if (response.status >= 500 && attempt < this.retries) {
          await sleep(this.retryBackoffMs * (attempt + 1));
          continue;
        }
        if (!response.ok) {
          throw new MemLiteApiError(
            `${method.toUpperCase()} ${path} failed`,
            response.status,
            payload,
          );
        }
        return payload as T;
      } catch (error) {
        lastError = error as Error;
        if (error instanceof MemLiteApiError) {
          if (error.statusCode >= 500 && attempt < this.retries) {
            await sleep(this.retryBackoffMs * (attempt + 1));
            continue;
          }
          throw error;
        }
        if (attempt >= this.retries) {
          throw new MemLiteClientError(lastError.message);
        }
        await sleep(this.retryBackoffMs * (attempt + 1));
      }
    }

    throw new MemLiteClientError(lastError?.message ?? "request failed");
  }
}

const sleep = async (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

const decodeResponse = async (response: Response): Promise<unknown> => {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};
