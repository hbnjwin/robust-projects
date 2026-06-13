import warnings
warnings.warn(
    "engine.datafeed is deprecated and will be removed in a future release. "
    "Use core.datafeed or live.data_loader_fast instead.",
    DeprecationWarning,
    stacklevel=2,
)


class DataFeed:
    def __init__(self, data):
        self.data = data.reset_index(drop=True)
        self.index = 0

    def next(self):
        if self.index < len(self.data):
            bar = self.data.iloc[self.index]
            self.index += 1
            return bar
        return None
