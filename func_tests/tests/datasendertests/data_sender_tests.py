import unittest
from nose.plugins.attrib import attr
from framework.base_test import setup_driver, teardown_driver
from framework.utils.data_fetcher import fetch_, from_
from pages.datasenderpage.data_sender_page import DataSenderPage
from pages.loginpage.login_page import LoginPage
from pages.websubmissionpage.web_submission_page import WebSubmissionPage
from testdata.test_data import DATA_WINNER_LOGIN_PAGE, ALL_DATA_PAGE
from tests.addsubjecttests.add_subject_data import VALID_DATA, SUCCESS_MSG
from tests.datasendertests.data_sender_data import PAGE_TITLE, SECTION_TITLE, SUBJECT_TYPE
from tests.logintests.login_data import DATA_SENDER_CREDENTIALS
from tests.websubmissiontests.web_submission_data import DEFAULT_ORG_DATA, PROJECT_NAME, VALID_ANSWERS


class DataSenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = setup_driver()
        cls.driver.go_to(DATA_WINNER_LOGIN_PAGE)
        login_page = LoginPage(cls.driver)
        login_page.login_with(DATA_SENDER_CREDENTIALS)

    def setUp(self):
        self.driver.go_to(ALL_DATA_PAGE)
        self.data_sender_page = DataSenderPage(self.driver)

    @classmethod
    def tearDownClass(cls):
        teardown_driver(cls.driver)

    @attr("functional_test")
    def test_go_back_to_project_list_from_data_submission_page(self):
        web_submission_page = self.data_sender_page.send_in_data()
        self.driver.wait_for_page_with_title(5, web_submission_page.get_title())
        web_submission_page.go_back_to_project_list()
        data_sender_page = DataSenderPage(self.driver)
        self.assertIsNotNone(data_sender_page.get_project_list())

    @attr("functional_test")
    def test_cancel_link_in_data_submission(self):
        web_submission_page = self.data_sender_page.send_in_data()
        self.driver.wait_for_page_with_title(5, web_submission_page.get_title())
        web_submission_page.fill_questionnaire_with(VALID_ANSWERS)
        warning_dialog = web_submission_page.cancel_submission()
        warning_dialog.cancel()
        web_submission_page = WebSubmissionPage(self.driver)
        self.assertEquals(web_submission_page.get_project_name(), fetch_(PROJECT_NAME, from_(DEFAULT_ORG_DATA)))
        warning_dialog = web_submission_page.cancel_submission()
        warning_dialog.confirm()
        data_sender_page = DataSenderPage(self.driver)
        self.assertIsNotNone(data_sender_page.get_project_list())

    @attr("functional_test")
    def test_register_subject(self):
        add_subject_page = self.data_sender_page.register_subject()
        self.assertEquals(add_subject_page.get_title(), PAGE_TITLE)
        self.assertEquals(add_subject_page.get_section_title(), SECTION_TITLE)
        self.assertEquals(add_subject_page.get_subject_type(), SUBJECT_TYPE)
        add_subject_page.add_subject_with(VALID_DATA)
        add_subject_page.submit_subject()
        message = fetch_(SUCCESS_MSG, from_(VALID_DATA))
        self.assertIn(message, add_subject_page.get_flash_message())

    @attr("functional_test")
    def test_go_back_to_project_list_from_register_subject_page(self):
        add_subject_page = self.data_sender_page.register_subject()
        add_subject_page.go_back_to_project_list()
        data_sender_page = DataSenderPage(self.driver)
        self.assertIsNotNone(data_sender_page.get_project_list())

    @attr("functional_test")
    def test_navigation_via_navigate_bar(self):
        web_submission_page = self.data_sender_page.send_in_data()
        self.driver.wait_for_page_with_title(5, web_submission_page.get_title())
        web_submission_page.navigate_to_project_list()
        data_sender_page = DataSenderPage(self.driver)
        self.assertIsNotNone(data_sender_page.get_project_list())

        web_submission_page = self.data_sender_page.send_in_data()
        smart_phone_instruction_page = data_sender_page.navigate_to_smart_phone_instruction()
        self.assertIsNotNone(smart_phone_instruction_page.get_smart_phone_instruction())

        smart_phone_instruction_page.navigate_to_project_list()
        self.assertIsNotNone(data_sender_page.get_project_list())

        web_submission_page = data_sender_page.send_in_data()
        smart_phone_instruction_page = web_submission_page.navigate_to_smart_phone_instruction()
        self.assertIsNotNone(smart_phone_instruction_page.get_smart_phone_instruction())

        smart_phone_instruction_page.navigate_to_project_list()
        data_sender_page = DataSenderPage(self.driver)
        add_subject_page = data_sender_page.register_subject()
        smart_phone_instruction_page = add_subject_page.navigate_to_smart_phone_instruction()
        self.assertIsNotNone(smart_phone_instruction_page.get_smart_phone_instruction())

    @attr("functional_test")
    def test_go_back_to_project_list_directly_when_user_cancel_submission_without_fill_out_form(self):
        web_submission_page = self.data_sender_page.send_in_data()
        web_submission_page.cancel_submission()
        data_sender_page = DataSenderPage(self.driver)
        self.assertIsNotNone(data_sender_page.get_project_list())
