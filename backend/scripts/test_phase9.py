"""Phase 9 comprehensive test — executive dashboards + compliance bundle."""
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
    print('===== PHASE 9 — Executive Dashboard Test =====\n')

    r = requests.post(f'{B}/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
    check('Login admin', r.status_code == 200)
    H = {'Authorization': f'Bearer {r.json()["access_token"]}'}

    print('\n--- Per-kitchen KPI ---')
    r = requests.get(f'{B}/api/executive/kpi', headers=H)
    check('GET /executive/kpi 200', r.status_code == 200)
    kpi = r.json()
    keys = ['target_porsi', 'items_received', 'items_processed', 'trays_packed', 'trays_delivered',
            'porsi_confirmed', 'defects_count', 'defect_rate_pct', 'expense_today_idr',
            'cost_per_porsi_today_idr', 'cost_per_porsi_target_idr']
    for k in keys:
        check(f'KPI has field "{k}"', k in kpi)
    check('target_porsi numeric', isinstance(kpi['target_porsi'], int))
    check('cost target = 15000', kpi['cost_per_porsi_target_idr'] == 15000)

    print('\n--- Compliance Score ---')
    r = requests.get(f'{B}/api/executive/compliance-score?days=30', headers=H)
    check('Compliance 200', r.status_code == 200)
    cs = r.json()
    check('Has composite', 'composite' in cs)
    check('Has 5 factors', len(cs['factors']) == 5)
    check('Has grade A/B/C/D', cs['grade'] in ('A', 'B', 'C', 'D'))
    factor_keys = ['inspections_completed_pct', 'menus_approved_pct', 'distribution_confirmed_pct',
                   'lra_submitted_pct', 'daily_checklists_done_pct']
    for k in factor_keys:
        check(f'Factor "{k}"', k in cs['factors'])
    check('Composite is 0-100', 0 <= cs['composite'] <= 100)

    # Validation
    r = requests.get(f'{B}/api/executive/compliance-score?days=3', headers=H)
    check('days < 7 rejected', r.status_code == 400)
    r = requests.get(f'{B}/api/executive/compliance-score?days=400', headers=H)
    check('days > 365 rejected', r.status_code == 400)

    print('\n--- Trend ---')
    for metric in ['porsi_confirmed', 'expense', 'defects', 'items_received']:
        r = requests.get(f'{B}/api/executive/trend?metric={metric}&days=30', headers=H)
        check(f'Trend metric={metric} 200', r.status_code == 200)
        check(f'  has 30 series points', len(r.json()['series']) == 30)

    r = requests.get(f'{B}/api/executive/trend?metric=invalid_metric&days=30', headers=H)
    check('Invalid metric rejected', r.status_code == 400)

    r = requests.get(f'{B}/api/executive/trend?days=200', headers=H)
    check('Trend days > 90 rejected', r.status_code == 400)

    print('\n--- Multi-kitchen (admin role gets through) ---')
    r = requests.get(f'{B}/api/executive/multi-kitchen', headers=H)
    check('Multi-kitchen 200 (admin)', r.status_code == 200)
    mk = r.json()
    check('Has kitchens array', 'kitchens' in mk)
    check('Has rankings', 'rankings' in mk)
    check('Rankings 3 categories', all(k in mk['rankings'] for k in ('best_compliance', 'lowest_cost', 'highest_defect')))

    print('\n--- Platform overview (platform_admin) ---')
    r = requests.get(f'{B}/api/executive/platform', headers=H)
    check('Platform 200 (admin is platform_admin)', r.status_code == 200)
    pf = r.json()
    check('Has totals', 'totals' in pf)
    check('Has per_org', 'per_org' in pf)
    for k in ['organizations', 'kitchens', 'users', 'porsi_nasional', 'items_received']:
        check(f'Totals has "{k}"', k in pf['totals'])

    print('\n--- BGN Compliance Bundle ---')
    r = requests.get(f'{B}/api/compliance/bundle?from_date=2026-04-01&to_date=2026-04-30', headers=H)
    check('Bundle 200', r.status_code == 200)
    b = r.json()
    for k in ['kitchen_id', 'from_date', 'to_date', 'lra_periods', 'food_samples',
              'food_samples_count', 'daily_checklists', 'variance', 'porsi_total']:
        check(f'Bundle has "{k}"', k in b)
    check('variance has defect_rate', 'defect_rate_pct' in b['variance'])

    # Validation
    r = requests.get(f'{B}/api/compliance/bundle?from_date=invalid&to_date=2026-04-30', headers=H)
    check('Invalid from_date rejected', r.status_code == 400)
    r = requests.get(f'{B}/api/compliance/bundle?from_date=2026-05-01&to_date=2026-04-01', headers=H)
    check('from > to rejected', r.status_code == 400)

    print('\n--- Auth boundaries ---')
    r = requests.get(f'{B}/api/executive/kpi')
    check('No auth → 401', r.status_code == 401)
    r = requests.get(f'{B}/api/executive/platform')
    check('Platform no auth → 401', r.status_code == 401)

    print(f'\n===== RESULT =====')
    print(f'PASS: {len(PASS)}/{len(PASS) + len(FAIL)}')
    print(f'FAIL: {len(FAIL)}')
    if FAIL:
        for f in FAIL: print(f'  - {f}')
        sys.exit(1)
    print('\n[DONE] Phase 9 all checks passed.')


if __name__ == '__main__':
    main()
