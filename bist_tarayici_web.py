import sys
import os
import math
import csv
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import yfinance as yf
import streamlit as st

# --- STREAMLIT PAGE CONFIG ---
st.set_page_config(
    page_title="🔍 BIST Hisse Tarayıcı & Pozisyon Hesaplayıcı",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS FOR DARK PREMIUM THEME ---
st.markdown("""
<style>
    /* Dark theme customizations */
    .stApp {
        background-color: #0f1117;
        color: #e2e8f0;
    }
    div[data-testid="stSidebar"] {
        background-color: #1a1f2e;
        border-right: 1px solid #2a3a55;
    }
    div[data-testid="stMetricValue"] {
        font-family: 'Consolas', monospace;
        font-size: 1.5rem !important;
        font-weight: bold;
    }
    .metric-card {
        background-color: #1e2535;
        border: 1px solid #2a3a55;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
    }
    .metric-title {
        font-size: 0.8rem;
        color: #64748b;
        text-transform: uppercase;
        margin-bottom: 4px;
        font-weight: bold;
    }
    .metric-value {
        font-family: 'Consolas', monospace;
        font-size: 1.15rem;
        font-weight: bold;
        color: #e2e8f0;
    }
    .metric-value.accent { color: #4a9eff; }
    .metric-value.green { color: #10d98a; }
    .metric-value.red { color: #ff4d6a; }
    .metric-value.yellow { color: #f59e0b; }
    
    /* Segmented risk meter */
    .risk-bar {
        display: flex;
        height: 14px;
        border-radius: 4px;
        overflow: hidden;
        margin-top: 5px;
        margin-bottom: 5px;
        background-color: #2a3a55;
    }
    .risk-segment {
        flex: 1;
        height: 100%;
    }
    .risk-indicator-container {
        position: relative;
        height: 24px;
        margin-top: 10px;
    }
    .risk-indicator-needle {
        position: absolute;
        top: 0;
        width: 12px;
        height: 12px;
        background-color: #ffffff;
        border: 2px solid #0f1117;
        border-radius: 50%;
        transform: translateX(-50%);
    }
    .rules-card {
        background-color: #1e2535;
        border: 1px solid #2a3a55;
        border-radius: 8px;
        padding: 15px;
        margin-top: 15px;
    }
    .rule-title {
        font-weight: bold;
        font-size: 0.95rem;
        margin-top: 10px;
        margin-bottom: 2px;
    }
    /* Horizontal factors layout */
    .factor-container {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        margin-top: 8px;
        margin-bottom: 8px;
    }
    .factor-item {
        flex: 1;
        background-color: #1e2535;
        border: 1px solid #2a3a55;
        border-radius: 6px;
        padding: 8px;
        text-align: center;
    }
    .factor-name {
        font-size: 0.7rem;
        color: #64748b;
        font-weight: bold;
        text-transform: uppercase;
    }
    .factor-score {
        font-family: 'Consolas', monospace;
        font-size: 1.05rem;
        font-weight: bold;
        margin-top: 2px;
    }
</style>
""", unsafe_allow_html=True)

# --- BIST100 TICKERS & SECTORS ---
BIST100_TICKERS = [
    "AKBNK", "AKSEN", "AKSA",  "AEFES", "ALARK", "ANACM", "ARCLK", "ASELS",
    "AYGAZ", "BAGFS", "BIMAS", "BIOEN", "BRISA", "CCOLA", "CIMSA", "DEVA",
    "DOHOL", "EGEEN", "EKGYO", "ENKAI", "ENJSA", "EREGL", "FENER", "FROTO",
    "GARAN", "GESAN", "GUBRF", "GWIND", "HALKB", "HEKTS", "INDES", "IPEKE",
    "ISCTR", "ISDMR", "ISGSY", "ISMEN", "JANTS", "KAREL", "KCHOL", "KERVT",
    "KLNMA", "KONYA", "KRDMD", "LOGO",  "MAVI",  "MGROS", "MIATK", "NETAS",
    "NTHOL", "ODAS",  "OTKAR", "OYAKC", "PARSN", "PETKM", "PGSUS", "PLTUR",
    "PRKAB", "RAYSG", "RYSAS", "SAHOL", "SARKY", "SASA",  "SELEC", "SISE",
    "SKBNK", "SODA",  "SOKM",  "TATEN", "TAVHL", "TCELL", "THYAO", "TIRE",
    "TKFEN", "TOASO", "TRCAS", "TRGYO", "TRKCM", "TSKB",  "TTKOM", "TTRAK",
    "TUPRS", "TURSG", "ULKER", "ULUUN", "VAKBN", "VESBE", "VESTL", "YATAS",
    "YKBNK", "ZGOLD", "AGHOL", "ALGYO", "CEMTS", "HRKET", "SNPAM", "AKGRT",
    "ANHYT", "KUYAS", "NUHCM", "ZRGYO",
]

BIST_SECTORS = {
    "Bankaci": ["AKBNK", "GARAN", "HALKB", "ISCTR", "SKBNK", "TSKB", "VAKBN", "YKBNK"],
    "Holding": ["DOHOL", "ENKAI", "KCHOL", "SAHOL", "AGHOL", "NTHOL", "ISMEN", "ISGSY"],
    "Emlak": ["EKGYO", "TRGYO", "ALGYO", "ZRGYO"],
    "Enerji": ["AKSEN", "ENJSA", "ODAS", "BIOEN", "GWIND", "TATEN", "AYGAZ", "TUPRS", "IPEKE"],
    "Sanayi": ["ARCLK", "ASELS", "FROTO", "OTKAR", "TOASO", "VESTL", "VESBE", "TTRAK", "JANTS", "BRISA"],
    "Metal": ["EREGL", "KRDMD", "ISDMR", "SARKY", "TIRE", "TRCAS"],
    "Kimya": ["PETKM", "SASA", "SODA", "BAGFS", "GUBRF", "AKSA", "HEKTS", "DEVA"],
    "Perakende": ["BIMAS", "MGROS", "SOKM", "ULKER", "CCOLA", "AEFES", "MAVI", "YATAS"],
    "Havacilik": ["THYAO", "PGSUS", "TAVHL", "TURSG"],
    "Telekom": ["TTKOM", "TCELL", "LOGO", "NETAS", "KAREL", "INDES", "SELEC"],
    "Insaat": ["CIMSA", "KONYA", "ANACM", "TRKCM", "NUHCM", "CEMTS", "TKFEN"],
    "Sigorta": ["AKGRT", "ANHYT", "RAYSG", "ALARK", "MIATK", "ULUUN"],
}

# --- HTTP SESSION CREATION FOR YFINANCE ---
def get_yf_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    retries = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session

# --- PIVOT ANALYSIS ---
def find_pivot_lows(prices: pd.Series, window: int = 10) -> list:
    arr = prices.values
    n   = len(arr)
    pivots = []
    for i in range(window, n - window):
        lo = arr[max(0, i - window): i + window + 1]
        if arr[i] == lo.min() and arr[i] > 0:
            pivots.append((prices.index[i], float(arr[i])))
    return pivots

def cluster_support_zones(pivots: list, tolerance: float = 0.03) -> list:
    if not pivots:
        return []
    sorted_pivots = sorted(pivots, key=lambda x: x[1])
    zones = []
    current_group = [sorted_pivots[0]]
    for date, price in sorted_pivots[1:]:
        ref = current_group[0][1]
        if ref > 0 and (price - ref) / ref <= tolerance:
            current_group.append((date, price))
        else:
            avg  = sum(p for _, p in current_group) / len(current_group)
            last = max(d for d, _ in current_group)
            zones.append({"price": avg, "touches": len(current_group), "last_date": last})
            current_group = [(date, price)]
    avg  = sum(p for _, p in current_group) / len(current_group)
    last = max(d for d, _ in current_group)
    zones.append({"price": avg, "touches": len(current_group), "last_date": last})
    return zones

def score_support_proximity(current_usd: float, zones: list, now: datetime) -> dict:
    supports_below = [z for z in zones if z["price"] <= current_usd * 1.05]
    if not supports_below:
        return {"score": 0, "nearest_support": None, "distance_pct": None, "touches": 0}
    nearest = min(supports_below, key=lambda z: abs(current_usd - z["price"]))
    distance_pct = (current_usd - nearest["price"]) / nearest["price"] * 100
    proximity_score = max(0.0, 100.0 - distance_pct * 4.0)
    touch_mult = min(1.0, 0.6 + nearest["touches"] * 0.13)
    ld = nearest["last_date"]
    try:
        if hasattr(ld, "to_pydatetime"):
            ld = ld.to_pydatetime().replace(tzinfo=None)
        days_ago = (now - ld).days
    except Exception:
        days_ago = 730
    recency = max(0.3, 1.0 - days_ago / (365 * 3))
    final = min(100.0, proximity_score * touch_mult * recency)
    return {
        "score":           final,
        "nearest_support": nearest["price"],
        "distance_pct":    distance_pct,
        "touches":         nearest["touches"],
    }

# --- PD/DD ANALYSIS ---
def _pb_score(current_pb, hist_avg_pb) -> float:
    if current_pb is None or hist_avg_pb is None or hist_avg_pb <= 0:
        return 50.0
    ratio = current_pb / hist_avg_pb
    if   ratio <= 0.50: return 100.0
    elif ratio <= 0.65: return  88.0
    elif ratio <= 0.80: return  74.0
    elif ratio <= 0.95: return  58.0
    elif ratio <= 1.10: return  38.0
    elif ratio <= 1.30: return  18.0
    else:               return   0.0

def compute_historical_pb_custom(bs, info, price_try_df: pd.DataFrame) -> dict:
    current_pb = None
    try:
        current_pb = info.get("priceToBook", None)
    except Exception:
        pass

    hist_avg   = None
    pb_samples = 0
    try:
        if bs is None or bs.empty:
            raise ValueError("Bilanco bos")
        eq_row = None
        for key in ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity", 
                    "Total Equity Gross Minority Interest", "Equity"]:
            if key in bs.index:
                eq_row = bs.loc[key]
                break
        shares = None
        try:
            shares = info.get("sharesOutstanding", None)
        except Exception:
            pass
        if eq_row is None or not shares or shares <= 0:
            raise ValueError("Eksik veri")

        pb_list = []
        for col_date in eq_row.index:
            eq_val = eq_row[col_date]
            if pd.isna(eq_val) or eq_val <= 0:
                continue
            bvps = float(eq_val) / float(shares)
            try:
                ts  = pd.Timestamp(col_date)
                idx = price_try_df.index.asof(ts)
                if pd.isna(idx):
                    continue
                price = float(price_try_df.loc[idx, "Close"])
                if price > 0 and bvps > 0:
                    pb = price / bvps
                    if 0.01 < pb < 1000:
                        pb_list.append(pb)
            except Exception:
                continue
        if pb_list:
            hist_avg   = float(np.mean(pb_list))
            pb_samples = len(pb_list)
    except Exception:
        pass

    score    = _pb_score(current_pb, hist_avg)
    pb_ratio = (current_pb / hist_avg) if (current_pb and hist_avg and hist_avg > 0) else None

    if current_pb is not None and pb_samples >= 8:
        quality = "iyi"
    elif current_pb is not None and pb_samples >= 3:
        quality = "orta"
    elif current_pb is not None:
        quality = "eksik-tarih"
    else:
        quality = "eksik"

    return {
        "current_pb":  current_pb,
        "hist_avg_pb": hist_avg,
        "pb_score":    score,
        "pb_ratio":    pb_ratio,
        "pb_quality":  quality,
        "pb_samples":  pb_samples,
    }

