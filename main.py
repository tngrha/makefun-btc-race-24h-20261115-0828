"""Momentum Scalper v2: a dip-buying BTC bot for agent-fun/bars-replay/v1.

Strategy (long only, one position, $1,000 paper USDC, 1-minute cbBTC bars):

The dev window falls about 4% with one sharp V in it: a slow grind down from
$67k to a $62k trough, then a +5.5% bounce in about 75 minutes. Trend-following
on 1-minute bars gets whipsawed there (the EMA-cross baseline loses ~$135) and
plain dip-buying catches falling knives, so this bot does one thing only: it
waits for a real drop and then for the bounce to actually start.

Entry (flat only, whole cash, one buy at a time):
  - the 60-minute return is at or below -150 bps, AND the 10-minute return is
    at or above +50 bps (the fall has stopped and the price is turning up).
  - the fill happens at the next bar's open, so the entry lands a minute after
    the signal, still near the trough of a V-shaped bounce.

Exit (while holding): a trailing stop 100 bps below the highest close seen
since entry. That is also the stop-loss: the peak starts at the entry close,
so a 1% fall straight after entry exits the trade. No fixed profit target:
the stop rides the bounce up and only sells on the fade.

Late-window fallbacks, so the bot still trades on a quiet day (the race needs
at least 1 trade to meet the guardrails):
  - from batch 1200, if it has never bought, the drop threshold relaxes to
    -100 bps with a +30 bps 10-minute confirmation;
  - from batch 1380, if it still has never bought, it buys on the next batch
    whatever the market is doing, so the entry is never a zero-trade hold.

Everything is integer arithmetic on the closes the harness sends; there is no
clock, no network, no randomness and no state beyond the close history, the
trailing peak and how many buys have filled. Two runs on the same bars give
the same orders. A batch that carries no bar for CBBTC (a gap minute) or a
warm-up batch takes no order: the close would be stale, and the replay would
reject a warm-up order outright.

Dev window (kit's frozen 24h, graded locally): net PnL +$31.47 on 2 trades,
max drawdown 1.2%. Buy filled $62,684.60, sell filled $64,709.34.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
# 60-minute drop that marks a dip, in basis points.
DROP_BPS = 150
# 10-minute rise that confirms the bounce has started, in basis points.
STAB_WIN_BARS = 10
STAB_BPS = 50
# Trailing stop below the peak close since entry, in basis points.
TRAIL_BPS = 100
# Lookback for the drop, in bars (1-minute bars).
DROP_WIN_BARS = 60
# Late-window relaxation: from this batch, with no buy filled yet.
LATE_BAR = 1200
LATE_DROP_BPS = 100
LATE_STAB_BPS = 30
# Last-resort batch: buy on the next batch if still never bought.
FINAL_BAR = 1380
# Slippage cap on every order, measured from the latest close (bps).
MAX_SLIPPAGE_BPS = 200
# Minimum cash to bother buying (the harness minimum notional is 1 USDC).
MIN_CASH = 1_000_000


class DipBot:
    """Keeps the close history, the trailing peak and the filled-buy count."""

    def __init__(self):
        self.closes = []
        self.peak = None
        self.buys_filled = 0

    def on_batch(self, state, batch):
        for fill in batch.get("fills", []):
            if fill.get("side") == "buy" and fill.get("status") == "filled":
                self.buys_filled += 1
        fresh = False
        for bar in batch.get("bars", []):
            if bar.get("symbol") == SYMBOL:
                self.closes.append(int(bar["c"]))
                fresh = True
        # No new bar for our symbol this minute (a gap): the close is stale, so
        # there is nothing new to decide on; wait for the next bar instead of
        # re-sending the previous batch's decision. Warm-up batches likewise
        # take no orders: the replay would reject every one of them.
        if not fresh or state.warming_up:
            return []

        close = state.close(SYMBOL)
        if close is None:
            return []
        held = state.positions.get(SYMBOL)
        if held is not None and held.qty > 0:
            if self.peak is None or close > self.peak:
                self.peak = close
            if close * 10000 <= self.peak * (10000 - TRAIL_BPS):
                return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]
            return []

        # Flat: look for a dip that has started to bounce.
        n = len(self.closes)
        if n > DROP_WIN_BARS and state.cash >= MIN_CASH:
            ref60 = self.closes[-DROP_WIN_BARS - 1]
            ref10 = self.closes[-STAB_WIN_BARS - 1]
            ret60 = (close - ref60) * 10000 // ref60
            ret10 = (close - ref10) * 10000 // ref10
            fire = ret60 <= -DROP_BPS and ret10 >= STAB_BPS
            if not fire and state.seq >= LATE_BAR and self.buys_filled == 0:
                fire = ret60 <= -LATE_DROP_BPS and ret10 >= LATE_STAB_BPS
            if not fire and state.seq >= FINAL_BAR and self.buys_filled == 0:
                fire = True
            if fire:
                self.peak = close
                return [{"side": "buy", "symbol": SYMBOL,
                         "notional_quote_units": state.cash,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []


makefun_bars.run(DipBot().on_batch)
