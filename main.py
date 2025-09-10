import time

import MetaTrader5 as mt5
import pandas as pd
import ta
from loguru import logger


class TradingBot:
    def __init__(
        self,
        symbol=None,
        timeframe=None,
        rsi_period=14,
        rsi_oversold=30,
        rsi_overbought=70,
        initial_lot=0.01,
        martingale_mode=True,
        max_steps=5,
        multiplier=2,
        take_profit=None,
        stop_loss=None,
        deviation=20,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.initial_lot = initial_lot

        self.martingale_mode = martingale_mode
        if self.martingale_mode:
            self.max_steps = max_steps
            self.multiplier = multiplier
        else:
            self.max_steps = 1
            self.multiplier = 1

        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.deviation = deviation

    def _get_account_info(self):
        account_info = mt5.account_info()

        if account_info is None:
            logger.error("Account info is None")
            exit()

        # Account info
        logger.info("=" * 50)
        logger.info("ACCOUNT INFORMATION")
        logger.info("=" * 50)
        logger.info(f"ID: {account_info.login}")
        logger.info(f"Server: {account_info.server}")
        logger.info(f"Balance: {account_info.balance}")
        logger.info(f"Currency: {account_info.currency}")
        logger.info(f"Equity: {account_info.equity}")
        logger.info(f"Free margin: {account_info.margin}")
        logger.info(f"Margin level: {account_info.margin_level}")
        logger.info(f"Profit: {account_info.profit}")

    def _get_symbol_info(self):
        symbol_info = mt5.symbol_info(self.symbol)

        if symbol_info is None:
            logger.error("Symbol info is None")
            exit()

        self.tick_value = symbol_info.trade_tick_value
        self.tick_size = symbol_info.trade_tick_size

        # Symbol info
        logger.info("=" * 50)
        logger.info("SYMBOL INFORMATION")
        logger.info("=" * 50)
        logger.info(f"Symbol: {symbol_info.name}")
        logger.info(f"Tick value: {self.tick_value}")
        logger.info(f"Tick size: {self.tick_size}")
        logger.info(f"Description: {symbol_info.description}")

    def _get_strategy_info(self):
        logger.info("=" * 50)
        logger.info("STRATEGY INFORMATION")
        logger.info("=" * 50)
        logger.info(f"Timeframe: {self.timeframe}")
        logger.info(f"RSI Period: {self.rsi_period}")
        logger.info(f"RSI Oversold: {self.rsi_oversold}")
        logger.info(f"RSI Overbought: {self.rsi_overbought}")
        logger.info(f"Initial Lot: {self.initial_lot}")
        logger.info(f"Martingale Mode: {self.martingale_mode}")
        logger.info(f"Max Steps: {self.max_steps}")
        logger.info(f"Take Profit: {self.take_profit}")
        logger.info(f"Stop Loss: {self.stop_loss}")
        logger.info("=" * 50)

    def copy_rates(self, n=100):
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, n)

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df["rsi"] = ta.momentum.RSIIndicator(
            close=df["close"], window=self.rsi_period
        ).rsi()

        return df

    def send_order(self, order_type, magic, lot, price, tp, sl):
        if order_type == "buy":
            action = mt5.TRADE_ACTION_DEAL
            type = mt5.ORDER_TYPE_BUY
        elif order_type == "sell":
            action = mt5.TRADE_ACTION_DEAL
            type = mt5.ORDER_TYPE_SELL
        elif order_type == "buy_limit":
            action = mt5.TRADE_ACTION_PENDING
            type = mt5.ORDER_TYPE_BUY_LIMIT
        elif order_type == "sell_limit":
            action = mt5.TRADE_ACTION_PENDING
            type = mt5.ORDER_TYPE_SELL_LIMIT
        else:
            raise ValueError(f"Invalid order type {order_type}")

        request = {
            "action": action,
            "symbol": self.symbol,
            "volume": lot,
            "type": type,
            "price": price,
            "tp": tp,
            "sl": sl,
            "magic": magic,
            "deviation": self.deviation,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        logger.info(f"Sending order: {request}")

        result = mt5.order_send(request)
        logger.info(f"Order result: {result}")

        return result

    def calculate_entry(self, order_type, price):
        pip_value = (self.tick_value / self.tick_size) * self.initial_lot

        tp_diff = self.take_profit / pip_value
        sl_diff = self.stop_loss / pip_value

        if order_type == "buy" or order_type == "buy_limit":
            tp = price + tp_diff
            sl = price - sl_diff
        elif order_type == "sell" or order_type == "sell_limit":
            tp = price - tp_diff
            sl = price + sl_diff
        else:
            raise ValueError("Invalid order type")

        return tp, sl

    def total_profit(self):
        positions = mt5.positions_get(symbol=self.symbol)

        return sum([position.profit for position in positions])

    def total_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)

        return len(positions) if positions else 0

    def validate_position(self, order_type):
        position = mt5.positions_get(symbol=self.symbol)[0]

        type = mt5.POSITION_TYPE_BUY if order_type == "buy" else mt5.POSITION_TYPE_SELL

        if position.type != type and position.magic != 1:
            return False

        return True

    def close_all_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)

        results = []

        for position in positions:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": (
                    mt5.POSITION_TYPE_BUY
                    if position.type == mt5.POSITION_TYPE_SELL
                    else mt5.POSITION_TYPE_SELL
                ),
                "position": position.ticket,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            logger.info(f"Sending order: {request}")

            result = mt5.order_send(request)
            logger.info(f"Order result: {result}")

            results.append(result)

        return results

    def remove_pending_orders(self):
        orders = mt5.orders_get(symbol=self.symbol)

        results = []

        for order in orders:
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "ticket": order.ticket,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            logger.info(f"Sending order: {request}")

            result = mt5.order_send(request)
            logger.info(f"Order result: {result}")

            results.append(result)

        return results

    def martingale_strategy(self, order_type, price):
        entry_price = price

        for step in range(1, self.max_steps + 1):
            lot = self.initial_lot * (self.multiplier ** (step - 1))

            tp_price, sl_price = self.calculate_entry(order_type, entry_price)

            if step == 1:
                self.send_order(order_type, step, lot, entry_price, tp_price, sl_price)
            else:
                if order_type == "buy":
                    type = "buy_limit"
                elif order_type == "sell":
                    type = "sell_limit"
                else:
                    raise ValueError("Invalid order type")

                self.send_order(type, step, lot, entry_price, tp_price, sl_price)

            entry_price = sl_price

    def run(self):
        self._get_account_info()
        self._get_symbol_info()
        self._get_strategy_info()

        while True:
            rates = self.copy_rates(200)

            last_rsi = rates["rsi"].iloc[-1]
            logger.info(f"Last RSI: {last_rsi}")

            last_tick = mt5.symbol_info_tick(self.symbol)
            logger.info(f"Last tick: {last_tick}")

            total_positions = self.total_positions()
            total_profit = self.total_profit()

            logger.info(f"Total positions: {total_positions}")
            logger.info(f"Total profit: {total_profit}")

            if last_rsi > self.rsi_overbought:
                logger.info("Signal Detected! RSI is overbought...")

                if total_positions > 0:
                    logger.info("Checking position...")
                    if self.validate_position("sell") == False:
                        logger.info("Position is not valid. Closing all positions...")

                        self.close_all_positions()
                        self.remove_pending_orders()
                    else:
                        logger.info("Position is valid. Skipping...")
                        time.sleep(1)
                        continue

                price = last_tick.bid

                if self.martingale_mode:
                    self.martingale_strategy("sell", price)
                else:
                    tp_price, sl_price = self.calculate_entry("sell", price)
                    self.send_order(
                        "sell", 1, self.initial_lot, price, tp_price, sl_price
                    )

            elif last_rsi < self.rsi_oversold:
                logger.info("Signal Detected! RSI is oversold....")

                if total_positions > 0:
                    logger.info("Checking position...")

                    if self.validate_position("buy") == False:
                        logger.info("Position is not valid. Closing all positions...")

                        self.close_all_positions()
                        self.remove_pending_orders()
                    else:
                        logger.info("Position is valid. Skipping...")
                        time.sleep(1)
                        continue

                price = last_tick.ask

                if self.martingale_mode:
                    self.martingale_strategy("buy", price)
                else:
                    tp_price, sl_price = self.calculate_entry("buy", price)
                    self.send_order(
                        "buy", 1, self.initial_lot, price, tp_price, sl_price
                    )
            else:
                logger.info("Waiting for RSI to reach oversold/overbought...")

                if total_positions == 0:
                    self.remove_pending_orders()

                time.sleep(1)
                continue

            time.sleep(1)


