from abc import ABC, abstractmethod
from app.models import IR
from app.models_v2 import IRv2


class BaseHandler(ABC):
    @abstractmethod
    def handle(self, ir_v2: IRv2, ir_v1: IR) -> None:
        """
        Apply logic to ir_v2 based on the state of ir_v1 or other factors.
        This method should modify ir_v2 in-place.
        """
        pass
