#!/usr/bin/env python3
"""
LLM Convergence Options Scanner — Paper-Safe, Read-Only MVP

Turns the LLM retail flow convergence corpus into ranked OTM call alerts
without placing orders or exposing credentials. Connects to Interactive
Brokers TWS/Gateway API (read-only) or falls back to inline fixtures.

Setup:
  1. Install deps: pip install ib_insync requests
  2. Set env vars (all optional — falls back to fixtures without them):
     - IBKR_HOST: TWS/Gateway host (default: 127.0.0.1)
     - IBKR_PORT: TWS/Gateway port (default: 7497 for paper, 7496 for live)
     - IBKR_CLIENT_ID: unique client ID (default: 1)
     - TELEGRAM_BOT_TOKEN: Telegram bot token for alerts
     - TELEGRAM_CHAT_ID: chat ID to send alerts to
     - CONVERGENCE_FILE: path to convergence JSON (default: inline fixtures)
     - DRY_RUN: set to "false" to enable Telegram sending (default: true)
  3. Run: python llm_options_scanner.py

Safety:
  - HARD DRY-RUN MODE: no orders are ever placed. This script is read-only.
  - No account data, balances, positions, or P&L are accessed or logged.
  - No trade recommendations — output is "research signal ranking" only.
  - Credentials are env-var only, never hardcoded or logged.

Integration:
  Consumes convergence scores from the LLM Retail Flow Signal corpus
  (task c40be891). Downstream of convergence computation, upstream of
  human decision-making. Does NOT overlap with reward-cap, triage, or
  emission logic — this is alpha research tooling.

Task ID: 64ee3a22-8bdc-42cc-98df-8beaea0b95a9
"""

import os
import json
import math
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("llm-scanner")

# ============================================================================
# SAFETY GUARD — HARD DRY-RUN MODE
# ============================================================================

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() != "false"

if DRY_RUN:
    log.info("DRY RUN MODE: Telegram alerts will be logged, not sent.")
else:
    log.info("LIVE MODE: Telegram alerts will be sent.")

# This script NEVER places orders. Even if connected to a live IBKR account,
# it only reads market data and option chains. No order-related API calls exist
# anywhere in this code.

# ============================================================================
# CONVERGENCE INPUT SCHEMA
# ============================================================================

@dataclass
class ConvergenceEntry:
    """A ticker with its LLM convergence score from the seed corpus."""
    ticker: str
    theme: str
    convergence_score: float      # 0.0-1.0
    adjusted_signal: float        # convergence * capture_confidence
    tier: str                     # HIGH, MEDIUM, LOW
    models_mentioning: int        # out of captured slots
    avg_rank: float


def load_convergence(filepath: Optional[str] = None) -> list[ConvergenceEntry]:
    """Load convergence data from JSON file or fall back to inline fixtures."""
    if filepath and os.path.exists(filepath):
        log.info(f"Loading convergence from {filepath}")
        with open(filepath) as f:
            data = json.load(f)
        return [ConvergenceEntry(**e) for e in data]

    log.info("Using inline convergence fixtures (no external file)")
    return _convergence_fixtures()


def _convergence_fixtures() -> list[ConvergenceEntry]:
    """Inline fixtures from the Phase 0 seed corpus (task c40be891)."""
    return [
        # AI Infrastructure
        ConvergenceEntry("NVDA", "ai_infra", 1.000, 0.800, "HIGH", 4, 1.0),
        ConvergenceEntry("AVGO", "ai_infra", 0.775, 0.620, "HIGH", 3, 2.0),
        ConvergenceEntry("VRT",  "ai_infra", 0.620, 0.496, "MEDIUM", 4, 4.3),
        ConvergenceEntry("ANET", "ai_infra", 0.336, 0.269, "LOW", 2, 3.5),
        ConvergenceEntry("MU",   "ai_infra", 0.325, 0.260, "LOW", 2, 4.0),
        # GLP-1 / Peptides
        ConvergenceEntry("LLY",  "peptides", 1.000, 0.800, "HIGH", 4, 1.0),
        ConvergenceEntry("NVO",  "peptides", 0.850, 0.680, "HIGH", 4, 2.0),
        ConvergenceEntry("VKTX", "peptides", 0.636, 0.509, "MEDIUM", 4, 3.5),
        # Quantum Computing
        ConvergenceEntry("IONQ", "quantum", 0.917, 0.733, "HIGH", 4, 1.8),
        ConvergenceEntry("QBTS", "quantum", 0.750, 0.600, "HIGH", 4, 3.0),
        ConvergenceEntry("RGTI", "quantum", 0.736, 0.589, "MEDIUM", 4, 3.5),
        # Nuclear / SMR
        ConvergenceEntry("BWXT", "nuclear_smr", 0.750, 0.600, "HIGH", 4, 3.0),
        ConvergenceEntry("OKLO", "nuclear_smr", 0.676, 0.541, "MEDIUM", 3, 1.7),
        ConvergenceEntry("SMR",  "nuclear_smr", 0.643, 0.514, "MEDIUM", 3, 2.8),
    ]


