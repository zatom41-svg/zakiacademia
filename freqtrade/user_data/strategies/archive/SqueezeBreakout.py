"""
SqueezeBreakout - cassure après compression de volatilité (« squeeze »).

Idée : quand les bandes de Bollinger passent à l'intérieur des canaux de
Keltner, le marché se comprime ; la sortie de compression donne souvent un
mouvement directionnel.

  Entrée long  : il y a eu un squeeze dans les K dernières bougies,
                 clôture > bande de Bollinger haute, momentum > 0, clôture > EMA 200
  Entrée short : symétrique
  Sortie       : clôture repasse sous l'EMA 20 (long) / au-dessus (short)
  Stop         : suiveur ATR
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import DecimalParameter, IntParameter

from za_common import ZaBase


class SqueezeBreakout(ZaBase):
    timeframe = "1h"
    startup_candle_count = 250

    squeeze_lookback = IntParameter(3, 20, default=6, space="buy")
    kc_mult = DecimalParameter(1.0, 2.0, default=1.5, decimals=1, space="buy")
    atr_stop_mult = DecimalParameter(1.5, 4.0, default=2.5, decimals=1, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        mid = dataframe["close"].rolling(20).mean()
        sd = dataframe["close"].rolling(20).std()
        dataframe["bb_up"] = mid + 2 * sd
        dataframe["bb_lo"] = mid - 2 * sd
        dataframe["mom"] = dataframe["close"] - dataframe["close"].shift(12)
        atr20 = ta.ATR(dataframe, timeperiod=20)
        for m in self.kc_mult.range:
            kc_up = dataframe["ema_20"] + m * atr20
            kc_lo = dataframe["ema_20"] - m * atr20
            dataframe[f"sq_{m}"] = ((dataframe["bb_up"] < kc_up) & (dataframe["bb_lo"] > kc_lo)).astype(int)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        sq = dataframe[f"sq_{self.kc_mult.value}"]
        recent_squeeze = sq.rolling(self.squeeze_lookback.value).max().shift(1) > 0
        dataframe.loc[
            recent_squeeze & (dataframe["close"] > dataframe["bb_up"]) & (dataframe["mom"] > 0)
            & (dataframe["close"] > dataframe["ema_200"]) & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "squeeze_up")
        dataframe.loc[
            recent_squeeze & (dataframe["close"] < dataframe["bb_lo"]) & (dataframe["mom"] < 0)
            & (dataframe["close"] < dataframe["ema_200"]) & (dataframe["volume"] > 0),
            ["enter_short", "enter_tag"],
        ] = (1, "squeeze_down")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] < dataframe["ema_20"], ["exit_long", "exit_tag"]] = (1, "ema20")
        dataframe.loc[dataframe["close"] > dataframe["ema_20"], ["exit_short", "exit_tag"]] = (1, "ema20")
        return dataframe