def main():
    try:
        logger.add("logs/log_{time}.log", level="DEBUG")

        if not mt5.initialize():
            logger.error("initialize() failed, error code =", mt5.last_error())
            quit()

        symbol = str(input("Symbol: "))

        timeframe = str(input("Timeframe (default: M1): ") or "M1").upper()
        if timeframe == "M1":
            timeframe = mt5.TIMEFRAME_M1
        elif timeframe == "M5":
            timeframe = mt5.TIMEFRAME_M5
        elif timeframe == "M15":
            timeframe = mt5.TIMEFRAME_M15
        elif timeframe == "M30":
            timeframe = mt5.TIMEFRAME_M30
        elif timeframe == "H1":
            timeframe = mt5.TIMEFRAME_H1
        elif timeframe == "H4":
            timeframe = mt5.TIMEFRAME_H4

        rsi_period = int(input("RSI Period (default: 14): ") or 14)
        rsi_oversold = int(input("RSI Oversold (default: 30): ") or 30)
        rsi_overbought = int(input("RSI Overbought (default: 70): ") or 70)
        initial_lot = float(input("Initial Lot (default: 0.01): ") or 0.01)
        martingale_mode = str(input("Martingale Mode (Y/N): ")).upper() == "Y"

        if martingale_mode:
            max_steps = int(input("Max Steps (default: 5): ") or 5)
            multiplier = int(input("Multiplier (default: 2): ") or 2)
        else:
            max_steps = 1
            multiplier = 1

        take_profit = float(input("Take Profit (default: 15): ") or 15)
        stop_loss = float(input("Stop Loss (default: 10): ") or 10)

        tradingBot = TradingBot(
            symbol,
            timeframe,
            rsi_period,
            rsi_oversold,
            rsi_overbought,
            initial_lot,
            martingale_mode,
            max_steps,
            multiplier,
            take_profit,
            stop_loss,
        )
        tradingBot.run()
    except KeyboardInterrupt as e:
        logger.error(e)
        quit()
    except Exception as e:
        logger.error(e)
        quit()


if __name__ == "__main__":
    main()
