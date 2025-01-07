from flask import Flask, request, render_template, redirect, url_for, session, send_file, jsonify, flash
from flask_socketio import SocketIO, emit
import pandas as pd
import os
import json
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dateutil.relativedelta import relativedelta
from werkzeug.utils import secure_filename
import requests
from base64 import b64encode
import random
import string
import openpyxl
from openpyxl import load_workbook

from docx import Document
from docx2pdf import convert
from num2words import num2words
from xhtml2pdf import pisa


app = Flask(__name__)
app.secret_key = 'Manish'  # Use a secure, unique secret key
socketio = SocketIO(app)

# Paths to files
employees_file = 'employees_hashed.csv'
leave_balances_csv = 'employee_leave_balances.csv'
holidays_csv = 'national_leave.csv'
upload_folder = 'static/profiles'
proofs_folder = 'static/proofs'
data_file = 'leave_data.json'
reimbursement_file = 'reimbursement_data.json'
cl_sl_leave_csv = 'CL_SL_Leave.csv'
unpaid_early_wfh_leave_csv = 'Unpaid_Early_WFH_Leave.csv'
records_csv = 'records.csv'
salary_data_file_path = 'salary_data_with_random_monthly_data.xlsx'
template_path = 'SALARY SLIP FORMAT.docx'
output_dir = 'generated_salary_slip'
html_template_path='salary_template.html'

# Flask app configuration
app.config['UPLOAD_FOLDER'] = upload_folder
os.makedirs(upload_folder, exist_ok=True)
os.makedirs(proofs_folder, exist_ok=True)

# Predefined manager passwords
manager_passwords = {
    'Digital Marketing': 'password_digital_marketing',
    'Market Research': 'password_market_research',
    'Data Analytics': 'password_data_analytics',
    'HR': 'password_hr',
    'Sales': 'password_sales'
}

def ensure_profiles_prefix(path):
    if not path.startswith('profiles/'):
        return f'profiles/{path}'
    return path

employees_df = pd.read_csv(employees_file)
employees_df['Employee ID'] = employees_df['Employee ID'].astype(str)
employees_df['profile_photo'] = employees_df['profile_photo'].fillna('default.jpg')
employees_df['profile_photo'] = employees_df['profile_photo'].apply(ensure_profiles_prefix)
employees = employees_df.set_index('Employee ID').to_dict(orient='index')





def load_employees_df():
    return pd.read_csv(employees_file)

def save_records_df(df):
    df.to_csv(records_csv, index=False)
    socketio.emit('update', {'action': 'refresh_records'})

def save_employees_df(df):
    df.to_csv(employees_file, index=False)
    socketio.emit('update', {'action': 'refresh_employees'})

def save_cl_sl_leave_df(df):
    df.to_csv(cl_sl_leave_csv, index=False)
    socketio.emit('update', {'action': 'refresh_leave_balances'})

def save_unpaid_early_wfh_leave_df(df):
    df.to_csv(unpaid_early_wfh_leave_csv, index=False)
    socketio.emit('update', {'action': 'refresh_leave_balances'})

def save_data(data):
    with open(data_file, 'w') as file:
        json.dump(data, file, indent=4)
    socketio.emit('update', {'action': 'refresh_leave_applications'})

def load_data():
    if os.path.exists(data_file):
        with open(data_file, 'r') as file:
            return json.load(file)
    else:
        return {}

def load_reimbursement_data():    
    if os.path.exists(reimbursement_file):
        with open(reimbursement_file, 'r') as file:
            return json.load(file)
    else:
        return {}

def load_unpaid_early_wfh_leave_df():
    return pd.read_csv(unpaid_early_wfh_leave_csv)

def load_cl_sl_leave_df():
    return pd.read_csv(cl_sl_leave_csv)

def save_reimbursement_data(data):
    with open(reimbursement_file, 'w') as file:
        json.dump(data, file, indent=4)

def get_current_date():
    return datetime.now().strftime("%Y-%m-%d")

def get_current_month():
    return datetime.now().strftime("%Y-%m")

def role_required(*roles):
    def decorator(f):
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                return "Access denied", 403
            return f(*args, **kwargs)
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator

@app.route('/add_employee', methods=['GET', 'POST'])
@role_required('hr', 'director')
def add_employee():
    if request.method == 'POST':
        try:
            # Collect form data
            employee_id = '6WR_' + request.form['employee_id']
            employee_name = request.form['employee_name']
            doj = request.form['doj']
            employee_email = request.form['employee_email'] + '@6wresearch.com'
            employee_password = request.form['employee_password']
            department = request.form['department']
            manager_email = request.form['manager_email']
            manager_password = manager_passwords.get(department, '')  # Get manager password from dictionary
            role = 'probation'  # Default role for new employees
            profile_photo = request.files['profile_photo']
            designation = request.form['designation']
            uan = request.form['uan']
            team_members = ""

            # Normalize Employee ID
            normalized_employee_id = employee_id.replace('6WR_', '').lstrip('0')
            

            # Load existing employee data
            employees_df = load_employees_df()
            

            # Check if Employee ID already exists
            employees_df['Normalized Employee ID'] = employees_df['Employee ID'].apply(lambda x: x.replace('6WR_', '').lstrip('0'))
            if not employees_df[employees_df['Normalized Employee ID'] == normalized_employee_id].empty:
                flash('Employee ID already exists. Cannot add the employee.', 'danger')
                
                return redirect(url_for('add_employee'))

            # Check if Employee Email already exists
            if not employees_df[employees_df['employee_email'] == employee_email].empty:
                flash('Employee email already exists. Cannot add the employee.', 'danger')
                app.logger.warning(f'Employee email {employee_email} already exists')
                return redirect(url_for('add_employee'))

            # Save profile photo
            filename = secure_filename(profile_photo.filename)
            profile_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_photo.save(profile_photo_path)
            

            # Calculate probation dates
            doj = pd.to_datetime(doj)
            first_probation = doj + pd.DateOffset(days=90)
            second_probation = doj + pd.DateOffset(days=180)
            doj_formatted = doj.strftime('%d-%m-%Y')
            first_probation_formatted = first_probation.strftime('%d-%m-%Y')
            second_probation_formatted = second_probation.strftime('%d-%m-%Y')

            # Add new employee data
            new_employee = pd.DataFrame([{
                'Employee ID': employee_id,
                'employee_name': employee_name,
                'doj': doj_formatted,
                'first_probation': first_probation_formatted,
                'second_probation': second_probation_formatted,
                'designation': designation,
                'department': department,
                'employee_email': employee_email,
                'employee_password': employee_password,
                'manager_email': manager_email,
                'manager_password': manager_password,
                'role': role,
                'team_members': team_members,
                'profile_photo': filename,
                'login_password': employee_id + "_" + "password",
                'Normalized Employee ID' : normalized_employee_id
            }])
            

            # Update manager's team_members column
            if manager_email in employees_df['employee_email'].values:
                manager_idx = employees_df[employees_df['employee_email'] == manager_email].index[0]
                if pd.notna(employees_df.at[manager_idx, 'team_members']):
                    employees_df.at[manager_idx, 'team_members'] += ',' + employee_id
                else:
                    employees_df.at[manager_idx, 'team_members'] = employee_id
                

            # Append new employee data to employees DataFrame
            employees_df = pd.concat([employees_df, new_employee], ignore_index=True)
            save_employees_df(employees_df)
            

            # Save new employee data to Records.csv
            records_df = pd.read_csv(records_csv,on_bad_lines='skip')
            records_df = pd.concat([records_df, new_employee], ignore_index=True)
            save_records_df(records_df)
            

            # Update CL_SL_Leave.csv
            cl_sl_leave_df = load_cl_sl_leave_df()
            new_cl_sl_leave_entry = pd.DataFrame([{
                'Employee ID': employee_id,
                'Employee Name': employee_name,
                'CL_Balance': 0,
                'SL_Balance': 0,
                'Comp_Off_Taken': 0,
                'Birthday/Aniversary': 0
            }])
            cl_sl_leave_df = pd.concat([cl_sl_leave_df, new_cl_sl_leave_entry], ignore_index=True)
            save_cl_sl_leave_df(cl_sl_leave_df)
            

            # Update Unpaid_Early_WFH_Leave.csv
            unpaid_early_wfh_leave_df = load_unpaid_early_wfh_leave_df()
            current_year = datetime.now().year
            new_unpaid_early_wfh_entries = []
            for month in range(1, 13):
                new_unpaid_early_wfh_entries.append({
                    'Employee ID': employee_id,
                    'Employee Name': employee_name,
                    'Month': f"{current_year}-{month:02}",
                    'Unpaid_Leave_Taken': 0,
                    'Early_Leave_Taken': 0,
                    'WFH_Taken': 0,
                    'Comp_Pay_Taken': 0,
                    'reimbursements': 0,
                    'incentives': 0
                })
            unpaid_early_wfh_leave_df = pd.concat([unpaid_early_wfh_leave_df, pd.DataFrame(new_unpaid_early_wfh_entries)], ignore_index=True)
            save_unpaid_early_wfh_leave_df(unpaid_early_wfh_leave_df)
            

            # Update the 12 monthly CSV files
            csv_directory = r"/home/v3wihx1dfu5s/leave-app/monthly_csv"
            for month in range(1, 13):
                try:
                    month_name = datetime(current_year, month, 1).strftime('%B')
                    csv_file_path = os.path.join(csv_directory, f"{month_name}.csv")
                    monthly_df = pd.read_csv(csv_file_path)
                    new_row = {
                        'Employee ID': employee_id,
                        'employee_name': employee_name,
                        'month': month_name,
                        'uan': uan,
                        'salary': 0,
                        'basic salary': 0,
                        'hra': 0,
                        'conveyance': 0,
                        'total earnings': 0,
                        'Unpaid_Leave_Taken': 0,
                        'compensatory pay': 0,
                        'reimbursements': 0,
                        'incentives': 0,
                        'net pay': 0,
                        'total deductions': 0,
                        'amount': 0,
                        'total_days_month': pd.Period(year=current_year, month=month, freq='M').days_in_month,
                        'total_paid_days': 0,
                        'in words': 'zero only /-',
                        'Comp_Pay_Taken': 0,
                        'deductions': 0
                    }
                    monthly_df = pd.concat([monthly_df, pd.DataFrame([new_row])], ignore_index=True)
                    monthly_df.to_csv(csv_file_path, index=False)
                    
                except Exception as e:
                    
                    print(f"Error processing month {month_name} for employee {employee_id}: {str(e)}")
                    
                    

            # Update the in-memory employees dictionary
            employees[employee_id] = {
                'employee_name': employee_name,
                'doj': doj_formatted,
                'designation': designation,
                'department': department,
                'employee_email': employee_email,
                'employee_password': employee_password,
                'manager_email': manager_email,
                'manager_password': manager_password,
                'role': role,
                'team_members': team_members,
                'profile_photo': filename
            }
            

            # Notify via socket
            socketio.emit('update', {'action': 'add', 'employee': new_employee.to_dict(orient='records')[0]})
            flash('Employee added successfully.', 'success')

        except Exception as e:
            app.logger.error(f'Error adding employee: {str(e)}')
            flash(f'Error adding employee: {str(e)}', 'danger')

        return redirect(url_for('add_employee'))

    return render_template('add_employee.html')

