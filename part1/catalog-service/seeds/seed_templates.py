"""Seed 4 base system templates into MongoDB."""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path

import beanie
from motor.motor_asyncio import AsyncIOMotorClient


TEMPLATES_DIR = Path(__file__).parent / "templates"


async def seed():
    mongo_user = os.getenv("MONGO_USER", "catalog_user")
    mongo_password = os.getenv("MONGO_PASSWORD", "catalog_secret")
    mongo_host = os.getenv("MONGO_HOST", "localhost")
    mongo_port = int(os.getenv("MONGO_PORT", "27017"))
    mongo_db = os.getenv("MONGO_DB", "catalog_db")

    if mongo_user and mongo_password:
        mongo_url = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}"
    else:
        mongo_url = f"mongodb://{mongo_host}:{mongo_port}"

    client = AsyncIOMotorClient(mongo_url)
    db = client[mongo_db]

    from app.models.template import Template

    await beanie.init_beanie(database=db, document_models=[Template])

    for json_file in sorted(TEMPLATES_DIR.glob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        template_id = data.pop("_id")

        existing = await Template.get(template_id)
        if existing:
            print(f"  skip (exists): {template_id}")
            continue

        tmpl = Template(id=template_id, **data)
        await tmpl.insert()
        print(f"  seeded: {template_id} — {tmpl.name}")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
