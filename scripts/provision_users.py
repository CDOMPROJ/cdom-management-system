import httpx
import asyncio
import re

# ==============================================================================
# SYSADMIN UTILITY: DIOCESE-WIDE BATCH PROVISIONING
# ==============================================================================
API_URL = "http://192.168.18.9:8000/api/v1/auth/register"

# Your Genesis SysAdmin Token
SYSADMIN_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzeXNhZG1pbkBkb21hbnNhLm9yZyIsInJvbGUiOiJTeXNBZG1pbiIsInBhcmlzaF9pZCI6bnVsbCwiZGVhbmVyeV9pZCI6bnVsbCwidGVuYW50X3NjaGVtYSI6InB1YmxpYyIsInNlc3Npb25faWQiOiIzYjk2MjdjOC0zN2ExLTRkZWMtODkzZC1jOGRkYTM4YzIwMTMiLCJleHAiOjE3NzQwNjg5MzB9.vwoz7qo6WDvtIGJjLruA1ZhcbLo71m5RKg6rTOzJHXM"

HEADERS = {
    "Authorization": f"Bearer {SYSADMIN_TOKEN}",
    "Content-Type": "application/json"
}

# 1. Deanery Mapping (For Deanery-Level Roles)
DIOCESE_DEANERIES = {
    1: "Kashikishi",
    2: "Kawambwa",
    3: "Kabunda",
    4: "Mansa",
    5: "Lubwe",
    6: "Samfya"
}

# 2. Parish Mapping (For Parish-Level Roles)
# Note: St. Christopher (ID: 17) is intentionally excluded per SysAdmin orders.
DIOCESE_PARISHES = [
    # Deanery 1: Kashikishi
    (1, 1, "St. Peter"),
    (2, 1, "St. Paul"),
    (3, 1, "Our Lady of the Rosary"),
    (4, 1, "Mary Help of Christians"),
    (5, 1, "St. Don Bosco"),

    # Deanery 2: Kawambwa
    (6, 2, "St. Mary"),
    (7, 2, "St. Theresa of the Child Jesus"),
    (8, 2, "St. Andrew"),
    (9, 2, "St. Joseph the Worker"),
    (10, 2, "Our Lady of Peace"),

    # Deanery 3: Kabunda
    (11, 3, "St. Stephen"),
    (12, 3, "St. James"),
    (13, 3, "Uganda Martyrs"),
    (14, 3, "Kacema Musuma"),
    (15, 3, "Our Lady of Victory"),

    # Deanery 4: Mansa
    (16, 4, "Mansa Cathedral"),
    # ID 17 is St. Christopher (Skipped)
    (18, 4, "St. Michael the Archangel"),
    (19, 4, "St. John the Baptist"),
    (20, 4, "St. Francis of Assisi"),
    (21, 4, "St. Augustine"),
    (22, 4, "St. Francis de Sales"),
    (23, 4, "St. John Paul II"),

    # Deanery 5: Lubwe
    (24, 5, "St. Joseph Husband of Mary"),
    (25, 5, "St. Anthony of Padua"),
    (26, 5, "St. Margaret"),

    # Deanery 6: Samfya
    (27, 6, "St. John Maria Vianney"),
    (28, 6, "Holy Family"),
    (29, 6, "Christ the King"),
    (30, 6, "St. Peter the Apostle"),
    (31, 6, "St. Monica"),
    (32, 6, "Sacred Heart of Jesus")
]


def format_email_prefix(name: str) -> str:
    """Strips spaces and punctuation to create a clean email prefix."""
    return re.sub(r'[^a-z]', '', name.lower())


async def provision_users():
    print("🚀 Initiating Diocese-Wide Provisioning Sequence (Full Hierarchy)...")

    users_to_create = []

    # ==========================================================================
    # PHASE 1: GENERATE DEANERY-LEVEL ROLES
    # ==========================================================================
    for d_id, d_name in DIOCESE_DEANERIES.items():
        clean_d_name = format_email_prefix(d_name)

        # 1. Dean
        users_to_create.append({
            "email": f"dean{clean_d_name}@domansa.org",
            "password": "SecurePassword123!",
            "role": "Dean",
            "parish_id": None,  # Deans sit above the parish level
            "deanery_id": d_id
        })

        # 2. Deanery Youth Chaplain
        users_to_create.append({
            "email": f"dyc{clean_d_name}@domansa.org",
            "password": "SecurePassword123!",
            "role": "Deanery Youth Chaplain",
            "parish_id": None,
            "deanery_id": d_id
        })

    # ==========================================================================
    # PHASE 2: GENERATE PARISH-LEVEL ROLES
    # ==========================================================================
    for parish_id, deanery_id, name in DIOCESE_PARISHES:
        clean_prefix = format_email_prefix(name)

        # 3. Parish Secretary
        users_to_create.append({
            "email": f"sec{clean_prefix}@domansa.org",
            "password": "SecurePassword123!",
            "role": "Parish Secretary",
            "parish_id": parish_id,
            "deanery_id": deanery_id
        })

        # 4. Parish Priest
        users_to_create.append({
            "email": f"pp{clean_prefix}@domansa.org",
            "password": "SecurePassword123!",
            "role": "Parish Priest",
            "parish_id": parish_id,
            "deanery_id": deanery_id
        })

        # 5. Assistant Priest
        users_to_create.append({
            "email": f"ap{clean_prefix}@domansa.org",
            "password": "SecurePassword123!",
            "role": "Assistant Priest",
            "parish_id": parish_id,
            "deanery_id": deanery_id
        })

        # 6. Parish Youth Chaplain
        users_to_create.append({
            "email": f"pyc{clean_prefix}@domansa.org",
            "password": "SecurePassword123!",
            "role": "Parish Youth Chaplain",
            "parish_id": parish_id,
            "deanery_id": deanery_id
        })

    print(f"📦 Payload generated: Attempting to provision {len(users_to_create)} user accounts...\n")

    async with httpx.AsyncClient() as client:
        for user in users_to_create:
            print(f"🔄 Registering [{user['role']}] -> {user['email']}")

            try:
                response = await client.post(API_URL, json=user, headers=HEADERS)

                if response.status_code == 201 or response.status_code == 200:
                    print(f"  ✅ SUCCESS")
                elif response.status_code == 400 and "already exists" in response.text.lower():
                    print(f"  ⚠️ SKIPPED: Account already exists.")
                else:
                    print(f"  ❌ FAILED: Status {response.status_code}: {response.text}")

            except Exception as e:
                print(f"  ❌ CRITICAL ERROR: {e}")

    print("\n🏁 Diocese-Wide Provisioning Complete!")


if __name__ == "__main__":
    asyncio.run(provision_users())