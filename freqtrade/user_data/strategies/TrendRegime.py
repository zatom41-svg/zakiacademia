"""
TrendRegime - momentum 30 jours + filtre de régime BTC + taille selon la volatilité.

Meilleure famille trouvée par tools/explore.py sur 2022-2026 (OKX futures,
8 grosses cryptos). Idée, appuyée par la littérature (« time-series momentum ») :
  - on n'achète une crypto que si elle a monté sur les N derniers jours
  - et seulement quand le BTC est au-dessus de sa moyenne 100 jours
    (en marché baissier, on reste en dollars)
  - la taille de chaque position est inversement proportionnelle à sa
    volatilité : moins de mise sur les cryptos qui bougent beaucoup

Long uniquement. Décision à la clôture journalière.
"""

import numpy as np
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IntParameter, merge_informative_pair

from za_common import ZaBase


class TrendRegime(ZaBase):
    timeframe = "1d"
    can_short = False
    startup_candle_count = 120

    lookback = IntParameter(14, 90, default=30, space="buy")
    btc_sma = IntParameter(50, 200, default=100, space="buy")
    vol_target = DecimalParameter(0.2, 1.0, default=0.5, decimals=2, space="buy")

    # Stop « catastrophe » large : la sortie normale se fait par le signal
    atr_stop_mult = 5.0

    btc_pair = "BTC/USDT:USDT"

    def informative_pairs(self):
        return [(self.btc_pair, self.timeframe)]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        import talib.abstract as ta

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["ret"] = dataframe["close"].pct_change(self.lookback.value)
        dataframe["vol"] = dataframe["close"].pct_change().rolling(30).std() * np.sqrt(365)

        btc = self.dp.get_pair_dataframe(self.btc_pair, self.timeframe).copy()
        btc["btc_up"] = (btc["close"] > btc["close"].rolling(self.btc_sma.value).mean()).astype(int)
        dataframe = merge_informative_pair(
            dataframe, btc[["date", "btc_up"]], self.timeframe, self.timeframe, ffill=True
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["ret"] > 0) & (dataframe[f"btc_up_{self.timeframe}"] == 1)
            & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "momentum_regime")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["ret"] <= 0) | (dataframe[f"btc_up_{self.timeframe}"] == 0),
            ["exit_long", "exit_tag"],
        ] = (1, "regime_off")
        return dataframe

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs) -> float:
        """Part égale du portefeuille par paire, réduite si la paire est très volatile."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return proposed_stake
        vol = float(df["vol"].iat[-1])
        if not vol or vol != vol:
            return proposed_stake
        n_slots = max(int(self.config.get("max_open_trades", 8)), 1)
        weight = min(self.vol_target.value / vol, 1.0)
        stake = self.wallets.get_total_stake_amount() / n_slots * weight
        return max(min(stake, max_stake), min_stake or 0)
