#!/usr/bin/env python3
import pymongo
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import bcrypt
from bson.objectid import ObjectId
import datetime
import uuid
import sys
import json
import random
import string

load_dotenv()

def connect_to_db():
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "opencanary_test")
    
    try:
        client = MongoClient(mongodb_uri)
        client.admin.command('ping')
        print(f"Connected to MongoDB at {mongodb_uri}")
        return client[db_name]
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        sys.exit(1)


def list_users(db):
    users = list(db.users.find())
    if not users:
        print("No users found.")
        return
    
    print("\n=== Users ===")
    for user in users:
        print(f"ID: {user['_id']}")
        print(f"Email: {user['email']}")
        print(f"Username: {user.get('username', 'N/A')}")
        print(f"Devices: {user.get('devices', [])}")
        print(f"Created: {user.get('created_at', 'N/A')}")
        print("-" * 30)

def add_user(db):
    email = input("Enter email: ")
    username = input("Enter username: ")
    password = input("Enter password: ")
    
    if db.users.find_one({"email": email}):
        print(f"User with email {email} already exists")
        return
    
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))
    
    user = {
        "email": email,
        "username": username,
        "password": hashed.decode('utf-8'),
        "devices": [],
        "created_at": datetime.datetime.now()
    }
    
    result = db.users.insert_one(user)
    print(f"User created with ID: {result.inserted_id}")

def list_devices(db):
    devices = list(db.devices.find())
    
    if devices:
        print("\n=== Devices ===")
        for device in devices:
            device_id = device.get('device_id')
            print(f"Device ID: {device_id}")
            print(f"Created: {device.get('created_at', 'N/A')}")
            print(f"Last seen: {device.get('last_seen', 'Never')}")
            print("-" * 30)
    
    if not devices:
        print("No devices found.")

def generate_device_id():
    return f"honeypot-{random.randint(1, 999)}"

def add_device(db):
    device_id = input("Enter device ID (leave empty to generate): ")
    if not device_id:
        device_id = generate_device_id()
        print(f"Generated device ID: {device_id}")
    
    if db.config.find_one({"device_id": device_id}):
        print(f"Device with ID {device_id} already exists in config")
        return
    
    users = list(db.users.find({}, {"_id": 1, "email": 1, "username": 1}))
    if not users:
        print("No users found. Create a user first.")
        return
    
    print("\nSelect a user to assign this device to:")
    for i, user in enumerate(users):
        username = user.get('username', 'N/A')
        print(f"{i+1}. {username} ({user['email']})")
    
    try:
        selection = int(input("Enter user number (or 0 for no user): "))
        
        user_id = None
        if selection > 0:
            user = users[selection-1]
            user_id = user["_id"]
            
            db.users.update_one(
                {"_id": user_id},
                {"$addToSet": {"devices": device_id}}
            )
            print(f"Device added to user {user.get('username', user['email'])}")
        
        location = input("Enter device location (e.g., living room, office): ")
        
        default_config = {
            "device_id": device_id,
            "config": {
                "device.node_id": device_id,
                "logtype.ignorelist": [1000, 1001, 1002, 1003, 1004, 1005, 1006],
                "ftp.enabled": True,
                "ftp.port": 21,
                "ftp.banner": "FTP server ready",
                "ssh.enabled": True,
                "ssh.port": 8022,
                "ssh.version": "SSH-2.0-OpenSSH_5.1p1 Debian-4",
                "http.enabled": True,
                "http.port": 80,
                "http.banner": "Apache/2.2.22 (Ubuntu)",
                "http.skin": "nasLogin",
                "http.skin.list": [
                    {"name": "basicLogin", "desc": "Plain HTML Login"},
                    {"name": "nasLogin", "desc": "Synology NAS Login"}
                ],
                "logger": {
                    "class": "PyLogger",
                    "kwargs": {
                        "formatters": {
                            "plain": {"format": "%(message)s"},
                            "syslog_rfc": {"format": "opencanaryd[%(process)-5s:%(thread)d]: %(name)s %(levelname)-5s %(message)s"}
                        },
                        "handlers": {
                            "console": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
                            "file": {"class": "logging.FileHandler", "filename": "/var/tmp/opencanary.log", "formatter": "plain"}
                        }
                    }
                }
            },
            "version": "1.0",
            "updated_at": datetime.datetime.now(),
            "pulled": False 
        }
        
        device_record = {
            "device_id": device_id,
            "status": "active",
            "created_at": datetime.datetime.now(),
            "last_seen": None,
            "ip_address": None,
            "user_id": user_id,
            "type": "honeypot",
            "location": location
        }
        
        device_result = db.devices.insert_one(device_record)
        print(f"Device record created with ID: {device_result.inserted_id}")
        
        result = db.config.insert_one(default_config)
        print(f"Device config created with ID: {result.inserted_id}")
        
        configs_result = db.configs.insert_one(default_config)
        print(f"Device config added to configs collection with ID: {configs_result.inserted_id}")
            
    except (ValueError, IndexError) as e:
        print(f"Error: {e}")
        print("Invalid selection")

