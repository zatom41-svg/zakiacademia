"""
SupertrendTrend - suivi de tendance avec l'indicateur Supertrend.

Plus réactif que MomentumTrend : entre dès que le Supertrend change de sens,
filtré par une EMA longue et l'ADX.

  Entrée long  : Supertrend passe haussier ET clôture > EMA lente ET ADX > seuil
  Entrée short : symétrique
  Sortie       : Supertrend repasse dans l'autre sens
  Stop         : suiveur ATR
"""

import numpy as np
from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import CategoricalParameter, DecimalParameter, IntParameter

from za_common import ZaBase


def supertrend(df: DataFrame, period: int, mult: float) -> np.ndarray:
    """Retourne la direction du Supertrend : +1 haussier, -1 baissier."""
    atr = ta.ATR(df, timeperiod=period).to_numpy()
    hl2 = ((df["high"] + df["low"]) / 2).to_numpy()
    close = df["close"].to_numpy()
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    n = len(df)
    fu, fl = upper.copy(), lower.copy()
    direction = np.ones(n)
    for i in range(1, n):
        if np.isnan(atr[i - 1]):
            continue
        fu[i] = upper[i] if (upper[i] < fu[i - 1] or close[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lower[i] if (lower[i] > fl[i - 1] or close[i - 1] < fl[i - 1]) else fl[i - 1]
        if direction[i - 1] < 0 and close[i] > fu[i - 1]:
            direction[i] = 1
        elif direction[i - 1] > 0 and close[i] < fl[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]
    direction[np.isnan(atr)] = 0
    return direction


class SupertrendTrend(ZaBase):
    timeframe = "4h"
    startup_candle_count = 250

    st_period = CategoricalParameter([7, 10, 14], default=10, space="buy")
    st_mult = CategoricalParameter([2.0, 3.0, 4.0], default=3.0, space="buy")
    ema_slow = CategoricalParameter([100, 200], default=200, space="buy")
    adx_min = IntParameter(10, 30, default=18, space="buy")
    atr_stop_mult = DecimalParameter(2.0, 5.0, default=3.5, decimals=1, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        for p in self.ema_slow.range:
            dataframe[f"ema_{p}"] = ta.EMA(dataframe, timeperiod=p)
        for p in self.st_period.range:
            for m in self.st_mult.range:
                dataframe[f"st_{p}_{m}"] = supertrend(dataframe, p, m)
        return dataframe

    def _st(self, df: DataFrame):
        return df[f"st_{self.st_period.value}_{self.st_mult.value}"]

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        st = self._st(dataframe)
        slow = dataframe[f"ema_{self.ema_slow.value}"]
        trending = dataframe["adx"] > self.adx_min.value
        flip_up = (st > 0) & (st.shift(1) < 0)
        flip_down = (st < 0) & (st.shift(1) > 0)

        dataframe.loc[
            flip_up & (dataframe["close"] > slow) & trending & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "st_up")
        dataframe.loc[
            flip_down & (dataframe["close"] < slow) & trending & (dataframe["volume"] > 0),
            ["enter_short", "enter_tag"],
        ] = (1, "st_down")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        st = self._st(dataframe)
        dataframe.loc[st < 0, ["exit_long", "exit_tag"]] = (1, "st_flip")
        dataframe.loc[st > 0, ["exit_short", "exit_tag"]] = (1, "st_flip")
        return dataframe
