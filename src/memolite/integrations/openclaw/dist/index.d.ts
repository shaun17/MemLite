type OpenClawContext = {
    sessionKey?: string;
};
type OpenClawLogger = {
    info(message: string): void;
    warn(message: string): void;
    error(message: string): void;
};
type OpenClawPluginApi = {
    pluginConfig?: Record<string, unknown>;
    logger: OpenClawLogger;
    registerTool(factory: (ctx: OpenClawContext) => unknown, meta?: {
        name: string;
    }): void;
    registerService(service: {
        id: string;
        start: () => void;
        stop: () => void;
    }): void;
    on(event: string, handler: (event: any, ctx: OpenClawContext) => Promise<unknown> | unknown): void;
};
declare const memlitePlugin: {
    id: string;
    name: string;
    description: string;
    kind: "memory";
    configSchema: {
        jsonSchema: {
            readonly type: "object";
            readonly additionalProperties: false;
            readonly properties: {
                readonly baseUrl: {
                    readonly type: "string";
                };
                readonly userId: {
                    readonly type: "string";
                };
                readonly orgId: {
                    readonly type: "string";
                };
                readonly projectId: {
                    readonly type: "string";
                };
                readonly autoCapture: {
                    readonly type: "boolean";
                };
                readonly autoRecall: {
                    readonly type: "boolean";
                };
                readonly searchThreshold: {
                    readonly type: "number";
                };
                readonly topK: {
                    readonly type: "number";
                };
            };
            readonly required: readonly [];
        };
    };
    register(api: OpenClawPluginApi): void;
};

export { memlitePlugin as default };
