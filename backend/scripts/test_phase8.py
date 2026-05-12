"""Phase 8 comprehensive test — notifications + triggers + preferences."""
import requests
import sys

B = 'http://127.0.0.1:8001'
PASS, FAIL = [], []


def check(name, cond, detail=''):
    if cond:
        PASS.append(name); print(f'  [OK]   {name}')
    else:
        FAIL.append(name); print(f'  [FAIL] {name} :: {detail}')


def main():
    print('===== PHASE 8 — Notifications Test =====\n')

    r = requests.post(f'{B}/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
    check('Login admin', r.status_code == 200)
    H = {'Authorization': f'Bearer {r.json()["access_token"]}'}
    me = r.json()
    user_id = requests.get(f'{B}/api/auth/me', headers=H).json()['id']

    print('\n--- Migration ---')
    from backend.core.database import db_list_applied_migrations
    migs = [m['version'] for m in db_list_applied_migrations()]
    check('Migration 016 applied', '016_notifications' in migs)
    check('Total migrations = 16', len(migs) == 16, f'got {len(migs)}')

    print('\n--- Empty state ---')
    # Mark all as read first to clean baseline
    requests.post(f'{B}/api/notifications/mark-all-read', headers=H)
    r = requests.get(f'{B}/api/notifications/unread-count', headers=H)
    check('GET unread-count 200', r.status_code == 200)
    baseline_unread = r.json()['unread']
    check('Baseline unread = 0 after mark-all-read', baseline_unread == 0, f'got {baseline_unread}')

    print('\n--- Manual create via /test endpoint ---')
    r = requests.post(f'{B}/api/notifications/test', headers=H, json={
        'user_id': user_id,
        'type': 'test.manual',
        'title': 'Test notification 1',
        'category': 'system',
        'body': 'Body test 1',
        'link': '/dashboard',
    })
    check('Create test notif 201', r.status_code == 201)
    nid1 = r.json()['id']

    r = requests.post(f'{B}/api/notifications/test', headers=H, json={
        'user_id': user_id, 'type': 'test.menu',
        'title': 'Menu pending review', 'category': 'menu', 'body': 'Bu Ratih submit menu', 'link': '/menu-approval',
    })
    check('Create category=menu notif', r.status_code == 201)
    nid2 = r.json()['id']

    print('\n--- List + counts ---')
    r = requests.get(f'{B}/api/notifications', headers=H)
    check('GET list 200', r.status_code == 200)
    notifs = r.json()['notifications']
    check('At least 2 notifs', len(notifs) >= 2, f'got {len(notifs)}')
    check('Latest notif has title', notifs[0]['title'] in ('Menu pending review', 'Test notification 1'))
    check('Latest is unread', notifs[0]['read'] is False)

    r = requests.get(f'{B}/api/notifications/unread-count', headers=H)
    check('Unread count = 2', r.json()['unread'] == 2, f"got {r.json()['unread']}")

    # Filter unread_only
    r = requests.get(f'{B}/api/notifications?unread_only=true', headers=H)
    check('Filter unread_only', all(not n['read'] for n in r.json()['notifications']))

    print('\n--- Mark single as read ---')
    r = requests.post(f'{B}/api/notifications/{nid1}/read', headers=H)
    check('POST mark-read 200', r.status_code == 200)
    check('Returned updated=1', r.json()['updated'] == 1)

    r = requests.get(f'{B}/api/notifications/unread-count', headers=H)
    check('Unread now = 1', r.json()['unread'] == 1)

    # Idempotent: mark already-read returns updated=0
    r = requests.post(f'{B}/api/notifications/{nid1}/read', headers=H)
    check('Re-mark idempotent (updated=0)', r.json()['updated'] == 0)

    print('\n--- Mark all read ---')
    r = requests.post(f'{B}/api/notifications/mark-all-read', headers=H)
    check('POST mark-all-read 200', r.status_code == 200)
    check('Updated >= 1', r.json()['updated'] >= 1)
    r = requests.get(f'{B}/api/notifications/unread-count', headers=H)
    check('Unread = 0 after mark-all', r.json()['unread'] == 0)

    print('\n--- Preferences ---')
    r = requests.get(f'{B}/api/notifications/preferences', headers=H)
    check('GET prefs 200', r.status_code == 200)
    prefs = r.json()['preferences']
    check('All categories defaulted to true', all(prefs.get(cat) is True for cat in ('menu', 'finance', 'compliance')))

    # Disable 'menu' category
    r = requests.put(f'{B}/api/notifications/preferences', headers=H, json={
        'preferences': {'menu': False}
    })
    check('PUT prefs disable menu', r.status_code == 200)

    # Now creating menu category notif should be skipped
    r = requests.post(f'{B}/api/notifications/test', headers=H, json={
        'user_id': user_id, 'type': 'test.menu', 'title': 'Should be filtered',
        'category': 'menu',
    })
    check('Menu notif filtered (500)', r.status_code == 500, f'got {r.status_code}')

    # System category still works
    r = requests.post(f'{B}/api/notifications/test', headers=H, json={
        'user_id': user_id, 'type': 'test.system', 'title': 'System still works',
        'category': 'system',
    })
    check('System notif still works', r.status_code == 201)

    # Re-enable menu
    requests.put(f'{B}/api/notifications/preferences', headers=H, json={
        'preferences': {'menu': True}
    })

    print('\n--- Trigger: menu submit ---')
    # Create a manual menu and submit it → expect notification to head_sppg/admin
    requests.post(f'{B}/api/notifications/mark-all-read', headers=H)  # baseline
    save = requests.post(f'{B}/api/menu/saved', headers=H, json={
        'name': 'Test Phase8 Menu', 'payload': {'items': []},
        'source': 'manual',
    })
    mid = save.json()['id']
    submit = requests.post(f'{B}/api/menu/saved/{mid}/submit', headers=H, json={})
    check('Menu submit 200', submit.status_code == 200)
    # Allow trigger to fire async
    import time; time.sleep(0.5)
    r = requests.get(f'{B}/api/notifications/unread-count', headers=H)
    # admin role is "admin" → has approve perm via being treated as superadmin → should get notif
    check('Menu submit triggered notif', r.json()['unread'] >= 1, f"got {r.json()['unread']}")

    r = requests.get(f'{B}/api/notifications', headers=H)
    menu_notif = next((n for n in r.json()['notifications'] if n['type'] == 'menu.pending_review'), None)
    check('Menu trigger has correct type', menu_notif is not None)
    if menu_notif:
        check('Menu notif has link', menu_notif['link'] == '/menu-approval')
        check('Menu notif category=menu', menu_notif['category'] == 'menu')

    # Cleanup
    requests.delete(f'{B}/api/menu/saved/{mid}', headers=H)

    print('\n--- Trigger: inspection.create ---')
    requests.post(f'{B}/api/notifications/mark-all-read', headers=H)
    # Create supplier + PO + inspection
    sup = requests.post(f'{B}/api/suppliers', headers=H, json={'name': 'Test P8', 'kategori': 'sayur'}).json()
    po = requests.post(f'{B}/api/purchase-orders', headers=H, json={
        'supplier_id': sup['id'], 'lines': [{'item_name': 'Bayam', 'total_weight_grams': 5000, 'unit': 'kg', 'expected_containers': 2, 'unit_price_idr': 12000}],
    }).json()
    insp = requests.post(f'{B}/api/inspections', headers=H, json={'po_id': po['id']}).json()
    check('Inspection created', 'id' in insp)
    import time; time.sleep(0.5)
    r = requests.get(f'{B}/api/notifications', headers=H)
    insp_notifs = [n for n in r.json()['notifications'] if n['type'] == 'inspection.scheduled']
    check('Inspection trigger fired', len(insp_notifs) >= 1)
    if insp_notifs:
        check('Inspection notif category=receiving', insp_notifs[0]['category'] == 'receiving')

    print('\n--- Push subscriptions ---')
    r = requests.post(f'{B}/api/notifications/subscriptions', headers=H, json={
        'endpoint': 'https://fcm.googleapis.com/fcm/send/test-endpoint-123',
        'p256dh': 'dummy_p256dh', 'auth': 'dummy_auth',
        'user_agent': 'Mozilla/5.0 Test',
    })
    check('Subscribe push 201', r.status_code == 201)
    sub_id = r.json()['id']

    # Idempotent: re-subscribe same endpoint replaces
    r = requests.post(f'{B}/api/notifications/subscriptions', headers=H, json={
        'endpoint': 'https://fcm.googleapis.com/fcm/send/test-endpoint-123',
        'p256dh': 'dummy2', 'auth': 'dummy2',
    })
    check('Re-subscribe replaces (idempotent)', r.status_code == 201)

    r = requests.delete(f'{B}/api/notifications/subscriptions/{r.json()["id"]}', headers=H)
    check('Unsubscribe 200', r.status_code == 200)

    print('\n--- Auth boundary ---')
    no_auth = requests.get(f'{B}/api/notifications')
    check('No auth → 401', no_auth.status_code == 401)

    print(f'\n===== RESULT =====')
    print(f'PASS: {len(PASS)}/{len(PASS) + len(FAIL)}')
    print(f'FAIL: {len(FAIL)}')
    if FAIL:
        for f in FAIL: print(f'  - {f}')
        sys.exit(1)
    print('\n[DONE] Phase 8 all checks passed.')


if __name__ == '__main__':
    main()