@app.route('/extend_probation/<employee_id>', methods=['POST'])
@role_required('hr', 'director')
def extend_probation(employee_id):
    current_date = datetime.now()
    probation_end_date = current_date + timedelta(days=90)

    employees_df = load_employees_df()
    employees_df.loc[employees_df['Employee ID'] == employee_id, 'doj'] = probation_end_date.strftime('%Y-%m-%d')
    save_employees_df(employees_df)

    flash('Employee probation extended successfully.', 'success')
    socketio.emit('update', {'action': 'extend', 'employee_id': employee_id, 'probation_end_date': probation_end_date.strftime('%Y-%m-%d')})
    return redirect(url_for('probation_employees'))

@app.route('/filter_employees', methods=['GET'])
def filter_employees():
    letter = request.args.get('letter').lower()
    employees_df = load_employees_df()
    results = employees_df[employees_df['employee_name'].str.lower().str.startswith(letter, na=False)]
    results = results[['Employee ID', 'employee_name']].to_dict(orient='records')
    return jsonify(results)

@app.route('/delete_employee', methods=['GET', 'POST'])
@role_required('hr', 'director')
def delete_employee():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = session.get('role')
    last_login = session.get('last_login')
    today_date = get_current_date()
    user_name = employees[user_id]['employee_name']
    profile_photo = employees[user_id].get('profile_photo', 'profiles/default.jpg')

    try:
        employees_df = load_employees_df()
    except Exception as e:
        print(f"Error loading employees_df: {e}")
        return "Error loading employee data", 500

    if request.method == 'POST':
        employee_ids = request.json.get('employee_ids', [])

        if not employee_ids:
            return "No employees selected.", 400

        try:
            cl_sl_leave_df = load_cl_sl_leave_df()
            unpaid_early_wfh_leave_df = load_unpaid_early_wfh_leave_df()
            employee_df = load_employees_df()  # Load the employee_hashed.csv DataFrame
        except Exception as e:
            print(f"Error loading leave DataFrames: {e}")
            return "Error loading leave data", 500

        for employee_id in employee_ids:
            # Delete the employee from employees_df
            employees_df = employees_df[employees_df['Employee ID'] != employee_id]

            # Delete the employee from cl_sl_leave_df
            cl_sl_leave_df = cl_sl_leave_df[cl_sl_leave_df['Employee ID'] != employee_id]

            # Delete the employee from unpaid_early_wfh_leave_df
            unpaid_early_wfh_leave_df = unpaid_early_wfh_leave_df[unpaid_early_wfh_leave_df['Employee ID'] != employee_id]

            # Remove the employee_id from the team_member column of its manager row in employee_df
            if not employees_df[employees_df['Employee ID'] == employee_id].empty:
                manager_email = employees_df[employees_df['Employee ID'] == employee_id].iloc[0]['manager_email']
                manager_idx = employees_df[employees_df['employee_email'] == manager_email].index
                if not manager_idx.empty:
                    team_members = employees_df.at[manager_idx[0], 'team_members']
                    if pd.notna(team_members):
                        updated_team_members = ','.join([tm for tm in team_members.split(',') if tm != employee_id])
                        employees_df.at[manager_idx[0], 'team_members'] = updated_team_members

            # Update the 12 monthly CSV files
            csv_directory = r"/home/v3wihx1dfu5s/leave-app/monthly_csv"
            for month in range(1, 13):
                month_name = datetime(datetime.now().year, month, 1).strftime('%B')
                csv_file_path = os.path.join(csv_directory, f"{month_name}.csv")
                if os.path.exists(csv_file_path):
                    monthly_df = pd.read_csv(csv_file_path)
                    monthly_df = monthly_df[monthly_df['Employee ID'] != employee_id]
                    monthly_df.to_csv(csv_file_path, index=False)

        # Save the updated DataFrames
        try:
            save_employees_df(employees_df)
            save_cl_sl_leave_df(cl_sl_leave_df)
            save_unpaid_early_wfh_leave_df(unpaid_early_wfh_leave_df)
        except Exception as e:
            print(f"Error saving updated DataFrames: {e}")
            return "Error saving updated data", 500

        socketio.emit('update', {'action': 'delete', 'employee_ids': employee_ids})
        return jsonify({"message": "Employees deleted successfully."}), 200

    employees_list = employees_df.to_dict(orient='records')
    return render_template('delete_employee.html', employees=employees_list, user_name=user_name, role=role, last_login=last_login, today_date=today_date, profile_photo=profile_photo)


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['employee_id']
        password = request.form['password']

        user_id = str(user_id)

        employees_df = load_employees_df()
        employee_record = employees_df[employees_df['Employee ID'] == user_id]

        if not employee_record.empty:
            expected_password = employee_record['login_password'].values[0]

            if password == expected_password:
                session['user_id'] = user_id
                session['role'] = employees[user_id]['role']
                session['last_login'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                session['department'] = employee_record['department'].values[0]
                session['designation'] = employee_record['designation'].values[0]
                session['doj'] = employee_record['doj'].values[0]

                socketio.emit('update', {'action': 'login', 'user_id': user_id, 'role': session['role']})
                return redirect(url_for('welcome'))
            else:
                return render_template('index.html', error='Invalid credentials')
        else:
            return render_template('index.html', error='Invalid credentials')
    return render_template('index.html')

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.form['email']
    employee_id = request.form['employee_id']

    # Validate employee ID
    if not employee_id.startswith('6WR_'):
        return jsonify({'message': 'Invalid Employee ID'}), 400

    # Load employee data
    employees_df = load_employees_df()  # Assuming this loads a DataFrame of employee data
    employee_record = employees_df[(employees_df['employee_email'] == email) & (employees_df['Employee ID'] == employee_id)]

    # If employee exists
    if not employee_record.empty:
        user_id = employee_record['Employee ID'].values[0]
        reset_token = generate_reset_token()  # Generate secure reset token
        token_expiry = datetime.now() + timedelta(hours=1)  # Token expiry in 1 hour
        unique_link = f"https://hr.6wconsult.com/login/reset_password?user_id={user_id}&token={reset_token}"

        # Store token and expiry in session
        session['reset_token'] = reset_token
        session['token_expiry'] = token_expiry.strftime('%Y-%m-%d %H:%M:%S')

        # Prepare email details
        subject = 'Password Reset Link'
        body = render_template(
            'password_reset.html',
            unique_link=unique_link,
            current_year=datetime.now().year
        )

        # Send email using the send_email function
        if send_email(subject, email, body):
            return jsonify({'message': 'Email sent'}), 200
        else:
            return jsonify({'message': 'Failed to send email'}), 500
    else:
        return jsonify({'message': 'Email/Employee ID not found'}), 404


def generate_reset_token(length=20):
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for i in range(length))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    user_id = request.args.get('user_id')
    token = request.args.get('token')

    token_expiry = session.get('token_expiry')
    if not token_expiry or datetime.now() > datetime.strptime(token_expiry, '%Y-%m-%d %H:%M:%S'):
        return 'Expired reset link', 400

    if token != session.get('reset_token'):
        return 'Invalid reset link', 400

    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            return render_template('reset_password.html', error='Passwords do not match', user_id=user_id, token=token)

        employees_df = load_employees_df()
        employees_df.loc[employees_df['Employee ID'] == user_id, 'login_password'] = new_password

        save_employees_df(employees_df)

        session.pop('reset_token', None)
        session.pop('token_expiry', None)

        return render_template('reset_password.html', success=True)

    return render_template('reset_password.html', user_id=user_id, token=token)

@app.route('/logout')
def logout():
    session.clear()
    socketio.emit('update', {'action': 'logout'})
    return redirect(url_for('login'))

@app.route('/welcome')
def welcome():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    role = session.get('role')
    last_login = session.get('last_login')
    today_date = datetime.now().strftime("%d-%m-%Y")
    if user_id in employees:
        user_name = employees[user_id]['employee_name']
        profile_photo = employees[user_id].get('profile_photo', 'profiles/default.jpg')
        department = session.get('department', 'N/A')
        designation = session.get('designation', 'N/A')
        doj = session.get('doj', 'N/A')
        return render_template('welcome.html', user_name=user_name, role=role, last_login=last_login, 
                               today_date=today_date, profile_photo=profile_photo, department=department, 
                               designation=designation, doj=doj, employee_id=user_id)
    else:
        return "Employee not found", 404

