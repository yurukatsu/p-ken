"""p-ken: EM market review figures and factor returns.

    config   paths, universes, report period (config/report.toml)
    io       local data readers (data/)
    stats    Blom scores, ntile, regression slopes, period returns
    gemq3    GEMQ3 score
    factors  daily factor returns (regression on exposures by default)
    markets  index / country / sector / stock data for the charts
    charts   slide-sized charts
    report   builds and saves every figure

See docs/manual.md (how to use) and docs/methodology.md (formulas).
"""
