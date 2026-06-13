import warnings
warnings.warn(
    "engine.broker is deprecated and will be removed in a future release. "
    "Use execution.broker_simulator or live.execution_engine_v3 instead.",
    DeprecationWarning,
    stacklevel=2,
)


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
