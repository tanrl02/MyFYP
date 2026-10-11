import { Platform } from "react-native";

// Expo serves both desktop web and Android. Desktop localhost uses the local API;
// the phone needs the computer's LAN address injected by Start-Mobile.cmd.
export const apiBase = Platform.OS === "web" && typeof window !== "undefined" &&
  ["localhost", "127.0.0.1"].includes(window.location.hostname)
  ? `http://${window.location.hostname}:8000`
  : process.env.EXPO_PUBLIC_API_URL || "http://127.0.0.1:8000";
