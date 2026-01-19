
import sys
import os

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

from models.user import user_model

def add_admin():
    email = "admin@example.com"
    password = "admin123"
    name = "Admin User"
    role = "admin"

    print(f"Attempting to create admin user: {email}")

    # Check if user exists first to avoid error spam if running multiple times
    existing = user_model.find_by_email(email)
    if existing:
        print(f"User {email} already exists.")
        if existing.get('role') != 'admin':
            print("User exists but is not an admin. Updating role...")
            user_model.update_one({"id": existing["id"]}, {"$set": {"role": "admin", "status": "active"}})
            print("Role updated to admin.")
        else:
            print("User is already an admin.")
        return

    user, error = user_model.create_user(email, password, name, role=role)
    
    if error:
        print(f"Error creating user: {error}")
    else:
        print(f"Successfully created admin user: {user['email']} (ID: {user['id']})")
        # Ensure it's active
        user_model.approve_user(user['id'])
        print("User approved/activated.")

if __name__ == "__main__":
    add_admin()
