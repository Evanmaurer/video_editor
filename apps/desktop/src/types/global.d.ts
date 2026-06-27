import type { MontageAPI } from "../../electron/preload/index";

declare global {
  interface Window {
    montageAPI: MontageAPI;
  }
}

export {};
