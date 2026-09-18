import os
import subprocess
import sys

probe='import sys;sys.path.insert(0,"backend");import app.main_from_txt'
for provider in ('unconfigured','sandbox','test','mock'):
    env={**os.environ,'APP_ENV':'production','JWT_SECRET':'x'*40,'ADMIN_PASSWORD':'Production-Admin-123!','PAYMENT_PROVIDER':provider}
    result=subprocess.run([sys.executable,'-c',probe],env=env,capture_output=True,text=True)
    assert result.returncode!=0 and 'PAYMENT_PROVIDER' in (result.stdout+result.stderr)
print('Production guard: unconfigured and test payment providers are rejected at startup')