import requests
import logging
from pythonjsonlogger import jsonlogger

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create file handler
log_file = 'app_logs.json'
file_handler = logging.FileHandler(log_file)

# Define JSON formatter
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def process_log_record(self, log_record):
        # Add custom timestamp format
        log_record['timestamp'] = datetime.now().isoformat()
        return super().process_log_record(log_record)

# Add JSON formatter to file handler
formatter = CustomJsonFormatter('%(timestamp)s %(levelname)s %(message)s')
file_handler.setFormatter(formatter)

# Add file handler to logger
logger.addHandler(file_handler)


@app.route('/apply', methods=['GET', 'POST'])
def apply():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_info = employees[user_id]
    role = user_info['role']
    last_login = session.get('last_login')
    today_date = datetime.now().strftime('%Y-%m-%d')
    user_name = user_info['employee_name']
    profile_photo = employees[user_id].get('profile_photo', 'profiles/default.jpg')
    logging.info(f"User {user_id} ({user_info['employee_name']}) accessed apply page.")

    if request.method == 'POST':
        logging.info(f"Processing leave application for user {user_id}.")
        leave_type = request.form['leave_type']
        leave_mode = request.form['leave_mode']
        start_date_str = request.form['start_date']
        end_date_str = request.form['end_date']
        reason = request.form['reason']
        manager_email = user_info['manager_email']

        start_date = parse_date(start_date_str)
        end_date = parse_date(end_date_str)
        logging.info(f"Parsed dates - Start: {start_date}, End: {end_date}")
        today = datetime.now()
        min_date = today - timedelta(days=15)
        max_date = today + timedelta(days=30)
        leave_month = start_date.strftime('%Y-%m')

        if start_date > end_date:
            return render_template('apply.html', user_name=user_name, role=role, last_login=last_login, 
                                   today_date=today_date, profile_photo=profile_photo,
                                   error='Start Date cannot be ahead of End Date.')

        if start_date < min_date:
            return render_template('apply.html', user_name=user_name, role=role, last_login=last_login, 
                                   today_date=today_date, profile_photo=profile_photo,
                                   error='Leave dates cannot be more than 7 days in the past.')

        if end_date > max_date:
            return render_template('apply.html', user_name=user_name, role=role, last_login=last_login, 
                                   today_date=today_date, profile_photo=profile_photo,
                                   error='Leave dates cannot be more than 2 month in the future.')

        data = load_data()
        logging.info(f"Loaded data for validation. Checking for overlapping leaves.")
        for application in data.values():
            if application['employee_id'] == user_id and application['status'] == 'Approved':
                existing_start_date = parse_date(application['start_date'])
                existing_end_date = parse_date(application['end_date'])
                
                # Check if there is any overlap with an existing approved leave
                if (start_date <= existing_end_date) and (end_date >= existing_start_date):
                    if leave_mode == 'Half Day' and application['leave_mode'] == 'Half Day' and start_date == existing_start_date:
                        # Check if the user has already applied for two half days on the same date
                        approved_half_days_on_date = sum(
                            1 for app in data.values()
                            if app['employee_id'] == user_id and app['status'] == 'Approved'
                            and app['leave_mode'] == 'Half Day' and parse_date(app['start_date']) == start_date
                        )
                        if approved_half_days_on_date >= 2:
                            return render_template('apply.html', user_name=user_name, role=role, last_login=last_login, 
                                                   today_date=today_date, profile_photo=profile_photo,
                                                   error='You have already applied for two half days on this date.')
                        continue
                    else:
                        return render_template('apply.html', user_name=user_name, role=role, last_login=last_login, 
                                               today_date=today_date, profile_photo=profile_photo,
                                               error='Leave application overlaps with an already approved leave.')

        leave_days = (end_date - start_date).days + 1
        if leave_mode == 'Half Day':
            leave_days /= 2

        unpaid_early_wfh_leave_df = load_unpaid_early_wfh_leave_df()
        cl_sl_leave_df = load_cl_sl_leave_df()
        current_cl_balance = cl_sl_leave_df.loc[cl_sl_leave_df['Employee ID'] == user_id, 'CL_Balance'].sum()
        current_sl_balance = cl_sl_leave_df.loc[cl_sl_leave_df['Employee ID'] == user_id, 'SL_Balance'].sum()
        current_comp_off_balance = cl_sl_leave_df.loc[cl_sl_leave_df['Employee ID'] == user_id, 'Comp_Off_Taken'].sum()

        if role == 'probation':
            if leave_type not in ['Unpaid Leave', 'Work from Home']:
                return render_template(
                    'apply.html', 
                    user_name=user_name, 
                    role=role, 
                    last_login=last_login, 
                    today_date=today_date, 
                    profile_photo=profile_photo,
                    error='Probation employees can only apply for Unpaid Leave or Work from Home.'
                )
        
        if leave_type == 'Casual Leave':
            available_balance = current_cl_balance
        elif leave_type == 'Sick Leave':
            available_balance = current_sl_balance
        elif leave_type == 'Compensatory Off':
            available_balance = current_comp_off_balance
        elif leave_type == 'Unpaid Leave':
            available_balance = 0
        elif leave_type == 'Work from Home':
            available_balance = float('inf')
        elif leave_type == 'Compensatory Pay':
            available_balance = float('inf')
        else:
            available_balance = 0
        
        if leave_type == 'Early Leave':
            existing_early_leaves = unpaid_early_wfh_leave_df.loc[
                (unpaid_early_wfh_leave_df['Employee ID'] == user_id) & 
                (unpaid_early_wfh_leave_df['Month'] == leave_month), 
                'Early_Leave_Taken'
            ].sum()
            if existing_early_leaves != 0:
                return render_template('apply.html', error='Only one early leave is allowed in a month')
        
        if leave_type == 'Birthday/Anniversary':
                    existing_Birthday_Aniversary_leaves = cl_sl_leave_df.loc[
                        (cl_sl_leave_df['Employee ID'] == user_id), 
                        'Birthday/Aniversary'
                    ].sum()
                    if existing_Birthday_Aniversary_leaves != 0:
                        return render_template('apply.html', error='Only one Birthday/Anniversary leave is allowed in a year')
        
        unpaid_leave_days = max(0, leave_days - available_balance)
        if unpaid_leave_days > 0 and leave_type in ['Casual Leave', 'Sick Leave', 'Compensatory Off']:
            return render_template(
                'apply.html', 
                user_name=user_name, 
                role=role, 
                last_login=last_login, 
                today_date=today_date, 
                profile_photo=profile_photo,
                error='Insufficient leave balance. Please adjust your leave duration.'
            )
        
        logging.info(f"Saving leave application for {user_id}.")
        employee_name = user_info['employee_name'].replace(' ', '_')
        user_applications = [app_id for app_id in data.keys() if app_id.startswith(employee_name)]
        # Determine the next application number based on existing applications
        next_application_number = len(user_applications) + 1
        # Create a random 4-character token for added uniqueness
        random_token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        # Generate the application ID using employee_name, next_application_number, and random token
        application_id = f"{employee_name}_{next_application_number}_{random_token}"
        data[application_id] = {
            'employee_id': user_id,
            'employee_name': user_info['employee_name'],
            'leave_type': leave_type,
            'leave_mode': leave_mode,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'reason': reason,
            'status': 'Pending',
            'date_of_apply': today_date,
            'unpaid_leave_days': unpaid_leave_days
        }

        approve_link = f"https://hr.6wconsult.com/login/approve/{application_id}"
        deny_link = f"https://hr.6wconsult.com/login/deny/{application_id}"

        subject = f"Leave Application from {user_info['employee_name']}"
        # Render the email body from the HTML template
        body = render_template('email_body.html', 
                               employee_name=user_info['employee_name'], 
                               leave_type=leave_type, 
                               leave_mode=leave_mode,
                               start_date=start_date_str, 
                               end_date=end_date_str, 
                               reason=reason,
                               approve_link=approve_link,
                               deny_link=deny_link)

        if send_email(subject, manager_email, body):
            save_data(data)
            logging.info("Email sent successfully.")
            return redirect(url_for('welcome'))
        else:
            logging.error("Failed to send email to manager.")
            return render_template('apply.html', user_name=user_name, role=role, last_login=last_login, 
                                   today_date=today_date, profile_photo=profile_photo,
                                   error='Failed to send email to manager. Please try again later.')

    leave_options = ['Unpaid Leave', 'Work from Home'] if role == 'probation' else ['Casual Leave', 'Sick Leave', 'Early Leave', 'Compensatory Off', 'Compensatory Pay', 'Unpaid Leave', 'Work from Home']
    return render_template('apply.html', user_name=user_name, role=role, last_login=last_login, 
                           today_date=today_date, profile_photo=profile_photo, leave_options=leave_options)


def send_email(subject, recipient, body, is_html=False):
    try:
        # Prepare email payload with 'subject_line' for the subject
        email_data = {
            'to': recipient,
            'subject_line': subject,  # Use 'subject_line' instead of 'subject'
            'msg': body,              # Body of the email
            'from': "noreply@6wconsult.com"
        }
        
        # Send the request to the email sending API
        response = requests.post('http://6wconsult.com/api-mail-send', json=email_data)
        
        # Check the response status
        if response.status_code == 200:
            print(f"Email sent successfully to {recipient}")
            return True
        else:
            print(f"Failed to send email. Status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error sending email: {e}")
        return False


def send_approval_email(employee_email, employee_name, leave_type, leave_mode, start_date, end_date):
    # Render the HTML template with the appropriate values
    html_content = render_template(
        'leave_approval_template.html',
        employee_name=employee_name,
        leave_type=leave_type,
        leave_mode=leave_mode,
        start_date=start_date,
        end_date=end_date
    )

    # Send the HTML email
    send_email("Leave Application Approved", employee_email, html_content, is_html=True)


