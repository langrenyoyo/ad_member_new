import os
import sys
sys.path.insert(0, 'backend')
from app.payment import configured_provider

os.environ.pop('PAYMENT_PROVIDER', None)
result=configured_provider().transfer([1,2])
assert result.provider=='unconfigured' and result.confirmed is False
os.environ['PAYMENT_PROVIDER']='sandbox'
result=configured_provider().transfer([3])
# Sandbox is intentionally not a payment integration: it must remain
# unconfirmed and use the same inert provider boundary as the default.
assert result.provider=='unconfigured' and result.confirmed is False
os.environ.pop('PAYMENT_PROVIDER', None)
print('Payment provider contract: default/configured names never imply confirmed payment')
