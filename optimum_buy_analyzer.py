"""
Optimum Alım Noktası ve Teknik Analiz Optimizasyon Algoritması
=============================================================
Bu modül, geçmiş veriler üzerinde simülasyon (backtest) koşturarak,
en iyi getiri ve risk yönetimi sağlayan teknik gösterge parametrelerini
ve ağırlıklarını bulan bir Grid Search optimizasyon motoru içerir.
"""

import os
import sys
import math
import time
import argparse
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests

# UTF-8 ayarı (Türkçe karakterlerin komut satırında düzgün görünmesi için)
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ─────────────────────────────────────────────────────────
# VERİ ÇEKME YARDIMCILARI
# ─────────────────────────────────────────────────────────

def download_stock_data(symbol: str, start_str: str, end_str: str) -> pd.DataFrame:
    """
    Yahoo Finance API'den belirtilen tarih aralığındaki veriyi çeker.
    """
    try:
        start_ts = int(time.mktime(time.strptime(start_str, "%Y-%m-%d")))
        end_ts   = int(time.mktime(time.strptime(end_str, "%Y-%m-%d")))
    except Exception as e:
        print(f"Tarih dönüştürme hatası: {e}")
        return pd.DataFrame()

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"period1": start_ts, "period2": end_ts, "interval": "1d"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return pd.DataFrame()
        
        res = result[0]
        timestamps = res.get("timestamp", [])
        indicators = res.get("indicators", {}).get("quote", [{}])[0]
        
        closes = indicators.get("close", [])
        opens  = indicators.get("open", [])
        highs  = indicators.get("high", [])
        lows   = indicators.get("low", [])
        volumes = indicators.get("volume", [])
        
        df = pd.DataFrame({
            "Open": opens, "High": highs, "Low": lows, 
            "Close": closes, "Volume": volumes
        }, index=pd.to_datetime(timestamps, unit="s"))
        
        # Eksik verileri doldur
        df = df.ffill().bfill()
        return df
    except Exception as e:
        print(f"{symbol} için veri çekme hatası: {e}")
        return pd.DataFrame()

# ─────────────────────────────────────────────────────────
# TEKNİK GÖSTERGE HESAPLAMALARI
# ─────────────────────────────────────────────────────────

class IndicatorCalculator:
    @staticmethod
    def calculate_atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
        h, l, c = df['High'], df['Low'], df['Close']
        tr = pd.concat([
            h - l,
            (h - c.shift(1)).abs(),
            (l - c.shift(1)).abs()
        ], axis=1).max(axis=1)
        return tr.rolling(n).mean()

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, n: int = 14) -> pd.Series:
        delta = df['Close'].diff()
        gain = (delta.clip(lower=0)).rolling(n).mean()
        loss = (-delta.clip(upper=0)).rolling(n).mean()
        rs = gain / (loss + 1e-9)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast=12, slow=26, signal=9):
        c = df['Close']
        ema_fast = c.ewm(span=fast, adjust=False).mean()
        ema_slow = c.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        macd_hist = macd_line - signal_line
        return macd_line, signal_line, macd_hist

    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, n=20, num_std=2):
        c = df['Close']
        middle = c.rolling(n).mean()
        std = c.rolling(n).std()
        upper = middle + num_std * std
        lower = middle - num_std * std
        return upper, middle, lower

    @staticmethod
    def find_pivot_lows(df: pd.DataFrame, window: int = 20) -> list:
        """
        Yerel dip noktalarını (pivot lows) bulur.
        Dönen liste formatı: (tarih, dip_fiyat)
        """
        lows = df['Low'].values
        dates = df.index
        n = len(lows)
        pivots = []
        for i in range(window, n - window):
            seg = lows[i - window : i + window + 1]
            if lows[i] == seg.min() and lows[i] > 0:
                pivots.append((dates[i], float(lows[i])))
        return pivots

    @staticmethod
    def cluster_support_zones(pivots: list, tolerance: float = 0.03) -> list:
        """
        Fiyat bazında yakın olan pivot dipleri gruplayarak güçlü destek seviyeleri oluşturur.
        """
        if not pivots:
            return []
        # Fiyata göre sırala
        sorted_pivots = sorted(pivots, key=lambda x: x[1])
        zones = []
        current_group = [sorted_pivots[0]]
        
        for date, price in sorted_pivots[1:]:
            ref = current_group[0][1]
            if ref > 0 and (price - ref) / ref <= tolerance:
                current_group.append((date, price))
            else:
                avg = sum(p for _, p in current_group) / len(current_group)
                last_dt = max(d for d, _ in current_group)
                zones.append({"price": avg, "touches": len(current_group), "last_date": last_dt})
                current_group = [(date, price)]
                
        avg = sum(p for _, p in current_group) / len(current_group)
        last_dt = max(d for d, _ in current_group)
        zones.append({"price": avg, "touches": len(current_group), "last_date": last_dt})
        return zones

    @staticmethod
    def get_volume_profile_supports(df: pd.DataFrame, bins: int = 20) -> list:
        """
        En yüksek hacmin gerçekleştiği fiyat bantlarını bularak yatay destek alanları belirler.
        """
        if len(df) < bins:
            return []
        l = df['Low'].min()
        h = df['High'].max()
        if h == l:
            return []
        price_range = np.linspace(l, h, bins + 1)
        vol_per_bin = []
        
        for i in range(bins):
            mask = (df['Close'] >= price_range[i]) & (df['Close'] < price_range[i+1])
            vol_per_bin.append(df['Volume'][mask].sum())
            
        # En yüksek hacimli ilk 3 bandın orta fiyatını al
        top_indices = np.argsort(vol_per_bin)[::-1][:3]
        supports = []
        for idx in top_indices:
            mid_val = (price_range[idx] + price_range[idx+1]) / 2.0
            supports.append(mid_val)
        return sorted(supports)

