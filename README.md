# MediFind — Medicine Availability & Verified Pharmacy Locator

MediFind is a full-stack healthcare web application that bridges customers and verified local pharmacies. Customers can search for medicines via autocomplete, find verified local pharmacies with real-time inventory, and choose between automated **Store Pickup** (auto-locates nearest eligible pharmacy with stock) and **Home Delivery**.

---

## 🌟 Key Features

### 1. Customer Medicine Search & Discovery
* **Home Page Live Autocomplete**: Fast, case-insensitive autocomplete suggestions querying the database catalogue.
* **Simplified Decision Flow**: Clean 2-choice ordering screen: **Take From Store** vs **Take From Delivery**.
* **Store Pickup (Automated Selection)**:
  * Uses browser GPS coordinates and the Haversine formula.
  * Automatically filters pharmacies that are **Active**, **Admin-Approved / Verified**, **Pickup-Enabled**, and have **Sufficient Stock**.
  * Selects the nearest store automatically — no manual store browsing required.
* **Home Delivery**:
  * Lists active, verified, delivery-enabled pharmacies showing name and distance.
  * Dedicated delivery checkout form with address, contact details, quantity, and optional prescription attachment.

### 2. Pharmacy Portal
* **Real-time Order Processing**: Manage incoming Store Pickup and Home Delivery orders.
* **Strict Order State Machine**:
  `PENDING` ➔ `ACCEPTED` ➔ `CONFIRMED` ➔ `PREPARING` ➔ `READY_FOR_PICKUP` / `OUT_FOR_DELIVERY` ➔ `COMPLETED`.
* **Stock & Inventory Control**: Update quantity, price, batch numbers, and expiry dates with automatic stock status recalculation (`AVAILABLE`, `LOW_STOCK`, `OUT_OF_STOCK`).
* **Prescription Review**: Authorized manual human review for uploaded prescription documents.

### 3. Admin Verification Portal
* **Pharmacy Licensure Review**: Admin reviews pharmacy store names and Drug License numbers.
* **Approve / Reject Verification**: Only verified pharmacies are exposed to customer searches and ordering.
* **Store Activation**: Instantly toggle pharmacy active/inactive status.
* **Platform Metrics**: View total pharmacies, pending verifications, verified stores, and order volume.

### 4. Safety & Security
* Non-negative stock enforcement with transactional stock decrements.
* Automatic inventory restoration on order cancellation or rejection.
* Protected prescription storage (not publicly exposed).
* Role-based server-side authentication (Customer, Pharmacy, Admin) with Flask-Login and password hashing.

---

## 🛠️ Technology Stack

* **Frontend**: HTML5, Vanilla CSS3, Vanilla JavaScript (ES6+)
* **Backend**: Python 3, Flask, Flask-Login, Flask-SQLAlchemy, Werkzeug
* **Database**: SQLite (built-in default) / MySQL production-ready
* **Testing**: Pytest

---

## 🚀 Getting Started

### 1. Prerequisites
* Python 3.10+ installed

### 2. Install Dependencies
```bash
pip install flask flask-login flask-sqlalchemy werkzeug pytest
```

### 3. Run the Application
```bash
python run.py
```
The server will start at:
👉 **`http://127.0.0.1:5000`**

The database (`medifind.db`) is automatically seeded with verified pharmacies, medicines, and inventory on first run.

---

## 🧪 Running Tests

Execute the automated test suite with pytest:
```bash
python -m pytest tests/test_medifind.py -v
```

All 8 test suites validate:
* Haversine distance calculations
* Autocomplete & catalogue search
* Non-negative inventory rules & status updates
* Pharmacy registration and admin approval flow
* Order creation, stock decrement, state machine & cancellation stock restoration
* Auto-nearest pharmacy selection for store pickup
* Delivery pharmacy distance listing
* Client REST API integration

---

## 👥 Demo Accounts for Testing

| Role | Email | Password | Details |
| :--- | :--- | :--- | :--- |
| **Customer** | `customer@example.com` | `customer123` | Aditya Sharma / Pratik Kasar |
| **Ram Medical** | `ram@pharmacy.com` | `pharmacy123` | Pitreshwer Colony, Shirpur (098238 63004) |
| **Shree Ji Medical** | `shreeji@pharmacy.com` | `pharmacy123` | Hira Nagar, Shirpur (098238 63004) |
| **Tasir Medical** | `tasir@pharmacy.com` | `pharmacy123` | Ganesh Colony, Shirpur (075587 31868) |
| **Shree Gangai Medical** | `gangai@pharmacy.com` | `pharmacy123` | Swami Vivekanand Nagar, Shirpur (077981 04626) |
| **Admin** | `admin@medifind.com` | `admin123` | Platform Administrator |

---

## 📁 Project Structure

```
├── backend/
│   ├── routes/              # API blueprints (auth, medicines, orders, pharmacy, admin)
│   ├── services/            # Business logic (Location, Medicine, Order, Inventory, etc.)
│   ├── config.py            # App & upload configuration
│   ├── database.py          # SQLAlchemy instance
│   ├── models.py            # SQLAlchemy database models
│   ├── seed.py              # Realistic catalogue & verified pharmacy seed script
│   └── app.py               # Flask application factory
├── frontend/
│   ├── js/                  # Frontend modular JavaScript (API, Auth, Search, Selection, Portals)
│   ├── HomePage.html / .css
│   ├── FindMedi.html / .css
│   ├── Pharmacies.html / .css
│   ├── login.html / .css
│   ├── register*.html / .css
│   ├── pharmacy-dashboard.html
│   └── admin-dashboard.html
├── tests/
│   └── test_medifind.py     # Automated Pytest suite
├── run.py                   # Application entry point
├── .gitignore
└── README.md
```
