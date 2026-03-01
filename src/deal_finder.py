"""
Investment deal finder and scoring engine.
Identifies opportunities based on market metrics and scores each county
on a 0-100 scale across multiple dimensions.
"""
from __future__ import annotations
import math


class DealFinder:

    # -------------------------------------------------------- find deals
    def find_deals(self, zhvi_data: dict, redfin_data: dict, market_stats: dict) -> list:
        """
        Identify current investment opportunities in the market.
        Returns a list of opportunity dicts ordered by score.
        """
        deals = []
        current = market_stats.get("current_zhvi", 0)
        pct_from_high = market_stats.get("pct_from_high", 0)
        gross_yield = market_stats.get("gross_rental_yield_pct", 0)
        net_yield = market_stats.get("net_rental_yield_pct", 0)
        price_to_rent = market_stats.get("price_to_rent_ratio", 20)
        price_to_income = market_stats.get("price_to_income_ratio", 5)
        affordability_idx = market_stats.get("affordability_index", 100)
        volatility = market_stats.get("volatility_pct", 10)

        # Redfin signals
        redfin_history = redfin_data.get("history", [])
        dom_trend = self._dom_trend(redfin_history)       # days on market trend
        inventory_tight = self._inventory_tight(redfin_history)

        # --- Opportunity 1: Buy-the-dip ---
        if pct_from_high <= -5:
            dip = abs(pct_from_high)
            score = min(dip * 2.5, 95)
            deals.append({
                "type": "Buy-the-Dip Opportunity",
                "icon": "📉",
                "description": (
                    f"Prices are {dip:.1f}% below the recent peak. "
                    "Markets that correct often recover to prior highs."
                ),
                "opportunity_score": round(score, 1),
                "action": "Target properties near the median price — the upside to prior peak is built-in.",
                "risk": "Medium",
                "risk_color": "#f59e0b",
                "metrics": {"below_peak_pct": round(dip, 1), "recovery_potential": round(dip, 1)},
            })

        # --- Opportunity 2: Cash flow (rental yield) ---
        if gross_yield >= 5.0:
            score = min((gross_yield - 4) * 15, 95)
            tier = "Strong" if gross_yield >= 7 else "Decent"
            deals.append({
                "type": f"{tier} Cash-Flow Rental",
                "icon": "🏠",
                "description": (
                    f"Gross rental yield of {gross_yield:.1f}% (net ~{net_yield:.1f}% after expenses). "
                    "Positive cash flow likely at standard leverage."
                ),
                "opportunity_score": round(score, 1),
                "action": (
                    "Buy-and-hold rental strategy. Run detailed cash flow analysis "
                    "with local property manager quotes."
                ),
                "risk": "Low-Medium" if gross_yield >= 7 else "Medium",
                "risk_color": "#10b981" if gross_yield >= 7 else "#f59e0b",
                "metrics": {
                    "gross_yield_pct": gross_yield,
                    "net_yield_pct": net_yield,
                    "price_to_rent": price_to_rent,
                },
            })

        # --- Opportunity 3: Affordability / entry point ---
        if price_to_income <= 4.0:
            score = min((5.0 - price_to_income) * 22, 95)
            deals.append({
                "type": "High-Affordability Entry Point",
                "icon": "💰",
                "description": (
                    f"Price-to-income ratio of {price_to_income:.1f}x is well below the national "
                    f"average (~6x). Broad pool of qualified buyers and renters."
                ),
                "opportunity_score": round(score, 1),
                "action": "Affordable markets sustain strong demand. Good for both rentals and future resale.",
                "risk": "Low",
                "risk_color": "#10b981",
                "metrics": {"price_to_income": price_to_income, "national_avg": 6.0},
            })

        # --- Opportunity 4: Favorable buy vs. rent ---
        if price_to_rent <= 18:
            score = min((22 - price_to_rent) * 5, 90)
            deals.append({
                "type": "Buy vs. Rent Advantage",
                "icon": "🔑",
                "description": (
                    f"Price-to-rent ratio of {price_to_rent:.1f} (below 18) means purchasing "
                    "beats renting financially over a 5-year horizon."
                ),
                "opportunity_score": round(score, 1),
                "action": "Ideal for owner-occupant investors and long-term buy-and-hold strategies.",
                "risk": "Low",
                "risk_color": "#10b981",
                "metrics": {"price_to_rent": price_to_rent, "benchmark": 18},
            })

        # --- Opportunity 5: Tight inventory / seller's market ---
        if inventory_tight:
            deals.append({
                "type": "Low-Inventory Market",
                "icon": "⚡",
                "description": (
                    "Redfin data shows declining inventory. Limited supply + sustained "
                    "demand historically drives price appreciation."
                ),
                "opportunity_score": 72.0,
                "action": "Move quickly — properties likely selling at or above list price. Pre-approval essential.",
                "risk": "Medium",
                "risk_color": "#f59e0b",
                "metrics": {"dom_trend": dom_trend},
            })

        # --- Opportunity 6: Low volatility (stable market) ---
        if volatility < 8:
            score = min((10 - volatility) * 8, 80)
            deals.append({
                "type": "Stable, Predictable Market",
                "icon": "🛡️",
                "description": (
                    f"Low price volatility ({volatility:.1f}%) indicates a steady market. "
                    "Lower risk of sudden equity loss."
                ),
                "opportunity_score": round(score, 1),
                "action": "Good for conservative investors and long-term wealth building.",
                "risk": "Low",
                "risk_color": "#10b981",
                "metrics": {"volatility_pct": volatility},
            })

        # Sort by score descending
        deals.sort(key=lambda d: d["opportunity_score"], reverse=True)
        return deals

    def _dom_trend(self, history: list) -> str:
        if len(history) < 4:
            return "unknown"
        recent = [h.get("median_dom", 0) for h in history[-4:] if h.get("median_dom", 0)]
        if len(recent) < 2:
            return "unknown"
        return "declining" if recent[-1] < recent[0] else "rising"

    def _inventory_tight(self, history: list) -> bool:
        if len(history) < 4:
            return False
        inv = [h.get("inventory", 0) for h in history[-6:] if h.get("inventory", 0)]
        if len(inv) < 2:
            return False
        return inv[-1] < inv[0] * 0.9  # 10%+ decline = tight

    # ----------------------------------------------------- investment score
    def calculate_investment_score(self, zhvi_data: dict, census_data: dict) -> dict:
        history = zhvi_data.get("history", [])
        values = [h["value"] for h in history if h.get("value", 0) > 0]

        if not values:
            return {"score": 50, "grade": "C", "components": {}, "recommendation": "Insufficient data."}

        current = values[-1]
        median_rent = census_data.get("median_rent") or 950
        median_income = census_data.get("median_income") or 65000
        annual_rent = median_rent * 12
        gross_yield = (annual_rent / current) * 100 if current else 0
        price_to_income = current / median_income if median_income else 5

        components = {}

        # 1. Price momentum (6-month YoY)
        if len(values) >= 7:
            c6 = ((current - values[-7]) / values[-7]) * 100
            if 1.5 <= c6 <= 4:
                ms = 88
            elif 0 < c6 < 1.5:
                ms = 70
            elif 4 < c6 <= 7:
                ms = 65  # hot — risk of correction
            elif c6 > 7:
                ms = 50
            elif -2 < c6 <= 0:
                ms = 45
            else:
                ms = 25
        else:
            ms = 55
        components["price_momentum"] = round(ms, 1)

        # 2. Affordability
        if price_to_income < 3:
            af = 95
        elif price_to_income < 3.5:
            af = 85
        elif price_to_income < 4:
            af = 75
        elif price_to_income < 5:
            af = 60
        elif price_to_income < 6:
            af = 45
        else:
            af = 28
        components["affordability"] = round(af, 1)

        # 3. Rental yield
        if gross_yield >= 8:
            ry = 95
        elif gross_yield >= 7:
            ry = 85
        elif gross_yield >= 6:
            ry = 72
        elif gross_yield >= 5:
            ry = 60
        elif gross_yield >= 4:
            ry = 45
        else:
            ry = 28
        components["rental_yield"] = round(ry, 1)

        # 4. Market stability (low CV = stable)
        if len(values) > 12:
            mean = sum(values) / len(values)
            std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
            cv = (std / mean) * 100 if mean else 20
            if cv < 5:
                st = 92
            elif cv < 10:
                st = 78
            elif cv < 15:
                st = 60
            elif cv < 20:
                st = 45
            else:
                st = 30
        else:
            st = 60
        components["market_stability"] = round(st, 1)

        # 5. Long-term appreciation (24-month)
        if len(values) >= 25:
            c24 = ((current - values[-25]) / values[-25]) * 100
            if 8 <= c24 <= 25:
                la = 85
            elif c24 > 25:
                la = 65  # potentially overheated
            elif 3 <= c24 < 8:
                la = 70
            elif 0 <= c24 < 3:
                la = 55
            else:
                la = 35
        else:
            la = 58
        components["long_term_appreciation"] = round(la, 1)

        weights = {
            "price_momentum": 0.25,
            "affordability": 0.20,
            "rental_yield": 0.25,
            "market_stability": 0.15,
            "long_term_appreciation": 0.15,
        }
        total = sum(components[k] * weights[k] for k in components)
        total = round(total, 1)

        if total >= 80:
            grade = "A"
        elif total >= 70:
            grade = "B"
        elif total >= 60:
            grade = "C"
        elif total >= 50:
            grade = "D"
        else:
            grade = "F"

        rec_map = {
            "A": "Excellent investment market. Strong fundamentals across all metrics. High confidence for buy-and-hold or rental strategies.",
            "B": "Good investment potential. Above-average metrics with manageable risk. Suitable for both rental and appreciation plays.",
            "C": "Average conditions. Selective opportunities exist — focus on properties with value-add potential or below-median pricing.",
            "D": "Below-average conditions. Higher risk. Thorough due diligence and conservative underwriting required.",
            "F": "Challenging market. Wait for better entry or target heavily discounted / distressed properties only.",
        }

        return {
            "score": total,
            "grade": grade,
            "components": components,
            "recommendation": rec_map.get(grade, ""),
        }
