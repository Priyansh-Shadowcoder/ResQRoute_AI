from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from models import (db, User, Hospital, Doctor, BloodInventory, MedicalInventory, Equipment, Ambulance)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from datetime import datetime, date
from functools import wraps
import os

from dotenv import load_dotenv

load_dotenv()
# ==========================================
# APPLICATION CONFIGURATION
# ==========================================

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY'
)

if not app.config['SECRET_KEY']:
    raise RuntimeError("SECRET_KEY environment variable is missing!")
load_dotenv()

database_url = os.getenv("DATABASE_URL", "sqlite:///health.db")

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg2://",
        1
    )
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg2://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True
}

db.init_app(app)

# ==========================================
# ROLE CONFIGURATION
# ==========================================

ROLE_PAGES = {
    'admin': 'admin_interface',
    'hospital': 'hospital_interface',
    'ambulance': 'ambulance_interface',
    'drone': 'drone_telemetry'
}

ROLE_ALIASES = {
    'admin_dashboard.html': 'admin',
    'hospital_portal.html': 'hospital',
    'index_hospital.html': 'hospital',
    'ambulance_hud.html': 'ambulance',
    'drone_telemetry.html': 'drone'
}


def normalize_role(role):

    role = role.strip().lower()

    if role in ROLE_PAGES:
        return role

    return ROLE_ALIASES.get(role)


# ==========================================
# ROLE-BASED ACCESS CONTROL
# ==========================================

def role_required(required_role):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if 'user_id' not in session:

                flash("Please login first.", "error")

                return redirect(url_for('interface'))

            if session.get('role') != required_role:

                flash("Unauthorized access!", "error")

                return redirect(url_for('dashboard_redirect'))

            return function(*args, **kwargs)

        return wrapper

    return decorator


# ==========================================
# MAIN PORTAL
# ==========================================

@app.route('/')
@app.route('/interface')
@app.route('/interface.html')
def interface():

    return render_template('interface.html')


# ==========================================
# REGISTRATION
# ==========================================

@app.route('/register', methods=['POST'])
def register():

    name = request.form.get('name', '').strip()
    mobile = request.form.get('mobile', '').strip()
    password = request.form.get('password', '')

    role = normalize_role(request.form.get('role', ''))
    if role == 'ambulance':

        flash("Ambulance accounts must be created by hospital staff.", "error")

        return redirect(url_for('interface'))

    # Hospital name is required only for hospital accounts
    hospital_name = request.form.get('hospital_name', '').strip()

    # Basic validation
    if not name or not mobile or not password or not role:

        flash("Please fill all registration fields.", "error")
        return redirect(url_for('interface'))

    if not mobile.isdigit() or len(mobile) != 10:

        flash("Enter a valid 10-digit mobile number.", "error")
        return redirect(url_for('interface'))

    if len(password) < 6:

        flash("Password must contain at least 6 characters.", "error")
        return redirect(url_for('interface'))

    if role == 'admin':

        flash("Admin accounts cannot be self-registered.", "error")
        return redirect(url_for('interface'))

    if role == 'hospital' and not hospital_name:

        flash("Please enter your hospital name.", "error")
        return redirect(url_for('interface'))

    # Check duplicate mobile number
    existing_user = User.query.filter_by(mobile=mobile).first()

    if existing_user:

        flash("Mobile number is already registered.", "error")
        return redirect(url_for('interface'))

    # Hash password
    hashed_password = generate_password_hash(password)

    try:

        hospital_id = None

        # ==================================
        # HOSPITAL FIND OR CREATE
        # ==================================

        if role == 'hospital':

            # Search for an existing hospital
            hospital = Hospital.query.filter(
                db.func.lower(db.func.trim(Hospital.name))
                == hospital_name.lower()
            ).first()

            # Create hospital if it doesn't exist
            if not hospital:

                hospital = Hospital(
                    name=hospital_name
                )

                db.session.add(hospital)

                db.session.flush()

            hospital_id = hospital.id

        # ==================================
        # CREATE USER
        # ==================================

        new_user = User(
            name=name,
            mobile=mobile,
            password=hashed_password,
            role=role,
            hospital_id=hospital_id
        )

        db.session.add(new_user)

        db.session.commit()

        flash("Registration successful! Please login.", "success")

    except Exception as e:

        db.session.rollback()

        print("Registration Error:", e)

        flash("Registration failed. Please try again.", "error")

    return redirect(url_for('interface'))


