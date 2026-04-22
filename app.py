from flask import Flask, render_template, request, session, redirect, url_for, flash, Response
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error
import hashlib
import secrets
import random
import string
from functools import wraps
import qrcode
import io
import os

# UPI Payment Config
UPI_ID = 'makwanarahul0021@okicici'
UPI_NAME = 'CarRental'

app = Flask(__name__)
app.secret_key = 'car-rental-secret-key-2024!@#$%'
app.permanent_session_lifetime = timedelta(days=7)

# Add context processor to make 'now' available in all templates
@app.context_processor
def utility_processor():
    def get_image_url(image_path):
        """Helper function to generate proper image URLs"""
        if not image_path:
            return None
        
        # If it's already a full URL
        if image_path.startswith('http://') or image_path.startswith('https://'):
            return image_path
        
        # Clean the path
        clean_path = image_path.strip()
        
        # Handle different path formats
        if clean_path.startswith('/static/'):
            clean_path = clean_path.replace('/static/', '')
        elif clean_path.startswith('static/'):
            clean_path = clean_path.replace('static/', '')
        elif clean_path.startswith('images/'):
            pass  # Already has images/ prefix
        else:
            # Assume it's just a filename, add images/ prefix
            clean_path = f'images/{clean_path}'
        
        return url_for('static', filename=clean_path)
    
    return dict(now=datetime.now, get_image_url=get_image_url)

# Add date filter for templates
@app.template_filter('date_only')
def date_only_filter(value):
    """Convert datetime to YYYY-MM-DD string"""
    if value:
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d')
        return str(value)[:10]
    return '-'

# Add number formatting filter for templates
@app.template_filter('format_number')
def format_number_filter(value):
    """Format large numbers with commas"""
    if value is None:
        return '0'
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)

# MySQL Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234567',
    'database': 'car_rental_db'
}

# Database connection function
def get_db():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

# Execute query function with better error handling
def execute_query(query, params=None, fetchone=False, fetchall=False):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        
        if fetchone:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()
        else:
            conn.commit()
            result = cursor.lastrowid
        
        return result
    except Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

# Generate transaction ID
def generate_transaction_id():
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_num = random.randint(100, 999)
    return f"TXN{timestamp}{random_num:03d}"

