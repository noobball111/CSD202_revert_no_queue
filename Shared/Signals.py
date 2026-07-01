from dataclasses import dataclass, field
from Utils.Signal import Signal

@dataclass
class SearchSignals:
    BySKU: Signal = Signal.new() 
    ByUPC: Signal = Signal.new()
    ByProduct: Signal = Signal.new()
    ByCategory: Signal = Signal.new()

@dataclass
class ProductSignals:
    # Events
    Added: Signal = Signal.new()
    Removing: Signal = Signal.new()
    Edited: Signal = Signal.new()
    Processed: Signal = Signal.new() 

    # Method
    AddStock: Signal = Signal.new()
    Edit: Signal = Signal.new()

    

@dataclass
class SignalsContainer:

    # Product events
    Product: ProductSignals = field(default_factory=ProductSignals)

    # Search
    Search: SearchSignals = field(default_factory=SearchSignals)

    OnKeywordAdded: Signal = Signal.new()
    OnKeywordRemoved: Signal = Signal.new()

# Create shared instance
Signals = SignalsContainer()