def change_device_location(db):
    devices = list(db.devices.find({}, {"device_id": 1, "location": 1}))
    
    if not devices:
        print("No devices found.")
        return
    
    print("\nSelect a device to update location:")
    for i, device in enumerate(devices):
        location = device.get('location', 'Unknown')
        print(f"{i+1}. {device['device_id']} - Current location: {location}")
    
    try:
        selection = int(input("Enter device number: "))
        device = devices[selection-1]
        device_id = device["device_id"]
        
        new_location = input(f"Enter new location for {device_id}: ")
        
        db.devices.update_one(
            {"device_id": device_id},
            {"$set": {"location": new_location}}
        )
        
        print(f"Location for device {device_id} updated to: {new_location}")
            
    except (ValueError, IndexError) as e:
        print(f"Error: {e}")
        print("Invalid selection")

def assign_device_to_user(db):
    all_device_ids = db.devices.distinct("device_id")
    
    if not all_device_ids:
        print("No devices found. Create a device first.")
        return
    
    users = list(db.users.find({}, {"_id": 1, "email": 1, "username": 1, "devices": 1}))
    if not users:
        print("No users found. Create a user first.")
        return
    
    print("\nSelect a user:")
    for i, user in enumerate(users):
        username = user.get('username', 'N/A')
        print(f"{i+1}. {username} ({user['email']})")
    
    try:
        user_selection = int(input("Enter user number: "))
        user = users[user_selection-1]
        user_devices = user.get("devices", [])
        
        print("\nSelect a device to assign:")
        device_list = list(all_device_ids)
        for i, device_id in enumerate(device_list):
            status = "Already assigned" if device_id in user_devices else "Available"
            print(f"{i+1}. {device_id} - {status}")
        
        device_selection = int(input("Enter device number: "))
        device_id = device_list[device_selection-1]
        
        if device_id in user_devices:
            print("This device is already assigned to this user")
            return
        
        db.users.update_one(
            {"_id": user["_id"]},
            {"$addToSet": {"devices": device_id}}
        )
        print(f"Device {device_id} added to user {user.get('username', user['email'])}")
            
    except (ValueError, IndexError) as e:
        print(f"Error: {e}")
        print("Invalid selection")

