"""A CLI deployment exit code alone does not establish a working Function host."""
import json
import re
import sys
import time
from urllib.request import urlopen
from urllib.error import HTTPError, URLError


def check(hostname, attempts=8):
    if not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)*\.azurewebsites\.net', hostname):
        raise ValueError('Azure did not return a valid hostname. No readiness claim can be made.')
    url = 'https://' + hostname + '/api/health'
    print('Health check URL: ' + url, flush=True)
    for attempt in range(attempts):
        try:
            with urlopen(url, timeout=15) as response:
                data = json.loads(response.read(4096))
                if response.status == 200 and data.get('ready') is True and data.get('service') == 'flash-cards-sync':
                    print('API ready: Blob and Cosmos connections passed.', flush=True)
                    return True
        except HTTPError as error:
            print(f'Waiting for API ({attempt+1}/{attempts}): HTTP {error.code}', flush=True)
        except (URLError, TimeoutError, ValueError):
            print(f'Waiting for API ({attempt+1}/{attempts}): no valid ready response yet.', flush=True)
        if attempt + 1 < attempts:
            time.sleep(5)
    print('API is not ready. Storage has NOT switched. Share this result for diagnosis.', flush=True)
    return False


if __name__ == '__main__':
    sys.exit(0 if check(sys.argv[1]) else 1)
