import logging

import psycopg2

from elasticsearch_client import ElasticsearchClient
from postgres_client import PostgresClient


def get_categories_mapping() -> dict:
    conn = psycopg2.connect(
        host="postgres", database="marketplace", user="user", password="password"
    )
    cur = conn.cursor()

    cur.execute(
        """
        SELECT category_id, category_lvl_1, category_lvl_2, category_lvl_3, \
            category_remaining
        FROM sku
    """
    )
    categories = cur.fetchall()
    cur.close()
    conn.close()

    category_mapping = {
        cat[0]: {
            "category_lvl_1": cat[1],
            "category_lvl_2": cat[2],
            "category_lvl_3": cat[3],
            "category_remaining": cat[4],
        }
        for cat in categories
    }
    return category_mapping


def process_offer(offer: dict, category_mapping: dict) -> dict:
    category_id = offer.get("categoryId")

    if category_id in category_mapping:
        category_info = category_mapping[category_id]
        offer["category_lvl_1"] = category_info["category_lvl_1"]
        offer["category_lvl_2"] = category_info["category_lvl_2"]
        offer["category_lvl_3"] = category_info["category_lvl_3"]
        offer["category_remaining"] = category_info["category_remaining"]
    else:
        offer["category_lvl_1"] = None
        offer["category_lvl_2"] = None
        offer["category_lvl_3"] = None
        offer["category_remaining"] = None

    return offer


def main():
    logging.basicConfig(level=logging.INFO)

    pg_client = PostgresClient()
    es_client = ElasticsearchClient()

    # Загрузить и проиндексировать товары
    offers_file_path = "offers.xml"
    category_mapping = get_categories_mapping()
    pg_client.parse_xml_file(offers_file_path, category_mapping)
    es_client.index_products_to_es(pg_client)

    # Пройтись по каждому товару, найти похожие и обновить поле similar_sku
    cursor = pg_client.conn.cursor()
    cursor.execute("SELECT uuid, title, description, features FROM public.sku")
    logging.info("Начало обработки похожих товаров")
    for product in cursor.fetchall():
        product_uuid = product[0]
        logging.info(f"Product {product_uuid}")
        product_data = {
            "title": product[1],
            "description": product[2],
            "features": product[3],
        }

        # Поиск похожих товаров
        similar_products = es_client.find_similar_products(product_uuid, product_data)

        # Обновление поля similar_sku
        pg_client.update_similar_sku(product_uuid, similar_products)

    pg_client.close()
    logging.info("Обработка завершена!")


if __name__ == "__main__":
    main()
