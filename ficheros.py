
from TradingviewData import TradingViewData,Interval
import pandas as pd 
request = TradingViewData()

coins = ['BTCUSD', 'ETHUSD','XRPUSD', 'DOGEUSD','ADAUSD', 'SHIBUSD','DOTUSD', 'AAVEUSD', 'XLMUSD' ]

for coin in coins: 
    nifty_data = request.get_hist(symbol=coin,exchange='COINBASE',interval=Interval.daily,n_bars=1460)
    
    # Asegurar que el índice es datetime
    nifty_data = nifty_data.reset_index()
    nifty_data['datetime'] = pd.to_datetime(nifty_data['datetime'])  # Convertir a datetime si no lo está
    nifty_data.set_index('datetime', inplace=True)

    # Guardar los datos por año
    for year, data in nifty_data.groupby(nifty_data.index.year):
        data.to_csv(f"{coin}_{year}.csv", index=True)

    # nifty_data.to_csv(f"{coin}.csv", index=True)
