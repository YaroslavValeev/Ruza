import type { CapacitorConfig } from "@capacitor/cli";

const lanHost = process.env.MOBILE_LAN_HOST || "127.0.0.1";

const config: CapacitorConfig = {
  appId: "club.icebeach.wake",
  appName: "Ice Beach",
  webDir: "dist",
  server: {
    androidScheme: "http",
    cleartext: true,
    url: process.env.CAPACITOR_SERVER_URL || `http://${lanHost}:5173`,
  },
  android: {
    allowMixedContent: true,
  },
};

export default config;