# Initialize database and create tables
def init_db():
    # First create database if not exists
    try:
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password']
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']}")
        cursor.close()
        conn.close()
        print("[OK] Database created/verified successfully")
    except Error as e:
        print(f"[ERROR] Error creating database: {e}")
        return
    
    # Create tables
    try:
        # Users table
        execute_query('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                full_name VARCHAR(100),
                phone VARCHAR(20),
                role ENUM('USER', 'ADMIN') DEFAULT 'USER',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("[OK] Users table created")
        
        # Vehicles table with enhanced columns
        execute_query('''
            CREATE TABLE IF NOT EXISTS vehicles (
                vehicle_id INT AUTO_INCREMENT PRIMARY KEY,
                model VARCHAR(100) NOT NULL,
                year INT NOT NULL,
                type VARCHAR(50) NOT NULL,
                daily_rate INT NOT NULL,
                location VARCHAR(100) NOT NULL,
                availability BOOLEAN DEFAULT TRUE,
                image_url VARCHAR(255),
                description TEXT,
                fuel_type VARCHAR(50) DEFAULT 'Petrol',
                transmission VARCHAR(50) DEFAULT 'Manual',
                seating_capacity INT DEFAULT 5,
                km_driven INT DEFAULT 0,
                variant VARCHAR(100),
                engine_cc VARCHAR(20),
                mileage VARCHAR(20),
                color VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("[OK] Vehicles table created")
        
        # Bookings table
        execute_query('''
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                vehicle_id INT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                total_days INT NOT NULL,
                total_price INT NOT NULL,
                payment_method VARCHAR(50),
                payment_status VARCHAR(20) DEFAULT 'PENDING',
                booking_status VARCHAR(20) DEFAULT 'PENDING',
                booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id) ON DELETE CASCADE
            )
        ''')
        print("[OK] Bookings table created")
        
        # Payments table
        execute_query('''
            CREATE TABLE IF NOT EXISTS payments (
                payment_id INT AUTO_INCREMENT PRIMARY KEY,
                booking_id INT NOT NULL UNIQUE,
                amount INT NOT NULL,
                payment_method VARCHAR(50) NOT NULL,
                status VARCHAR(20) DEFAULT 'PENDING',
                transaction_id VARCHAR(100),
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (booking_id) REFERENCES bookings(booking_id) ON DELETE CASCADE
            )
        ''')
        print("[OK] Payments table created")
        
        # Insert admin user if not exists
        admin = execute_query("SELECT * FROM users WHERE username = 'admin'", fetchone=True)
        if not admin:
            execute_query('''
                INSERT INTO users (username, password, email, full_name, role) 
                VALUES (%s, %s, %s, %s, %s)
            ''', ('admin', hash_password('admin123'), 'admin@carrental.com', 'System Admin', 'ADMIN'))
            print("[OK] Admin user created")
        
        # Insert sample vehicles if none exist
        vehicles = execute_query("SELECT COUNT(*) as count FROM vehicles", fetchone=True)
        if vehicles and vehicles['count'] == 0:
            sample_vehicles = [
                # Sedans
                ('Toyota Camry', 2024, 'Sedan', 5500, 'Mumbai', 1, 'images/camry.png', 'The Toyota Camry offers a perfect blend of luxury, comfort, and reliability. Features include leather seats, sunroof, premium sound system, and advanced safety features.', 'Petrol', 'Automatic', 5, 15000, 'VX', '2487cc', '15 km/l', 'White'),
                ('Honda City', 2023, 'Sedan', 4200, 'Delhi', 1, 'images/honda_city.png', 'Honda City is a premium sedan known for its spacious interior, smooth ride, and excellent fuel efficiency. Perfect for long drives and business trips.', 'Petrol', 'CVT', 5, 25000, 'ZX', '1498cc', '18 km/l', 'Silver'),
                ('Hyundai Verna', 2024, 'Sedan', 4000, 'Bangalore', 1, 'images/verna.png', 'Hyundai Verna comes with a powerful engine, stylish design, and loaded with features like ventilated seats, Bose sound system, and blue link connected car technology.', 'Diesel', 'Automatic', 5, 10000, 'SX Opt', '1493cc', '22 km/l', 'Phantom Black'),
                ('Skoda Slavia', 2023, 'Sedan', 4800, 'Pune', 1, 'images/slavia.png', 'European engineering meets Indian roads. The Skoda Slavia offers excellent build quality, powerful turbo engine, and a spacious cabin with premium finishes.', 'Petrol', 'DSG', 5, 8000, 'Style', '999cc', '19 km/l', 'Carbon Steel'),
                # SUVs
                ('Toyota Fortuner', 2024, 'SUV', 12000, 'Mumbai', 1, 'images/fortuner.png', 'The legendary Toyota Fortuner - a powerful and rugged SUV perfect for off-road adventures and family trips. Features 4x4 capability, 7 seats, and premium interior.', 'Diesel', 'Automatic', 7, 35000, 'Legender', '2755cc', '14 km/l', 'Pearl White'),
                ('Hyundai Creta', 2024, 'SUV', 6500, 'Delhi', 1, 'images/creta.png', 'India\'s favorite compact SUV. The Hyundai Creta offers a perfect balance of style, comfort, and performance. Features include panoramic sunroof, ventilated seats, and advanced safety.', 'Diesel', 'Automatic', 5, 18000, 'SX Plus', '1493cc', '21 km/l', 'Titan Grey'),
                ('Kia Seltos', 2023, 'SUV', 6200, 'Bangalore', 1, 'images/seltos.png', 'The Kia Seltos is a feature-packed SUV with striking design and powerful engine options. Includes 10.25-inch touchscreen, Bose speakers, and UVO connected car tech.', 'Petrol', 'DCT', 5, 22000, 'GTX+', '1353cc', '16 km/l', 'Glacier White Pearl'),
                ('Mahindra Scorpio N', 2023, 'SUV', 7000, 'Chennai', 1, 'images/scorpio.png', 'Built tough for Indian roads. The Mahindra Scorpio N offers commanding road presence, powerful diesel engine, and 7-seater configuration. Perfect for family adventures.', 'Diesel', 'Manual', 7, 15000, 'Z8 L', '2184cc', '15 km/l', 'Napoli Black'),
                ('MG Hector', 2024, 'SUV', 5800, 'Pune', 1, 'images/hector.png', 'The MG Hector is a tech-loaded SUV with India\'s largest touchscreen, AI assistant, and panoramic sunroof. Spacious interior and comfortable ride quality.', 'Petrol', 'CVT', 5, 12000, 'Sharp', '1451cc', '15 km/l', 'Aurora Silver'),
                # Electric Cars
                ('Tesla Model 3', 2024, 'Electric', 8500, 'Bangalore', 1, 'images/tesla.png', 'Experience the future with Tesla Model 3. Features include autopilot, 500km+ range, 0-100 in 3.3 seconds, premium interior, and over-the-air updates.', 'Electric', 'Automatic', 5, 5000, 'Long Range', 'N/A', '500 km/charge', 'Red Multi-Coat'),
                ('MG ZS EV', 2023, 'Electric', 5500, 'Mumbai', 1, 'images/zsev.png', 'MG ZS EV is a practical electric SUV with 461km range, fast charging capability, and premium features like panoramic sunroof and digital cockpit.', 'Electric', 'Automatic', 5, 8000, 'Excite Pro', 'N/A', '461 km/charge', 'Curry Yellow'),
                ('Tata Nexon EV', 2024, 'Electric', 4500, 'Delhi', 1, 'images/nexonev.png', 'India\'s best-selling electric car. The Tata Nexon EV offers great range, zippy performance, and excellent value for money. Perfect for city commutes.', 'Electric', 'Automatic', 5, 10000, 'Prime', 'N/A', '312 km/charge', 'Teal Blue'),
                # Hatchbacks
                ('Maruti Suzuki Baleno', 2024, 'Hatchback', 2800, 'Mumbai', 1, 'images/baleno.png', 'The premium hatchback from Maruti Suzuki. The Baleno offers a spacious cabin, excellent fuel efficiency, and modern features like heads-up display.', 'Petrol', 'Manual', 5, 5000, 'Alpha', '1197cc', '23 km/l', 'Nexa Blue'),
                ('Hyundai i20', 2023, 'Hatchback', 3000, 'Chennai', 1, 'images/i20.png', 'Hyundai i20 is a stylish and feature-rich premium hatchback. Comes with Bose sound system, sunroof, and ventilated seats - a segment first.', 'Petrol', 'DCT', 5, 12000, 'Sportz', '1197cc', '20 km/l', 'Fiery Red'),
                # MPV
                ('Toyota Innova Crysta', 2023, 'MPV', 8000, 'Pune', 1, 'images/innova.png', 'The king of MPVs - Toyota Innova Crysta offers unmatched comfort, reliability, and space for 7-8 passengers. Perfect for family trips and airport transfers.', 'Diesel', 'Automatic', 8, 45000, 'ZX', '2393cc', '14 km/l', 'Super White')
            ]
            for vehicle in sample_vehicles:
                execute_query('''
                    INSERT INTO vehicles (model, year, type, daily_rate, location, availability, image_url, description, fuel_type, transmission, seating_capacity, km_driven, variant, engine_cc, mileage, color) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', vehicle)
            print("[OK] 15 sample vehicles created")
            
    except Exception as e:
        print(f"[ERROR] Error creating tables: {e}")

