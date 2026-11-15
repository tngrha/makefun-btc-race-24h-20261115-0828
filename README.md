# Momentum Scalper v2

A dip-buying BTC trading bot for the make.fun `btc-race-24h-20261115-0828`
competition ($250, paper-money BTC trading bot race). It trades Coinbase
Wrapped BTC (cbBTC) against USDC on 1-minute on-chain bars, starting with
$1,000 of paper money. Simulation only: no real money is traded.

## Strategy

Long only, one position at a time, whole cash per trade. The bot waits for a
real drop and then for the bounce to actually start:

- **Entry:** the 60-minute return is at or below **-150 bps** AND the
  10-minute return is at or above **+50 bps** (the fall has stopped and the
  price is turning up). The order fills at the next bar's open, still near
  the trough of a V-shaped bounce.
- **Exit:** a trailing stop **100 bps** below the highest close seen since
  entry. The peak starts at the entry close, so this is also a 1% stop-loss.
  There is no fixed profit target: the stop rides the bounce up and only
  sells on the fade.

Late-window fallbacks, so the bot still trades on a quiet day (the race
needs at least 1 trade to meet the guardrails):

- From batch 1200, if it has never bought, the drop threshold relaxes to
  -100 bps with a +30 bps 10-minute confirmation.
- From batch 1380, if it still has never bought, it buys on the next batch
  whatever the market is doing.

## Why this shape

The published dev window falls about 4% with one sharp V: a slow grind down
from $67k to a $62k trough, then a +5.5% bounce in about 75 minutes.
Trend-following on 1-minute bars gets whipsawed there (the kit's EMA-cross
baseline loses ~$135) and plain dip-buying catches falling knives. Waiting
for the drop *plus* the bounce confirmation is what survives it.

## Dev-window result (kit's frozen 24h, local grade)

- Net PnL: **+$31.47** (+3.1%), 2 trades, max drawdown 1.2%
- Buy filled at $62,684.60, sell filled at $64,709.34
- Buy-and-hold on the same window loses $44.01

## Running

Python 3.13, standard library only. The bot speaks `agent-fun/bars-replay/v1`
(newline-delimited JSON on stdin/stdout) through the vendored kit shim in
`vendor/` (a byte-for-byte copy of the kit's `sdk/makefun_bars.py`):

```
python3 -P -s main.py
```

Grade it on the kit's dev window:

```
node cli/makefun.mjs grade-local --kit <kit dir> --bot <this repo> --driver process
```

Everything is integer arithmetic on the closes the harness sends. No clock,
no network, no randomness, no files outside the repository: two runs on the
same bars give the same orders.

## License

MIT — see `LICENSE`.
