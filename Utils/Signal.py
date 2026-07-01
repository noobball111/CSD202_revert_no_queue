import uuid
from typing import Any, Callable, Optional

class Connection:
    # Use Optional because these become None after Disconnect()
    _event: Optional[Signal]
    _id: Optional[uuid.UUID]

    def __init__(self, event: Signal, connection_id: uuid.UUID):
        self._event = event
        self._id = connection_id
        self.connected = True

    def Disconnect(self) -> None:
        if self.connected and self._event and self._id != None:
            if self._id in self._event.Listeners:
                del self._event.Listeners[self._id]
            
            self._event = None
            self._id = None
            self.connected = False

class Signal:
    def __init__(self) -> None:
        self.Listeners: dict[uuid.UUID, Callable[..., Any]] = {}

    @classmethod 
    def new(cls) -> Signal:
        return cls()

    def Connect(self, func: Callable[..., Any]) -> Connection:
        connection_id = uuid.uuid4()
        self.Listeners[connection_id] = func
        return Connection(self, connection_id)

    def Fire(self, *args: Any) -> None:
        for func in list(self.Listeners.values()):
            func(*args)