# ==========================================
# LOGIN
# ==========================================

@app.route('/login', methods=['POST'])
def login():

    mobile = request.form.get('login_id', '').strip()

    password = request.form.get('password', '')

    user = User.query.filter_by(
        mobile=mobile
    ).first()

    if user and check_password_hash(user.password, password):

        session.clear()

        session['user_id'] = user.id

        session['name'] = user.name

        session['role'] = user.role

        session['hospital_id'] = user.hospital_id

        session['ambulance_id'] = user.ambulance_id

        flash("Welcome to ResQRoute AI!", "success")

        return redirect(url_for('dashboard_redirect'))

    flash("Invalid mobile number or password.", "error")

    return redirect(url_for('interface'))


# ==========================================
# DASHBOARD REDIRECTION
# ==========================================

@app.route('/dashboard')
def dashboard_redirect():

    if 'user_id' not in session:

        return redirect(url_for('interface'))

    role = session.get('role')

    endpoint = ROLE_PAGES.get(role)

    if endpoint:

        return redirect(url_for(endpoint))

    session.clear()

    return redirect(url_for('interface'))


# ==========================================
# LOGOUT
# ==========================================

@app.route('/logout')
def logout():

    session.clear()

    flash("You have been logged out successfully.", "success")

    return redirect(url_for('interface'))


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@app.route('/admin')
@app.route('/admin_dashboard.html')
@role_required('admin')
def admin_interface():

    # Fetch overall hospital statistics
    total_hospitals = Hospital.query.count()

    total_beds = db.session.query(
        db.func.sum(Hospital.total_beds)
    ).scalar() or 0

    available_beds = db.session.query(
        db.func.sum(Hospital.available_beds)
    ).scalar() or 0

    total_doctors = Doctor.query.count()

    # Fetch ambulance statistics
    total_ambulances = Ambulance.query.count()

    available_ambulances = Ambulance.query.filter_by(
        status='Available'
    ).count()

    enroute_ambulances = Ambulance.query.filter_by(
        status='En Route'
    ).count()

    # Fetch all ambulances across hospitals
    ambulances = Ambulance.query.order_by(Ambulance.updated_at.desc()).all()

    # Fetch all registered hospitals
    hospitals = Hospital.query.order_by(Hospital.name.asc()).all()

    return render_template(
        'admin_interface.html',

        total_hospitals=total_hospitals,

        total_beds=total_beds,

        available_beds=available_beds,

        total_doctors=total_doctors,

        total_ambulances=total_ambulances,

        available_ambulances=available_ambulances,

        enroute_ambulances=enroute_ambulances,

        ambulances=ambulances,
        
        hospitals=hospitals
    )


# ==========================================
# HOSPITAL DASHBOARD
# ==========================================

@app.route('/hospital')
@app.route('/hospital_portal.html')
@app.route('/index_hospital.html')
@role_required('hospital')
def hospital_interface():

    # Get the logged-in user's hospital ID
    hospital_id = session.get('hospital_id')

    # Find the corresponding hospital
    hospital = Hospital.query.get_or_404(hospital_id)

    # Fetch only this hospital's records
    doctors = Doctor.query.filter_by(
        hospital_id=hospital_id
    ).all()

    blood_inventory = BloodInventory.query.filter_by(
        hospital_id=hospital_id
    ).all()

    medical_inventory = MedicalInventory.query.filter_by(
        hospital_id=hospital_id
    ).all()

    equipment = Equipment.query.filter_by(
        hospital_id=hospital_id
    ).all()

    ambulances = Ambulance.query.filter_by(
        hospital_id=hospital_id
    ).all()

    # Count doctors currently available
    doctors_on_duty = Doctor.query.filter_by(
        hospital_id=hospital_id,
        status='Available'
    ).count()

    return render_template(
        'hospital_interface.html',

        hospital=hospital,

        doctors=doctors,

        blood_inventory=blood_inventory,

        medical_inventory=medical_inventory,

        equipment=equipment,

        ambulances=ambulances,

        doctors_on_duty=doctors_on_duty
    )


