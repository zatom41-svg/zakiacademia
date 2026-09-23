"""
MomentumTrend - suivi de tendance par cassure (Donchian) pour crypto.

Pourquoi : le momentum / suivi de tendance est la famille de stratégies crypto
la mieux documentée (Liu & Tsyvinski, Review of Financial Studies 2021).

  Entrée long  : clôture > plus haut des N bougies précédentes
                 ET EMA rapide > EMA lente ET clôture > EMA lente ET ADX > seuil
  Entrée short : symétrique (futures uniquement)
  Sortie       : clôture sous le plus bas des M bougies, ou croisement des EMA
  Stop         : suiveur ATR (voir za_common.ZaBase)
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import CategoricalParameter, DecimalParameter, IntParameter

from za_common import ZaBase


class MomentumTrend(ZaBase):
    timeframe = "4h"
    startup_candle_count = 250

    breakout_period = IntParameter(10, 55, default=20, space="buy")
    ema_fast = CategoricalParameter([20, 50], default=50, space="buy")
    ema_slow = CategoricalParameter([100, 150, 200], default=200, space="buy")
    adx_min = IntParameter(15, 35, default=20, space="buy")
    exit_period = IntParameter(5, 30, default=10, space="sell")
    atr_stop_mult = DecimalParameter(1.5, 4.5, default=3.0, decimals=1, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        for p in set(self.ema_fast.range) | set(self.ema_slow.range):
            dataframe[f"ema_{p}"] = ta.EMA(dataframe, timeperiod=p)
        for p in set(self.breakout_period.range) | set(self.exit_period.range):
            # shift(1) : canal des bougies PRÉCÉDENTES (pas de biais du futur)
            dataframe[f"hh_{p}"] = dataframe["high"].rolling(p).max().shift(1)
            dataframe[f"ll_{p}"] = dataframe["low"].rolling(p).min().shift(1)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        fast = dataframe[f"ema_{self.ema_fast.value}"]
        slow = dataframe[f"ema_{self.ema_slow.value}"]
        bp = self.breakout_period.value
        trending = dataframe["adx"] > self.adx_min.value

        dataframe.loc[
            (dataframe["close"] > dataframe[f"hh_{bp}"]) & (fast > slow)
            & (dataframe["close"] > slow) & trending & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "breakout_up")
        dataframe.loc[
            (dataframe["close"] < dataframe[f"ll_{bp}"]) & (fast < slow)
            & (dataframe["close"] < slow) & trending & (dataframe["volume"] > 0),
            ["enter_short", "enter_tag"],
        ] = (1, "breakout_down")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        fast = dataframe[f"ema_{self.ema_fast.value}"]
        slow = dataframe[f"ema_{self.ema_slow.value}"]
        ep = self.exit_period.value
        dataframe.loc[
            (dataframe["close"] < dataframe[f"ll_{ep}"]) | (fast < slow),
            ["exit_long", "exit_tag"],
        ] = (1, "trend_end")
        dataframe.loc[
            (dataframe["close"] > dataframe[f"hh_{ep}"]) | (fast > slow),
            ["exit_short", "exit_tag"],
        ] = (1, "trend_end")
        return dataframe
