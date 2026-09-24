//+------------------------------------------------------------------+
//|                                          FTMO_TrendBreakout.mq5  |
//|  Robot de suivi de tendance / cassure avec protections FTMO.     |
//|                                                                  |
//|  Logique :                                                       |
//|   - Achat  : cloture > plus haut des N bougies precedentes       |
//|              ET cloture > EMA 200 (tendance de fond haussiere)   |
//|   - Vente  : symetrique                                          |
//|   - Stop   : ATR x multiplicateur, puis break-even a +1R,        |
//|              puis stop suiveur (chandelier ATR)                  |
//|   - Taille : calculee pour risquer X % du compte par trade       |
//|                                                                  |
//|  Protections FTMO (codees en dur, avant les limites officielles):|
//|   - perte journaliere : coupe tout a -4 % (limite FTMO : -5 %)   |
//|   - perte max         : coupe tout a -9 % (limite FTMO : -10 %)  |
//|   - objectif atteint  : ferme tout et arrete de trader           |
//|   - fermeture avant le week-end                                  |
//+------------------------------------------------------------------+
#property copyright "zakiacademia"
#property version   "1.20"

#include <Trade/Trade.mqh>

enum ENUM_ZA_MODE
{
   ZA_BREAKOUT = 0, // Cassure de tendance (Donchian + EMA 200)
   ZA_RSI2     = 1  // Retour a la moyenne RSI(2)
};

//--- Strategie
input group "=== Strategie ==="
input ENUM_ZA_MODE    InpMode           = ZA_BREAKOUT; // Strategie
input ENUM_TIMEFRAMES InpTimeframe      = PERIOD_H1; // Unite de temps
input int             InpBreakoutBars   = 20;        // Cassure : nombre de bougies (Donchian)
input int             InpEmaPeriod      = 200;       // Filtre de tendance : EMA
input int             InpAtrPeriod      = 14;        // ATR : periode
input double          InpSlAtrMult      = 3.0;       // Stop initial = ATR x
input double          InpTrailAtrMult   = 3.0;       // Stop suiveur = ATR x (mode cassure)
input double          InpBreakevenR     = 1.0;       // Break-even a +xR (0 = off)
input double          InpTakeProfitR    = 0.0;       // Take profit a +xR (0 = laisser courir)
input bool            InpAllowLong      = true;      // Autoriser les achats
input bool            InpAllowShort     = true;      // Autoriser les ventes

input group "=== Mode RSI(2) ==="
input double          InpRsiLevel       = 5;         // Achat si RSI(2) < x, vente si > 100 - x
input double          InpRsiTpAtr       = 1.0;       // Objectif = ATR x
input int             InpRsiMaxBars     = 6;         // Sortie apres x bougies au maximum

//--- Risque
input group "=== Risque ==="
input double InpRiskPercent       = 1.0;  // Risque par trade (% du solde) : 0.5 prudent, 1.0 normal
input int    InpMaxTradesPerDay   = 3;    // Trades max par jour (ce symbole)
input double InpMaxSpreadPoints   = 0;    // Spread max en points (0 = pas de filtre)

//--- Regles FTMO
input group "=== Regles FTMO ==="
input double InpInitialBalance    = 0;    // Capital initial du challenge (0 = solde au 1er lancement)
input double InpDailyLossPct      = 4.0;  // Coupure perte journaliere en % (FTMO : 5)
input double InpMaxLossPct        = 9.0;  // Coupure perte max en % (FTMO : 10)
input double InpProfitTargetPct   = 10.0; // Objectif en % (phase 1 : 10, phase 2 : 5, 0 = off)
input bool   InpStopAtTarget      = true; // Tout fermer et arreter une fois l'objectif atteint

//--- Horaires (heure serveur)
input group "=== Horaires (heure serveur) ==="
input int  InpStartHour           = 8;    // Debut des entrees
input int  InpEndHour             = 20;   // Fin des entrees
input bool InpCloseBeforeWeekend  = true; // Fermer les positions le vendredi
input int  InpFridayCloseHour     = 20;   // Heure de fermeture du vendredi

input group "=== Divers ==="
input ulong InpMagic              = 41410001; // Numero magique

//--- Etat
CTrade   trade;
int      hEma = INVALID_HANDLE;
int      hAtr = INVALID_HANDLE;
int      hRsi = INVALID_HANDLE;
datetime lastBarTime   = 0;
datetime lastManageMin = 0;
datetime currentDay    = 0;
double   dayStartBalance = 0;
double   initialBalance  = 0;
bool     haltedToday   = false;
int      tradesToday   = 0;

