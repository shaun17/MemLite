export class MemLiteClientError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MemLiteClientError";
  }
}

export class MemLiteApiError extends MemLiteClientError {
  statusCode: number;
  responseBody: unknown;

  constructor(message: string, statusCode: number, responseBody: unknown) {
    super(message);
    this.name = "MemLiteApiError";
    this.statusCode = statusCode;
    this.responseBody = responseBody;
  }
}
