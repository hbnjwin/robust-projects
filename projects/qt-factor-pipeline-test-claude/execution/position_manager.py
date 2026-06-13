class PositionManager:
    def __init__(self):
        self.position = 0
        self.last_buy_date = None

    def can_sell(self, current_date):
        # T+1 rule: must hold at least one day
        if self.last_buy_date is None:
            return True
        return current_date > self.last_buy_date

    def update_position(self, size, side, date):
        if side == 1:
            self.position += size
            self.last_buy_date = date
        elif side == -1:
            self.position -= size