# ==========================================
# UPDATE HOSPITAL CAPACITY
# ==========================================

@app.route('/update_hospital_capacity', methods=['POST'])
@role_required('hospital')
def update_hospital_capacity():

    hospital_id = session.get('hospital_id')

    hospital = Hospital.query.get_or_404(hospital_id)

    try:
        total_beds = int(request.form.get('total_beds'))
        available_beds = int(request.form.get('available_beds'))
        emergency_bays = int(request.form.get('emergency_bays'))
        oxygen_percentage = float(request.form.get('oxygen_percentage'))

        # Validate values
        if total_beds < 0 or available_beds < 0 or emergency_bays < 0:
            flash("Resource quantities cannot be negative.", "error")
            return redirect(url_for('hospital_interface'))

        if available_beds > total_beds:
            flash("Available beds cannot exceed total beds.", "error")
            return redirect(url_for('hospital_interface'))

        if not 0 <= oxygen_percentage <= 100:
            flash("Oxygen percentage must be between 0 and 100.", "error")
            return redirect(url_for('hospital_interface'))

        # Update hospital information
        hospital.total_beds = total_beds
        hospital.available_beds = available_beds
        hospital.emergency_bays = emergency_bays
        hospital.oxygen_percentage = oxygen_percentage

        db.session.commit()

        flash("Hospital capacity updated successfully!", "success")

    except (ValueError, TypeError):
        db.session.rollback()
        flash("Please enter valid numerical values.", "error")

    return redirect(url_for('hospital_interface'))


# ==========================================
# ADD DOCTOR
# ==========================================

@app.route('/add_doctor', methods=['POST'])
@role_required('hospital')
def add_doctor():

    # Get hospital ID from logged-in session
    hospital_id = session.get('hospital_id')

    # Get form data
    name = request.form.get('name', '').strip()
    specialization = request.form.get('specialization', '').strip()
    shift = request.form.get('shift', '').strip()
    status = request.form.get('status', '').strip()

    # Basic validation
    if not name or not specialization or not shift or not status:

        flash("Please fill all doctor details.", "error")

        return redirect(url_for('hospital_interface'))

    try:

        # Create doctor record
        new_doctor = Doctor(
            name=name,
            specialization=specialization,
            shift=shift,
            status=status,
            hospital_id=hospital_id
        )

        db.session.add(new_doctor)

        db.session.commit()

        flash("Doctor added successfully!", "success")

    except Exception as e:

        db.session.rollback()

        print("Doctor Addition Error:", e)

        flash("Unable to add doctor.", "error")

    return redirect(url_for('hospital_interface') + '#doctors')

@app.route('/add_blood', methods=['POST'])
@role_required('hospital')
def add_blood():

    hospital_id = session.get('hospital_id')

    blood_group = request.form.get('blood_group', '').strip().upper()

    try:
        available_units = int(request.form.get('available_units', 0))
        required_units = int(request.form.get('required_units', 0))

        if not blood_group:
            flash("Please select a blood group.", "error")
            return redirect(url_for('hospital_interface') + '#blood-bank')

        if available_units < 0 or required_units < 0:
            flash("Blood units cannot be negative.", "error")
            return redirect(url_for('hospital_interface') + '#blood-bank')

        # Check whether this blood group already exists
        existing_blood = BloodInventory.query.filter_by(
            hospital_id=hospital_id,
            blood_group=blood_group
        ).first()

        if existing_blood:
            flash("This blood group already exists in your inventory.", "error")
            return redirect(url_for('hospital_interface') + '#blood-bank')

        new_blood = BloodInventory(
            blood_group=blood_group,
            available_units=available_units,
            required_units=required_units,
            hospital_id=hospital_id
        )

        db.session.add(new_blood)
        db.session.commit()

        flash("Blood inventory added successfully!", "success")

    except ValueError:
        flash("Please enter valid numerical values.", "error")

    except Exception as e:
        db.session.rollback()
        print("Blood Inventory Error:", e)
        flash("Unable to add blood inventory.", "error")

    return redirect(url_for('hospital_interface') + '#blood-bank')