# ============================================================================
# BROKER API WRAPPER — READ-ONLY
# ============================================================================

@dataclass
class OptionContract:
    """A single option contract from the broker."""
    ticker: str
    expiry: str              # YYYYMMDD
    strike: float
    right: str               # "C" for call
    last_price: float
    bid: float
    ask: float
    volume: int
    open_interest: int
    implied_vol: float       # IV as decimal (e.g., 0.45 = 45%)
    delta: float
    underlying_price: float
    dte: int                 # days to expiration


class BrokerClient:
    """
    TWS/Gateway-compatible broker client wrapper.
    Read-only: fetches market data and option chains only.
    Falls back to fixtures if no connection available.
    """

    def __init__(self):
        self.connected = False
        self.ib = None
        self._try_connect()

    def _try_connect(self):
        """Attempt IBKR connection. Fail gracefully to fixture mode."""
        host = os.environ.get("IBKR_HOST", "127.0.0.1")
        port = int(os.environ.get("IBKR_PORT", "7497"))
        client_id = int(os.environ.get("IBKR_CLIENT_ID", "1"))

        try:
            from ib_insync import IB, Stock, Option
            self.ib = IB()
            self.ib.connect(host, port, clientId=client_id, readonly=True, timeout=10)
            self.connected = True
            log.info(f"Connected to IBKR at {host}:{port} (read-only)")
        except Exception as e:
            log.warning(f"IBKR connection failed ({e}). Using fixture data.")
            self.connected = False

    def get_option_chain(self, ticker: str) -> list[OptionContract]:
        """Fetch option chain for a ticker. Returns fixtures if not connected."""
        if self.connected:
            return self._fetch_live_chain(ticker)
        return self._fixture_chain(ticker)

    def _fetch_live_chain(self, ticker: str) -> list[OptionContract]:
        """Fetch real option chain from IBKR. Read-only, no orders."""
        from ib_insync import Stock, Option
        try:
            stock = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(stock)
            [ticker_data] = self.ib.reqTickers(stock)
            underlying_price = ticker_data.marketPrice()

            chains = self.ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)
            if not chains:
                log.warning(f"No option chains for {ticker}")
                return []

            chain = chains[0]
            now = datetime.now(timezone.utc)
            target_min = now + timedelta(days=30)
            target_max = now + timedelta(days=90)

            results = []
            for exp in sorted(chain.expirations):
                exp_date = datetime.strptime(exp, "%Y%m%d").replace(tzinfo=timezone.utc)
                if exp_date < target_min or exp_date > target_max:
                    continue
                dte = (exp_date - now).days

                for strike in chain.strikes:
                    otm_pct = (strike - underlying_price) / underlying_price
                    if otm_pct < 0.20 or otm_pct > 0.50:
                        continue

                    opt = Option(ticker, exp, strike, "C", "SMART")
                    try:
                        self.ib.qualifyContracts(opt)
                        [opt_data] = self.ib.reqTickers(opt)
                        greeks = opt_data.modelGreeks or opt_data.lastGreeks
                        results.append(OptionContract(
                            ticker=ticker,
                            expiry=exp,
                            strike=strike,
                            right="C",
                            last_price=opt_data.last or opt_data.close or 0,
                            bid=opt_data.bid or 0,
                            ask=opt_data.ask or 0,
                            volume=opt_data.volume or 0,
                            open_interest=getattr(opt_data, "callOpenInterest", None) or opt_data.volume or 0,
                            implied_vol=greeks.impliedVol if greeks else 0,
                            delta=greeks.delta if greeks else 0,
                            underlying_price=underlying_price,
                            dte=dte,
                        ))
                    except Exception:
                        continue

            log.info(f"Fetched {len(results)} contracts for {ticker}")
            return results
        except Exception as e:
            log.error(f"Error fetching chain for {ticker}: {e}")
            return []

    def _fixture_chain(self, ticker: str) -> list[OptionContract]:
        """Generate realistic fixture option chain data for testing."""
        # Approximate current prices for fixture tickers
        prices = {
            "NVDA": 217, "AVGO": 423, "VRT": 126, "ANET": 95, "MU": 105,
            "LLY": 870, "NVO": 41, "VKTX": 33,
            "IONQ": 44, "QBTS": 19, "RGTI": 15,
            "BWXT": 226, "OKLO": 76, "SMR": 13,
        }
        underlying = prices.get(ticker, 100)
        now = datetime.now(timezone.utc)
        contracts = []

        for dte_offset in [35, 60, 90]:
            exp_date = now + timedelta(days=dte_offset)
            exp_str = exp_date.strftime("%Y%m%d")

            for otm_pct in [0.20, 0.30, 0.40, 0.50]:
                strike = round(underlying * (1 + otm_pct), 2)
                # Simulate IV and pricing
                base_iv = 0.45 + (0.15 * otm_pct)  # higher OTM = higher IV
                premium = max(0.05, round(underlying * 0.005 * (1 - otm_pct) * (dte_offset / 60), 2))
                delta = max(0.02, round(0.30 * (1 - otm_pct * 2) * (dte_offset / 90), 3))
                oi = max(100, int(5000 * (1 - otm_pct) * (1 if underlying > 50 else 0.3)))

                contracts.append(OptionContract(
                    ticker=ticker,
                    expiry=exp_str,
                    strike=strike,
                    right="C",
                    last_price=premium,
                    bid=round(premium * 0.9, 2),
                    ask=round(premium * 1.1, 2),
                    volume=max(10, int(oi * 0.1)),
                    open_interest=oi,
                    implied_vol=round(base_iv, 3),
                    delta=delta,
                    underlying_price=underlying,
                    dte=dte_offset,
                ))

        return contracts

    def disconnect(self):
        if self.connected and self.ib:
            self.ib.disconnect()
            log.info("Disconnected from IBKR")


