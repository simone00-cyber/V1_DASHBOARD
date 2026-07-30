"""Fundamental (financial statement) data providers.

`FundamentalDataProvider` is the seam between the analytical engine in
`fundamentals/` and whichever external source supplies raw financial-statement
data. Yahoo Finance (via `yfinance`) is the only implementation today; a future
Financial Modeling Prep (or other) provider can be added here without any
change to `fundamentals/*`.
"""

from data.providers.fundamentals.base import (
    FundamentalDataConfigurationError,
    FundamentalDataError,
    FundamentalDataProvider,
    FundamentalDataUnavailableError,
)
from data.providers.fundamentals.models import RawFundamentalsBundle
from data.providers.fundamentals.yfinance_provider import YFinanceFundamentalsProvider

__all__ = [
    "FundamentalDataConfigurationError",
    "FundamentalDataError",
    "FundamentalDataProvider",
    "FundamentalDataUnavailableError",
    "RawFundamentalsBundle",
    "YFinanceFundamentalsProvider",
]