string GvKey(const string name)
{
   return StringFormat("ZA_%I64u_%I64d_%s", InpMagic, AccountInfoInteger(ACCOUNT_LOGIN), name);
}

//+------------------------------------------------------------------+
int OnInit()
{
   hEma = iMA(_Symbol, InpTimeframe, InpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   hAtr = iATR(_Symbol, InpTimeframe, InpAtrPeriod);
   hRsi = iRSI(_Symbol, InpTimeframe, 2, PRICE_CLOSE);
   if(hEma == INVALID_HANDLE || hAtr == INVALID_HANDLE || hRsi == INVALID_HANDLE)
   {
      Print("Erreur : impossible de creer les indicateurs");
      return INIT_FAILED;
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(20);

   // Capital initial : saisi, sinon memorise au premier lancement
   if(InpInitialBalance > 0)
      initialBalance = InpInitialBalance;
   else if(GlobalVariableCheck(GvKey("init")))
      initialBalance = GlobalVariableGet(GvKey("init"));
   else
   {
      initialBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      GlobalVariableSet(GvKey("init"), initialBalance);
   }

   StartNewDayIfNeeded();
   PrintFormat("EA demarre. Capital initial=%.2f, risque=%.2f%%, coupure jour=%.1f%%, coupure max=%.1f%%",
               initialBalance, InpRiskPercent, InpDailyLossPct, InpMaxLossPct);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hEma != INVALID_HANDLE) IndicatorRelease(hEma);
   if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr);
   if(hRsi != INVALID_HANDLE) IndicatorRelease(hRsi);
   Comment("");
}

//+------------------------------------------------------------------+
void OnTick()
{
   StartNewDayIfNeeded();

   if(IsPermanentlyHalted())
   {
      CloseAll("EA arrete (objectif atteint ou perte max)");
      ShowStatus("ARRETE");
      return;
   }

   if(!CheckRiskGuards())
   {
      ShowStatus("PAUSE jusqu'a demain");
      return;
   }

   if(InpCloseBeforeWeekend && IsFridayClose())
   {
      CloseAll("Fermeture avant le week-end");
      ShowStatus("Week-end");
      return;
   }

   // Stop suiveur : une fois par minute suffit pour un EA en H1
   // (le faire a chaque tick rendait le testeur tres lent)
   datetime nowMin = TimeCurrent() - TimeCurrent() % 60;
   if(nowMin != lastManageMin)
   {
      lastManageMin = nowMin;
      ManageOpenPosition();
   }

   // Signaux uniquement a l'ouverture d'une nouvelle bougie
   datetime barTime = iTime(_Symbol, InpTimeframe, 0);
   if(barTime == 0 || barTime == lastBarTime)
   {
      ShowStatus("Actif");
      return;
   }
   lastBarTime = barTime;

   CheckEntry();
   ShowStatus("Actif");
}

//+------------------------------------------------------------------+
//| Gestion du jour (FTMO : reset a minuit heure serveur CE(S)T)      |
//+------------------------------------------------------------------+
void StartNewDayIfNeeded()
{
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   t.hour = 0; t.min = 0; t.sec = 0;
   datetime today = StructToTime(t);
   if(today != currentDay)
   {
      currentDay      = today;
      dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      haltedToday     = false;
      tradesToday     = 0;
   }
}

bool IsPermanentlyHalted()
{
   return GlobalVariableCheck(GvKey("halt")) && GlobalVariableGet(GvKey("halt")) > 0;
}

void HaltPermanently(const string why)
{
   GlobalVariableSet(GvKey("halt"), 1);
   Print("ARRET DEFINITIF : ", why, " (supprimez la variable globale ", GvKey("halt"), " pour relancer)");
   CloseAll(why);
}

