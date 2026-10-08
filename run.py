import os
from backend.app import create_app
from backend.seed import seed_database

app = create_app()

if __name__ == '__main__':
    # Ensure database is seeded on start
    with app.app_context():
        seed_database()

    port = int(os.environ.get('PORT', 5000))
    print(f"Starting MediFind server on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
