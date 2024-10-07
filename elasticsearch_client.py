import logging
import uuid

import psycopg2
from elasticsearch import Elasticsearch, helpers

from config import settings
from postgres_client import PostgresClient


class ElasticsearchClient:
    def __init__(self):
        self.es = Elasticsearch(
            hosts=[settings.elasticsearch_url],
            headers={"Content-Type": "application/json"},
        )

    def index_products_to_es(self, postgs: PostgresClient, batch_size=500):
        cursor = postgs.conn.cursor(
            name="products_cursor", cursor_factory=psycopg2.extras.DictCursor
        )
        cursor.execute(
            "SELECT uuid, marketplace_id, product_id, title, description, brand, "
            "features FROM public.sku"
        )

        es = Elasticsearch(
            hosts=["http://elasticsearch:9200"],
            headers={"Content-Type": "application/json"},
        )

        logging.info("Начало индексации товаров...")

        try:
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break

                actions = []
                for row in rows:
                    doc = {
                        "_index": "products",
                        "_id": row["uuid"],
                        "_source": {
                            "uuid": row["uuid"],
                            "marketplace_id": row["marketplace_id"],
                            "product_id": row["product_id"],
                            "title": row["title"],
                            "description": row["description"],
                            "brand": row["brand"],
                            "features": row["features"],  # Поле features в формате JSON
                        },
                    }
                    actions.append(doc)
                helpers.bulk(es, actions)

        except Exception as e:
            logging.error(f"Ошибка индексации товаров в Elasticsearch: {e}")
            raise
        finally:
            cursor.close()
            logging.info("Подключение к базе данных закрыто после индексации товаров")

    def find_similar_products(self, product_uuid, product_data, max_results=5):
        query = {
            "more_like_this": {
                "fields": ["title", "description", "features"],
                "like": [{"_id": product_uuid}],
                "min_term_freq": 1,
                "max_query_terms": 12,
            }
        }

        result = self.es.search(
            index="products", body={"query": query}, size=max_results
        )

        # Преобразование идентификаторов в UUID
        similar_products = [uuid.UUID(hit["_id"]) for hit in result["hits"]["hits"]]

        return similar_products