// Retourne false si on ne doit plus trader aujourd'hui
bool CheckRiskGuards()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);

   // Perte max (statique, FTMO 2-Step)
   double maxFloor = initialBalance * (1.0 - InpMaxLossPct / 100.0);
   if(equity <= maxFloor)
   {
      HaltPermanently(StringFormat("Perte max atteinte : equity %.2f <= %.2f", equity, maxFloor));
      return false;
   }

   // Objectif atteint
   if(InpProfitTargetPct > 0 && InpStopAtTarget)
   {
      double target = initialBalance * (1.0 + InpProfitTargetPct / 100.0);
      if(equity >= target)
      {
         HaltPermanently(StringFormat("Objectif atteint : equity %.2f >= %.2f", equity, target));
         return false;
      }
   }

   // Perte journaliere (FTMO : % du capital initial, depuis le solde de debut de journee)
   double dayFloor = dayStartBalance - initialBalance * InpDailyLossPct / 100.0;
   if(equity <= dayFloor)
   {
      if(!haltedToday)
         PrintFormat("Coupure journaliere : equity %.2f <= %.2f", equity, dayFloor);
      haltedToday = true;
   }
   if(haltedToday)
   {
      CloseAll("Coupure perte journaliere");
      return false;
   }
   return true;
}

bool IsFridayClose()
{
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   return (t.day_of_week == 5 && t.hour >= InpFridayCloseHour) || t.day_of_week == 6 || t.day_of_week == 0;
}

bool InTradingHours()
{
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   if(InpStartHour <= InpEndHour)
      return t.hour >= InpStartHour && t.hour < InpEndHour;
   return t.hour >= InpStartHour || t.hour < InpEndHour; // plage qui passe minuit
}

//+------------------------------------------------------------------+
//| Entrees                                                          |
//+------------------------------------------------------------------+
void CheckEntry()
{
   if(HasPosition()) return;
   if(tradesToday >= InpMaxTradesPerDay) return;
   if(!InTradingHours()) return;
   if(InpMaxSpreadPoints > 0 && SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPoints) return;

   double ema[], atr[];
   if(CopyBuffer(hEma, 0, 1, 1, ema) != 1) return;
   if(CopyBuffer(hAtr, 0, 1, 1, atr) != 1) return;

   double close1 = iClose(_Symbol, InpTimeframe, 1);
   // Plus haut / plus bas des N bougies AVANT la bougie de signal
   int hiIdx = iHighest(_Symbol, InpTimeframe, MODE_HIGH, InpBreakoutBars, 2);
   int loIdx = iLowest(_Symbol, InpTimeframe, MODE_LOW, InpBreakoutBars, 2);
   if(hiIdx < 0 || loIdx < 0 || close1 == 0) return;
   double channelHigh = iHigh(_Symbol, InpTimeframe, hiIdx);
   double channelLow  = iLow(_Symbol, InpTimeframe, loIdx);

   double slDist = atr[0] * InpSlAtrMult;
   if(slDist <= 0) return;

   if(InpMode == ZA_RSI2)
   {
      double rsi[];
      if(CopyBuffer(hRsi, 0, 1, 1, rsi) != 1) return;
      double tpDist = atr[0] * InpRsiTpAtr;
      if(InpAllowLong && rsi[0] < InpRsiLevel && close1 > ema[0])
         OpenTrade(ORDER_TYPE_BUY, slDist, tpDist);
      else if(InpAllowShort && rsi[0] > 100.0 - InpRsiLevel && close1 < ema[0])
         OpenTrade(ORDER_TYPE_SELL, slDist, tpDist);
      return;
   }

   if(InpAllowLong && close1 > channelHigh && close1 > ema[0])
      OpenTrade(ORDER_TYPE_BUY, slDist, 0);
   else if(InpAllowShort && close1 < channelLow && close1 < ema[0])
      OpenTrade(ORDER_TYPE_SELL, slDist, 0);
}