# ─────────────────────────────────────────────────────────
# SKORLAMA VE SİNYAL MOTORU
# ─────────────────────────────────────────────────────────

def calculate_technical_score(row: pd.Series, prev_row: pd.Series, nearest_support: float, 
                              w_sup: float, w_rsi: float, w_macd: float, w_bb: float, w_ema: float) -> dict:
    """
    Tek bir satır (gün) için teknik birleşik skoru (0-100) hesaplar.
    """
    c = row['Close']
    
    # 1. Destek Yakınlık Skoru (Destek altındaysa 0, tam üzerindeyse 100, %5 uzaklaştıkça azalır)
    score_sup = 0.0
    if nearest_support is not None and nearest_support > 0:
        if c >= nearest_support:
            dist_pct = (c - nearest_support) / nearest_support
            score_sup = max(0.0, 100.0 - dist_pct * 2000.0)  # %5 uzaklıkta (0.05) 0 puan olur (0.05 * 2000 = 100)
        else:
            # Desteğin altına sarkmışsa (Kırılım veya Ayı Tuzağı)
            score_sup = 0.0
            
    # 2. RSI Skoru (Aşırı satım ve toparlanma)
    rsi_val = row['RSI']
    score_rsi = 0.0
    if rsi_val <= 30:
        score_rsi = 100.0  # Aşırı satım
    elif rsi_val <= 45:
        score_rsi = 100.0 - (rsi_val - 30) * 5.0  # Lineer azalan (30'da 100, 45'te 25)
    elif rsi_val <= 65:
        score_rsi = 25.0
    else:
        score_rsi = 0.0  # Aşırı alım yaklaşımı
        
    # 3. MACD Skoru (Momentum ve kesişim)
    score_macd = 0.0
    macd_hist = row['MACD_Hist']
    prev_macd_hist = prev_row['MACD_Hist'] if prev_row is not None else 0.0
    
    if macd_hist > 0:
        if macd_hist > prev_macd_hist:
            score_macd = 100.0  # Pozitif bölgede artan momentum
        else:
            score_macd = 70.0   # Pozitif bölgede azalan momentum
    else:
        if macd_hist > prev_macd_hist:
            score_macd = 50.0   # Negatif bölgede yukarı dönüş emaresi
        else:
            score_macd = 10.0   # Negatif bölgede derinleşen düşüş
            
    # 4. Bollinger Bandı Skoru (Alt banda yakınlık)
    score_bb = 0.0
    bb_upper = row['BB_Upper']
    bb_lower = row['BB_Lower']
    if bb_upper > bb_lower:
        pct_bb = (c - bb_lower) / (bb_upper - bb_lower)
        if pct_bb <= 0.1:
            score_bb = 100.0  # Alt bandın hemen üstünde veya altında
        elif pct_bb <= 0.5:
            score_bb = 100.0 - (pct_bb - 0.1) * 200.0  # Lineer azalan (0.1'de 100, 0.5'te 20)
        else:
            score_bb = 10.0
            
    # 5. EMA Trend Skoru (Uzun vadeli trend yönü)
    score_ema = 0.0
    ema200 = row['EMA200']
    if ema200 > 0:
        if c > ema200:
            score_ema = 100.0  # Yükselen trend üzerinde
        else:
            score_ema = 30.0   # Düşen trend altında (Riskli)
            
    # Ağırlıklı Toplam
    total_weight = w_sup + w_rsi + w_macd + w_bb + w_ema
    if total_weight <= 0:
        composite = 50.0
    else:
        composite = (
            w_sup * score_sup +
            w_rsi * score_rsi +
            w_macd * score_macd +
            w_bb * score_bb +
            w_ema * score_ema
        ) / total_weight
        
    return {
        "composite": composite,
        "score_sup": score_sup,
        "score_rsi": score_rsi,
        "score_macd": score_macd,
        "score_bb": score_bb,
        "score_ema": score_ema
    }

