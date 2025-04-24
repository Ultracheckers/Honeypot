#!/usr/bin/env python3
import os
import json
import time
import logging
import subprocess
import sys
import json
import datetime
import pymongo
import dotenv
from pymongo import MongoClient

dotenv.load_dotenv()

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if str(type(obj)) == "<class 'bson.objectid.ObjectId'>":
            return str(obj)
        return super().default(obj)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/tmp/opencanary_sync.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('opencanary-sync')

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DB_NAME", "opencanary_test")
CONFIG_COLLECTION = "configs"
LOG_COLLECTION = "logs"
DEVICE_ID = "honeypot-3"  # Unique identifier for this device
CONFIG_PATH = "/etc/opencanaryd/opencanary.conf"
LOG_PATH = "/var/tmp/opencanary.log"
SYNC_INTERVAL = 60  # Seconds between sync operations
LAST_SYNC_MARKER = "/var/tmp/opencanary_last_sync"
ARCHIVE_LOG_DIR = "/var/tmp/log_archive"
ARCHIVE_LOG_FILE = os.path.join(ARCHIVE_LOG_DIR, "all_logs.json")

# Global process handle for OpenCanary
opencanary_process = None

def connect_to_mongodb():
    """Connect to MongoDB and return database instance"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Verify connection works
        client.server_info()
        db = client[DATABASE_NAME]
        logger.info("Connected to MongoDB successfully")
        return db
    except pymongo.errors.ServerSelectionTimeoutError as e:
        logger.error(f"Could not connect to MongoDB: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        return None

def get_remote_config(db):
    """Fetch the latest config from MongoDB"""
    try:
        config_doc = db[CONFIG_COLLECTION].find_one(
            {"device_id": DEVICE_ID},
            sort=[("updated_at", pymongo.DESCENDING)]
        )
        
        if not config_doc:
            logger.info("No config found for this device")
            
            # Check if we have a local config to upload
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, 'r') as f:
                        current_config = json.load(f)
                    
                    # Upload the current config to the database
                    logger.info("Uploading current config to database")
                    now = datetime.datetime.utcnow()
                    db[CONFIG_COLLECTION].insert_one({
                        "device_id": DEVICE_ID,
                        "config": current_config,
                        "version": current_config.get("version", "1.0"),
                        "updated_at": now,
                        "pulled": True
                    })
                    logger.info("Current config uploaded successfully")
                    
                except json.JSONDecodeError:
                    logger.warning("Current config is not valid JSON, cannot upload")
                except Exception as e:
                    logger.error(f"Error uploading current config: {e}")
            
            return None
            
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    current_config = json.load(f)
                    
                    pulled_latest = config_doc.get("pulled")
                    
                    if pulled_latest:
                        logger.info(f"Config already up to date (version: {config_doc.get('version')})")
                        return None
                    
            except json.JSONDecodeError:
                logger.warning("Current config is not valid JSON, will replace")
                    
        logger.info(f"Pulling new config!")
        
        config = config_doc.get("config", {})
        
        db[CONFIG_COLLECTION].update_one(
            {"_id": config_doc["_id"]},
            {"$set": {"pulled": True}}
        )
        
        return config
        
    except Exception as e:
        logger.error(f"Error fetching remote config: {e}")
        return None 

def start_opencanary():
    try:
        logger.info("Starting OpenCanary via script...")
        result = subprocess.run(
            ["/opt/opencanary/start_opencanary.sh"],
            capture_output=True,
            text=True
        )
        logger.info(f"Start script output: {result.stdout}")
        if result.stderr:
            logger.error(f"Start script errors: {result.stderr}")
        
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error executing start script: {e}")
        return False

def stop_opencanary():
    try:
        logger.info("Stopping OpenCanary via script...")
        result = subprocess.run(
            ["/opt/opencanary/stop_opencanary.sh"],
            capture_output=True,
            text=True
        )
        logger.info(f"Stop script output: {result.stdout}")
        if result.stderr:
            logger.error(f"Stop script errors: {result.stderr}")
        
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error executing stop script: {e}")
        return False

def parse_log_file(last_sync_time):
    """Parse the log file and extract entries newer than last_sync_time"""
    new_logs = []
    
    try:
        if not os.path.exists(LOG_PATH):
            logger.warning(f"Log file not found: {LOG_PATH}")
            return new_logs
            
        with open(LOG_PATH, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    if "time" in log_entry and log_entry["time"] > last_sync_time:
                        log_entry["device_id"] = DEVICE_ID
                        new_logs.append(log_entry)
                except json.JSONDecodeError:
                    continue 
    except Exception as e:
        logger.error(f"Error parsing log file: {e}")
    
    logger.info(f"Found {len(new_logs)} new log entries")
    return new_logs

def archive_logs(log_entries):
    """Append the processed logs to a single archive file."""
    try:
        os.makedirs(ARCHIVE_LOG_DIR, exist_ok=True)

        if os.path.exists(ARCHIVE_LOG_FILE) and os.path.getsize(ARCHIVE_LOG_FILE) > 0:
            with open(ARCHIVE_LOG_FILE, 'r') as f:
                try:
                    existing_logs = json.load(f)
                except json.JSONDecodeError:
                    existing_logs = []
        else:
            existing_logs = []

        existing_logs.extend(log_entries)

        with open(ARCHIVE_LOG_FILE, 'w') as f:
            json.dump(existing_logs, f, indent=4)

        logger.info(f"Appended {len(log_entries)} logs to {ARCHIVE_LOG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error appending logs: {e}")
        return False

def upload_logs(db, logs):
    """Upload new logs to MongoDB and archive them"""
    if not logs:
        logger.info("No new logs to upload")
        return True
    
    try:
        result = db[LOG_COLLECTION].insert_many(logs)
        logger.info(f"Uploaded {len(result.inserted_ids)} logs successfully")
        
        if archive_logs(logs):
            logger.info("Logs archived successfully.")
        else:
            logger.error("Failed to archive logs.")
        
        return True
    except Exception as e:
        logger.error(f"Error uploading logs: {e}")
        return False

def ensure_log_file_exists():
    """Make sure the log file exists and is writable"""
    try:
        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH, 'w') as f:
                pass 
            os.chmod(LOG_PATH, 0o666) 
            logger.info(f"Created log file: {LOG_PATH}")
    except Exception as e:
        logger.error(f"Error creating log file: {e}")

def check_opencanary_status():
    """Check if OpenCanary is running and restart if needed"""
    try:
        result = subprocess.run(
            ["/opt/opencanary/check_opencanary.sh"], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            logger.info("OpenCanary is running based on check script")
            return True
    except Exception as e:
        logger.error(f"Error checking OpenCanary process: {e}")
        
    logger.warning("OpenCanary not running, attempting to restart")
    return start_opencanary()

def sync_logs_with_mongodb():
    """Sync all logs with MongoDB and archive them"""
    db = connect_to_mongodb()
    if db is None:
        logger.error("Log sync failed: Could not connect to MongoDB")
        return False
    
    try:
        if not os.path.exists(LOG_PATH):
            logger.warning(f"Log file not found: {LOG_PATH}")
            return False
            
        with open(LOG_PATH, 'r') as f:
            log_lines = f.readlines()
        
        if not log_lines:
            logger.info("No logs found in log file")
            return True
            
        logs_to_upload = []
        for line in log_lines:
            try:
                log_entry = json.loads(line.strip())
                log_entry["device_id"] = DEVICE_ID
                logs_to_upload.append(log_entry)
            except json.JSONDecodeError:
                continue  
        
        if not logs_to_upload:
            logger.info("No valid logs found to upload")
            return True
            
        result = db[LOG_COLLECTION].insert_many(logs_to_upload)
        logger.info(f"Uploaded {len(result.inserted_ids)} logs successfully")
        
        timestamp = int(time.time())
        archive_path = os.path.join(ARCHIVE_LOG_DIR, f"opencanary_logs_{timestamp}.json")
        
        os.makedirs(ARCHIVE_LOG_DIR, exist_ok=True)
        
        with open(archive_path, 'w') as f:
            for log in logs_to_upload:
                f.write(json.dumps(log, cls=MongoJSONEncoder) + "\n")
        

        with open(LOG_PATH, 'w') as f:
            pass 
            
        logger.info(f"Archived {len(logs_to_upload)} logs to {archive_path}")
        logger.info("Cleared original log file")
        
        return True
    except Exception as e:
        logger.error(f"Error processing logs: {e}")
        return False
    
def update_local_config(config_data):
    """Update local config file with new config data"""
    try:
        if os.path.exists(CONFIG_PATH):
            backup_path = f"{CONFIG_PATH}.backup.{int(time.time())}"
            with open(CONFIG_PATH, 'r') as src, open(backup_path, 'w') as dst:
                dst.write(src.read())
            logger.info(f"Backed up current config to {backup_path}")
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config_data, f, indent=4)
        
        logger.info("Updated local config successfully")
        return True
    except Exception as e:
        logger.error(f"Error updating local config: {e}")
        return False
    
def sync_with_mongodb():
    """Sync config and logs with MongoDB"""
    db = connect_to_mongodb()
    if db is None: 
        logger.error("Sync failed: Could not connect to MongoDB")
        return
    
    update_device_info(db)

    config_updated = False
    config_data = get_remote_config(db)
    if config_data:
        config_updated = update_local_config(config_data)
    
    sync_logs_with_mongodb()
    
    if config_updated:
        if stop_opencanary():
            time.sleep(2) 
            start_opencanary()
    
    logger.info("Sync operation completed")

def update_device_info(db):
    if db is None:
        logger.error("Cannot update device, DB was None.")
        
    try:
        current_time = datetime.datetime.utcnow()
        ip_address = os.environ.get("HOST_IP")

        result = db["devices"].update_one(
            {"device_id": DEVICE_ID},
            {"$set": {
                "ip_address": ip_address,
                "last_seen": current_time
            }}
        )

        if result.matched_count > 0:
            logger.info(f"Updated device info: IP={ip_address}, last_seen={current_time}")
            return True
        else:
            logger.info(f"No device entry found, creating new entry")
            db["devices"].insert_one({
                "device_id": DEVICE_ID,
                "status": "active",
                "created_at": current_time,
                "last_seen": current_time,
                "ip_address": ip_address,
                "type": "honeypot"
            })
            logger.info(f"Created new device entry with IP={ip_address}")
            return True
            
    except Exception as e:
        logger.error(f"Error updating device info: {e}")
        return False

def main():
    """Main function that runs the sync process and manages OpenCanary"""
    
    logger.info("Starting OpenCanary Manager with MongoDB Sync")
    
    ensure_log_file_exists()
    
    if not start_opencanary():
        logger.error("Failed to start OpenCanary initially, continuing anyway...")
    

    while True:
        try:
            sync_with_mongodb()

            time.sleep(1)  
            check_opencanary_status()
            
        except Exception as e:
            logger.error(f"Unhandled exception in main loop: {e}")
        
        logger.info(f"Sleeping for {SYNC_INTERVAL} seconds")
        time.sleep(SYNC_INTERVAL)

if __name__ == "__main__":
    main()