def send_denial_email(employee_email, employee_name, leave_type, leave_mode, start_date, end_date):
    # Render the HTML template with the appropriate values
    html_content = render_template(
        'leave_denial_template.html',
        employee_name=employee_name,
        leave_type=leave_type,
        leave_mode=leave_mode,
        start_date=start_date,
        end_date=end_date
    )

    # Send the HTML email
    send_email("Leave Application Denied", employee_email, html_content, is_html=True)



def send_reimbursement_approval_email(employee_email, employee_name, reimbursement_type, amount, reason):
    html_content = render_template(
        'reimbursement_approval_template.html',
        employee_name=employee_name,
        reimbursement_type=reimbursement_type,
        amount=amount,
        reason=reason
    )
    send_email("Reimbursement Approved", employee_email, html_content, is_html=True)

def send_reimbursement_denial_email(employee_email, employee_name, reimbursement_type, amount, reason):
    html_content = render_template(
        'reimbursement_denial_template.html',
        employee_name=employee_name,
        reimbursement_type=reimbursement_type,
        amount=amount,
        reason=reason
    )
    send_email("Reimbursement Denied", employee_email, html_content, is_html=True)

def send_hr_approval_notification_email(hr_email, employee_name, leave_type, leave_mode, start_date, end_date):
    html_content = render_template(
        'hr_leave_approval_notification.html',
        employee_name=employee_name,
        leave_type=leave_type,
        leave_mode=leave_mode,
        start_date=start_date,
        end_date=end_date
    )
    send_email("Leave Approved Notification", hr_email, html_content, is_html=True)

def send_hr_denial_notification_email(hr_email, employee_name, leave_type, leave_mode, start_date, end_date):
    html_content = render_template(
        'hr_leave_denial_notification.html',
        employee_name=employee_name,
        leave_type=leave_type,
        leave_mode=leave_mode,
        start_date=start_date,
        end_date=end_date
    )
    send_email("Leave Denied Notification", hr_email, html_content, is_html=True)


@app.route('/leave_balance', methods=['GET', 'POST'])
def leave_balance():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_info = employees[user_id]
    role = user_info['role']
    last_login = session.get('last_login')
    today_date = get_current_date()
    current_month = get_current_month()
    user_name = user_info['employee_name']
    profile_photo = user_info.get('profile_photo', 'profiles/default.jpg')

    cl_sl_leave_df = load_cl_sl_leave_df()
    unpaid_early_wfh_leave_df = load_unpaid_early_wfh_leave_df()

    if request.method == 'POST':
        selected_month = request.form.get('month')
    else:
        selected_month = current_month

    leave_balances_user = cl_sl_leave_df[cl_sl_leave_df['Employee ID'] == user_id]
    if not leave_balances_user.empty:
        casual_leave_balance = leave_balances_user['CL_Balance'].values[0]
        sick_leave_balance = leave_balances_user['SL_Balance'].values[0]
        comp_off_taken1 = leave_balances_user['Comp_Off_Taken'].values[0]
    else:
        casual_leave_balance = 0
        sick_leave_balance = 0
        comp_off_taken1 = 0

    total_leaves_left = casual_leave_balance + sick_leave_balance

    leave_taken_user = unpaid_early_wfh_leave_df[
        (unpaid_early_wfh_leave_df['Employee ID'] == user_id) &
        (unpaid_early_wfh_leave_df['Month'] <= selected_month)
    ]

    unpaid_leave_taken = leave_taken_user['Unpaid_Leave_Taken'].sum()
    early_leave_taken = leave_taken_user['Early_Leave_Taken'].sum()
    wfh_taken = leave_taken_user['WFH_Taken'].sum()
    comp_pay_taken = int(leave_taken_user['Comp_Pay_Taken'].sum())

    user_info = {
        'employee_name': user_name,
        'role': role,
        'profile_photo': profile_photo,
        'casual_leave_balance': casual_leave_balance,
        'sick_leave_balance': sick_leave_balance,
        'total_leaves_left': total_leaves_left,
        'unpaid_leave_taken': unpaid_leave_taken,
        'early_leave_taken': early_leave_taken,
        'wfh_taken': wfh_taken,
        'comp_off_taken': comp_off_taken1,
        'comp_pay_taken': comp_pay_taken
    }

    months = get_month_list_until_current()

    return render_template('leave_balance.html', user_info=user_info, last_login=last_login, today_date=today_date,
                           profile_photo=profile_photo, user_name=user_name, selected_month=selected_month, months=months, role=role)

def get_month_list_until_current():
    today = datetime.now()
    start_date = datetime(today.year, 1, 1)
    end_date = datetime(today.year, today.month, 1)

    month_list = pd.date_range(start_date, end_date, freq='MS').strftime('%Y-%m').tolist()
    return month_list

@app.route('/team_leave_balance')
def team_leave_balance():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = session.get('role')
    last_login = session.get('last_login')
    today_date = get_current_date()
    user_name = employees[user_id]['employee_name']
    profile_photo = employees[user_id].get('profile_photo', 'profiles/default.jpg')

    if role not in ['manager', 'director']:
        return "Access denied"

    if role == 'director':
        team_members_ids = employees.keys()
    else:
        team_members = str(employees[user_id].get('team_members', ''))
        team_members_ids = team_members.split(',') if team_members else []

    cl_sl_leave_df = load_cl_sl_leave_df()
    unpaid_early_wfh_leave_df = load_unpaid_early_wfh_leave_df()

    team_members_info = []
    for emp_id in team_members_ids:
        emp_id = emp_id.strip()
        if emp_id in employees:
            emp_info = employees[emp_id]
            emp_leave_data = cl_sl_leave_df[cl_sl_leave_df['Employee ID'] == emp_id]
            total_cl_balance = emp_leave_data['CL_Balance'].sum()
            total_sl_balance = emp_leave_data['SL_Balance'].sum()

            emp_leave_taken = unpaid_early_wfh_leave_df[unpaid_early_wfh_leave_df['Employee ID'] == emp_id]
            total_unpaid_leave_taken = emp_leave_taken['Unpaid_Leave_Taken'].sum()
            total_early_leave_taken = emp_leave_taken['Early_Leave_Taken'].sum()
            total_wfh_taken = emp_leave_taken['WFH_Taken'].sum()

            emp_info['casual_leave_balance'] = total_cl_balance
            emp_info['sick_leave_balance'] = total_sl_balance
            emp_info['unpaid_leave_taken'] = total_unpaid_leave_taken
            emp_info['early_leave_taken'] = total_early_leave_taken
            emp_info['wfh_taken'] = total_wfh_taken

            team_members_info.append(emp_info)

    return render_template('team_leave_balance.html', team_members=team_members_info, user_name=user_name, role=role, last_login=last_login, today_date=today_date, profile_photo=profile_photo)

@app.route('/team_leave_status', methods=['GET', 'POST'])
def team_leave_status():
    if 'user_id' not in session:
        return "Access denied"

    user_id = session['user_id']
    role = session.get('role')
    last_login = session.get('last_login')
    today_date = get_current_date()
    user_name = employees[user_id]['employee_name']
    profile_photo = employees[user_id].get('profile_photo', 'profiles/default.jpg')

    if role not in ['manager', 'director']:
        return "Access denied"

    filter_name = request.form.get('employee_name', '').lower() if request.method == 'POST' else ''
    
    if role == 'director':
        team_members_ids = employees.keys()
    else:
        team_members = str(employees[user_id].get('team_members', ''))
        team_members_ids = team_members.split(',') if team_members else []

    team_leaves = []
    data = load_data()
    for app_id, leave in data.items():
        if str(leave['employee_id']) in team_members_ids:
            if filter_name and filter_name not in leave['employee_name'].lower():
                continue
            start_date = leave.get('start_date')
            end_date = leave.get('end_date')
            if start_date and end_date:
                leave['number_of_days'] = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
            else:
                leave['number_of_days'] = 'N/A'
            leave['date_of_apply'] = leave.get('date_of_apply', 'N/A')
            team_leaves.append(leave)

    return render_template('team_leave_status.html', team_leaves=team_leaves, user_name=user_name, role=role, last_login=last_login, today_date=today_date, profile_photo=profile_photo)



@app.route('/status')
def status():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = session.get('role')
    last_login = session.get('last_login')
    today_date = get_current_date()
    user_name = employees[user_id]['employee_name']
    profile_photo = employees[user_id].get('profile_photo', 'profiles/default.jpg')

    logging.info(f"Function 'status' accessed by {user_name} (ID: {user_id}, Role: {role}) "
                 f"on {today_date}. Last login: {last_login}.")

    user_info = {
        'employee_name': user_name,
        'role': role,
        'profile_photo': profile_photo
    }

    data = load_data()
    
    # Filter leave applications for the current user and sort by apply date
    user_leaves = [
        (app_id, details) for app_id, details in data.items()
        if details['employee_id'] == user_id
    ]
    sorted_leaves = sorted(user_leaves, key=lambda x: parse_date(x[1]['date_of_apply']), reverse=True)
    
    # Get the IDs of the last two applied leaves
    last_two_leave_ids = [leave[0] for leave in sorted_leaves[:2]]
    
    # Pass last two leave IDs to the template along with all leave status
    leave_status = {k: v for k, v in data.items() if v['employee_id'] == user_id}

    # Apply month filter if requested
    month = request.args.get('month')
    if month:
        leave_status = {
            k: v for k, v in leave_status.items() 
            if datetime.strptime(v['date_of_apply'], '%Y-%m-%d').strftime('%m') == month
        }

    logging.info(f"Found {len(leave_status)} leave applications for {user_name} "
                 f"(ID: {user_id}) after applying filters.")

    return render_template(
        'status.html', 
        leave_status=leave_status, 
        last_two_leave_ids=last_two_leave_ids, 
        user_info=user_info, 
        last_login=last_login, 
        today_date=today_date, 
        profile_photo=profile_photo, 
        user_name=user_name
    )

