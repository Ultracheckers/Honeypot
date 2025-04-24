use mongodb::{Client, Database};
use mongodb::options::ClientOptions;
use bson::doc;
use serde::{Serialize, Deserialize};
use bcrypt::{hash, verify, DEFAULT_COST};
use anyhow::{Result, anyhow};
use dotenv::dotenv;
use uuid::Uuid;
use chrono::{Utc, Duration};
use futures_util::StreamExt;
use dotenvy_macro::dotenv;

#[derive(Debug, Serialize, Deserialize)]
pub struct Device {
    #[serde(rename = "_id", skip_serializing_if = "Option::is_none")]
    pub id: Option<bson::oid::ObjectId>,
    pub device_id: String,
    pub status: String,
    pub ip_address: String,
    pub location: String,
    #[serde(rename = "type")]
    pub device_type: String,  
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<bson::DateTime>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_seen: Option<bson::DateTime>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Log {
    #[serde(rename = "_id", skip_serializing_if = "Option::is_none")]
    pub id: Option<bson::oid::ObjectId>,
    pub logdata: serde_json::Value,  
    pub dst_host: String,
    pub dst_port: serde_json::Value, 
    pub local_time: String,
    pub local_time_adjusted: String,
    pub logtype: serde_json::Value,  
    pub node_id: String,
    pub src_host: String,
    pub src_port: serde_json::Value,  
    pub utc_time: String,
    pub device_id: String,
}


#[tauri::command]
async fn get_user_devices(user_id: String) -> Result<Vec<Device>, String> {
    println!("Fetching devices for user: {}", user_id);
    
    let user_oid = match bson::oid::ObjectId::parse_str(&user_id) {
        Ok(oid) => oid,
        Err(_) => return Err("Invalid user ID format".to_string()),
    };
    
    let db = match connect_db().await {
        Ok(db) => db,
        Err(e) => return Err(format!("Database connection error: {}", e)),
    };
    
    let users_collection = db.collection::<User>("users");
    let user = match users_collection.find_one(doc! { "_id": user_oid }, None).await {
        Ok(Some(user)) => user,
        Ok(None) => return Err("User not found".to_string()),
        Err(e) => return Err(format!("Failed to query user: {}", e)),
    };
    
    println!("Found user with {} devices", user.devices.len());
    
    let devices_collection = db.collection::<Device>("devices");
    
    let mut devices = Vec::new();
    
    for device_id in &user.devices {
        println!("Looking for device with id: {}", device_id);
        
        match devices_collection.find_one(doc! { "device_id": device_id }, None).await {
            Ok(Some(device)) => {
                println!("Found device: {} (type: {})", device_id, device.device_type);
                devices.push(device);
            },
            Ok(None) => {
                println!("Device {} not found in database", device_id);
                continue;
            },
            Err(e) => {
                println!("Error fetching device {}: {}", device_id, e);
                continue;
            }
        }
    }
    
    println!("Successfully fetched {} devices", devices.len());
    Ok(devices)
}

#[tauri::command]
async fn get_user_logs(user_id: String) -> Result<Vec<Log>, String> {
    println!("Fetching logs for user: {}", user_id);
    

    let user_oid = match bson::oid::ObjectId::parse_str(&user_id) {
        Ok(oid) => oid,
        Err(_) => return Err("Invalid user ID format".to_string()),
    };
    

    let db = match connect_db().await {
        Ok(db) => db,
        Err(e) => return Err(format!("Database connection error: {}", e)),
    };
    

    let users_collection = db.collection::<User>("users");
    let user = match users_collection.find_one(doc! { "_id": user_oid }, None).await {
        Ok(Some(user)) => user,
        Ok(None) => return Err("User not found".to_string()),
        Err(e) => return Err(format!("Failed to query user: {}", e)),
    };
    

    if user.devices.is_empty() {
        return Ok(Vec::new());
    }
    

    let logs_collection = db.collection::<Log>("logs");
    let mut logs = Vec::new();
    
    for device_id in &user.devices {
        let mut logs_cursor = match logs_collection
            .find(doc! { "device_id": device_id }, None).await 
        {
            Ok(cursor) => cursor,
            Err(e) => {
                println!("Error fetching logs for device {}: {}", device_id, e);
                continue;
            }
        };
        

        while let Some(log_result) = logs_cursor.next().await {
            match log_result {
                Ok(log) => {
                    logs.push(log);
                },
                Err(e) => {
                    println!("Error processing log: {}", e);
                    continue;
                }
            }
        }
    }
    

    logs.sort_by(|a, b| {
        let time_a = chrono::DateTime::parse_from_rfc3339(&a.utc_time)
            .unwrap_or_else(|_| chrono::DateTime::parse_from_rfc3339("1970-01-01T00:00:00Z").unwrap());
        let time_b = chrono::DateTime::parse_from_rfc3339(&b.utc_time)
            .unwrap_or_else(|_| chrono::DateTime::parse_from_rfc3339("1970-01-01T00:00:00Z").unwrap());
        time_b.cmp(&time_a)
    });
    
    println!("Fetched {} logs", logs.len());
    Ok(logs)
}




#[derive(Debug, Serialize, Deserialize)]
pub struct User {
    #[serde(rename = "_id", skip_serializing_if = "Option::is_none")]
    pub id: Option<bson::oid::ObjectId>,
    pub email: String,
    pub username: String,
    pub devices: Vec<String>,
    pub password: String, 
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<bson::DateTime>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct UserCredentials {
    pub email: String,
    pub password: String, 
}


#[derive(Debug, Serialize, Deserialize)]
pub struct RegistrationCredentials {
    pub email: String,
    pub username: String,
    pub password: String, 
}


#[derive(Serialize)]
pub struct AuthResponse {
    pub success: bool,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub token: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expiry: Option<i64>,
}


#[derive(Debug, Serialize, Deserialize)]
pub struct SessionToken {
    #[serde(rename = "_id", skip_serializing_if = "Option::is_none")]
    pub id: Option<bson::oid::ObjectId>,
    pub token: String,
    pub user_id: bson::oid::ObjectId,
    pub expires_at: bson::DateTime,
    pub created_at: bson::DateTime,
}


#[derive(Serialize)]
pub struct TokenValidationResponse {
    pub success: bool,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_id: Option<String>,
}


async fn connect_db() -> Result<Database> {
    dotenv().ok();
    

    let mongodb_uri: &str = dotenv!("MONGODB_URI");
    

    let client_options = ClientOptions::parse(&mongodb_uri)
        .await
        .map_err(|e| anyhow!("Failed to parse MongoDB connection string: {}", e))?;
    

    let client = Client::with_options(client_options)
        .map_err(|e| anyhow!("Failed to create MongoDB client: {}", e))?;
    

    let db_name = std::env::var("DB_NAME").unwrap_or_else(|_| "opencanary_test".to_string());
    let db = client.database(&db_name);
    

    client.database("admin").run_command(doc! { "ping": 1 }, None)
        .await
        .map_err(|e| anyhow!("Failed to connect to MongoDB: {}", e))?;
    
    Ok(db)
}


async fn register_user(credentials: RegistrationCredentials) -> Result<User> {
    // Validate input
    if credentials.email.trim().is_empty() {
        return Err(anyhow!("Email cannot be empty"));
    }
    
    if credentials.password.len() < 6 {
        return Err(anyhow!("Password must be at least 6 characters"));
    }

    if credentials.username.len() < 4 {
        return Err(anyhow!("Username must be at least 4 characters"));
    }
    
    let db = connect_db().await?;
    let users_collection = db.collection::<User>("users");
    

    let existing_user = users_collection
        .find_one(doc! { "email": &credentials.email }, None)
        .await?;
    
    if existing_user.is_some() {
        return Err(anyhow!("User with this email already exists"));
    }
    

    let hashed_password = hash(credentials.password, DEFAULT_COST)
        .map_err(|e| anyhow!("Failed to hash password: {}", e))?;
    

    let new_user = User {
        id: None,
        email: credentials.email,
        username: credentials.username,
        devices:  Vec::<String>::new(),
        password: hashed_password,
        created_at: Some(bson::DateTime::now()),
    };
    

    let insert_result = users_collection.insert_one(&new_user, None).await
        .map_err(|e| anyhow!("Failed to insert user: {}", e))?;
    
    let id = insert_result.inserted_id.as_object_id()
        .ok_or_else(|| anyhow!("Failed to get inserted ID"))?;
    

    Ok(User {
        id: Some(id),
        ..new_user
    })
}


async fn authenticate_user(credentials: UserCredentials) -> Result<User> {
    let db = connect_db().await?;
    let users_collection = db.collection::<User>("users");
    

    let user = users_collection
        .find_one(doc! { "email": &credentials.email }, None)
        .await
        .map_err(|e| anyhow!("Database error: {}", e))?
        .ok_or_else(|| anyhow!("User not found"))?;
    

    let password_valid = verify(&credentials.password, &user.password)
        .map_err(|e| anyhow!("Password verification error: {}", e))?;
        
    if !password_valid {
        return Err(anyhow!("Invalid password"));
    }
    
    Ok(user)
}


async fn create_session_token(user_id: bson::oid::ObjectId) -> Result<SessionToken> {
    let db = connect_db().await?;
    let tokens_collection = db.collection::<SessionToken>("session_tokens");
    

    let token = Uuid::new_v4().to_string();
    

    let now = Utc::now();
    let expires_at = now + Duration::days(7);
    

    let session_token = SessionToken {
        id: None,
        token,
        user_id,
        expires_at: bson::DateTime::from_chrono(expires_at),
        created_at: bson::DateTime::from_chrono(now),
    };
    

    let insert_result = tokens_collection.insert_one(&session_token, None).await
        .map_err(|e| anyhow!("Failed to insert session token: {}", e))?;
    
    let id = insert_result.inserted_id.as_object_id()
        .ok_or_else(|| anyhow!("Failed to get inserted ID"))?;
    

    Ok(SessionToken {
        id: Some(id),
        ..session_token
    })
}


async fn validate_session_token(token_str: &str) -> Result<User> {
    let db = connect_db().await?;
    let tokens_collection = db.collection::<SessionToken>("session_tokens");
    

    let token = tokens_collection
        .find_one(doc! { "token": token_str }, None)
        .await
        .map_err(|e| anyhow!("Database error: {}", e))?
        .ok_or_else(|| anyhow!("Token not found"))?;
    

    let now = Utc::now();
    if token.expires_at.to_chrono() < now {

        tokens_collection
            .delete_one(doc! { "token": token_str }, None)
            .await
            .map_err(|e| anyhow!("Failed to delete expired token: {}", e))?;
        
        return Err(anyhow!("Token has expired"));
    }
    

    let users_collection = db.collection::<User>("users");
    let user = users_collection
        .find_one(doc! { "_id": token.user_id }, None)
        .await
        .map_err(|e| anyhow!("Database error: {}", e))?
        .ok_or_else(|| anyhow!("User not found"))?;
    
    Ok(user)
}


async fn invalidate_user_tokens(user_id_str: &str) -> Result<()> {
    let user_id = bson::oid::ObjectId::parse_str(user_id_str)
        .map_err(|_| anyhow!("Invalid user ID format"))?;
    
    let db = connect_db().await?;
    let tokens_collection = db.collection::<SessionToken>("session_tokens");
    

    tokens_collection
        .delete_many(doc! { "user_id": user_id }, None)
        .await
        .map_err(|e| anyhow!("Failed to delete user tokens: {}", e))?;
    
    Ok(())
}


#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}


#[tauri::command]
async fn register(credentials: RegistrationCredentials) -> AuthResponse {
    println!("Registering user with email: {}", credentials.email);
    
    match register_user(credentials).await {
        Ok(user) => {
            println!("User registered successfully");
            AuthResponse {
                success: true,
                message: "Registration successful".to_string(),
                user_id: user.id.map(|id| id.to_hex()),
                token: None,
                expiry: None,
            }
        },
        Err(e) => {
            println!("Registration failed: {}", e);
            AuthResponse {
                success: false,
                message: format!("Registration failed: {}", e),
                user_id: None,
                token: None,
                expiry: None,
            }
        },
    }
}


#[tauri::command]
async fn login(credentials: UserCredentials, remember: bool) -> AuthResponse {
    println!("Logging in user with email: {}", credentials.email);
    
    match authenticate_user(credentials).await {
        Ok(user) => {
            println!("Login successful");
            

            let user_id = match user.id {
                Some(id) => id,
                None => return AuthResponse {
                    success: false,
                    message: "User ID not found".to_string(),
                    user_id: None,
                    token: None,
                    expiry: None,
                },
            };
            

            if remember {
                match create_session_token(user_id).await {
                    Ok(session_token) => {
                        let expiry = session_token.expires_at.to_chrono().timestamp() * 1000; // Convert to milliseconds
                        
                        AuthResponse {
                            success: true,
                            message: "Login successful".to_string(),
                            user_id: Some(user_id.to_hex()),
                            token: Some(session_token.token),
                            expiry: Some(expiry),
                        }
                    },
                    Err(e) => {
                        println!("Failed to create session token: {}", e);
                        AuthResponse {
                            success: true,
                            message: "Login successful, but failed to remember session".to_string(),
                            user_id: Some(user_id.to_hex()),
                            token: None,
                            expiry: None,
                        }
                    }
                }
            } else {

                AuthResponse {
                    success: true,
                    message: "Login successful".to_string(),
                    user_id: Some(user_id.to_hex()),
                    token: None,
                    expiry: None,
                }
            }
        },
        Err(e) => {
            println!("Login failed: {}", e);
            AuthResponse {
                success: false,
                message: format!("Login failed: {}", e),
                user_id: None,
                token: None,
                expiry: None,
            }
        },
    }
}


#[tauri::command]
async fn validate_token(token: String) -> TokenValidationResponse {
    println!("Validating token");
    
    match validate_session_token(&token).await {
        Ok(user) => {
            println!("Token validation successful");
            TokenValidationResponse {
                success: true,
                message: "Token is valid".to_string(),
                user_id: user.id.map(|id| id.to_hex()),
            }
        },
        Err(e) => {
            println!("Token validation failed: {}", e);
            TokenValidationResponse {
                success: false,
                message: format!("Token validation failed: {}", e),
                user_id: None,
            }
        },
    }
}


#[tauri::command]
async fn logout(user_id: String) -> Result<(), String> {
    println!("Logging out user: {}", user_id);
    
    invalidate_user_tokens(&user_id)
        .await
        .map_err(|e| format!("Failed to logout: {}", e))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            greet, 
            register, 
            login,
            validate_token,
            logout,
            get_user_devices,
            get_user_logs
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}