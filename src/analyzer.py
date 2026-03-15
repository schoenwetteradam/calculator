"""
Property market trend analyzer.
Calculates price trends, moving averages, momentum indicators,
and key market statistics from ZHVI + Census data.
"""
from __future__ import annotations
import math
from typing import Any


class PropertyAnalyzer:

    @staticmethod
    def _bounded_score(value: float, low: float, high: float) -> float:
        if high <= low:
            return 50.0
        score = (value - low) / (high - low) * 100
        return max(0.0, min(100.0, round(score, 1)))

    @staticmethod
    def _letter_grade(score: float) -> str:
        if score >= 93:
            return "A"
        if score >= 90:
            return "A-"
        if score >= 87:
            return "B+"
        if score >= 83:
            return "B"
        if score >= 80:
            return "B-"
        if score >= 77:
            return "C+"
        if score >= 73:
            return "C"
        if score >= 70:
            return "C-"
        if score >= 67:
            return "D+"
        if score >= 63:
            return "D"
        if score >= 60:
            return "D-"
        return "F"


    # ---------------------------------------------------------------- trend
    def calculate_trend(self, zhvi_data: dict) -> dict:
        """High-level trend summary for the county."""
        history = zhvi_data.get("history", [])
        values = [h["value"] for h in history if h.get("value", 0) > 0]

        if len(values) < 3:
            return {
                "direction": "unknown",
                "strength": "unknown",
                "current_value": 0,
                "change_3mo_pct": 0,
                "change_6mo_pct": 0,
                "change_12mo_pct": 0,
                "change_24mo_pct": 0,
                "projected_12mo": 0,
                "monthly_growth_rate": 0,
            }

        current = values[-1]

        def pct(old, new):
            return round(((new - old) / old) * 100, 2) if old else 0

        c3 = pct(values[-4], current) if len(values) >= 4 else pct(values[0], current)
        c6 = pct(values[-7], current) if len(values) >= 7 else pct(values[0], current)
        c12 = pct(values[-13], current) if len(values) >= 13 else pct(values[0], current)
        c24 = pct(values[-25], current) if len(values) >= 25 else pct(values[0], current)

        # Linear regression slope
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den else 0
        monthly_growth = (slope / y_mean) * 100 if y_mean else 0

        if c6 >= 4:
            direction, strength = "up", "strong"
        elif c6 >= 1.5:
            direction, strength = "up", "moderate"
        elif c6 <= -4:
            direction, strength = "down", "strong"
        elif c6 <= -1.5:
            direction, strength = "down", "moderate"
        else:
            direction, strength = "stable", "stable"

        return {
            "direction": direction,
            "strength": strength,
            "current_value": round(current, 2),
            "change_3mo_pct": c3,
            "change_6mo_pct": c6,
            "change_12mo_pct": c12,
            "change_24mo_pct": c24,
            "monthly_growth_rate": round(monthly_growth, 3),
            "projected_12mo": round(current * (1 + monthly_growth / 100) ** 12, 2),
        }

    # ---------------------------------------------------------- market stats
    def get_market_stats(self, zhvi_data: dict, census_data: dict) -> dict:
        history = zhvi_data.get("history", [])
        values = [h["value"] for h in history if h.get("value", 0) > 0]
        if not values:
            return {}

        current = values[-1]
        median_rent = census_data.get("median_rent") or 950
        median_income = census_data.get("median_income") or 65000
        annual_rent = median_rent * 12

        price_to_rent = round(current / annual_rent, 1) if annual_rent else 0
        price_to_income = round(current / median_income, 2) if median_income else 0
        gross_yield = round((annual_rent / current) * 100, 2) if current else 0

        # Estimated net yield (assume 40% expense ratio on gross rent)
        net_yield = round(gross_yield * 0.60, 2)

        hist_high = max(values)
        hist_low = min(values)
        pct_from_high = round(((current - hist_high) / hist_high) * 100, 2) if hist_high else 0
        pct_from_low = round(((current - hist_low) / hist_low) * 100, 2) if hist_low else 0

        # Volatility
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance)
        volatility = round((std_dev / mean) * 100, 2) if mean else 0

        # Affordability: monthly PITI estimate at 7% 30yr
        monthly_rate = 0.07 / 12
        n_payments = 360
        down = current * 0.20
        loan = current - down
        if monthly_rate > 0:
            piti = loan * (monthly_rate * (1 + monthly_rate) ** n_payments) / (
                (1 + monthly_rate) ** n_payments - 1
            )
        else:
            piti = loan / n_payments
        piti += current * 0.012 / 12  # property tax estimate 1.2% annually
        piti = round(piti, 2)
        affordability_index = round((median_income / 12) / piti * 100, 1) if piti else 0

        # Family/owner-occupant metrics (target: 4+ bed, 2+ bath single-family)
        sf_detached = census_data.get("single_family_detached", 0)
        sf_attached = census_data.get("single_family_attached", 0)
        four_bed = census_data.get("four_bedroom_units", 0)
        five_bed = census_data.get("five_plus_bedroom_units", 0)
        four_plus_bed_units = four_bed + five_bed

        single_family_units = sf_detached + sf_attached
        single_family_share = round((single_family_units / census_data.get("total_units", 1)) * 100, 1) if census_data.get("total_units", 0) else 0
        four_plus_bed_share = round((four_plus_bed_units / census_data.get("total_units", 1)) * 100, 1) if census_data.get("total_units", 0) else 0

        sfh_family_price_estimate = round(current * 1.35, 2)
        sfh_down = sfh_family_price_estimate * 0.20
        sfh_loan = sfh_family_price_estimate - sfh_down
        if monthly_rate > 0:
            sfh_piti = sfh_loan * (monthly_rate * (1 + monthly_rate) ** n_payments) / (((1 + monthly_rate) ** n_payments) - 1)
        else:
            sfh_piti = sfh_loan / n_payments
        sfh_piti += sfh_family_price_estimate * 0.012 / 12
        sfh_piti = round(sfh_piti, 2)

        income_needed = round(sfh_piti * 12 / 0.30, 2)
        family_payment_burden_pct = round((sfh_piti / (median_income / 12)) * 100, 1) if median_income else 0
        family_affordability_score = self._bounded_score(45 - family_payment_burden_pct, 0, 30)
        sfh_supply_score = self._bounded_score(single_family_share, 30, 85)
        bedroom_depth_score = self._bounded_score(four_plus_bed_share, 8, 40)
        volatility_score = self._bounded_score(12 - volatility, 0, 10)
        family_investor_fit_score = round(
            (family_affordability_score * 0.40)
            + (sfh_supply_score * 0.25)
            + (bedroom_depth_score * 0.25)
            + (volatility_score * 0.10),
            1,
        )
        family_investor_fit_grade = self._letter_grade(family_investor_fit_score)

        # Target-home finder metrics (4+ bed, 2+ bath SFH)
        # ACS provides bedroom mix but not a direct 2+ bathroom field at this geography,
        # so we model bath adequacy as a conservative share of larger single-family stock.
        two_plus_bath_proxy_share = round(min(95.0, (single_family_share * 0.62) + (four_plus_bed_share * 0.45)), 1)
        target_4bd2ba_share = round(min(four_plus_bed_share, two_plus_bath_proxy_share), 1)
        target_4bd2ba_units = int(round((census_data.get("total_units", 0) * target_4bd2ba_share) / 100))
        target_home_price_estimate = round(current * 1.38, 2)
        target_down = target_home_price_estimate * 0.20
        target_loan = target_home_price_estimate - target_down
        if monthly_rate > 0:
            target_piti = target_loan * (monthly_rate * (1 + monthly_rate) ** n_payments) / (((1 + monthly_rate) ** n_payments) - 1)
        else:
            target_piti = target_loan / n_payments
        target_piti += target_home_price_estimate * 0.012 / 12
        target_piti = round(target_piti, 2)
        target_income_needed = round(target_piti * 12 / 0.30, 2)
        target_affordability_ratio = round((median_income / target_income_needed) if target_income_needed else 0, 2)
        target_affordability_index = round(target_affordability_ratio * 100, 1)
        target_payment_burden = round((target_piti / (median_income / 12)) * 100, 1) if median_income else 0

        analysis_rationales = [
            f"4+BD/2+BA estimated inventory uses a bedroom-depth floor ({four_plus_bed_share:.1f}%) and a 2+ bath proxy ({two_plus_bath_proxy_share:.1f}%) derived from single-family mix.",
            "Target monthly payment uses a 30-year fixed assumption at 7.0% with 20% down plus 1.2% annual property tax.",
            f"Household feasibility is measured by a 30%-of-gross-income guideline; current median-income burden is {target_payment_burden:.1f}%.",
            "Family investor-fit combines affordability, single-family supply, 4+ bedroom depth, and market stability to balance cash flow and owner-occupant demand.",
        ]

        return {
            "current_zhvi": round(current, 2),
            "median_home_value_census": census_data.get("median_home_value", 0),
            "median_rent": median_rent,
            "median_income": median_income,
            "price_to_rent_ratio": price_to_rent,
            "price_to_income_ratio": price_to_income,
            "gross_rental_yield_pct": gross_yield,
            "net_rental_yield_pct": net_yield,
            "estimated_monthly_piti": piti,
            "affordability_index": affordability_index,
            "historical_high": round(hist_high, 2),
            "historical_low": round(hist_low, 2),
            "pct_from_high": pct_from_high,
            "pct_from_low": pct_from_low,
            "volatility_pct": volatility,
            "single_family_units": single_family_units,
            "single_family_share_pct": single_family_share,
            "four_plus_bedroom_units": four_plus_bed_units,
            "four_plus_bedroom_share_pct": four_plus_bed_share,
            "sfh_family_price_estimate": sfh_family_price_estimate,
            "sfh_family_monthly_piti": sfh_piti,
            "income_needed_for_sfh_family_home": income_needed,
            "family_payment_burden_pct": family_payment_burden_pct,
            "family_affordability_score": family_affordability_score,
            "sfh_supply_score": sfh_supply_score,
            "bedroom_depth_score": bedroom_depth_score,
            "market_volatility_score": volatility_score,
            "family_investor_fit_score": family_investor_fit_score,
            "family_investor_fit_grade": family_investor_fit_grade,
            "two_plus_bath_proxy_share_pct": two_plus_bath_proxy_share,
            "target_4bd2ba_share_pct": target_4bd2ba_share,
            "target_4bd2ba_units_estimate": target_4bd2ba_units,
            "target_4bd2ba_price_estimate": target_home_price_estimate,
            "target_4bd2ba_monthly_piti": target_piti,
            "target_4bd2ba_income_needed": target_income_needed,
            "target_4bd2ba_affordability_ratio": target_affordability_ratio,
            "target_4bd2ba_affordability_index": target_affordability_index,
            "target_4bd2ba_payment_burden_pct": target_payment_burden,
            "analysis_rationales": analysis_rationales,
            "population": census_data.get("population", 0),
            "total_units": census_data.get("total_units", 0),
            "owner_occupied": census_data.get("owner_occupied", 0),
            "renter_occupied": census_data.get("renter_occupied", 0),
        }

    # ------------------------------------------------------ detailed trends
    def detailed_trend_analysis(self, zhvi_data: dict) -> dict:
        history = zhvi_data.get("history", [])
        values = [h["value"] for h in history if h.get("value", 0) > 0]
        dates = [h["date"] for h in history if h.get("value", 0) > 0]

        if len(values) < 4:
            return {"values": values, "dates": dates, "ma3": [], "ma6": [], "ma12": []}

        def moving_avg(data: list, window: int) -> list:
            result = []
            for i in range(len(data)):
                if i < window - 1:
                    result.append(None)
                else:
                    avg = sum(data[i - window + 1: i + 1]) / window
                    result.append(round(avg, 2))
            return result

        ma3 = moving_avg(values, 3)
        ma6 = moving_avg(values, 6)
        ma12 = moving_avg(values, 12)

        # Momentum: price-rate-of-change oscillator over 3 months
        gains, losses = [], []
        for i in range(1, len(values)):
            diff = values[i] - values[i - 1]
            gains.append(max(diff, 0))
            losses.append(abs(min(diff, 0)))

        period = min(14, len(gains))
        avg_gain = sum(gains[-period:]) / period if period else 0
        avg_loss = sum(losses[-period:]) / period if period else 1e-9
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        momentum = round(100 - (100 / (1 + rs)), 1)

        # Market phase
        current = values[-1]
        ma3_v = next((v for v in reversed(ma3) if v), current)
        ma6_v = next((v for v in reversed(ma6) if v), current)
        ma12_v = next((v for v in reversed(ma12) if v), current)

        if current > ma3_v > ma6_v > ma12_v:
            phase, phase_color = "Strong Uptrend", "#10b981"
        elif current < ma3_v < ma6_v < ma12_v:
            phase, phase_color = "Strong Downtrend", "#ef4444"
        elif current > ma6_v and current > ma12_v:
            phase, phase_color = "Moderate Uptrend", "#34d399"
        elif current < ma6_v and current < ma12_v:
            phase, phase_color = "Moderate Downtrend", "#f87171"
        else:
            phase, phase_color = "Sideways / Consolidating", "#f59e0b"

        return {
            "values": [round(v, 2) for v in values],
            "dates": dates,
            "ma3": ma3,
            "ma6": ma6,
            "ma12": ma12,
            "momentum": momentum,
            "phase": phase,
            "phase_color": phase_color,
        }
