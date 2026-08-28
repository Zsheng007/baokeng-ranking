try:
    import tushare as ts
    print('tushare installed:', ts.__version__)
    try:
        pro = ts.pro_api()
        df = pro.stock_st(trade_date='20260806')
        print('records:', len(df))
        print(df.head(10).to_string())
    except Exception as e:
        print('API error:', e)
except ImportError as e:
    print('tushare not installed:', e)
