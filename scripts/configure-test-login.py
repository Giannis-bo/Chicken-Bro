"""Set test credentials without putting plaintext in files, commands or chat."""
import getpass
import hashlib
import json
import subprocess
import sys


def main():
    remote = ['ssh', '-o', 'BatchMode=yes', 'wow-lighthouse', 'sudo', '-n', 'env',
              'PYTHONPATH=/opt/chickenbro-test/current', '/opt/chickenbro-runtime/bin/python',
              '-m', 'server.deploy_test_login']
    if sys.argv[1:] == ['--disable']:
        subprocess.run([*remote, '--disable', '--apply'], check=True)
        return
    if sys.argv[1:]:
        raise SystemExit('usage: python scripts/configure-test-login.py [--disable]')
    hashes = {}
    for account in ('A', 'B'):
        credential = getpass.getpass(f'Test account {account}: enter a unique credential (32-256 characters): ')
        if not 32 <= len(credential) <= 256:
            raise ValueError('Credential must contain 32-256 characters.')
        if credential != getpass.getpass('Confirm credential: '):
            raise ValueError('Credentials do not match.')
        hashes[account] = hashlib.sha256(credential.encode()).hexdigest()
        del credential
    if hashes['A'] == hashes['B']:
        raise ValueError('Accounts A and B must use different credentials.')
    subprocess.run([*remote, '--configure', '--apply'],
                   input=json.dumps(hashes), text=True, check=True,
                   env=None)
    print('Configured. Open https://www.chickenbro.cloud/test/ and enter your test credential.')


if __name__ == '__main__':
    main()
