'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { sendTripChat, startTripChat } from '../../lib/api/trips';
import { ChatResponse, ChatTurnResponse, Money } from '../../lib/api/schemas';
import { formatMoney } from '../../lib/formatMoney';

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  turnResponse?: ChatTurnResponse;
  stateSummary?: Record<string, unknown>;
  tripStatus?: string;
}

interface ChatBotProps {
  tripId?: string;
  onTripCreated?: (tripId: string) => void;
  className?: string;
}

interface DestinationOptionItem {
  city?: string;
  country?: string;
  vibeMatchScore?: number;
  reason?: string;
  estimatedFlightPrice?: Money;
}

interface SpotOptionItem {
  name?: string;
  title?: string;
  category?: string;
  rating?: number;
}

interface HotelOptionItem {
  name?: string;
  star_rating?: number;
  distance_km_from_cluster?: number;
  rate_per_night?: Money | number;
  ratePerNight?: Money | number;
  price?: Money | number;
}

interface FlightOptionItem {
  airline?: string;
  is_best?: boolean;
  departure_time?: string;
  arrival_time?: string;
  total_duration_minutes?: number;
  price?: Money | number;
}

interface ItineraryDayItem {
  day?: number;
  stops?: Array<{
    name?: string;
    travel_minutes_from_previous?: number;
  }>;
}