# --- BOFA MULTI-FACTOR QUANTITATIVE MODEL ---
def calculate_bofa_metrics(hist: pd.DataFrame, info: dict, pb_info: dict) -> dict:
    # 1. VALUE PILLAR (Değer)
    # PEG Ratio: PEG <= 1.0 -> 100 pts, PEG >= 2.0 -> 0 pts. Linear interpolation.
    peg = info.get("pegRatio")
    if peg is not None:
        peg_score = max(0.0, min(100.0, 100.0 - (peg - 1.0) * 100.0))
    else:
        peg_score = 50.0  # neutral fallback
        
    # FCF Yield: Free Cash Flow / Market Cap. Yield >= 8% -> 100 pts, <= 0% -> 0 pts.
    fcf = info.get("freeCashflow")
    mcap = info.get("marketCap")
    fcf_yield = (fcf / mcap) if (fcf and mcap and mcap > 0) else None
    if fcf_yield is not None:
        fcf_score = max(0.0, min(100.0, (fcf_yield / 0.08) * 100.0))
    else:
        fcf_score = 50.0
        
    # P/B Ratio Deviation relative to 5Y historical average
    pb_ratio = pb_info.get("pb_ratio")
    if pb_ratio is not None:
        pb_deviation_score = max(0.0, min(100.0, 100.0 - (pb_ratio - 0.8) * 142.8)) # 0.8 -> 100, 1.5 -> 0
    else:
        pb_deviation_score = 50.0
        
    value_score = (peg_score + fcf_score + pb_deviation_score) / 3.0

    # 2. GROWTH PILLAR (Büyüme)
    # Revenue Growth (YoY): Growth >= 30% -> 100 pts, <= 0% -> 0.
    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None:
        rev_growth_score = max(0.0, min(100.0, (rev_growth / 0.3) * 100.0))
    else:
        rev_growth_score = 50.0
        
    # Earnings Growth (YoY): Growth >= 20% -> 100 pts, <= -10% -> 0.
    earn_growth = info.get("earningsGrowth")
    if earn_growth is not None:
        earn_growth_score = max(0.0, min(100.0, ((earn_growth + 0.1) / 0.3) * 100.0))
    else:
        earn_growth_score = 50.0
        
    growth_score = (rev_growth_score + earn_growth_score) / 2.0

    # 3. QUALITY PILLAR (Kalite)
    # ROE (Return on Equity): ROE >= 25% -> 100 pts, <= 5% -> 0.
    roe = info.get("returnOnEquity")
    if roe is not None:
        roe_score = max(0.0, min(100.0, ((roe - 0.05) / 0.20) * 100.0))
    else:
        roe_score = 50.0
        
    # Debt to Equity: D/E <= 50% -> 100 pts, D/E >= 200% -> 0.
    de = info.get("debtToEquity")
    if de is not None:
        de_val = de / 100.0 if de > 3.0 else de
        de_score = max(0.0, min(100.0, 100.0 - (de_val - 0.5) * 66.6)) # 0.5 -> 100, 2.0 -> 0
    else:
        de_score = 50.0
        
    quality_score = (roe_score + de_score) / 2.0

    # 4. MOMENTUM PILLAR (Trend)
    # 6-Month Return: Return >= 30% -> 100 pts, <= -10% -> 0.
    mom_score_6m = 50.0
    ret_6m = None
    if not hist.empty and len(hist) >= 120:
        try:
            close_prices = hist["Close"].values
            ret_6m = (close_prices[-1] - close_prices[-120]) / close_prices[-120]
            mom_score_6m = max(0.0, min(100.0, ((ret_6m + 0.1) / 0.4) * 100.0)) # -10% -> 0, +30% -> 100
        except Exception:
            mom_score_6m = 50.0
    else:
        mom_score_6m = 50.0
        
    # Golden Cross: 50 EMA > 200 EMA -> 100, else 30
    has_golden_cross = False
    if not hist.empty and len(hist) >= 200:
        try:
            ema50 = hist["Close"].ewm(span=50, adjust=False).mean().iloc[-1]
            ema200 = hist["Close"].ewm(span=200, adjust=False).mean().iloc[-1]
            has_golden_cross = bool(ema50 > ema200)
        except Exception:
            pass
            
    trend_score = 100.0 if has_golden_cross else 30.0
    momentum_score = (mom_score_6m + trend_score) / 2.0

    # COMPOSITE BOFA SCORE
    composite = 0.25 * value_score + 0.25 * growth_score + 0.25 * quality_score + 0.25 * momentum_score
    
    return {
        "bofa_val_peg": peg,
        "bofa_val_fcf_yield": fcf_yield,
        "bofa_val_pb_ratio": pb_ratio,
        "bofa_gro_rev": rev_growth,
        "bofa_gro_earn": earn_growth,
        "bofa_qal_roe": roe,
        "bofa_qal_de": de,
        "bofa_mom_ret6m": ret_6m,
        "bofa_mom_golden": has_golden_cross,
        
        "bofa_score_value": value_score,
        "bofa_score_growth": growth_score,
        "bofa_score_quality": quality_score,
        "bofa_score_momentum": momentum_score,
        "bofa_composite": composite
    }

