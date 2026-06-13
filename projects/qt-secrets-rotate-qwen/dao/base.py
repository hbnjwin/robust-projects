class BaseDAO:
    def get_daily_price(self, ts_code: str):
        raise NotImplementedError
