import logging

from datawinners.accountmanagement.models import OrganizationSetting
from datawinners.main.database import get_db_manager
from datawinners.project.models import Reminder, Project
from migration.couch.utils import migrate, mark_as_completed


org_ids_with_reminders = [org[0] for org in Reminder.objects.values_list('organization').distinct()]
organization_names = [store[0] for store in OrganizationSetting.objects.filter(organization__in=org_ids_with_reminders).values_list('document_store')]
datastore_org_id_map = dict(zip(organization_names, org_ids_with_reminders))

def remove_reminders_for_deleted_questionnaires(db_name):
    logger = logging.getLogger(db_name)
    try:
       dbm = get_db_manager(db_name)
       org_id = datastore_org_id_map[db_name]
       reminders = Reminder.objects.filter(organization=org_id)
       for reminder in reminders:
           questionnaire = Project.get(dbm, reminder.project_id)
           if questionnaire._doc['void']:
               reminder.delete()
    except Exception as e:
        logger.exception(db_name)
    mark_as_completed(db_name)


migrate(organization_names, remove_reminders_for_deleted_questionnaires, version=(14, 1, 1), threads=1)