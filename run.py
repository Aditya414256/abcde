import os
from backend.app import create_app
from backend.seed import seed_database

app = create_app()

if __name__ == '__main__':
    if os.environ.get('SEED_DEMO_DATA') == '1' and not os.environ.get('VERCEL') and os.environ.get('FLASK_ENV') != 'production':
        with app.app_context():
            seed_database()

    port = int(os.environ.get('PORT', 5000))
    print(f"Starting MediFind server on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG') == '1' and not os.environ.get('VERCEL') and os.environ.get('FLASK_ENV') != 'production')
