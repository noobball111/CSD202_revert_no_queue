from Services import UIService

from Classes.StorageManager import StorageManager
from Classes.ProductEnum import ProductEnum

manager = StorageManager()
prodEnum = ProductEnum()

UIService.Init(manager, prodEnum)