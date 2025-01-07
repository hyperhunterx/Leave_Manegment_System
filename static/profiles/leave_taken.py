import json
import pandas as pd
from datetime import datetime

# Load leave balances from JSON file
def load_leave_balances():
    with open('leave_balances.json', 'r') as file:
        leave_balances = json.load(file)
    return leave_balances

# Update leave balances for previous months
def update_leave_balances_for_previous_months(leave_balances):
    today = datetime.now()
    current_year = today.year

    for emp_id, balance in leave_balances.items():
        # Reset the leave balances for this function to recalculate from the start
        balance['casual_leave_balance'] = 0
        balance['sick_leave_balance'] = 0
        balance['monthly_data'] = {}

        # Calculate leave for each month from January to the current month
        for month in range(1, today.month + 1):
            month_str = f"{current_year}-{month:02d}"
            
            balance['casual_leave_balance'] += 1.75
            balance['sick_leave_balance'] += 0.5
            
            # Cap the annual leave balances
            if balance['casual_leave_balance'] > 21:
                balance['casual_leave_balance'] = 21
            if balance['sick_leave_balance'] > 6:
                balance['sick_leave_balance'] = 6

            if month_str not in balance['monthly_data']:
                balance['monthly_data'][month_str] = {
                    'casual_leave_balance': balance['casual_leave_balance'],
                    'sick_leave_balance': balance['sick_leave_balance'],
                    'unpaid_leaves_taken': 0,
                    'wfh_taken': 0,
                    'early_leave': 0
                }
        
        # Update the last_updated field to the current date
        balance['last_updated'] = today.strftime('%Y-%m-%d')

    return leave_balances

# Save the leave balances to a CSV file
def save_leave_balances_to_csv(leave_balances):
    rows = []
    for emp_id, balance in leave_balances.items():
        for month, data in balance['monthly_data'].items():
            row = {
                'Employee ID': emp_id,
                'Month': month,
                'Casual Leave Balance': data['casual_leave_balance'],
                'Sick Leave Balance': data['sick_leave_balance'],
                'Unpaid Leaves Taken': data['unpaid_leaves_taken'],
                'Work from Home Taken': data['wfh_taken'],
                'Early Leave': data['early_leave']
            }
            rows.append(row)
    
    df = pd.DataFrame(rows)
    df.to_csv('employee_leave_balances.csv', index=False)

# Main function to execute the update and save process
def main():
    leave_balances = load_leave_balances()
    updated_leave_balances = update_leave_balances_for_previous_months(leave_balances)
    save_leave_balances_to_csv(updated_leave_balances)
    print("Leave balances have been updated and saved to employee_leave_balances.csv")

if __name__ == "__main__":
    main()
