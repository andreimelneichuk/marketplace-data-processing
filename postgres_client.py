import json
import logging
import uuid
from typing import List

import psycopg2
import psycopg2.extras
from lxml import etree


class PostgresClient:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                dbname="marketplace",
                user="user",
                password="password",
                host="postgres",
                port="5432",
            )
            self.cursor = self.conn.cursor()
            logging.info("Подключение к базе данных установлено")
        except Exception as e:
            logging.error(f"Ошибка подключения к базе данных: {e}")
            raise

    def update_similar_sku(
        self, product_uuid: str, similar_products: List[uuid.UUID]
    ) -> None:
        try:
            if not isinstance(similar_products, list):
                raise ValueError("similar_products должно быть списком UUID")

            similar_products_str = [str(u) for u in similar_products]

            self.cursor.execute(
                """
                UPDATE public.sku
                SET similar_sku = %s::uuid[]
                WHERE uuid = %s
                """,
                (similar_products_str, product_uuid),
            )
            self.conn.commit()
        except Exception as e:
            logging.error(f"Ошибка обновления similar_sku для {product_uuid}: {e}")
            raise

    def create_table_if_not_exists(self):
        try:
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.sku (
                    uuid uuid PRIMARY KEY,
                    marketplace_id integer,
                    product_id bigint,
                    title text,
                    description text,
                    brand text,
                    seller_id integer,
                    seller_name text,
                    category_lvl_1 text,
                    category_lvl_2 text,
                    category_lvl_3 text,
                    features json,
                    price_before_discounts real,
                    price_after_discounts real,
                    inserted_at timestamp default now(),
                    updated_at timestamp default now()
                );
                """
            )
            self.conn.commit()
            logging.info("Таблица public.sku проверена/создана")
        except Exception as e:
            logging.error(f"Ошибка создания таблицы: {e}")
            raise

    def insert_product(self, data):
        try:
            product_id = data.get("product_id")
            if not product_id:
                raise ValueError("Поле product_id отсутствует")

            self.cursor.execute(
                """
                INSERT INTO public.sku (uuid, marketplace_id, product_id, title,
                                        description, brand, category_lvl_1,
                                        category_lvl_2, category_lvl_3, features,
                                        price_before_discounts, price_after_discounts)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    data["marketplace_id"],
                    product_id,
                    data["title"],
                    data["description"],
                    data["brand"],
                    data["category_lvl_1"],
                    data["category_lvl_2"],
                    data["category_lvl_3"],
                    json.dumps(data["features"]),
                    data["price_before_discounts"],
                    data["price_after_discounts"],
                ),
            )
            self.conn.commit()
        except Exception as e:
            logging.error(f"Ошибка вставки продукта {product_id} в базу данных: {e}")
            raise

    def parse_features(self, offer_element):
        features = {}
        for param in offer_element.findall("param"):
            name = param.attrib.get("name")
            value = param.text
            features[name] = value
        logging.debug(f"Извлечены параметры продукта: {features}")
        return features

    def parse_xml_file(self, xml_file, category_mapping):
        self.create_table_if_not_exists()

        logging.info("Начало обработки файла")

        context = etree.iterparse(xml_file, events=("end",), tag="offer")
        batch_size = 100
        batch = []

        try:
            for _, elem in context:
                offer_data = {
                    "marketplace_id": 1,
                    "product_id": int(elem.get("id")),
                    "title": elem.findtext("name"),
                    "description": elem.findtext("description"),
                    "brand": elem.findtext("vendor"),
                    "features": self.parse_features(elem),
                    "price_before_discounts": float(
                        elem.findtext("price", default="0")
                    ),
                    "price_after_discounts": float(elem.findtext("price", default="0")),
                }

                category_id = elem.findtext("categoryId")
                if category_id and category_id.isdigit():
                    category_id = int(category_id)
                    if category_id in category_mapping:
                        category_info = category_mapping[category_id]
                        offer_data["category_lvl_1"] = category_info["category_lvl_1"]
                        offer_data["category_lvl_2"] = category_info["category_lvl_2"]
                        offer_data["category_lvl_3"] = category_info["category_lvl_3"]
                    else:
                        offer_data["category_lvl_1"] = None
                        offer_data["category_lvl_2"] = None
                        offer_data["category_lvl_3"] = None
                else:
                    offer_data["category_lvl_1"] = None
                    offer_data["category_lvl_2"] = None
                    offer_data["category_lvl_3"] = None

                batch.append(offer_data)

                if len(batch) >= batch_size:
                    for item in batch:
                        self.insert_product(item)
                    batch.clear()

                elem.clear()

            if batch:
                for item in batch:
                    self.insert_product(item)
                logging.info(
                    f"Последний пакет из {len(batch)} продуктов добавлен в базу данных"
                )

        except Exception as e:
            logging.error(f"Ошибка при обработке XML файла: {e}")
            raise

    def close(self):
        self.cursor.close()
        self.conn.close()
        logging.info("Подключение к базе данных закрыто")
