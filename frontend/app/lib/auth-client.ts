import { createAuthClient } from "better-auth/react";

function getBaseUrl() {
  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    if (process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_URL.includes("localhost")) {
      return process.env.NEXT_PUBLIC_API_URL;
    }
    return `${protocol}//${hostname}:5000`;
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
}

export const authClient = createAuthClient({
  baseURL: getBaseUrl(),
});

export const { signIn, signUp, signOut, useSession } = authClient;
