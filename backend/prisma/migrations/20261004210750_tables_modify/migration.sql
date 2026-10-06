-- CreateEnum
CREATE TYPE "TripStatus" AS ENUM ('PLANNING', 'SPOTS_SELECTED', 'HOTEL_SELECTED', 'FLIGHTS_SELECTED', 'COMPLETED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "FlightDirection" AS ENUM ('OUTBOUND', 'RETURN');

-- CreateTable
CREATE TABLE "trip" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "destination" TEXT NOT NULL,
    "country" TEXT,
    "startDate" TIMESTAMP(3) NOT NULL,
    "endDate" TIMESTAMP(3) NOT NULL,
    "travelers" INTEGER NOT NULL DEFAULT 1,
    "status" "TripStatus" NOT NULL DEFAULT 'PLANNING',
    "budgetAmount" DECIMAL(12,2),
    "budgetCurrency" TEXT,
    "vibes" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "trip_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "trip_spot" (
    "id" TEXT NOT NULL,
    "tripId" TEXT NOT NULL,
    "provider" TEXT,
    "providerId" TEXT,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "address" TEXT,
    "latitude" DECIMAL(10,7),
    "longitude" DECIMAL(10,7),
    "category" TEXT,
    "imageUrl" TEXT,
    "isSelected" BOOLEAN NOT NULL DEFAULT false,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "trip_spot_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "trip_hotel" (
    "id" TEXT NOT NULL,
    "tripId" TEXT NOT NULL,
    "provider" TEXT,
    "providerId" TEXT,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "address" TEXT,
    "latitude" DECIMAL(10,7),
    "longitude" DECIMAL(10,7),
    "pricePerNight" DECIMAL(12,2),
    "totalPrice" DECIMAL(12,2),
    "currency" TEXT,
    "rating" DECIMAL(3,2),
    "starRating" INTEGER,
    "reviewCount" INTEGER,
    "imageUrl" TEXT,
    "isSelected" BOOLEAN NOT NULL DEFAULT false,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "trip_hotel_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "trip_flight" (
    "id" TEXT NOT NULL,
    "tripId" TEXT NOT NULL,
    "provider" TEXT,
    "providerId" TEXT,
    "flightDirection" "FlightDirection" NOT NULL,
    "departureAirport" TEXT NOT NULL,
    "arrivalAirport" TEXT NOT NULL,
    "departureCity" TEXT,
    "arrivalCity" TEXT,
    "departureTime" TIMESTAMP(3) NOT NULL,
    "arrivalTime" TIMESTAMP(3) NOT NULL,
    "airline" TEXT,
    "airlineCode" TEXT,
    "flightNumber" TEXT,
    "durationMinutes" INTEGER,
    "stops" INTEGER NOT NULL DEFAULT 0,
    "price" DECIMAL(12,2),
    "currency" TEXT,
    "bookingUrl" TEXT,
    "isSelected" BOOLEAN NOT NULL DEFAULT false,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "trip_flight_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "budget_estimate" (
    "id" TEXT NOT NULL,
    "tripId" TEXT NOT NULL,
    "durationDays" INTEGER NOT NULL,
    "isInternational" BOOLEAN NOT NULL DEFAULT false,
    "vibes" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "estimatedFlightCost" DECIMAL(12,2),
    "estimatedHotelCost" DECIMAL(12,2),
    "estimatedFoodCost" DECIMAL(12,2),
    "estimatedActivityCost" DECIMAL(12,2),
    "estimatedTransportCost" DECIMAL(12,2),
    "estimatedTotal" DECIMAL(12,2),
    "currency" TEXT,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "budget_estimate_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "savings_suggestion" (
    "id" TEXT NOT NULL,
    "tripId" TEXT NOT NULL,
    "flightPrice" DECIMAL(12,2),
    "hotelPricePerNight" DECIMAL(12,2),
    "nights" INTEGER,
    "stayBudget" DECIMAL(12,2),
    "currency" TEXT,
    "suggestions" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "savings_suggestion_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "trip_summary" (
    "id" TEXT NOT NULL,
    "tripId" TEXT NOT NULL,
    "city" TEXT NOT NULL,
    "country" TEXT,
    "hotelLatitude" DECIMAL(10,7),
    "hotelLongitude" DECIMAL(10,7),
    "selectedSpots" JSONB NOT NULL,
    "flightPrice" DECIMAL(12,2),
    "hotelTotalPrice" DECIMAL(12,2),
    "nights" INTEGER NOT NULL,
    "totalCost" DECIMAL(12,2),
    "currency" TEXT,
    "summary" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "trip_summary_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "trip_userId_idx" ON "trip"("userId");

-- CreateIndex
CREATE INDEX "trip_destination_idx" ON "trip"("destination");

-- CreateIndex
CREATE INDEX "trip_spot_tripId_idx" ON "trip_spot"("tripId");

-- CreateIndex
CREATE INDEX "trip_spot_tripId_isSelected_idx" ON "trip_spot"("tripId", "isSelected");

-- CreateIndex
CREATE INDEX "trip_hotel_tripId_idx" ON "trip_hotel"("tripId");

-- CreateIndex
CREATE INDEX "trip_hotel_tripId_isSelected_idx" ON "trip_hotel"("tripId", "isSelected");

-- CreateIndex
CREATE INDEX "trip_flight_tripId_idx" ON "trip_flight"("tripId");

-- CreateIndex
CREATE INDEX "trip_flight_tripId_flightDirection_idx" ON "trip_flight"("tripId", "flightDirection");

-- CreateIndex
CREATE INDEX "trip_flight_tripId_isSelected_idx" ON "trip_flight"("tripId", "isSelected");

-- CreateIndex
CREATE UNIQUE INDEX "budget_estimate_tripId_key" ON "budget_estimate"("tripId");

-- CreateIndex
CREATE INDEX "savings_suggestion_tripId_idx" ON "savings_suggestion"("tripId");

-- CreateIndex
CREATE UNIQUE INDEX "trip_summary_tripId_key" ON "trip_summary"("tripId");

-- AddForeignKey
ALTER TABLE "trip" ADD CONSTRAINT "trip_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "trip_spot" ADD CONSTRAINT "trip_spot_tripId_fkey" FOREIGN KEY ("tripId") REFERENCES "trip"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "trip_hotel" ADD CONSTRAINT "trip_hotel_tripId_fkey" FOREIGN KEY ("tripId") REFERENCES "trip"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "trip_flight" ADD CONSTRAINT "trip_flight_tripId_fkey" FOREIGN KEY ("tripId") REFERENCES "trip"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "budget_estimate" ADD CONSTRAINT "budget_estimate_tripId_fkey" FOREIGN KEY ("tripId") REFERENCES "trip"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "savings_suggestion" ADD CONSTRAINT "savings_suggestion_tripId_fkey" FOREIGN KEY ("tripId") REFERENCES "trip"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "trip_summary" ADD CONSTRAINT "trip_summary_tripId_fkey" FOREIGN KEY ("tripId") REFERENCES "trip"("id") ON DELETE CASCADE ON UPDATE CASCADE;