export const ChatBot: React.FC<ChatBotProps> = ({
  tripId: initialTripId,
  onTripCreated,
  className = '',
}) => {
  const router = useRouter();
  const [currentTripId, setCurrentTripId] = useState<string | undefined>(initialTripId);
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    !initialTripId
      ? [
          {
            id: 'welcome',
            sender: 'assistant',
            text: "Hello! I am your AI Travel Concierge. Tell me where you'd like to travel, or describe your dream vacation (destination, dates, budget, or preferred vibes) and I will plan and book everything for you!",
            timestamp: new Date(),
          },
        ]
      : []
  );
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedSpots, setSelectedSpots] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialTriggerRef = useRef(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = useCallback(
    async (textToSend?: string) => {
      const text = (textToSend || inputValue).trim();
      if (!text || isLoading) return;

      const userMessage: ChatMessage = {
        id: `msg-${Date.now()}`,
        sender: 'user',
        text,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      if (!textToSend) setInputValue('');
      setIsLoading(true);

      try {
        let res: ChatResponse;
        if (currentTripId) {
          res = await sendTripChat(currentTripId, text);
        } else {
          res = await startTripChat(text);
          if (res.tripId && res.tripId !== currentTripId) {
            setCurrentTripId(res.tripId);
            if (onTripCreated) {
              onTripCreated(res.tripId);
            }
          }
        }

        const assistantMessage: ChatMessage = {
          id: `msg-${Date.now() + 1}`,
          sender: 'assistant',
          text: res.turnResponse.reply || 'Here is what I found for you.',
          timestamp: new Date(),
          turnResponse: res.turnResponse,
          stateSummary: res.stateSummary,
          tripStatus: res.tripStatus,
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err: unknown) {
        const errorText =
          err instanceof Error
            ? err.message
            : 'Sorry, I encountered an issue while processing that. Please try again.';
        const errorMessage: ChatMessage = {
          id: `err-${Date.now()}`,
          sender: 'assistant',
          text: errorText,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
      }
    },
    [currentTripId, inputValue, isLoading, onTripCreated]
  );

  // Initial greeting or initial context trigger
  useEffect(() => {
    if (!initialTriggerRef.current) {
      initialTriggerRef.current = true;
      if (initialTripId) {
        const timer = setTimeout(() => {
          handleSend('Hi, can you show my trip status and next steps?');
        }, 0);
        return () => clearTimeout(timer);
      }
    }
  }, [initialTripId, handleSend]);

  const handleSelectOption = (optionText: string) => {
    handleSend(optionText);
  };

  const handleToggleSpot = (name: string) => {
    setSelectedSpots((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]
    );
  };

  const handleConfirmSelectedSpots = () => {
    if (selectedSpots.length === 0) return;
    const msg = `I want to visit: ${selectedSpots.join(', ')}`;
    setSelectedSpots([]);
    handleSend(msg);
  };

  return (
    <div
      className={`flex flex-col h-[700px] max-h-[85vh] bg-white rounded-3xl border border-slate-200/90 shadow-xl overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-500 to-violet-500 flex items-center justify-center text-white shadow-md">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
          </div>
          <div>
            <h2 className="text-base font-bold tracking-tight">AI Travel Concierge</h2>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs text-slate-400">Live Assistant</span>
            </div>
          </div>
        </div>

        {currentTripId && (
          <button
            onClick={() => router.push(`/trips/${currentTripId}/summary`)}
            className="text-xs font-semibold px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-indigo-500/30 transition-all flex items-center gap-1.5"
          >
            <span>View Full Summary</span>
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        )}
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/50">
        {messages.map((msg) => {
          const isUser = msg.sender === 'user';
          const uiComponent = msg.turnResponse?.uiComponent;
          const options = msg.turnResponse?.options || [];

          return (
            <div
              key={msg.id}
              className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-full`}
            >
              <div
                className={`flex gap-3 max-w-[88%] sm:max-w-[80%] ${
                  isUser ? 'flex-row-reverse' : 'flex-row'
                }`}
              >
                {!isUser && (
                  <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex-shrink-0 flex items-center justify-center font-bold text-xs shadow-sm mt-1">
                    AI
                  </div>
                )}

                <div
                  className={`rounded-2xl px-5 py-3.5 text-sm leading-relaxed shadow-sm ${
                    isUser
                      ? 'bg-indigo-600 text-white rounded-tr-none'
                      : 'bg-white text-slate-800 border border-slate-200/80 rounded-tl-none'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                </div>
              </div>

              {/* Dynamic Interactive Components */}
              {!isUser && uiComponent && options.length > 0 && (
                <div className="w-full mt-4 pl-11">
                  {/* Destination Options */}
                  {uiComponent === 'destination_options' && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {(options as unknown as DestinationOptionItem[]).map((opt, idx) => (
                        <div
                          key={idx}
                          className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:border-indigo-400 transition-all flex flex-col justify-between"
                        >
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <h4 className="font-bold text-slate-900">{opt.city || 'City'}</h4>
                              {typeof opt.vibeMatchScore === 'number' && (
                                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  {Math.round(opt.vibeMatchScore * 100)}% match
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-slate-500 mb-2">{opt.country}</p>
                            {opt.reason && (
                              <p className="text-xs text-slate-600 italic mb-3">&ldquo;{opt.reason}&rdquo;</p>
                            )}
                            {opt.estimatedFlightPrice && (
                              <p className="text-xs font-semibold text-slate-800 mb-3">
                                Est. Flight: {formatMoney(opt.estimatedFlightPrice)}
                              </p>
                            )}
                          </div>
                          {opt.city && (
                            <button
                              onClick={() => handleSelectOption(`I choose ${opt.city}`)}
                              className="w-full py-1.5 px-3 text-xs font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-600 hover:text-white rounded-lg transition-all"
                            >
                              Choose {opt.city}
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Attraction / Spots Options */}
                  {uiComponent === 'attraction_options' && (
                    <div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                        {(options as unknown as SpotOptionItem[]).map((spot, idx) => {
                          const spotName = spot.name || spot.title || `Spot ${idx + 1}`;
                          const isSelected = selectedSpots.includes(spotName);

                          return (
                            <div
                              key={idx}
                              onClick={() => handleToggleSpot(spotName)}
                              className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-start gap-3 ${
                                isSelected
                                  ? 'bg-indigo-50/70 border-indigo-500 ring-2 ring-indigo-400/20'
                                  : 'bg-white border-slate-200 hover:border-slate-300'
                              }`}
                            >
                              <div
                                className={`w-4 h-4 mt-0.5 rounded flex items-center justify-center border text-white text-[10px] ${
                                  isSelected ? 'bg-indigo-600 border-indigo-600' : 'border-slate-300'
                                }`}
                              >
                                {isSelected && '✓'}
                              </div>
                              <div className="flex-1">
                                <h4 className="font-bold text-xs text-slate-900">{spotName}</h4>
                                {spot.category && (
                                  <span className="text-[10px] text-slate-500 uppercase tracking-wider block mt-0.5">
                                    {spot.category}
                                  </span>
                                )}
                                {spot.rating && (
                                  <span className="text-[11px] font-semibold text-amber-600 mt-1 block">
                                    ★ {spot.rating}
                                  </span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {selectedSpots.length > 0 && (
                        <button
                          onClick={handleConfirmSelectedSpots}
                          className="px-4 py-2 text-xs font-bold bg-indigo-600 text-white rounded-xl shadow-sm hover:bg-indigo-700 transition-all"
                        >
                          Confirm {selectedSpots.length} Selected Spot{selectedSpots.length > 1 ? 's' : ''}
                        </button>
                      )}
                    </div>
                  )}

                  {/* Hotel Options */}
                  {uiComponent === 'hotel_options' && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {(options as unknown as HotelOptionItem[]).map((hotel, idx) => {
                        const hotelName = hotel.name || `Hotel ${idx + 1}`;
                        const rate = hotel.rate_per_night || hotel.ratePerNight || hotel.price;

                        return (
                          <div
                            key={idx}
                            className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:border-indigo-400 transition-all flex flex-col justify-between"
                          >
                            <div>
                              <div className="flex items-start justify-between gap-1 mb-1">
                                <h4 className="font-bold text-xs text-slate-900">{hotelName}</h4>
                                {hotel.star_rating && (
                                  <span className="text-[11px] font-semibold text-amber-500">
                                    ★ {hotel.star_rating}
                                  </span>
                                )}
                              </div>
                              {hotel.distance_km_from_cluster && (
                                <p className="text-[11px] text-slate-500 mb-2">
                                  {hotel.distance_km_from_cluster.toFixed(1)} km from attractions
                                </p>
                              )}
                              {rate && (
                                <p className="text-xs font-bold text-slate-800 mb-3">
                                  Rate:{' '}
                                  {typeof rate === 'object' && 'amountMinor' in rate
                                    ? formatMoney(rate as Money)
                                    : `₹${rate}`}{' '}
                                  / night
                                </p>
                              )}
                            </div>
                            <button
                              onClick={() => handleSelectOption(`I choose ${hotelName}`)}
                              className="w-full py-1.5 px-3 text-xs font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-600 hover:text-white rounded-lg transition-all"
                            >
                              Select {hotelName}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Flight Options */}
                  {uiComponent === 'flight_options' && (
                    <div className="space-y-2">
                      {(options as unknown as FlightOptionItem[]).map((flight, idx) => {
                        const airline = flight.airline || 'Flight Option';
                        const price = flight.price;

                        return (
                          <div
                            key={idx}
                            className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between gap-4"
                          >
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-xs text-slate-900">{airline}</span>
                                {flight.is_best && (
                                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                                    Best Value
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] text-slate-500 mt-1">
                                {flight.departure_time || 'Dep'} → {flight.arrival_time || 'Arr'} •{' '}
                                {flight.total_duration_minutes
                                  ? `${Math.round(flight.total_duration_minutes / 60)}h`
                                  : ''}
                              </p>
                              {price && (
                                <p className="text-xs font-bold text-slate-800 mt-1">
                                  {typeof price === 'object' && 'amountMinor' in price
                                    ? formatMoney(price as Money)
                                    : `₹${price}`}
                                </p>
                              )}
                            </div>
                            <button
                              onClick={() => handleSelectOption(`I choose flight ${airline}`)}
                              className="py-1.5 px-3 text-xs font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-600 hover:text-white rounded-lg transition-all whitespace-nowrap"
                            >
                              Select Flight
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Itinerary */}
                  {uiComponent === 'itinerary' && Array.isArray(options) && (
                    <div className="space-y-3 bg-white p-4 rounded-2xl border border-slate-200">
                      <h4 className="font-bold text-xs uppercase tracking-wider text-slate-500 mb-2">
                        Generated Itinerary
                      </h4>
                      {(options as unknown as ItineraryDayItem[]).map((dayPlan, dIdx) => (
                        <div key={dIdx} className="border-l-2 border-indigo-400 pl-3 py-1">
                          <h5 className="font-bold text-xs text-indigo-900">Day {dayPlan.day || dIdx + 1}</h5>
                          <ul className="mt-1 space-y-1">
                            {(dayPlan.stops || []).map((stop, sIdx) => (
                              <li key={sIdx} className="text-xs text-slate-600 flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                                <span>{stop.name}</span>
                                {typeof stop.travel_minutes_from_previous === 'number' && (
                                  <span className="text-[10px] text-slate-400">
                                    ({stop.travel_minutes_from_previous} mins commute)
                                  </span>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {isLoading && (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shadow-sm">
              AI
            </div>
            <div className="bg-white border border-slate-200/80 px-4 py-3 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" />
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce [animation-delay:0.2s]" />
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce [animation-delay:0.4s]" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <div className="p-4 bg-white border-t border-slate-200/90">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type your message, change preferences, or choose options..."
            disabled={isLoading}
            className="flex-1 px-4 py-3 text-sm bg-slate-50 border border-slate-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-800 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={isLoading || !inputValue.trim()}
            className="px-5 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-bold text-sm rounded-2xl transition-all shadow-md shadow-indigo-500/20 flex items-center gap-1.5"
          >
            <span>Send</span>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
};