@app.route('/add_medicine', methods=['POST'])
@role_required('hospital')
def add_medicine():

    hospital_id = session.get('hospital_id')

    item_name = request.form.get('item_name', '').strip()
    expiry_date_input = request.form.get('expiry_date', '').strip()

    try:
        quantity = int(request.form.get('quantity', 0))

        if not item_name or not expiry_date_input:
            flash("Please fill all medicine details.", "error")
            return redirect(url_for('hospital_interface') + '#medical-inventory')

        if quantity < 0:
            flash("Medicine quantity cannot be negative.", "error")
            return redirect(url_for('hospital_interface') + '#medical-inventory')

        expiry_date = datetime.strptime(
            expiry_date_input, '%Y-%m-%d'
        ).date()

        # Automatically determine medicine status
        if expiry_date < date.today():
            status = "Expired"
        elif quantity == 0:
            status = "Out of Stock"
        else:
            status = "Available"

        new_medicine = MedicalInventory(
            item_name=item_name,
            quantity=quantity,
            expiry_date=expiry_date,
            status=status,
            hospital_id=hospital_id
        )

        db.session.add(new_medicine)
        db.session.commit()

        flash("Medicine added successfully!", "success")

    except ValueError:
        flash("Please enter valid medicine details.", "error")

    except Exception as e:
        db.session.rollback()
        print("Medicine Addition Error:", e)
        flash("Unable to add medicine.", "error")

    return redirect(url_for('hospital_interface') + '#medical-inventory')
@app.route('/add_equipment', methods=['POST'])
@role_required('hospital')
def add_equipment():

    hospital_id = session.get('hospital_id')

    equipment_name = request.form.get('equipment_name', '').strip()

    try:
        total_quantity = int(request.form.get('total_quantity', 0))
        available_quantity = int(request.form.get('available_quantity', 0))

        if not equipment_name:
            flash("Please enter equipment name.", "error")
            return redirect(url_for('hospital_interface') + '#equipment')

        if total_quantity < 0 or available_quantity < 0:
            flash("Equipment quantities cannot be negative.", "error")
            return redirect(url_for('hospital_interface') + '#equipment')

        if available_quantity > total_quantity:
            flash("Available quantity cannot exceed total quantity.", "error")
            return redirect(url_for('hospital_interface') + '#equipment')

        # Determine equipment availability
        new_equipment = Equipment(
            equipment_name=equipment_name,
            total_quantity=total_quantity,
            available_quantity=available_quantity,
            hospital_id=hospital_id
        )

        db.session.add(new_equipment)
        db.session.commit()

        flash("Equipment added successfully!", "success")

    except ValueError:
        flash("Please enter valid numerical quantities.", "error")

    except Exception as e:
        db.session.rollback()
        print("Equipment Addition Error:", e)
        flash("Unable to add equipment.", "error")

    return redirect(url_for('hospital_interface') + '#equipment')


