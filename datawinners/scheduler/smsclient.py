# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import json
from urllib2 import URLError
import uuid
from django.conf import settings
import logging
from datawinners.scheduler.vumiclient import VumiClient, Connection, VumiInvalidDestinationNumberException
from datawinners.sms.models import SMS, MSG_TYPE_REMINDER
from datawinners.submission.organization_finder import OrganizationFinder
from mangrove.utils.types import is_not_empty
from datawinners.utils import strip_accents
import socket

logger = logging.getLogger("datawinners.reminders")


class NoSMSCException(Exception):
    pass


def log_sms(to_tel, from_tel, message, organization, message_id, transport_name, message_type):
    SMS(message= message,
        message_id=message_id,
        organization=organization,
        msg_from = from_tel,
        msg_to= to_tel,
        smsc = transport_name,
        msg_type = message_type,
        status="Submitted").save()


class SMSClient(object):

    def send_sms(self,from_tel,to_tel, message, message_type="Unknown"):
        message = strip_accents(message)
        if is_not_empty(from_tel):
            organization_setting = OrganizationFinder().find_organization_setting(from_tel)
            is_there_orgnization_with_to_number = OrganizationFinder().find_organization_setting(to_tel) != None
            if (is_there_orgnization_with_to_number): return False
            smsc = None
            if organization_setting is not None and organization_setting.outgoing_number is not None:
                smsc = organization_setting.outgoing_number.smsc
            if smsc is None:
                logger.error("No SMSC configured for %s" % organization_setting.organization.org_id)
                raise NoSMSCException()
            socket.setdefaulttimeout(10)
            logger.debug("Posting sms to %s" % settings.VUMI_API_URL)
            if settings.USE_NEW_VUMI:
                client = VumiApiClient(connection=Connection(smsc.vumi_username, smsc.vumi_username, base_url=settings.VUMI_API_URL))
                sms_response = client.send_sms(to_addr=to_tel, from_addr=from_tel, content=message.encode('utf-8'),
                    transport_name=smsc.vumi_username)
                return sms_response[0]
            else:
                try:
                    client = VumiClient(None, None, connection=Connection(smsc.vumi_username, smsc.vumi_username, base_url=settings.VUMI_API_URL))
                    client.debug = True
                    resp = client.send_sms(to_msisdn=to_tel,from_msisdn=from_tel, message=message.encode('utf-8'))
                    response_object = json.loads(resp.content)
                    if (response_object):
                        log_sms(to_tel, from_tel, message, organization_setting.organization,
                                response_object[0].get('id'), smsc.vumi_username,message_type)
                    return True
                except (URLError, VumiInvalidDestinationNumberException) as err:
                    logger.exception('Unable to send sms. %s' %err)
                    return False
        return False

    def send_reminder(self,from_number, on_date, project, reminder, dbm):
        count = 0
        for data_sender in reminder.get_sender_list(project, on_date,dbm):
            sms_sent = self.send_sms(from_number, data_sender["mobile_number"], reminder.message, MSG_TYPE_REMINDER)
            if sms_sent:
                count += 1
                reminder.log(dbm, project.id, on_date, number_of_sms=1, to_number=data_sender["mobile_number"])
            logger.info("Reminder sent for %s, Message: %s" % (data_sender["mobile_number"],reminder.message,) )
        return count

class VumiApiClient(object):

    def __init__(self, connection):
        self.connection = connection

    def send_sms(self, **kwargs):
        try:
            response = self.connection.post('/', kwargs)
            return True, response
        except URLError as err:
            logger.exception('Unable to send sms. %s' %err)
            return False, 'Unable to send sms'
