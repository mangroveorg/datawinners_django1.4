# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
from pages.createprojectpage.create_project_page import CreateProjectPage
from pages.dashboardpage.dashboard_locator import *
from pages.page import Page


class DashboardPage(Page):
    def __init__(self, driver):
        Page.__init__(self, driver)

    def navigate_to_create_project_page(self):
        self.driver.find(CREATE_PROJECT_LINK).click()
        return CreateProjectPage(self.driver)