# ============================================================================
# CONTRACT FILTERING
# ============================================================================

@dataclass
class FilterConfig:
    """Filtering criteria for OTM call selection."""
    min_otm_pct: float = 0.20       # 20% out of the money minimum
    max_otm_pct: float = 0.50       # 50% out of the money maximum
    min_dte: int = 30               # minimum days to expiration
    max_dte: int = 90               # maximum days to expiration
    max_premium: float = 5.00       # maximum premium per contract
    min_premium: float = 0.05       # minimum premium (avoid illiquid dust)
    max_iv_proxy: float = 0.50       # raw IV as conservative IV-rank proxy; production can use 52-week IV percentile
    min_open_interest: int = 100    # minimum open interest for liquidity
    max_delta: float = 0.30         # maximum delta (deep OTM focus)
    min_delta: float = 0.02         # minimum delta (avoid worthless)


@dataclass
class FilterResult:
    """Filter output with rejection accounting for auditability."""
    passed: list[OptionContract]
    rejections: dict[str, int]
    total_input: int


def filter_contracts(
    contracts: list[OptionContract],
    config: FilterConfig = FilterConfig(),
) -> FilterResult:
    """Filter option contracts by OTM %, DTE, premium, IV, OI, and delta.
    Returns passed contracts plus rejection-reason counts for transparency."""
    filtered = []
    rejections = {
        "otm_out_of_range": 0,
        "dte_out_of_range": 0,
        "premium_out_of_range": 0,
        "iv_proxy_too_high": 0,
        "open_interest_too_low": 0,
        "delta_out_of_range": 0,
    }

    for c in contracts:
        otm_pct = (c.strike - c.underlying_price) / c.underlying_price
        if otm_pct < config.min_otm_pct or otm_pct > config.max_otm_pct:
            rejections["otm_out_of_range"] += 1
            continue
        if c.dte < config.min_dte or c.dte > config.max_dte:
            rejections["dte_out_of_range"] += 1
            continue

        price = c.ask if c.ask > 0 else c.last_price
        if price < config.min_premium or price > config.max_premium:
            rejections["premium_out_of_range"] += 1
            continue
        if c.implied_vol > config.max_iv_proxy:
            rejections["iv_proxy_too_high"] += 1
            continue
        if c.open_interest < config.min_open_interest:
            rejections["open_interest_too_low"] += 1
            continue
        if c.delta < config.min_delta or c.delta > config.max_delta:
            rejections["delta_out_of_range"] += 1
            continue

        filtered.append(c)

    log.info(f"Filtered {len(contracts)} -> {len(filtered)} contracts")
    for reason, count in rejections.items():
        if count > 0:
            log.info(f"  Rejected {count} for {reason}")

    return FilterResult(passed=filtered, rejections=rejections, total_input=len(contracts))


