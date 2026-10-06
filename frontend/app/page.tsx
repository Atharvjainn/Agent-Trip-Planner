"use client";

import { useState } from "react";
import { useSession, signIn, signUp, signOut } from "./lib/auth-client";

export default function Home() {
  const { data: session, isPending, refetch } = useSession();

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [protectedData, setProtectedData] = useState<unknown>(null);
  const [loadingProtected, setLoadingProtected] = useState(false);

  const resetStatus = () => {
    setErrorMsg(null);
    setSuccessMsg(null);
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    resetStatus();
    setLoading(true);

    await signUp.email(
      {
        email,
        password,
        name,
      },
      {
        onSuccess: () => {
          setSuccessMsg("Account created successfully!");
          refetch();
        },
        onError: (ctx) => {
          setErrorMsg(ctx.error.message || "Failed to sign up.");
        },
      }
    );
    setLoading(false);
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    resetStatus();
    setLoading(true);

    await signIn.email(
      {
        email,
        password,
      },
      {
        onSuccess: () => {
          setSuccessMsg("Signed in successfully!");
          refetch();
        },
        onError: (ctx) => {
          setErrorMsg(ctx.error.message || "Failed to sign in.");
        },
      }
    );
    setLoading(false);
  };

  const handleGoogleSignIn = async () => {
    resetStatus();
    await signIn.social({
      provider: "google",
      callbackURL: window.location.origin,
    });
  };

  const testProtectedRoute = async () => {
    setLoadingProtected(true);
    setProtectedData(null);
    try {
      const res = await fetch("http://localhost:5000/api/me", {
        credentials: "include",
      });
      const data = await res.json();
      setProtectedData(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network error while calling /api/me";
      setProtectedData({
        status: "error",
        message: msg,
      });
    } finally {
      setLoadingProtected(false);
    }
  };

  const handleSignOut = async () => {
    resetStatus();
    setProtectedData(null);
    await signOut({
      fetchOptions: {
        onSuccess: () => {
          refetch();
        },
      },
    });
  };

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col items-center justify-center p-6 antialiased selection:bg-indigo-500 selection:text-white">
      <div className="w-full max-w-md bg-neutral-900/90 border border-neutral-800 rounded-2xl p-8 shadow-2xl backdrop-blur-xl space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 font-bold text-xl mb-1">
            ✈️
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Travel Planner
          </h1>
          <p className="text-sm text-neutral-400">
            Better Auth & Express Backend Integration
          </p>
        </div>

        {/* Feedback messages */}
        {errorMsg && (
          <div className="p-3 bg-red-950/60 border border-red-800 text-red-300 text-sm rounded-xl">
            {errorMsg}
          </div>
        )}
        {successMsg && (
          <div className="p-3 bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-sm rounded-xl">
            {successMsg}
          </div>
        )}

        {/* Content based on session */}
        {isPending ? (
          <div className="text-center py-8 text-neutral-400 animate-pulse">
            Checking session...
          </div>
        ) : session?.user ? (
          <div className="space-y-6">
            {/* User Profile Card */}
            <div className="bg-neutral-800/60 border border-neutral-700/50 rounded-xl p-4 space-y-3">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white font-semibold text-lg">
                  {session.user.name?.charAt(0).toUpperCase() || "U"}
                </div>
                <div className="overflow-hidden">
                  <p className="font-semibold text-white truncate">
                    {session.user.name || "Anonymous User"}
                  </p>
                  <p className="text-xs text-neutral-400 truncate">
                    {session.user.email}
                  </p>
                </div>
              </div>
              <div className="pt-2 border-t border-neutral-700/50 flex justify-between items-center text-xs text-neutral-400">
                <span>User ID:</span>
                <span className="font-mono text-neutral-300 truncate max-w-[200px]">
                  {session.user.id}
                </span>
              </div>
            </div>

            {/* Travel Planner Action */}
            <a
              href="/trips/new"
              className="block w-full py-3 px-4 text-center bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold rounded-xl transition duration-150 shadow-lg shadow-indigo-600/25"
            >
              Start Planning Trip →
            </a>

            {/* Actions */}
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={testProtectedRoute}
                disabled={loadingProtected}
                className="w-full py-2.5 px-4 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-sm font-medium rounded-xl border border-neutral-700 transition duration-150"
              >
                {loadingProtected ? "Calling..." : "Test GET /api/me"}
              </button>
              <button
                onClick={handleSignOut}
                className="w-full py-2.5 px-4 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-sm font-medium rounded-xl border border-neutral-700 transition duration-150"
              >
                Sign Out
              </button>
            </div>

            {/* Protected Route Output */}
            {Boolean(protectedData) && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
                  Backend Response (/api/me)
                </p>
                <pre className="p-3 bg-neutral-950 border border-neutral-800 rounded-xl text-xs font-mono text-emerald-400 overflow-x-auto max-h-48">
                  {JSON.stringify(protectedData, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Mode Switcher */}
            <div className="flex bg-neutral-950 p-1 rounded-xl border border-neutral-800">
              <button
                type="button"
                onClick={() => {
                  setMode("signin");
                  resetStatus();
                }}
                className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition ${
                  mode === "signin"
                    ? "bg-neutral-800 text-white shadow-sm"
                    : "text-neutral-400 hover:text-neutral-200"
                }`}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode("signup");
                  resetStatus();
                }}
                className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition ${
                  mode === "signup"
                    ? "bg-neutral-800 text-white shadow-sm"
                    : "text-neutral-400 hover:text-neutral-200"
                }`}
              >
                Sign Up
              </button>
            </div>

            <form
              onSubmit={mode === "signin" ? handleSignIn : handleSignUp}
              className="space-y-3"
            >
              {mode === "signup" && (
                <div>
                  <label className="block text-xs font-medium text-neutral-300 mb-1">
                    Name
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="John Doe"
                    className="w-full px-3.5 py-2.5 bg-neutral-950 border border-neutral-800 focus:border-indigo-500 focus:outline-none rounded-xl text-sm text-neutral-100 placeholder-neutral-600 transition"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="traveler@example.com"
                  className="w-full px-3.5 py-2.5 bg-neutral-950 border border-neutral-800 focus:border-indigo-500 focus:outline-none rounded-xl text-sm text-neutral-100 placeholder-neutral-600 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 bg-neutral-950 border border-neutral-800 focus:border-indigo-500 focus:outline-none rounded-xl text-sm text-neutral-100 placeholder-neutral-600 transition"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition duration-150 shadow-lg shadow-indigo-600/25"
              >
                {loading
                  ? "Processing..."
                  : mode === "signin"
                  ? "Sign In"
                  : "Create Account"}
              </button>
            </form>

            <div className="relative flex py-1 items-center">
              <div className="flex-grow border-t border-neutral-800"></div>
              <span className="flex-shrink mx-3 text-xs text-neutral-500">OR</span>
              <div className="flex-grow border-t border-neutral-800"></div>
            </div>

            <button
              type="button"
              onClick={handleGoogleSignIn}
              className="w-full py-2.5 px-4 bg-neutral-950 hover:bg-neutral-800/80 border border-neutral-800 text-neutral-200 text-sm font-medium rounded-xl transition duration-150 flex items-center justify-center space-x-2"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              <span>Continue with Google</span>
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
