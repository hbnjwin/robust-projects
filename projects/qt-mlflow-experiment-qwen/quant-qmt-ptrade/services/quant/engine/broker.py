class Broker:
    def __init__(self, commission=0.001, slippage=0.0005):
        self.commission = commission
        self.slippage = slippage

    def execute(self, action, price, size):
        if action == "buy":
            exec_price = price * (1 + self.slippage)
        else:
            exec_price = price * (1 - self.slippage)

        fee = exec_price * size * self.commission
        return exec_price, fee
