"""One-time script to reset a user's password. Run via: railway ssh -- python scripts/reset_password.py"""
import asyncio
import os
import sys

import asyncpg
import bcrypt


async def main():
    password = sys.argv[1] if len(sys.argv) > 1 else input("New password: ")
    email = sys.argv[2] if len(sys.argv) > 2 else input("Email: ")
    h = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")
    conn = await asyncpg.connect(url)
    try:
        r = await conn.execute(
            "UPDATE candidates SET password_hash = $1 WHERE email = $2", h, email
        )
        count = int(str(r).split(" ")[-1])
        if count == 0:
            print(f"ERROR: No candidate found with email '{email}'. Password NOT changed.")
        else:
            print(f"Password updated successfully for {email}")
    finally:
        await conn.close()


asyncio.run(main())