# --- CACHED DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_usdtry_rates(start_date, end_date):
    try:
        session = get_yf_session()
        raw = yf.download("USDTRY=X", start=start_date, end=end_date, auto_adjust=True, progress=False, session=session)
        if not raw.empty:
            close_col = raw["Close"]
            if isinstance(close_col, pd.DataFrame):
                close_col = close_col.iloc[:, 0]
            usdtry = close_col.squeeze()
            if hasattr(usdtry.index, 'tz') and usdtry.index.tz is not None:
                usdtry.index = usdtry.index.tz_convert(None)
            return usdtry
    except Exception:
        pass
    return pd.Series(dtype=float)

@st.cache_data(ttl=3600)
def fetch_single_ticker_raw(ticker, start_date, end_date):
    symbol = ticker + ".IS"
    session = get_yf_session()
    t = yf.Ticker(symbol, session=session)
    hist = t.history(start=start_date, end=end_date, auto_adjust=True)
    info = {}
    try:
        info = t.info
    except Exception:
        pass
    qbs = None
    try:
        qbs = t.quarterly_balance_sheet
    except Exception:
        pass
    return hist, info, qbs

def fetch_one_stock(ticker: str, usdtry: pd.Series, start, end, now: datetime) -> dict:
    try:
        hist, info, qbs = fetch_single_ticker_raw(ticker, start, end)
        if hist.empty or len(hist) < 60:
            return None
        if hasattr(hist.index, 'tz') and hist.index.tz is not None:
            hist.index = hist.index.tz_convert(None)

        price_try = hist[["Close"]].copy()

        # USD Fiyat Serisi
        if not usdtry.empty:
            rate_aligned = usdtry.reindex(price_try.index, method="ffill")
            price_usd    = price_try["Close"] / rate_aligned
        else:
            try:
                cur_rate = float(info.get("regularMarketPrice", 38.0))
            except Exception:
                cur_rate = 38.0
            price_usd = price_try["Close"] / cur_rate

        price_usd = price_usd.dropna()
        if len(price_usd) < 60:
            return None

        current_usd = float(price_usd.iloc[-1])
        current_try = float(price_try["Close"].iloc[-1])

        # Destek analizi
        pivots       = find_pivot_lows(price_usd, window=10)
        zones        = cluster_support_zones(pivots, tolerance=0.03)
        support_info = score_support_proximity(current_usd, zones, now)

        # PD/DD analizi
        pb_info = compute_historical_pb_custom(qbs, info, price_try)

        # Bileşik Skor (Destek + PD/DD)
        composite = 0.4 * support_info["score"] + 0.6 * pb_info["pb_score"]
        
        # BofA Kantitatif Skorları hesapla
        bofa = calculate_bofa_metrics(hist, info, pb_info)

        name = info.get("longName", ticker) or ticker
        sector = info.get("sector", "—") or "—"

        res = {
            "ticker":              ticker,
            "name":                name,
            "sector":              sector,
            "current_try":         current_try,
            "current_usd":         current_usd,
            "nearest_support_usd": support_info.get("nearest_support"),
            "distance_pct":        support_info.get("distance_pct"),
            "support_score":       support_info["score"],
            "support_touches":     support_info.get("touches", 0),
            "zones_count":         len(zones),
            "current_pb":          pb_info["current_pb"],
            "hist_avg_pb":         pb_info["hist_avg_pb"],
            "pb_ratio":            pb_info["pb_ratio"],
            "pb_score":            pb_info["pb_score"],
            "pb_quality":          pb_info.get("pb_quality", "eksik"),
            "pb_samples":          pb_info.get("pb_samples", 0),
            "composite_score":     composite,
        }
        res.update(bofa)
        return res
    except Exception:
        return None

