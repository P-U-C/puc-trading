#!/usr/bin/env python3
"""
Live IBKR Options Scanner — Convergence-Weighted
Connects to IB Gateway, scans options chains for HIGH-convergence tickers,
scores by asymmetry, exports dashboard JSON + sends Telegram alert.
"""

import json, os, math, time
from datetime import datetime, timezone, timedelta
from ib_insync import IB, Stock, Option

# -- Config --
IBKR_PORT = int(os.environ.get("IBKR_PORT", "4002"))
OUTPUT_JSON = os.path.expanduser("~/pft-validator/scanner/scan-results.json")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "505841972")
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() != "false"

# -- Convergence Data (from seed corpus) --
CONVERGENCE = [
    # AI Infrastructure
    {"ticker": "NVDA", "theme": "AI Infrastructure", "score": 0.800, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "AVGO", "theme": "AI Infrastructure", "score": 0.620, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "VRT",  "theme": "AI Infrastructure", "score": 0.496, "tier": "MEDIUM", "status": "peak_hype"},
    {"ticker": "ANET", "theme": "AI Infrastructure", "score": 0.269, "tier": "LOW", "status": "peak_hype"},
    {"ticker": "MU",   "theme": "AI Infrastructure", "score": 0.260, "tier": "LOW", "status": "peak_hype"},
    {"ticker": "TSM",  "theme": "AI Infrastructure", "score": 0.250, "tier": "LOW", "status": "peak_hype"},
    {"ticker": "DELL", "theme": "AI Infrastructure", "score": 0.200, "tier": "LOW", "status": "peak_hype"},
    # GLP-1 / Peptides
    {"ticker": "LLY",  "theme": "GLP-1 / Peptides", "score": 0.800, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "NVO",  "theme": "GLP-1 / Peptides", "score": 0.680, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "VKTX", "theme": "GLP-1 / Peptides", "score": 0.509, "tier": "MEDIUM", "status": "peak_hype"},
    {"ticker": "AMGN", "theme": "GLP-1 / Peptides", "score": 0.350, "tier": "MEDIUM", "status": "peak_hype"},
    {"ticker": "GPCR", "theme": "GLP-1 / Peptides", "score": 0.250, "tier": "LOW", "status": "growing"},
    # Quantum Computing
    {"ticker": "IONQ", "theme": "Quantum Computing", "score": 0.733, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "QBTS", "theme": "Quantum Computing", "score": 0.600, "tier": "HIGH", "status": "peak_hype"},
    {"ticker": "RGTI", "theme": "Quantum Computing", "score": 0.589, "tier": "MEDIUM", "status": "peak_hype"},
    # Nuclear / SMR
    {"ticker": "BWXT", "theme": "Nuclear / SMR", "score": 0.600, "tier": "HIGH", "status": "growing"},
    {"ticker": "OKLO", "theme": "Nuclear / SMR", "score": 0.541, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "SMR",  "theme": "Nuclear / SMR", "score": 0.514, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "GEV",  "theme": "Nuclear / SMR", "score": 0.465, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "CEG",  "theme": "Nuclear / SMR", "score": 0.400, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "CCJ",  "theme": "Nuclear / SMR", "score": 0.300, "tier": "LOW", "status": "growing"},
    {"ticker": "LEU",  "theme": "Nuclear / SMR", "score": 0.250, "tier": "LOW", "status": "growing"},
    # Robotics / Humanoid
    {"ticker": "TSLA", "theme": "Robotics / Humanoid", "score": 0.500, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "ISRG", "theme": "Robotics / Humanoid", "score": 0.400, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "SYM",  "theme": "Robotics / Humanoid", "score": 0.350, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "SERV", "theme": "Robotics / Humanoid", "score": 0.250, "tier": "LOW", "status": "growing"},
    # Photonic Computing (emerging - pre-corpus, estimated convergence)
    {"ticker": "LITE", "theme": "Photonic Computing", "score": 0.400, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "COHR", "theme": "Photonic Computing", "score": 0.350, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "IIVI", "theme": "Photonic Computing", "score": 0.300, "tier": "LOW", "status": "emerging"},
    # Space / Satellite
    {"ticker": "RKLB", "theme": "Space / Satellite", "score": 0.500, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "ASTS", "theme": "Space / Satellite", "score": 0.400, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "PL",   "theme": "Space / Satellite", "score": 0.300, "tier": "LOW", "status": "growing"},
    {"ticker": "LUNR", "theme": "Space / Satellite", "score": 0.250, "tier": "LOW", "status": "emerging"},
    # Defense AI / Autonomy
    {"ticker": "PLTR", "theme": "Defense AI", "score": 0.600, "tier": "HIGH", "status": "growing"},
    {"ticker": "LDOS", "theme": "Defense AI", "score": 0.350, "tier": "MEDIUM", "status": "growing"},
    {"ticker": "BWXT", "theme": "Defense AI", "score": 0.300, "tier": "LOW", "status": "growing"},
    # Longevity / Anti-Aging (emerging)
    {"ticker": "ABBV", "theme": "Longevity", "score": 0.350, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "CELH", "theme": "Longevity", "score": 0.250, "tier": "LOW", "status": "emerging"},
    # Bitcoin Mining
    {"ticker": "MARA", "theme": "Bitcoin Mining", "score": 0.500, "tier": "MEDIUM", "status": "post_peak"},
    {"ticker": "RIOT", "theme": "Bitcoin Mining", "score": 0.450, "tier": "MEDIUM", "status": "post_peak"},
    {"ticker": "CLSK", "theme": "Bitcoin Mining", "score": 0.350, "tier": "MEDIUM", "status": "post_peak"},
    # Brain-Computer Interface / Neurotech (emerging — pre-catalyst)
    {"ticker": "BFLY", "theme": "BCI / Neurotech", "score": 0.500, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "QSI",  "theme": "BCI / Neurotech", "score": 0.400, "tier": "MEDIUM", "status": "emerging"},
    # Solid-State Batteries (emerging — pre-catalyst)
    {"ticker": "QS",   "theme": "Solid-State Battery", "score": 0.550, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "SLDP", "theme": "Solid-State Battery", "score": 0.350, "tier": "MEDIUM", "status": "emerging"},
    # Synthetic Biology (emerging)
    {"ticker": "CRBU", "theme": "Synthetic Biology", "score": 0.400, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "TWST", "theme": "Synthetic Biology", "score": 0.350, "tier": "MEDIUM", "status": "emerging"},
    {"ticker": "PACB", "theme": "Synthetic Biology", "score": 0.300, "tier": "LOW", "status": "emerging"},
    # Edge AI / Neuromorphic (emerging)
    {"ticker": "AMBA", "theme": "Edge AI", "score": 0.500, "tier": "MEDIUM", "status": "emerging"},
]

