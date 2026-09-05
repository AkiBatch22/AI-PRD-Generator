"""Exercise a disposable demo stack through its frontend proxy.

Usage: python scripts/smoke.py [--url http://127.0.0.1:3000]
Creates a 'Pipeline smoke test' organization; intended for CI or a test workspace.
Uses only the standard library, so it can run before installing application packages.
"""

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(base, path, method='GET', data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = Request(base + '/api' + path, data=body, method=method,
                  headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode(errors='replace')
        raise RuntimeError(f'{method} {path}: HTTP {error.code}: {detail}') from error


def smoke(base):
    for attempt in range(60):
        try:
            with urlopen(base, timeout=5) as response:
                assert response.status == 200
            health = request(base, '/health')
            assert health['provider'] == 'mock', 'Smoke tests require mock mode'
            break
        except (URLError, RuntimeError, TimeoutError):
            if attempt == 59:
                raise
            time.sleep(2)

    org = request(base, '/organizations', 'POST', {
        'name': 'Pipeline smoke test', 'mode': 'greenfield',
        'description': 'Disposable organization created by the CI smoke test.',
    })
    request(base, f'/organizations/{org["id"]}/context', 'POST', {
        'category': 'customers', 'title': 'Primary user',
        'content': 'Product managers', 'status': 'confirmed',
    })
    request(base, f'/organizations/{org["id"]}/validate', 'POST')
    product = request(base, '/products', 'POST', {
        'organization_id': org['id'], 'name': 'Reporting',
        'description': 'Export a product report.', 'users': 'Product managers',
    })
    prd = request(base, '/prds', 'POST', {
        'product_id': product['id'], 'title': 'Report export',
        'idea': 'Let product managers export their reports as text documents.',
    })
    prefix = f'/prds/{prd["id"]}'
    prd = request(base, prefix + '/discovery', 'POST')
    for question in prd['questions']:
        answer = ('Increase export completion to 90% within 30 days'
                  if question['category'] == 'metrics'
                  else 'Use the existing reporting service with an explicit retry on failure.')
        request(base, prefix + '/discovery/' + question['id'], 'PATCH', {
            'answer': answer, 'status': 'answered',
        })
    request(base, prefix + '/brief', 'POST')
    request(base, prefix + '/brief/approve', 'POST')
    request(base, prefix + '/requirements', 'POST')
    request(base, prefix + '/generate', 'POST')
    prd = request(base, prefix + '/review', 'POST')
    for issue in prd['review_issues']:
        assert issue['severity'] != 'critical', issue['title']
        request(base, prefix + '/review/' + issue['id'], 'PATCH', {'action': 'ignore'})
    result = request(base, prefix + '/finalize', 'POST')
    assert result['status'] == 'final'
    assert result['requirements'] and len(result['document_sections']) == 21
    with urlopen(base + '/api' + prefix + '/export', timeout=10) as response:
        assert 'Acceptance criteria' in response.read().decode()
    print('Smoke passed: organization -> context -> product -> discovery -> brief -> requirements -> review -> final -> export')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:3000')
    args = parser.parse_args()
    smoke(args.url.rstrip('/'))
