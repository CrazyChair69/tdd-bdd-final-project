######################################################################
# Copyright 2016, 2023 John J. Rofrano. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
######################################################################
"""
Product API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
  codecov --token=$CODECOV_TOKEN

  While debugging just these tests it's convenient to use this:
    nosetests --stop tests/test_service.py:TestProductService
"""
import os
import logging
from decimal import Decimal
from unittest import TestCase
from urllib.parse import quote_plus
from service import app
from service.common import status
from service.models import db, init_db, Product, Category
from tests.factories import ProductFactory

# Disable all but critical errors during normal test run
# uncomment for debugging failing tests
# logging.disable(logging.CRITICAL)

# DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///../db/test.db')
DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)
BASE_URL = "/products"


######################################################################
#  T E S T   C A S E S
######################################################################
# pylint: disable=too-many-public-methods
class TestProductRoutes(TestCase):
    """Product Service tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Run once after all tests"""
        db.session.close()

    def setUp(self):
        """Runs before each test"""
        self.client = app.test_client()
        db.session.query(Product).delete()  # clean up the last tests
        db.session.commit()

    def tearDown(self):
        db.session.remove()

    ############################################################
    # Utility function to bulk create products
    ############################################################
    def _create_products(self, count: int = 1) -> list:
        """Factory method to create products in bulk"""
        products = []
        for _ in range(count):
            test_product = ProductFactory()
            response = self.client.post(BASE_URL, json=test_product.serialize())
            self.assertEqual(
                response.status_code, status.HTTP_201_CREATED, "Could not create test product"
            )
            new_product = response.get_json()
            test_product.id = new_product["id"]
            products.append(test_product)
        return products

    ############################################################
    #  T E S T   C A S E S
    ############################################################
    def test_index(self):
        """It should return the index page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"Product Catalog Administration", response.data)

    def test_health(self):
        """It should be healthy"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data['message'], 'OK')

    # ----------------------------------------------------------
    # TESTS: Create a product
    # ----------------------------------------------------------
    def test_create_product(self):
        """It should Create a new Product"""
        test_product = ProductFactory()
        logging.debug("Test Product: %s", test_product.serialize())
        response = self.client.post(BASE_URL, json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)
        # Check the data is correct
        new_product = response.get_json()
        self.assertEqual(new_product["name"], test_product.name)
        self.assertEqual(new_product["description"], test_product.description)
        self.assertEqual(Decimal(new_product["price"]), test_product.price)
        self.assertEqual(new_product["available"], test_product.available)
        self.assertEqual(new_product["category"], test_product.category.name)
        # Check that the location header was correct
        response = self.client.get(location)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_product = response.get_json()
        logging.debug("new_product: %s", new_product)
        self.assertEqual(new_product["name"], test_product.name)
        self.assertEqual(new_product["description"], test_product.description)
        self.assertEqual(Decimal(new_product["price"]), test_product.price)
        self.assertEqual(new_product["available"], test_product.available)
        self.assertEqual(new_product["category"], test_product.category.name)

    def test_create_product_with_no_name(self):
        """It should not Create a Product without a name"""
        product = self._create_products()[0]
        new_product = product.serialize()
        del new_product["name"]
        logging.debug("Product no name: %s", new_product)
        response = self.client.post(BASE_URL, json=new_product)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_no_content_type(self):
        """It should not Create a Product with no Content-Type"""
        response = self.client.post(BASE_URL, data="bad data")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_create_product_wrong_content_type(self):
        """It should not Create a Product with wrong Content-Type"""
        response = self.client.post(BASE_URL, data={}, content_type="plain/text")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # ----------------------------------------------------------
    # TESTS: Read a product
    # ----------------------------------------------------------
    def test_read_product(self):
        """It should read a product"""
        product = self._create_products()[0]
        response = self.client.get(f"{BASE_URL}/{product.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_json = response.get_json()
        read_product = Product()
        read_product.deserialize(response_json)
        # Set ID separately because deserialize()
        # doesn't deserialize ID of product
        read_product.id = response_json["id"]
        self.assertEqual(read_product.id, product.id)
        self.assertEqual(read_product.name, product.name)
        self.assertEqual(read_product.description, product.description)
        self.assertEqual(read_product.price, product.price)
        self.assertEqual(read_product.available, product.available)
        self.assertEqual(read_product.category, product.category)

    def test_read_product_not_found(self):
        """It should return error status code when no product could be read"""
        invalid_product_id = 0
        response = self.client.get(f"{BASE_URL}/{invalid_product_id}")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ----------------------------------------------------------
    # TESTS: Update a product
    # ----------------------------------------------------------
    def test_update_product(self):
        """It should update a product"""
        product = self._create_products()[0]
        data = {
            "name": "Update Name",
            "description": "Update Description",
            "price": 69.69,
            "available": True,
            "category": product.category.name
        }
        product.deserialize(data)
        response = self.client.put(f"{BASE_URL}/{product.id}", json=product.serialize())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_json = response.get_json()
        updated_product = Product()
        updated_product.deserialize(response_json)
        # Set ID separately because deserialize()
        # doesn't deserialize ID of product
        updated_product.id = response_json["id"]
        self.assertEqual(updated_product.id, product.id)
        self.assertEqual(updated_product.name, product.name)
        self.assertEqual(updated_product.description, product.description)
        self.assertEqual(updated_product.price, product.price)
        self.assertEqual(updated_product.available, product.available)
        self.assertEqual(updated_product.category, product.category)

    def test_update_product_wrong_content_type(self):
        """It should not update a product with wrong content-type"""
        response = self.client.put(f"{BASE_URL}/{1}", data={}, content_type="plain/text")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_update_product_no_content_type(self):
        """It should not update a product with no content-type"""
        response = self.client.put(f"{BASE_URL}/{1}", data="bad data")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_update_product_id_not_found(self):
        """It should not update a product if product ID not found"""
        product = self._create_products()[0]
        id_not_found = product.id + 1
        self.assertNotEqual(product.id, id_not_found)
        product.id = id_not_found
        response = self.client.put(f"{BASE_URL}/{product.id}", json=product.serialize())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ----------------------------------------------------------
    # TESTS: Delete a product
    # ----------------------------------------------------------
    def test_delete_product(self):
        """It should delete a product"""
        product = self._create_products()[0]
        response = self.client.delete(f"{BASE_URL}/{product.id}", json=product.serialize())
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Data of response as text. Otherwise, it returns 'b""' and not just '""'
        self.assertEqual(response.get_data(as_text=True), "")
        self.assertEqual(Product.find(product.id), None)
        self.assertEqual(len(Product.all()), 0)

    def test_delete_product_wrong_content_type(self):
        """It should not delete a product with wrong content-type"""
        response = self.client.delete(f"{BASE_URL}/{1}", data={}, content_type="plain/text")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_delete_product_no_content_type(self):
        """It should not delete a product with no content-type"""
        response = self.client.delete(f"{BASE_URL}/{1}", data="bad data")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_delete_product_id_not_found(self):
        """It should not delete a product if product ID not found"""
        product = self._create_products()[0]
        id_not_found = product.id + 1
        self.assertNotEqual(product.id, id_not_found)
        product.id = id_not_found
        response = self.client.delete(f"{BASE_URL}/{product.id}", json=product.serialize())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ----------------------------------------------------------
    # TESTS: List all products
    # ----------------------------------------------------------
    def test_list_all_products(self):
        """It should list all products"""
        product_count = 5
        self._create_products(product_count)
        response = self.client.get(f"{BASE_URL}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.get_json()
        self.assertEqual(len(response_data), product_count)

    def test_list_all_products_no_products_found(self):
        """It should return no list but a status code when no products in database"""
        response = self.client.get(f"{BASE_URL}")
        self.assertEqual(len(Product.all()), 0)
        self.assertEqual(len(response.get_data()), 0)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # ----------------------------------------------------------
    # TESTS: List by name
    # ----------------------------------------------------------
    def test_list_by_name(self):
        """It should return a list of products with requested name"""
        products = self._create_products(20)
        # Use name of first product as a baseline for validation
        first_product_name = products[0].name
        response = self.client.get(
            BASE_URL,
            query_string=f"name={quote_plus(first_product_name)}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.get_json()
        # Compare number of occurrences
        expected_occurrences = 0
        for product in products:
            if product.name == first_product_name:
                expected_occurrences += 1
        self.assertEqual(len(response_data), expected_occurrences)
        # Every product from query should have the requested name
        for product in response_data:
            self.assertEqual(product["name"], first_product_name)

    def test_list_by_name_no_products_found(self):
        """
        It should return no list but a status code
        when no products with requested name found
        """
        test_name = "blabla"
        response = self.client.get(
            BASE_URL,
            query_string=f"name={quote_plus(test_name)}"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(response.get_data()), 0)

    # ----------------------------------------------------------
    # TESTS: List by category
    # ----------------------------------------------------------
    def test_list_by_category(self):
        """It should return a list of products with requested category"""
        products = self._create_products(20)
        # Use category of first product as a baseline for validation
        first_product_category = products[0].category
        response = self.client.get(
            BASE_URL,
            query_string=f"category={quote_plus(first_product_category.name)}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.get_json()
        # Compare number of occurrences
        expected_occurrences = 0
        for product in products:
            if product.category == first_product_category:
                expected_occurrences += 1
        self.assertEqual(len(response_data), expected_occurrences)
        # Every product from query should have the requested category
        for product in response_data:
            self.assertEqual(product["category"], first_product_category.name)

    def test_list_by_category_no_products_found(self):
        """
        It should return no list but a status code
        when no products with requested category found
        """
        test_category = Category.UNKNOWN.name
        response = self.client.get(
            BASE_URL,
            query_string=f"category={quote_plus(test_category)}"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(response.get_data()), 0)

    # ----------------------------------------------------------
    # TESTS: List by availability
    # ----------------------------------------------------------
    def test_list_by_availability(self):
        """It should return a list of products with requested availability"""
        products = self._create_products(20)
        # Use availability of first product as a baseline for validation
        first_product_availability = products[0].available
        response = self.client.get(
            BASE_URL,
            query_string=f"available={quote_plus(str(first_product_availability))}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.get_json()
        # Compare number of occurrences
        expected_occurrences = 0
        for product in products:
            if product.available == first_product_availability:
                expected_occurrences += 1
        self.assertEqual(len(response_data), expected_occurrences)
        # Every product from query should have the requested availability
        for product in response_data:
            self.assertEqual(product["available"], first_product_availability)

    def test_list_by_availability_no_products_found(self):
        """
        It should return no list but a status code
        when no products with requested availability found
        """
        test_available = False
        response = self.client.get(
            BASE_URL,
            query_string=f"available={quote_plus(str(test_available))}"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(response.get_data()), 0)

    ######################################################################
    # Utility functions
    ######################################################################
    def get_product_count(self):
        """save the current number of products"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        # logging.debug("data = %s", data)
        return len(data)