# Initialize database
init_db()

app = Flask(__name__)
@app.route('/')
def index():
    return render_template('index.html')

# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Access denied. Admin only.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    vehicles = execute_query('''
        SELECT * FROM vehicles WHERE availability = TRUE 
        ORDER BY created_at DESC LIMIT 10
    ''', fetchall=True)
    return render_template('index.html', vehicles=vehicles)

@app.route('/vehicles')
def vehicles():
    vehicle_type = request.args.get('type', '')
    location = request.args.get('location', '')
    min_price = request.args.get('min_price', 0, type=int)
    max_price = request.args.get('max_price', 1000, type=int)
    
    query = "SELECT * FROM vehicles WHERE availability = TRUE"
    params = []
    
    if vehicle_type:
        query += " AND type = %s"
        params.append(vehicle_type)
    if location:
        query += " AND location = %s"
        params.append(location)
    if min_price:
        query += " AND daily_rate >= %s"
        params.append(min_price)
    if max_price < 1000:
        query += " AND daily_rate <= %s"
        params.append(max_price)
    
    query += " ORDER BY created_at DESC"
    
    vehicles = execute_query(query, params, fetchall=True)
    
    types = execute_query("SELECT DISTINCT type FROM vehicles ORDER BY type", fetchall=True)
    locations = execute_query("SELECT DISTINCT location FROM vehicles ORDER BY location", fetchall=True)
    
    return render_template('vehicles.html', vehicles=vehicles, types=types, locations=locations)

@app.route('/vehicle/<int:vehicle_id>')
def vehicle_detail(vehicle_id):
    vehicle = execute_query('SELECT * FROM vehicles WHERE vehicle_id = %s', (vehicle_id,), fetchone=True)
    if not vehicle:
        flash('Vehicle not found', 'danger')
        return redirect(url_for('vehicles'))
    return render_template('vehicle_detail.html', vehicle=vehicle)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = request.form.get('remember', False)
        
        user = execute_query("SELECT * FROM users WHERE username = %s", (username,), fetchone=True)
        
        if user:
            if verify_password(password, user['password']):
                session.permanent = remember
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['full_name'] = user['full_name']
                session['is_admin'] = (user['role'] == 'ADMIN')
                
                flash(f'Welcome back, {user["full_name"] or user["username"]}!', 'success')
                
                if user['role'] == 'ADMIN':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('index'))
            else:
                flash('Invalid password', 'danger')
        else:
            flash('Username not found', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        email = request.form['email']
        full_name = request.form['full_name']
        phone = request.form['phone']
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        existing = execute_query('SELECT * FROM users WHERE username = %s OR email = %s', 
                                (username, email), fetchone=True)
        if existing:
            flash('Username or email already exists', 'danger')
            return render_template('register.html')
        
        hashed_password = hash_password(password)
        execute_query('''
            INSERT INTO users (username, password, email, full_name, phone, role) 
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (username, hashed_password, email, full_name, phone, 'USER'))
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/book/<int:vehicle_id>', methods=['GET', 'POST'])
@login_required
def book_vehicle(vehicle_id):
    vehicle = execute_query('SELECT * FROM vehicles WHERE vehicle_id = %s', (vehicle_id,), fetchone=True)
    
    if not vehicle or not vehicle['availability']:
        flash('Vehicle not available', 'danger')
        return redirect(url_for('vehicles'))
    
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        total_days = (end - start).days
        total_price = total_days * vehicle['daily_rate']
        
        if total_days <= 0:
            flash('End date must be after start date', 'danger')
            return render_template('book.html', vehicle=vehicle)
        
        existing = execute_query('''
            SELECT * FROM bookings WHERE vehicle_id = %s 
            AND booking_status IN ('PENDING', 'CONFIRMED')
            AND ((start_date BETWEEN %s AND %s) OR (end_date BETWEEN %s AND %s))
        ''', (vehicle_id, start_date, end_date, start_date, end_date), fetchone=True)
        
        if existing:
            flash('Vehicle not available for selected dates', 'danger')
            return render_template('book.html', vehicle=vehicle)
        
        session['temp_booking'] = {
            'vehicle_id': vehicle_id,
            'vehicle_name': vehicle['model'],
            'start_date': start_date,
            'end_date': end_date,
            'total_days': total_days,
            'total_price': total_price
        }
        
        return redirect(url_for('payment'))
    
    return render_template('book.html', vehicle=vehicle)

