from Classes import Product

def GenerateSKU(ItemClass):
    if isinstance(ItemClass, Product.Clothes):
        return f"{ItemClass.Category}-{ItemClass.Name}-{ItemClass.Size}-{ItemClass.Size}-{ItemClass.Color}"
    elif isinstance(ItemClass, Product.Item):
        return f"{ItemClass.Category}-{ItemClass.Name}"