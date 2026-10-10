'use client';

import React, { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { useSession, signOut } from '../lib/auth-client';
import { Spinner } from '../components/ui/Spinner';
import { Button } from '../components/ui/Button';

export default function TripsLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: session, isPending } = useSession();

  const tripMatch = pathname.match(/^\/trips\/([^/]+)/);
  const activeTripId = tripMatch && tripMatch[1] !== 'new' ? tripMatch[1] : null;
  const isChatPage = pathname.endsWith('/chat');

  useEffect(() => {
    if (!isPending && !session) {
      router.push('/');
    }
  }, [session, isPending, router]);

  if (isPending) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!session) {
    return null;
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      {/* App Navigation */}
      <header className="bg-white border-b border-slate-200/80 sticky top-0 z-50 backdrop-blur-md bg-white/90">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link href="/trips/new" className="flex items-center gap-2">
            <span className="text-xl font-black bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
              TravelFlow
            </span>
          </Link>

          <div className="flex items-center gap-4">
            <Link
              href="/trips/new"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50 px-3 py-1.5 rounded-xl border border-indigo-100 transition-all"
            >
              + New Trip
            </Link>
            <span className="text-xs sm:text-sm text-slate-600 hidden sm:inline">
              {session.user.name || session.user.email}
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                await signOut();
                router.push('/');
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8">
        {children}
      </main>

      {/* Floating Chat Button for Active Trips */}
      {activeTripId && !isChatPage && (
        <div className="fixed bottom-6 right-6 z-40">
          <Link
            href={`/trips/${activeTripId}/chat`}
            className="flex items-center gap-2.5 px-5 py-3 rounded-2xl bg-slate-900 text-white font-bold text-sm shadow-xl shadow-slate-900/25 hover:bg-slate-800 hover:scale-105 active:scale-95 transition-all border border-slate-700/60"
          >
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
            <span>Ask AI Concierge</span>
          </Link>
        </div>
      )}
    </div>
  );
}