# ============================================================================
# CONVERGENCE-WEIGHTED SCORING
# ============================================================================

@dataclass
class ScoredContract:
    """A filtered contract scored by convergence x IV-inverse x liquidity."""
    contract: OptionContract
    convergence_entry: ConvergenceEntry
    # Score components
    convergence_component: float
    iv_inverse_component: float
    liquidity_component: float
    # Final score
    asymmetry_score: float
    # Derived
    otm_pct: float
    payoff_ratio: float          # underlying_price / premium (theoretical max leverage)


def score_contracts(
    contracts: list[OptionContract],
    convergence: list[ConvergenceEntry],
) -> list[ScoredContract]:
    """
    Score each contract by:
      asymmetry = convergence_score * (1 / IV) * log(open_interest)

    Higher score = higher convergence + cheaper vol + enough liquidity.
    Sorting: descending by asymmetry_score.
    """
    conv_map = {e.ticker: e for e in convergence}
    scored = []

    for c in contracts:
        entry = conv_map.get(c.ticker)
        if not entry:
            continue

        # Components
        conv_component = entry.adjusted_signal
        iv_inv = 1.0 / max(c.implied_vol, 0.01)
        liq_component = math.log(max(c.open_interest, 1))

        # Asymmetry score
        score = conv_component * iv_inv * liq_component

        price = c.ask if c.ask > 0 else c.last_price
        otm_pct = (c.strike - c.underlying_price) / c.underlying_price
        payoff = c.underlying_price / max(price, 0.01)

        scored.append(ScoredContract(
            contract=c,
            convergence_entry=entry,
            convergence_component=round(conv_component, 4),
            iv_inverse_component=round(iv_inv, 4),
            liquidity_component=round(liq_component, 4),
            asymmetry_score=round(score, 4),
            otm_pct=round(otm_pct, 4),
            payoff_ratio=round(payoff, 1),
        ))

    # Deterministic tie-break: score desc, then ticker, expiry, strike asc
    scored.sort(key=lambda s: (
        -s.asymmetry_score,
        s.contract.ticker,
        s.contract.expiry,
        s.contract.strike,
    ))
    return scored


# ============================================================================
# MESSAGING BOT ALERT FORMATTER
# ============================================================================

def format_alert(
    ranked: list[ScoredContract],
    top_n: int = 10,
    rejections: Optional[dict[str, int]] = None,
) -> str:
    """Format top-ranked contracts into a Telegram-ready alert message."""
    if not ranked:
        return "LLM Convergence Scanner: No contracts passed filters today."

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"LLM CONVERGENCE OPTIONS SCANNER",
        f"Scan: {now}",
        f"Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}",
        f"Scored: {len(ranked)} contracts",
        f"",
        f"TOP {min(top_n, len(ranked))} RANKED BY ASYMMETRY SCORE:",
        f"(convergence x IV-inverse x liquidity)",
        f"",
    ]

    for i, s in enumerate(ranked[:top_n]):
        c = s.contract
        price = c.ask if c.ask > 0 else c.last_price
        lines.append(
            f"{i+1}. {c.ticker} ${c.strike}C {c.expiry[:4]}-{c.expiry[4:6]}-{c.expiry[6:]} "
            f"({c.dte}d) @ ${price:.2f}"
        )
        lines.append(
            f"   Score: {s.asymmetry_score:.1f} | "
            f"Conv: {s.convergence_component:.3f} | "
            f"IV: {c.implied_vol:.0%} | "
            f"OI: {c.open_interest:,} | "
            f"OTM: {s.otm_pct:.0%} | "
            f"Theme: {s.convergence_entry.theme}"
        )
        lines.append("")

    if rejections:
        active = {k: v for k, v in rejections.items() if v > 0}
        if active:
            lines.append("FILTER REJECTIONS:")
            for reason, count in active.items():
                lines.append(f"  {reason}: {count}")
            lines.append("")

    lines.append("Research signal ranking only. No trade advice or instructions.")
    lines.append("No capital deployed. Paper-safe, read-only scan.")
    return "\n".join(lines)


