from flask import Flask, jsonify, request, g
from database import get_logs
import sqlite3
from datetime import datetime
from config import DATABASE_FILE
from mqtt_publisher import (send_dispense_command, send_refill_command, 
                          set_hard_mode, reset_pending_module, publish_schedule)
from utils import transform_schedule_for_mqtt

app = Flask(__name__)

# Database connection management
def get_db():
    """Get database connection for the current request context"""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    """Close database connection at the end of request"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def start_api():
    app.run(host="0.0.0.0", port=4000)

# Doctor endpoints
"""
POST /api/doctors/create
Request format:
{
    "name": "Dr. Smith",
    "email": "smith@hospital.com"
}
"""
@app.route('/api/doctors/create', methods=['POST'])
def create_doctor():
    data = request.get_json()
    if not data or 'name' not in data or 'email' not in data:
        return jsonify({'error': 'Name and email required'}), 400
    
    db = get_db()
    c = db.cursor()
    try:
        c.execute('''
            INSERT INTO doctor (name, email) 
            VALUES (?, ?)
        ''', (data['name'], data['email']))
        db.commit()
        return jsonify({'id': c.lastrowid, 'status': 'success'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email already exists'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

"""
GET /api/doctors
Response: 
[
    {
        "id": 1,
        "name": "Dr. Smith",
        "email": "smith@hospital.com"
    }
]
"""
@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    db = get_db()
    c = db.cursor()
    c.execute('SELECT id, name, email FROM doctor')
    doctors = [{'id': row['id'], 'name': row['name'], 'email': row['email']} 
               for row in c.fetchall()]
    return jsonify(doctors)

"""
GET /api/doctors/{doctor_id}
Response: 
{
    "id": 1,
    "name": "Dr. Smith",
    "email": "smith@hospital.com",
    "patient_count": 10
}
"""
@app.route('/api/doctors/<int:doctor_id>', methods=['GET'])
def get_doctor_by_id(doctor_id):
    db = get_db()
    c = db.cursor()
    
    # Get doctor info
    c.execute('''
        SELECT id, name, email 
        FROM doctor 
        WHERE id = ?
    ''', (doctor_id,))
    
    doctor = c.fetchone()
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404
        
    # Get count of assigned patients
    c.execute('''
        SELECT COUNT(*) as count
        FROM patient 
        WHERE doctor_id = ?
    ''', (doctor_id,))
    
    patient_count = c.fetchone()['count']
    
    result = {
        'id': doctor['id'],
        'name': doctor['name'],
        'email': doctor['email'],
        'patient_count': patient_count
    }
    
    return jsonify(result)

"""
POST /api/doctors/search_by_email
Request:
{
    "email": "smith@hospital.com"
}
Response: 
{
    "id": 1,
    "name": "Dr. Smith",
    "email": "smith@hospital.com",
    "patient_count": 10
}
"""
@app.route('/api/doctors/search_by_email', methods=['POST'])
def get_doctor_by_email():
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'error': 'Name required'}), 400

    db = get_db()
    c = db.cursor()
    
    email= data.get("email")
    
    # Get doctor info
    c.execute('''
        SELECT d.id, d.name, d.email,
               COUNT(p.id) as patient_count
        FROM doctor d
        LEFT JOIN patient p ON p.doctor_id = d.id
        WHERE d.email = ?
        GROUP BY d.id
    ''', (email,))
    
    doctor = c.fetchone()
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404
    
    result = {
        'id': doctor['id'],
        'name': doctor['name'],
        'email': doctor['email'],
        'patient_count': doctor['patient_count']
    }
    
    return jsonify(result)

# Patient endpoints
"""
POST /api/patients/create
Request format:
{
    "name": "John Doe",
    "age": 45,
    "doctor_id": 1,
    "notes": "Diabetes patient"
}
"""
@app.route('/api/patients/create', methods=['POST'])
def create_patient():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Name required'}), 400

    db = get_db()
    c = db.cursor()
    try:
        doctor_id = data.get('doctor_id')
        if doctor_id is not None:
            c.execute('SELECT id FROM doctor WHERE id = ?', (doctor_id,))
            if not c.fetchone():
                return jsonify({'error': 'Invalid doctor_id'}), 400

        c.execute('''
            INSERT INTO patient (name, age, doctor_id, notes) 
            VALUES (?, ?, ?, ?)
        ''', (data['name'], 
              data.get('age'), 
              doctor_id,
              data.get('notes')))
        db.commit()
        return jsonify({'id': c.lastrowid, 'status': 'success'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Invalid doctor_id'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

"""
POST /api/patients/{patient_id}/assign_doctor
Request format:
{
    "doctor_id": 1
}
"""
@app.route('/api/patients/<int:patient_id>/assign_doctor', methods=['POST'])
def assign_doctor(patient_id):
    data = request.get_json()
    if not data or 'doctor_id' not in data:
        return jsonify({'error': 'doctor_id required'}), 400
    
    db = get_db()
    c = db.cursor()
    try:
        # Verify doctor exists
        c.execute('SELECT id FROM doctor WHERE id = ?', (data['doctor_id'],))
        if not c.fetchone():
            return jsonify({'error': 'Doctor not found'}), 404
            
        # Update patient's doctor
        c.execute('''
            UPDATE patient 
            SET doctor_id = ? 
            WHERE id = ?
        ''', (data['doctor_id'], patient_id))
        
        if c.rowcount == 0:
            return jsonify({'error': 'Patient not found'}), 404
            
        db.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

"""
GET /api/doctors/{doctor_id}/patients
Response: 
[
    {
        "id": 1,
        "name": "John Doe",
        "age": 45,
        "notes": "Diabetes patient"
    }
]
"""
@app.route('/api/doctors/<int:doctor_id>/patients', methods=['GET'])
def get_doctor_patients(doctor_id):
    db = get_db()
    c = db.cursor()
    c.execute('''
        SELECT p.id, p.name, p.age, p.notes 
        FROM patient p
        WHERE p.doctor_id = ?
    ''', (doctor_id,))
    
    patients = [{
        'id': row['id'],
        'name': row['name'],
        'age': row['age'],
        'notes': row['notes']
    } for row in c.fetchall()]
    
    return jsonify(patients)

"""
GET /api/patients
Response: 
[
    {
        "id": 1,
        "name": "John Doe",
        "age": 45,
        "doctor": "Dr. Smith"
    }
]
"""
@app.route('/api/patients', methods=['GET'])
def get_patients():
    db = get_db()
    c = db.cursor()
    c.execute('''
        SELECT p.id, p.name, p.age, d.name as doctor_name 
        FROM patient p 
        LEFT JOIN doctor d ON p.doctor_id = d.id
    ''')
    patients = [{
        'id': row['id'], 
        'name': row['name'], 
        'age': row['age'], 
        'doctor': row['doctor_name']
    } for row in c.fetchall()]
    return jsonify(patients)

"""
GET /api/patients/{patient_id}
Response: 
{
    "patient": {
        "id": 1,
        "name": "John Doe",
        "age": 45,
        "doctor": "Dr. Smith",
        "notes": "Diabetes patient"
    },
    "device": {
        "id": 1,
        "serial_number": "SN123456",
        "modules": [
            {
                "module": "module1",
                "pills_left": 10,
                "threshold": 5,
                "pending": false
            }
        ]
    },
   
}
"""
@app.route('/api/patients/<int:patient_id>', methods=['GET'])
def get_patient_details_by_id(patient_id):
    db = get_db()
    c = db.cursor()
    
    # Get patient info with device and modules
    c.execute('''
        SELECT p.id, p.name, p.age, p.notes,
               d.name as doctor_name,
               pd.id as dispenser_id, pd.serial_number,
               dm.module_name, dm.pills_left, dm.threshold, dm.pending
        FROM patient p 
        LEFT JOIN doctor d ON p.doctor_id = d.id 
        LEFT JOIN pill_dispenser pd ON p.id = pd.patient_id
        LEFT JOIN dispenser_module dm ON pd.id = dm.pill_dispenser_id
        WHERE p.id = ?
    ''', (patient_id,))
    
    rows = c.fetchall()
    if not rows:
        return jsonify({'error': 'Patient not found'}), 404

    # First row contains patient info
    first_row = rows[0]
    result = {
        'patient': {
            'id': first_row['id'],
            'name': first_row['name'],
            'age': first_row['age'],
            'doctor': first_row['doctor_name'],
            'notes': first_row['notes']
        },
        'device': {
            'id': first_row['dispenser_id'],
            'serial_number': first_row['serial_number'],
            'modules': [{
                'module': row['module_name'],
                'pills_left': row['pills_left'],
                'threshold': row['threshold'],
                'pending': bool(row['pending'])
            } for row in rows if row['module_name']],
        } if first_row['dispenser_id'] else None,
       
    }
    
    return jsonify(result)

"""
GET /api/patients/{patient_id}/schedule
Response: 
[
    {
        "id": 1,
        "module": "module1",
        "medicine_name": "Aspirin",
        "time": "08:00",
        "repeat_type": "custom",
        "days": ["mon", "wed", "fri"],
        "until_date": "2025-07-01"
    }
]
"""
@app.route('/api/patients/<int:patient_id>/schedule', methods=['GET'])
def get_patient_schedule(patient_id):
    db = get_db()
    c = db.cursor()
    c.execute('''
        SELECT s.*, dm.module_name 
        FROM schedule s
        LEFT JOIN dispenser_module dm ON s.dispenser_module_id = dm.id
        WHERE s.patient_id = ?
    ''', (patient_id,))
    
    schedules = [{
        'id': row['id'],
        'module': row['module_name'],
        'medicine_name': row['medicine_name'],
        'time': row['time'],
        'repeat_type': row['repeat_type'],
        'days': row['days_of_week'].split(',') if row['days_of_week'] else [],
        'until_date': row['until_date']
    } for row in c.fetchall()]
    
    return jsonify(schedules)

"""
POST /api/patients/{patient_id}/schedule
Request format:
[
    {
        "time": "08:00",
        "module": "module1",
        "medicine_name": "Aspirin",
        "days": ["mon", "wed", "fri"],
        "repeat_type": "custom",
        "until_date": "2025-07-01"
    }
]
Response:
{
    "status": "success",
    "schedules": [...]
}
"""
@app.route('/api/patients/<int:patient_id>/schedule', methods=['POST'])
def create_schedule(patient_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing schedule data'}), 400
        
    db = get_db()
    c = db.cursor()
    
    try:
        # Get the device id
        c.execute('''
            SELECT pd.id, pd.serial_number 
            FROM pill_dispenser pd 
            WHERE pd.patient_id = ?
        ''', (patient_id,))
        device = c.fetchone()
        if not device:
            return jsonify({'error': 'No device found for patient'}), 404
            
        new_schedules = []
        
        for schedule in data:
            # Validate required fields
            if not all(key in schedule for key in ['time', 'module', 'medicine_name']):
                return jsonify({'error': 'Missing required schedule fields'}), 400

            # Get module id
            c.execute('''
                SELECT id FROM dispenser_module 
                WHERE pill_dispenser_id = ? AND module_name = ?
            ''', (device['id'], schedule['module']))
            module = c.fetchone()
            if not module:
                return jsonify({'error': f'Module {schedule["module"]} not found'}), 404

            # Insert schedule
            c.execute('''
                INSERT INTO schedule (
                    patient_id, 
                    dispenser_module_id,
                    medicine_name,
                    time,
                    repeat_type,
                    days_of_week,
                    until_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                patient_id,
                module['id'],
                schedule['medicine_name'],
                schedule['time'],
                schedule.get('repeat_type', 'daily'),
                ','.join(schedule.get('days', [])) if schedule.get('days') else None,
                schedule.get('until_date')
            ))
            
            schedule_id = c.lastrowid
            new_schedules.append({**schedule, 'id': schedule_id})
            
        db.commit()
        
        # Transform and publish to MQTT
        mqtt_schedule = transform_schedule_for_mqtt(new_schedules)
        publish_schedule(device['serial_number'], mqtt_schedule)
        
        return jsonify({'status': 'success', 'schedules': new_schedules}), 201
        
    except Exception as e:
        db.rollback()
        print("Error at create schedule: ", e)
        return jsonify({'error': str(e)}), 500
    

# Device control endpoints
"""
POST /api/devices/{device_id}/dispense
Request format:
{
    "module_name": "module1"
}
Response: 
{
    "status": "success",
    "message": "Dispense command sent to module1"
}
"""
@app.route('/api/devices/<device_id>/dispense', methods=['POST'])
def trigger_dispense(device_id):
    data = request.get_json()
    if not data or 'module_name' not in data:
        return jsonify({'error': 'module_name required'}), 400
    
    db = get_db()
    c = db.cursor()
    try:
        # Verify module exists and get its ID
        c.execute('''
            SELECT dm.id, dm.pills_left 
            FROM dispenser_module dm
            JOIN pill_dispenser pd ON dm.pill_dispenser_id = pd.id
            WHERE pd.serial_number = ? AND dm.module_name = ?
        ''', (device_id, data['module_name']))
        
        module = c.fetchone()
        if not module:
            return jsonify({'error': 'Module not found'}), 404
            
        if module['pills_left'] <= 0:
            return jsonify({'error': 'Module is empty'}), 400
            
        # Update pills count and set pending
        c.execute('''
            UPDATE dispenser_module 
            SET pills_left = pills_left - 1
            WHERE id = ?
        ''', (module['id'],))
        
        # Log the event
        c.execute('''
            INSERT INTO logs (timestamp, dispenser_module_id, message)
            VALUES (?, ?, ?)
        ''', (datetime.now().isoformat(), module['id'], f"Dispense command sent"))
        
        db.commit()
        
        # Send MQTT command
        send_dispense_command(device_id, data['module_name'])
        return jsonify({'status': 'success', 'message': f'Dispense command sent to {data["module_name"]}'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

"""
POST /api/devices/{device_id}/refill
Request format:
{
    "module_name": "module1",
    "count": 30
}
Response:
{
    "status": "success",
    "message": "Refill command sent to module1"
}
"""
@app.route('/api/devices/<device_id>/refill', methods=['POST'])
def refill_module(device_id):
    data = request.get_json()
    if not data or 'module_name' not in data or 'count' not in data:
        return jsonify({'error': 'module_name and count required'}), 400
    
    db = get_db()
    c = db.cursor()
    try:
        # Verify module exists
        c.execute('''
            SELECT dm.id
            FROM dispenser_module dm
            JOIN pill_dispenser pd ON dm.pill_dispenser_id = pd.id
            WHERE pd.serial_number = ? AND dm.module_name = ?
        ''', (device_id, data['module_name']))
        
        module = c.fetchone()
        if not module:
            return jsonify({'error': 'Module not found'}), 404
            
        # Update pills count
        c.execute('''
            UPDATE dispenser_module 
            SET pills_left = ?,
                pending = 0
            WHERE id = ?
        ''', (data['count'], module['id']))
        
        # Log the event
        c.execute('''
            INSERT INTO logs (timestamp, dispenser_module_id, message)
            VALUES (?, ?, ?)
        ''', (datetime.now().isoformat(), module['id'], f"Refilled with {data['count']} pills"))
        
        db.commit()
        
        # Send MQTT command
        send_refill_command(device_id, data['module_name'], data['count'])
        return jsonify({'status': 'success', 'message': f'Refill command sent to {data["module_name"]}'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

"""
POST /api/devices/{device_id}/reset_pending
Request format:
{
    "module_name": "module1"
}
Response:
{
    "status": "success",
    "message": "Reset pending state"
}
"""
@app.route('/api/devices/<device_id>/reset_pending', methods=['POST'])
def reset_pending_state(device_id):
    data = request.get_json()
    if not data or 'module_name' not in data:
        return jsonify({'error': 'module_name required'}), 400
    
    db = get_db()
    c = db.cursor()
    try:
        # Verify module exists
        c.execute('''
            SELECT dm.id
            FROM dispenser_module dm
            JOIN pill_dispenser pd ON dm.pill_dispenser_id = pd.id
            WHERE pd.serial_number = ? AND dm.module_name = ?
        ''', (device_id, data['module_name']))
        
        module = c.fetchone()
        if not module:
            return jsonify({'error': 'Module not found'}), 404
            
        # Reset pending state
        c.execute('''
            UPDATE dispenser_module 
            SET pending = 0
            WHERE id = ?
        ''', (module['id'],))
        
        # Log the event
        c.execute('''
            INSERT INTO logs (timestamp, dispenser_module_id, message)
            VALUES (?, ?, ?)
        ''', (datetime.now().isoformat(), module['id'], "Pending state reset"))
        
        db.commit()
        
        # Send MQTT command
        reset_pending_module(device_id, data['module_name'])
        return jsonify({'status': 'success', 'message': 'Reset pending state'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

# Device status endpoint
"""
GET /api/patients/{patient_id}/device
Response: 
{
    "serial_number": "SN123456",
    "modules": [
        {
            "name": "module1",
            "pills_left": 10,
            "threshold": 5,
            "pending": false
        }
    ]
}
"""
@app.route('/api/patients/<int:patient_id>/device', methods=['GET'])
def get_device_status(patient_id):
    db = get_db()
    c = db.cursor()
    
    # First get the pill_dispenser for this patient
    c.execute('''
        SELECT pd.id, pd.serial_number
        FROM pill_dispenser pd
        WHERE pd.patient_id = ?
    ''', (patient_id,))
    
    device = c.fetchone()
    if not device:
        return jsonify({'error': 'No device found for this patient'}), 404
        
    # Now get the modules for this dispenser
    c.execute('''
        SELECT module_name, pills_left, threshold, pending
        FROM dispenser_module
        WHERE pill_dispenser_id = ?
    ''', (device['id'],))
    
    modules = [{
        'name': row['module_name'],
        'pills_left': row['pills_left'],
        'threshold': row['threshold'],
        'pending': bool(row['pending'])
    } for row in c.fetchall()]
    
    device_status = {
        'serial_number': device['serial_number'],
        'modules': modules
    }
    
    return jsonify(device_status)

"""
POST /api/patients/{patient_id}/assign_device
Request format:
{
    "serial_number": "PD001"
}
Response:
{
    "status": "success",
    "device": {
        "id": 1,
        "serial_number": "PD001"
    }
}
"""
@app.route('/api/patients/<int:patient_id>/assign_device', methods=['POST'])
def assign_device(patient_id):
    data = request.get_json()
    if not data or 'serial_number' not in data:
        return jsonify({'error': 'serial_number required'}), 400

    db = get_db()
    c = db.cursor()
    try:
        # Check if patient exists
        c.execute('SELECT id FROM patient WHERE id = ?', (patient_id,))
        if not c.fetchone():
            return jsonify({'error': 'Patient not found'}), 404

        # ! currently only device is there, so no need to check already assigned
        # ! in case its already assigned it will be reassigned to another patient 
        # ! for testing
        # # Check if device is already assigned
        # c.execute('SELECT id FROM pill_dispenser WHERE serial_number = ?', (data['serial_number'],))
        # if c.fetchone():
        #     return jsonify({'error': 'Device already assigned to another patient'}), 409

        # # Create pill dispenser entry
        # c.execute('''
        #     INSERT INTO pill_dispenser (patient_id, serial_number)
        #     VALUES (?, ?)
        # ''', (patient_id, data['serial_number']))
        
        # dispenser_id = c.lastrowid
        
        # Get pill dispenser by serial number
        c.execute('SELECT id FROM pill_dispenser WHERE serial_number = ?', (data['serial_number'],))
        dispenser = c.fetchone()
        if not dispenser:
            return jsonify({'error': 'Device not found'}), 404

        dispenser_id = dispenser['id']

        # Assign patient_id to the dispenser
        c.execute('UPDATE pill_dispenser SET patient_id = ? WHERE id = ?', (patient_id, dispenser_id))
        if c.rowcount == 0:
            return jsonify({'error': 'Failed to assign device to patient'}), 500

        # !not needed as only one device there and its getting reassigned to other people
        # # Create default modules (two per dispenser)
        # c.execute('''
        #     INSERT INTO dispenser_module (pill_dispenser_id, module_name, pills_left, threshold)
        #     VALUES 
        #         (?, 'module1', 0, 5),
        #         (?, 'module2', 0, 5)
        # ''', (dispenser_id, dispenser_id))

        db.commit()
        
        return jsonify({
            'status': 'success',
            'device': {
                'id': dispenser_id,
                'serial_number': data['serial_number']
            }
        }), 201
        
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({'error': 'Patient already has a device assigned'}), 409
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

"""
PUT /api/schedules/{schedule_id}
Request format:
{
    "time": "08:00",
    "module": "module1",
    "medicine_name": "Aspirin",
    "days": ["mon", "wed", "fri"],
    "repeat_type": "custom",
    "until_date": "2025-07-01"
}
Response:
{
    "status": "success",
    "schedule": {
        "id": 1,
        "time": "08:00",
        ...
    }
}
"""
@app.route('/api/schedules/<int:schedule_id>', methods=['PUT'])
def update_schedule(schedule_id):
    import traceback
    import sys
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    db = get_db()
    c = db.cursor()
    
    try:
        # First get the existing schedule to verify it exists and get patient_id
        c.execute('''
            SELECT s.*, dm.module_name, pd.serial_number 
            FROM schedule s
            JOIN dispenser_module dm ON s.dispenser_module_id = dm.id
            JOIN pill_dispenser pd ON dm.pill_dispenser_id = pd.id
            WHERE s.id = ?
        ''', (schedule_id,))
 
        existing = c.fetchone()
        if not existing:
            return jsonify({'error': 'Schedule not found'}), 404

        # If module is being changed, verify new module exists
        if 'module' in data:
            c.execute('''
                SELECT dm.id 
                FROM dispenser_module dm
                JOIN pill_dispenser pd ON dm.pill_dispenser_id = pd.id
                WHERE pd.patient_id = ? AND dm.module_name = ?
            ''', (existing['patient_id'], data['module']))
            
            module = c.fetchone()
            if not module:
                return jsonify({'error': 'Invalid module name'}), 400
            module_id = module['id']
        else:
            module_id = existing['dispenser_module_id']

        # Update the schedule
        c.execute('''
            UPDATE schedule 
            SET time = ?,
                medicine_name = ?,
                repeat_type = ?,
                days_of_week = ?,
                until_date = ?,
                dispenser_module_id = ?
            WHERE id = ?
        ''', (
            data.get('time', existing['time']),
            data.get('medicine_name', existing['medicine_name']),
            data.get('repeat_type', existing['repeat_type']),
            ','.join(data.get('days', existing['days_of_week'].split(','))),
            data.get('until_date', existing['until_date']),
            module_id,
            schedule_id
        ))

        # Get all schedules for this patient to republish
        c.execute('''
            SELECT s.*, dm.module_name
            FROM schedule s
            JOIN dispenser_module dm ON s.dispenser_module_id = dm.id
            JOIN pill_dispenser pd ON dm.pill_dispenser_id = pd.id
            WHERE s.patient_id = ?
        ''', (existing['patient_id'],))

        schedules = [{
            'id': row['id'],
            'time': row['time'],
            'module': row['module_name'],
            'days': row['days_of_week'].split(',') if row['days_of_week'] else [],
            'until_date': row['until_date']
        } for row in c.fetchall()]

        db.commit()

        # Republish entire schedule via MQTT
        mqtt_schedule = transform_schedule_for_mqtt(schedules)
        publish_schedule(existing['serial_number'], mqtt_schedule)

        return jsonify({
            'status': 'success',
            'schedule': {
                'id': schedule_id,
                'time': data.get('time', existing['time']),
                'module': data.get('module', existing['module_name']),
                'medicine_name': data.get('medicine_name', existing['medicine_name']),
                'repeat_type': data.get('repeat_type', existing['repeat_type']),
                'days': data.get('days', existing['days_of_week'].split(',')),
                'until_date': data.get('until_date', existing['until_date'])
            }
        })

    except Exception as e:
        db.rollback()
        print("error @update_schedule: ", e )
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb = traceback.extract_tb(exc_traceback)
        for line in tb:
            print(f'File "{line.filename}", line {line.lineno}, in {line.name}')
        print(f'  {line.line}')
        return jsonify({'error': str(e)}), 500

"""
DELETE /api/schedules/{schedule_id}
Response:
{
    "status": "success",
    "message": "Schedule deleted successfully"
}
"""
@app.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    db = get_db()
    c = db.cursor()
    
    try:
        # First get the schedule details to get patient_id and device info
        c.execute('''
            SELECT s.patient_id, pd.serial_number 
            FROM schedule s
            JOIN dispenser_module dm ON s.dispenser_module_id = dm.id
            JOIN pill_dispenser pd ON dm.pill_dispenser_id = pd.id
            WHERE s.id = ?
        ''', (schedule_id,))
        
        schedule = c.fetchone()
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404

        # Delete the schedule
        c.execute('DELETE FROM schedule WHERE id = ?', (schedule_id,))
        
        # Get remaining schedules for this patient to republish
        c.execute('''
            SELECT s.*, dm.module_name
            FROM schedule s
            JOIN dispenser_module dm ON s.dispenser_module_id = dm.id
            WHERE s.patient_id = ?
        ''', (schedule['patient_id'],))

        schedules = [{
            'time': row['time'],
            'module': row['module_name'],
            'days': row['days_of_week'].split(',') if row['days_of_week'] else [],
            'until_date': row['until_date']
        } for row in c.fetchall()]

        db.commit()

        # Republish updated schedule via MQTT
        if schedules:
            mqtt_schedule = transform_schedule_for_mqtt(schedules)
            publish_schedule(schedule['serial_number'], mqtt_schedule)
        else:
            # If no schedules left, send empty schedule
            publish_schedule(schedule['serial_number'], [])

        return jsonify({
            'status': 'success',
            'message': 'Schedule deleted successfully'
        })

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500


# ! hardmode endpoint left