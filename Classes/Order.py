import uuid

class Order:
    def __init__(self, Item, Amount) -> None:
        self.Item = Item
        self.ID = uuid.uuid4
        self.Amount = Amount
