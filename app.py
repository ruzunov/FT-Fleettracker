from re import L
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import csv
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Required for flashing messages


# Helper function to read issues from CSV
def read_issues():
    issues = []
    if os.path.isfile('issues.csv'):
        with open('issues.csv', 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                issues.append(row)
    return issues

# Helper function to write issues back to CSV
def write_issues(issues):
    with open('issues.csv', 'w', newline='') as csvfile:
        fieldnames = ['Model', 'Number', 'Issue', 'Description', 'DateTime', 'Comments']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)

# Helper function to read resolved issues from CSV
def read_resolved_issues():
    resolved_issues = []
    if os.path.isfile('resolved_issues.csv'):
        with open('resolved_issues.csv', 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                resolved_issues.append(row)
    return resolved_issues
    
# Helper function to read resolved battery issues from CSV
def read_resolved_battery_issues():
    resolved_battery_issues = []
    if os.path.isfile('resolved_battery_issues.csv'):
        with open('resolved_battery_issues.csv', 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                resolved_battery_issues.append(row)
    return resolved_battery_issues

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
        with open(csv_path, 'r') as csvfile:
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
    with open(csv_path, 'a', newline='') as csvfile:
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
        with open('battery_issues.csv', 'w', newline='') as csvfile:
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
        with open('resolved_battery_issues.csv', 'a', newline='') as csvfile:
            fieldnames = ['Model', 'Number', 'Issue', 'Description', 'DateTime', 'Comments', 'ResolutionDateTime']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(resolved_issue)

        # Update battery_issues.csv by removing the resolved issue
        with open('battery_issues.csv', 'w', newline='') as csvfile:
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
        with open(csv_path, 'r') as csvfile:
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
        with open(csv_path, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields)
            if os.stat(csv_path).st_size == 0:
                writer.writeheader()
            writer.writerow(new_entry)

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
        with open(csv_path, 'r') as csvfile:
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
    with open('issues.csv', 'a', newline='') as csvfile:
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
    last_entry = {}
    csv_path = 'forklift_work_hours.csv'
    if os.path.exists(csv_path):
        with open(csv_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                key = (row['Model'], row['Number'])
                # Calculate differences for maintenance intervals
                row['GreasingDue'] = (int(row['WorkHours']) - int(row.get('GreasingWorkHours', '0'))) > int(row.get('GreasingInterval', '1000'))
                row['OilChangeDue'] = (int(row['WorkHours']) - int(row.get('OilChangeWorkHours', '0'))) > int(row.get('OilChangeInterval', '1000'))
                row['HydraulicChangeDue'] = (int(row['WorkHours']) - int(row.get('HydraulicChangeWorkHours', '0'))) > int(row.get('HydraulicChangeInterval', '1000'))
                row['FilterChangeDue'] = (int(row['WorkHours']) - int(row.get('FilterChangeWorkHours', '0'))) > int(row.get('FilterChangeInterval', '1000'))
                
                last_entry[key] = row  # Keep only the last entry for each Model/Number

    # Convert to list and sort by 'Number'
    sorted_data = sorted(last_entry.values(), key=lambda x: x['Number'])
    return sorted_data


@app.route('/maintenance', methods=['GET', 'POST'])
def maintenance():
    if request.method == 'POST':
        model = request.form['model']
        number = request.form['number']
        current_hours = request.form['current_hours']

        # Retrieve the last entry for the specific model and number
        last_entry = None
        csv_path = 'forklift_work_hours.csv'
        with open(csv_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['Model'] == model and row['Number'] == number:
                    last_entry = row

        # Prepare new entry with default values and update only where necessary
        new_entry = last_entry.copy() if last_entry else {}
        new_entry.update({
            'Model': model,
            'Number': number,
            'WorkHours': current_hours,
            'DateEntered': datetime.now().strftime("%Y-%m-%d, %H:%M:%S"),
            'Greasing': 'Yes' if request.form.get('greasing') == 'Yes' else last_entry.get('Greasing', 'No'),
            'GreasingDate': datetime.now().strftime("%Y-%m-%d") if request.form.get('greasing') == 'Yes' else last_entry.get('GreasingDate', ''),
            'GreasingWorkHours': current_hours if request.form.get('greasing') == 'Yes' else last_entry.get('GreasingWorkHours', ''),
            'GreasingInterval': '1000',
            'OilChange': 'Yes' if request.form.get('oil_change') == 'Yes' else last_entry.get('OilChange', 'No'),
            'OilChangeDate': datetime.now().strftime("%Y-%m-%d") if request.form.get('oil_change') == 'Yes' else last_entry.get('OilChangeDate', ''),
            'OilChangeWorkHours': current_hours if request.form.get('oil_change') == 'Yes' else last_entry.get('OilChangeWorkHours', ''),
            'OilChangeInterval': '1000',
            'HydraulicChange': 'Yes' if request.form.get('hydraulic_change') == 'Yes' else last_entry.get('HydraulicChange', 'No'),
            'HydraulicChangeDate': datetime.now().strftime("%Y-%m-%d") if request.form.get('hydraulic_change') == 'Yes' else last_entry.get('HydraulicChangeDate', ''),
            'HydraulicChangeWorkHours': current_hours if request.form.get('hydraulic_change') == 'Yes' else last_entry.get('HydraulicChangeWorkHours', ''),
            'HydraulicChangeInterval': '1000',
            'FilterChange': 'Yes' if request.form.get('filter_change') == 'Yes' else last_entry.get('FilterChange', 'No'),
            'FilterChangeDate': datetime.now().strftime("%Y-%m-%d") if request.form.get('filter_change') == 'Yes' else last_entry.get('FilterChangeDate', ''),
            'FilterChangeWorkHours': current_hours if request.form.get('filter_change') == 'Yes' else last_entry.get('FilterChangeWorkHours', ''),
            'FilterChangeInterval': '1000',
        })

        # Append new row to the CSV
        with open(csv_path, 'a', newline='') as csvfile:
            fieldnames = new_entry.keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if os.stat(csv_path).st_size == 0:
                writer.writeheader()
            writer.writerow(new_entry)

        return redirect(url_for('maintenance'))

    # Load the last entry for each forklift
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