@app.route('/approve/<application_id>')
def approve(application_id):
    approver_id = session.get('user_id')  
    approver_role = session.get('role')
    approver_name = employees.get(approver_id, {}).get('employee_name', 'Unknown')
    approval_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    logging.info(f"Approve route accessed by {approver_name} (ID: {approver_id}, Role: {approver_role}) "
                 f"for application_id {application_id} at {approval_time}.")
    

    data = load_data()
    if application_id in data:
        logging.info(f"Application found for {application_id}. Approving leave.")
        application = data[application_id]

        if data[application_id]['status'] in ['Approved', 'Denied']:
            logging.info(f"Leave application {application_id} for {employee_name} (ID: {employee_id}) "
                         f"is already {application['status']} by another approver.")
            return f"Leave already {application['status']}."
        elif data[application_id]['status'] in ['Revoked']:
                return "Leave revoked by user."

        leave_type = data[application_id]['leave_type']
        leave_mode = data[application_id]['leave_mode']
        employee_id = data[application_id]['employee_id']
        employee_name = data[application_id]['employee_name']

        try:
            start_date = parse_date(data[application_id]['start_date'])
            end_date = parse_date(data[application_id]['end_date'])
        except ValueError as e:
            return str(e), 400

        leave_days = (end_date - start_date).days + 1
        if leave_mode == 'Half Day':
            leave_days /= 2

        unpaid_early_wfh_leave_df = load_unpaid_early_wfh_leave_df()
        cl_sl_leave_df = load_cl_sl_leave_df()

        current_date = start_date
        while current_date <= end_date:
            leave_month = current_date.strftime('%Y-%m')
            days_in_month = pd.Period(leave_month).days_in_month
            month_start_date = current_date.replace(day=1)
            month_end_date = month_start_date + timedelta(days=days_in_month - 1)

            leave_days_in_month = min(leave_days, (month_end_date - current_date).days + 1)

            if leave_type == 'Unpaid Leave':
                unpaid_early_wfh_leave_df.loc[
                    (unpaid_early_wfh_leave_df['Employee ID'] == employee_id) & 
                    (unpaid_early_wfh_leave_df['Month'] == leave_month), 'Unpaid_Leave_Taken'] += leave_days_in_month
            elif leave_type == 'Early Leave':
                existing_early_leaves = unpaid_early_wfh_leave_df.loc[
                    (unpaid_early_wfh_leave_df['Employee ID'] == employee_id) & 
                    (unpaid_early_wfh_leave_df['Month'] == leave_month), 'Early_Leave_Taken'
                ].sum()
                if existing_early_leaves == 0:
                    unpaid_early_wfh_leave_df.loc[
                        (unpaid_early_wfh_leave_df['Employee ID'] == employee_id) & 
                        (unpaid_early_wfh_leave_df['Month'] == leave_month), 'Early_Leave_Taken'
                    ] += 1
                else:
                    return "Only one early leave is allowed per month."
            
            elif leave_type == 'Work from Home':
                unpaid_early_wfh_leave_df.loc[
                    (unpaid_early_wfh_leave_df['Employee ID'] == employee_id) & 
                    (unpaid_early_wfh_leave_df['Month'] == leave_month), 'WFH_Taken'] += leave_days_in_month
                
            elif leave_type == 'Compensatory pay':
                unpaid_early_wfh_leave_df.loc[
                    (unpaid_early_wfh_leave_df['Employee ID'] == employee_id) & 
                    (unpaid_early_wfh_leave_df['Month'] == leave_month), 'Comp_Pay_Taken'] += leave_days_in_month

            elif leave_type == 'Casual Leave':
                current_balance = cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == employee_id, 'CL_Balance'
                ].sum()
                new_balance = max(0, current_balance - leave_days)
                cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == employee_id, 'CL_Balance'
                ] = new_balance

            elif leave_type == 'Sick Leave':
                current_balance = cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == employee_id, 'SL_Balance'
                ].sum()
                new_balance = max(0, current_balance - leave_days)
                cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == employee_id, 'SL_Balance'
                ] = new_balance

            elif leave_type == 'Compensatory Off':
                current_balance = cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == employee_id, 'Comp_Off_Taken'
                ].sum()
                new_balance = max(0, current_balance - leave_days)
                cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == employee_id, 'Comp_Off_Taken'
                ] = new_balance

            elif leave_type == 'Birthday/Anniversary':
                current_balance = cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == employee_id, 'Birthday/Aniversary'
                ].sum()
                if current_balance == 0:
                    cl_sl_leave_df.loc[
                        cl_sl_leave_df['Employee ID'] == employee_id, 'Birthday/Aniversary'
                    ] += 1
                else:
                    return "Only 1 Birthday/Aniversary leave is allowed per month."

            leave_days -= leave_days_in_month
            current_date = month_end_date + timedelta(days=1)

        save_unpaid_early_wfh_leave_df(unpaid_early_wfh_leave_df)
        save_cl_sl_leave_df(cl_sl_leave_df)

        # Mark the leave application as approved
        data[application_id]['status'] = 'Approved'
        save_data(data)
        logging.info(f"Leave application {application_id} for {employee_name} approved by {approver_name} "
                         f"at {approval_time}.")

         # Extract email and leave details and send the approval email
        employee_email = employees[employee_id]['employee_email']
        leave_type = data[application_id]['leave_type']
        leave_mode = data[application_id]['leave_mode']
        start_date = data[application_id]['start_date']
        end_date = data[application_id]['end_date']

        # Send approval email
        send_approval_email(employee_email, employee_name, leave_type, leave_mode, start_date, end_date)

        hr_email = 'people@6wresearch.com'
        employee_name = data[application_id]['employee_name']
        leave_type = data[application_id]['leave_type']
        leave_mode = data[application_id]['leave_mode']
        start_date = data[application_id]['start_date']
        end_date = data[application_id]['end_date']

        # Send styled email to HR
        send_hr_approval_notification_email(hr_email, employee_name, leave_type, leave_mode, start_date, end_date)



        # Additional code to notify HR, etc., if needed
        return "Leave approved successfully."


@app.route('/deny/<application_id>')
def deny(application_id):

    logging.info(f"Deny route accessed for application_id {application_id}.")

    approver_id = session.get('user_id')
    approver_role = session.get('role')
    approver_name = employees.get(approver_id, {}).get('employee_name', 'Unknown')
    denial_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    logging.info(f"Deny route accessed by {approver_name} (ID: {approver_id}, Role: {approver_role}) "
                 f"for application_id {application_id} at {denial_time}.")

    data = load_data()
    if application_id in data:
        if data[application_id]['status'] == 'Denied':
            return "Leave already denied."
        
        # Mark the leave application as denied
        data[application_id]['status'] = 'Denied'
        save_data(data)
        logging.info(f"Leave application {application_id} for {employee_name} (ID: {employee_id}) "
                     f"was denied by {approver_name} at {denial_time}.")
        
        # Extract necessary information for email
        employee_id = data[application_id]['employee_id']
        employee_email = employees[employee_id]['employee_email']
        employee_name = employees[employee_id]['employee_name']
        leave_type = data[application_id]['leave_type']
        leave_mode = data[application_id]['leave_mode']
        start_date = data[application_id]['start_date']
        end_date = data[application_id]['end_date']
        
        # Send styled denial email to the employee
        send_denial_email(employee_email, employee_name, leave_type, leave_mode, start_date, end_date)

        hr_email = 'people@6wresearch.com'
        employee_name = data[application_id]['employee_name']
        leave_type = data[application_id]['leave_type']
        leave_mode = data[application_id]['leave_mode']
        start_date = data[application_id]['start_date']
        end_date = data[application_id]['end_date']

        # Send styled email to HR
        send_hr_denial_notification_email(hr_email, employee_name, leave_type, leave_mode, start_date, end_date)
        logging.info(f"Denial email sent for application_id {application_id}.")

    return "Leave denied successfully."


@app.route('/holidays')
def holidays():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = session.get('role')
    last_login = session.get('last_login')
    today_date = datetime.now().strftime("%Y-%m-%d")
    current_year = datetime.now().year
    user_name = employees[user_id]['employee_name']
    profile_photo = employees[user_id].get('profile_photo', 'profiles/default.jpg')
    user_info = {
        'employee_name': user_name,
        'role': role,
        'profile_photo': profile_photo
    }

    try:
        filename = 'national_leave.csv'
        holidays_df = pd.read_csv(filename, header=0)
        holidays_df['DATE'] = pd.to_datetime(holidays_df['DATE'], format='%d-%m-%Y')
        holidays_df['DAY'] = holidays_df['DATE'].dt.day_name()


        holidays = holidays_df.to_dict('records')
    except Exception as e:
        print(f"Error processing holidays: {e}")
        holidays = []

    return render_template('holidays.html', holidays=holidays, user_name=user_name, role=role, last_login=last_login, today_date=today_date, profile_photo=profile_photo, current_year=current_year, user_info=user_info)


