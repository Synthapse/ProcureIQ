import logging

from neo4j import GraphDatabase
from app.config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self):
        self._driver = None

    def connect(self):
        logger.info("Connecting to Neo4j at %s", settings.neo4j_uri)
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self):
        if self._driver:
            self._driver.close()
            logger.debug("Neo4j connection closed")

    def run_query(self, cypher: str, parameters: dict | None = None) -> list[dict]:
        if self._driver is None:
            self.connect()
        logger.debug("Running Cypher (params keys: %s)", list((parameters or {}).keys()))
        with self._driver.session() as session:
            result = session.run(cypher, parameters or {})
            records = [record.data() for record in result]
        logger.debug("Query returned %d records", len(records))
        return records

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()


neo4j_client = Neo4jClient()