# -- Filter Config --
MIN_OTM = 0.20
MAX_OTM = 0.50
MIN_DTE = 30
MAX_DTE = 90
MAX_PREMIUM = 10.00
MIN_PREMIUM = 0.05
MIN_OI = 50
MAX_IV = 1.50  # generous for now, real IV can be high on small caps

def run():
    import random
    client_id = random.randint(100, 999)
    print(f"[{now()}] Connecting to IBKR Gateway on port {IBKR_PORT} (clientId={client_id})...")
    ib = IB()
    ib.connect("127.0.0.1", IBKR_PORT, clientId=client_id, readonly=True, timeout=30)
    ib.reqMarketDataType(3)  # delayed data
    print(f"[{now()}] Connected. Account: {ib.managedAccounts()}")

    all_scored = []
    scan_meta = {
        "scanned_at": now(),
        "tickers_scanned": 0,
        "contracts_fetched": 0,
        "contracts_passed": 0,
        "themes": {},
    }

    # Deduplicate tickers (some appear in multiple themes)
    seen_tickers = set()
    unique_entries = []
    for entry in CONVERGENCE:
        if entry["ticker"] not in seen_tickers:
            seen_tickers.add(entry["ticker"])
            unique_entries.append(entry)

    for idx, entry in enumerate(unique_entries):
        sym = entry["ticker"]
        print(f"\n[{now()}] Scanning {sym} ({entry['theme']}) [{idx+1}/{len(unique_entries)}]...")

        # Rate limit: 3s between tickers to avoid gateway overload
        if idx > 0:
            ib.sleep(3)

        # Reconnect if connection dropped
        if not ib.isConnected():
            print(f"  Reconnecting...")
            try:
                new_id = random.randint(100, 999)
                ib.connect("127.0.0.1", IBKR_PORT, clientId=new_id, readonly=True, timeout=30)
                ib.reqMarketDataType(3)
                print(f"  Reconnected (clientId={new_id}).")
            except Exception as e:
                print(f"  Reconnect failed: {e}. Skipping remaining tickers.")
                break

        try:
            stock = Stock(sym, "SMART", "USD")
            ib.qualifyContracts(stock)
            [ticker] = ib.reqTickers(stock)
            ib.sleep(2)
            [ticker] = ib.reqTickers(stock)
            price = ticker.last or ticker.close or 0
            if price <= 0 or math.isnan(price):
                print(f"  No price for {sym}, skipping")
                continue
            print(f"  Price: ${price:.2f}")
        except Exception as e:
            print(f"  Error getting price for {sym}: {e}")
            continue

        scan_meta["tickers_scanned"] += 1

        # Get option chain parameters
        try:
            chains = ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)
            if not chains:
                print(f"  No option chains")
                continue
            chain = chains[0]
        except Exception as e:
            print(f"  Error getting chains: {e}")
            continue

        now_dt = datetime.now(timezone.utc)
        contracts_for_ticker = []

        for exp in sorted(chain.expirations):
            exp_date = datetime.strptime(exp, "%Y%m%d").replace(tzinfo=timezone.utc)
            dte = (exp_date - now_dt).days
            if dte < MIN_DTE or dte > MAX_DTE:
                continue

            # Find OTM strikes
            otm_strikes = []
            for strike in sorted(chain.strikes):
                otm_pct = (strike - price) / price
                if MIN_OTM <= otm_pct <= MAX_OTM:
                    otm_strikes.append((strike, otm_pct))

            if not otm_strikes:
                continue

            # Fetch option data (limit per expiry, with delay)
            for strike, otm_pct in otm_strikes[:8]:  # limit per expiry to reduce requests
                try:
                    opt = Option(sym, exp, strike, "C", "SMART")
                    ib.qualifyContracts(opt)
                    [opt_ticker] = ib.reqTickers(opt)
                    ib.sleep(0.5)
                    [opt_ticker] = ib.reqTickers(opt)

                    bid = opt_ticker.bid if opt_ticker.bid and opt_ticker.bid > 0 else 0
                    ask = opt_ticker.ask if opt_ticker.ask and opt_ticker.ask > 0 else 0
                    last = opt_ticker.last if opt_ticker.last and opt_ticker.last > 0 else 0
                    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else last
                    vol = opt_ticker.volume or 0

                    greeks = opt_ticker.modelGreeks or opt_ticker.lastGreeks
                    iv = greeks.impliedVol if greeks and greeks.impliedVol else 0
                    delta = greeks.delta if greeks and greeks.delta else 0

                    # Use volume as OI proxy (delayed data doesn't always have OI)
                    raw_oi = getattr(opt_ticker, "callOpenInterest", None)
                    oi = raw_oi if raw_oi and not math.isnan(raw_oi) and raw_oi > 0 else 0
                    # Liquidity proxy: best of OI, volume, or 1
                    liquidity = max(oi, vol, 1)

                    scan_meta["contracts_fetched"] += 1

                    # Filter — relaxed for delayed/after-hours data
                    premium = mid if mid > 0 else last
                    if premium < MIN_PREMIUM or premium > MAX_PREMIUM:
                        continue
                    if iv <= 0:
                        continue
                    # Skip liquidity filter if after hours (bid=0 is normal)
                    # Just need some evidence of trading activity
                    if liquidity < 1 and vol < 1:
                        continue

                    # Score
                    conv = entry["score"]
                    iv_inv = 1.0 / max(iv, 0.01)
                    liq = math.log(max(liquidity, 1))
                    score = round(conv * iv_inv * liq, 2)

                    contracts_for_ticker.append({
                        "ticker": sym,
                        "theme": entry["theme"],
                        "theme_status": entry["status"],
                        "convergence": conv,
                        "tier": entry["tier"],
                        "strike": strike,
                        "expiry": exp,
                        "dte": dte,
                        "otm_pct": round(otm_pct * 100, 1),
                        "bid": round(bid, 2),
                        "ask": round(ask, 2),
                        "mid": round(mid, 2),
                        "last": round(last, 2),
                        "iv": round(iv * 100, 1),
                        "delta": round(delta, 4),
                        "volume": vol,
                        "oi_proxy": int(liquidity),
                        "underlying_price": round(price, 2),
                        "asymmetry_score": round(score, 2),
                        "payoff_ratio": round(price / max(premium, 0.01), 1),
                    })
                    scan_meta["contracts_passed"] += 1

                except Exception:
                    continue

        print(f"  {len(contracts_for_ticker)} contracts passed filters")
        all_scored.extend(contracts_for_ticker)

        # Update theme stats
        theme = entry["theme"]
        if theme not in scan_meta["themes"]:
            scan_meta["themes"][theme] = {"tickers": [], "contracts": 0}
        scan_meta["themes"][theme]["tickers"].append(sym)
        scan_meta["themes"][theme]["contracts"] += len(contracts_for_ticker)

    ib.disconnect()
    print(f"\n[{now()}] Disconnected. Total scored: {len(all_scored)}")

    # Sort by asymmetry score
    all_scored.sort(key=lambda x: (-x["asymmetry_score"], x["ticker"], x["expiry"], x["strike"]))

    # Export JSON for dashboard
    output = {
        "scan_meta": scan_meta,
        "results": all_scored[:50],  # top 50 for dashboard
        "convergence": CONVERGENCE,
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    print(f"[{now()}] Results written to {OUTPUT_JSON}")

    # Format alert
    alert = format_alert(all_scored[:10], scan_meta)
    if DRY_RUN:
        print(f"\n[DRY RUN] Alert:\n{alert}")
    else:
        send_telegram(alert)

    return all_scored


def format_alert(top, meta):
    lines = [
        "LLM CONVERGENCE SCANNER - LIVE IBKR",
        f"Scan: {meta['scanned_at']}",
        f"Tickers: {meta['tickers_scanned']} | Contracts: {meta['contracts_fetched']} fetched, {meta['contracts_passed']} passed",
        "",
    ]
    for i, c in enumerate(top):
        lines.append(
            f"{i+1}. {c['ticker']} ${c['strike']}C {c['expiry'][:4]}-{c['expiry'][4:6]}-{c['expiry'][6:]} "
            f"({c['dte']}d, {c['otm_pct']}% OTM)"
        )
        lines.append(
            f"   ${c['ask']:.2f} ask | IV:{c['iv']}% | Score:{c['asymmetry_score']} | "
            f"{c['theme']} ({c['theme_status']})"
        )
        lines.append("")

    lines.append("Research ranking only. No trade advice.")
    lines.append("Paper-safe, read-only scan.")
    return "\n".join(lines)


def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN:
        print("No Telegram token, printing instead")
        print(msg)
        return
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=10,
        )
        print("Alert sent to Telegram")
    except Exception as e:
        print(f"Telegram error: {e}")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


if __name__ == "__main__":
    run()