# ─────────────────────────────────────────────────────────
# BACKTEST SİMÜLASYONU
# ─────────────────────────────────────────────────────────

def run_backtest(df: pd.DataFrame, pivots: list, params: dict) -> dict:
    """
    Belirli parametreler ile geçmiş veride işlem simülasyonu çalıştırır.
    Look-ahead bias'ı engellemek için sadece geçmiş pivotları kullanır.
    """
    # Parametreleri al
    w_sup = params.get("w_support", 0.5)
    w_rsi = params.get("w_rsi", 0.15)
    w_macd = params.get("w_macd", 0.15)
    w_bb = params.get("w_bb", 0.1)
    w_ema = params.get("w_ema", 0.1)
    buy_threshold = params.get("buy_threshold", 60.0)
    sl_atr_mult = params.get("sl_atr", 2.0)
    tp_atr_mult = params.get("tp_atr", 3.0)
    max_hold_days = params.get("max_hold_days", 20)
    pivot_window = params.get("pivot_window", 20)
    support_tolerance = params.get("support_tolerance", 0.03)

    in_position = False
    entry_price = 0.0
    entry_idx = 0
    entry_atr = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    hold_days = 0
    
    trades = []
    daily_returns = []
    
    closes = df['Close'].values
    highs = df['High'].values
    lows = df['Low'].values
    dates = df.index
    n = len(df)
    
    # Skorları doldurmak için boş listeler
    composite_scores = []
    
    for i in range(n):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1] if i > 0 else None
        curr_date = dates[i]
        
        # 1. Look-ahead bias engelleme: Sadece 'i - pivot_window' tarihine kadar olan pivotları al.
        # Çünkü bir pivot low ancak pivot_window gün geçtikten sonra teyit edilir.
        limit_date = curr_date - timedelta(days=pivot_window)
        past_pivots = [p for p in pivots if p[0] <= limit_date]
        
        # Destek gruplarını hesapla
        zones = IndicatorCalculator.cluster_support_zones(past_pivots, tolerance=support_tolerance)
        
        # En yakın desteği bul (fiyatın altındaki en yakın destek)
        curr_close = closes[i]
        supports_below = [z for z in zones if z["price"] <= curr_close]
        nearest_support = None
        if supports_below:
            nearest_support = min(supports_below, key=lambda z: curr_close - z["price"])["price"]
            
        # Teknik skoru hesapla
        score_res = calculate_technical_score(
            row, prev_row, nearest_support, 
            w_sup, w_rsi, w_macd, w_bb, w_ema
        )
        score = score_res["composite"]
        composite_scores.append(score)
        
        # 2. İşlem Simülasyonu Mantığı
        if not in_position:
            daily_returns.append(0.0)
            # Alım sinyali kontrolü (skor eşiği aşıldıysa ve ATR pozitifse)
            if score >= buy_threshold and row['ATR'] > 0:
                in_position = True
                entry_price = curr_close
                entry_idx = i
                entry_atr = row['ATR']
                stop_loss = entry_price - sl_atr_mult * entry_atr
                take_profit = entry_price + tp_atr_mult * entry_atr
                hold_days = 0
        else:
            hold_days += 1
            # Günlük getiri hesaplama (pozisyondayken)
            day_ret = (curr_close - closes[i - 1]) / closes[i - 1]
            daily_returns.append(day_ret)
            
            # Çıkış Koşulları
            # A. Stop Loss
            if lows[i] <= stop_loss:
                exit_price = min(row['Open'], stop_loss)
                pnl_pct = (exit_price - entry_price) / entry_price
                trades.append({
                    "entry_date": dates[entry_idx],
                    "exit_date": curr_date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": pnl_pct,
                    "type": "STOP_LOSS",
                    "hold_days": hold_days
                })
                in_position = False
            # B. Take Profit
            elif highs[i] >= take_profit:
                exit_price = max(row['Open'], take_profit)
                pnl_pct = (exit_price - entry_price) / entry_price
                trades.append({
                    "entry_date": dates[entry_idx],
                    "exit_date": curr_date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": pnl_pct,
                    "type": "TAKE_PROFIT",
                    "hold_days": hold_days
                })
                in_position = False
            # C. Maksimum Süre Sonu Çıkış
            elif hold_days >= max_hold_days:
                exit_price = curr_close
                pnl_pct = (exit_price - entry_price) / entry_price
                trades.append({
                    "entry_date": dates[entry_idx],
                    "exit_date": curr_date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": pnl_pct,
                    "type": "TIME_EXIT",
                    "hold_days": hold_days
                })
                in_position = False
                
    # Metrik Hesaplamaları
    df_result = df.copy()
    df_result['Score'] = composite_scores
    
    total_return = 0.0
    win_rate = 0.0
    profit_factor = 1.0
    max_dd = 0.0
    sharpe = 0.0
    
    if trades:
        # Kümülatif Getiri
        trade_returns = [t["pnl_pct"] for t in trades]
        cumulative = 1.0
        for r in trade_returns:
            cumulative *= (1.0 + r)
        total_return = (cumulative - 1.0) * 100.0
        
        # Win Rate
        wins = sum(1 for t in trades if t["pnl_pct"] > 0)
        win_rate = (wins / len(trades)) * 100.0
        
        # Profit Factor
        gross_profits = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0)
        gross_losses = sum(abs(t["pnl_pct"]) for t in trades if t["pnl_pct"] < 0)
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else (gross_profits * 10.0 if gross_profits > 0 else 1.0)
        
        # Max Drawdown
        equity_curve = [1.0]
        for r in trade_returns:
            equity_curve.append(equity_curve[-1] * (1.0 + r))
        eq_arr = np.array(equity_curve)
        cum_max = np.maximum.accumulate(eq_arr)
        drawdowns = (eq_arr - cum_max) / cum_max
        max_dd = abs(drawdowns.min()) * 100.0
        
        # Sharpe Ratio (Basit günlük volatilite bazlı Sharpe)
        daily_returns_arr = np.array(daily_returns)
        mean_ret = daily_returns_arr.mean()
        std_ret = daily_returns_arr.std()
        if std_ret > 0:
            sharpe = (mean_ret / std_ret) * math.sqrt(252)
        else:
            sharpe = 0.0
            
    return {
        "trades": trades,
        "total_return": total_return,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "df_scored": df_result
    }

