## Rule34 Webapp

Flask web app (HTML + JSON API) with an **admin API** secured by **Firebase Auth admin claims**.

### Admin API (Firebase Auth)

#### 1) Configure Firebase Admin credentials (server)

Use **one** of these environment variables:

- **`FIREBASE_SERVICE_ACCOUNT_JSON`**: the full service account JSON as a string
- **`GOOGLE_APPLICATION_CREDENTIALS`**: path to a service account JSON file

#### 2) Mark your user as admin (one-time)

Set a Firebase custom claim `admin: true` for your Firebase Auth user.
You can do it from a small script using Firebase Admin SDK (run locally with service account credentials):

```python
import firebase_admin
from firebase_admin import auth, credentials

firebase_admin.initialize_app(credentials.Certificate("serviceAccount.json"))
auth.set_custom_user_claims("<FIREBASE_UID>", {"admin": True})
print("done")
```

After setting claims, **re-login** in the client to get a fresh ID token.

#### 3) Call admin endpoints

Pass Firebase ID token as:

- `Authorization: Bearer <ID_TOKEN>`

Endpoints:

- `GET /api/admin/health`
- `GET /api/admin/stats/overview?hours=24&limit=5000`

