"""
Briques communes à toutes les stratégies zakiacademia :
  - levier réglable (config "za_leverage")
  - taille de position calculée sur le risque (config "za_risk_per_trade")
  - stop suiveur ATR (ne fait que se resserrer)
  - protections anti-série de pertes

Les stratégies héritent de ZaBase et définissent `atr_stop_mult`
(nombre ou DecimalParameter) et la colonne "atr" dans populate_indicators.
"""

from datetime import datetime

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_absolute


class ZaBase(IStrategy):
    INTERFACE_VERSION = 3
    can_short = True
    minimal_roi = {"0": 100}
    stoploss = -0.25  # filet de sécurité ; le vrai stop est custom_stoploss
    use_custom_stoploss = True
    process_only_new_candles = True

    # Stop suiveur ATR. Si False : stop fixe posé à l'entrée (mean reversion).
    trailing_atr = True

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 4,
                "stop_duration_candles": 12,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 48,
                "trade_limit": 5,
                "stop_duration_candles": 24,
                "max_allowed_drawdown": 0.25,
            },
        ]

    # --- helpers --------------------------------------------------------
    def _atr_mult(self) -> float:
        m = self.atr_stop_mult
        return float(getattr(m, "value", m))

    def _last_atr(self, pair: str) -> float | None:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return None
        atr = df["atr"].iat[-1]
        return float(atr) if atr == atr else None  # NaN -> None

    def _entry_atr(self, pair: str, trade: Trade) -> float | None:
        """ATR de la bougie de signal (mémorisé dans le trade)."""
        stored = trade.get_custom_data("entry_atr")
        if stored:
            return float(stored)
        atr = self._last_atr(pair)
        if atr:
            trade.set_custom_data("entry_atr", atr)
        return atr

    # --- callbacks Freqtrade ---------------------------------------------
    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float | None:
        if self.trailing_atr:
            atr = self._last_atr(pair)
            if atr is None:
                return None
            distance = atr * self._atr_mult()
            ref = current_rate
        else:
            atr = self._entry_atr(pair, trade)
            if atr is None:
                return None
            distance = atr * self._atr_mult()
            ref = trade.open_rate
        stop_rate = ref + distance if trade.is_short else ref - distance
        return stoploss_from_absolute(
            stop_rate, current_rate, is_short=trade.is_short, leverage=trade.leverage
        )

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """Taille la position pour perdre ~za_risk_per_trade du portefeuille au stop.

        Le levier ne change PAS la perte au stop : il réduit seulement la marge
        immobilisée (et rapproche le prix de liquidation).
        """
        atr = self._last_atr(pair)
        if atr is None or current_rate <= 0:
            return proposed_stake
        stop_pct = atr * self._atr_mult() / current_rate
        if stop_pct <= 0:
            return proposed_stake
        # Avec trop de levier, la liquidation arrive AVANT le stop : on refuse
        # le trade plutôt que de risquer toute la marge.
        if stop_pct * max(leverage, 1.0) > 0.8:
            return 0
        risk = float(self.config.get("za_risk_per_trade", 0.02))
        wallet = self.wallets.get_total_stake_amount()
        stake = wallet * risk / stop_pct / max(leverage, 1.0)
        return max(min(stake, max_stake), min_stake or 0)

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        return min(float(self.config.get("za_leverage", 2.0)), max_leverage)
