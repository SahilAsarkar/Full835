import os, sys, subprocess

def main():
    print("==========================================================")
    print("   OneSmarter Admin Portal — Django + React Stack         ")
    print("==========================================================")
    print("Backend:  Django REST Framework (http://127.0.0.1:8000)")
    print("Frontend: React Vite SPA (http://127.0.0.1:3000)")
    print("Database: PostgreSQL / SQLite (data/onesmarter_django.db)")
    print("==========================================================")
    
    os.chdir(os.path.join(os.path.dirname(__file__), 'django_backend'))
    subprocess.run([sys.executable, 'manage.py', 'runserver', '127.0.0.1:8000'])

if __name__ == '__main__':
    main()
