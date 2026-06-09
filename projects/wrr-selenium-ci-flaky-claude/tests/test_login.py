from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestLogin:
    def setup_method(self):
        self.driver = webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, 5)

    def test_login_success(self):
        self.driver.get("http://localhost:8080/login")
        # BUG: no explicit wait for element, relies on implicit timing
        self.driver.find_element(By.ID, "username").send_keys("admin")
        self.driver.find_element(By.ID, "password").send_keys("password")
        self.driver.find_element(By.ID, "submit").click()
        # BUG: assert happens before page loads
        assert "Dashboard" in self.driver.title

    def teardown_method(self):
        self.driver.quit()
