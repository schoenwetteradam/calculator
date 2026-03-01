"""
Dodge County Property Price Analyzer
Flask backend serving market data from Zillow Research, Census Bureau, and Redfin.
"""
from flask import Flask, render_template, jsonify, request
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from data_fetcher import DataFetcher
from analyzer import PropertyAnalyzer
from deal_finder import DealFinder

app = Flask(__name__)

fetcher = DataFetcher()
analyzer = PropertyAnalyzer()
deal_finder = DealFinder()

DODGE_COUNTIES = [
    {"state": "WI", "fips_state": "55", "fips_county": "027", "label": "Dodge County, Wisconsin", "city": "Beaver Dam"},
    {"state": "MN", "fips_state": "27", "fips_county": "039", "label": "Dodge County, Minnesota", "city": "Mantorville"},
    {"state": "NE", "fips_state": "31", "fips_county": "053", "label": "Dodge County, Nebraska", "city": "Fremont"},
    {"state": "GA", "fips_state": "13", "fips_county": "091", "label": "Dodge County, Georgia", "city": "Eastman"},
]


@app.route("/")
def index():
    return render_template("property_analyzer.html", counties=DODGE_COUNTIES)


@app.route("/api/counties")
def get_counties():
    return jsonify(DODGE_COUNTIES)


@app.route("/api/market-data")
def get_market_data():
    state = request.args.get("state", "WI")
    county_cfg = next((c for c in DODGE_COUNTIES if c["state"] == state), DODGE_COUNTIES[0])

    try:
        zhvi_data = fetcher.get_zillow_zhvi(state, "Dodge County", county_cfg)
        census_data = fetcher.get_census_data(county_cfg)
        redfin_data = fetcher.get_redfin_data(state)

        trend = analyzer.calculate_trend(zhvi_data)
        market_stats = analyzer.get_market_stats(zhvi_data, census_data)
        trend_detail = analyzer.detailed_trend_analysis(zhvi_data)
        deals = deal_finder.find_deals(zhvi_data, redfin_data, market_stats)
        inv_score = deal_finder.calculate_investment_score(zhvi_data, census_data)

        return jsonify(
            {
                "success": True,
                "county": county_cfg,
                "trend": trend,
                "market_stats": market_stats,
                "trend_detail": trend_detail,
                "deals": deals,
                "investment_score": inv_score,
                "zhvi_history": zhvi_data.get("history", []),
                "data_source": zhvi_data.get("source", "API"),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/compare")
def compare_counties():
    """Return summary for all Dodge Counties for side-by-side comparison."""
    results = []
    for county_cfg in DODGE_COUNTIES:
        state = county_cfg["state"]
        try:
            zhvi_data = fetcher.get_zillow_zhvi(state, "Dodge County", county_cfg)
            census_data = fetcher.get_census_data(county_cfg)
            trend = analyzer.calculate_trend(zhvi_data)
            market_stats = analyzer.get_market_stats(zhvi_data, census_data)
            inv_score = deal_finder.calculate_investment_score(zhvi_data, census_data)
            results.append(
                {
                    "county": county_cfg,
                    "trend": trend,
                    "market_stats": market_stats,
                    "investment_score": inv_score,
                    "source": zhvi_data.get("source", "API"),
                }
            )
        except Exception as e:
            results.append({"county": county_cfg, "error": str(e)})
    return jsonify({"success": True, "counties": results})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
