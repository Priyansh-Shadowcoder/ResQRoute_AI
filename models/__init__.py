from flask_sqlalchemy import SQLAlchemy
from datetime import datetime



db = SQLAlchemy()


# ==========================================
# USER MODEL
# ==========================================

class User(db.Model):

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    mobile = db.Column(db.String(10), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(30), nullable=False)

    hospital_id = db.Column(
        db.Integer,
        db.ForeignKey('hospitals.id'),
        nullable=True
    )

    hospital = db.relationship('Hospital')
    ambulance_id = db.Column(db.Integer, db.ForeignKey('ambulances.id'), nullable=True)
    ambulance = db.relationship('Ambulance')

# ==========================================
# HOSPITAL MODEL
# ==========================================

class Hospital(db.Model):

    __tablename__ = 'hospitals'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)

    location = db.Column(db.String(200))

    total_beds = db.Column(db.Integer, default=0)

    available_beds = db.Column(db.Integer, default=0)

    emergency_bays = db.Column(db.Integer, default=0)

    oxygen_percentage = db.Column(db.Float, default=100)

    contact = db.Column(db.String(15))


# ==========================================
# AMBULANCE MODEL
# ==========================================

class Ambulance(db.Model):

    __tablename__ = 'ambulances'

    id = db.Column(db.Integer, primary_key=True)

    vehicle_number = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )

    driver_id = db.Column(db.String(50), nullable=False)

    hospital_id = db.Column(
        db.Integer,
        db.ForeignKey('hospitals.id')
    )

    status = db.Column(db.String(50))

    medical_equipment = db.Column(db.Text)

    medical_supplies = db.Column(db.Text)

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    hospital = db.relationship(
        'Hospital',
        backref='ambulances'
    )


# ==========================================
# DRONE MODEL
# ==========================================

class Drone(db.Model):

    __tablename__ = 'drones'

    id = db.Column(db.Integer, primary_key=True)

    drone_id = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    operator_name = db.Column(db.String(100))

    dgca_number = db.Column(db.String(100))

    operational_status = db.Column(db.String(50))

    battery_percentage = db.Column(db.Float, default=100)

    altitude = db.Column(db.Float, default=0)

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

# ==========================================
# DOCTOR MODEL
# ==========================================

class Doctor(db.Model):

    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    specialization = db.Column(db.String(100))

    shift = db.Column(db.String(30))

    status = db.Column(db.String(30), default="Available")

    hospital_id = db.Column(
        db.Integer,
        db.ForeignKey('hospitals.id'),
        nullable=False
    )

    hospital = db.relationship(
        'Hospital',
        backref='doctors'
    )


# ==========================================
# BLOOD INVENTORY MODEL
# ==========================================

class BloodInventory(db.Model):

    __tablename__ = 'blood_inventory'

    id = db.Column(db.Integer, primary_key=True)

    blood_group = db.Column(db.String(5), nullable=False)

    available_units = db.Column(db.Integer, default=0)

    required_units = db.Column(db.Integer, default=0)

    hospital_id = db.Column(
        db.Integer,
        db.ForeignKey('hospitals.id'),
        nullable=False
    )

    hospital = db.relationship(
        'Hospital',
        backref='blood_inventory'
    )

    __table_args__ = (
        db.UniqueConstraint(
            'hospital_id',
            'blood_group',
            name='unique_hospital_blood_group'
        ),
    )


# ==========================================
# MEDICAL INVENTORY MODEL
# ==========================================

class MedicalInventory(db.Model):

    __tablename__ = 'medical_inventory'

    id = db.Column(db.Integer, primary_key=True)

    item_name = db.Column(db.String(150), nullable=False)

    quantity = db.Column(db.Integer, default=0)

    expiry_date = db.Column(db.Date)

    status = db.Column(db.String(30), default="Available")

    hospital_id = db.Column(
        db.Integer,
        db.ForeignKey('hospitals.id'),
        nullable=False
    )

    hospital = db.relationship(
        'Hospital',
        backref='medical_inventory'
    )


# ==========================================
# EMERGENCY EQUIPMENT MODEL
# ==========================================

class Equipment(db.Model):

    __tablename__ = 'equipment'

    id = db.Column(db.Integer, primary_key=True)

    equipment_name = db.Column(db.String(150), nullable=False)

    total_quantity = db.Column(db.Integer, default=0)

    available_quantity = db.Column(db.Integer, default=0)

    hospital_id = db.Column(
        db.Integer,
        db.ForeignKey('hospitals.id'),
        nullable=False
    )

    hospital = db.relationship(
        'Hospital',
        backref='equipment'
    )


# ==========================================
# EMERGENCY REQUEST MODEL
# ==========================================

class EmergencyRequest(db.Model):

    __tablename__ = 'emergency_requests'

    id = db.Column(db.Integer, primary_key=True)

    patient_name = db.Column(db.String(100))

    emergency_type = db.Column(db.String(100), nullable=False)

    priority = db.Column(db.String(30), default="Normal")

    pickup_location = db.Column(db.String(250), nullable=False)

    destination = db.Column(db.String(250))

    contact_number = db.Column(db.String(15))

    status = db.Column(db.String(50), default="Pending")

    hospital_id = db.Column(
        db.Integer,
        db.ForeignKey('hospitals.id')
    )

    ambulance_id = db.Column(
        db.Integer,
        db.ForeignKey('ambulances.id')
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    hospital = db.relationship('Hospital')

    ambulance = db.relationship('Ambulance')


# ==========================================
# DRONE MISSION MODEL
# ==========================================

class DroneMission(db.Model):

    __tablename__ = 'drone_missions'

    id = db.Column(db.Integer, primary_key=True)

    drone_id = db.Column(
        db.Integer,
        db.ForeignKey('drones.id'),
        nullable=False
    )

    ambulance_id = db.Column(
        db.Integer,
        db.ForeignKey('ambulances.id')
    )

    target_junction = db.Column(db.String(200))

    selected_route = db.Column(db.String(250))

    altitude = db.Column(db.Float)

    battery_at_launch = db.Column(db.Float)

    mission_status = db.Column(
        db.String(50),
        default="Pending"
    )

    started_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    completed_at = db.Column(db.DateTime)

    drone = db.relationship(
        'Drone',
        backref='missions'
    )

    ambulance = db.relationship('Ambulance')


# ==========================================
# ROUTE HISTORY MODEL
# ==========================================

class RouteHistory(db.Model):

    __tablename__ = 'route_history'

    id = db.Column(db.Integer, primary_key=True)

    ambulance_id = db.Column(
        db.Integer,
        db.ForeignKey('ambulances.id'),
        nullable=False
    )

    emergency_id = db.Column(
        db.Integer,
        db.ForeignKey('emergency_requests.id')
    )

    source_location = db.Column(db.String(250))

    destination = db.Column(db.String(250))

    selected_route = db.Column(db.Text)

    distance_km = db.Column(db.Float)

    estimated_time_minutes = db.Column(db.Float)

    actual_time_minutes = db.Column(db.Float)

    optimization_algorithm = db.Column(
        db.String(100),
        default="OR-Tools"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    ambulance = db.relationship('Ambulance')

    emergency = db.relationship('EmergencyRequest')