@app.route('/edit_equipment/<int:equipment_id>', methods=['GET', 'POST'])
@role_required('hospital')
def edit_equipment(equipment_id):

    hospital_id = session.get('hospital_id')

    equipment = Equipment.query.filter_by(
        id=equipment_id,
        hospital_id=hospital_id
    ).first_or_404()

    if request.method == 'POST':

        equipment_name = request.form.get(
            'equipment_name', ''
        ).strip()

        try:
            total_quantity = int(
                request.form.get('total_quantity', 0)
            )

            available_quantity = int(
                request.form.get('available_quantity', 0)
            )

            if not equipment_name:
                flash("Please enter equipment name.", "error")
                return redirect(
                    url_for('edit_equipment', equipment_id=equipment.id)
                )

            if total_quantity < 0 or available_quantity < 0:
                flash("Quantities cannot be negative.", "error")
                return redirect(
                    url_for('edit_equipment', equipment_id=equipment.id)
                )

            if available_quantity > total_quantity:
                flash(
                    "Available quantity cannot exceed total quantity.",
                    "error"
                )
                return redirect(
                    url_for('edit_equipment', equipment_id=equipment.id)
                )

            equipment.equipment_name = equipment_name
            equipment.total_quantity = total_quantity
            equipment.available_quantity = available_quantity

            db.session.commit()

            flash("Equipment updated successfully!", "success")

            return redirect(
                url_for('hospital_interface') + '#equipment'
            )

        except ValueError:
            flash("Please enter valid numerical quantities.", "error")

        except Exception as e:
            db.session.rollback()
            print("Equipment Update Error:", e)
            flash("Unable to update equipment.", "error")

    return render_template(
        'edit_equipment.html',
        equipment=equipment
    )

@app.route('/delete_equipment/<int:equipment_id>', methods=['POST'])
@role_required('hospital')
def delete_equipment(equipment_id):

    hospital_id = session.get('hospital_id')

    equipment = Equipment.query.filter_by(
        id=equipment_id,
        hospital_id=hospital_id
    ).first_or_404()

    try:
        db.session.delete(equipment)
        db.session.commit()

        flash("Equipment deleted successfully!", "success")

    except Exception as e:
        db.session.rollback()
        flash("Error deleting equipment.", "danger")
        print("Equipment deletion error:", e)

    return redirect(url_for('hospital_interface') + '#equipment')

@app.route('/add_ambulance', methods=['POST'])
@role_required('hospital')
def add_ambulance():

    hospital_id = session.get('hospital_id')

    vehicle_number = request.form.get('vehicle_number', '').strip().upper()
    driver_id = request.form.get('driver_id', '').strip()
    status = request.form.get('status', '').strip()
    medical_equipment = request.form.get('medical_equipment', '').strip()
    medical_supplies = request.form.get('medical_supplies', '').strip()

    # Validate required fields
    if not vehicle_number or not driver_id or not status:
        flash('Please fill in all required ambulance details.', 'error')
        return redirect(url_for('hospital_interface') + '#ambulances')

    # Check whether this vehicle is already registered
    existing_ambulance = Ambulance.query.filter_by(
        vehicle_number=vehicle_number
    ).first()

    if existing_ambulance:
        flash('This ambulance is already registered.', 'error')
        return redirect(url_for('hospital_interface') + '#ambulances')

    try:
        new_ambulance = Ambulance(
            vehicle_number=vehicle_number,
            driver_id=driver_id,
            hospital_id=hospital_id,
            status=status,
            medical_equipment=medical_equipment,
            medical_supplies=medical_supplies
        )

        db.session.add(new_ambulance)
        db.session.commit()

        flash('Ambulance registered successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        print("Ambulance registration error:", e)
        flash('Something went wrong while registering the ambulance.', 'error')

    return redirect(url_for('hospital_interface') + '#ambulances')

@app.route('/edit_ambulance/<int:ambulance_id>', methods=['GET', 'POST'])
@role_required('hospital')
def edit_ambulance(ambulance_id):

    hospital_id = session.get('hospital_id')

    # Fetch only an ambulance belonging to this hospital
    ambulance = Ambulance.query.filter_by(
        id=ambulance_id,
        hospital_id=hospital_id
    ).first_or_404()

    if request.method == 'POST':

        vehicle_number = request.form.get('vehicle_number', '').strip().upper()
        driver_id = request.form.get('driver_id', '').strip()
        status = request.form.get('status', '').strip()
        medical_equipment = request.form.get('medical_equipment', '').strip()
        medical_supplies = request.form.get('medical_supplies', '').strip()

        if not vehicle_number or not driver_id or not status:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for(
                'edit_ambulance',
                ambulance_id=ambulance.id
            ))

        # Check whether another ambulance uses this registration number
        duplicate = Ambulance.query.filter(
            Ambulance.vehicle_number == vehicle_number,
            Ambulance.id != ambulance_id
        ).first()

        if duplicate:
            flash('This vehicle registration number is already in use.', 'error')
            return redirect(url_for(
                'edit_ambulance',
                ambulance_id=ambulance.id
            ))

        try:
            ambulance.vehicle_number = vehicle_number
            ambulance.driver_id = driver_id
            ambulance.status = status
            ambulance.medical_equipment = medical_equipment
            ambulance.medical_supplies = medical_supplies

            db.session.commit()

            flash('Ambulance updated successfully!', 'success')

            return redirect(url_for('hospital_interface') + '#ambulances')

        except Exception as e:
            db.session.rollback()
            print("Ambulance update error:", e)
            flash('Unable to update ambulance.', 'error')

    return render_template(
        'edit_ambulance.html',
        ambulance=ambulance
    )


