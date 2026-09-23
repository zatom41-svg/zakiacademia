"""
DonchianRegime - cassure journalière façon « Turtle traders », long uniquement,
avec filtre de régime BTC.

Remplace MomentumTrend (cassure 4h long/short), qui perdait sur les deux
périodes à cause des faux signaux et des frais. Sur bougies journalières,
en long uniquement et seulement quand le BTC est en tendance haussière,
la même idée devient rentable dans l'exploration 2022-2026.

  Entrée : clôture > plus haut des N jours précédents ET BTC > SMA 100
  Sortie : clôture < plus bas des M jours précédents, ou BTC repasse sous sa SMA 100
  Stop   : suiveur ATR large (catastrophe)
"""

import numpy as np
from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IntParameter, merge_informative_pair

from za_common import ZaBase


class DonchianRegime(ZaBase):
    timeframe = "1d"
    can_short = False
    startup_candle_count = 120

    entry_period = IntParameter(10, 55, default=20, space="buy")
    exit_period = IntParameter(5, 30, default=20, space="sell")
    atr_stop_mult = 5.0

    btc_pair = "BTC/USDT:USDT"

    def informative_pairs(self):
        return [(self.btc_pair, self.timeframe)]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["vol"] = dataframe["close"].pct_change().rolling(30).std() * np.sqrt(365)
        for p in set(self.entry_period.range) | set(self.exit_period.range):
            dataframe[f"hh_{p}"] = dataframe["high"].rolling(p).max().shift(1)
            dataframe[f"ll_{p}"] = dataframe["low"].rolling(p).min().shift(1)
        btc = self.dp.get_pair_dataframe(self.btc_pair, self.timeframe).copy()
        btc["btc_up"] = (btc["close"] > btc["close"].rolling(100).mean()).astype(int)
        return merge_informative_pair(dataframe, btc[["date", "btc_up"]], self.timeframe, self.timeframe, ffill=True)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] > dataframe[f"hh_{self.entry_period.value}"])
            & (dataframe[f"btc_up_{self.timeframe}"] == 1) & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "breakout")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe[f"ll_{self.exit_period.value}"])
            | (dataframe[f"btc_up_{self.timeframe}"] == 0),
            ["exit_long", "exit_tag"],
        ] = (1, "breakdown")
        return dataframe

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs) -> float:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return proposed_stake
        vol = float(df["vol"].iat[-1])
        if not vol or vol != vol:
            return proposed_stake
        n_slots = max(int(self.config.get("max_open_trades", 8)), 1)
        stake = self.wallets.get_total_stake_amount() / n_slots * min(0.5 / vol, 1.0)
        return max(min(stake, max_stake), min_stake or 0)