def view_device_logs(db):
    all_device_ids = db.devices.distinct("device_id")
    
    if not all_device_ids:
        print("No devices found.")
        return
    
    print("\nSelect a device to view logs:")
    device_list = list(all_device_ids)
    for i, device_id in enumerate(device_list):
        print(f"{i+1}. {device_id}")
    
    try:
        selection = int(input("Enter device number: "))
        device_id = device_list[selection-1]
        
        limit = int(input("How many logs to show? "))
        
        logs = list(db.logs.find(
            {"device_id": device_id}, 
            sort=[("utc_time", pymongo.DESCENDING)],
            limit=limit
        ))
        
        if not logs:
            print(f"No logs found for device {device_id}")
            return
        
        print(f"\n=== Recent Logs for {device_id} ===")
        for log in logs:
            print(f"Time: {log.get('utc_time', 'N/A')}")
            print(f"Log Type: {log.get('logtype', 'N/A')}")
            
            # Handle different log data formats
            logdata = log.get('logdata', {})
            if isinstance(logdata, dict) and 'msg' in logdata:
                msg = logdata['msg']
                if isinstance(msg, dict) and 'logdata' in msg:
                    print(f"Message: {msg['logdata']}")
                else:
                    print(f"Message: {msg}")
            else:
                print(f"Data: {logdata}")
                
            print(f"Source: {log.get('src_host', 'N/A')}:{log.get('src_port', 'N/A')}")
            print(f"Destination: {log.get('dst_host', 'N/A')}:{log.get('dst_port', 'N/A')}")
            print("-" * 30)
            
    except (ValueError, IndexError) as e:
        print(f"Error: {e}")
        print("Invalid selection")


def remove_device_from_user(db):
    users = list(db.users.find({}, {"_id": 1, "email": 1, "username": 1, "devices": 1}))
    if not users:
        print("No users found.")
        return
    
    users_with_devices = [user for user in users if user.get("devices")]
    
    if not users_with_devices:
        print("No users with assigned devices found.")
        return
    
    print("\nSelect a user:")
    for i, user in enumerate(users_with_devices):
        username = user.get('username', 'N/A')
        devices = user.get('devices', [])
        print(f"{i+1}. {username} ({user['email']}) - {len(devices)} device(s)")
    
    try:
        user_selection = int(input("Enter user number: "))
        user = users_with_devices[user_selection-1]
        user_devices = user.get("devices", [])
        
        if not user_devices:
            print("This user has no devices.")
            return
        
        print("\nSelect a device to remove:")
        for i, device_id in enumerate(user_devices):
            print(f"{i+1}. {device_id}")
        
        device_selection = int(input("Enter device number: "))
        device_id = user_devices[device_selection-1]
        
        db.users.update_one(
            {"_id": user["_id"]},
            {"$pull": {"devices": device_id}}
        )
        print(f"Device {device_id} removed from user {user.get('username', user['email'])}")
            
    except (ValueError, IndexError) as e:
        print(f"Error: {e}")
        print("Invalid selection")

def export_device_config(db):
    config_device_ids = list(db.config.distinct("device_id"))
    
    if not config_device_ids:
        print("No device configs found.")
        return
    
    print("\nSelect a device to export config:")
    for i, device_id in enumerate(config_device_ids):
        print(f"{i+1}. {device_id}")
    
    try:
        selection = int(input("Enter device number: "))
        device_id = config_device_ids[selection-1]
        
        config_doc = db.config.find_one({"device_id": device_id})
        if not config_doc:
            print(f"No config found for device {device_id}")
            return
        
        config = config_doc.get("config", {})
        
        filename = f"{device_id}_config.json"
        
        with open(filename, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"Config exported to {filename}")
            
    except (ValueError, IndexError) as e:
        print(f"Error: {e}")
        print("Invalid selection")

def main_menu():
    db = connect_to_db()
    
    while True:
        print("\n=== Honeypot Admin Management Tool ===")
        print("1. List all users")
        print("2. Add new user")
        print("3. List all devices")
        print("4. Add new device")
        print("5. Assign device to user")
        print("6. Remove device from user")
        print("7. View device logs")
        print("8. Edit device location")
        print("0. Exit")
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1':
            list_users(db)
        elif choice == '2':
            add_user(db)
        elif choice == '3':
            list_devices(db)
        elif choice == '4':
            add_device(db)
        elif choice == '5':
            assign_device_to_user(db)
        elif choice == '6':
            remove_device_from_user(db)
        elif choice == '7':
            view_device_logs(db)
        elif choice == '8':
            change_device_location(db)
        elif choice == '0':
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main_menu()