def parse_date(date_str):
    for fmt in ('%Y-%m-%d', '%Y-%d-%m', '%d-%m-%Y', '%m-%d-%Y'):
        try:
            return pd.to_datetime(date_str, format=fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")

@app.route('/probation_employees')
def probation_employees():
    if 'user_id' not in session or session.get('role') not in ['hr', 'director']:
        return "Access denied", 403
    
    user_id = session['user_id']
    profile_photo = employees[user_id].get('profile_photo', 'profiles/default.jpg')
    
    employees_df = load_employees_df()
    probation_employees = employees_df[employees_df['role'].isin(['probation', 'Not Confirmed'])].copy()

    if not probation_employees.empty:
        # Convert 'doj', 'first_probation', and 'second_probation' to datetime, handling errors by setting NaT values
        probation_employees['doj'] = pd.to_datetime(probation_employees['doj'], errors='coerce')
        probation_employees['first_probation'] = pd.to_datetime(probation_employees['first_probation'], errors='coerce')
        probation_employees['second_probation'] = pd.to_datetime(probation_employees['second_probation'], errors='coerce')

        # Calculate days left for probation, handling NaT by filling with a default value or setting to 0
        probation_employees['days_left_first'] = (probation_employees['first_probation'] - datetime.now()).dt.days.fillna(0).astype(int)
        probation_employees['days_left_second'] = (probation_employees['second_probation'] - datetime.now()).dt.days.fillna(0).astype(int)

        # Convert dates to strings where possible, otherwise set to None for missing dates
        probation_employees['doj'] = probation_employees['doj'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) else None)
        probation_employees['first_probation'] = probation_employees['first_probation'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) else None)
        probation_employees['second_probation'] = probation_employees['second_probation'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notnull(x) else None)

        # Filter into probation categories
        first_probation_employees = probation_employees[probation_employees['role'] == 'probation']
        second_probation_employees = probation_employees[probation_employees['role'] == 'Not Confirmed']

        # Convert to records for passing to template
        first_probation_employees = first_probation_employees.to_dict(orient='records')
        second_probation_employees = second_probation_employees.to_dict(orient='records')
    else:
        first_probation_employees = []
        second_probation_employees = []

    return render_template('probation_employees.html', 
                           first_probation_employees=first_probation_employees,
                           second_probation_employees=second_probation_employees,
                           profile_photo=profile_photo)





@app.route('/end_first_probation_call/<employee_id>', methods=['POST'])
def end_first_probation_call(employee_id):
    employees_df = load_employees_df()
    cl_sl_leave_df = load_cl_sl_leave_df()
    
    try:
        if not employees_df[employees_df['Employee ID'] == employee_id].empty:
            if employees_df.loc[employees_df['Employee ID'] == employee_id, 'role'].values[0] == 'probation':
                employees_df.loc[employees_df['Employee ID'] == employee_id, 'role'] = 'Not Confirmed'
                
                # Calculate and update CL and SL leaves
                today_date = datetime.now().day
                current_month = datetime.now().month
                
                if today_date > 15:
                    new_cl_leaves = 15 - ((15 / 12) * current_month) + 1
                    new_sl_leaves = 6 - ((6 / 12) * current_month) 
                else:
                    new_cl_leaves = 15 - ((15 / 12) * current_month) + 1.25
                    new_sl_leaves = 6 - ((6 / 12) * current_month)+0.5
                
                cl_sl_leave_df.loc[cl_sl_leave_df['Employee ID'] == employee_id, 'CL_Balance'] += new_cl_leaves
                cl_sl_leave_df.loc[cl_sl_leave_df['Employee ID'] == employee_id, 'SL_Balance'] += new_sl_leaves

                save_employees_df(employees_df)
                save_cl_sl_leave_df(cl_sl_leave_df)
                
                socketio.emit('update', {'action': 'end_first_probation', 'employee_id': employee_id})
                
                return jsonify({'message': 'First probation call ended, role updated to Not Confirmed, and leaves updated.'}), 200
            else:
                return jsonify({'error': 'Employee is not currently on probation.'}), 400
        else:
            return jsonify({'error': 'Employee does not exist.'}), 400
    except Exception as e:
        return jsonify({'error': f'Error ending first probation call: {str(e)}'}), 500

@app.route('/end_second_probation_call/<employee_id>', methods=['POST'])
def end_second_probation_call(employee_id):
    employees_df = load_employees_df()
    try:
        if not employees_df[employees_df['Employee ID'] == employee_id].empty:
            if employees_df.loc[employees_df['Employee ID'] == employee_id, 'role'].values[0] == 'Not Confirmed':
                employees_df.loc[employees_df['Employee ID'] == employee_id, 'role'] = 'employee'
                save_employees_df(employees_df)
                socketio.emit('update', {'action': 'end_second_probation', 'employee_id': employee_id})
                return jsonify({'message': 'Second probation call ended and role updated to employee.'}), 200
            else:
                return jsonify({'error': 'Employee is not currently Not Confirmed.'}), 400
        else:
            return jsonify({'error': 'Employee does not exist.'}), 400
    except Exception as e:
        return jsonify({'error': f'Error ending second probation call: {str(e)}'}), 500




@app.route('/apply_reimbursement', methods=['GET', 'POST'])
def apply_reimbursement():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_info = employees[user_id]
    role = user_info['role']
    last_login = session.get('last_login')
    today_date = get_current_date()
    user_name = user_info['employee_name']
    profile_photo = employees[user_id].get('profile_photo', 'profiles/default.jpg')

    if request.method == 'POST':
        try:
            reimbursement_type = request.form.get('reimbursement_type')
            reason = request.form.get('reason')
            num_days = None
            proof_filename = None
            amount = None
            proof_path = None

            print(f"Processing reimbursement type: {reimbursement_type}")  # Debug log

            # Handle compensatory off
            if reimbursement_type == 'Add Compensatory Off':
                num_days = request.form.get('num_days')
            else:
                # Handle incentive and reimbursement types
                amount = request.form.get('amount')
                proof = request.files.get('proof')
                
                if proof and proof.filename != '':
                    proof_filename = secure_filename(proof.filename)
                    proof_path = os.path.join('static', 'proofs', proof_filename)
                    proof.save(proof_path)
                    print(f"File saved for {reimbursement_type}: {proof_filename}")  # Debug log
                else:
                    print(f"No proof file uploaded for {reimbursement_type}")  # Debug log

            # Load existing reimbursement data and generate a new reimbursement ID
            reimbursement_data = load_reimbursement_data()
            user_name_slug = user_info['employee_name'].replace(' ', '_')
            next_reimbursement_number = len([k for k in reimbursement_data.keys() if k.startswith(user_name_slug)]) + 1
            reimbursement_id = f"{user_name_slug}_reimbursement_{next_reimbursement_number}"

            # Save the reimbursement data
            reimbursement_data[reimbursement_id] = {
                'employee_id': user_id,
                'employee_name': user_info['employee_name'],
                'reimbursement_type': reimbursement_type,
                'reason': reason,
                'amount': amount,
                'proof': proof_filename,
                'num_days': num_days if reimbursement_type == 'Add Compensatory Off' else None,
                'status': 'Pending',
                'date_of_apply': today_date
            }
            save_reimbursement_data(reimbursement_data)

            # Prepare email approval and denial links
            approve_link = f"https://hr.6wconsult.com/login/approve_reimbursement/{reimbursement_id}"
            deny_link = f"https://hr.6wconsult.com/login/deny_reimbursement/{reimbursement_id}"

            # Subject and body of the email
            proof_url = f"https://hr.6wconsult.com/login/static/proofs/{proof_filename}" if proof_filename else 'N/A'
            subject = f"Reimbursement Application from {user_info['employee_name']}"
            body = render_template(
                'reimbursement_mail.html',
                employee_name=user_info['employee_name'],
                reimbursement_type=reimbursement_type,
                reason=reason,
                amount=amount,
                num_days=num_days,
                proof_url=proof_url,
                proof_filename=proof_filename,
                approve_link=approve_link,
                deny_link=deny_link
            )



            print(f"Sending email for {reimbursement_type}...")  # Debug log

            # Send email without attachment, just with a link to the proof
            send_email(subject, user_info['manager_email'], body)

            flash('Reimbursement application submitted successfully.', 'success')

        except Exception as e:
            flash(f'Error applying for reimbursement: {str(e)}', 'danger')
            print(f"Error: {str(e)}")  # Log the error for debugging

        return redirect(url_for('apply_reimbursement'))

    # Load previous reimbursements for the user
    reimbursements = [r for r in load_reimbursement_data().values() if r['employee_id'] == user_id]
    total_incentives_amount = sum(float(r['amount']) for r in reimbursements if r['reimbursement_type'] == 'Incentive' and r['status'] == 'Approved')
    total_reimbursements_amount = sum(float(r['amount']) for r in reimbursements if r['reimbursement_type'] == 'Reimbursement' and r['status'] == 'Approved')

    return render_template('reimbursement.html', user_name=user_name, last_login=last_login, 
                           today_date=today_date, profile_photo=profile_photo, role=role, reimbursements=reimbursements,
                           total_incentives_amount=total_incentives_amount, total_reimbursements_amount=total_reimbursements_amount)







def send_email_with_attachment(subject, recipient, body, attachment):
    try:
        email_data = {
            'to': recipient,
            'subject_line': subject,
            'msg': body,
            'from': 'noreply@6wconsult.com'
        }

        # Get the filename and determine its MIME type
        filename = os.path.basename(attachment)
        mime_type, _ = mimetypes.guess_type(attachment)
        mime_type = mime_type or 'application/octet-stream'  # Fallback if MIME type cannot be guessed

        with open(attachment, 'rb') as attachment_file:
            files = {
                'attachment': (
                    filename,  # Use the actual filename
                    attachment_file,
                    mime_type,
                    {'Content-Disposition': f'attachment; filename="{filename}"'}
                )
            }

            # Send the request to the API using multipart/form-data
            response = requests.post('http://6wconsult.com/api-mail-send', data=email_data, files=files)

        if response.status_code == 200:
            print(f"Email sent successfully to {recipient}")
            return True
        else:
            print(f"Failed to send email. Status code: {response.status_code}")
            print(f"Response content: {response.content.decode()}")
            return False
    except FileNotFoundError:
        print(f"Attachment file not found: {attachment}")
        return False
    except Exception as e:
        print(f"Error sending email with attachment: {e}")
        return False






    