@app.route('/delete_ambulance/<int:ambulance_id>', methods=['POST'])
@role_required('hospital')
def delete_ambulance(ambulance_id):

    hospital_id = session.get('hospital_id')

    ambulance = Ambulance.query.filter_by(
        id=ambulance_id,
        hospital_id=hospital_id
    ).first_or_404()

    try:
        db.session.delete(ambulance)
        db.session.commit()

        flash('Ambulance deleted successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        print("Ambulance deletion error:", e)
        flash('Unable to delete ambulance.', 'error')

    return redirect(url_for('hospital_interface') + '#ambulances')


@app.route('/edit_medicine/<int:medicine_id>', methods=['GET', 'POST'])
@role_required('hospital')
def edit_medicine(medicine_id):

    hospital_id = session.get('hospital_id')

    # Find medicine belonging to the logged-in hospital
    medicine = MedicalInventory.query.filter_by(
        id=medicine_id,
        hospital_id=hospital_id
    ).first_or_404()

    if request.method == 'POST':

        item_name = request.form.get('item_name', '').strip()
        expiry_date_input = request.form.get('expiry_date', '').strip()

        try:
            quantity = int(request.form.get('quantity', 0))

            if not item_name or not expiry_date_input or quantity < 0:
                flash("Please enter valid medicine details.", "error")
                return redirect(
                    url_for('edit_medicine', medicine_id=medicine.id)
                )

            expiry_date = datetime.strptime(
                expiry_date_input, '%Y-%m-%d'
            ).date()

            # Automatically calculate medicine status
            if expiry_date < date.today():
                status = "Expired"
            elif quantity == 0:
                status = "Out of Stock"
            else:
                status = "Available"

            medicine.item_name = item_name
            medicine.quantity = quantity
            medicine.expiry_date = expiry_date
            medicine.status = status

            db.session.commit()

            flash("Medicine updated successfully!", "success")

            return redirect(
                url_for('hospital_interface') + '#inventory'
            )

        except ValueError:
            flash("Please enter valid medicine details.", "error")

        except Exception as e:
            db.session.rollback()
            print("Medicine Update Error:", e)
            flash("Unable to update medicine.", "error")

    return render_template(
        'edit_medicine.html',
        medicine=medicine
    )
@app.route('/delete_medicine/<int:medicine_id>', methods=['POST'])
@role_required('hospital')
def delete_medicine(medicine_id):

    hospital_id = session.get('hospital_id')

    medicine = MedicalInventory.query.filter_by(
        id=medicine_id,
        hospital_id=hospital_id
    ).first_or_404()

    try:
        db.session.delete(medicine)
        db.session.commit()

        flash("Medicine deleted successfully!", "success")

    except Exception as e:
        db.session.rollback()
        print("Medicine Deletion Error:", e)
        flash("Unable to delete medicine.", "error")

    return redirect(url_for('hospital_interface') + '#inventory')

@app.route('/edit_blood/<int:blood_id>', methods=['GET', 'POST'])
@role_required('hospital')
def edit_blood(blood_id):

    hospital_id = session.get('hospital_id')

    blood = BloodInventory.query.filter_by(
        id=blood_id,
        hospital_id=hospital_id
    ).first_or_404()

    if request.method == 'POST':

        blood_group = request.form.get('blood_group', '').strip().upper()

        try:
            available_units = int(request.form.get('available_units', 0))
            required_units = int(request.form.get('required_units', 0))

            if not blood_group or available_units < 0 or required_units < 0:
                flash("Please enter valid blood inventory details.", "error")
                return redirect(url_for('edit_blood', blood_id=blood.id))

            duplicate = BloodInventory.query.filter(
                BloodInventory.hospital_id == hospital_id,
                BloodInventory.blood_group == blood_group,
                BloodInventory.id != blood.id
            ).first()

            if duplicate:
                flash("This blood group already exists.", "error")
                return redirect(url_for('edit_blood', blood_id=blood.id))

            blood.blood_group = blood_group
            blood.available_units = available_units
            blood.required_units = required_units

            db.session.commit()

            flash("Blood inventory updated successfully!", "success")
            return redirect(url_for('hospital_interface') + '#blood-bank')

        except ValueError:
            flash("Please enter valid numerical values.", "error")

        except Exception as e:
            db.session.rollback()
            print("Blood Update Error:", e)
            flash("Unable to update blood inventory.", "error")

    return render_template('edit_blood.html', blood=blood)

@app.route('/delete_blood/<int:blood_id>', methods=['POST'])
@role_required('hospital')
def delete_blood(blood_id):

    hospital_id = session.get('hospital_id')

    blood = BloodInventory.query.filter_by(
        id=blood_id,
        hospital_id=hospital_id
    ).first_or_404()

    try:
        db.session.delete(blood)
        db.session.commit()

        flash("Blood inventory deleted successfully!", "success")

    except Exception as e:
        db.session.rollback()
        print("Blood Deletion Error:", e)
        flash("Unable to delete blood inventory.", "error")

    return redirect(url_for('hospital_interface') + '#blood-bank')


# ==========================================
# DELETE DOCTOR
# ==========================================

@app.route('/delete_doctor/<int:doctor_id>', methods=['POST'])
@role_required('hospital')
def delete_doctor(doctor_id):

    hospital_id = session.get('hospital_id')

    # Find doctor belonging to this hospital only
    doctor = Doctor.query.filter_by(
        id=doctor_id,
        hospital_id=hospital_id
    ).first_or_404()

    try:

        db.session.delete(doctor)

        db.session.commit()

        flash("Doctor deleted successfully!", "success")

    except Exception as e:

        db.session.rollback()

        print("Doctor Deletion Error:", e)

        flash("Unable to delete doctor.", "error")

    return redirect(url_for('hospital_interface') + '#doctors')

@app.route('/edit_doctor/<int:doctor_id>', methods=['GET', 'POST'])
@role_required('hospital')
def edit_doctor(doctor_id):

    hospital_id = session.get('hospital_id')

    # Find doctor belonging to the logged-in hospital only
    doctor = Doctor.query.filter_by(
        id=doctor_id,
        hospital_id=hospital_id
    ).first_or_404()

    if request.method == 'POST':

        name = request.form.get('name', '').strip()
        specialization = request.form.get('specialization', '').strip()
        shift = request.form.get('shift', '').strip()
        status = request.form.get('status', '').strip()

        if not name or not specialization or not shift or not status:
            flash("Please fill all doctor details.", "error")
            return redirect(url_for('edit_doctor', doctor_id=doctor.id))

        try:
            doctor.name = name
            doctor.specialization = specialization
            doctor.shift = shift
            doctor.status = status

            db.session.commit()

            flash("Doctor details updated successfully!", "success")

            return redirect(url_for('hospital_interface') + '#doctors')

        except Exception as e:
            db.session.rollback()
            print("Doctor Update Error:", e)
            flash("Unable to update doctor details.", "error")

    return render_template('edit_doctor.html', doctor=doctor)


# ==========================================
# CREATE AMBULANCE LOGIN ACCOUNT
# ==========================================

@app.route('/create_ambulance_account', methods=['POST'])
@role_required('hospital')
def create_ambulance_account():

    hospital_id = session.get('hospital_id')

    name = request.form.get('name', '').strip()
    mobile = request.form.get('mobile', '').strip()
    password = request.form.get('password', '')
    ambulance_id = request.form.get('ambulance_id', '').strip()

    # Basic validation
    if not name or not mobile or not password or not ambulance_id:
        flash("Please fill all ambulance account details.", "error")
        return redirect(url_for('hospital_interface'))

    if not mobile.isdigit() or len(mobile) != 10:
        flash("Enter a valid 10-digit mobile number.", "error")
        return redirect(url_for('hospital_interface'))

    if len(password) < 6:
        flash("Password must contain at least 6 characters.", "error")
        return redirect(url_for('hospital_interface'))

    # Check whether mobile number already exists
    existing_user = User.query.filter_by(mobile=mobile).first()

    if existing_user:
        flash("This mobile number is already registered.", "error")
        return redirect(url_for('hospital_interface'))

    # Verify ambulance belongs to this hospital
    ambulance = Ambulance.query.filter_by(
        id=ambulance_id,
        hospital_id=hospital_id
    ).first()

    if not ambulance:
        flash("Invalid ambulance selection.", "error")
        return redirect(url_for('hospital_interface'))

    try:

        new_user = User(
            name=name,
            mobile=mobile,
            password=generate_password_hash(password),
            role='ambulance',
            hospital_id=hospital_id,
            ambulance_id=ambulance.id
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Ambulance login account created successfully!", "success")

    except Exception as e:

        db.session.rollback()

        print("Ambulance Account Creation Error:", e)

        flash("Unable to create ambulance account.", "error")

    return redirect(url_for('hospital_interface'))


@app.route('/ambulance')
@app.route('/ambulance_hud.html')
@role_required('ambulance')
def ambulance_interface():

    ambulance_id = session.get('ambulance_id')
    hospital_id = session.get('hospital_id')

    # Ensure the account has an assigned ambulance
    if not ambulance_id:
        flash("No ambulance has been assigned to this account.", "error")
        return redirect(url_for('logout'))

    # Fetch only the assigned ambulance
    ambulance = Ambulance.query.filter_by(
        id=ambulance_id,
        hospital_id=hospital_id
    ).first_or_404()

    return render_template(
        'ambulance.html',
        ambulance=ambulance
    )

# ==========================================
# UPDATE AMBULANCE STATUS
# ==========================================


@app.route('/update_ambulance_status', methods=['POST'])
@role_required('ambulance')
def update_ambulance_status():

    ambulance_id = session.get('ambulance_id')
    hospital_id = session.get('hospital_id')

    ambulance = Ambulance.query.filter_by(
        id=ambulance_id,
        hospital_id=hospital_id
    ).first_or_404()

    new_status = request.form.get('status', '').strip()

    allowed_statuses = [
        'Available',
        'En Route',
        'Maintenance',
        'Out of Service'
    ]

    if new_status not in allowed_statuses:
        flash("Invalid ambulance status.", "error")
        return redirect(url_for('ambulance_interface'))

    try:

        # Update operational status
        ambulance.status = new_status

        # Update selected medical equipment
        selected_equipment = request.form.getlist('medical_equipment')
        ambulance.medical_equipment = ', '.join(selected_equipment)

        # Update medical supplies
        ambulance.medical_supplies = request.form.get(
            'medical_supplies', ''
        ).strip()

        db.session.commit()

        flash(
            "Ambulance status, equipment and supplies updated successfully!",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print("Ambulance Update Error:", e)

        flash("Unable to update ambulance information.", "error")

    return redirect(url_for('ambulance_interface'))



@app.route('/drone')
@app.route('/drone_telemetry.html')
@role_required('drone')
def drone_telemetry():

    return render_template('drone_telemetry.html')



if __name__ == '__main__':
    app.run(debug=True)


