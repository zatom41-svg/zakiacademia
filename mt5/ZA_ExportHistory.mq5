//+------------------------------------------------------------------+
//|                                            ZA_ExportHistory.mq5  |
//|  Script : exporte l'historique H1 de plusieurs symboles en CSV   |
//|  dans  MQL5\Files\za_export\<symbole>_H1.csv                     |
//|                                                                  |
//|  Utilisation : glisser le script sur n'importe quel graphique.   |
//|  Heure = heure du serveur du courtier (FTMO : UTC+2 / UTC+3).    |
//+------------------------------------------------------------------+
#property copyright "zakiacademia"
#property version   "1.00"
#property script_show_inputs

input string InpSymbols = "XAUUSD,US100.cash,US30.cash,US500.cash,GER40.cash,UK100.cash,JP225.cash,EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,USDCHF,NZDUSD,EURJPY,GBPJPY,EURGBP,XAGUSD,USOIL.cash,BTCUSD,ETHUSD"; // Symboles, separes par des virgules
input datetime InpFrom = D'2023.01.01';  // Depuis
input ENUM_TIMEFRAMES InpTf = PERIOD_H1; // Unite de temps

void OnStart()
{
   string list[];
   int n = StringSplit(InpSymbols, ',', list);
   int ok = 0;
   for(int k = 0; k < n; k++)
   {
      string sym = list[k];
      StringTrimLeft(sym);
      StringTrimRight(sym);
      if(sym == "") continue;
      if(!SymbolSelect(sym, true))
      {
         PrintFormat("%s : symbole introuvable chez ce courtier, ignore", sym);
         continue;
      }

      // Laisse au terminal le temps de telecharger l'historique
      MqlRates rates[];
      int got = -1;
      for(int attempt = 0; attempt < 20 && got <= 0; attempt++)
      {
         got = CopyRates(sym, InpTf, InpFrom, TimeCurrent(), rates);
         if(got <= 0) Sleep(1000);
      }
      if(got <= 0)
      {
         PrintFormat("%s : pas d'historique (erreur %d)", sym, GetLastError());
         continue;
      }

      string name = "za_export\\" + sym + "_H1.csv";
      int h = FileOpen(name, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
      if(h == INVALID_HANDLE)
      {
         PrintFormat("%s : impossible d'ecrire %s", sym, name);
         continue;
      }
      FileWrite(h, "time_server", "open", "high", "low", "close", "spread_points");
      for(int i = 0; i < got; i++)
         FileWrite(h, (long)rates[i].time, rates[i].open, rates[i].high, rates[i].low, rates[i].close, rates[i].spread);
      FileClose(h);
      ok++;
      PrintFormat("%s : %d bougies exportees", sym, got);
   }
   PrintFormat("Termine : %d symboles exportes dans %s\\MQL5\\Files\\za_export",
               ok, TerminalInfoString(TERMINAL_DATA_PATH));
   Alert("Export termine : ", ok, " symboles. Dossier : MQL5\\Files\\za_export");
}