@app.route('/approve_reimbursement/<reimbursement_id>')
def approve_reimbursement(reimbursement_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    reimbursement_data = load_reimbursement_data()
    
    if reimbursement_id in reimbursement_data:
        if reimbursement_data[reimbursement_id]['status'] == 'Approved':
            return "Reimbursement already approved."

        # Update reimbursement status to Approved
        reimbursement_data[reimbursement_id]['status'] = 'Approved'
        save_reimbursement_data(reimbursement_data)

        # Extract employee and reimbursement details
        employee_id = reimbursement_data[reimbursement_id]['employee_id']
        employee_name = employees[employee_id]['employee_name']
        employee_email = employees[employee_id]['employee_email']
        reimbursement_type = reimbursement_data[reimbursement_id]['reimbursement_type']
        amount = float(reimbursement_data[reimbursement_id].get('amount', 0))
        reason = reimbursement_data[reimbursement_id].get('reason', '')
        current_month = datetime.now().strftime('%Y-%m')
        
        # HR email
        hr_email = 'people@6wresearch.com'

        # Handle "Add Compensatory Off" reimbursement
        if reimbursement_type == 'Add Compensatory Off':
            num_days = int(reimbursement_data[reimbursement_id].get('num_days', 0))
            cl_sl_leave_df = load_cl_sl_leave_df()
            cl_sl_leave_df.loc[
                cl_sl_leave_df['Employee ID'] == employee_id, 'Comp_Off_Taken'] += num_days
            save_cl_sl_leave_df(cl_sl_leave_df)

            # Send approval email to the employee with HTML template
            send_reimbursement_approval_email(employee_email, employee_name, reimbursement_type, num_days, reason)

            # Notify HR with compensatory off details
            hr_subject = f"Compensatory Off Approved for {employee_name}"
            hr_body = f"Compensatory off for {employee_name} has been approved for {num_days} days."
            send_email(hr_subject, hr_email, hr_body)

        # Handle "Reimbursement" type
        elif reimbursement_type == 'Reimbursement':
            # Update reimbursement in the records
            unpaid_early_wfh_leave_df = load_unpaid_early_wfh_leave_df()
            row_index = unpaid_early_wfh_leave_df[
                (unpaid_early_wfh_leave_df['Employee ID'] == employee_id) & 
                (unpaid_early_wfh_leave_df['Month'] == current_month)
            ].index

            if not row_index.empty:
                unpaid_early_wfh_leave_df.at[row_index[0], 'reimbursements'] += amount
                save_unpaid_early_wfh_leave_df(unpaid_early_wfh_leave_df)

            # Send approval email to the employee with HTML template
            send_reimbursement_approval_email(employee_email, employee_name, reimbursement_type, amount, reason)

            # Notify HR with reimbursement details
            hr_subject = f"Reimbursement Approved for {employee_name}"
            hr_body = f"Reimbursement for {employee_name} has been approved for the amount of {amount}."
            send_email(hr_subject, hr_email, hr_body)

        # Handle "Incentive" type
        elif reimbursement_type == 'Incentive':
            # Update incentive in the records
            unpaid_early_wfh_leave_df = load_unpaid_early_wfh_leave_df()
            row_index = unpaid_early_wfh_leave_df[
                (unpaid_early_wfh_leave_df['Employee ID'] == employee_id) & 
                (unpaid_early_wfh_leave_df['Month'] == current_month)
            ].index

            if not row_index.empty:
                unpaid_early_wfh_leave_df.at[row_index[0], 'incentives'] += amount
                save_unpaid_early_wfh_leave_df(unpaid_early_wfh_leave_df)

            # Send approval email to the employee with HTML template
            send_reimbursement_approval_email(employee_email, employee_name, reimbursement_type, amount, reason)

            # Notify HR with incentive details
            hr_subject = f"Incentive Approved for {employee_name}"
            hr_body = f"Incentive for {employee_name} has been approved for the amount of {amount}."
            send_email(hr_subject, hr_email, hr_body)

        return "Reimbursement/Incentive approved successfully."
    else:
        return "Reimbursement not found."



@app.route('/deny_reimbursement/<reimbursement_id>')
def deny_reimbursement(reimbursement_id):
    reimbursement_data = load_reimbursement_data()
    if reimbursement_id in reimbursement_data:
        if reimbursement_data[reimbursement_id]['status'] == 'Denied':
            return "Reimbursement already denied."

        # Update reimbursement status to Denied
        reimbursement_data[reimbursement_id]['status'] = 'Denied'
        save_reimbursement_data(reimbursement_data)

        # Extract employee and reimbursement details
        employee_id = reimbursement_data[reimbursement_id]['employee_id']
        employee_email = employees[employee_id]['employee_email']
        employee_name = employees[employee_id]['employee_name']
        reimbursement_type = reimbursement_data[reimbursement_id]['reimbursement_type']
        amount = float(reimbursement_data[reimbursement_id].get('amount', 0))
        reason = reimbursement_data[reimbursement_id].get('reason', '')

        # Send denial email with HTML template
        send_reimbursement_denial_email(employee_email, employee_name, reimbursement_type, amount, reason)

        return "Reimbursement denied successfully."
    else:
        return "Reimbursement not found."

    
@app.route('/update_csv', methods=['POST'])
@role_required('hr', 'director')
def update_csv():
    # Read the CSV file into a DataFrame
    csv_df = load_unpaid_early_wfh_leave_df()

    # Map months to CSV filenames
    month_to_csv = {
        '2024-01': 'January.csv',
        '2024-02': 'February.csv',
        '2024-03': 'March.csv',
        '2024-04': 'April.csv',
        '2024-05': 'May.csv',
        '2024-06': 'June.csv',
        '2024-07': 'July.csv',
        '2024-08': 'August.csv',
        '2024-09': 'September.csv',
        '2024-10': 'October.csv',
        '2024-11': 'November.csv',
        '2024-12': 'December.csv'
    }

    # Path to the directory containing monthly CSV files
    csv_directory = r"/home/v3wihx1dfu5s/leave-app/monthly_csv"

    # Iterate through each month and update the corresponding CSV file
    for index, row in csv_df.iterrows():
        month = row['Month'].upper()
        csv_filename = month_to_csv.get(month)

        if csv_filename:
            csv_file_path = os.path.join(csv_directory, csv_filename)

            # Load the CSV file from the local directory
            monthly_df = pd.read_csv(csv_file_path)

            employee_id = row['Employee ID']
            unpaid_leave = row['Unpaid_Leave_Taken']
            reimbursement = row['reimbursements']
            incentive = row['incentives']
            comp_pay_taken = row['Comp_Pay_Taken']

            # Extract month and year from the "YYYY-MM" format
            month_number = int(month.split('-')[1])
            current_year = int(month.split('-')[0])
            total_days = pd.Period(year=current_year, month=month_number, freq='M').days_in_month

            for i, monthly_row in monthly_df.iterrows():
                if monthly_row['Employee ID'] == employee_id:
                    total_salary = monthly_row['salary']
                    if total_salary > 0:
                        deductions = int(round((total_salary / total_days) * unpaid_leave))
                        base_salary = (total_salary * 50) / 100
                        hra = (total_salary * 40) / 100
                        conveyance = (total_salary * 10) / 100
                        total_earnings = incentive + reimbursement + total_salary
                        net_pay = int(round((total_earnings + ((total_salary / total_days) * comp_pay_taken)) - deductions - 1800))
                        amount = net_pay + 1800
                        total_paid_days = total_days - unpaid_leave
                        in_words = num2words(net_pay) + ' only.'
                        total_deductions = 1800 + deductions
                    else:
                        deductions = base_salary = total_deductions = hra = conveyance = total_earnings = amount = net_pay = 0
                        total_paid_days = total_days
                        in_words = 'zero only.'

                    # Update the row with the new values
                    monthly_df.at[i, 'Unpaid_Leave_Taken'] = unpaid_leave
                    monthly_df.at[i, 'reimbursements'] = reimbursement
                    monthly_df.at[i, 'incentives'] = incentive
                    monthly_df.at[i, 'compensatory pay'] = comp_pay_taken
                    monthly_df.at[i, 'deductions'] = deductions
                    monthly_df.at[i, 'basic salary'] = base_salary
                    monthly_df.at[i, 'hra'] = hra
                    monthly_df.at[i, 'conveyance'] = conveyance
                    monthly_df.at[i, 'total earnings'] = total_earnings
                    monthly_df.at[i, 'net pay'] = net_pay
                    monthly_df.at[i, 'amount'] = amount
                    monthly_df.at[i, 'total_days_month'] = total_days
                    monthly_df.at[i, 'total_paid_days'] = total_paid_days
                    monthly_df.at[i, 'in words'] = in_words
                    monthly_df.at[i, 'total deductions'] = total_deductions
                    break

            # Write the updated DataFrame back to the file
            monthly_df.to_csv(csv_file_path, index=False)  # Overwrite the file directly

    # Save the update date to a file locally
    update_date = datetime.now().strftime('%Y-%m')
    last_update_date_path = "last_update_date.json"
    last_update_content = json.dumps({"last_update_date": update_date})
    with open(last_update_date_path, 'w') as f:
        f.write(last_update_content)

    return jsonify({"message": "CSV files updated successfully"}), 200




def fill_salary_slip(template_name, output_path_pdf, employee_info):
    # Render the HTML template with employee data
    rendered_html = render_template(template_name, **employee_info)

    # Convert HTML to PDF
    with open(output_path_pdf, "w+b") as result_file:
        pisa_status = pisa.CreatePDF(rendered_html, dest=result_file)
    
    if pisa_status.err:
        raise Exception("Error creating PDF")


@app.route('/salary_slips', methods=['GET', 'POST'])
def salary_slips():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = session.get('role')
    last_login = session.get('last_login')

    today_date = get_current_date()
    user_name = employees[user_id]['employee_name']
    profile_photo = employees[user_id].get('profile_photo', 'profiles/default.jpg')

    current_date = datetime.now()
    month_name_mapping = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }

    # Load the last update date
    try:
        with open('last_update_date.json', 'r') as f:
            last_update_date = json.load(f)["last_update_date"]
    except FileNotFoundError:
        last_update_date = current_date.strftime('%Y-%m')

    last_update_date_obj = datetime.strptime(last_update_date, '%Y-%m')

    last_month_date = last_update_date_obj.replace(day=1) - relativedelta(months=1)
    last_to_last_month_date = last_update_date_obj.replace(day=1) - relativedelta(months=2)
    month_before_last_to_last_month_date = last_update_date_obj.replace(day=1) - relativedelta(months=3)

    months_to_fetch = [
        month_name_mapping[last_month_date.month],
        month_name_mapping[last_to_last_month_date.month],
        month_name_mapping[month_before_last_to_last_month_date.month]
    ]

    # Directory where CSV files are stored
    csv_directory = r"/home/v3wihx1dfu5s/leave-app/monthly_csv"

    employee_salary_data = []

    # Load salary and employee data from CSV files
    for month in months_to_fetch:
        csv_filename = f"{month}.csv"
        csv_file_path = os.path.join(csv_directory, csv_filename)
        if os.path.exists(csv_file_path):
            data = pd.read_csv(csv_file_path)
            data['Employee ID'] = data['Employee ID'].astype(str)
            emp_data = data[data['Employee ID'] == user_id]
            if not emp_data.empty:
                for _, row in emp_data.iterrows():
                    employee_salary_data.append({
                        'Month': month.upper(),
                        'Employee': row['employee_name'],
                        'DOJ': employees_df.loc[employees_df['Employee ID'] == user_id, 'doj'].values[0],
                        'Designation': employees_df.loc[employees_df['Employee ID'] == user_id, 'designation'].values[0],
                        'Employee_ID': row['Employee ID'],
                        'Department': employees_df.loc[employees_df['Employee ID'] == user_id, 'department'].values[0],
                        'UAN': row['uan'],
                        'Basic_Salary': row['basic salary'],
                        'HRA': row['hra'],
                        'Conveyance': row['conveyance'],
                        'Total_Earnings': row['total earnings'],
                        'Compensatory_Pay': row['compensatory pay'],
                        'Reimbursements': row['reimbursements'],
                        'Incentives': row['incentives'],
                        'Net_Pay': row['net pay'],
                        'Total_Deductions': row['deductions'],
                        'Amount': row['amount'],
                        'Salary': row['salary'],
                        'Leave_Without_Pay': row['Unpaid_Leave_Taken'],
                        'Total_Days': row['total_days_month'],
                        'Total_Paid_Days': row['total_paid_days'],
                        'In_Words': row['in words']
                    })

    for slip in employee_salary_data:
        month_year = slip['Month']
        output_path_pdf = os.path.join(output_dir, f'Salary_Slip_{user_id}_{month_year}.pdf')
        fill_salary_slip(html_template_path, output_path_pdf, slip)

    return render_template('salary_slip/salary_slip.html', salary_slips=employee_salary_data, user_name=user_name, role=role, last_login=last_login, today_date=today_date, profile_photo=profile_photo)



