'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useSession, signOut } from '../lib/auth-client';
import { Spinner } from '../components/ui/Spinner';
import { Button } from '../components/ui/Button';

export default function TripsLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: session, isPending } = useSession();

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
    </div>
  );
}
