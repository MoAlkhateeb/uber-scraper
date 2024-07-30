import csv
import time
import os
import re
import datetime
from typing import List, Dict
from dotenv import load_dotenv
from scraper import Scraper
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class UberScraper(Scraper):
    LOGIN_URL = "https://auth.uber.com/v2/"
    SEARCH_URL = "https://m.uber.com/looking"

    def __init__(self, proxy_list: List[str] = None, proxy_rotation_threshold: int = 6):
        super().__init__(
            proxy_list=proxy_list,
            proxy_rotation_threshold=proxy_rotation_threshold,
            cookies_path="uber_cookies.pkl",
        )
        self.delay = 5

    def authenticate(self, phone_number: str, password: str) -> None:
        print(f"[{datetime.datetime.now()}]: Authentication called")
        self.web_get(self.LOGIN_URL)

        max_attempts = 3
        for attempt in range(max_attempts):
            if self._check_if_logged_in():
                return
            try:
                self._enter_phone_number(phone_number)
                use_password = self._check_password_option()

                if use_password:
                    self._enter_password(password)
                else:
                    self._handle_otp(password)

                self.current_driver.find_element(value="forward-button").click()
                self.web_get(self.SEARCH_URL)
                self.save_cookies()
                return
            except Exception as e:
                print(f"Authentication attempt {attempt + 1} failed: {e}")
                if attempt == max_attempts - 1:
                    raise Exception("Authentication failed after multiple attempts")

    def get_price(
        self, pickup_lat: float, pickup_long: float, drop_lat: float, drop_long: float
    ) -> None:
        print(f"[{datetime.datetime.now()}]: Getting Prices!")
        link = self._generate_link(pickup_lat, pickup_long, drop_lat, drop_long)
        self.web_get(link)

        if not self._check_if_logged_in():
            raise Exception("Not logged in. Please authenticate first.")

        try:
            ride_types = self._get_ride_types()
            if not ride_types:
                raise Exception("No ride types found")
            for ride_type in ride_types:
                ride_data = self._extract_ride_data(ride_type)
                self._save_ride_data(ride_data)

            self.save_cookies()
        except Exception as e:
            print(f"Error getting prices: {e}")
            raise

    def _check_if_logged_in(self) -> bool:
        try:
            WebDriverWait(self.current_driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "._css-ipKQbc"))
            )
            return True
        except TimeoutException:
            return False

    def _enter_phone_number(self, phone_number: str) -> None:
        try:
            phone_number_box = self.current_driver.find_element(
                value="PHONE_NUMBER_or_EMAIL_ADDRESS"
            )
            phone_number_box.click()
            phone_number_box.send_keys(phone_number)
            self.current_driver.find_element(value="forward-button").click()
        except NoSuchElementException as e:
            print(f"Error entering phone number: {e}")
            raise

    def _check_password_option(self) -> bool:
        try:
            use_password = WebDriverWait(self.current_driver, self.delay).until(
                EC.presence_of_element_located((By.ID, "alt-PASSWORD"))
            )
            print(f"[{datetime.datetime.now()}]: Using Password Instead of OTP!")
            use_password.click()
            return True
        except TimeoutException:
            print(f"[{datetime.datetime.now()}]: OTP Required!")
            return False

    def _enter_password(self, password: str) -> None:
        try:
            password_box = WebDriverWait(self.current_driver, self.delay).until(
                EC.presence_of_element_located((By.ID, "PASSWORD"))
            )
            password_box.click()
            password_box.send_keys(password)
        except TimeoutException as e:
            print(f"Error entering password: {e}")
            raise

    def _handle_otp(self, password: str) -> None:
        try:
            first_field = WebDriverWait(self.current_driver, self.delay).until(
                EC.presence_of_element_located((By.ID, "PHONE_SMS_OTP-0"))
            )
            first_field.click()
            first_field.send_keys(input("Enter OTP: "))
            self._enter_password(password)
        except TimeoutException as e:
            print(f"Error handling OTP: {e}")
            raise

    def _get_ride_types(self) -> List:
        try:
            ul = WebDriverWait(self.current_driver, self.delay).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//ul[contains(@class, 'css-')]")
                )
            )
            return ul.find_elements(By.CSS_SELECTOR, "li")
        except TimeoutException as e:
            print(f"Error getting ride types: {e}")
            raise

    def _extract_ride_data(self, ride_type) -> Dict[str, str]:
        ride_type.click()
        time.sleep(1)  # Allow time for data to load

        selectors = {
            "ride_name": "h6._css-eMXiub:nth-child(1)",
            "ride_estimate": "h6._css-eMXiub:nth-child(2)",
            "base_fare": "div._css-kROmvp:nth-child(2) > p:nth-child(2)",
            "minimum_fare": "div._css-kROmvp:nth-child(3) > p:nth-child(2)",
            "plus_per_minute": "div._css-kROmvp:nth-child(4) > p:nth-child(2)",
            "plus_per_kilometer": "div._css-kROmvp:nth-child(5) > p:nth-child(2)",
        }

        ride_data = {}
        for key, selector in selectors.items():
            try:
                ride_data[key] = self._get_element_text(selector)
            except Exception as e:
                print(f"Error extracting {key}: {e}")
                ride_data[key] = "N/A"

        ride_data["wait_charge"] = self._get_wait_charge()
        return ride_data

    def _get_element_text(self, css_selector: str) -> str:
        try:
            return (
                WebDriverWait(self.current_driver, self.delay)
                .until(EC.presence_of_element_located((By.CSS_SELECTOR, css_selector)))
                .text
            )
        except TimeoutException as e:
            print(f"Error getting element text for selector {css_selector}: {e}")
            raise

    def _get_wait_charge(self) -> str:
        try:
            wait_charge_text = self._get_element_text("._css-lcvSVT")
            match = re.search(r"EGP (\d+\.\d+)", wait_charge_text)
            return match.group(0) if match else "N/A"
        except Exception as e:
            print(f"Error getting wait charge: {e}")
            return "N/A"

    def _save_ride_data(self, ride_data: Dict[str, str]) -> None:
        print(f"[{datetime.datetime.now()}]: Saving {ride_data['ride_name']} data!")
        filename = os.path.join("csv", "uber", f"{ride_data['ride_name']}.csv")
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, "a", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "date",
                    "time",
                    "trip_estimate",
                    "base_fare",
                    "minimum_fare",
                    "plus_per_minute",
                    "plus_per_kilometer",
                    "wait_charge",
                ],
            )
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow(
                {
                    "date": str(datetime.datetime.now().date()),
                    "time": str(datetime.datetime.now().time()),
                    "trip_estimate": ride_data["ride_estimate"],
                    "base_fare": ride_data["base_fare"],
                    "minimum_fare": ride_data["minimum_fare"],
                    "plus_per_minute": ride_data["plus_per_minute"],
                    "plus_per_kilometer": ride_data["plus_per_kilometer"],
                    "wait_charge": ride_data["wait_charge"],
                }
            )

    @staticmethod
    def _generate_link(
        pickup_lat: float, pickup_long: float, drop_lat: float, drop_long: float
    ) -> str:
        return (
            f'https://m.uber.com/looking?drop[0]={{"latitude":{drop_lat},"longitude":{drop_long}}}'
            f'&pickup={{"latitude":{pickup_lat},"longitude":{pickup_long}}}'
        )


def run(
    scraper: UberScraper,
    phone_number: str,
    uber_password: str,
    drop_lat: float,
    drop_long: float,
    pickup_lat: float,
    pickup_long: float,
) -> None:
    try:
        scraper.get_price(
            drop_lat=drop_lat,
            drop_long=drop_long,
            pickup_lat=pickup_lat,
            pickup_long=pickup_long,
        )
    except Exception as e:
        print(f"Error occurred: {e}. Attempting to authenticate and retry.")
        scraper.authenticate(phone_number, uber_password)
        scraper.get_price(
            drop_lat=drop_lat,
            drop_long=drop_long,
            pickup_lat=pickup_lat,
            pickup_long=pickup_long,
        )


if __name__ == "__main__":
    load_dotenv()

    uber_phonenumber = os.getenv("UBER_PHONE_NUMBER")
    uber_password = os.getenv("UBER_PASSWORD")

    scraper = UberScraper()

    run(
        scraper=scraper,
        phone_number=uber_phonenumber,
        uber_password=uber_password,
        drop_lat=30.0249469,
        drop_long=30.8969389,
        pickup_lat=30.0272027,
        pickup_long=31.1384884,
    )