# ─────────────────────────────────────────────────────────
# OPTİMİZASYON MOTORU
# ─────────────────────────────────────────────────────────

class StrategyOptimizer:
    @staticmethod
    def optimize(df: pd.DataFrame, pivots: list, show_progress: bool = True) -> tuple:
        """
        Geçmiş veride en iyi sonucu veren parametre setini bulur.
        Ağırlıklar, Skor eşikleri, SL ve TP çarpanları Grid Search ile taranır.
        """
        # Optimize edilecek grid parametreleri (Hızlı arama için kompakt tutulmuştur)
        grid_w_sup = [0.4, 0.6]
        grid_w_rsi = [0.15, 0.25]
        grid_w_macd = [0.15, 0.2]
        grid_buy_threshold = [60.0, 65.0]
        grid_sl = [1.5, 2.0]
        grid_tp = [2.5, 3.5]
        
        best_metric = -999.0
        best_params = None
        best_metrics_results = {}
        
        total_comb = len(grid_w_sup) * len(grid_w_rsi) * len(grid_w_macd) * len(grid_buy_threshold) * len(grid_sl) * len(grid_tp)
        count = 0
        
        if show_progress:
            print(f"Optimizasyon başladı. Toplam kombinasyon: {total_comb}")
            
        for w_sup in grid_w_sup:
            for w_rsi in grid_w_rsi:
                for w_macd in grid_w_macd:
                    # Kalan ağırlıklar dengelenir
                    rem = 1.0 - (w_sup + w_rsi + w_macd)
                    if rem < 0:
                        continue
                    w_bb = rem * 0.5
                    w_ema = rem * 0.5
                    
                    for buy_th in grid_buy_threshold:
                        for sl in grid_sl:
                            for tp in grid_tp:
                                count += 1
                                if show_progress and count % 50 == 0:
                                    print(f"Kombinasyon {count}/{total_comb} taranıyor...")
                                    
                                test_params = {
                                    "w_support": w_sup,
                                    "w_rsi": w_rsi,
                                    "w_macd": w_macd,
                                    "w_bb": w_bb,
                                    "w_ema": w_ema,
                                    "buy_threshold": buy_th,
                                    "sl_atr": sl,
                                    "tp_atr": tp,
                                    "max_hold_days": 20,
                                    "pivot_window": 20,
                                    "support_tolerance": 0.03
                                }
                                
                                bt = run_backtest(df, pivots, test_params)
                                num_trades = len(bt["trades"])
                                
                                # Performans Skoru Formülü: Sharpe * Win Rate * (1 - DD)
                                # Az sayıda işlem açan uç stratejileri cezalandır
                                if num_trades < 4:
                                    perf_score = -50.0 + num_trades
                                else:
                                    perf_score = bt["sharpe"] * 10.0 + bt["total_return"] * 0.1 - bt["max_drawdown"] * 0.2
                                    
                                if perf_score > best_metric:
                                    best_metric = perf_score
                                    best_params = test_params
                                    best_metrics_results = {
                                        "total_return": bt["total_return"],
                                        "win_rate": bt["win_rate"],
                                        "profit_factor": bt["profit_factor"],
                                        "max_drawdown": bt["max_drawdown"],
                                        "sharpe": bt["sharpe"],
                                        "trades_count": num_trades
                                    }
                                    
        return best_params, best_metrics_results

