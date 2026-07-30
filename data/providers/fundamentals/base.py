from __future__ import annotations

from abc import ABC, abstractmethod

from data.providers.fundamentals.models import RawFundamentalsBundle


class FundamentalDataError(RuntimeError):
    """Base exception raised by fundamental data providers."""


class FundamentalDataConfigurationError(FundamentalDataError):
    """Raised when the provider is misconfigured (bad ticker, bad client, ...)."""


class FundamentalDataUnavailableError(FundamentalDataError):
    """Raised when the provider cannot be reached at all (network/API failure).

    This is distinct from a security simply lacking some financial fields —
    that is a normal, expected outcome represented by empty/missing values
    inside `RawFundamentalsBundle`, not an exception. Only a total fetch
    failure (the source could not be reached or returned nothing at all)
    raises this.
    """


class FundamentalDataProvider(ABC):
    """Interface implemented by every supported fundamental-data source.

    Providers return only the raw, unmodified statement data Yahoo (or any
    future source) publishes — never a computed ratio, rating or valuation.
    All analytical logic lives in `fundamentals/*` and depends only on this
    interface, never on a specific provider's SDK or response shape.
    """

    @abstractmethod
    def fetch(self, ticker: str) -> RawFundamentalsBundle:
        """Fetch the raw fundamentals bundle for one ticker.

        Must never fabricate missing fields: absent data stays absent
        (empty DataFrame / missing dict key), it is never filled with a
        default or an estimate.
        """
        raise NotImplementedError
