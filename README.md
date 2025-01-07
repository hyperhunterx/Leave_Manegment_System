### Functional Details: Leave Management and Payroll System

**Project Overview**  
During my internship at 6Wresearch, I developed a Leave Management and Payroll System to automate leave requests, approvals, and payroll processes. The application was built using Python and Flask, with leave and payroll data stored in JSON files. After completing and testing the system locally, it was successfully deployed on **cPanel** and is currently being used by the company.

**Key Functionalities**  

1. **Leave Management Features**:  
   - **Employee Leave Application**:  
     Employees can apply for leave by selecting leave types (e.g., Casual, Sick, Annual) and providing relevant details such as duration and reason. The requests are stored and managed in JSON files.  
   - **Manager Approval Workflow**:  
     Leave requests are routed for approval or rejection by the manager. The system dynamically updates the JSON database to reflect the status of each request.  
   - **Leave Balance Tracking**:  
     Real-time tracking of leave balances, automatically updated upon approval or cancellation.  
   - **Leave Calendar Integration**:  
     A shared calendar view displays leave data fetched from JSON files, enabling better team coordination.  
   - **Notifications and Alerts**:  
     Automated email notifications are sent for submission, approval, and rejection of leave requests.

2. **Payroll Features**:  
   - **Employee Payslip Access**:  
     Employees can securely access and download their payslips for the last three months. Payslip data, stored in JSON format, includes detailed breakdowns such as basic salary, allowances, and deductions.  
   - **Role-Based Access**:  
     Authentication ensures employees view only their data, while HR/Admins have access to manage and generate payslips.

3. **Analytics and Reporting**:  
   - Leave and payroll trends are extracted from JSON files for reporting purposes.  
   - Reports are generated in CSV or PDF formats for HR use.

4. **Error Handling and Validation**:  
   - Overlapping leave requests are flagged automatically.  
   - Validation checks ensure JSON data integrity and adherence to leave and payroll policies.  

**Technical Advantages**  

- **JSON as a Database**:  
  Using JSON as a database provided hands-on experience with document-based storage systems. This understanding translated well to learning MongoDB, as both share similar structures and data management concepts, such as key-value pairs and hierarchical data representation.  

- **Flask Framework**:  
  Developing this application in Flask offered a lightweight, modular approach to web development. The knowledge gained from Flask, such as working with routes, middleware, and REST APIs, served as a foundation for learning Django. Django's built-in ORM, admin panel, and robust features were easier to grasp due to the familiarity with Flask’s basics.

**Technical Stack**  
- **Backend**: Flask (Python) for application logic and workflows.  
- **Database**: JSON files for lightweight and efficient data storage.  
- **Frontend**: HTML, CSS, JavaScript for an intuitive user interface.  
- **Deployment**: Hosted on **cPanel**, making it accessible for all employees and administrators.

**Outcomes**  
- Successfully transitioned from local testing to deployment on cPanel.  
- The application is actively used by 6Wresearch, improving leave and payroll management efficiency by 70%.  
- Provided valuable learning experiences in MongoDB (through JSON usage) and Django (through Flask foundations).