@app.route('/generate_qr/<int:amount>')
@login_required
def generate_qr(amount):
    upi_url = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&cu=INR"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return Response(buffer.getvalue(), mimetype='image/png')

@app.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    if 'temp_booking' not in session:
        flash('No booking in progress', 'warning')
        return redirect(url_for('vehicles'))
    
    booking = session['temp_booking']
    
    if request.method == 'POST':
        upi_ref = request.form.get('upi_ref', '').strip()
        
        booking_id = execute_query('''
            INSERT INTO bookings (user_id, vehicle_id, start_date, end_date, total_days, total_price, payment_method, booking_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (session['user_id'], booking['vehicle_id'], booking['start_date'], 
              booking['end_date'], booking['total_days'], booking['total_price'], 
              'UPI', 'PENDING'))
        
        transaction_id = upi_ref if upi_ref else generate_transaction_id()
        execute_query('''
            INSERT INTO payments (booking_id, amount, payment_method, status, transaction_id)
            VALUES (%s, %s, %s, %s, %s)
        ''', (booking_id, booking['total_price'], 'UPI', 'SUCCESS', transaction_id))
        
        flash('Booking submitted! Payment will be verified by admin.', 'success')
        session.pop('temp_booking', None)
        return redirect(url_for('my_bookings'))
    
    return render_template('payment.html', booking=booking, upi_id=UPI_ID)

@app.route('/my-bookings')
@login_required
def my_bookings():
    bookings = execute_query('''
        SELECT b.*, v.model, v.type, v.daily_rate,
               p.payment_method, p.status as payment_status, p.transaction_id
        FROM bookings b
        JOIN vehicles v ON b.vehicle_id = v.vehicle_id
        LEFT JOIN payments p ON b.booking_id = p.booking_id
        WHERE b.user_id = %s
        ORDER BY b.booking_id DESC
    ''', (session['user_id'],), fetchall=True)
    
    return render_template('my_bookings.html', bookings=bookings)

@app.route('/cancel-booking/<int:booking_id>')
@login_required
def cancel_booking(booking_id):
    execute_query('''
        UPDATE bookings SET booking_status='CANCELLED' 
        WHERE booking_id=%s AND user_id=%s AND booking_status='PENDING'
    ''', (booking_id, session['user_id']))
    
    flash('Booking cancelled', 'success')
    return redirect(url_for('my_bookings'))

# Admin Routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = {
        'total_vehicles': execute_query('SELECT COUNT(*) as count FROM vehicles', fetchone=True)['count'],
        'available_vehicles': execute_query('SELECT COUNT(*) as count FROM vehicles WHERE availability=TRUE', fetchone=True)['count'],
        'total_users': execute_query('SELECT COUNT(*) as count FROM users', fetchone=True)['count'],
        'total_bookings': execute_query('SELECT COUNT(*) as count FROM bookings', fetchone=True)['count'],
        'pending_bookings': execute_query('SELECT COUNT(*) as count FROM bookings WHERE booking_status="PENDING"', fetchone=True)['count'],
        'total_revenue': execute_query('SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE status="SUCCESS"', fetchone=True)['total']
    }
    
    recent_bookings = execute_query('''
        SELECT b.*, u.username, v.model 
        FROM bookings b
        JOIN users u ON b.user_id = u.user_id
        JOIN vehicles v ON b.vehicle_id = v.vehicle_id
        ORDER BY b.booking_id DESC LIMIT 5
    ''', fetchall=True)
    
    return render_template('admin/dashboard.html', stats=stats, recent_bookings=recent_bookings)

@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    status = request.args.get('status', '')
    
    query = '''
        SELECT b.*, u.username, u.full_name, u.email, u.phone,
               v.model, v.type, v.daily_rate,
               p.payment_method, p.status as payment_status, p.transaction_id
        FROM bookings b
        JOIN users u ON b.user_id = u.user_id
        JOIN vehicles v ON b.vehicle_id = v.vehicle_id
        LEFT JOIN payments p ON b.booking_id = p.booking_id
    '''
    
    if status:
        query += f" WHERE b.booking_status = '{status}'"
    
    query += " ORDER BY b.booking_id ASC"
    
    bookings = execute_query(query, fetchall=True)
    return render_template('admin/bookings.html', bookings=bookings)

@app.route('/admin/update-booking/<int:booking_id>', methods=['POST'])
@admin_required
def update_booking(booking_id):
    status = request.form['status']
    
    execute_query('UPDATE bookings SET booking_status=%s WHERE booking_id=%s', (status, booking_id))
    
    flash(f'Booking status updated to {status}', 'success')
    return redirect(url_for('admin_bookings'))

@app.route('/admin/vehicles')
@admin_required
def admin_vehicles():
    vehicles = execute_query('SELECT * FROM vehicles ORDER BY vehicle_id DESC', fetchall=True)
    return render_template('admin/vehicles.html', vehicles=vehicles)

@app.route('/admin/vehicles/add', methods=['GET', 'POST'])
@admin_required
def admin_add_vehicle():
    if request.method == 'POST':
        model = request.form['model']
        year = request.form['year']
        vehicle_type = request.form['type']
        daily_rate = request.form['daily_rate']
        location = request.form['location']
        description = request.form['description']
        image_url = request.form.get('image_url', '')
        
        # New fields
        variant = request.form.get('variant', '')
        fuel_type = request.form.get('fuel_type', 'Petrol')
        transmission = request.form.get('transmission', 'Manual')
        seating_capacity = request.form.get('seating_capacity', 5)
        km_driven = request.form.get('km_driven', 0)
        engine_cc = request.form.get('engine_cc', '')
        mileage = request.form.get('mileage', '')
        color = request.form.get('color', '')
        
        if not image_url:
            image_url = None
        
        execute_query('''
            INSERT INTO vehicles (model, year, type, daily_rate, location, description, image_url,
                                 variant, fuel_type, transmission, seating_capacity, km_driven, engine_cc, mileage, color)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (model, year, vehicle_type, daily_rate, location, description, image_url,
              variant, fuel_type, transmission, seating_capacity, km_driven, engine_cc, mileage, color))
        
        flash('Vehicle added successfully', 'success')
        return redirect(url_for('admin_vehicles'))
    
    return render_template('admin/add_vehicle.html')

