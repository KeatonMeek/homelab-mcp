"""Interactive local configuration wizard. Never prints credentials or uploads data."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
import sys
from cryptography.fernet import Fernet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True, help='Absolute private directory outside this checkout')
    parser.add_argument('--client', choices=('dcr', 'chatgpt'), default='dcr',
                        help='chatgpt enables only its exact public metadata/JWKS URLs; default dcr enables neither')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    directory = args.directory
    if not directory.is_absolute() or directory == root or root in directory.resolve().parents:
        parser.error('Use an absolute directory outside the source checkout')
    if any(p.is_symlink() for p in [directory, *directory.parents]):
        parser.error('Symlink directory components are not allowed')
    os.umask(0o077)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
        parser.error('Directory must be owned by this account with mode 0700')
    filename = directory/'settings.json'
    if filename.exists() or filename.is_symlink():
        parser.error('settings.json already exists; no overwrite performed')
    # Interactive inputs are kept out of shell command history and process args.
    base = input('Public HTTPS origin (for example https://mcp.example.com): ').strip()
    owner = input('Your numeric GitHub account ID: ').strip()
    client_id = input('GitHub OAuth App client ID: ').strip()
    client_secret = getpass.getpass('GitHub OAuth App client secret (hidden): ')
    redirect = input('Exact HTTPS callback shown by your MCP client: ').strip()
    for name in ('oauth', 'health', 'audit', 'run'):
        (directory/name).mkdir(mode=0o700, exist_ok=True)
    data = {
        'HOMELAB_BASE_URL': base, 'HOMELAB_GITHUB_OWNER_ID': owner,
        'HOMELAB_GITHUB_CLIENT_ID': client_id, 'HOMELAB_GITHUB_CLIENT_SECRET': client_secret,
        'HOMELAB_JWT_SIGNING_KEY': secrets.token_urlsafe(48),
        'HOMELAB_STORAGE_ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'HOMELAB_CLIENT_REDIRECT_URIS': json.dumps([redirect]),
        'HOMELAB_STATE_DIR': str(directory/'oauth'),
        'HOMELAB_HEALTH_SNAPSHOT': str(directory/'health'/'health.json'),
        'HOMELAB_BROKER_SOCKET': str(directory/'run'/'broker.sock'),
        'HOMELAB_ENABLE_EXECUTION': 'false', 'HOMELAB_PORT': '8080',
        'HOMELAB_TRUSTED_CLIENT_METADATA_URIS': json.dumps(['https://chatgpt.com/oauth/client.json'] if args.client == 'chatgpt' else []),
        'HOMELAB_TRUSTED_JWKS_URIS': json.dumps(['https://chatgpt.com/oauth/jwks.json'] if args.client == 'chatgpt' else []),
    }
    sys.path.insert(0, str(root))
    from app.config import Settings
    Settings.from_environment(data)
    fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')
    print('Private configuration created. Keep it and its directory outside Git and public backups.')


if __name__ == '__main__':
    main()
