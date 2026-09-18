"""Check password hashing and public serialization without creating business records."""
import sys
sys.path.insert(0, 'backend')
from app.main_from_txt import Member, hash_password, prepare_member_passwords, serialize_member, verify_password

changes={'password':'MemberPass-123','pay_password':'PayPass-456'}
prepare_member_passwords(changes)
assert 'password' not in changes and 'pay_password' not in changes
assert verify_password('MemberPass-123', changes['password_hash'], changes['password_salt'])
assert verify_password('PayPass-456', changes['pay_password_hash'], changes['pay_password_salt'])
assert not verify_password('wrong', changes['password_hash'], changes['password_salt'])
public=serialize_member(Member(username='fixture'))
assert not any(key in public for key in ('password','pay_password','password_hash','password_salt','pay_password_hash','pay_password_salt'))
print('Member password contract: salted hashes, wrong-password rejection and public-field exclusion passed')
