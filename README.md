# Dodge County Property Price Analyzer

A web application that pulls publicly available real estate data to analyze housing price trends and surface investment opportunities in all four Dodge Counties across the US.

## Features

- **Live price history chart** — Zillow Home Value Index (ZHVI) with 3, 6, and 12-month moving averages
- **Market trend detection** — automatically classifies the market as strong uptrend, downtrend, or sideways
- **Investment scoring** — 0-100 composite score across 5 dimensions: price momentum, affordability, rental yield, market stability, and long-term appreciation
- **Deal finder** — identifies specific opportunities (buy-the-dip, cash-flow rental, affordability plays, favorable buy-vs-rent)
- **County comparison** — side-by-side view of all four Dodge Counties (WI, MN, NE, GA)
- **Key metrics** — price-to-rent ratio, price-to-income ratio, gross/net rental yield, affordability index, estimated monthly PITI

## Data Sources (all free, no API keys needed)

| Source | Data |
|---|---|
| [Zillow Research](https://www.zillow.com/research/data/) | County-level ZHVI monthly, 2000–present |
| [US Census Bureau ACS](https://www.census.gov/data/developers/data-sets/acs-5year.html) | Median home value, rent, income (2022 ACS 5-year) |
| [Redfin Data Center](https://www.redfin.com/news/data-center/) | State-level median sale price, DOM, inventory |

## Setup

```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

## Disclaimer

For educational and research purposes only. Consult a licensed real estate professional before making investment decisions.
