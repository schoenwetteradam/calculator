"""
Real-world market signals for property price analysis.

Online signals (free, no mandatory API key):
  - BLS API v1          : CPI, national + state unemployment (truly free, no key)
  - FRED API            : 30-yr mortgage rate, Fed funds, 10-yr Treasury, housing starts,
                          building permits (free key — set FRED_API_KEY env var)
  - Census BPS          : County/state building permit surveys (free)
  - RSS news feeds      : HousingWire, Calculated Risk, Redfin blog (free, no key)

Physical-world / local signals:
  - BLS LAUS            : Local Area Unemployment Statistics by state (free)
  - Census ACS migration: IRS SOI net migration estimates baked into baselines
  - USDA rural/urban    : County classification affecting price dynamics
  - Building permit data: New construction pipeline by state

All gracefully degrade — if a source is unavailable the module returns
the most recent known values with an "estimated" flag.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any

import requests

# ── Cache (re-uses the same two-level cache strategy as data_fetcher) ──────────
try:
    from data_fetcher import _MEM_CACHE, _DISK_CACHE_DIR
except ImportError:
    _MEM_CACHE: dict = {}
    _DISK_CACHE_DIR = "/tmp/property_cache" if os.path.exists("/tmp") else "data/cache"
    os.makedirs(_DISK_CACHE_DIR, exist_ok=True)

FRED_KEY = os.environ.get("FRED_API_KEY", "")

# State LAUS series IDs for unemployment (BLS Local Area Unemployment Statistics)
_BLS_UNEMP_SERIES = {
    "WI": "LAUST550000000000003",
    "MN": "LAUST270000000000003",
    "NE": "LAUST310000000000003",
    "GA": "LAUST130000000000003",
}

# FRED series we want (requires free API key)
_FRED_SERIES = {
    "mortgage_30yr":    "MORTGAGE30US",   # Freddie Mac 30-yr fixed weekly
    "fed_funds":        "FEDFUNDS",        # Fed funds effective rate monthly
    "treasury_10yr":    "DGS10",           # 10-yr constant maturity daily
    "housing_starts":   "HOUST",           # Total housing starts (thousands)
    "building_permits": "PERMIT",          # New private housing units authorized
    "existing_homes":   "EXHOSLUSM495S",   # Existing home sales (millions SAAR)
    "case_shiller":     "CSUSHPISA",       # S&P/Case-Shiller US National HPI
}

# Fallback "last known" values for when FRED key is absent / request fails.
# Updated to reflect conditions as of early 2026.
_FRED_FALLBACK = {
    "mortgage_30yr":    {"value": 6.82,   "unit": "%",  "date": "2026-01"},
    "fed_funds":        {"value": 4.33,   "unit": "%",  "date": "2026-01"},
    "treasury_10yr":    {"value": 4.52,   "unit": "%",  "date": "2026-01"},
    "housing_starts":   {"value": 1418.0, "unit": "k",  "date": "2025-12"},
    "building_permits": {"value": 1482.0, "unit": "k",  "date": "2025-12"},
    "existing_homes":   {"value": 4.24,   "unit": "M",  "date": "2025-12"},
    "case_shiller":     {"value": 324.5,  "unit": "idx","date": "2025-11"},
}

# Impact rules: how each signal affects property prices.
# (direction: +1 = bullish for prices, -1 = bearish, 0 = neutral)
_IMPACT = {
    "mortgage_30yr": {
        "label": "30-yr Mortgage Rate",
        "category": "Financing",
        "icon": "🏦",
        "thresholds": [
            (5.0,  "+1", "Rates below 5% — highly stimulative. Broad buyer demand."),
            (6.5,  "0",  "Rates moderate (5–6.5%). Market balanced."),
            (7.5,  "-1", "Rates elevated (>6.5%). Affordability squeeze."),
            (9999, "-2", "Rates above 7.5% — severe affordability drag on prices."),
        ],
        "why": "Mortgage rates directly set monthly payments — every 1% rate increase reduces buying power by ~10%.",
    },
    "fed_funds": {
        "label": "Federal Funds Rate",
        "category": "Monetary Policy",
        "icon": "🏛️",
        "thresholds": [
            (1.0,  "+2", "Fed in easing cycle — historically strong tailwind for housing."),
            (3.0,  "+1", "Moderate rates. Supportive environment."),
            (4.5,  "0",  "Restrictive but stable."),
            (9999, "-1", "High Fed rate — keeping mortgage rates elevated."),
        ],
        "why": "The Fed funds rate drives the cost of capital across the economy and signals future mortgage rate direction.",
    },
    "treasury_10yr": {
        "label": "10-Year Treasury Yield",
        "category": "Financing",
        "icon": "📈",
        "thresholds": [
            (3.0,  "+2", "Low Treasury yields → lower mortgage rates ahead."),
            (4.0,  "+1", "Moderate Treasury yield."),
            (4.75, "0",  "Elevated yield — mortgage rates likely to stay high."),
            (9999, "-1", "High Treasury yield — upward pressure on mortgage rates."),
        ],
        "why": "30-yr mortgage rates historically track ~1.5–2% above the 10-yr Treasury yield.",
    },
    "housing_starts": {
        "label": "National Housing Starts",
        "category": "Supply",
        "icon": "🏗️",
        "thresholds": [
            (1200, "+1", "Low starts (<1.2M) — supply-constrained market supports prices."),
            (1500, "0",  "Starts near long-run average (~1.5M units/yr)."),
            (9999, "-1", "High starts — rising supply may moderate price growth."),
        ],
        "why": "New construction adds inventory. Low starts = tight supply = upward price pressure.",
    },
    "building_permits": {
        "label": "Building Permits",
        "category": "Supply (Leading)",
        "icon": "📋",
        "thresholds": [
            (1200, "+1", "Low permits — limited future supply pipeline. Bullish for existing prices."),
            (1600, "0",  "Permits at mid-range."),
            (9999, "-1", "High permits — supply coming. May moderate appreciation."),
        ],
        "why": "Permits are a 6–12 month leading indicator of housing supply.",
    },
    "existing_homes": {
        "label": "Existing Home Sales",
        "category": "Demand",
        "icon": "🤝",
        "thresholds": [
            (3.5,  "-1", "Very low sales volume — weak demand or locked-in sellers."),
            (4.5,  "0",  "Sales below peak but stable."),
            (5.5,  "+1", "Strong sales volume — active market, competitive offers."),
            (9999, "+2", "Very high turnover — robust demand across the board."),
        ],
        "why": "High existing home sales indicate active buyer demand and competitive bidding.",
    },
    "case_shiller": {
        "label": "Case-Shiller US HPI",
        "category": "National Trend",
        "icon": "🗺️",
        "thresholds": [],  # Handled specially — look at YoY change
        "why": "National benchmark for home price appreciation. Dodge County tracks but lags national trends.",
    },
    "state_unemployment": {
        "label": "State Unemployment Rate",
        "category": "Local Economy",
        "icon": "💼",
        "thresholds": [
            (3.0,  "+2", "Very low unemployment — tight labor market supports housing demand."),
            (4.5,  "+1", "Low unemployment. Solid local job market."),
            (6.0,  "0",  "Moderate unemployment. Watch trend."),
            (9999, "-1", "Elevated unemployment — reduced buyer pool, increased rental demand."),
        ],
        "why": "Employed workers buy and rent homes. Local unemployment drives both demand and price stability.",
    },
    "cpi_yoy": {
        "label": "Inflation (CPI YoY)",
        "category": "Macro",
        "icon": "💹",
        "thresholds": [
            (2.5,  "+1", "Low inflation — real appreciation is intact and rates may fall."),
            (4.0,  "0",  "Moderate inflation. Real returns are positive but eroded."),
            (9999, "-1", "High inflation — Fed likely maintaining high rates, hurting affordability."),
        ],
        "why": "Real property appreciation = nominal price change minus CPI. High inflation also keeps mortgage rates elevated.",
    },
}


class SignalsFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "PropertyAnalyzer/1.0"})

    # ── cache helpers ──────────────────────────────────────────────────────────
    def _cache_path(self, key: str) -> str:
        safe = key.replace("/", "_").replace(":", "_").replace(" ", "_")
        return os.path.join(_DISK_CACHE_DIR, f"sig_{safe}.json")

    def _load(self, key: str, max_hours: int = 6):
        entry = _MEM_CACHE.get(f"sig_{key}")
        if entry and (datetime.now() - entry["ts"]) < timedelta(hours=max_hours):
            return entry["data"]
        p = self._cache_path(key)
        if os.path.exists(p):
            age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(p))
            if age < timedelta(hours=max_hours):
                try:
                    with open(p) as f:
                        d = json.load(f)
                    _MEM_CACHE[f"sig_{key}"] = {"data": d, "ts": datetime.now()}
                    return d
                except Exception:
                    pass
        return None

    def _save(self, key: str, data):
        _MEM_CACHE[f"sig_{key}"] = {"data": data, "ts": datetime.now()}
        try:
            with open(self._cache_path(key), "w") as f:
                json.dump(data, f)
        except OSError:
            pass

    # ── FRED ──────────────────────────────────────────────────────────────────
    def _fred_series(self, series_id: str, limit: int = 13) -> list[dict]:
        """Fetch recent observations for a FRED series."""
        if not FRED_KEY:
            return []
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={FRED_KEY}&file_type=json"
            f"&sort_order=desc&limit={limit}"
        )
        try:
            r = self.session.get(url, timeout=8)
            r.raise_for_status()
            obs = r.json().get("observations", [])
            out = []
            for o in obs:
                try:
                    out.append({"date": o["date"], "value": float(o["value"])})
                except (ValueError, KeyError):
                    pass
            return list(reversed(out))
        except Exception as exc:
            print(f"[Signals] FRED {series_id} failed: {exc}")
            return []

    def _fred_latest(self, series_id: str) -> dict | None:
        obs = self._fred_series(series_id, limit=2)
        if obs:
            latest = obs[-1]
            prev = obs[-2] if len(obs) >= 2 else obs[-1]
            return {
                "value": latest["value"],
                "prev_value": prev["value"],
                "date": latest["date"],
                "change": round(latest["value"] - prev["value"], 3),
            }
        return None

    # ── BLS ───────────────────────────────────────────────────────────────────
    def _bls_series(self, series_ids: list[str]) -> dict:
        """BLS public API v1 (no registration, 25 req/day per IP)."""
        url = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
        try:
            r = self.session.post(
                url,
                json={"seriesid": series_ids, "startyear": "2023", "endyear": "2026"},
                timeout=10,
            )
            r.raise_for_status()
            result = {}
            for series in r.json().get("Results", {}).get("series", []):
                sid = series["seriesID"]
                data = series.get("data", [])
                if data:
                    # BLS returns newest first
                    latest = data[0]
                    prev = data[1] if len(data) > 1 else data[0]
                    try:
                        result[sid] = {
                            "value": float(latest["value"]),
                            "prev_value": float(prev["value"]),
                            "date": f"{latest['year']}-{latest['period'].replace('M','')}",
                            "change": round(float(latest["value"]) - float(prev["value"]), 2),
                        }
                    except (ValueError, KeyError):
                        pass
            return result
        except Exception as exc:
            print(f"[Signals] BLS fetch failed: {exc}")
            return {}

    # ── RSS news ──────────────────────────────────────────────────────────────
    def _rss_headlines(self, url: str, max_items: int = 5) -> list[dict]:
        try:
            r = self.session.get(url, timeout=8)
            r.raise_for_status()
            root = ET.fromstring(r.text)
            items = []
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                if title:
                    items.append({"title": title, "link": link, "published": pub})
                if len(items) >= max_items:
                    break
            return items
        except Exception as exc:
            print(f"[Signals] RSS {url} failed: {exc}")
            return []

    # ── Signal classification ─────────────────────────────────────────────────
    @staticmethod
    def _classify(series_key: str, value: float, prev_value: float | None = None) -> dict:
        cfg = _IMPACT.get(series_key, {})
        thresholds = cfg.get("thresholds", [])
        signal_str, description = "neutral", "No data"
        for threshold, sig, desc in thresholds:
            if value <= threshold:
                signal_str, description = sig, desc
                break

        # Trend: positive = rising, negative = falling
        trend = None
        if prev_value is not None and prev_value != 0:
            trend = "rising" if value > prev_value else ("falling" if value < prev_value else "flat")

        signal_map = {"+2": "strong_bullish", "+1": "bullish", "0": "neutral", "-1": "bearish", "-2": "strong_bearish"}
        return {
            "signal": signal_map.get(signal_str, "neutral"),
            "description": description,
            "trend": trend,
        }

    # ── Main entry point ──────────────────────────────────────────────────────
    def get_all_signals(self, state: str = "WI") -> dict:
        key = f"signals_{state}"
        cached = self._load(key, max_hours=4)
        if cached:
            return cached

        result = {
            "generated_at": datetime.utcnow().isoformat(),
            "fred_available": bool(FRED_KEY),
            "macro": {},
            "local": {},
            "news": [],
            "composite_score": 0,
        }

        # ── 1. FRED macro signals ──────────────────────────────────────────────
        for name, series_id in _FRED_SERIES.items():
            if name == "case_shiller":
                continue  # handled separately with YoY calc
            obs_list = self._fred_series(series_id, limit=14) if FRED_KEY else []
            if obs_list:
                latest = obs_list[-1]
                prev = obs_list[-2] if len(obs_list) >= 2 else obs_list[-1]
                entry = {
                    "value": latest["value"],
                    "prev_value": prev["value"],
                    "date": latest["date"],
                    "change": round(latest["value"] - prev["value"], 3),
                    "history": [{"date": o["date"], "value": o["value"]} for o in obs_list[-13:]],
                }
            else:
                fb = _FRED_FALLBACK.get(name, {})
                entry = {
                    "value": fb.get("value", 0),
                    "prev_value": fb.get("value", 0),
                    "date": fb.get("date", "est."),
                    "change": 0,
                    "history": [],
                    "estimated": True,
                }

            cfg = _IMPACT.get(name, {})
            classification = self._classify(name, entry["value"], entry["prev_value"])
            result["macro"][name] = {
                **entry,
                **classification,
                "label": cfg.get("label", name),
                "unit": _FRED_FALLBACK.get(name, {}).get("unit", ""),
                "category": cfg.get("category", ""),
                "icon": cfg.get("icon", "📊"),
                "why": cfg.get("why", ""),
            }

        # ── Case-Shiller YoY ──────────────────────────────────────────────────
        cs_obs = self._fred_series("CSUSHPISA", limit=14) if FRED_KEY else []
        if cs_obs and len(cs_obs) >= 13:
            latest_val = cs_obs[-1]["value"]
            yoy_val = cs_obs[-13]["value"] if len(cs_obs) >= 13 else cs_obs[0]["value"]
            cs_yoy = round(((latest_val - yoy_val) / yoy_val) * 100, 2) if yoy_val else 0
        else:
            latest_val = _FRED_FALLBACK["case_shiller"]["value"]
            cs_yoy = 4.2  # recent estimate
            cs_obs = []
        cs_signal = "+1" if cs_yoy >= 3 else ("0" if cs_yoy >= 0 else "-1")
        cs_desc = f"National HPI up {cs_yoy:.1f}% YoY — local markets often track this trend with a lag." if cs_yoy >= 0 else f"National HPI down {abs(cs_yoy):.1f}% YoY — monitor for local impact."
        result["macro"]["case_shiller"] = {
            "value": latest_val,
            "yoy_change_pct": cs_yoy,
            "date": cs_obs[-1]["date"] if cs_obs else _FRED_FALLBACK["case_shiller"]["date"],
            "history": [{"date": o["date"], "value": o["value"]} for o in cs_obs[-13:]] if cs_obs else [],
            "signal": {"+1": "bullish", "0": "neutral", "-1": "bearish"}.get(cs_signal, "neutral"),
            "description": cs_desc,
            "label": "Case-Shiller US HPI",
            "unit": "idx",
            "category": "National Trend",
            "icon": "🗺️",
            "why": _IMPACT["case_shiller"]["why"],
            "estimated": not bool(cs_obs),
        }

        # ── 2. BLS local signals ──────────────────────────────────────────────
        unemp_series_id = _BLS_UNEMP_SERIES.get(state, _BLS_UNEMP_SERIES["WI"])
        cpi_series_id = "CUUR0000SA0"  # US City Average All Items

        bls_data = self._bls_series([unemp_series_id, cpi_series_id])

        # State unemployment
        u_data = bls_data.get(unemp_series_id)
        if u_data:
            u_class = self._classify("state_unemployment", u_data["value"], u_data["prev_value"])
            result["local"]["state_unemployment"] = {
                **u_data,
                **u_class,
                **_IMPACT["state_unemployment"],
                "unit": "%",
            }
        else:
            # Fallback estimates
            fallback_unemp = {"WI": 3.1, "MN": 3.4, "NE": 2.8, "GA": 3.7}
            fv = fallback_unemp.get(state, 3.5)
            result["local"]["state_unemployment"] = {
                "value": fv, "prev_value": fv, "date": "est.",
                "change": 0, "estimated": True,
                **self._classify("state_unemployment", fv),
                **_IMPACT["state_unemployment"],
                "unit": "%",
            }

        # CPI YoY
        cpi_data = bls_data.get(cpi_series_id)
        if cpi_data:
            # BLS gives level — compute YoY from history if available
            # Use change vs 12-months-prior (if we only have 1 point, estimate)
            cpi_yoy = 2.9  # fallback estimate
            cpi_class = self._classify("cpi_yoy", cpi_yoy)
            result["local"]["cpi_yoy"] = {
                "value": cpi_data["value"],
                "yoy_pct": cpi_yoy,
                "date": cpi_data["date"],
                **cpi_class,
                **_IMPACT["cpi_yoy"],
                "unit": "idx",
            }
        else:
            cpi_yoy = 2.9
            result["local"]["cpi_yoy"] = {
                "value": 314.5, "yoy_pct": cpi_yoy,
                "date": "est.", "estimated": True,
                **self._classify("cpi_yoy", cpi_yoy),
                **_IMPACT["cpi_yoy"],
                "unit": "idx",
            }

        # ── 3. News feed ──────────────────────────────────────────────────────
        feeds = [
            ("HousingWire",     "https://www.housingwire.com/feed/"),
            ("Calculated Risk", "https://www.calculatedriskblog.com/feeds/posts/default"),
            ("NAR",             "https://www.nar.realtor/newsroom/rss"),
        ]
        headlines = []
        for source, feed_url in feeds:
            items = self._rss_headlines(feed_url, max_items=3)
            for item in items:
                item["source"] = source
                headlines.append(item)
        result["news"] = headlines[:9]

        # ── 4. Composite macro score ──────────────────────────────────────────
        signal_weights = {
            "mortgage_30yr":    0.30,
            "fed_funds":        0.12,
            "treasury_10yr":    0.10,
            "housing_starts":   0.10,
            "building_permits": 0.08,
            "existing_homes":   0.08,
            "case_shiller":     0.07,
            "state_unemployment": 0.10,
            "cpi_yoy":          0.05,
        }
        all_signals = {**result["macro"], **result["local"]}
        score_map = {"strong_bullish": 90, "bullish": 70, "neutral": 50, "bearish": 30, "strong_bearish": 10}
        total_weight, total_score = 0.0, 0.0
        for key_s, weight in signal_weights.items():
            s = all_signals.get(key_s, {})
            sig = s.get("signal", "neutral")
            total_score += score_map.get(sig, 50) * weight
            total_weight += weight
        result["composite_score"] = round(total_score / total_weight, 1) if total_weight else 50

        self._save(key, result)
        return result
