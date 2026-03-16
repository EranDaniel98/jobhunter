"""One-time script to reset a user's password. Run via: railway ssh -- python scripts/reset_password.py"""
import asyncio
import os

import asyncpg
import bcrypt


async def main():
    password = "Admin123"
    email = "erand1998@gmail.com"
    h = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")
    conn = await asyncpg.connect(url)
    r = await conn.execute(
        "UPDATE candidates SET password_hash = $1 WHERE email = $2", h, email
    )
    count = int(str(r).split(" ")[-1])
    if count == 0:
        print(f"ERROR: No candidate found with email '{email}'. Password NOT changed.")
    else:
        print(f"Password updated successfully for {email}")
    await conn.close()


asyncio.run(main())
