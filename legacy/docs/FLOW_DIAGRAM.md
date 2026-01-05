"""
SIMPLIFIED FLOW DIAGRAM
=======================

ON EACH ORDERBOOK UPDATE (Bid/Ask/Trade event):
┌─────────────────────────────────────────────────────────────┐
│ 1. Update OrderBook with new best bid/ask                  │
│    - If BID: orderbook.bids.clear(); set new bid           │
│    - If ASK: orderbook.asks.clear(); set new ask           │
│    - If TRADE: just record the trade                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Generate Quotes (get best bid/ask from orderbook)       │
│    bid_price = best_bid_price                               │
│    ask_price = best_ask_price                               │
│    bid_size = 65,000 (configured)                           │
│    ask_size = 65,000 (configured)                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. CHECK BID SIDE                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
            ┌───────────────────────────────┐
            │ should_refill_side('bid')?    │
            │ - If last_refill_time = None  │
            │   → TRUE (first time)         │
            │ - If elapsed >= 180 sec       │
            │   → TRUE (cooldown expired)   │
            │ - Otherwise → FALSE           │
            └───────────────────────────────┘
                      ↓             ↓
                   FALSE          TRUE
                      ↓             ↓
              ┌──────────┐   ┌────────────────────────────┐
              │  SKIP    │   │ Check Liquidity:           │
              │ (in      │   │ liq = bid_price * qty_ahead│
              │cooldown) │   │ Is liq >= $13,000?         │
              └──────────┘   └────────────────────────────┘
                                      ↓         ↓
                                    FALSE      TRUE
                                      ↓         ↓
                          ┌──────────────┐  ┌─────────────────────┐
                          │ SUPPRESS     │  │ PLACE QUOTE:        │
                          │ our_rem = 0  │  │ - Save quote price  │
                          │ NO quote     │  │ - Set our_rem=65k   │
                          │ NO timer set │  │ - Save ahead_qty    │
                          └──────────────┘  │ - SET REFILL TIME   │
                                            │   (start cooldown)  │
                                            └─────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 4. CHECK ASK SIDE (same logic as bid)                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 5. IF EVENT IS A TRADE - Check for fills                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
            ┌───────────────────────────────┐
            │ If trade_price <= bid_price:  │
            │   BID HIT (we BUY)            │
            └───────────────────────────────┘
                            ↓
            ┌───────────────────────────────┐
            │ 1. Consume ahead_qty first    │
            │    consumed = min(ahead, qty) │
            │    ahead -= consumed          │
            │    remaining = qty - consumed │
            └───────────────────────────────┘
                            ↓
            ┌───────────────────────────────┐
            │ 2. Consume our_remaining      │
            │    filled = min(our_rem, rem) │
            │    our_rem -= filled          │
            └───────────────────────────────┘
                            ↓
            ┌───────────────────────────────┐
            │ 3. IF filled > 0:             │
            │    - Record fill              │
            │    - Update position          │
            │    - RESET refill_time        │
            │      (new cooldown starts)    │
            └───────────────────────────────┘

            ┌───────────────────────────────┐
            │ If trade_price >= ask_price:  │
            │   ASK HIT (we SELL)           │
            │   (same logic as bid)         │
            └───────────────────────────────┘


STATE MACHINE VIEW:
===================

For Each Side (Bid/Ask independently):

   ┌─────────────┐
   │   NO QUOTE  │ ← Initial state, or after liquidity fails
   └─────────────┘
         ↓ liquidity sufficient
   ┌─────────────┐
   │ QUOTE PLACED│ ← refill_time set, cooldown starts
   │ (Active)    │
   └─────────────┘
         ↓ market trade hits
   ┌─────────────┐
   │ PARTIAL FILL│ ← our_remaining decreases, refill_time RESET
   │ (Active)    │
   └─────────────┘
         ↓ fully filled OR cooldown expires
   ┌─────────────┐
   │  COOLDOWN   │ ← 180 seconds, quote stays at price
   │  EXPIRED    │
   └─────────────┘
         ↓ can place new quote
   Back to: Check liquidity → Place or Suppress


CRITICAL TIMING RULES:
======================

Rule 1: WHEN refill_time IS SET
   ✓ When quote passes liquidity AND is placed
   ✓ When fill occurs (partial or complete)
   ✗ NOT when liquidity fails
   ✗ NOT when in cooldown

Rule 2: WHEN refill_time IS RESET (new cooldown)
   ✓ Every time a fill occurs (even partial)
   ✓ When placing a new quote after cooldown expires
   ✗ NOT on subsequent fills within same second
   
Rule 3: QUOTE STAYS ACTIVE DURING COOLDOWN
   ✓ Price does NOT update even if market moves
   ✓ Can still get filled by market trades
   ✓ ahead_qty decreases as market trades occur
   ✓ our_remaining decreases only when WE get filled

Rule 4: INDEPENDENT SIDES
   ✓ Bid and Ask have separate refill timers
   ✓ Bid in cooldown does NOT affect Ask
   ✓ Fill on Bid does NOT reset Ask timer


EXAMPLE: RAPID MARKET SCENARIO
===============================

Time: 10:00:00 - Place bid@3.10, ask@3.15 (both pass liquidity)
  → bid cooldown until 10:03:00
  → ask cooldown until 10:03:00

Time: 10:00:05 - Market trades @3.10, we get filled 10k on bid
  → bid cooldown RESET to 10:03:05 (new 180s from fill)
  → ask cooldown unchanged (still 10:03:00)
  → bid quote now has 55k remaining @3.10

Time: 10:00:30 - Market moves to bid 3.11, ask 3.14
  → bid: should_refill=FALSE (only 25s elapsed), quote stays @3.10
  → ask: should_refill=FALSE (only 30s elapsed), quote stays @3.15
  → Both quotes stale but still active

Time: 10:01:00 - Market trades @3.10 again, we get filled 30k
  → bid cooldown RESET to 10:04:00
  → bid quote now has 25k remaining @3.10
  → ask still at @3.15

Time: 10:03:00 - Ask cooldown expires
  → ask: should_refill=TRUE, place new quote @3.14 (current market)
  → ask cooldown RESET to 10:06:00
  → bid: still in cooldown until 10:04:00

Time: 10:04:00 - Bid cooldown expires
  → bid: should_refill=TRUE, place new quote @3.11 (current market)
  → bid cooldown RESET to 10:07:00
  → Now both sides have fresh quotes
"""
