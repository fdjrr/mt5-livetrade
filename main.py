import time

import MetaTrader5 as mt5
import pandas as pd
import ta
from loguru import logger

SYMBOL = "BTCUSDc"
TIMEFRAME = mt5.TIMEFRAME_M1
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
INITIAL_LOT = 0.01
MAGIC = 123456
MARTINGALE_MODE = True
MAX_STEPS = 5
MULTIPLIER = 2
TAKE_PROFIT = 15
STOP_LOSS = 10
DEVIATION = 20
TICK_VALUE = 0.0001
TICK_SIZE = 0.0001


def get_data(n=100):
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, n)

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df["rsi"] = ta.momentum.RSIIndicator(close=df["close"], window=RSI_PERIOD).rsi()

    return df


def send_order(order_type, lot, price, tp, sl):
    if order_type == "buy":
        type = mt5.ORDER_TYPE_BUY
        action = mt5.TRADE_ACTION_DEAL
    elif order_type == "sell":
        type = mt5.ORDER_TYPE_SELL
        action = mt5.TRADE_ACTION_DEAL
    elif order_type == "buy_limit":
        type = mt5.ORDER_TYPE_BUY_LIMIT
        action = mt5.TRADE_ACTION_PENDING
    elif order_type == "sell_limit":
        type = mt5.ORDER_TYPE_SELL_LIMIT
        action = mt5.TRADE_ACTION_PENDING
    else:
        raise ValueError(f"Invalid order type {order_type}")

    request = {
        "action": action,
        "symbol": SYMBOL,
        "volume": lot,
        "type": type,
        "price": price,
        "tp": tp,
        "sl": sl,
        "magic": MAGIC,
        "deviation": DEVIATION,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    logger.info(f"Sending order: {request}")

    result = mt5.order_send(request)
    logger.info(f"Order result: {result}")

    return result


def calculate_entry(order_type, price):
    pip_value = (TICK_VALUE / TICK_SIZE) * INITIAL_LOT

    tp_diff = TAKE_PROFIT / pip_value
    sl_diff = STOP_LOSS / pip_value

    if order_type == "buy" or order_type == "buy_limit":
        tp = price + tp_diff
        sl = price - sl_diff
    elif order_type == "sell" or order_type == "sell_limit":
        tp = price - tp_diff
        sl = price + sl_diff
    else:
        raise ValueError("Invalid order type")

    return tp, sl


def total_profit():
    positions = mt5.positions_get(symbol=SYMBOL)

    return sum([position.profit for position in positions])


def total_positions():
    positions = mt5.positions_get(symbol=SYMBOL)

    return len(positions) if positions else 0


def martingle_strategy(order_type, price):
    entry_price = price

    for step in range(MAX_STEPS):
        lot = INITIAL_LOT * (MULTIPLIER**step)

        tp_price, sl_price = calculate_entry(order_type, entry_price)

        send_order(order_type, lot, entry_price, tp_price, sl_price)

        entry_price = sl_price


def main():
    global TICK_VALUE, TICK_SIZE

    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        quit()

    # Account info
    print("=" * 50)
    print("ACCOUNT INFORMATION")
    print("=" * 50)
    account_info = mt5.account_info()
    print("ID:", account_info.login)
    print("Server:", account_info.server)
    print("Balance:", account_info.balance)
    print("Currency:", account_info.currency)
    print("Equity:", account_info.equity)
    print("Free margin:", account_info.margin)
    print("Margin level:", account_info.margin_level)
    print("Profit:", account_info.profit)

    # Symbol info
    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        print(f"Symbol {SYMBOL} not found")
        quit()

    TICK_VALUE = symbol_info.trade_tick_value
    TICK_SIZE = symbol_info.trade_tick_size

    print("=" * 50)
    print("SYMBOL INFORMATION")
    print("=" * 50)
    print("Symbol:", SYMBOL)
    print("Tick value:", TICK_VALUE)
    print("Tick size:", TICK_SIZE)
    print("Description:", symbol_info.description)
    print("Page:", symbol_info.page)
    print("Path:", symbol_info.path)

    print("=" * 50)
    print("STRATEGY INFORMATION")
    print("=" * 50)
    print("Timeframe:", TIMEFRAME)
    print("RSI Period:", RSI_PERIOD)
    print("RSI Oversold:", RSI_OVERSOLD)
    print("RSI Overbought:", RSI_OVERBOUGHT)
    print("Initial Lot:", INITIAL_LOT)
    print("Martingale Mode:", MARTINGALE_MODE)
    print("Max Steps:", MAX_STEPS)
    print("Target Profit:", TAKE_PROFIT)
    print("=" * 50)

    while True:
        df = get_data(200)

        last_rsi = df["rsi"].iloc[-1]
        logger.info(f"Last RSI: {last_rsi}")

        logger.info(f"Total positions: {total_positions()}")
        logger.info(f"Total profit: {total_profit()}")

        last_tick = mt5.symbol_info_tick(SYMBOL)
        logger.info(f"Last tick: {last_tick}")

        if last_rsi < RSI_OVERSOLD:
            if total_positions() > 0:
                logger.info("Already in position, skipping...")
                time.sleep(1)
                continue

            price = last_tick.ask

            martingle_strategy("buy_limit", price)

        elif last_rsi > RSI_OVERBOUGHT:
            if total_positions() > 0:
                logger.info("Already in position, skipping...")
                time.sleep(1)
                continue

            price = last_tick.bid

            martingle_strategy("sell_limit", price)

        time.sleep(1)


if __name__ == "__main__":
    main()
