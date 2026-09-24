"""
DipReversion - achat de creux brutaux dans une tendance haussière (type Connors RSI).

Famille opposée au suivi de tendance, donc utile en complément de TrendRegime :
elle achète quand une crypto a beaucoup baissé en 2-3 jours alors que sa
tendance de fond (moyenne 100 jours) reste haussière, et revend au rebond.

  Entrée : RSI(3) < seuil ET clôture > SMA 100 ET BTC au-dessus de sa SMA 100
  Sortie : RSI(3) > seuil de sortie, ou clôture < SMA 100 x 0,9
  Stop   : fixe, ATR x mult depuis l'entrée

Long uniquement, décision à la clôture journalière. Peu de trades, petits
gains, pertes faibles (exploration 2022-2026 : environ +8 % par période à x1,
baisse max ~3 %).
"""

import numpy as np
from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import DecimalParameter, IntParameter, merge_informative_pair

from za_common import ZaBase


class DipReversion(ZaBase):
    timeframe = "1d"
    can_short = False
    startup_candle_count = 120
    trailing_atr = False

    rsi_entry = IntParameter(5, 30, default=10, space="buy")
    trend_sma = IntParameter(50, 200, default=100, space="buy")
    rsi_exit = IntParameter(50, 80, default=60, space="sell")
    atr_stop_mult = DecimalParameter(1.5, 4.0, default=3.0, decimals=1, space="sell")

    btc_pair = "BTC/USDT:USDT"

    def informative_pairs(self):
        return [(self.btc_pair, self.timeframe)]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["rsi3"] = ta.RSI(dataframe, timeperiod=3)
        dataframe["sma"] = dataframe["close"].rolling(self.trend_sma.value).mean()
        dataframe["vol"] = dataframe["close"].pct_change().rolling(30).std() * np.sqrt(365)
        btc = self.dp.get_pair_dataframe(self.btc_pair, self.timeframe).copy()
        btc["btc_up"] = (btc["close"] > btc["close"].rolling(100).mean()).astype(int)
        return merge_informative_pair(dataframe, btc[["date", "btc_up"]], self.timeframe, self.timeframe, ffill=True)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["rsi3"] < self.rsi_entry.value) & (dataframe["close"] > dataframe["sma"])
            & (dataframe[f"btc_up_{self.timeframe}"] == 1) & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "dip")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["rsi3"] > self.rsi_exit.value) | (dataframe["close"] < dataframe["sma"] * 0.9),
            ["exit_long", "exit_tag"],
        ] = (1, "rebound")
        return dataframe

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs) -> float:
        """Part égale par paire, réduite si la paire est très volatile."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return proposed_stake
        vol = float(df["vol"].iat[-1])
        if not vol or vol != vol:
            return proposed_stake
        n_slots = max(int(self.config.get("max_open_trades", 8)), 1)
        stake = self.wallets.get_total_stake_amount() / n_slots * min(0.5 / vol, 1.0)
        return max(min(stake, max_stake), min_stake or 0)
