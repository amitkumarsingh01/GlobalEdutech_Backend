# Google Authentication Backend Integration

This document explains the Google authentication integration that has been added to the FastAPI backend.

## New Endpoints Added

### 1. Google Authentication
**POST** `/auth/google`

Authenticates users with Google and creates/updates user accounts.

**Request Body:**
```json
{
  "firebase_uid": "firebase_user_id",
  "name": "User Name",
  "email": "user@example.com",
  "photo_url": "https://profile_picture_url",
  "access_token": "google_access_token",
  "id_token": "google_id_token",
  "provider": "google"
}
```

**Response:**
```json
{
  "message": "Google authentication successful",
  "user_id": "user_id",
  "token": "jwt_token",
  "user": {
    "id": "user_id",
    "name": "User Name",
    "email": "user@example.com",
    "firebase_uid": "firebase_user_id",
    "photo_url": "profile_picture_url",
    "provider": "google",
    "contact_no": "",
    "gender": "other",
    "dob": null,
    "education": "Higher education",
    "course": "Select Course",
    "is_active": true,
    "last_login": "2024-01-01T00:00:00",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
}
```

### 2. Link Google Account
**POST** `/auth/link-google`

Links a Google account to an existing email/password account.

**Request Body:**
```json
{
  "firebase_uid": "firebase_user_id",
  "photo_url": "https://profile_picture_url"
}
```

**Headers:**
```
Authorization: Bearer <jwt_token>
```

### 3. Unlink Google Account
**POST** `/auth/unlink-google`

Unlinks Google account from user profile.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

### 4. Update User Profile
**PUT** `/users/{user_id}/profile`

Updates user profile information (useful for Google users to complete their profile).

**Request Body:**
```json
{
  "contact_no": "1234567890",
  "gender": "male",
  "dob": "1990-01-01",
  "education": "Graduation",
  "course": "B.Com"
}
```

**Headers:**
```
Authorization: Bearer <jwt_token>
```

### 5. Get User by Email
**GET** `/users/email/{email}`

Checks if a user exists by email address.

## Database Schema Updates

The user collection now includes these additional fields for Google authentication:

```javascript
{
  "_id": ObjectId,
  "name": String,
  "email": String,
  "password": String, // null for Google users
  "contact_no": String,
  "gender": String,
  "dob": Date,
  "education": String,
  "course": String,
  "firebase_uid": String, // NEW: Firebase user ID
  "photo_url": String,    // NEW: Google profile picture
  "provider": String,     // NEW: "email" or "google"
  "is_active": Boolean,
  "last_login": Date,
  "created_at": Date,
  "updated_at": Date
}
```

## Authentication Flow

### For New Google Users:
1. User signs in with Google in Flutter app
2. Firebase authentication completes
3. App sends Google user data to `/auth/google`
4. Backend creates new user with default values
5. Returns JWT token and user data
6. User can later complete profile via `/users/{user_id}/profile`

### For Existing Google Users:
1. User signs in with Google in Flutter app
2. Firebase authentication completes
3. App sends Google user data to `/auth/google`
4. Backend finds existing user by email or firebase_uid
5. Updates user information with latest Google data
6. Returns JWT token and updated user data

### For Existing Email/Password Users:
1. User can link Google account via `/auth/link-google`
2. User can then sign in with either method
3. User can unlink Google account via `/auth/unlink-google`

## Security Features

1. **JWT Token Authentication**: All protected endpoints require valid JWT tokens
2. **User Authorization**: Users can only update their own profiles
3. **Firebase UID Validation**: Prevents duplicate Google account linking
4. **Sensitive Field Protection**: Password and other sensitive fields are protected from updates

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: User not authorized for action
- `404 Not Found`: User or resource not found
- `500 Internal Server Error`: Server-side errors

## Testing the Integration

### Test Google Authentication:
```bash
curl -X POST "http://localhost:8000/auth/google" \
  -H "Content-Type: application/json" \
  -d '{
    "firebase_uid": "test_firebase_uid",
    "name": "Test User",
    "email": "test@example.com",
    "photo_url": "https://example.com/photo.jpg",
    "provider": "google"
  }'
```

### Test Profile Update:
```bash
curl -X PUT "http://localhost:8000/users/{user_id}/profile" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{
    "contact_no": "1234567890",
    "gender": "male",
    "dob": "1990-01-01"
  }'
```

## Integration with Flutter App

The Flutter app's `ApiService.googleAuth()` method calls the `/auth/google` endpoint with the required data structure. The backend handles:

1. User creation/update
2. JWT token generation
3. User data serialization
4. Error handling

## Future Enhancements

1. **Google Token Verification**: Implement server-side Google ID token verification
2. **Multiple Provider Support**: Add support for Facebook, Apple, etc.
3. **Account Merging**: Allow merging of duplicate accounts
4. **Profile Picture Upload**: Handle custom profile pictures
5. **Email Verification**: Add email verification for Google users

## Dependencies

No additional Python packages are required for basic Google authentication. For enhanced security, consider adding:

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2
```

## Configuration

Ensure your MongoDB database is running and accessible. The API uses the existing MongoDB connection and user collection.

## Monitoring and Logging

Consider adding logging for:
- Google authentication attempts
- User account linking/unlinking
- Profile updates
- Failed authentication attempts

This will help with debugging and security monitoring.
