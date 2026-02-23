from neo4j import GraphDatabase
from app.config import settings


class Neo4jClient:
    def __init__(self):
        self._driver = None

    def connect(self):
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self):
        if self._driver:
            self._driver.close()

    def run_query(self, cypher: str, parameters: dict | None = None) -> list[dict]:
        if self._driver is None:
            self.connect()
        with self._driver.session() as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()


neo4j_client = Neo4jClient()
