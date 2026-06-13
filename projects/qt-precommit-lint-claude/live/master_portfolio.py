import numpy as np

class MasterPortfolio:

    def __init__(self, total_capital, target_vol=0.15):
        self.total_capital = total_capital
        self.strategy_accounts = {}
        self.total_equity = total_capital
        self.max_equity = total_capital
        self.max_drawdown = 0
        self.equity_curve = []
        self.target_vol = target_vol
        self.drawdown_control_triggered = False

    def add_strategy(self, name, account):
        self.strategy_accounts[name] = account

    def update_total_equity(self):
        total = 0
        for account in self.strategy_accounts.values():
            total += account.total_equity
        self.total_equity = total
        if total > self.max_equity:
            self.max_equity = total
        drawdown = (self.max_equity - total) / self.max_equity if self.max_equity else 0
        self.max_drawdown = max(self.max_drawdown, drawdown)
        return drawdown

    def compute_volatility(self, lookback=20):
        if len(self.equity_curve) < lookback + 1:
            return None
        returns = []
        for i in range(-lookback, 0):
            prev = self.equity_curve[i - 1]["equity"]
            curr = self.equity_curve[i]["equity"]
            if prev > 0:
                returns.append((curr - prev) / prev)
        if len(returns) < 2:
            return None
        return np.std(returns) * np.sqrt(252)

    def get_vol_target_leverage(self):
        """前瞻性 Vol Target：根据当前波动率计算新订单的仓位缩放比例"""
        vol = self.compute_volatility()
        if vol is None or vol <= 0:
            return 1.0
        leverage = self.target_vol / vol
        return min(leverage, 1.5)  # 上限 1.5 倍

    def apply_drawdown_control(self, prices, fee_rate=0.0003):
        """通过真实卖出执行回撤控制，现金正确回收，扣除手续费"""
        current_dd = self.max_drawdown

        if current_dd > 0.25:
            # 强平：清空所有持仓，按 close 价回收现金（含滑点近似）
            for account in self.strategy_accounts.values():
                for code in list(account.positions.keys()):
                    shares = account.positions[code]["shares"]
                    if code in prices and shares > 0:
                        sell_price = prices[code]["close"] * 0.999  # 滑点
                        revenue = shares * sell_price
                        fee = revenue * fee_rate
                        account.cash += revenue - fee
                    del account.positions[code]
            self.drawdown_control_triggered = True

        elif current_dd > 0.15:
            # 减半：卖出一半持仓，现金正确回收
            for account in self.strategy_accounts.values():
                for code in list(account.positions.keys()):
                    shares = account.positions[code]["shares"]
                    sell_shares = shares // 2
                    if sell_shares > 0 and code in prices:
                        sell_price = prices[code]["close"] * 0.999  # 滑点
                        revenue = sell_shares * sell_price
                        fee = revenue * fee_rate
                        account.cash += revenue - fee
                        account.positions[code]["shares"] -= sell_shares
                        if account.positions[code]["shares"] == 0:
                            del account.positions[code]
            self.drawdown_control_triggered = True

    def record(self, date):
        self.equity_curve.append({
            "date": date,
            "equity": self.total_equity,
            "drawdown": self.max_drawdown
        })
