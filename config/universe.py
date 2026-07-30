from typing import Dict, List

EQUITY_INDICES: Dict[str, str] = {
    "S&P 500": "^GSPC", "NASDAQ": "^IXIC", "DOW JONES": "^DJI",
    "RUSSELL 2000": "^RUT", "VIX": "^VIX", "EURO STOXX 50": "^STOXX50E",
    "FTSE MIB": "FTSEMIB.MI", "DAX": "^GDAXI", "CAC 40": "^FCHI",
    "FTSE 100": "^FTSE", "SMI": "^SSMI", "NIKKEI 225": "^N225",
    "HANG SENG": "^HSI", "SHANGHAI": "000001.SS", "SENSEX": "^BSESN",
    "KOSPI": "^KS11",
}
FX_UNIVERSE: Dict[str, str] = {
    "DXY": "DX-Y.NYB", "EUR/USD": "EURUSD=X", "USD/JPY": "JPY=X",
    "GBP/USD": "GBPUSD=X", "USD/CHF": "CHF=X", "AUD/USD": "AUDUSD=X",
    "USD/CNH": "CNH=X",
}
COMMODITY_UNIVERSE: Dict[str, str] = {
    "WTI": "CL=F", "BRENT": "BZ=F", "GOLD": "GC=F", "SILVER": "SI=F",
    "COPPER": "HG=F", "NATURAL GAS": "NG=F",
}
CRYPTO_UNIVERSE: Dict[str, str] = {"BITCOIN": "BTC-USD", "ETHEREUM": "ETH-USD"}
CREDIT_UNIVERSE: Dict[str, str] = {
    "HIGH YIELD": "HYG", "INVESTMENT GRADE": "LQD", "EM BONDS": "EMB",
    "US TREASURY 20Y+": "TLT",
}
BOND_PRICE_PROXIES: Dict[str, str] = {
    "US 2Y FUTURE": "ZT=F", "US 5Y FUTURE": "ZF=F",
    "US 10Y FUTURE": "ZN=F", "US LONG BOND": "ZB=F",
    "BTP 10Y ETF": "BTP10.MI", "GERMANY GOVT BOND ETF": "IS0L.DE",
}
RATE_CANDIDATES: Dict[str, List[str]] = {
    "US 13W": ["^IRX"], "US 2Y": ["^AXTWO", "^USTTWO", "TMUBMUSD02Y"],
    "US 5Y": ["^FVX"], "US 10Y": ["^TNX"], "US 30Y": ["^TYX"],
}
TIMEFRAME_LABELS = {
    "YEARLY": "Annuale", "QUARTERLY": "Trimestrale",
    "MONTHLY": "Mensile", "WEEKLY": "Settimanale",
}
REGIME_UNIVERSE = {
    "SPY": "SPY", "QQQ": "QQQ", "ACWI": "ACWI", "VIX": "^VIX",
    "DXY": "DX-Y.NYB", "HYG": "HYG", "LQD": "LQD", "TLT": "TLT",
    "COPPER": "HG=F", "GOLD": "GC=F", "US_13W": "^IRX", "US_10Y": "^TNX",
}
