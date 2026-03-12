from re import L
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import csv
import os
from datetime import datetime, timedelta
from collections import Counter, defaultdict

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Required for flashing messages

# ─── FLEET MANAGEMENT USERS ───────────────────────────────────────────────────
# To add more users: add entries to this dict as 'username': 'pin'
# To change a PIN:   edit the value next to the username
# Pins can be any string — numbers, letters, or mixed
FLEET_USERS = {
    'admin': '1234',
    # 'supervisor': '5678',   # ← uncomment and set pin to add more users
}

def check_fleet_pin(username, pin):
    """Return True if username+pin is valid."""
    return FLEET_USERS.get(username) == pin


# Helper function to read issues from CSV
def read_issues():
    issues = []
    if os.path.isfile('issues.csv'):
        with open('issues.csv', 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                issues.append(row)
    return issues

# Helper function to write issues back to CSV
def write_issues(issues):
    with open('issues.csv', 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Model', 'Number', 'Issue', 'Description', 'DateTime', 'Comments']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)

# ─── DASHBOARD ────────────────────────────────────────────────────────────────

def safe_read_csv(path, encoding='utf-8-sig'):
    rows = []
    if not os.path.isfile(path):
        return rows
    for enc in [encoding, 'cp1251', 'cp1252', 'latin-1']:
        try:
            with open(path, 'r', encoding=enc) as f:
                reader = csv.DictReader(f)
                rows = [r for r in reader]
            return rows
        except Exception:
            continue
    return rows

# Helper function to read resolved issues from CSV
def read_resolved_issues():
    return safe_read_csv('resolved_issues.csv')

# Helper function to read resolved battery issues from CSV
def read_resolved_battery_issues():
    return safe_read_csv('resolved_battery_issues.csv')

@app.route('/dashboard')
def dashboard():
    issues           = safe_read_csv('issues.csv')
    battery_issues   = safe_read_csv('battery_issues.csv')
    resolved         = safe_read_csv('resolved_issues.csv')
    resolved_battery = safe_read_csv('resolved_battery_issues.csv')
    work_hours_raw   = safe_read_csv('forklift_work_hours.csv')

    # Maintenance overdue (latest entry per unit)
    last_entry = {}
    for row in work_hours_raw:
        key = (row.get('Model',''), row.get('Number',''))
        last_entry[key] = row

    maintenance_overdue_list = []
    for row in last_entry.values():
        try: wh = float(row.get('WorkHours', 0))
        except: wh = 0
        overdue = False
        for prefix, default_interval in [('Greasing',500),('OilChange',10000),('HydraulicChange',6000),('FilterChange',1000)]:
            try:
                last_wh = float(row.get(f'{prefix}WorkHours', 0))
                interval = float(row.get(f'{prefix}Interval', default_interval))
                row[f'{prefix}Due'] = (wh - last_wh) > interval
                if row[f'{prefix}Due']: overdue = True
            except:
                row[f'{prefix}Due'] = False
        if overdue:
            maintenance_overdue_list.append(row)

    maintenance_overdue_list.sort(key=lambda x: x.get('Number',''))

    stats = {
        'open_forklift_issues': len(issues),
        'open_battery_issues':  len(battery_issues),
        'total_resolved':       len(resolved) + len(resolved_battery),
        'maintenance_overdue':  len(maintenance_overdue_list),
        'total_units':          len(last_entry),
    }

    all_issues = issues + resolved
    issue_types = Counter(r.get('Issue','Unknown') or 'Unknown' for r in all_issues if r.get('Issue'))
    issue_type_data = {'labels': list(issue_types.keys()), 'values': list(issue_types.values())}

    all_battery = battery_issues + resolved_battery
    bat_types = Counter(r.get('Issue','Unknown') or 'Unknown' for r in all_battery if r.get('Issue'))
    battery_type_data = {'labels': list(bat_types.keys()), 'values': list(bat_types.values())}

    today = datetime.now().date()
    day_counts = defaultdict(int)
    for r in resolved + resolved_battery:
        dt_str = r.get('ResolutionDateTime') or r.get('DateTime','')
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                d = datetime.strptime(dt_str[:19], fmt).date()
                if (today - d).days <= 29:
                    day_counts[d] += 1
                break
            except: continue

    trend_labels, trend_values = [], []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        trend_labels.append(d.strftime('%d/%m'))
        trend_values.append(day_counts.get(d, 0))
    trend_data = {'labels': trend_labels, 'values': trend_values}

    model_counts = Counter(r.get('Model','?') for r in all_issues + all_battery)
    model_data = {'labels': list(model_counts.keys()), 'values': list(model_counts.values())}

    unit_counts = Counter(f"{r.get('Model','')} {r.get('Number','')}" for r in all_issues + all_battery)
    top_raw = unit_counts.most_common(7)
    max_count = top_raw[0][1] if top_raw else 1
    top_offenders = [(unit, count, int(count/max_count*100)) for unit, count in top_raw]

    return render_template(
        'dashboard.html',
        stats=stats,
        current_issues=issues,
        maintenance_overdue_list=maintenance_overdue_list,
        top_offenders=top_offenders,
        issue_type_data=issue_type_data,
        battery_type_data=battery_type_data,
        trend_data=trend_data,
        model_data=model_data,
    )

# ──────────────────────────────────────────────────────────────────────────────

# Route to render the landing page
@app.route('/')
def landing_page():
    return render_template('landing.html')
    
# Route to render the issue type selection page for current issues
@app.route('/current_issue_type_selection')
def current_issue_type_selection():
    return render_template('current_issue_type_selection.html')

# Route to render the current battery issues page
@app.route('/current_battery_issues')
def current_battery_issues():
    battery_issues = read_battery_issues()
    return render_template('current_battery_issues.html', issues=battery_issues)

# Helper function to read battery issues from CSV
def read_battery_issues():
    battery_issues = []
    csv_path = 'battery_issues.csv'
    if os.path.isfile(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                battery_issues.append(row)
    return battery_issues

# Route to render the model selection page (index.html)
@app.route('/report')
def report_page():
    return render_template('index.html')

# Route to render the number selection page (number.html)
@app.route('/select_number', methods=['GET'])
def select_number_page():
    model = request.args.get('model')
    return render_template('number.html', model=model)

# Route to render the issue selection page (issue.html)
@app.route('/select_issue', methods=['GET'])
def select_issue_page():
    model = request.args.get('model')
    number = request.args.get('number')
    return render_template('issue.html', model=model, number=number)

# Route to render the confirmation page (confirm.html)
@app.route('/confirm', methods=['GET'])
def confirm_page():
    model = request.args.get('model')
    number = request.args.get('number')
    issue = request.args.get('issue')
    description = request.args.get('description')
    return render_template('confirm.html', model=model, number=number, issue=issue, description=description)

# Route for battery number selection page
@app.route('/battery_select_number', methods=['GET'])
def battery_select_number():
    model = request.args.get('model')  # Toyota or Still
    return render_template('battery_number.html', model=model)
    
    # Route for battery issue reporting page
@app.route('/report_battery_issue', methods=['GET'])
def report_battery_issue():
    model = request.args.get('model')
    number = request.args.get('number')
    return render_template('report_battery_issue.html', model=model, number=number)

    # Route to show last 10 resolved issues
@app.route('/last_10_resolved')
def last_10_resolved():
    all_rows = safe_read_csv('resolved_issues.csv')
    last_10 = list(reversed(all_rows[-10:]))
    return render_template('last_10_resolved.html', issues=last_10)

# Route to handle form submission for battery issues and save to CSV
@app.route('/submit_battery_issue', methods=['POST'])
def submit_battery_issue():
    model = request.form.get('model')
    number = request.form.get('number')
    issue = request.form.get('issue')
    description = request.form.get('description')

    # Capture the current date and time
    datetime_submitted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Path to battery issues CSV file
    csv_path = 'battery_issues.csv'

    # Check if the CSV file exists, if not, create it and add headers
    file_exists = os.path.isfile(csv_path)
    with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Model', 'Number', 'Issue', 'Description', 'DateTime', 'Comments']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()  # Write headers if the file is created

        # Write the submitted battery issue to the CSV file
        writer.writerow({
            'Model': model,
            'Number': number,
            'Issue': issue,
            'Description': description,
            'DateTime': datetime_submitted,
            'Comments': ''
        })

    return redirect(url_for('landing_page'))
    
# Route to display the comment page for a specific battery issue
@app.route('/comment_battery_issue/<int:index>')
def comment_battery_issue(index):
    battery_issues = read_battery_issues()
    if index < len(battery_issues):
        issue = battery_issues[index]
        return render_template('comment_battery_issue.html', issue=issue, index=index)
    return redirect(url_for('current_battery_issues'))

# Route to add a comment to a specific battery issue
@app.route('/add_battery_comment/<int:index>', methods=['POST'])
def add_battery_comment(index):
    comment = request.form.get('comment')
    battery_issues = read_battery_issues()

    if index < len(battery_issues):
        # Add a timestamp to the comment
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        comment_with_timestamp = f"{timestamp}: {comment}"

        # Append comment with timestamp to the issue
        if 'Comments' in battery_issues[index] and battery_issues[index]['Comments']:
            battery_issues[index]['Comments'] += f" | {comment_with_timestamp}"
        else:
            battery_issues[index]['Comments'] = comment_with_timestamp

        # Write the updated list back to battery_issues.csv
        with open('battery_issues.csv', 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Model', 'Number', 'Issue', 'Description', 'DateTime', 'Comments']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(battery_issues)

    return redirect(url_for('comment_battery_issue', index=index))

# Route to resolve a specific battery issue
@app.route('/resolve_battery_issue/<int:index>', methods=['POST'])
def resolve_battery_issue(index):
    battery_issues = read_battery_issues()
    if index < len(battery_issues):
        resolved_issue = battery_issues.pop(index)

        # Save the final comment with a timestamp
        final_comment = request.form.get('comment')
        resolution_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if final_comment:
            if 'Comments' in resolved_issue and resolved_issue['Comments']:
                resolved_issue['Comments'] += f" | Resolved at {resolution_timestamp}: {final_comment}"
            else:
                resolved_issue['Comments'] = f"Resolved at {resolution_timestamp}: {final_comment}"

        # Add the resolution timestamp
        resolved_issue['ResolutionDateTime'] = resolution_timestamp

        # Write the resolved issue to resolved_battery_issues.csv
        file_exists = os.path.isfile('resolved_battery_issues.csv')
        with open('resolved_battery_issues.csv', 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Model', 'Number', 'Issue', 'Description', 'DateTime', 'Comments', 'ResolutionDateTime']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(resolved_issue)

        # Update battery_issues.csv by removing the resolved issue
        with open('battery_issues.csv', 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Model', 'Number', 'Issue', 'Description', 'DateTime', 'Comments']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(battery_issues)

    return redirect(url_for('landing_page'))

# Route to render the current issues page (current_issues.html)
@app.route('/current_issues')
def current_issues():
    issues = read_issues()
    return render_template('current_issues.html', issues=issues)

# Route for battery issues model selection page
@app.route('/battery_issue_model_selection')
def battery_issue_model_selection():
    return render_template('battery_issue_model_selection.html')

# Route to render the issue type selection page (forklift or battery issues)
@app.route('/issue_type_selection')
def issue_type_selection():
    return render_template('issue_type_selection.html')

# Route to render the Service page
@app.route('/service')
def service_page():
    return render_template('service.html')

# ── Fleet Registry helpers ────────────────────────────────────────────────────
FLEET_CSV    = 'fleet_registry.csv'
BATTERY_CSV  = 'battery_registry.csv'
FLEET_FIELDS   = ['Model', 'Number']
BATTERY_FIELDS = ['Model', 'Number']

def read_fleet():
    return safe_read_csv(FLEET_CSV)

def read_batteries():
    return safe_read_csv(BATTERY_CSV)

def write_fleet(rows):
    with open(FLEET_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FLEET_FIELDS)
        w.writeheader()
        w.writerows(rows)

def write_batteries(rows):
    with open(BATTERY_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=BATTERY_FIELDS)
        w.writeheader()
        w.writerows(rows)

# ── Fleet Management page ─────────────────────────────────────────────────────
@app.route('/fleet_management', methods=['GET', 'POST'])
def fleet_management():
    if request.method == 'POST':
        action   = request.form.get('action')
        reg_type = request.form.get('reg_type')  # 'forklift' or 'battery'

        # ── PIN check ─────────────────────────────────────────────────────────
        username = request.form.get('username', '').strip().lower()
        pin      = request.form.get('pin', '').strip()
        if not check_fleet_pin(username, pin):
            flash('Incorrect username or PIN. Action not performed.', 'error')
            return redirect(url_for('fleet_management'))

        if action == 'add':
            model  = request.form.get('model', '').strip()
            number = request.form.get('number', '').strip().upper()
            if model and number:
                if reg_type == 'forklift':
                    rows = read_fleet()
                    if not any(r['Model'] == model and r['Number'] == number for r in rows):
                        rows.append({'Model': model, 'Number': number})
                        rows.sort(key=lambda x: (x['Model'], int(''.join(filter(str.isdigit, x['Number'])) or 0)))
                        write_fleet(rows)
                        flash(f'Forklift {model} {number} added successfully.', 'success')
                    else:
                        flash(f'{model} {number} already exists.', 'error')
                else:
                    rows = read_batteries()
                    if not any(r['Model'] == model and r['Number'] == number for r in rows):
                        rows.append({'Model': model, 'Number': number})
                        rows.sort(key=lambda x: (x['Model'], int(''.join(filter(str.isdigit, x['Number'])) or 0)))
                        write_batteries(rows)
                        flash(f'Battery {model} {number} added successfully.', 'success')
                    else:
                        flash(f'{model} {number} already exists.', 'error')

        elif action == 'delete':
            number = request.form.get('number', '').strip()
            model  = request.form.get('model', '').strip()
            if reg_type == 'forklift':
                rows = [r for r in read_fleet() if not (r['Model'] == model and r['Number'] == number)]
                write_fleet(rows)
                flash(f'Forklift {model} {number} removed.', 'success')
            else:
                rows = [r for r in read_batteries() if not (r['Model'] == model and r['Number'] == number)]
                write_batteries(rows)
                flash(f'Battery {model} {number} removed.', 'success')

        return redirect(url_for('fleet_management'))

    forklifts = read_fleet()
    batteries = read_batteries()
    return render_template('fleet_management.html', forklifts=forklifts, batteries=batteries)

# ── API endpoints for dynamic dropdowns ──────────────────────────────────────
@app.route('/api/forklifts')
def api_forklifts():
    model = request.args.get('model', '')
    rows = [r for r in read_fleet() if not model or r['Model'] == model]
    from flask import jsonify
    return jsonify([r['Number'] for r in rows])

@app.route('/api/batteries')
def api_batteries():
    model = request.args.get('model', '')
    rows = [r for r in read_batteries() if not model or r['Model'] == model]
    from flask import jsonify
    return jsonify([r['Number'] for r in rows])

# ── Service Intervals ─────────────────────────────────────────────────────────
INTERVAL_FIELDS = [
    ('Greasing',       'GreasingInterval'),
    ('OilChange',      'OilChangeInterval'),
    ('HydraulicChange','HydraulicChangeInterval'),
    ('FilterChange',   'FilterChangeInterval'),
]

def read_all_wh_rows():
    return safe_read_csv('forklift_work_hours.csv')

def write_all_wh_rows(rows):
    fields = [
        'Model','Number','WorkHours','DateEntered',
        'Greasing','GreasingDate','GreasingWorkHours','GreasingInterval',
        'OilChange','OilChangeDate','OilChangeWorkHours','OilChangeInterval',
        'HydraulicChange','HydraulicChangeDate','HydraulicChangeWorkHours','HydraulicChangeInterval',
        'FilterChange','FilterChangeDate','FilterChangeWorkHours','FilterChangeInterval',
    ]
    with open('forklift_work_hours.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)

@app.route('/service_intervals', methods=['GET','POST'])
def service_intervals():
    if request.method == 'POST':
        username = request.form.get('username','').strip().lower()
        pin      = request.form.get('pin','').strip()
        if not check_fleet_pin(username, pin):
            flash('Incorrect username or PIN.', 'error')
            return redirect(url_for('service_intervals'))

        action = request.form.get('action')
        all_rows = safe_read_csv('forklift_work_hours.csv')

        WH_FIELDS = [
            'Model','Number','WorkHours','DateEntered',
            'Greasing','GreasingDate','GreasingWorkHours','GreasingInterval',
            'OilChange','OilChangeDate','OilChangeWorkHours','OilChangeInterval',
            'HydraulicChange','HydraulicChangeDate','HydraulicChangeWorkHours','HydraulicChangeInterval',
            'FilterChange','FilterChangeDate','FilterChangeWorkHours','FilterChangeInterval'
        ]

        def save_wh(rows):
            with open('forklift_work_hours.csv', 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=WH_FIELDS, extrasaction='ignore')
                w.writeheader()
                w.writerows(rows)

        if action == 'bulk':
            model      = request.form.get('bulk_model','').strip()
            grease_int = request.form.get('bulk_grease','').strip()
            oil_int    = request.form.get('bulk_oil','').strip()
            hyd_int    = request.form.get('bulk_hyd','').strip()
            filt_int   = request.form.get('bulk_filt','').strip()
            count = 0
            for r in all_rows:
                if r.get('Model') == model:
                    if grease_int: r['GreasingInterval']        = grease_int
                    if oil_int:    r['OilChangeInterval']       = oil_int
                    if hyd_int:    r['HydraulicChangeInterval'] = hyd_int
                    if filt_int:   r['FilterChangeInterval']    = filt_int
                    count += 1
            save_wh(all_rows)
            flash(f'Updated intervals for {count} {model} rows.', 'success')

        elif action == 'unit':
            model      = request.form.get('unit_model','').strip()
            number     = request.form.get('unit_number','').strip()
            grease_int = request.form.get('unit_grease','').strip()
            oil_int    = request.form.get('unit_oil','').strip()
            hyd_int    = request.form.get('unit_hyd','').strip()
            filt_int   = request.form.get('unit_filt','').strip()
            count = 0
            for r in all_rows:
                if r.get('Model') == model and r.get('Number') == number:
                    if grease_int: r['GreasingInterval']        = grease_int
                    if oil_int:    r['OilChangeInterval']       = oil_int
                    if hyd_int:    r['HydraulicChangeInterval'] = hyd_int
                    if filt_int:   r['FilterChangeInterval']    = filt_int
                    count += 1
            save_wh(all_rows)
            flash(f'Updated intervals for {model} {number} ({count} rows).', 'success')

        return redirect(url_for('service_intervals'))

    # GET — build summary
    all_rows = safe_read_csv('forklift_work_hours.csv')
    latest = {}
    max_wh = {}
    for r in all_rows:
        k = (r.get('Model',''), r.get('Number',''))
        latest[k] = r   # keep last row for service dates/intervals
        try:
            wh = float(r.get('WorkHours', 0) or 0)
            if k not in max_wh or wh > max_wh[k]:
                max_wh[k] = wh
        except: pass

    units = []
    for (model, number), r in sorted(latest.items(),
            key=lambda x: (x[0][0], int(''.join(filter(str.isdigit, x[0][1])) or 0))):
        def safe_int(v):
            try: return int(float(v))
            except: return 0

        # Use max WorkHours seen, not just the latest row value
        wh = int(max_wh.get((model, number), 0))
        g_wh  = safe_int(r.get('GreasingWorkHours',0))
        g_int = safe_int(r.get('GreasingInterval',500))
        o_wh  = safe_int(r.get('OilChangeWorkHours',0))
        o_int = safe_int(r.get('OilChangeInterval',1000))
        h_wh  = safe_int(r.get('HydraulicChangeWorkHours',0))
        h_int = safe_int(r.get('HydraulicChangeInterval',2000))
        f_wh  = safe_int(r.get('FilterChangeWorkHours',0))
        f_int = safe_int(r.get('FilterChangeInterval',1000))

        def progress(last, interval, current):
            if interval <= 0: return 0, 0, False
            done   = max(0, current - last)
            pct    = min(100, round(done / interval * 100))
            due_at = last + interval
            return pct, due_at, done >= interval

        g_pct, g_due, g_over = progress(g_wh, g_int, wh)
        o_pct, o_due, o_over = progress(o_wh, o_int, wh)
        h_pct, h_due, h_over = progress(h_wh, h_int, wh)
        f_pct, f_due, f_over = progress(f_wh, f_int, wh)

        units.append({
            'model': model, 'number': number,
            'work_hours': wh,
            'last_date': r.get('DateEntered',''),
            'grease':    {'last':g_wh,'interval':g_int,'pct':g_pct,'due_at':g_due,'over':g_over,'date':r.get('GreasingDate','')},
            'oil':       {'last':o_wh,'interval':o_int,'pct':o_pct,'due_at':o_due,'over':o_over,'date':r.get('OilChangeDate','')},
            'hydraulic': {'last':h_wh,'interval':h_int,'pct':h_pct,'due_at':h_due,'over':h_over,'date':r.get('HydraulicChangeDate','')},
            'filter':    {'last':f_wh,'interval':f_int,'pct':f_pct,'due_at':f_due,'over':f_over,'date':r.get('FilterChangeDate','')},
        })

    from collections import Counter
    def modal_interval(model_name, field):
        vals = [r.get(field,'') for r in latest.values() if r.get('Model')==model_name]
        return Counter(vals).most_common(1)[0][0] if vals else ''

    bulk = {
        'Toyota': {'grease': modal_interval('Toyota','GreasingInterval'),
                   'oil':    modal_interval('Toyota','OilChangeInterval'),
                   'hyd':    modal_interval('Toyota','HydraulicChangeInterval'),
                   'filt':   modal_interval('Toyota','FilterChangeInterval')},
        'Still':  {'grease': modal_interval('Still','GreasingInterval'),
                   'oil':    modal_interval('Still','OilChangeInterval'),
                   'hyd':    modal_interval('Still','HydraulicChangeInterval'),
                   'filt':   modal_interval('Still','FilterChangeInterval')},
    }

    return render_template('service_intervals.html', units=units, bulk=bulk)

# ── Work Hours Log ────────────────────────────────────────────────────────────
WH_CSV    = 'forklift_work_hours.csv'
WH_FIELDS = [
    'Model','Number','WorkHours','DateEntered',
    'Greasing','GreasingDate','GreasingWorkHours','GreasingInterval',
    'OilChange','OilChangeDate','OilChangeWorkHours','OilChangeInterval',
    'HydraulicChange','HydraulicChangeDate','HydraulicChangeWorkHours','HydraulicChangeInterval',
    'FilterChange','FilterChangeDate','FilterChangeWorkHours','FilterChangeInterval'
]

@app.route('/work_hours_log', methods=['GET', 'POST'])
def work_hours_log():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        pin      = request.form.get('pin', '').strip()
        if not check_fleet_pin(username, pin):
            flash('Incorrect username or PIN.', 'error')
            return redirect(url_for('work_hours_log') + '?' + request.query_string.decode())

        # Delete selected rows by index (1-based, matching original file order)
        indices_to_delete = set()
        for v in request.form.getlist('delete_rows'):
            try:
                indices_to_delete.add(int(v))
            except ValueError:
                pass

        if indices_to_delete:
            all_rows = safe_read_csv(WH_CSV)
            kept = [r for i, r in enumerate(all_rows) if i not in indices_to_delete]
            with open(WH_CSV, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=WH_FIELDS, extrasaction='ignore')
                w.writeheader()
                w.writerows(kept)
            flash(f'Deleted {len(indices_to_delete)} log entr{"y" if len(indices_to_delete)==1 else "ies"}.', 'success')
        else:
            flash('No rows selected.', 'error')

        # Preserve filter in redirect
        qs = request.query_string.decode()
        return redirect(url_for('work_hours_log') + (('?' + qs) if qs else ''))

    # GET — load and filter
    filter_model  = request.args.get('model', 'all')
    filter_number = request.args.get('number', '').strip().upper()

    all_rows = safe_read_csv(WH_CSV)

    # Build unit list for filter dropdowns
    seen = set()
    units_list = []
    for r in all_rows:
        k = (r.get('Model',''), r.get('Number',''))
        if k not in seen and k[0]:
            seen.add(k)
            units_list.append(k)
    units_list.sort(key=lambda x: (x[0], int(''.join(filter(str.isdigit, x[1])) or 0)))

    # Apply filters and attach original row index
    rows_with_idx = []
    for i, r in enumerate(all_rows):
        if filter_model != 'all' and r.get('Model','') != filter_model:
            continue
        if filter_number and r.get('Number','') != filter_number:
            continue
        rows_with_idx.append((i, r))

    # Sort newest first (by DateEntered best-effort)
    def parse_date(d):
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d.%m.%Y %H:%M', '%d.%m.%Y'):
            try:
                from datetime import datetime
                return datetime.strptime(d, fmt)
            except: pass
        return datetime.min
    rows_with_idx.sort(key=lambda x: parse_date(x[1].get('DateEntered','')), reverse=True)

    return render_template('work_hours_log.html',
        rows=rows_with_idx,
        units_list=units_list,
        filter_model=filter_model,
        filter_number=filter_number,
        total=len(all_rows)
    )

# Route to render the comment and resolve issue page (comment_issue.html)
@app.route('/comment/<int:index>')
def comment_issue_page(index):
    issues = read_issues()
    if index < len(issues):
        issue = issues[index]
        return render_template('comment_issue.html', issue=issue, index=index)
    return redirect(url_for('current_issues'))

# Route to add a comment to an issue
@app.route('/add_comment/<int:index>', methods=['POST'])
def add_comment(index):
    comment = request.form.get('comment')
    issues = read_issues()

    if index < len(issues):
        # Add a timestamp to the comment
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        comment_with_timestamp = f"{timestamp}: {comment}"

        # Append comment with timestamp to the issue
        if 'Comments' in issues[index] and issues[index]['Comments']:
            issues[index]['Comments'] += f" | {comment_with_timestamp}"
        else:
            issues[index]['Comments'] = comment_with_timestamp
        write_issues(issues)

    return redirect(url_for('comment_issue_page', index=index))

@app.route('/resolve_issue/<int:index>', methods=['POST'])
def resolve_issue(index):
    issues = read_issues()  # Fetch unresolved issues
    if index < len(issues):
        # Remove the issue being resolved
        resolved_issue = issues.pop(index)
        
        # Set the new WorkHours and DateEntered based on form input
        new_work_hours = request.form.get('work_hours')
        new_date_entered = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Find the last entry for this Model and Number in forklift_work_hours.csv
        last_entry = None
        csv_path = 'forklift_work_hours.csv'
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['Model'] == resolved_issue['Model'] and row['Number'] == resolved_issue['Number']:
                    last_entry = row  # Keep updating to get the last occurrence

        # Define all required fields for the CSV
        fields = [
            'Model', 'Number', 'WorkHours', 'DateEntered',
            'Greasing', 'GreasingDate', 'GreasingWorkHours', 'GreasingInterval',
            'OilChange', 'OilChangeDate', 'OilChangeWorkHours', 'OilChangeInterval',
            'HydraulicChange', 'HydraulicChangeDate', 'HydraulicChangeWorkHours', 'HydraulicChangeInterval',
            'FilterChange', 'FilterChangeDate', 'FilterChangeWorkHours', 'FilterChangeInterval'
        ]

        # Create a new entry with updated WorkHours and DateEntered, retaining all other fields from last_entry
        new_entry = {field: last_entry.get(field, "No" if "Change" in field else "0") for field in fields}
        new_entry.update({
            'Model': resolved_issue['Model'],
            'Number': resolved_issue['Number'],
            'WorkHours': new_work_hours,
            'DateEntered': new_date_entered
        })

        # Remove any None keys if they exist (to prevent CSV writer errors)
        new_entry = {k: v for k, v in new_entry.items() if k is not None}

        # Write the updated row to forklift_work_hours.csv
        with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields)
            if os.stat(csv_path).st_size == 0:
                writer.writeheader()
            writer.writerow(new_entry)

        # Append the final resolution comment (if any)
        final_comment = request.form.get('comment', '').strip()
        resolution_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if final_comment:
            if resolved_issue.get('Comments'):
                resolved_issue['Comments'] += f" | Resolved at {resolution_timestamp}: {final_comment}"
            else:
                resolved_issue['Comments'] = f"Resolved at {resolution_timestamp}: {final_comment}"

        # ➕ NEW: Add resolution time and write to resolved_issues.csv
        resolved_issue['ResolutionDateTime'] = resolution_timestamp
        if resolved_issue.get('DateTime'):
            dt1 = datetime.strptime(resolved_issue['DateTime'], "%Y-%m-%d %H:%M:%S")
            dt2 = datetime.strptime(resolved_issue['ResolutionDateTime'], "%Y-%m-%d %H:%M:%S")
            delta = dt2 - dt1
            resolved_issue['ResolutionTime'] = f"{delta.days} days" if delta.days else f"{delta.seconds // 3600} hours"
        else:
            resolved_issue['ResolutionTime'] = "N/A"

        resolved_fields = list(resolved_issue.keys())
        with open('resolved_issues.csv', 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=resolved_fields)
            if os.stat('resolved_issues.csv').st_size == 0:
                writer.writeheader()
            writer.writerow(resolved_issue)

        # Write remaining unresolved issues back to forklift_work_hours.csv
        write_issues(issues)

    return redirect(url_for('landing_page'))


# Route to display work hours from forklift_work_hours.csv, filtered by model and number
@app.route('/view_work_hours', methods=['GET', 'POST'])
def view_work_hours():
    selected_model = request.form.get('model')  # Model selected by user
    selected_number = request.form.get('number')  # Number selected by user

    # Load all work hours data
    work_hours_data = []
    csv_path = 'forklift_work_hours.csv'
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                work_hours_data.append(row)

    # Filter data if model and number are selected
    filtered_data = [
        entry for entry in work_hours_data
        if (selected_model is None or entry['Model'] == selected_model) and
           (selected_number is None or entry['Number'] == selected_number)
    ]

    # Extract unique model and number options for the dropdowns
    models = sorted(set(entry['Model'] for entry in work_hours_data))
    numbers = sorted(set(entry['Number'] for entry in work_hours_data if entry['Model'] == selected_model)) if selected_model else []

    return render_template(
        'work_hours.html',
        work_hours=filtered_data,
        models=models,
        numbers=numbers,
        selected_model=selected_model,
        selected_number=selected_number
    )

# Route to handle form submission and save to CSV
@app.route('/submit', methods=['POST'])
def submit_issue():
    model = request.form.get('model')
    number = request.form.get('number')
    issue = request.form.get('issue')
    description = request.form.get('description')

    # Capture the current date and time
    datetime_submitted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check if the CSV file exists, if not, create it and add headers
    file_exists = os.path.isfile('issues.csv')
    with open('issues.csv', 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Model', 'Number', 'Issue', 'Description', 'DateTime', 'Comments']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()  # Write headers if the file is created

        # Write the submitted issue to the CSV file
        writer.writerow({'Model': model, 'Number': number, 'Issue': issue, 'Description': description, 'DateTime': datetime_submitted, 'Comments': ''})

    return redirect(url_for('landing_page'))



# Route to render the issue type selection page for resolved issues
@app.route('/select_resolved')
def select_resolved():
    return render_template('select_resolved.html')

# Route to view resolved forklift issues for a specific model and number
@app.route('/view_resolved', methods=['GET'])
def view_resolved_issues():
    model = request.args.get('model')
    number = request.args.get('number')

    # Read resolved issues and filter based on model and number
    resolved_issues = read_resolved_issues()
    filtered_issues = [issue for issue in resolved_issues if issue['Model'] == model and issue['Number'] == number]

    return render_template('resolved_issues.html', resolved_issues=filtered_issues, model=model, number=number)

# Route to view resolved battery issues for a specific model and number
@app.route('/view_resolved_battery', methods=['GET'])
def view_resolved_battery_issues():
    model = request.args.get('battery_model')
    number = request.args.get('battery_number')

    # Read resolved battery issues and filter based on model and number
    resolved_battery_issues = read_resolved_battery_issues()
    filtered_issues = [issue for issue in resolved_battery_issues if issue['Model'] == model and issue['Number'] == number]

    return render_template('resolved_battery_issues.html', resolved_issues=filtered_issues, model=model, number=number)

# Route to render confirm_battery.html
@app.route('/confirm_battery')
def confirm_battery():
    model = request.args.get('model')
    number = request.args.get('number')
    issue = request.args.get('issue')
    description = request.args.get('description')
    return render_template('confirm_battery.html', model=model, number=number, issue=issue, description=description)

# Helper function to read only the last entry for each forklift (model + number) and sort by Number
def read_work_hours_with_maintenance():
    """Safely read forklift_work_hours.csv and calculate maintenance due flags.
    Uses MAX WorkHours seen across all entries per unit as current hours,
    so a reset/low odometer entry doesn't break progress calculations."""
    last_entry = {}
    max_wh     = {}   # (model, number) -> highest WorkHours seen
    csv_path   = 'forklift_work_hours.csv'

    if not os.path.exists(csv_path):
        return []

    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                model  = row.get('Model', '').strip()
                number = row.get('Number', '').strip()
                if not model or not number:
                    continue
                key = (model, number)

                try:
                    wh = float(row.get('WorkHours', 0) or 0)
                except (ValueError, TypeError):
                    wh = 0

                # Track max hours and keep the latest row for service fields
                if key not in max_wh or wh > max_wh[key]:
                    max_wh[key] = wh
                last_entry[key] = row

    except Exception:
        return []

    # Now compute due flags using max_wh as current hours
    result = []
    for key, row in last_entry.items():
        work_hours = max_wh.get(key, 0)
        row = dict(row)  # copy so we don't mutate CSV data
        row['WorkHours'] = str(int(work_hours))  # overwrite with max

        row['GreasingDue']      = False
        row['OilChangeDue']     = False
        row['HydraulicChangeDue'] = False
        row['FilterChangeDue']  = False

        try:
            g_wh  = float(row.get('GreasingWorkHours', 0) or 0)
            g_int = float(row.get('GreasingInterval', 1000) or 1000)
            row['GreasingDue'] = g_int > 0 and (work_hours - g_wh) > g_int
        except: pass

        try:
            o_wh  = float(row.get('OilChangeWorkHours', 0) or 0)
            o_int = float(row.get('OilChangeInterval', 1000) or 1000)
            row['OilChangeDue'] = o_int > 0 and (work_hours - o_wh) > o_int
        except: pass

        try:
            h_wh  = float(row.get('HydraulicChangeWorkHours', 0) or 0)
            h_int = float(row.get('HydraulicChangeInterval', 2000) or 2000)
            row['HydraulicChangeDue'] = h_int > 0 and (work_hours - h_wh) > h_int
        except: pass

        try:
            f_wh  = float(row.get('FilterChangeWorkHours', 0) or 0)
            f_int = float(row.get('FilterChangeInterval', 1000) or 1000)
            row['FilterChangeDue'] = f_int > 0 and (work_hours - f_wh) > f_int
        except: pass

        result.append(row)

    return sorted(result, key=lambda x: x.get('Number', 'ZZZ'))

@app.route('/maintenance', methods=['GET', 'POST'])
def maintenance():
    if request.method == 'POST':
        # Safe form data extraction
        model = request.form.get('model', '').strip()
        number = request.form.get('number', '').strip()
        current_hours = request.form.get('current_hours', '0').strip()
        
        if not model or not number:
            flash('Model and Number are required')
            return redirect(url_for('maintenance'))
        
        csv_path = 'forklift_work_hours.csv'
        fields = [
            'Model', 'Number', 'WorkHours', 'DateEntered', 'Greasing', 'GreasingDate',
            'GreasingWorkHours', 'GreasingInterval', 'OilChange', 'OilChangeDate',
            'OilChangeWorkHours', 'OilChangeInterval', 'HydraulicChange', 
            'HydraulicChangeDate', 'HydraulicChangeWorkHours', 'HydraulicChangeInterval',
            'FilterChange', 'FilterChangeDate', 'FilterChangeWorkHours', 'FilterChangeInterval'
        ]
        
        # Get last entry or create new with defaults
        last_entry = {}
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        if row.get('Model') == model and row.get('Number') == number:
                            last_entry = row
                            break
            except:
                pass
        
        # Build new entry
        new_entry = {field: last_entry.get(field, 'No' if 'Change' in field else '0') for field in fields}
        new_entry.update({
            'Model': model,
            'Number': number,
            'WorkHours': current_hours,
            'DateEntered': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'Greasing': request.form.get('greasing', 'No'),
            'OilChange': request.form.get('oil_change', 'No'),
            'HydraulicChange': request.form.get('hydraulic_change', 'No'),
            'FilterChange': request.form.get('filter_change', 'No')
        })
        
        # Safe write
        try:
            with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fields)
                if os.stat(csv_path).st_size == 0:
                    writer.writeheader()
                writer.writerow(new_entry)
        except:
            flash('Error saving data')
        
        return redirect(url_for('maintenance'))
    
    # GET request - show page
    work_hours_data = read_work_hours_with_maintenance()
    return render_template('maintenance.html', work_hours=work_hours_data)


# Route to download the resolved forklift issues CSV file
@app.route('/download_resolved_csv')
def download_resolved_csv():
    csv_path = 'resolved_issues.csv'
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True, download_name='resolved_issues.csv', mimetype='text/csv')
    else:
        flash("The resolved forklift issues file is not available.")
        return redirect(url_for('select_resolved'))

# Route to download the resolved battery issues CSV file
@app.route('/download_resolved_battery_csv')
def download_resolved_battery_csv():
    csv_path = 'resolved_battery_issues.csv'
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True, download_name='resolved_battery_issues.csv', mimetype='text/csv')
    else:
        flash("The resolved battery issues file is not available.")
        return redirect(url_for('select_resolved'))

if __name__ == '__main__':
    app.run(debug=True)