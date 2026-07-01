from .Node import Node

class Queue:
    def __init__(self) -> None:
        self.Head: Node|None = None
        self.Tail: Node|None = None
        self.size = 0

    def enqueue(self, val):
        newNode = Node(val)

        if self.size == 0:
            self.Head = newNode
            self.Tail = newNode
        else:
            self.Tail.Next = newNode
            newNode.Prev = self.Tail
            self.Tail = newNode

        self.size += 1
    
    def dequeue(self):
        self.Head = self.Head.Prev

    # Don't call this yet
    # TODO: it is missing some features but I forgot
    def RemoveByAttribute(self, attr, val):
        curr = self.Head

        # while curr.val.OrderID != OrderID:
        while getattr(curr.val, attr) != val:
            curr = curr.Prev

        if curr == self.Head:
            self.dequeue()
        elif curr == self.Tail:
            self.Tail = self.Tail.Next
            self.Tail.Prev = None
        else:
            curr.Next.Prev = curr.Prev
            curr.Prev.Next = curr.Next
        
        self.size -= 1

    def Size(self, val):
        return self.size