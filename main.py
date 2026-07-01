from Services import UIService
from Services.FileLoader import FileLoader

from Classes.StorageManager import StorageManager
from Classes.ProductEnum import ProductEnum

manager = StorageManager()
prodEnum = ProductEnum()

DEFAULT_SAVE_FILE = "Data/Data.txt"

UIService.Init(manager, prodEnum)