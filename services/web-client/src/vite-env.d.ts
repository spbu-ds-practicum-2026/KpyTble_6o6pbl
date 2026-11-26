/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_WS_URL?: string;
  readonly VITE_RETRY_PENDING_COMMANDS?: string;
  readonly VITE_HEARTBEAT_TIMEOUT_MS?: string;
  readonly VITE_STATE_SYNC_INTERVAL_MS?: string;
  readonly VITE_RUTUBE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
