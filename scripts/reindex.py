"""Explicitly migrate one project's stored documents to the configured index version."""

import argparse
import asyncio
import json
import uuid

from sqlalchemy import select
from qdrant_client import AsyncQdrantClient

from app.config import get_settings
from app.database import create_database_engine, create_session_factory
from app.ingestion import build_embedder, reindex_documents
from app.models import Project


async def run(project_id: uuid.UUID | None, document_id: uuid.UUID | None, force: bool) -> dict[str, int]:
    settings = get_settings()
    engine = create_database_engine(settings)
    sessions = create_session_factory(engine)

    qdrant = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        check_compatibility=False,
    )

    try:
        async with sessions() as session:

            # Automatically pick the first project if none supplied
            if project_id is None:
                project = (
                    await session.scalars(select(Project).limit(1))
                ).first()

                if project is None:
                    raise RuntimeError("No projects found in the database.")

                project_id = project.id
                print(f"Using project: {project_id}")

            return await reindex_documents(
                session,
                qdrant,
                build_embedder(settings),
                settings,
                project_id,
                document_id,
                force=force,
            )

    finally:
        await qdrant.close()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reindex Atlas documents."
    )

    parser.add_argument(
        "--project-id",
        type=uuid.UUID,
        required=False,
        help="Project UUID (optional). If omitted, the first project is used.",
    )

    parser.add_argument(
        "--document-id",
        type=uuid.UUID,
    )

    parser.add_argument(
        "--force",
        action="store_true",
    )

    args = parser.parse_args()

    result = asyncio.run(
        run(
            args.project_id,
            args.document_id,
            args.force,
        )
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()