# --- CUSTOM CIRCULAR GAUGE COMPONENT (SVG) ---
def draw_svg_gauge(score, title="BILEŞIK SKOR"):
    score = max(0, min(100, score))
    if score >= 65:
        color = "#10d98a"
    elif score >= 40:
        color = "#f59e0b"
    else:
        color = "#ff4d6a"
    angle = score * 1.8
    rad = math.radians(180 - angle)
    ex = 80 + 70 * math.cos(rad)
    ey = 90 - 70 * math.sin(rad)
    colored_path = f'<path d="M 10 90 A 70 70 0 0 1 {ex:.2f} {ey:.2f}" fill="none" stroke="{color}" stroke-width="12" stroke-linecap="round" />' if score > 0 else ""
    nx = 80 + 58 * math.cos(rad)
    ny = 90 - 58 * math.sin(rad)
    
    svg_html = f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; background-color: #1e2535; padding: 15px; border-radius: 8px; border: 1px solid #2a3a55; width: 100%;">
        <span style="font-size: 0.8rem; font-weight: bold; color: #64748b; text-transform: uppercase; margin-bottom: 5px;">{title}</span>
        <svg width="150" height="100" viewBox="0 0 160 105" xmlns="http://www.w3.org/2000/svg">
            <path d="M 10 90 A 70 70 0 0 1 150 90" fill="none" stroke="#2a3a55" stroke-width="12" stroke-linecap="round" />
            {colored_path}
            <line x1="80" y1="90" x2="{nx:.2f}" y2="{ny:.2f}" stroke="#ffffff" stroke-width="3" stroke-linecap="round" />
            <circle cx="80" cy="90" r="6" fill="#ffffff" />
            <text x="80" y="85" text-anchor="middle" font-family="monospace" font-size="20" font-weight="bold" fill="{color}">{score:.0f}</text>
        </svg>
    </div>
    """
    return svg_html

# --- INITIALIZE SESSION STATE ---
if "results" not in st.session_state:
    st.session_state.results = {}
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = None
if "calc_entry_price" not in st.session_state:
    st.session_state.calc_entry_price = 69.10
if "calc_usd_rate" not in st.session_state:
    st.session_state.calc_usd_rate = 47.03

# --- MAIN APP LAYOUT ---
st.title("🔍 BIST Hisse Analiz Platformu")
st.caption("BIST100 Çok Faktörlü Hisse Tarama & Pozisyon Risk Hesaplayıcı")

# Create main tabs
tab_scan, tab_calc = st.tabs(["🔍 BIST Hisse Tarayıcı", "📊 Pozisyon Hesaplayıcı"])

# --- TAB 1: STOCK SCANNER ---
with tab_scan:
    # Sidebar: Strategy & Filters
    st.sidebar.header("🎛️ Analiz Parametreleri")
    strategy = st.sidebar.selectbox("Analiz Stratejisi", ["Destek + PD/DD", "BofA Kantitatif Faktör"], help="Hisseleri analiz ederken ve puanlarken kullanılacak temel mantık modelini seçin.")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filtre Ayarları")
    
    if strategy == "Destek + PD/DD":
        min_support = st.sidebar.slider("Min Destek Skoru", 0, 100, 30, help="0: Etkisiz, 100: En güçlü destek seviyesi")
        min_pb = st.sidebar.slider("Min PD/DD Skoru", 0, 100, 60, help="Veri yoksa varsayılan 50p. Düşük PD/DD -> Yüksek skor")
        min_touches = st.sidebar.slider("Min Dokunma (Destek)", 1, 10, 2, help="Seviyenin test edilme sayısı")
    else:
        min_bofa = st.sidebar.slider("Min BofA Kompozit Skor", 0, 100, 50, help="4 faktörün (Değer, Büyüme, Kalite, Momentum) dengeli ortalama skoru.")
        min_value = st.sidebar.slider("Min Değer Skoru", 0, 100, 30, help="PEG Oranı, Serbest Nakit Verimi ve PD/DD sapma ortalaması.")
        min_growth = st.sidebar.slider("Min Büyüme Skoru", 0, 100, 30, help="Gelir ve Net Kar yıllık büyüme oranları.")
        min_quality = st.sidebar.slider("Min Kalite Skoru", 0, 100, 30, help="Borçluluk seviyesi ve ROE verimi.")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Veri Güncelliği")
    st.sidebar.info("Bilanço ve mali veriler Yahoo Finance üzerinden çeyreklik bazda çekilir. Hareketli ortalamalar ve trend günlük güncellenir.")

    # Actions panel
    col_act1, col_act2 = st.columns([1, 2])
    with col_act1:
        st.write("### 🚀 Taramayı Başlat")
        scan_bist100 = st.button("🔍 BIST100 Tümünü Tara", type="primary", use_container_width=True)
    with col_act2:
        st.write("### 📁 Sektör/Grup Bazlı Tara")
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            selected_sector = st.selectbox("Sektör Seçin", list(BIST_SECTORS.keys()), label_visibility="collapsed")
        with col_s2:
            scan_sector = st.button("Sektörü Tara", use_container_width=True)

    # Scanning Logic Execution
    if scan_bist100 or scan_sector:
        tickers = BIST100_TICKERS if scan_bist100 else BIST_SECTORS[selected_sector]
        st.session_state.results = {}
        
        start = datetime.now() - timedelta(days=365 * 5 + 60)
        end = datetime.now()
        now = datetime.now()
        
        # Pull USDTRY
        with st.spinner("USD/TRY Döviz Kuru Güncelleniyor..."):
            usdtry = get_usdtry_rates(start, end)
            
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total = len(tickers)
        success_count = 0
        for i, ticker in enumerate(tickers):
            status_text.text(f"⏳ Taranıyor: {ticker} ({i+1}/{total})")
            progress_bar.progress((i + 1) / total)
            
            res = fetch_one_stock(ticker, usdtry, start, end, now)
            if res:
                st.session_state.results[ticker] = res
                success_count += 1
                
            time.sleep(0.3)
                
        progress_bar.empty()
        status_text.success(f"✅ Tarama tamamlandı! {success_count} hisse analiz edildi.")

    # Process & Display Results
    if st.session_state.results:
        results_df = pd.DataFrame(list(st.session_state.results.values()))
        
        # Apply Filters based on active strategy
        if strategy == "Destek + PD/DD":
            filtered_df = results_df[
                (results_df["support_score"] >= min_support) &
                (results_df["pb_score"] >= min_pb) &
                (results_df["support_touches"] >= min_touches)
            ]
        else:
            filtered_df = results_df[
                (results_df["bofa_composite"] >= min_bofa) &
                (results_df["bofa_score_value"] >= min_value) &
                (results_df["bofa_score_growth"] >= min_growth) &
                (results_df["bofa_score_quality"] >= min_quality)
            ]
        
        if filtered_df.empty:
            st.warning("⚠️ Seçilen filtrelere uyan hisse bulunamadı. Filtre limitlerini azaltmayı deneyebilirsiniz.")
        else:
            # Format DataFrame for UI
            display_df = filtered_df.copy()
            display_df["current_try"] = display_df["current_try"].map("₺{:,.2f}".format)
            display_df["current_usd"] = display_df["current_usd"].map("${:,.4f}".format)
            
            # Strategy Specific formatting
            if strategy == "Destek + PD/DD":
                display_df["nearest_support_usd"] = display_df["nearest_support_usd"].map(lambda x: f"${x:,.4f}" if pd.notnull(x) else "—")
                display_df["distance_pct"] = display_df["distance_pct"].map(lambda x: f"{x:.1f}%" if pd.notnull(x) else "—")
                display_df["current_pb"] = display_df["current_pb"].map(lambda x: f"{x:.2f}x" if pd.notnull(x) else "—")
                display_df["hist_avg_pb"] = display_df["hist_avg_pb"].map(lambda x: f"{x:.2f}x" if pd.notnull(x) else "—")
                display_df["pb_ratio"] = display_df["pb_ratio"].map(lambda x: f"{x:.2f}×" if pd.notnull(x) else "—")
                display_df["composite_score"] = display_df["composite_score"].map("{:.1f}".format)
            else:
                display_df["bofa_composite"] = display_df["bofa_composite"].map("{:.1f}".format)
                display_df["bofa_score_value"] = display_df["bofa_score_value"].map("{:.1f}".format)
                display_df["bofa_score_growth"] = display_df["bofa_score_growth"].map("{:.1f}".format)
                display_df["bofa_score_quality"] = display_df["bofa_score_quality"].map("{:.1f}".format)
                display_df["bofa_score_momentum"] = display_df["bofa_score_momentum"].map("{:.1f}".format)
            
            # Layout: Table left, Detail Panel right
            col_tbl, col_det = st.columns([3, 1])
            
            with col_tbl:
                st.subheader(f"Analiz Edilen Hisseler ({len(filtered_df)} / {len(results_df)} adet listeleniyor)")
                
                # Render interactive Table depending on strategy
                if strategy == "Destek + PD/DD":
                    st.dataframe(
                        display_df[[
                            "ticker", "name", "sector", "current_try", "current_usd", 
                            "nearest_support_usd", "distance_pct", "support_touches", 
                            "current_pb", "hist_avg_pb", "pb_ratio", "composite_score"
                        ]].rename(columns={
                            "ticker": "Hisse", "name": "Adı", "sector": "Sektör",
                            "current_try": "Fiyat ₺", "current_usd": "USD Fiyat",
                            "nearest_support_usd": "USD Destek", "distance_pct": "Uzaklık %",
                            "support_touches": "Dokunma", "current_pb": "PD/DD",
                            "hist_avg_pb": "PD/DD 5Y Ort.", "pb_ratio": "PD/DD Oran",
                            "composite_score": "Bileşik Skor"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.dataframe(
                        display_df[[
                            "ticker", "name", "sector", "current_try", "current_usd",
                            "bofa_composite", "bofa_score_value", "bofa_score_growth", 
                            "bofa_score_quality", "bofa_score_momentum"
                        ]].rename(columns={
                            "ticker": "Hisse", "name": "Adı", "sector": "Sektör",
                            "current_try": "Fiyat ₺", "current_usd": "USD Fiyat",
                            "bofa_composite": "BofA Skoru", "bofa_score_value": "Değer",
                            "bofa_score_growth": "Büyüme", "bofa_score_quality": "Kalite",
                            "bofa_score_momentum": "Momentum"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                
                # Download CSV
                csv_data = filtered_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="📥 Sonuçları CSV Olarak İndir",
                    data=csv_data,
                    file_name=f"bist_tarayici_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
            with col_det:
                st.subheader("🔍 Hisse Büyüteci")
                selected_ticker = st.selectbox("Detaylı incelemek için hisse seçin", list(filtered_df["ticker"]))
                
                if selected_ticker:
                    r = st.session_state.results[selected_ticker]
                    st.session_state.selected_ticker = selected_ticker
                    
                    # Circular Gauge based on strategy
                    score_to_draw = r["composite_score"] if strategy == "Destek + PD/DD" else r["bofa_composite"]
                    title_to_draw = "DESTEK SKORU" if strategy == "Destek + PD/DD" else "BOFA KOMPOZİT"
                    st.markdown(draw_svg_gauge(score_to_draw, title_to_draw), unsafe_allow_html=True)
                    
                    st.markdown(f"### {r['name']}")
                    st.markdown(f"**Sektör:** `{r['sector']}` | **Yahoo Kodu:** `{r['ticker']}.IS`")
                    st.markdown("---")
                    
                    # Custom metric panel lists
                    def render_row(label, val, unit, style=""):
                        color_cls = f"class='metric-value {style}'" if style else "class='metric-value'"
                        return f"<div class='metric-card'><div class='metric-title'>{label}</div><div {color_cls}>{val} {unit}</div></div>"
                    
                    st.markdown(render_row("Fiyat (TRY)", f"{r['current_try']:,.2f}", "₺"), unsafe_allow_html=True)
                    st.markdown(render_row("Fiyat (USD)", f"{r['current_usd']:.4f}", "$"), unsafe_allow_html=True)
                    
                    if strategy == "Destek + PD/DD":
                        # Original Details Panel
                        supp_val = f"${r['nearest_support_usd']:.4f}" if r['nearest_support_usd'] else "—"
                        dist_val = f"{r['distance_pct']:.1f}%" if r['distance_pct'] else "—"
                        st.markdown(render_row("USD Destek Seviyesi", supp_val, ""), unsafe_allow_html=True)
                        st.markdown(render_row("Desteğe Uzaklık", dist_val, "", "yellow" if r['distance_pct'] and r['distance_pct'] < 5 else ""), unsafe_allow_html=True)
                        st.markdown(render_row("Destek Temas Sayısı", f"{r['support_touches']}", " kez"), unsafe_allow_html=True)
                        
                        pb_val = f"{r['current_pb']:.2f}x" if r['current_pb'] else "—"
                        pb_avg_val = f"{r['hist_avg_pb']:.2f}x" if r['hist_avg_pb'] else "—"
                        pb_dev_val = f"{r['pb_ratio']:.2f}×" if r['pb_ratio'] else "—"
                        st.markdown(render_row("PD/DD (Güncel)", pb_val, ""), unsafe_allow_html=True)
                        st.markdown(render_row("PD/DD (5 Yıllık Ortalama)", pb_avg_val, ""), unsafe_allow_html=True)
                        st.markdown(render_row("PD/DD Oranı (Güncel/Ortalama)", pb_dev_val, "ort.", "green" if r['pb_ratio'] and r['pb_ratio'] < 1 else "red" if r['pb_ratio'] and r['pb_ratio'] > 1.2 else ""), unsafe_allow_html=True)
                        
                        st.markdown(render_row("Destek Skoru", f"{r['support_score']:.0f}", "/ 100", "accent"), unsafe_allow_html=True)
                        st.markdown(render_row("PD/DD Skoru", f"{r['pb_score']:.0f}", "/ 100", "accent"), unsafe_allow_html=True)
                    else:
                        # BofA Factor Details Panel
                        st.markdown(f"""
                        <div class="factor-container">
                            <div class="factor-item">
                                <div class="factor-name">Değer</div>
                                <div class="factor-score" style="color: #4a9eff;">{r['bofa_score_value']:.0f}</div>
                            </div>
                            <div class="factor-item">
                                <div class="factor-name">Büyüme</div>
                                <div class="factor-score" style="color: #a78bfa;">{r['bofa_score_growth']:.0f}</div>
                            </div>
                            <div class="factor-item">
                                <div class="factor-name">Kalite</div>
                                <div class="factor-score" style="color: #10d98a;">{r['bofa_score_quality']:.0f}</div>
                            </div>
                            <div class="factor-item">
                                <div class="factor-name">Trend</div>
                                <div class="factor-score" style="color: #f59e0b;">{r['bofa_score_momentum']:.0f}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Individual BofA metrics
                        peg_val = f"{r['bofa_val_peg']:.2f}" if r['bofa_val_peg'] is not None else "—"
                        fcf_val = f"{r['bofa_val_fcf_yield']*100:.1f}%" if r['bofa_val_fcf_yield'] is not None else "—"
                        rev_val = f"{r['bofa_gro_rev']*100:.1f}%" if r['bofa_gro_rev'] is not None else "—"
                        earn_val = f"{r['bofa_gro_earn']*100:.1f}%" if r['bofa_gro_earn'] is not None else "—"
                        roe_val = f"{r['bofa_qal_roe']*100:.1f}%" if r['bofa_qal_roe'] is not None else "—"
                        de_val = f"{r['bofa_qal_de']:.1f}%" if r['bofa_qal_de'] is not None else "—"
                        
                        ret_val = f"{r['bofa_mom_ret6m']*100:.1f}%" if r['bofa_mom_ret6m'] is not None else "—"
                        gc_val = "Boğa (EMA50 > EMA200)" if r['bofa_mom_golden'] else "Ayı (EMA50 < EMA200)"
                        gc_style = "green" if r['bofa_mom_golden'] else "red"
                        
                        st.markdown(render_row("PEG Oranı (F/K / Büyüme)", peg_val, "", "green" if r['bofa_val_peg'] and r['bofa_val_peg'] < 1 else ""), unsafe_allow_html=True)
                        st.markdown(render_row("Serbest Nakit Akış Verimi", fcf_val, "", "green" if r['bofa_val_fcf_yield'] and r['bofa_val_fcf_yield'] > 0.08 else ""), unsafe_allow_html=True)
                        st.markdown(render_row("Yıllık Gelir Büyümesi (YoY)", rev_val, ""), unsafe_allow_html=True)
                        st.markdown(render_row("Yıllık Net Kar Büyümesi (YoY)", earn_val, ""), unsafe_allow_html=True)
                        st.markdown(render_row("Özsermaye Karlılığı (ROE)", roe_val, "", "green" if r['bofa_qal_roe'] and r['bofa_qal_roe'] > 0.25 else ""), unsafe_allow_html=True)
                        st.markdown(render_row("Borç / Özsermaye (D/E)", de_val, ""), unsafe_allow_html=True)
                        st.markdown(render_row("6 Aylık Fiyat Değişimi", ret_val, ""), unsafe_allow_html=True)
                        st.markdown(render_row("Uzun Vadeli Trend Yapısı", gc_val, "", gc_style), unsafe_allow_html=True)
                    
                    # Send to Calculator Button
                    if st.button("📊 Seçili Hisseyi Hesaplayıcıya Gönder", use_container_width=True, type="primary"):
                        st.session_state.calc_entry_price = r["current_try"]
                        st.session_state.calc_usd_rate = r["current_try"] / r["current_usd"] if r["current_usd"] > 0 else 38.0
                        st.success(f"✅ {selected_ticker} bilgileri Pozisyon Hesaplayıcı sekmesine aktarıldı!")
                        
    else:
        st.info("💡 Sonuçları görüntülemek için yukarıdaki butonlardan taramayı başlatın.")