# ─────────────────────────────────────────────────────────
# RAPOR VE CLI ARAYÜZÜ
# ─────────────────────────────────────────────────────────

def run_analysis_for_ticker(ticker: str, start_date: str, end_date: str) -> dict:
    """
    Belirli bir hisse için tüm veri indirme, gösterge hesaplama,
    optimizasyon ve güncel analiz adımlarını gerçekleştirir.
    """
    print(f"\n[+] {ticker} için 5 yıllık tarihsel veriler indiriliyor...")
    
    # 5 Yıllık Veri Çek (Optimizasyon ve destek bölgesi tespiti için geniş veri)
    df = download_stock_data(ticker, start_date, end_date)
    if df.empty or len(df) < 200:
        print(f"[!] {ticker} için yeterli veri indirilemedi.")
        return {}
        
    print(f"[+] Göstergeler hesaplanıyor (RSI, MACD, BB, ATR)...")
    # Göstergeleri hesapla
    df['ATR'] = IndicatorCalculator.calculate_atr(df, 14)
    df['RSI'] = IndicatorCalculator.calculate_rsi(df, 14)
    macd_l, macd_s, macd_h = IndicatorCalculator.calculate_macd(df)
    df['MACD'] = macd_l
    df['MACD_Signal'] = macd_s
    df['MACD_Hist'] = macd_h
    bb_u, bb_m, bb_l = IndicatorCalculator.calculate_bollinger_bands(df)
    df['BB_Upper'] = bb_u
    df['BB_Middle'] = bb_m
    df['BB_Lower'] = bb_l
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    df = df.dropna()
    if len(df) < 100:
        return {}
        
    print(f"[+] Tarihsel pivot dipleri tespit ediliyor...")
    pivots = IndicatorCalculator.find_pivot_lows(df, window=20)
    
    # Son 1 yıllık alt kümede optimizasyonu çalıştır (hız ve güncellik açısından)
    df_opt = df.iloc[-500:] if len(df) >= 500 else df
    best_params, opt_results = StrategyOptimizer.optimize(df_opt, pivots, show_progress=False)
    
    if not best_params:
        print("[!] Optimizasyon başarısız oldu.")
        return {}
        
    # En iyi parametrelerle tüm veri setini skorla
    bt_res = run_backtest(df, pivots, best_params)
    df_scored = bt_res["df_scored"]
    
    # En son satır (bugünün verisi)
    last_row = df_scored.iloc[-1]
    prev_row = df_scored.iloc[-2]
    now_dt = df_scored.index[-1]
    
    # Güncel destek bölgeleri ve en yakın destek
    curr_close = float(last_row['Close'])
    all_zones = IndicatorCalculator.cluster_support_zones(pivots, tolerance=best_params["support_tolerance"])
    supports_below = [z for z in all_zones if z["price"] <= curr_close]
    
    nearest_sup = None
    if supports_below:
        nearest_sup = min(supports_below, key=lambda z: curr_close - z["price"])["price"]
        
    # Hacim Profili Destekleri
    vol_sups = IndicatorCalculator.get_volume_profile_supports(df.iloc[-100:])
    
    # Alım bölgesi hesabı: En yakın destek ile onun 0.5 ATR yukarısı
    atr_val = float(last_row['ATR'])
    if nearest_sup is not None:
        buy_zone_low = nearest_sup
        buy_zone_high = nearest_sup + 0.5 * atr_val
    else:
        buy_zone_low = curr_close * 0.95
        buy_zone_high = curr_close * 0.97
        
    # Anlık Sinyal Belirleme İçin Gerekli Değişkenler
    score = float(last_row['Score'])
    buy_threshold = best_params["buy_threshold"]
    rsi_val = float(last_row['RSI'])

    # Kar-Al (TP) ve Zarar-Durdur (SL)
    # Sinyal varsa anlık fiyat, yoksa optimum alım bölgesi üst sınırı referans alınır.
    entry_ref = curr_close if score >= buy_threshold else buy_zone_high
    
    sl_val = entry_ref - best_params["sl_atr"] * atr_val
    tp_1 = entry_ref + best_params["tp_atr"] * 0.5 * atr_val
    tp_2 = entry_ref + best_params["tp_atr"] * atr_val
    
    if score >= buy_threshold:
        signal = "ALIM SİNYALİ"
        desc = f"Birleşik Teknik Skor ({score:.1f}) kritik eşiği ({buy_threshold}) aştı. Fiyat güçlü destek alanına yakın ve momentum pozitif."
    elif curr_close >= buy_zone_low and curr_close <= buy_zone_high:
        signal = "ALIM BÖLGESİNDE (ONAY BEKLENİYOR)"
        desc = f"Fiyat optimum alım bölgesinde [₺{buy_zone_low:.2f} - ₺{buy_zone_high:.2f}], ancak birleşik skor ({score:.1f}) henüz tetiği ({buy_threshold}) vermedi."
    elif rsi_val < 33:
        signal = "AŞIRI SATIMDA (İZLEMEDE)"
        desc = f"RSI ({rsi_val:.1f}) aşırı satım bölgesinde. Düşüşün durulması ve destekten dönüş beklenmeli."
    else:
        signal = "BEKLE / NÖTR"
        desc = f"Birleşik teknik skor {score:.1f} (Eşik: {buy_threshold}). Fiyat destekten uzak veya yükseliş momentumu yetersiz."
        
    return {
        "ticker": ticker,
        "close": curr_close,
        "date": now_dt,
        "atr": atr_val,
        "score": score,
        "signal": signal,
        "description": desc,
        "best_params": best_params,
        "opt_metrics": opt_results,
        "nearest_support": nearest_sup,
        "all_supports": all_zones,
        "vol_supports": vol_sups,
        "buy_zone": (buy_zone_low, buy_zone_high),
        "stop_loss": sl_val,
        "take_profit_t1": tp_1,
        "take_profit_t2": tp_2,
        "df_scored": df_scored
    }

