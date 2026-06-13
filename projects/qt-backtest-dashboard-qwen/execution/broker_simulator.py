class BrokerSimulator:
    def __init__(self, commission=0.001, slippage=0.0005):
        self.commission = commission
        self.slippage = slippage

    def execute(self, price, size, side):
        # side: 1 buy, -1 sell
        exec_price = price * (1 + self.slippage * side)
        cost = exec_price * size
        fee = abs(cost) * self.commission
        return exec_price, fee