// tpDist > 0 : objectif fixe en prix ; sinon InpTakeProfitR (0 = pas d'objectif)
void OpenTrade(const ENUM_ORDER_TYPE type, const double slDist, const double tpDist)
{
   double lots = LotsForRisk(slDist);
   if(lots <= 0)
   {
      Print("Taille calculee trop petite pour le risque demande, trade ignore");
      return;
   }

   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double price  = (type == ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                                            : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = (type == ORDER_TYPE_BUY) ? price - slDist : price + slDist;
   double tp = 0;
   double tpD = (tpDist > 0) ? tpDist : slDist * InpTakeProfitR;
   if(tpD > 0)
      tp = (type == ORDER_TYPE_BUY) ? price + tpD : price - tpD;
   sl = NormalizeDouble(sl, digits);
   tp = NormalizeDouble(tp, digits);

   bool ok = (type == ORDER_TYPE_BUY) ? trade.Buy(lots, _Symbol, 0, sl, tp, "ZA trend")
                                      : trade.Sell(lots, _Symbol, 0, sl, tp, "ZA trend");
   if(ok && trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
      tradesToday++;
      // Memorise la distance de stop initiale (1R) pour le break-even
      GlobalVariableSet(GvKey("r_" + _Symbol), slDist);
   }
   else
      PrintFormat("Echec ordre : %u %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

// Lots pour perdre InpRiskPercent % du solde si le stop est touche
double LotsForRisk(const double slDist)
{
   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0;
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue <= 0) tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0) return 0;

   double lossPerLot = slDist / tickSize * tickValue;
   if(lossPerLot <= 0) return 0;

   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   double lots = MathFloor(riskMoney / lossPerLot / step) * step;
   if(lots < minV) return 0;          // ne jamais depasser le risque demande
   return MathMin(lots, maxV);
}

//+------------------------------------------------------------------+
//| Gestion de la position ouverte : break-even puis stop suiveur     |
//+------------------------------------------------------------------+
void ManageOpenPosition()
{
   if(!SelectOwnPosition()) return;

   // Mode RSI(2) : pas de stop suiveur, sortie au bout de InpRsiMaxBars bougies
   if(InpMode == ZA_RSI2)
   {
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if(TimeCurrent() - opened >= (long)InpRsiMaxBars * PeriodSeconds(InpTimeframe))
         trade.PositionClose((ulong)PositionGetInteger(POSITION_TICKET));
      return;
   }

   double atr[];
   if(CopyBuffer(hAtr, 0, 1, 1, atr) != 1) return;

   long   type   = PositionGetInteger(POSITION_TYPE);
   double open   = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl     = PositionGetDouble(POSITION_SL);
   double tp     = PositionGetDouble(POSITION_TP);
   ulong  ticket = (ulong)PositionGetInteger(POSITION_TICKET);
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double oneR   = GlobalVariableCheck(GvKey("r_" + _Symbol)) ? GlobalVariableGet(GvKey("r_" + _Symbol))
                                                               : atr[0] * InpSlAtrMult;
   double newSl  = sl;

   if(type == POSITION_TYPE_BUY)
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(InpBreakevenR > 0 && bid - open >= oneR * InpBreakevenR)
         newSl = MathMax(newSl, open);
      if(bid - open >= oneR) // on ne suit qu'apres +1R pour laisser respirer le trade
         newSl = MathMax(newSl, bid - atr[0] * InpTrailAtrMult);
      newSl = NormalizeDouble(newSl, digits);
      if(newSl > sl + _Point && newSl < bid)
         trade.PositionModify(ticket, newSl, tp);
   }
   else
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(InpBreakevenR > 0 && open - ask >= oneR * InpBreakevenR)
         newSl = (sl == 0) ? open : MathMin(newSl, open);
      if(open - ask >= oneR)
         newSl = (newSl == 0) ? ask + atr[0] * InpTrailAtrMult : MathMin(newSl, ask + atr[0] * InpTrailAtrMult);
      newSl = NormalizeDouble(newSl, digits);
      if((sl == 0 || newSl < sl - _Point) && newSl > ask)
         trade.PositionModify(ticket, newSl, tp);
   }
}

//+------------------------------------------------------------------+
//| Utilitaires                                                      |
//+------------------------------------------------------------------+
bool SelectOwnPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
   }
   return false;
}

bool HasPosition()
{
   return SelectOwnPosition();
}

// Ferme toutes les positions de cet EA (tous symboles, meme magic)
void CloseAll(const string why)
{
   bool closedSomething = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(trade.PositionClose(ticket))
         closedSomething = true;
   }
   if(closedSomething)
      Print("Positions fermees : ", why);
}

void ShowStatus(const string state)
{
   // Pas d'affichage pendant un backtest non visuel : gros gain de vitesse
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))
      return;
   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   double pnlPct   = (equity / initialBalance - 1.0) * 100.0;
   double dayPct   = (equity - dayStartBalance) / initialBalance * 100.0;
   Comment(StringFormat("ZA TrendBreakout [%s]\nCapital initial : %.2f\nEquity : %.2f (%+.2f%%)\n"
                        "Aujourd'hui : %+.2f%% (coupure a -%.1f%%)\nObjectif : +%.1f%%\nTrades aujourd'hui : %d/%d",
                        state, initialBalance, equity, pnlPct, dayPct, InpDailyLossPct,
                        InpProfitTargetPct, tradesToday, InpMaxTradesPerDay));
}
//+------------------------------------------------------------------+
