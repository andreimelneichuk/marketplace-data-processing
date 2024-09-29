import uuid
import psycopg2
import psycopg2.extras
from lxml import etree
from elasticsearch import Elasticsearch, helpers
import json
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

def connect_db():
    try:
        conn = psycopg2.connect(
            dbname="marketplace", user="user", password="password", host="postgres", port="5432"
        )
        logging.info("Подключение к базе данных установлено")
        return conn
    except Exception as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")
        raise

def create_table_if_not_exists(cursor):
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public.sku (
                uuid uuid PRIMARY KEY,
                marketplace_id integer,
                product_id bigint,
                title text,
                description text,
                brand text,
                seller_id integer,
                seller_name text,
                first_image_url text,
                category_id integer,
                category_lvl_1 text,
                category_lvl_2 text,
                category_lvl_3 text,
                category_remaining text,
                features json,
                rating_count integer,
                rating_value double precision,
                price_before_discounts real,
                discount double precision,
                price_after_discounts real,
                bonuses integer,
                sales integer,
                inserted_at timestamp default now(),
                updated_at timestamp default now(),
                currency text,
                barcode bigint,
                similar_sku uuid[]
            );
        """)
        logging.info("Таблица public.sku проверена/создана")
    except Exception as e:
        logging.error(f"Ошибка создания таблицы: {e}")
        raise

def insert_product(cursor, data):
    try:
        cursor.execute(
            """
            INSERT INTO public.sku (uuid, marketplace_id, product_id, title, description, brand, category_lvl_1, 
                                    category_lvl_2, category_lvl_3, features, price_before_discounts, price_after_discounts)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()), data['marketplace_id'], data['product_id'], data['title'], data['description'],
                data['brand'], data['category_lvl_1'], data['category_lvl_2'], data['category_lvl_3'],
                json.dumps(data['features']), data['price_before_discounts'], data['price_after_discounts']
            )
        )
        #logging.info(f"Продукт {data['product_id']} добавлен в базу данных")
    except Exception as e:
        logging.error(f"Ошибка вставки продукта {data['product_id']} в базу данных: {e}")
        raise

def parse_features(offer_element):
    features = {}
    for param in offer_element.findall('param'):
        name = param.attrib.get('name')
        value = param.text
        features[name] = value
    logging.debug(f"Извлечены параметры продукта: {features}")
    return features

def parse_xml_file(xml_file):
    conn = connect_db()
    cursor = conn.cursor()
    
    create_table_if_not_exists(cursor)
    
    context = etree.iterparse(xml_file, events=('end',), tag='offer')
    batch_size = 100
    batch = []

    try:
        for event, elem in context:
            data = {
                'marketplace_id': 1,
                'product_id': int(elem.get('id')),
                'title': elem.findtext('name'),
                'description': elem.findtext('description'),
                'brand': elem.findtext('vendor'),
                'category_lvl_1': '',
                'category_lvl_2': '',
                'category_lvl_3': '',
                'features': parse_features(elem),
                'price_before_discounts': float(elem.findtext('price', default='0')),
                'price_after_discounts': float(elem.findtext('price', default='0'))
            }
            batch.append(data)
            
            if len(batch) >= batch_size:
                for item in batch:
                    insert_product(cursor, item)
                conn.commit()
                #logging.info(f"Пакет из {len(batch)} продуктов добавлен в базу данных")
                batch.clear()  # Очистите пакет после обработки
                
            elem.clear()

        if batch:
            for item in batch:
                insert_product(cursor, item)
            conn.commit()
            logging.info(f"Последний пакет из {len(batch)} продуктов добавлен в базу данных")
    
    except Exception as e:
        logging.error(f"Ошибка при обработке XML файла: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
        logging.info("Подключение к базе данных закрыто")

def index_products_to_es(batch_size=500):
    conn = connect_db()
    cursor = conn.cursor(name='products_cursor', cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT uuid, marketplace_id, product_id, title, description, brand, features FROM public.sku")

    es = Elasticsearch(
        hosts=["http://elasticsearch:9200"],
        headers={"Content-Type": "application/json"}
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
                    '_index': 'products',
                    '_id': row['uuid'],
                    '_source': {
                        'uuid': row['uuid'],
                        'marketplace_id': row['marketplace_id'],
                        'product_id': row['product_id'],
                        'title': row['title'],
                        'description': row['description'],
                        'brand': row['brand'],
                        'features': row['features']  # Поле features в формате JSON
                    }
                }
                actions.append(doc)
            helpers.bulk(es, actions)
            #logging.info(f"Пакет из {len(actions)} товаров проиндексирован в Elasticsearch")
    
    except Exception as e:
        logging.error(f"Ошибка индексации товаров в Elasticsearch: {e}")
        raise
    finally:
        cursor.close()
        conn.close() 
        logging.info("Подключение к базе данных закрыто после индексации товаров")

if __name__ == "__main__":
    logging.info("Начало обработки XML файла и индексации товаров")
    try:
        parse_xml_file('offers.xml')
        index_products_to_es()
        logging.info("Обработка завершена успешно")
    except Exception as e:
        logging.error(f"Критическая ошибка в процессе выполнения: {e}")