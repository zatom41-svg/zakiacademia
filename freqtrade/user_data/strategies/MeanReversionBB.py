"""
MeanReversionBB - retour à la moyenne sur les excès (Bollinger + RSI).

Famille OPPOSÉE au suivi de tendance : elle gagne dans les marchés sans
tendance nette et perd quand une tendance forte démarre. On ne l'active que
quand l'ADX est bas, et seulement dans le sens de la tendance de fond
(on achète les creux au-dessus de l'EMA 200, on vend les pics en dessous).

  Entrée long  : clôture < bande basse ET RSI < seuil ET ADX < seuil ET clôture > EMA 200
  Entrée short : clôture > bande haute ET RSI > 100-seuil ET ADX < seuil ET clôture < EMA 200
  Sortie       : retour à la moyenne (bande du milieu)
  Stop         : FIXE, ATR x mult depuis le prix d'entrée (pas de suiveur)
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import CategoricalParameter, DecimalParameter, IntParameter

from za_common import ZaBase


class MeanReversionBB(ZaBase):
    timeframe = "1h"
    startup_candle_count = 250
    trailing_atr = False

    bb_period = CategoricalParameter([20, 30], default=20, space="buy")
    bb_std = CategoricalParameter([2.0, 2.5, 3.0], default=2.5, space="buy")
    rsi_low = IntParameter(15, 35, default=25, space="buy")
    adx_max = IntParameter(15, 35, default=25, space="buy")
    atr_stop_mult = DecimalParameter(1.0, 3.5, default=2.0, decimals=1, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        for p in self.bb_period.range:
            mid = dataframe["close"].rolling(p).mean()
            sd = dataframe["close"].rolling(p).std()
            dataframe[f"bb_mid_{p}"] = mid
            for s in self.bb_std.range:
                dataframe[f"bb_up_{p}_{s}"] = mid + s * sd
                dataframe[f"bb_lo_{p}_{s}"] = mid - s * sd
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        p, s = self.bb_period.value, self.bb_std.value
        ranging = dataframe["adx"] < self.adx_max.value
        dataframe.loc[
            (dataframe["close"] < dataframe[f"bb_lo_{p}_{s}"])
            & (dataframe["rsi"] < self.rsi_low.value)
            & ranging & (dataframe["close"] > dataframe["ema_200"]) & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "bb_dip")
        dataframe.loc[
            (dataframe["close"] > dataframe[f"bb_up_{p}_{s}"])
            & (dataframe["rsi"] > 100 - self.rsi_low.value)
            & ranging & (dataframe["close"] < dataframe["ema_200"]) & (dataframe["volume"] > 0),
            ["enter_short", "enter_tag"],
        ] = (1, "bb_spike")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        mid = dataframe[f"bb_mid_{self.bb_period.value}"]
        dataframe.loc[dataframe["close"] > mid, ["exit_long", "exit_tag"]] = (1, "mean")
        dataframe.loc[dataframe["close"] < mid, ["exit_short", "exit_tag"]] = (1, "mean")
        return dataframe
