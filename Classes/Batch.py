from typing import Literal
import datetime as dt

Data = {
    "BatchID": -1,
}

Keywords = {"BatchID", "Amount", "State", "ExpirationDate", "ImportedDate"}

def _getNextBatchID():
    Data["BatchID"] += 1
    return Data["BatchID"]

class Batch:
    def __init__(self, UPC: str, amount: int = 1, state: Literal["Good", "ToBeReviewed"] = "Good"):
        self.BatchID = _getNextBatchID()
        self.ProductUPC = UPC
        self.Amount = amount
        self.State = state
        self.ImportedDate = dt.datetime.now()
        self.ExpirationDate: dt.datetime | None = None

    def SetExpirationDate(self, expirationDate: dt.datetime):
        self.ExpirationDate = expirationDate

    def AddAmount(self, amount: int):
        self.Amount += amount

    def SubtractAmount(self, amount: int):
        self.Amount -= amount

    def SetAmount(self, amount: int):
        self.Amount = amount

    def SetState(self, state: Literal["Good", "ToBeReviewed"]):
        self.State = state