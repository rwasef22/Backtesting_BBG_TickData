"""
COMPLETE FILL/REFILL LOGIC WALKTHROUGH WITH EXAMPLES
====================================================

Configuration:
- Security: ADNOCGAS
- Quote size: 65,000 shares
- Refill interval: 180 seconds (3 minutes)
- Min liquidity threshold: $13,000 AED

Key State Variables:
- last_refill_time[security][side]: Timestamp when quote was last placed on this side
- active_orders[security][side]: Currently active quote details
- quote_prices[security][side]: Current quote price for this side

================================================================================
SCENARIO 1: FIRST QUOTE PLACEMENT (No Previous Quotes)
================================================================================

Time: 10:00:00
Event: BID update - Best bid becomes 3.10 @ 500,000 shares
State BEFORE:
  last_refill_time['ADNOCGAS']['bid'] = None
  active_orders['ADNOCGAS']['bid'] = None
  quote_prices['ADNOCGAS']['bid'] = None

Processing Flow:
1. Orderbook update: Best bid = 3.10 @ 500,000 shares
2. should_refill_side('ADNOCGAS', 10:00:00, 'bid') called
   - last_refill_time is None
   - Returns: TRUE (first time, always allow)

3. Generate quote: bid_price = 3.10 (quote at best bid)
4. Check liquidity:
   - bid_ahead = 500,000 shares (qty at price 3.10)
   - bid_liquidity = 3.10 * 500,000 = $1,550,000
   - threshold = $13,000
   - bid_ok = TRUE ($1,550,000 >= $13,000)

5. Quote PASSES liquidity check:
   active_orders['ADNOCGAS']['bid'] = {
       'price': 3.10,
       'ahead_qty': 500,000,
       'our_remaining': 65,000
   }
   quote_prices['ADNOCGAS']['bid'] = 3.10
   set_refill_time('ADNOCGAS', 'bid', 10:00:00)

State AFTER:
  last_refill_time['ADNOCGAS']['bid'] = 10:00:00
  active_orders['ADNOCGAS']['bid'] = {price: 3.10, ahead_qty: 500000, our_remaining: 65000}
  quote_prices['ADNOCGAS']['bid'] = 3.10

Result: Quote is now ACTIVE and will remain for 180 seconds

================================================================================
SCENARIO 2: QUOTE UPDATE ATTEMPTS DURING COOLDOWN (No Fills Yet)
================================================================================

Time: 10:00:30 (30 seconds after quote placed)
Event: BID update - Best bid changes to 3.11 @ 300,000 shares

Processing Flow:
1. Orderbook update: Best bid = 3.11 @ 300,000 shares
2. should_refill_side('ADNOCGAS', 10:00:30, 'bid') called
   - last_refill_time = 10:00:00
   - elapsed = 30 seconds
   - refill_interval = 180 seconds
   - Returns: FALSE (30 < 180, still in cooldown)

3. BID quote logic SKIPPED - still in cooldown period

State: UNCHANGED (quote from 10:00:00 still active)
  last_refill_time['ADNOCGAS']['bid'] = 10:00:00
  active_orders['ADNOCGAS']['bid'] = {price: 3.10, ahead_qty: 500000, our_remaining: 65000}
  quote_prices['ADNOCGAS']['bid'] = 3.10

Result: Original quote at 3.10 remains active even though market moved to 3.11

---

Time: 10:01:00 (60 seconds after quote placed)
Event: Multiple orderbook updates

Processing Flow:
1. should_refill_side() returns FALSE (60 < 180)
2. Quote logic SKIPPED

State: UNCHANGED - quote still "sticking" at 3.10

---

Time: 10:02:30 (150 seconds after quote placed)
Event: BID update

Processing Flow:
1. should_refill_side() returns FALSE (150 < 180)
2. Quote logic SKIPPED

State: UNCHANGED

================================================================================
SCENARIO 3: COOLDOWN EXPIRES - NEW QUOTE PLACEMENT (No Fills Occurred)
================================================================================

Time: 10:03:00 (180 seconds after initial quote)
Event: BID update - Best bid is now 3.09 @ 800,000 shares

Processing Flow:
1. Orderbook update: Best bid = 3.09 @ 800,000 shares
2. should_refill_side('ADNOCGAS', 10:03:00, 'bid') called
   - last_refill_time = 10:00:00
   - elapsed = 180 seconds
   - refill_interval = 180 seconds
   - Returns: TRUE (180 >= 180, cooldown expired)

3. Generate NEW quote: bid_price = 3.09 (quote at NEW best bid)
4. Check liquidity:
   - bid_ahead = 800,000 shares
   - bid_liquidity = 3.09 * 800,000 = $2,472,000
   - bid_ok = TRUE

5. Place NEW quote:
   active_orders['ADNOCGAS']['bid'] = {
       'price': 3.09,          # UPDATED from 3.10
       'ahead_qty': 800,000,   # UPDATED
       'our_remaining': 65,000
   }
   quote_prices['ADNOCGAS']['bid'] = 3.09  # UPDATED
   set_refill_time('ADNOCGAS', 'bid', 10:03:00)  # RESET timer

State AFTER:
  last_refill_time['ADNOCGAS']['bid'] = 10:03:00  # RESET
  active_orders['ADNOCGAS']['bid'] = {price: 3.09, ahead_qty: 800000, our_remaining: 65000}
  quote_prices['ADNOCGAS']['bid'] = 3.09

Result: New 180-second cooldown period begins at 10:03:00

================================================================================
SCENARIO 4: MARKET TRADE HITS OUR QUOTE (PARTIAL FILL)
================================================================================

Time: 10:03:45 (45 seconds into new cooldown)
Event: TRADE @ 3.09, qty = 20,000 shares

Current State:
  quote_prices['ADNOCGAS']['bid'] = 3.09
  active_orders['ADNOCGAS']['bid'] = {
      'price': 3.09,
      'ahead_qty': 800,000,
      'our_remaining': 65,000
  }

Processing Flow:
1. Event type = 'trade', price = 3.09, qty = 20,000
2. process_trade() called
3. Check: trade_price (3.09) <= bid_price (3.09)? YES - BID HIT!

4. Consume qty_ahead FIRST:
   - ahead_qty = 800,000
   - consumed_ahead = min(800,000, 20,000) = 20,000
   - ahead_qty becomes: 800,000 - 20,000 = 780,000
   - remaining to consume = 20,000 - 20,000 = 0

5. Consume our_remaining (if anything left):
   - remaining = 0
   - No fill for us this time (qty_ahead consumed all)

State AFTER:
  active_orders['ADNOCGAS']['bid'] = {
      'price': 3.09,
      'ahead_qty': 780,000,  # DECREASED
      'our_remaining': 65,000  # UNCHANGED (still waiting)
  }
  
Result: Queue ahead decreased, our quote still active, NO fill recorded

---

Time: 10:04:30 (90 seconds into cooldown)
Event: TRADE @ 3.09, qty = 800,000 shares (LARGE TRADE)

Processing Flow:
1. Check: trade_price <= bid_price? YES
2. Consume qty_ahead:
   - ahead_qty = 780,000
   - consumed_ahead = min(780,000, 800,000) = 780,000
   - ahead_qty becomes: 0
   - remaining = 800,000 - 780,000 = 20,000

3. Consume our_remaining:
   - our_remaining = 65,000
   - consumed_ours = min(65,000, 20,000) = 20,000
   - our_remaining becomes: 65,000 - 20,000 = 45,000

4. Record fill:
   _record_fill('ADNOCGAS', 'buy', 3.09, 20,000, 10:04:30)
   - Updates position: position += 20,000
   - Records trade in trades list
   - RESETS refill time: set_refill_time('ADNOCGAS', 'bid', 10:04:30)

State AFTER:
  last_refill_time['ADNOCGAS']['bid'] = 10:04:30  # RESET after fill
  active_orders['ADNOCGAS']['bid'] = {
      'price': 3.09,
      'ahead_qty': 0,          # Queue cleared
      'our_remaining': 45,000  # PARTIALLY FILLED (65k -> 45k)
  }
  position['ADNOCGAS'] = 20,000  # NEW position
  trades list has new entry

Result: PARTIAL FILL, new 180-second cooldown starts from 10:04:30

================================================================================
SCENARIO 5: SUBSEQUENT FILLS ON SAME QUOTE
================================================================================

Time: 10:05:00 (30 seconds after first fill)
Event: TRADE @ 3.09, qty = 50,000 shares

Current State:
  active_orders['ADNOCGAS']['bid'] = {
      'price': 3.09,
      'ahead_qty': 0,
      'our_remaining': 45,000
  }

Processing Flow:
1. Check: trade_price <= bid_price? YES
2. Consume qty_ahead:
   - ahead_qty = 0
   - consumed_ahead = 0
   - remaining = 50,000

3. Consume our_remaining:
   - our_remaining = 45,000
   - consumed_ours = min(45,000, 50,000) = 45,000  # FULL FILL!
   - our_remaining becomes: 0

4. Record fill:
   _record_fill('ADNOCGAS', 'buy', 3.09, 45,000, 10:05:00)
   - position becomes: 20,000 + 45,000 = 65,000
   - set_refill_time('ADNOCGAS', 'bid', 10:05:00)  # RESET again

State AFTER:
  last_refill_time['ADNOCGAS']['bid'] = 10:05:00  # RESET again
  active_orders['ADNOCGAS']['bid'] = {
      'price': 3.09,
      'ahead_qty': 0,
      'our_remaining': 0  # FULLY FILLED
  }
  position['ADNOCGAS'] = 65,000
  
Result: COMPLETE FILL, all 65,000 shares executed, new cooldown from 10:05:00

---

Time: 10:05:30 (30 seconds after complete fill)
Event: BID update - Best bid moves to 3.12 @ 1,000,000 shares

Processing Flow:
1. should_refill_side('ADNOCGAS', 10:05:30, 'bid') called
   - last_refill_time = 10:05:00
   - elapsed = 30 seconds
   - Returns: FALSE (still in cooldown)

2. Quote logic SKIPPED

Result: Even though fully filled, must wait full 180 seconds before new quote

---

Time: 10:08:00 (180 seconds after last fill)
Event: BID update

Processing Flow:
1. should_refill_side() returns TRUE (cooldown expired)
2. Generate NEW quote at current best bid
3. Place new quote with fresh our_remaining = 65,000
4. Reset refill timer to 10:08:00

Result: New quote cycle begins

================================================================================
SCENARIO 6: INSUFFICIENT LIQUIDITY - QUOTE SUPPRESSED
================================================================================

Time: 10:10:00
Event: BID update - Best bid = 3.15 @ 100 shares (THIN MARKET)

Processing Flow:
1. should_refill_side() returns TRUE (assume cooldown expired)
2. Generate quote: bid_price = 3.15
3. Check liquidity:
   - bid_ahead = 100 shares
   - bid_liquidity = 3.15 * 100 = $315
   - threshold = $13,000
   - bid_ok = FALSE ($315 < $13,000)

4. Liquidity check FAILS:
   active_orders['ADNOCGAS']['bid'] = {
       'price': 3.15,
       'ahead_qty': 100,
       'our_remaining': 0  # SUPPRESSED
   }
   quote_prices['ADNOCGAS']['bid'] = None  # NO QUOTE
   # NO set_refill_time() call - timer NOT reset

State AFTER:
  last_refill_time['ADNOCGAS']['bid'] = 10:08:00  # UNCHANGED
  quote_prices['ADNOCGAS']['bid'] = None
  active_orders bid has our_remaining = 0

Result: Quote NOT placed, timer NOT reset, will check again on next update

---

Time: 10:10:01 (1 second later)
Event: BID update - Best bid = 3.14 @ 500,000 shares (LIQUIDITY RETURNS)

Processing Flow:
1. should_refill_side() returns TRUE
   - last_refill_time = 10:08:00
   - elapsed = 121 seconds (> 180)
   
2. Check liquidity:
   - bid_liquidity = 3.14 * 500,000 = $1,570,000
   - bid_ok = TRUE

3. Place quote:
   active_orders['ADNOCGAS']['bid'] = {
       'price': 3.14,
       'ahead_qty': 500,000,
       'our_remaining': 65,000
   }
   quote_prices['ADNOCGAS']['bid'] = 3.14
   set_refill_time('ADNOCGAS', 'bid', 10:10:01)

Result: Quote placed immediately when liquidity sufficient

================================================================================
KEY BEHAVIORS SUMMARY
================================================================================

1. QUOTE PLACEMENT:
   - Requires: should_refill_side() = TRUE AND liquidity >= threshold
   - Effect: Sets refill_time, starts 180-second cooldown
   - Quote "sticks" at that price for full cooldown period

2. DURING COOLDOWN (0-179 seconds after placement):
   - should_refill_side() returns FALSE
   - No new quotes generated even if market moves
   - Existing quote remains active at original price
   - Market can still trade against the active quote

3. COOLDOWN EXPIRES (180+ seconds):
   - should_refill_side() returns TRUE
   - New quote can be placed at current best bid/ask
   - Timer resets for another 180 seconds

4. PARTIAL FILLS:
   - Decrease our_remaining
   - Decrease ahead_qty (queue simulation)
   - Reset refill_time (new 180-second cooldown)
   - Quote stays at same price with remaining qty

5. COMPLETE FILLS:
   - our_remaining becomes 0
   - Reset refill_time
   - Must wait 180 seconds before placing new quote

6. INSUFFICIENT LIQUIDITY:
   - Quote NOT placed (our_remaining = 0)
   - Refill timer NOT reset
   - Will attempt again on next update if cooldown expired

7. INDEPENDENT BID/ASK:
   - Each side has separate refill_time
   - Bid can be in cooldown while ask is available
   - Fills on one side don't affect other side's timer

================================================================================
TIMING DIAGRAM EXAMPLE
================================================================================

Time      Event                      should_refill?  Action                  Cooldown Until
--------  -------------------------  --------------  ----------------------  --------------
10:00:00  Bid 3.10@500k, liq OK      TRUE (first)    Place quote 65k@3.10    10:03:00
10:00:30  Bid changes to 3.11        FALSE           Skip (in cooldown)      10:03:00
10:01:00  Bid changes to 3.09        FALSE           Skip (in cooldown)      10:03:00
10:02:30  Multiple updates           FALSE           Skip (in cooldown)      10:03:00
10:03:00  Bid 3.08@800k, liq OK      TRUE (expired)  Place new quote@3.08    10:06:00
10:03:45  Trade@3.08, qty 20k        N/A             Partial fill (20k)      10:06:45
10:04:00  Bid changes                FALSE           Skip (in cooldown)      10:06:45
10:05:00  Trade@3.08, qty 50k        N/A             Fill remaining (45k)    10:08:00
10:06:00  Bid changes                FALSE           Skip (in cooldown)      10:08:00
10:08:00  Bid 3.12@1M, liq OK        TRUE (expired)  Place new quote@3.12    10:11:00

================================================================================
WHY THIS DESIGN WORKS
================================================================================

1. Prevents Over-Trading:
   - 180-second cooldown limits quote frequency
   - Avoids constantly canceling/replacing quotes
   
2. Realistic Market Making:
   - Quotes remain stable, giving market time to interact
   - Simulates actual limit order behavior
   
3. Fill Opportunity:
   - Quote stays at price level for 3 minutes
   - Market trades can hit the quote during this window
   
4. Liquidity Protection:
   - Only quotes when $13k+ liquidity exists
   - Prevents getting filled on thin/volatile moves

5. Queue Simulation:
   - ahead_qty tracks orders ahead in queue
   - Realistic fill sequencing (others fill first)
"""
