import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/app-entry-20261112'
out.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env['JAVA_HOME'] = 'D:/Android/Java/jdk-17.0.20.1+1'
env['GRADLE_USER_HOME'] = 'D:/Android/gradle-cache'
env['PATH'] = env['JAVA_HOME'] + '/bin;' + env['PATH']
args = ['D:/Android/gradle-8.14.5/bin/gradle.bat', '-p', str(root / 'apk/ya_zhi_yi_ji'),
        ':app:testDebugUnitTest', ':app:testReleaseUnitTest', ':app:lintDebug', ':app:lintRelease',
        ':app:assembleRelease', ':app:assembleDeviceTest', '--offline', '--console=plain']
with (out / 'build.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(args, env=env, stdout=log, stderr=subprocess.STDOUT)
print('build_exit', result.returncode)
raise SystemExit(result.returncode)
