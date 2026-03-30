/**
 * PiNet OS Bridge SDK
 *
 * Provides a typed helper for communicating with the PiNet OS host
 * via the PostMessage bridge when Zedd Weather runs inside a PiNet
 * desktop iframe.
 */

/** Shape of a bridge response pushed by PiNet OS. */
interface PiNetBridgeResponse {
  type: 'pinet-bridge-response';
  requestId: string;
  success: boolean;
  data?: unknown;
  error?: string;
}

/** Shape of an event pushed by PiNet OS. */
export interface PiNetBridgeEvent {
  type: 'pinet-bridge-event';
  event: string;
  data: unknown;
}

/**
 * Send a single request to PiNet OS and wait for the matching response.
 *
 * @param method  Bridge method name (e.g. `wallet.getBalance`).
 * @param params  Optional key/value parameters for the method.
 * @returns       The `data` field from the bridge response.
 */
export function callPiNet(
  method: string,
  params: Record<string, unknown> = {},
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const requestId = crypto.randomUUID();

    const handler = (event: MessageEvent) => {
      const data = event.data as PiNetBridgeResponse | undefined;
      if (
        data?.type === 'pinet-bridge-response' &&
        data.requestId === requestId
      ) {
        window.removeEventListener('message', handler);
        if (data.success) {
          resolve(data.data);
        } else {
          reject(new Error(data.error ?? 'Bridge call failed'));
        }
      }
    };

    window.addEventListener('message', handler);

    window.parent.postMessage(
      {
        type: 'pinet-bridge-request',
        requestId,
        method,
        params,
      },
      '*',
    );

    // Timeout after 30 seconds
    setTimeout(() => {
      window.removeEventListener('message', handler);
      reject(new Error('Bridge call timed out'));
    }, 30_000);
  });
}

/** Listener callback for bridge events. */
export type PiNetEventListener = (event: string, data: unknown) => void;

/**
 * Subscribe to PiNet OS push events (blocks, balance changes, etc.).
 *
 * @param listener  Callback invoked for every bridge event.
 * @returns         A cleanup function that removes the listener.
 */
export function onPiNetEvent(listener: PiNetEventListener): () => void {
  const handler = (event: MessageEvent) => {
    const msg = event.data as PiNetBridgeEvent | undefined;
    if (msg?.type === 'pinet-bridge-event') {
      listener(msg.event, msg.data);
    }
  };

  window.addEventListener('message', handler);
  return () => window.removeEventListener('message', handler);
}

/**
 * Returns `true` when the page is running inside a PiNet OS iframe,
 * i.e. `window.parent` differs from `window`.
 */
export function isRunningInPiNet(): boolean {
  try {
    return window.self !== window.parent;
  } catch {
    return true; // cross-origin restriction → we are in an iframe
  }
}
