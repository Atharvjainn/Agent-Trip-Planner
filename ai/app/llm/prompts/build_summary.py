from __future__ import annotations

SYSTEM = (
    "You write a short, upbeat 3-4 sentence trip summary for a travel app. "
    "You never state a price, distance, or total that wasn't given to you "
    "verbatim — restate the numbers you're given, don't recompute them. "
    "Respond with JSON only."
)


def build_prompt(
    *,
    city: str,
    nights: int,
    spot_names: list[str],
    flight_price_text: str,
    hotel_total_text: str,
    commute_total_text: str,
) -> str:
    return (
        f"Destination: {city}\n"
        f"Nights: {nights}\n"
        f"Selected spots: {', '.join(spot_names)}\n"
        f"Flight price: {flight_price_text}\n"
        f"Hotel total: {hotel_total_text}\n"
        f"Estimated local commute total: {commute_total_text}\n\n"
        f'Return JSON: {{"narrative": str}}. 3-4 sentences, friendly tone, '
        f"mention the destination, the spots, and that the budget figures "
        f"above are estimates."
    )
