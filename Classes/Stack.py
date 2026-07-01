class Stack:
    def __init__(self) -> None:
        self.arr = []
        self.size = 0
    
    # Method

    def push(self, val) -> None:
        self.arr.append(val)
        self.size += 1
    
    def pop(self):
        self.size -= 1
        return self.arr.pop(-1)

    def GetSize(self) -> int:
        return len(self.arr)
    