import { getConfig } from "./api/client";

// Dash0 real-user monitoring. The backend decides whether it is on (config.rum is null when off).
// The SDK is imported lazily so it is only downloaded when needed, and any failure is swallowed:
// telemetry must never break the app.
export async function startRum(): Promise<void> {
  try {
    const config = await getConfig();
    if (!config.rum) return;
    const dash0 = await import("@dash0/sdk-web");
    dash0.init({
      serviceName: "hallway-web",
      endpoint: { url: config.rum.url, authToken: config.rum.token },
    });
  } catch (err) {
    console.warn("RUM disabled:", err);
  }
}