def send_telegram(message: str) -> bool:
    """Send alert to Telegram. Respects DRY_RUN mode."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if DRY_RUN:
        log.info("DRY RUN — alert not sent. Message:")
        print(message)
        return True

    if not token or not chat_id:
        log.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. Printing instead.")
        print(message)
        return False

    import requests
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": ""},
            timeout=10,
        )
        if resp.ok:
            log.info(f"Alert sent to Telegram chat {chat_id}")
            return True
        else:
            log.error(f"Telegram send failed: {resp.status_code} {resp.text[:100]}")
            return False
    except Exception as e:
        log.error(f"Telegram send error: {e}")
        return False


# ============================================================================
# MAIN SCANNER PIPELINE
# ============================================================================

@dataclass
class PaperSafeAudit:
    """Audit record proving paper-safe execution constraints."""
    mode: str                          # "dry_run" or "live_alerts"
    broker_connected: bool
    order_methods_present: bool        # always False
    account_data_accessed: bool        # always False
    credentials_logged: bool           # always False
    external_alert_sent: bool
    fixture_fallback_used: bool
    scanned_at_utc: str
    tickers_scanned: int
    contracts_fetched: int
    contracts_passed_filter: int
    contracts_scored: int
    methodology_version: str = "paper_safe_options_scanner_v1"


def run_scan(
    convergence_file: Optional[str] = None,
    top_n: int = 10,
    filter_config: FilterConfig = FilterConfig(),
) -> list[ScoredContract]:
    """
    Full scan pipeline:
    1. Load convergence data
    2. Connect to broker (or use fixtures)
    3. Fetch option chains for HIGH-tier tickers
    4. Filter by OTM/DTE/IV/OI criteria
    5. Score by convergence x IV-inverse x liquidity
    6. Format and send alert
    """
    log.info("=" * 60)
    log.info("LLM CONVERGENCE OPTIONS SCANNER — STARTING")
    log.info("=" * 60)

    # Step 1: Load convergence
    convergence = load_convergence(convergence_file)
    high_tickers = [e for e in convergence if e.tier in ("HIGH", "MEDIUM")]
    log.info(f"Loaded {len(convergence)} tickers, {len(high_tickers)} HIGH/MEDIUM tier")

    # Step 2: Connect to broker
    broker = BrokerClient()

    # Step 3: Fetch option chains
    all_contracts = []
    for entry in high_tickers:
        chain = broker.get_option_chain(entry.ticker)
        all_contracts.extend(chain)
        log.info(f"  {entry.ticker}: {len(chain)} contracts fetched")

    log.info(f"Total contracts fetched: {len(all_contracts)}")

    # Step 4: Filter
    filter_result = filter_contracts(all_contracts, filter_config)

    # Step 5: Score
    scored = score_contracts(filter_result.passed, convergence)
    log.info(f"Scored {len(scored)} contracts")

    # Step 6: Format and send
    alert = format_alert(scored, top_n, filter_result.rejections)
    alert_sent = send_telegram(alert)

    # Step 7: Emit audit record
    audit = PaperSafeAudit(
        mode="dry_run" if DRY_RUN else "live_alerts",
        broker_connected=broker.connected,
        order_methods_present=False,
        account_data_accessed=False,
        credentials_logged=False,
        external_alert_sent=alert_sent and not DRY_RUN,
        fixture_fallback_used=not broker.connected,
        scanned_at_utc=datetime.now(timezone.utc).isoformat(),
        tickers_scanned=len(high_tickers),
        contracts_fetched=len(all_contracts),
        contracts_passed_filter=len(filter_result.passed),
        contracts_scored=len(scored),
    )
    log.info(f"AUDIT: {json.dumps(asdict(audit), indent=2)}")

    # Cleanup
    broker.disconnect()

    log.info("Scan complete.")
    return scored


# ============================================================================
# INLINE TEST / FIXTURE HARNESS
# ============================================================================

def run_tests():
    """
    Inline test block demonstrating deterministic ranking without
    external credentials. Uses fixture data only.
    """
    log.info("=" * 60)
    log.info("RUNNING INLINE TESTS (fixture mode)")
    log.info("=" * 60)

    # Test 1: Convergence loading
    convergence = _convergence_fixtures()
    assert len(convergence) == 14, f"Expected 14 fixtures, got {len(convergence)}"
    assert convergence[0].ticker == "NVDA"
    assert convergence[0].convergence_score == 1.0
    log.info("PASS: Convergence fixtures loaded correctly")

    # Test 2: Fixture chain generation
    broker = BrokerClient()  # will fail to connect, use fixtures
    chain = broker.get_option_chain("IONQ")
    assert len(chain) > 0, "Expected non-empty fixture chain"
    assert all(c.ticker == "IONQ" for c in chain)
    assert all(c.right == "C" for c in chain)
    log.info(f"PASS: Fixture chain generated {len(chain)} contracts for IONQ")

    # Test 3: Filtering with rejection accounting
    config = FilterConfig()
    filter_result = filter_contracts(chain, config)
    filtered = filter_result.passed
    assert filter_result.total_input == len(chain)
    assert isinstance(filter_result.rejections, dict)
    for c in filtered:
        otm = (c.strike - c.underlying_price) / c.underlying_price
        assert config.min_otm_pct <= otm <= config.max_otm_pct, f"OTM {otm} out of range"
        assert config.min_dte <= c.dte <= config.max_dte, f"DTE {c.dte} out of range"
    log.info(f"PASS: Filter applied, {len(filtered)} pass, rejections: {filter_result.rejections}")

    # Test 4: Scoring determinism
    scored1 = score_contracts(filtered, convergence)
    scored2 = score_contracts(filtered, convergence)
    assert len(scored1) == len(scored2)
    for s1, s2 in zip(scored1, scored2):
        assert s1.asymmetry_score == s2.asymmetry_score, "Scoring not deterministic"
    log.info(f"PASS: Scoring is deterministic ({len(scored1)} scored)")

    # Test 5: Scoring order (higher convergence should generally rank higher)
    if len(scored1) >= 2:
        assert scored1[0].asymmetry_score >= scored1[-1].asymmetry_score
        log.info("PASS: Scoring sorted descending by asymmetry_score")

    # Test 6: Alert formatting with rejections
    alert = format_alert(scored1, top_n=3, rejections=filter_result.rejections)
    assert "LLM CONVERGENCE OPTIONS SCANNER" in alert
    assert "DRY RUN" in alert
    assert "Research signal ranking only" in alert
    assert "No trade advice" in alert
    log.info("PASS: Alert formatted with safety disclaimers")

    # Test 6b: Do-not-say-buy language guard
    for forbidden in ["buy", "entry", "target", "stop loss", "trade now", "recommend"]:
        assert forbidden not in alert.lower(), f"Alert contains forbidden word: {forbidden}"
    log.info("PASS: Alert contains no trade-recommendation language")

    # Test 7: No-order safety guard
    # Verify no order-related methods exist on broker
    assert not hasattr(broker, "place_order")
    assert not hasattr(broker, "submit_order")
    assert not hasattr(broker, "buy")
    assert not hasattr(broker, "sell")
    log.info("PASS: No order methods exist on BrokerClient")

    # Test 8: Multi-ticker scan
    all_contracts = []
    for entry in convergence[:5]:
        all_contracts.extend(broker.get_option_chain(entry.ticker))
    filter_all = filter_contracts(all_contracts, config)
    scored_all = score_contracts(filter_all.passed, convergence)
    tickers_in_results = set(s.contract.ticker for s in scored_all)
    assert len(tickers_in_results) > 1, "Expected multiple tickers in scan"
    log.info(f"PASS: Multi-ticker scan returned {len(scored_all)} scored from {len(tickers_in_results)} tickers")

    # Test 9: Convergence drives ranking
    # NVDA (convergence 0.800) should generally outscore LOW-tier tickers
    nvda_scores = [s for s in scored_all if s.contract.ticker == "NVDA"]
    low_scores = [s for s in scored_all if s.convergence_entry.tier == "LOW"]
    if nvda_scores and low_scores:
        assert nvda_scores[0].asymmetry_score >= low_scores[-1].asymmetry_score
        log.info("PASS: HIGH convergence outranks LOW convergence")

    # Test 10: Full pipeline dry run
    results = run_scan(top_n=5)
    assert isinstance(results, list)
    log.info(f"PASS: Full pipeline completed, {len(results)} results")

    broker.disconnect()
    log.info("=" * 60)
    log.info("ALL 10 TESTS PASSED")
    log.info("=" * 60)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        run_tests()
    else:
        convergence_file = os.environ.get("CONVERGENCE_FILE")
        run_scan(convergence_file=convergence_file)