# --- TAB 2: POSITION CALCULATOR ---
with tab_calc:
    st.subheader("📊 Pozisyon Büyüklüğü ve Risk Yönetimi Hesaplayıcısı")
    st.markdown("Komisyon hesaba katılmadan swing işlem limitleri belirler.")
    
    col_inp, col_res = st.columns([1, 2])
    
    with col_inp:
        st.write("### 📥 Girdiler")
        
        # Prepopulate helper if clicked from scanning
        st.markdown(f"**Yüklü Hisse Fiyatı:** `₺{st.session_state.calc_entry_price:,.2f}` | **Kur:** `{st.session_state.calc_usd_rate:.2f}`")
        
        capital = st.number_input("Toplam Portföy Sermayesi (TRY)", min_value=100.0, value=100000.0, step=1000.0, format="%.2f")
        entry_price = st.number_input("Hisse Giriş Fiyatı (TRY)", min_value=0.01, value=float(st.session_state.calc_entry_price), step=0.05, format="%.2f")
        usd_rate = st.number_input("USD/TRY Döviz Kuru", min_value=1.0, value=float(st.session_state.calc_usd_rate), step=0.01, format="%.4f")
        
        risk_pct = st.slider("Portföy Kayıp Riski (%)", 0.1, 10.0, 2.0, step=0.1, help="Tek işlemde kaybetmeyi göze aldığınız portföy yüzdesi")
        stop_pct = st.slider("Stop-Loss Yüzdesi (%)", 2.0, 15.0, 6.0, step=0.5, help="Giriş fiyatından stop fiyatına olan mesafe")
        rr_ratio = st.slider("Risk/Reward (T1) Oranı", 1.0, 5.0, 2.0, step=0.1, help="Risk başına beklenen getiri (örn: 2.0 ise stop mesafesinin 2 katı hedeftir)")
        
    with col_res:
        st.write("### ⚡ Sonuçlar")
        
        # Calculate Math
        max_risk = capital * (risk_pct / 100.0)
        stop_price = entry_price * (1.0 - (stop_pct / 100.0))
        loss_per_share = entry_price - stop_price
        
        lots = max(1, math.floor(max_risk / loss_per_share))
        position_try = lots * entry_price
        actual_risk = lots * loss_per_share
        
        # Targets
        t1 = entry_price * (1.0 + (stop_pct / 100.0) * rr_ratio)
        t2 = entry_price * (1.0 + (stop_pct / 100.0) * rr_ratio * 1.5)
        t3 = entry_price * (1.0 + (stop_pct / 100.0) * rr_ratio * 2.2)
        
        t1_profit = lots * (t1 - entry_price)
        t2_profit = lots * (t2 - entry_price)
        t3_profit = lots * (t3 - entry_price)
        
        # Render Metrics Grid
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Alınacak Lot Adedi", f"{lots:,} lot", f"${(entry_price / usd_rate * lots):,.2f} USD")
            st.metric("Pozisyon Büyüklüğü (TRY)", f"₺{position_try:,.2f}", f"Portföyün %{position_try / capital * 100.0:.1f}'i")
        with col_m2:
            st.metric("Maksimum Risk Tutarı", f"-₺{actual_risk:,.2f}", f"Portföyün %{actual_risk / capital * 100.0:.2f}'si", delta_color="inverse")
            st.metric("Stop-Loss Fiyatı", f"₺{stop_price:,.2f}", f"${stop_price / usd_rate:.4f} USD", delta_color="inverse")
        with col_m3:
            st.metric("Hedef T1 Fiyatı", f"₺{t1:,.2f}", f"${t1 / usd_rate:.4f} USD")
            st.metric("Hedef T2 Fiyatı", f"₺{t2:,.2f}", f"${t2 / usd_rate:.4f} USD")
            
        st.markdown("---")
        
        # Risk Meter segment visualization
        st.markdown("**Risk Derecesi Göstergesi**")
        risk_ratio_norm = min(risk_pct / 15.0, 0.98) # Normalize for CSS mapping
        
        # Segment bars
        st.markdown(f"""
        <div class="risk-bar">
            <div class="risk-segment" style="background-color: #10d98a;"></div>
            <div class="risk-segment" style="background-color: #f59e0b;"></div>
            <div class="risk-segment" style="background-color: #ff4d6a;"></div>
        </div>
        <div class="risk-indicator-container">
            <div class="risk-indicator-needle" style="left: {risk_ratio_norm * 100:.1f}%;"></div>
        </div>
        """, unsafe_allow_html=True)
        
        # Math Expectation Analysis
        expected_win = t1_profit * 0.5 + t2_profit * 0.5
        expected_loss = actual_risk
        ev = 0.55 * expected_win - 0.45 * expected_loss
        ev_monthly = ev * 2
        
        st.write("### 📈 Matematiksel Beklenti (Backtest: %55 Kazanma Oranı)")
        col_ev1, col_ev2 = st.columns(2)
        with col_ev1:
            ev_color = "green" if ev >= 0 else "red"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">1 İşlem Beklenen Değeri (EV)</div>
                <div class="metric-value {ev_color}">{'L' if ev < 0 else ''}₺{ev:,.2f}</div>
                <div style="font-size:0.75rem; color:#64748b;">Formül: 55% x (+₺{expected_win:,.0f}) - 45% x (-₺{expected_loss:,.0f})</div>
            </div>
            """, unsafe_allow_html=True)
        with col_ev2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Aylık Ortalama Beklenti (2 İşlem)</div>
                <div class="metric-value {ev_color}">{'L' if ev_monthly < 0 else ''}₺{ev_monthly:,.2f}</div>
                <div style="font-size:0.75rem; color:#64748b;">Sermaye Büyümesi: {'+' if ev_monthly >= 0 else ''}{ev_monthly / capital * 100:.2f}% / ay</div>
            </div>
            """, unsafe_allow_html=True)

        # Scenarios Table
        st.write("### 📊 Senaryo Analiz Tablosu (P&L)")
        scenarios_data = [
            {"Senaryo": "🔴 Stop-Loss Tetiklendi", "Fiyat (TRY)": f"₺{stop_price:,.2f}", "Net Kar/Zarar ₺": f"-₺{actual_risk:,.2f}", "Hisse Değişimi %": f"-{stop_pct:.1f}%", "Portföy Etkisi %": f"-{actual_risk / capital * 100:.2f}%"},
            {"Senaryo": "⚡ T1 Hedefi (%50 Çıkış)", "Fiyat (TRY)": f"₺{t1:,.2f}", "Net Kar/Zarar ₺": f"+₺{t1_profit*0.5:,.2f}", "Hisse Değişimi %": f"+{(t1 / entry_price - 1.0) * 100.0:.1f}%", "Portföy Etkisi %": f"+{(t1_profit * 0.5) / capital * 100:.2f}%"},
            {"Senaryo": "🎯 T1 Hedefi (Tam Çıkış)", "Fiyat (TRY)": f"₺{t1:,.2f}", "Net Kar/Zarar ₺": f"+₺{t1_profit:,.2f}", "Hisse Değişimi %": f"+{(t1 / entry_price - 1.0) * 100.0:.1f}%", "Portföy Etkisi %": f"+{t1_profit / capital * 100:.2f}%"},
            {"Senaryo": "🎯 T2 Hedefi (Tam Çıkış)", "Fiyat (TRY)": f"₺{t2:,.2f}", "Net Kar/Zarar ₺": f"+₺{t2_profit:,.2f}", "Hisse Değişimi %": f"+{(t2 / entry_price - 1.0) * 100.0:.1f}%", "Portföy Etkisi %": f"+{t2_profit / capital * 100:.2f}%"},
            {"Senaryo": "🏆 T3 Hedefi (Tam Çıkış)", "Fiyat (TRY)": f"₺{t3:,.2f}", "Net Kar/Zarar ₺": f"+₺{t3_profit:,.2f}", "Hisse Değişimi %": f"+{(t3 / entry_price - 1.0) * 100.0:.1f}%", "Portföy Etkisi %": f"+{t3_profit / capital * 100:.2f}%"},
            {"Senaryo": "⏱️ Zaman Stopu (Yatay Karar)", "Fiyat (TRY)": f"₺{entry_price:,.2f}", "Net Kar/Zarar ₺": "₺0.00", "Hisse Değişimi %": "0.0%", "Portföy Etkisi %": "0.00%"}
        ]
        st.table(pd.DataFrame(scenarios_data))

        # Trading rules
        st.write("### 📋 Otomatik İşlem Kuralları")
        half_lots = math.floor(lots / 2)
        st.markdown(f"""
        <div class="rules-card">
            <div class="rule-title" style="color: #ff4d6a;">🚫 STOP-LOSS SEVİYESİ → ₺{stop_price:,.2f} (${stop_price / usd_rate:.4f})</div>
            <div style="font-size:0.85rem; color:#64748b;">Fiyat bu seviyeye değerse beklemeden çıkın. Maksimum zarar: -₺{actual_risk:,.2f} (%{actual_risk / capital * 100:.2f} portföy kaybı)</div>
            
            <div class="rule-title" style="color: #10d98a;">🎯 T1 KISMİ ÇIKIŞ HEDEFİ → ₺{t1:,.2f} (+%{(t1 / entry_price - 1) * 100:.1f})</div>
            <div style="font-size:0.85rem; color:#64748b;">Fiyat T1'e ulaşırsa lotların yarısını ({half_lots} lot) satın. Kalan lotların stop seviyesini maliyete (₺{entry_price:,.2f}) taşıyın. İşlem artık risksizdir.</div>
            
            <div class="rule-title" style="color: #10d98a;">🏁 T2 TAM HEDEF HEDEFİ → ₺{t2:,.2f} (+%{(t2 / entry_price - 1) * 100:.1f})</div>
            <div style="font-size:0.85rem; color:#64748b;">Fiyat T2'ye ulaştığında kalan lotların tamamını kapatın. Toplam net karınız: +₺{t1_profit * 0.5 + t2_profit * 0.5:,.2f} olacaktır.</div>
            
            <div class="rule-title" style="color: #f59e0b;">⏱️ ZAMAN STOPU KURALI → 20 İşlem Günü</div>
            <div style="font-size:0.85rem; color:#64748b;">Eğer 20 işlem günü geçmesine rağmen hedefler veya stop seviyesi tetiklenmediyse işlemden manuel çıkın.</div>
        </div>
        """, unsafe_allow_html=True)

# --- FOOTER ---
st.markdown("---")
st.markdown("<p style='text-align: center; color: #64748b; font-size: 0.8rem;'>⚠️ Yatırım Tavsiyesi Değildir. Veriler Yahoo Finance üzerinden gecikmeli veya eksik gelebilir.</p>", unsafe_allow_html=True)