@app.route('/download_salary_slip/<month_year>')
def download_salary_slip(month_year):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    output_path_pdf = os.path.join(output_dir, f'Salary_Slip_{user_id}_{month_year}.pdf')

    if os.path.exists(output_path_pdf):
        return send_file(output_path_pdf, as_attachment=True)
    else:
        return "Salary slip not found", 404

@app.route('/view_salary_slip/<month_year>')
def view_salary_slip(month_year):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    slip_data = None

    # Normalize the month_year to capitalize the first letter (e.g., 'AUGUST' -> 'August')
    normalized_month_year = month_year.capitalize()

    # Directory where CSV files are stored
    csv_directory = r"/home/v3wihx1dfu5s/leave-app/monthly_csv"
    csv_file_path = os.path.join(csv_directory, f"{normalized_month_year}.csv")

    if os.path.exists(csv_file_path):
        data = pd.read_csv(csv_file_path)
        data['Employee ID'] = data['Employee ID'].astype(str)
        emp_data = data[data['Employee ID'] == user_id]

        if not emp_data.empty:
            slip_data = {
                'Month': normalized_month_year.upper(),
                'Employee': emp_data.iloc[0]['employee_name'],
                'DOJ': employees_df.loc[employees_df['Employee ID'] == user_id, 'doj'].values[0],
                'Designation': employees_df.loc[employees_df['Employee ID'] == user_id, 'designation'].values[0],
                'Employee_ID': emp_data.iloc[0]['Employee ID'],
                'Department': employees_df.loc[employees_df['Employee ID'] == user_id, 'department'].values[0],
                'UAN': emp_data.iloc[0]['uan'],
                'Basic_Salary': emp_data.iloc[0]['basic salary'],
                'HRA': emp_data.iloc[0]['hra'],
                'Conveyance': emp_data.iloc[0]['conveyance'],
                'Total_Earnings': emp_data.iloc[0]['total earnings'],
                'Compensatory_Pay': emp_data.iloc[0]['compensatory pay'],
                'Reimbursements': emp_data.iloc[0]['reimbursements'],
                'Incentives': emp_data.iloc[0]['incentives'],
                'Net_Pay': emp_data.iloc[0]['net pay'],
                'Total_Deductions': emp_data.iloc[0]['deductions'],
                'Amount': emp_data.iloc[0]['amount'],
                'Leave_Without_Pay': emp_data.iloc[0]['Unpaid_Leave_Taken'],
                'Total_Days': emp_data.iloc[0]['total_days_month'],
                'Total_Paid_Days': emp_data.iloc[0]['total_paid_days'],
                'In_Words': emp_data.iloc[0]['in words']
            }

    if slip_data:
        return render_template('salary_template.html', **slip_data)
    else:
        return "Salary slip not found", 404




@app.route('/revoke_leave/<application_id>', methods=['GET', 'POST'])
def revoke_leave(application_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST' or request.method == 'GET':
        user_id = session['user_id']
        data = load_data()

        if application_id not in data or data[application_id]['employee_id'] != user_id:
            return "Leave application not found or access denied.", 403

        leave_application = data[application_id]

        # Ensure leave is either Approved or Pending to be revoked
        if leave_application['status'] not in ['Approved', 'Pending']:
            return "Leave cannot be revoked.", 400

        # Only update leave balances if the status is "Approved"
        if leave_application['status'] == 'Approved':
            leave_type = leave_application['leave_type']
            leave_mode = leave_application['leave_mode']
            start_date = parse_date(leave_application['start_date'])
            end_date = parse_date(leave_application['end_date'])
            leave_days = (end_date - start_date).days + 1

            # Handle Half Day logic
            if leave_mode == 'Half Day':
                leave_days = leave_days / 2

            unpaid_early_wfh_leave_df = load_unpaid_early_wfh_leave_df()
            cl_sl_leave_df = load_cl_sl_leave_df()

            # Update balances for the specific leave type if approved
            if leave_type == 'Casual Leave':
                cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == user_id, 'CL_Balance'
                ] += leave_days

            elif leave_type == 'Sick Leave':
                cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == user_id, 'SL_Balance'
                ] += leave_days

            elif leave_type == 'Compensatory Off':
                cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == user_id, 'Comp_Off_Taken'
                ] += leave_days

            elif leave_type == 'Unpaid Leave':
                unpaid_early_wfh_leave_df.loc[
                    (unpaid_early_wfh_leave_df['Employee ID'] == user_id) & 
                    (unpaid_early_wfh_leave_df['Month'] == start_date.strftime('%Y-%m')),
                    'Unpaid_Leave_Taken'
                ] -= leave_days

            elif leave_type == 'Work from Home':
                unpaid_early_wfh_leave_df.loc[
                    (unpaid_early_wfh_leave_df['Employee ID'] == user_id) & 
                    (unpaid_early_wfh_leave_df['Month'] == start_date.strftime('%Y-%m')),
                    'WFH_Taken'
                ] -= leave_days

            elif leave_type == 'Early Leave':
                unpaid_early_wfh_leave_df.loc[
                    (unpaid_early_wfh_leave_df['Employee ID'] == user_id) & 
                    (unpaid_early_wfh_leave_df['Month'] == start_date.strftime('%Y-%m')),
                    'Early_Leave_Taken'
                ] -= 1

            elif leave_type == 'Compensatory Pay':
                unpaid_early_wfh_leave_df.loc[
                    (unpaid_early_wfh_leave_df['Employee ID'] == user_id) & 
                    (unpaid_early_wfh_leave_df['Month'] == start_date.strftime('%Y-%m')),
                    'Comp_Pay_Taken'
                ] -= leave_days

            elif leave_type == 'Birthday/Anniversary':
                cl_sl_leave_df.loc[
                    cl_sl_leave_df['Employee ID'] == user_id, 'Birthday/Anniversary'
                ] -= 1

            # Save updated leave data
            save_unpaid_early_wfh_leave_df(unpaid_early_wfh_leave_df)
            save_cl_sl_leave_df(cl_sl_leave_df)

        # Mark the leave application as revoked
        data[application_id]['status'] = 'Revoked'
        save_data(data)

        # Notify via socket
        socketio.emit('update', {'action': 'revoke', 'application_id': application_id})

        # Send email to HR or manager
        manager_email = employees[data[application_id]['employee_id']]['manager_email']
        hr_email = "people@6wresearch.com"
        subject = "Leave Revocation Notification"
        body = f"{leave_application['employee_name']} has revoked their leave from {leave_application['start_date']} to {leave_application['end_date']}."
        send_email(subject, manager_email, body)
        send_email(subject, hr_email, body)
        
        flash('Leave revoked successfully.', 'success')
        return redirect(url_for('status'))

    # GET request to confirm revocation
    return render_template('status.html', application_id=application_id)




if __name__ == '__main__':
    socketio.run(app, debug=True)
