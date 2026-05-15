#!/usr/bin/env python3
"""
Live IBKR Options Scanner — Convergence-Weighted
Connects to IB Gateway, scans options chains for HIGH-convergence tickers,
scores by asymmetry, exports dashboard JSON + sends Telegram alert.
"""

import json, os, math, sys, time
from datetime import datetime, timezone, timedelta

# -- Config --
IBKR_PORT = int(os.environ.get("IBKR_PORT", "4002"))
OUTPUT_JSON = os.path.expanduser("~/pft-validator/scanner/scan-results.json")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() != "false"

# -- Convergence Artifact --
CORPUS_ARTIFACT = os.path.expanduser(
    os.environ.get("CONVERGENCE_ARTIFACT", "~/puc-trading/corpus/convergence-latest.json")
)
REQUIRED_SCORE_FIELDS = {"ticker", "theme", "score", "tier", "status"}


class ConvergenceLoadError(RuntimeError):
    pass


def _parse_generated_at(value):
    if not value:
        raise ConvergenceLoadError("convergence artifact missing generated_at")
    if not isinstance(value, str):
        raise ConvergenceLoadError("convergence artifact generated_at must be a string")
    normalized = value.replace("Z", "+00:00")
    try:
        generated_at = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ConvergenceLoadError(f"convergence artifact generated_at is not parseable: {value}") from exc
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    return generated_at.astimezone(timezone.utc)


def validate_convergence_artifact(path=CORPUS_ARTIFACT, max_age_days=None, now_utc=None):
    path = os.path.expanduser(path)
    if max_age_days is None:
        try:
            max_age_days = int(os.environ.get("CORPUS_MAX_AGE_DAYS", "14"))
        except ValueError as exc:
            raise ConvergenceLoadError("CORPUS_MAX_AGE_DAYS must be an integer") from exc

    if not os.path.exists(path):
        raise ConvergenceLoadError(f"convergence artifact missing: {path}")

    try:
        with open(path) as f:
            artifact = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConvergenceLoadError(f"convergence artifact malformed JSON: {path}: {exc}") from exc

    if not isinstance(artifact, dict):
        raise ConvergenceLoadError("convergence artifact must be a JSON object")
    if not artifact.get("schema_version"):
        raise ConvergenceLoadError("convergence artifact missing schema_version")

    generated_at = _parse_generated_at(artifact.get("generated_at"))
    now_utc = now_utc or datetime.now(timezone.utc)
    age = now_utc - generated_at
    max_age = timedelta(days=max_age_days)
    if age > max_age:
        raise ConvergenceLoadError(
            "convergence artifact stale: "
            f"age={age.total_seconds() / 86400:.2f} days threshold={max_age_days} days"
        )

    scores = artifact.get("scores")
    if not isinstance(scores, list) or not scores:
        raise ConvergenceLoadError("convergence artifact scores must be a non-empty list")

    for idx, row in enumerate(scores):
        if not isinstance(row, dict):
            raise ConvergenceLoadError(f"convergence score row {idx} must be an object")
        missing = sorted(field for field in REQUIRED_SCORE_FIELDS if field not in row or row[field] in (None, ""))
        if missing:
            raise ConvergenceLoadError(f"convergence score row {idx} missing required fields: {', '.join(missing)}")

    return artifact


def map_convergence_scores(artifact):
    rows = []
    for row in artifact["scores"]:
        rows.append({
            "ticker": str(row["ticker"]).upper(),
            "theme": str(row["theme"]),
            "score": float(row["score"]),
            "tier": str(row["tier"]).upper(),
            "status": str(row["status"]),
        })
    return rows


def load_convergence(path=CORPUS_ARTIFACT, max_age_days=None, now_utc=None):
    return map_convergence_scores(validate_convergence_artifact(path, max_age_days, now_utc))


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
    convergence = load_convergence()
    from ib_insync import IB, Stock, Option

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
    for entry in convergence:
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
        "convergence": convergence,
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
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("No TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env, printing instead")
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
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--validate-convergence":
            artifact = validate_convergence_artifact()
            print(
                f"[{now()}] Convergence artifact valid: "
                f"{len(artifact['scores'])} scores from {artifact['generated_at']}"
            )
        else:
            run()
    except ConvergenceLoadError as exc:
        print(f"[{now()}] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
