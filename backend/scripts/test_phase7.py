"""Phase 7 comprehensive test — all sub-modules + edge cases."""
import requests
import sys

B = 'http://127.0.0.1:8001'
PASS = []
FAIL = []


def check(name, cond, detail=''):
    if cond:
        PASS.append(name)
        print(f'  [OK]   {name}')
    else:
        FAIL.append(name)
        print(f'  [FAIL] {name} :: {detail}')


def main():
    print('===== PHASE 7 — Comprehensive Test =====\n')

    r = requests.post(f'{B}/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
    check('Login admin', r.status_code == 200, f'status={r.status_code}')
    H = {'Authorization': f'Bearer {r.json()["access_token"]}'}

    print('\n--- Migration Verify ---')
    from backend.core.database import db_list_applied_migrations
    migs = [m['version'] for m in db_list_applied_migrations()]
    check('Migration 015 applied', '015_aslap_daily_ops' in migs)
    check('Total migrations = 15', len(migs) == 15, f'got {len(migs)}')

    print('\n--- 7A: Daily Checklist ---')
    r = requests.get(f'{B}/api/aslap/checklists/today', headers=H)
    check('GET today checklist 200', r.status_code == 200)
    data = r.json()
    check('Default 7 items in template', len(data['items']) == 7, f'got {len(data["items"])}')
    check('All items have required flag', all('required' in it for it in data['items']))
    check('All items have type field', all('type' in it for it in data['items']))

    items_filled = [
        {**it, 'value': True if it['type'] == 'bool' else 4, 'photo': None, 'ok': True}
        for it in data['items']
    ]
    r = requests.post(f'{B}/api/aslap/checklists/submit', headers=H, json={
        'items': items_filled, 'submit': False, 'notes': 'Draft test',
    })
    check('Save draft 200', r.status_code == 200)
    check('Draft status correct', r.json()['status'] == 'draft', f"got {r.json()['status']}")

    r = requests.post(f'{B}/api/aslap/checklists/submit', headers=H, json={
        'items': items_filled, 'submit': True, 'notes': 'Submitted test',
    })
    check('Submit checklist 200', r.status_code == 200)
    check('Submitted status correct', r.json()['status'] == 'submitted')
    check('submitted_at populated', r.json().get('submitted_at') is not None)

    r = requests.get(f'{B}/api/aslap/checklists?from_date=2026-04-01&to_date=2026-05-31', headers=H)
    check('GET checklists list 200', r.status_code == 200)
    check('At least 1 in list', len(r.json()['checklists']) >= 1)

    print('\n--- 7B: Water Quality ---')
    # 4-alert scenario
    r = requests.post(f'{B}/api/aslap/water-quality', headers=H, json={
        'tds_ppm': 800, 'ph': '5.0', 'bau': 'amis', 'warna': 'keruh',
    })
    check('Water log multi-alert 201', r.status_code == 201)
    alerts = r.json()['alerts']
    check('TDS alert detected', any('TDS' in a for a in alerts))
    check('pH min alert detected', any('pH' in a and 'min' in a for a in alerts))
    check('Bau alert detected', any('Bau' in a for a in alerts))
    check('Warna alert detected', any('Warna' in a for a in alerts))

    # Boundary: TDS=500, pH=6.5 = OK
    r = requests.post(f'{B}/api/aslap/water-quality', headers=H, json={
        'tds_ppm': 500, 'ph': '6.5', 'bau': 'normal', 'warna': 'jernih',
    })
    check('Boundary TDS=500, pH=6.5 → 0 alerts', r.json()['alert_count'] == 0)

    # Boundary: TDS=501 = alert
    r = requests.post(f'{B}/api/aslap/water-quality', headers=H, json={
        'tds_ppm': 501, 'ph': '8.5', 'bau': 'normal', 'warna': 'jernih',
    })
    check('Boundary TDS=501 → alert', r.json()['alert_count'] >= 1)

    # pH high
    r = requests.post(f'{B}/api/aslap/water-quality', headers=H, json={
        'tds_ppm': 100, 'ph': '9.0', 'bau': 'normal', 'warna': 'jernih',
    })
    check('pH 9.0 (>max) → alert', r.json()['alert_count'] >= 1)

    r = requests.get(f'{B}/api/aslap/water-quality?from_date=2026-04-01&to_date=2026-05-31', headers=H)
    check('GET water list 200', r.status_code == 200)
    logs = r.json()['logs']
    check('At least 4 water logs', len(logs) >= 4)
    check('All logs have alerts array', all('alerts' in l for l in logs))

    print('\n--- 7C: Production Observations ---')
    r = requests.get(f'{B}/api/production/batches', headers=H)
    batches = r.json().get('batches', [])
    batch_id = batches[0]['id'] if batches else None
    check('Existing batch found', batch_id is not None)

    r = requests.post(f'{B}/api/aslap/observations', headers=H, json={
        'batch_id': batch_id, 'suhu_masak': 95, 'waktu_menit': 30,
        'kebersihan_ok': True, 'notes': 'Tim cuci tangan, suhu sesuai',
    })
    check('Create obs (linked) 201', r.status_code == 201)

    r = requests.post(f'{B}/api/aslap/observations', headers=H, json={
        'suhu_masak': 100, 'waktu_menit': 35, 'kebersihan_ok': False,
        'notes': 'Tanpa batch link',
    })
    check('Create obs (standalone) 201', r.status_code == 201)

    r = requests.get(f'{B}/api/aslap/observations', headers=H)
    check('GET obs list 200', r.status_code == 200)
    check('At least 2 obs', len(r.json()['observations']) >= 2)

    if batch_id:
        r = requests.get(f'{B}/api/aslap/observations?batch_id={batch_id}', headers=H)
        obs_for_batch = r.json()['observations']
        check('Filter by batch_id works', all(o['batch_id'] == batch_id for o in obs_for_batch))

    print('\n--- 7D: School Communication Logs ---')
    for ch in ['call', 'wa', 'email', 'visit', 'sms']:
        r = requests.post(f'{B}/api/aslap/comm-logs', headers=H, json={
            'school_name': 'RA AL- AMANAH', 'channel': ch,
            'topic': f'Test {ch}', 'response': 'OK',
        })
        check(f'Create comm channel={ch} 201', r.status_code == 201)

    r = requests.post(f'{B}/api/aslap/comm-logs', headers=H, json={
        'school_name': 'X', 'channel': 'pigeon', 'topic': 'invalid',
    })
    check('Invalid channel rejected 400', r.status_code == 400, f'got {r.status_code}')

    r = requests.post(f'{B}/api/aslap/comm-logs', headers=H, json={
        'school_name': 'MTS', 'channel': 'wa', 'topic': 'Complaint',
        'response': 'Will follow up tomorrow', 'follow_up': True,
    })
    check('follow_up=true accepted 201', r.status_code == 201)

    r = requests.get(f'{B}/api/aslap/comm-logs', headers=H)
    check('GET comm logs 200', r.status_code == 200)

    print('\n--- 7E: Weekly Reports ---')
    r = requests.post(f'{B}/api/aslap/reports/generate', headers=H, json={
        'week_start': '2026-04-26', 'week_end': '2026-05-02',
    })
    check('Generate report 201', r.status_code == 201)
    report = r.json()
    sections = ['checklists', 'water_quality', 'production_observations', 'school_communications']
    check('Summary has 4 sections', all(k in report['summary'] for k in sections))
    check('Checklists count > 0', report['summary']['checklists']['total'] >= 1)
    check('Water alerts count tracked', 'with_alerts' in report['summary']['water_quality'])
    check('Obs avg_suhu computed', report['summary']['production_observations']['avg_suhu'] > 0)

    # Invalid date format
    r = requests.post(f'{B}/api/aslap/reports/generate', headers=H, json={
        'week_start': 'not-a-date', 'week_end': '2026-05-02',
    })
    check('Invalid date format rejected 400', r.status_code == 400)

    # End < start
    r = requests.post(f'{B}/api/aslap/reports/generate', headers=H, json={
        'week_start': '2026-05-02', 'week_end': '2026-04-26',
    })
    check('End < start rejected 400', r.status_code == 400)

    r = requests.get(f'{B}/api/aslap/reports', headers=H)
    check('GET reports 200', r.status_code == 200)
    rl = r.json()['reports']
    check('At least 1 report', len(rl) >= 1)
    check('Report has summary embedded', 'summary' in rl[0])

    rid = report['id']
    r = requests.post(f'{B}/api/aslap/reports/{rid}/submit', headers=H)
    check('Submit report 200', r.status_code == 200)

    r = requests.post(f'{B}/api/aslap/reports/99999/submit', headers=H)
    check('Submit non-existent → 404', r.status_code == 404)

    print('\n--- Permission boundary checks ---')
    # Create test user with role=user but no kitchen → should be 403 on /aslap routes
    # We'll skip user creation and just verify endpoints require auth
    no_auth = requests.get(f'{B}/api/aslap/checklists/today')
    check('No auth → 401', no_auth.status_code == 401)

    no_auth = requests.post(f'{B}/api/aslap/water-quality', json={'tds_ppm': 100})
    check('No auth on water log → 401', no_auth.status_code == 401)

    print(f'\n===== RESULT =====')
    print(f'PASS: {len(PASS)}/{len(PASS) + len(FAIL)}')
    print(f'FAIL: {len(FAIL)}')
    if FAIL:
        print('Failed checks:')
        for f in FAIL:
            print(f'  - {f}')
        sys.exit(1)
    print('\n[DONE] Phase 7 all checks passed.')


if __name__ == '__main__':
    main()
