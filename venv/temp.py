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

        # Prepare new entry with default "No" for fields left as "Changed"
        new_entry = last_entry.copy() if last_entry else {}
        new_entry.update({
            'Model': model,
            'Number': number,
            'DateEntered': datetime.now().strftime("%Y-%m-%d, %H:%M:%S"),
            'WorkHours': current_hours,
            'Greasing': 'Yes' if request.form.get('greasing') == 'Yes' else 'No',
            'GreasingDate': datetime.now().strftime("%Y-%m-%d") if request.form.get('greasing') == 'Yes' else last_entry.get('GreasingDate', ''),
            'GreasingWorkHours': current_hours if request.form.get('greasing') == 'Yes' else last_entry.get('GreasingWorkHours', ''),
            'GreasingInterval': '1000',
            'OilChange': 'Yes' if request.form.get('oil_change') == 'Yes' else 'No',
            'OilChangeDate': datetime.now().strftime("%Y-%m-%d") if request.form.get('oil_change') == 'Yes' else last_entry.get('OilChangeDate', ''),
            'OilChangeWorkHours': current_hours if request.form.get('oil_change') == 'Yes' else last_entry.get('OilChangeWorkHours', ''),
            'OilChangeInterval': '1000',
            'HydraulicChange': 'Yes' if request.form.get('hydraulic_change') == 'Yes' else 'No',
            'HydraulicChangeDate': datetime.now().strftime("%Y-%m-%d") if request.form.get('hydraulic_change') == 'Yes' else last_entry.get('HydraulicChangeDate', ''),
            'HydraulicChangeWorkHours': current_hours if request.form.get('hydraulic_change') == 'Yes' else last_entry.get('HydraulicChangeWorkHours', ''),
            'HydraulicChangeInterval': '1000',
            'FilterChange': 'Yes' if request.form.get('filter_change') == 'Yes' else 'No',
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
