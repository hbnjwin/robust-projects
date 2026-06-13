class RiskController:
    def __init__(self, dd_levels=(0.15, 0.25, 0.35)):
        self.dd_levels = dd_levels
        self.peak = 1.0
        self.exposure = 1.0

    def update(self, equity):
        self.peak = max(self.peak, equity)
        dd = (self.peak - equity) / self.peak
        if dd > self.dd_levels[2]:
            self.exposure = 0.0
        elif dd > self.dd_levels[1]:
            self.exposure = 0.4
        elif dd > self.dd_levels[0]:
            self.exposure = 0.7
        else:
            self.exposure = 1.0
        return self.exposure
