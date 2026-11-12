"""Create signed APK/source delivery, excluding local signing and SDK configuration."""
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
project = root/'apk/ya_zhi_yi_ji'
out = root/'artifacts/app-entry-20261112'
apk = out/'鸭只易记-1.0.5-五项需求修复-20261112.apk'
shutil.copy2(project/'app/build/outputs/apk/release/app-release.apk', apk)
digest = hashlib.sha256()
app = project/'app'
sources = [p for p in (app/'src/main').rglob('*') if p.is_file()] + [app/'build.gradle.kts']
for path in sorted(sources, key=lambda p: p.relative_to(app).as_posix()):
    digest.update(path.relative_to(app).as_posix().encode('utf-8'))
    digest.update(b'\0'); digest.update(path.read_bytes())
fingerprint = digest.hexdigest()
buildconfig = (app/'build/generated/source/buildConfig/release/com/example/idiomquiz/BuildConfig.java').read_text()
assert re.search(r'SOURCE_FINGERPRINT = "([a-f0-9]+)"', buildconfig).group(1) == fingerprint
source_zip = out/'鸭只易记-1.0.5-前端源码.zip'
skip_dirs = {'build','.gradle','.kotlin','.git','.idea'}
skip_files = {'local.properties','keystore.properties'}
with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED) as z:
    for path in project.rglob('*'):
        if not path.is_file(): continue
        rel = path.relative_to(project)
        if any(part in skip_dirs for part in rel.parts) or path.name in skip_files: continue
        if path.suffix.lower() in {'.jks','.keystore','.apk','.log'}: continue
        z.write(path, 'ya_zhi_yi_ji/'+rel.as_posix())
server_files = ['backend/app/main_from_txt.py','backend/app/member_policy.py','backend/app/invite_landing.py',
    'backend/tests/test_app_pagination.py','backend/tests/test_secondary_ads.py','backend/tests/test_invite_landing.py',
    'public/invite.html','public/invite.js','public/invite.css','docs/app-entry-invitation-fix-20261112.md']
server_zip = out/'后台及邀请网页修复.zip'
with zipfile.ZipFile(server_zip,'w',zipfile.ZIP_DEFLATED) as z:
    for name in server_files: z.write(root/name, name)
downloads = root/'public/downloads'
downloads.mkdir(exist_ok=True)
shutil.copy2(apk, downloads/'yazhiyiji-latest.apk')
manifest = {'version_name':'1.0.5','version_code':6,'package':'com.heshangzhilian.yazhiyiji',
    'source_fingerprint':fingerprint,'signing_certificate_sha256':'cce0a0b31e0cf6f64a4cff8460ff1ad1369ea6e74ff85cabb875ccbb22105e63',
    'artifacts':[{ 'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in [apk, source_zip, server_zip]], 'deployed':False}
(out/'release-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(manifest, ensure_ascii=True, indent=2))
