"""
Dodge County Property Price Analyzer
Flask backend serving market data from Zillow Research, Census Bureau, and Redfin.
"""
from flask import Flask, render_template, jsonify, request, send_from_directory
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from data_fetcher import DataFetcher
from analyzer import PropertyAnalyzer
from deal_finder import DealFinder
from signals import SignalsFetcher

app = Flask(__name__)

fetcher = DataFetcher()
analyzer = PropertyAnalyzer()
deal_finder = DealFinder()
signals_fetcher = SignalsFetcher()

DODGE_COUNTIES = [
    {"state": "WI", "fips_state": "55", "fips_county": "027", "label": "Dodge County, Wisconsin", "city": "Beaver Dam"},
    {"state": "MN", "fips_state": "27", "fips_county": "039", "label": "Dodge County, Minnesota", "city": "Mantorville"},
    {"state": "NE", "fips_state": "31", "fips_county": "053", "label": "Dodge County, Nebraska", "city": "Fremont"},
    {"state": "GA", "fips_state": "13", "fips_county": "091", "label": "Dodge County, Georgia", "city": "Eastman"},
]

DODGE_WI_MUNICIPALITIES = [
    {"id": "all", "label": "All of Dodge County", "name": "Dodge County", "kind": "county", "type": "county"},
    {"id": "beaver-dam-city", "label": "Beaver Dam", "name": "Beaver Dam", "kind": "city", "type": "city", "fips_place": "04825"},
    {"id": "columbus-city", "label": "Columbus", "name": "Columbus", "kind": "city", "type": "city", "fips_place": "16550"},
    {"id": "fox-lake-city", "label": "Fox Lake", "name": "Fox Lake", "kind": "city", "type": "city", "fips_place": "27400"},
    {"id": "horicon-city", "label": "Horicon", "name": "Horicon", "kind": "city", "type": "city", "fips_place": "36200"},
    {"id": "juneau-city", "label": "Juneau", "name": "Juneau", "kind": "city", "type": "city", "fips_place": "40350"},
    {"id": "mayville-city", "label": "Mayville", "name": "Mayville", "kind": "city", "type": "city", "fips_place": "49575"},
    {"id": "waupun-city", "label": "Waupun", "name": "Waupun", "kind": "city", "type": "city", "fips_place": "84350"},
    {"id": "burnett-town", "label": "Burnett", "name": "Burnett", "kind": "town", "type": "county_subdivision", "fips_subdivision": "11500"},
    {"id": "calamus-town", "label": "Calamus", "name": "Calamus", "kind": "town", "type": "county_subdivision", "fips_subdivision": "12775"},
    {"id": "clyman-town", "label": "Clyman", "name": "Clyman", "kind": "town", "type": "county_subdivision", "fips_subdivision": "15925"},
    {"id": "emmet-town", "label": "Emmet", "name": "Emmet", "kind": "town", "type": "county_subdivision", "fips_subdivision": "24350"},
    {"id": "forest-town", "label": "Forest", "name": "Forest", "kind": "town", "type": "county_subdivision", "fips_subdivision": "26600"},
    {"id": "lebanon-town", "label": "Lebanon", "name": "Lebanon", "kind": "town", "type": "county_subdivision", "fips_subdivision": "43375"},
    {"id": "lowell-town", "label": "Lowell", "name": "Lowell", "kind": "town", "type": "county_subdivision", "fips_subdivision": "46250"},
    {"id": "rubicon-town", "label": "Rubicon", "name": "Rubicon", "kind": "town", "type": "county_subdivision", "fips_subdivision": "69250"},
    {"id": "theresa-town", "label": "Theresa", "name": "Theresa", "kind": "town", "type": "county_subdivision", "fips_subdivision": "77175"},
    {"id": "ashippun-village", "label": "Ashippun", "name": "Ashippun", "kind": "village", "type": "place", "fips_place": "03325"},
    {"id": "clyman-village", "label": "Clyman", "name": "Clyman", "kind": "village", "type": "place", "fips_place": "15950"},
    {"id": "hustisford-village", "label": "Hustisford", "name": "Hustisford", "kind": "village", "type": "place", "fips_place": "37375"},
    {"id": "iron-ridge-village", "label": "Iron Ridge", "name": "Iron Ridge", "kind": "village", "type": "place", "fips_place": "38300"},
    {"id": "kekoskee-village", "label": "Kekoskee", "name": "Kekoskee", "kind": "village", "type": "place", "fips_place": "40925"},
    {"id": "lomira-village", "label": "Lomira", "name": "Lomira", "kind": "village", "type": "place", "fips_place": "45650"},
    {"id": "neosho-village", "label": "Neosho", "name": "Neosho", "kind": "village", "type": "place", "fips_place": "56450"},
    {"id": "reeseville-village", "label": "Reeseville", "name": "Reeseville", "kind": "village", "type": "place", "fips_place": "67375"},
    {"id": "theresa-village", "label": "Theresa", "name": "Theresa", "kind": "village", "type": "place", "fips_place": "77100"},
]


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/")
def index():
    return render_template("property_analyzer.html", counties=DODGE_COUNTIES)


