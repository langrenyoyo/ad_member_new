import os
import sys
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts' / (sys.argv[1] if len(sys.argv) > 1 else 'guangjiyexing-1.0')
out.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env['JAVA_HOME'] = 'D:/Android/Java/jdk-17.0.20.1+1'
env['GRADLE_USER_HOME'] = 'D:/Android/gradle-cache'
env['PATH'] = env['JAVA_HOME'] + '/bin;' + env['PATH']
args = ['D:/Android/gradle-8.14.5/bin/gradle.bat', '-p', str(root/'apk/guangjiyexing'),
        ':app:testDebugUnitTest', ':app:lintDebug', ':app:assembleRelease',
        '-Pkotlin.incremental=false', '--offline', '--console=plain']
with (out/'build.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(args, env=env, stdout=log, stderr=subprocess.STDOUT)
print('build_exit', result.returncode)
raise SystemExit(result.returncode)
