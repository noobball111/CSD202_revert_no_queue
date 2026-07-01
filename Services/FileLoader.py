from typing import TYPE_CHECKING

from Utils.Signal import Signal

from Shared.Signals import Signals

from Classes.Product import Product
from Classes.Node import Node
from Classes.Order import Order
from Classes.Queue import Queue
from Classes.Stack import Stack

# Module = None

class FileLoader:
    def __init__(self):
        self.Loaded = {}

    def Load(self, filePath: str):

        file =  open(filePath, "r")

        for line in file.readlines():
            line = line.strip()
            if line[-1] == "|": line = line[0:-2]

            ItemData = line.split("|")

            if getattr(self.Loaded, line):
                self.Loaded[line].Amount += ItemData[4]
            else:
                newData = []

                for i in range(len(ItemData)):
                    if i == 4: continue #Amount

                    newData[i] = ItemData[i]

                self.Loaded[line] = {
                    "Amount": ItemData[4],
                    "Data" : newData
                }
        
        return self.Loaded