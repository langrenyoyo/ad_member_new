"""Payment provider boundary for withdrawal transfers."""
from dataclasses import dataclass

@dataclass(frozen=True)
class PaymentResult:
    provider: str
    confirmed: bool

class PaymentProvider:
    name = "unconfigured"
    available = False
    def transfer(self, withdrawal_ids: list[int]) -> PaymentResult:
        return PaymentResult(self.name, False)

def configured_provider() -> PaymentProvider:
    # An environment label does not implement a payment integration.
    return PaymentProvider()
