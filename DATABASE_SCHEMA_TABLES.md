# MOBSTORE DATABASE SCHEMA

## Table 1: auth_user (Django Built-in)

| Column Name | Data Type | Size | Constraints | Description |
|---|---|---|---|---|
| id | int | 11 | Primary Key | User ID |
| username | varchar | 150 | Unique, Not Null | Login username |
| email | varchar | 254 | Nullable | User email |
| password | varchar | 128 | Not Null | Hashed password |
| is_staff | boolean | 1 | Not Null | Admin access flag |
| is_active | boolean | 1 | Not Null | Active account flag |
| date_joined | datetime | — | Not Null | Account creation date |

## Table 2: store_category

| Column Name | Data Type | Size | Constraints | Description |
|---|---|---|---|---|
| id | int | 11 | Primary Key | Category ID |
| name | varchar | 120 | Unique, Not Null | Product category name |
| description | text | — | Nullable | Category description |
| slug | varchar | 120 | Unique, Not Null | URL-friendly slug |

## Table 3: store_product

| Column Name | Data Type | Size | Constraints | Description |
|---|---|---|---|---|
| id | int | 11 | Primary Key | Product ID |
| name | varchar | 255 | Not Null | Product name |
| brand | varchar | 120 | Nullable | Brand name |
| category_id | int | 11 | Foreign Key, Not Null | Linked category ID |
| price | decimal | 10,2 | Not Null | Product price |
| description | text | — | Nullable | Product description |
| image | varchar | 255 | Nullable | Product image path |
| stock | int | 11 | Not Null | Available stock quantity |
| created_at | datetime | — | Not Null | Creation timestamp |

## Table 4: store_cart

| Column Name | Data Type | Size | Constraints | Description |
|---|---|---|---|---|
| id | int | 11 | Primary Key | Cart item ID |
| user_id | int | 11 | Foreign Key, Not Null | Linked user ID |
| product_id | int | 11 | Foreign Key, Not Null | Linked product ID |
| quantity | int | 11 | Not Null | Item quantity in cart |
| updated_at | datetime | — | Not Null | Last update timestamp |

## Table 5: store_order

| Column Name | Data Type | Size | Constraints | Description |
|---|---|---|---|---|
| id | int | 11 | Primary Key | Order ID |
| user_id | int | 11 | Foreign Key, Not Null | Customer user ID |
| order_date | datetime | — | Not Null | Order creation timestamp |
| total_price | decimal | 10,2 | Not Null | Order total amount |
| delivery_address | text | — | Nullable | Delivery address |
| phone_number | varchar | 20 | Nullable | Phone number |
| status | varchar | 20 | Not Null | Status: pending/processing/shipped/delivered/cancelled |

## Table 6: store_orderitem

| Column Name | Data Type | Size | Constraints | Description |
|---|---|---|---|---|
| id | int | 11 | Primary Key | Order item ID |
| order_id | int | 11 | Foreign Key, Not Null | Linked order ID |
| product_id | int | 11 | Foreign Key, Nullable | Linked product ID (can be NULL if deleted) |
| quantity | int | 11 | Not Null | Item quantity |
| price | decimal | 10,2 | Not Null | Item price at purchase |

## Table 7: store_userprofile

| Column Name | Data Type | Size | Constraints | Description |
|---|---|---|---|---|
| id | int | 11 | Primary Key | Profile ID |
| user_id | int | 11 | Foreign Key, Unique | Linked user ID (one-to-one) |
| delivery_address | text | — | Nullable | Saved delivery address |
| phone_number | varchar | 20 | Nullable | Saved phone number |