def print_cli_report(res: dict):
    if not res:
        print("[!] Rapor oluşturulamadı.")
        return
        
    print("\n" + "="*70)
    print(f" 🎯 TEKNİK ANALİZ VE OPTİMİZASYON RAPORU: {res['ticker']} ")
    print("="*70)
    print(f" Son Fiyat       : ₺{res['close']:.2f}")
    print(f" Güncel Tarih    : {res['date'].strftime('%Y-%m-%d')}")
    print(f" Güncel Sinyal   : {res['signal']}")
    print(f" Açıklama        : {res['description']}")
    print("-" * 70)
    
    print(" 🛠️ TARİHSEL OPTİMİZASYON PARAMETRELERİ (EN İYİ KOŞULLAR)")
    bp = res['best_params']
    print(f"  - Destek Ağırlığı     : %{bp['w_support']*100:.0f}")
    print(f"  - RSI / MACD Ağırlığı : %{bp['w_rsi']*100:.0f} / %{bp['w_macd']*100:.0f}")
    print(f"  - Bollinger Ağırlığı  : %{bp['w_bb']*100:.0f}")
    print(f"  - EMA Ağırlığı        : %{bp['w_ema']*100:.0f}")
    print(f"  - Alım Skor Eşiği     : {bp['buy_threshold']:.1f}")
    print(f"  - SL / TP Çarpanı     : {bp['sl_atr']:.1f}x ATR / {bp['tp_atr']:.1f}x ATR")
    print("-" * 70)
    
    print(" 📈 OPTİMİZE EDİLMİŞ STRATEJİ BACKTEST METRİKLERİ")
    om = res['opt_metrics']
    print(f"  - Toplam Getiri       : %{om['total_return']:.1f}")
    print(f"  - İşlem Başarı Oranı  : %{om['win_rate']:.1f}")
    print(f"  - Kar Faktörü (PF)    : {om['profit_factor']:.2f}")
    print(f"  - Maks. Drawdown      : %{om['max_drawdown']:.1f}")
    print(f"  - Sharpe Oranı        : {om['sharpe']:.2f}")
    print(f"  - Toplam İşlem Sayısı : {om['trades_count']}")
    print("-" * 70)
    
    print(" 🛒 OPTİMUM ALIM NOKTALARI VE HEDEFLER")
    bz = res['buy_zone']
    print(f"  - Optimum Alım Bölgesi: ₺{bz[0]:.2f} - ₺{bz[1]:.2f}")
    print(f"  - Zarar Durdur (SL)   : ₺{res['stop_loss']:.2f}")
    print(f"  - Hedef T1 (Kısa)     : ₺{res['take_profit_t1']:.2f}")
    print(f"  - Hedef T2 (Orta/Uzun): ₺{res['take_profit_t2']:.2f}")
    if res['nearest_support']:
        print(f"  - En Yakın Güçlü Dip  : ₺{res['nearest_support']:.2f}")
    print("="*70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimum Alım Noktası Belirleyici CLI")
    parser.add_argument("--ticker", type=str, default="THYAO.IS", help="Hisse Kodu (örn: EREGL.IS, THYAO.IS)")
    parser.add_argument("--years", type=int, default=5, help="Kaç yıllık veri analizi yapılacak?")
    parser.add_argument("--test", action="store_true", help="Test modunda çalıştır")
    
    args = parser.parse_args()
    
    # Tarih aralığını belirle
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=args.years * 365)).strftime("%Y-%m-%d")
    
    ticker_name = args.ticker
    if not ticker_name.endswith(".IS") and ticker_name != "USDTRY=X":
        ticker_name += ".IS"
        
    analysis_res = run_analysis_for_ticker(ticker_name, start_date, end_date)
    print_cli_report(analysis_res)