@app.route("/api/counties")
def get_counties():
    return jsonify(DODGE_COUNTIES)


@app.route("/api/wi-dodge-municipalities")
def get_wi_dodge_municipalities():
    return jsonify(DODGE_WI_MUNICIPALITIES)


@app.route("/api/market-data")
def get_market_data():
    state = request.args.get("state", "WI")
    municipality_id = request.args.get("municipality", "all")
    county_cfg = next((c for c in DODGE_COUNTIES if c["state"] == state), DODGE_COUNTIES[0])
    municipality_cfg = next((m for m in DODGE_WI_MUNICIPALITIES if m["id"] == municipality_id), DODGE_WI_MUNICIPALITIES[0])
    region_name = "Dodge County"
    region_type = "county"

    if state == "WI" and municipality_cfg["id"] != "all":
        region_name = municipality_cfg["name"]
        region_type = municipality_cfg.get("kind", "city")

    try:
        zhvi_data = fetcher.get_zillow_zhvi(state, region_name, county_cfg, region_type=region_type)
        if state == "WI" and municipality_cfg["id"] != "all":
            census_data = fetcher.get_census_municipality_data(county_cfg, municipality_cfg)
        else:
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
                "municipality": municipality_cfg if state == "WI" else None,
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


@app.route("/api/wi-municipality-rankings")
def get_wi_municipality_rankings():
    """Rank Dodge County, WI municipalities for investment + family home fit."""
    county_cfg = next((c for c in DODGE_COUNTIES if c["state"] == "WI"), DODGE_COUNTIES[0])
    rankings = []

    for municipality_cfg in DODGE_WI_MUNICIPALITIES:
        if municipality_cfg["id"] == "all":
            continue
        try:
            region_name = municipality_cfg["name"]
            region_type = municipality_cfg.get("kind", "city")
            zhvi_data = fetcher.get_zillow_zhvi("WI", region_name, county_cfg, region_type=region_type)
            census_data = fetcher.get_census_municipality_data(county_cfg, municipality_cfg)

            trend = analyzer.calculate_trend(zhvi_data)
            market_stats = analyzer.get_market_stats(zhvi_data, census_data)
            inv_score = deal_finder.calculate_investment_score(zhvi_data, census_data)

            overall = round((inv_score.get("score", 50) * 0.65) + (market_stats.get("family_investor_fit_score", 50) * 0.35), 1)
            rankings.append({
                "municipality": municipality_cfg,
                "trend": trend,
                "market_stats": market_stats,
                "investment_score": inv_score,
                "overall_rank_score": overall,
            })
        except Exception as exc:
            rankings.append({"municipality": municipality_cfg, "error": str(exc)})

    ranked = sorted([r for r in rankings if "error" not in r], key=lambda r: r["overall_rank_score"], reverse=True)
    errored = [r for r in rankings if "error" in r]
    return jsonify({"success": True, "rankings": ranked + errored})


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


@app.route("/api/signals")
def get_signals():
    """
    Real-world market signals: macro (FRED/BLS), local economy, and news RSS.
    Set FRED_API_KEY env var for live mortgage/Fed rate data.
    BLS CPI and unemployment work without any key.
    """
    state = request.args.get("state", "WI")
    try:
        data = signals_fetcher.get_all_signals(state)
        return jsonify({"success": True, **data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
