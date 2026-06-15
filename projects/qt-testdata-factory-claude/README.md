# qt-testdata-factory (l1-182)

| Field | Value |
|-------|-------|
| Question ID | l1-182 |
| Task Type | enhancement |
| App Domain | devtools_test |
| Language | python |
| Model | Claude |

## Query

现在测试要么连真实 PostgreSQL 数据库要么在测试里硬编码一堆 DataFrame，改起来很痛苦。我想建一个测试数据工厂模块 testing/market_data_factory.py，能按需生成各种行情场景的假数据。需要：1) 实现一个 MarketDataFactory 类，能生成指定股票数量、日期范围的日线 OHLCV 数据（DataFrame），价格走势要符合基本的金融常识——开盘价在前收盘价附近、最高最低价包含开收盘、成交量随波动率正相关，支持随机种子保证可复现；2) 提供预设场景方法：create_bull_market()、create_crash_scenario()、create_sideways_market()、create_limit_up_down()（涨跌停场景），每个场景返回的数据要有对应特征（比如连续涨停场景要有连续 10% 涨幅+成交量缩量）；3) 再做一个 FactorDataFactory，能生成与行情数据对齐的因子数据（momentum、volatility、turnover 等列），值域要合理；4) 用这个工厂重写 testing/ 下至少两个现有测试文件里的硬编码数据，确认测试仍然通过。
