CREATE TABLE public.sku
(
    uuid                   uuid PRIMARY KEY,
    marketplace_id         integer,
    product_id             bigint,
    title                  text,
    description            text,
    brand                  text,
    seller_id              integer,
    seller_name            text,
    first_image_url        text,
    category_id            integer,
    category_lvl_1         text,
    category_lvl_2         text,
    category_lvl_3         text,
    category_remaining     text,
    features               json,
    rating_count           integer,
    rating_value           double precision,
    price_before_discounts real,
    discount               double precision,
    price_after_discounts  real,
    bonuses                integer,
    sales                  integer,
    inserted_at            timestamp default now(),
    updated_at             timestamp default now(),
    currency               text,
    barcode                bigint,
    similar_sku            uuid[]
);

CREATE INDEX sku_brand_index
    ON public.sku (brand);

CREATE UNIQUE INDEX sku_marketplace_product_uindex
    ON public.sku (marketplace_id, product_id);

CREATE UNIQUE INDEX sku_uuid_uindex
    ON public.sku (uuid);

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_timestamp
BEFORE UPDATE ON public.sku
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();