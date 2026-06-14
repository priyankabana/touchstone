from __future__ import annotations

SOURCE_CONTRACTS = {
    "sec_13f": {
        "identity": "cusip",
        "value": "shares * price within 2%",
        "amendment": "13F-HR/A supersedes 13F-HR by filer + period",
    },
    "finra_trace": {
        "freshness": "daily",
    },
    "krx_adapter": {
        "units": "values are in KRW",
    },
    "news_claim": {
        "proof": "a headline's claimed figure must match the official filing",
    },
}