@app.route('/admin/vehicles/edit/<int:vehicle_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_vehicle(vehicle_id):
    if request.method == 'POST':
        model = request.form['model']
        year = request.form['year']
        vehicle_type = request.form['type']
        daily_rate = request.form['daily_rate']
        location = request.form['location']
        availability = 1 if request.form.get('availability') else 0
        description = request.form['description']
        image_url = request.form.get('image_url', '').strip()
        
        # New fields
        variant = request.form.get('variant', '')
        fuel_type = request.form.get('fuel_type', 'Petrol')
        transmission = request.form.get('transmission', 'Manual')
        seating_capacity = request.form.get('seating_capacity', 5)
        km_driven = request.form.get('km_driven', 0)
        engine_cc = request.form.get('engine_cc', '')
        mileage = request.form.get('mileage', '')
        color = request.form.get('color', '')
        
        # If image_url is empty, preserve the existing image from the database
        if not image_url:
            existing = execute_query('SELECT image_url FROM vehicles WHERE vehicle_id=%s', (vehicle_id,), fetchone=True)
            image_url = existing['image_url'] if existing else None
        
        execute_query('''
            UPDATE vehicles SET model=%s, year=%s, type=%s, daily_rate=%s, 
            location=%s, availability=%s, description=%s, image_url=%s,
            variant=%s, fuel_type=%s, transmission=%s, seating_capacity=%s, 
            km_driven=%s, engine_cc=%s, mileage=%s, color=%s
            WHERE vehicle_id=%s
        ''', (model, year, vehicle_type, daily_rate, location, availability, description, image_url,
              variant, fuel_type, transmission, seating_capacity, km_driven, engine_cc, mileage, color, vehicle_id))
        
        flash('Vehicle updated successfully', 'success')
        return redirect(url_for('admin_vehicles'))
    
    vehicle = execute_query('SELECT * FROM vehicles WHERE vehicle_id=%s', (vehicle_id,), fetchone=True)
    return render_template('admin/edit_vehicle.html', vehicle=vehicle)

@app.route('/admin/vehicles/delete/<int:vehicle_id>')
@admin_required
def admin_delete_vehicle(vehicle_id):
    bookings = execute_query('SELECT COUNT(*) as count FROM bookings WHERE vehicle_id=%s', 
                           (vehicle_id,), fetchone=True)['count']
    
    if bookings > 0:
        flash('Cannot delete vehicle with existing bookings', 'danger')
    else:
        execute_query('DELETE FROM vehicles WHERE vehicle_id=%s', (vehicle_id,))
        flash('Vehicle deleted successfully', 'success')
    
    return redirect(url_for('admin_vehicles'))

@app.route('/admin/users')
@admin_required
def admin_users():
    users = execute_query('''
        SELECT u.*, 
               (SELECT COUNT(*) FROM bookings WHERE user_id=u.user_id) as total_bookings,
               (SELECT COALESCE(SUM(total_price),0) FROM bookings WHERE user_id=u.user_id AND booking_status="COMPLETED") as total_spent
        FROM users u
        ORDER BY u.user_id DESC
    ''', fetchall=True)
    
    return render_template('admin/users.html', users=users)

@app.route('/admin/toggle-role/<int:user_id>')
@admin_required
def toggle_role(user_id):
    if user_id == session['user_id']:
        flash('Cannot change your own role', 'danger')
        return redirect(url_for('admin_users'))
    
    user = execute_query('SELECT role FROM users WHERE user_id=%s', (user_id,), fetchone=True)
    new_role = 'ADMIN' if user['role'] == 'USER' else 'USER'
    
    execute_query('UPDATE users SET role=%s WHERE user_id=%s', (new_role, user_id))
    
    flash(f'User role updated to {new_role}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/reports')
@admin_required
def admin_reports():
    period = request.args.get('period', 'month')
    
    if period == 'year':
        revenue_data = execute_query(
            '''SELECT YEAR(p.payment_date) as label,
                   COUNT(*) as transaction_count,
                   COALESCE(SUM(p.amount), 0) as total_revenue
            FROM payments p
            WHERE p.status = "SUCCESS"
            GROUP BY YEAR(p.payment_date)
            ORDER BY label DESC
            LIMIT 10''',
            fetchall=True
        )
        report_title = "Yearly Revenue"
    else:
        month_format = '%Y-%m'
        revenue_data = execute_query(
            '''SELECT DATE_FORMAT(p.payment_date, %s) as label,
                   COUNT(*) as transaction_count,
                   COALESCE(SUM(p.amount), 0) as total_revenue
            FROM payments p
            WHERE p.status = "SUCCESS"
            GROUP BY DATE_FORMAT(p.payment_date, %s)
            ORDER BY label DESC
            LIMIT 12''',
            params=(month_format, month_format),
            fetchall=True
        )
        report_title = "Monthly Revenue"
    
    if not revenue_data:
        revenue_data = []
    
    for row in revenue_data:
        row['total_revenue'] = float(row.get('total_revenue', 0) or 0)
        row['transaction_count'] = int(row.get('transaction_count', 0) or 0)
        if period == 'month':
            try:
                dt = datetime.strptime(str(row['label']), '%Y-%m')
                row['label'] = dt.strftime('%B %Y')
            except (ValueError, TypeError):
                pass
        else:
            row['label'] = str(row['label'])
    
    popular_vehicles = execute_query('''
        SELECT v.model, v.type, COUNT(b.booking_id) as booking_count,
               COALESCE(SUM(p.amount), 0) as revenue
        FROM vehicles v
        LEFT JOIN bookings b ON v.vehicle_id = b.vehicle_id
        LEFT JOIN payments p ON b.booking_id = p.booking_id AND p.status = "SUCCESS"
        GROUP BY v.vehicle_id, v.model, v.type
        ORDER BY revenue DESC, booking_count DESC
        LIMIT 10
    ''', fetchall=True)
    
    if not popular_vehicles:
        popular_vehicles = []
    
    for row in popular_vehicles:
        row['revenue'] = float(row.get('revenue', 0) or 0)
        row['booking_count'] = int(row.get('booking_count', 0) or 0)
    
    return render_template('admin/reports.html', 
                         revenue_data=revenue_data,
                         popular_vehicles=popular_vehicles,
                         period=period,
                         report_title=report_title)

if __name__ == '__main__':
    app.run(debug=True)