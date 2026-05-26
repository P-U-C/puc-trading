"""Phase 1: options-chain pull.

Primary path: IB Gateway via ib_insync (port 4002).
Fallback path: yfinance .option_chain() — narrower data but works
without IB Gateway being up.

Daily snapshot pattern: pull chain for each convergence ticker, cache
to options-cache/<ticker>-<YYYY-MM-DD>.json. Detector reads from cache.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

LOG = logging.getLogger("mispricing.ib_chain")
CACHE_DIR = Path(__file__).resolve().parent.parent / "options-cache"
IB_HOST = "127.0.0.1"
IB_PORT = 4002
IB_CLIENT_ID = 17


@dataclass
class ChainContract:
    """One option contract row."""
    strike: float
    expiry: str         # YYYY-MM-DD
    right: str          # "C" or "P"
    bid: float | None
    ask: float | None
    last: float | None
    iv: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    open_interest: int | None
    volume: int | None

    def mid(self) -> float | None:
        if self.bid is None or self.ask is None:
            return self.last
        if self.bid <= 0 or self.ask <= 0:
            return self.last
        return round((self.bid + self.ask) / 2, 4)


@dataclass
class ChainSnapshot:
    ticker: str
    snapshot_at: str          # ISO datetime
    spot: float | None
    source: str               # "ib" or "yfinance"
    contracts: list[ChainContract] = field(default_factory=list)
    error: str | None = None

    def expiries(self) -> list[str]:
        return sorted({c.expiry for c in self.contracts})

    def chain_for_expiry(self, expiry: str) -> list[ChainContract]:
        return [c for c in self.contracts if c.expiry == expiry]


# ---------- IB Gateway path -----------------------------------------------

def _pull_via_ib(ticker: str, max_expiries: int = 16) -> ChainSnapshot:
    try:
        from ib_insync import IB, Stock, util  # noqa
    except ImportError as exc:
        raise RuntimeError("ib_insync not installed") from exc

    ib = IB()
    snapshot = ChainSnapshot(
        ticker=ticker,
        snapshot_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        spot=None, source="ib", contracts=[],
    )
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
    except Exception as exc:
        snapshot.error = f"connect failed: {exc}"
        return snapshot

    try:
        stock = Stock(ticker, "SMART", "USD")
        qualified = ib.qualifyContracts(stock)
        if not qualified:
            snapshot.error = "ticker not qualified on IB SMART/USD"
            return snapshot
        stock = qualified[0]
        spot_ticker = ib.reqMktData(stock, snapshot=True)
        ib.sleep(1.5)
        snapshot.spot = spot_ticker.marketPrice() or spot_ticker.last or None
        ib.cancelMktData(stock)

        chains = ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)
        chain = next((c for c in chains if c.exchange == "SMART"), None)
        if chain is None:
            snapshot.error = "no SMART chain returned"
            return snapshot

        # Pick first N expiries; leave strike scope to the caller via filtering.
        expiries = sorted(chain.expirations)[:max_expiries]
        snapshot._raw_chain_meta = {  # type: ignore[attr-defined]
            "exchange": chain.exchange,
            "trading_class": chain.tradingClass,
            "all_expiries": list(sorted(chain.expirations)),
        }
        # Pull a moderate strike band around spot (±25% to capture both
        # ATM straddles and reasonable OTM).
        if snapshot.spot:
            min_k = snapshot.spot * 0.55
            max_k = snapshot.spot * 1.45
            strikes = sorted([k for k in chain.strikes if min_k <= k <= max_k])
        else:
            strikes = sorted(chain.strikes)[:20]

        from ib_insync import Option
        for expiry in expiries:
            for strike in strikes:
                for right in ("C", "P"):
                    opt = Option(stock.symbol, expiry, strike, right, "SMART",
                                 tradingClass=chain.tradingClass, currency="USD")
                    try:
                        qual = ib.qualifyContracts(opt)
                    except Exception:
                        continue
                    if not qual:
                        continue
                    opt = qual[0]
                    t = ib.reqMktData(opt, "100,101,104,105,106", snapshot=True)
                    ib.sleep(0.25)
                    iv = getattr(t.modelGreeks, "impliedVol", None) if t.modelGreeks else None
                    delta = getattr(t.modelGreeks, "delta", None) if t.modelGreeks else None
                    gamma = getattr(t.modelGreeks, "gamma", None) if t.modelGreeks else None
                    theta = getattr(t.modelGreeks, "theta", None) if t.modelGreeks else None
                    vega = getattr(t.modelGreeks, "vega", None) if t.modelGreeks else None
                    snapshot.contracts.append(ChainContract(
                        strike=strike, expiry=expiry, right=right,
                        bid=t.bid if t.bid and t.bid > 0 else None,
                        ask=t.ask if t.ask and t.ask > 0 else None,
                        last=t.last if t.last and t.last > 0 else None,
                        iv=iv, delta=delta, gamma=gamma, theta=theta, vega=vega,
                        open_interest=t.callOpenInterest or t.putOpenInterest,
                        volume=t.volume,
                    ))
                    ib.cancelMktData(opt)
    finally:
        try:
            ib.disconnect()
        except Exception:
            pass

    return snapshot


# ---------- yfinance fallback ---------------------------------------------

def _pull_via_yfinance(ticker: str, max_expiries: int = 16) -> ChainSnapshot:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance not installed") from exc

    snapshot = ChainSnapshot(
        ticker=ticker,
        snapshot_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        spot=None, source="yfinance", contracts=[],
    )
    try:
        tk = yf.Ticker(ticker)
        info = tk.fast_info if hasattr(tk, "fast_info") else None
        spot = None
        if info:
            spot = getattr(info, "last_price", None) or getattr(info, "regular_market_price", None)
        if spot is None:
            try:
                hist = tk.history(period="1d")
                if not hist.empty:
                    spot = float(hist["Close"].iloc[-1])
            except Exception:
                pass
        snapshot.spot = spot

        expiries = list(getattr(tk, "options", []) or [])[:max_expiries]
        if not expiries:
            snapshot.error = "no expiries returned by yfinance"
            return snapshot

        for expiry in expiries:
            try:
                chain = tk.option_chain(expiry)
            except Exception as exc:
                LOG.warning("yf chain %s %s failed: %s", ticker, expiry, exc)
                continue
            for df, right in ((chain.calls, "C"), (chain.puts, "P")):
                for _, row in df.iterrows():
                    snapshot.contracts.append(ChainContract(
                        strike=float(row["strike"]),
                        expiry=expiry, right=right,
                        bid=float(row["bid"]) if row["bid"] > 0 else None,
                        ask=float(row["ask"]) if row["ask"] > 0 else None,
                        last=float(row["lastPrice"]) if row["lastPrice"] > 0 else None,
                        iv=float(row["impliedVolatility"]) if row["impliedVolatility"] > 0 else None,
                        delta=None, gamma=None, theta=None, vega=None,  # yf doesn't expose greeks
                        open_interest=int(row["openInterest"]) if row["openInterest"] > 0 else None,
                        volume=int(row["volume"]) if row["volume"] > 0 else None,
                    ))
    except Exception as exc:
        snapshot.error = f"yfinance fallback failed: {exc}"
    return snapshot


# ---------- public API ----------------------------------------------------

def pull_chain(ticker: str, *, prefer: str = "ib",
               max_expiries: int = 16) -> ChainSnapshot:
    """Pull options chain. Prefer IB, fall back to yfinance on connect failure."""
    if prefer == "ib":
        snap = _pull_via_ib(ticker, max_expiries=max_expiries)
        if snap.error or not snap.contracts:
            LOG.info("IB failed for %s (%s); falling back to yfinance",
                     ticker, snap.error)
            snap = _pull_via_yfinance(ticker, max_expiries=max_expiries)
        return snap
    return _pull_via_yfinance(ticker, max_expiries=max_expiries)


def cache_path(ticker: str, date: dt.date | None = None) -> Path:
    date = date or dt.date.today()
    return CACHE_DIR / f"{ticker}-{date.isoformat()}.json"


def save_snapshot(snapshot: ChainSnapshot) -> Path:
    out = cache_path(snapshot.ticker)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(snapshot)
    payload["contracts"] = [asdict(c) for c in snapshot.contracts]
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(out)
    return out


def load_snapshot(ticker: str, date: dt.date | None = None) -> ChainSnapshot | None:
    p = cache_path(ticker, date)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    contracts = [ChainContract(**c) for c in data.pop("contracts", [])]
    return ChainSnapshot(**data, contracts=contracts) if False else ChainSnapshot(
        ticker=data["ticker"], snapshot_at=data["snapshot_at"], spot=data.get("spot"),
        source=data.get("source", "?"), contracts=contracts, error=data.get("error"),
    )


def refresh_universe(tickers: list[str], *, prefer: str = "ib") -> dict[str, dict[str, Any]]:
    """Daily snapshot: pull chain for each ticker, cache to disk.
    Returns a per-ticker summary suitable for printing / logging.
    """
    summary: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        try:
            snap = pull_chain(ticker, prefer=prefer)
            path = save_snapshot(snap)
            summary[ticker] = {
                "source": snap.source,
                "contracts": len(snap.contracts),
                "expiries": len(snap.expiries()),
                "spot": snap.spot,
                "path": str(path),
                "error": snap.error,
            }
        except Exception as exc:
            summary[ticker] = {"error": f"pull failed: {exc}"}
    return summary
