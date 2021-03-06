# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
from copy import copy
import os
import logging

from django.conf import settings
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.contrib.auth.models import User, Group
from django.core.validators import email_re
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.models import get_current_site
from django.core.mail.message import EmailMessage
from django.template.loader import render_to_string
from django.utils.http import int_to_base36
from datawinners.entity.helper import get_country_appended_location, get_entity_type_fields, tabulate_data, entity_type_as_sequence, get_json_field_infos, get_organization_telephone_number

from datawinners.exceptions import InvalidEmailException, NameNotFoundException
from mangrove.data_cleaner import TelephoneNumber
from mangrove.datastore.documents import FormModelDocument
from mangrove.datastore.entity_type import get_all_entity_types
from datawinners.location.LocationTree import get_location_tree
from datawinners.main.utils import timebox
from datawinners.entity.entity_exceptions import InvalidFileFormatException
from mangrove.datastore.entity import get_all_entities, Entity
from mangrove.errors.MangroveException import MangroveException, DataObjectAlreadyExists
from mangrove.errors.MangroveException import CSVParserInvalidHeaderFormatException, XlsParserInvalidHeaderFormatException
from mangrove.form_model.form_model import REPORTER, get_form_model_by_code, get_form_model_by_entity_type, \
    NAME_FIELD_CODE, SHORT_CODE, MOBILE_NUMBER_FIELD, FormModel
from mangrove.transport.player.parser import CsvParser, XlsParser, XlsDatasenderParser
from mangrove.transport.contract.transport_info import Channel, TransportInfo
from mangrove.transport.contract.response import Response
from mangrove.transport.player.player import Player
from mangrove.datastore import entity
from mangrove.transport.work_flow import RegistrationWorkFlow, GeneralWorkFlow, ActivityReportWorkFlow
from datawinners.location.LocationTree import get_location_hierarchy
from datawinners.submission.location import LocationBridge
from mangrove.contrib.registration_validators import case_insensitive_lookup
from datawinners.accountmanagement.helper import get_all_registered_phone_numbers_on_trial_account
from mangrove.form_model.form_model import ENTITY_TYPE_FIELD_CODE, MOBILE_NUMBER_FIELD_CODE
from datawinners.utils import get_organization
from datawinners.accountmanagement.models import NGOUserProfile
from datawinners.settings import HNI_SUPPORT_EMAIL_ID, EMAIL_HOST_USER
from datawinners.questionnaire.helper import get_location_field_code


class FormCodeDoesNotMatchException(Exception):
    def __init__(self, message, form_code=None):
        self.message = message
        self.data = form_code

    def __str__(self):
        return self.message


class FilePlayer(Player):
    def __init__(self, dbm, parser, channel_name, location_tree=None):
        Player.__init__(self, dbm, location_tree)
        self.parser = parser
        self.channel_name = channel_name
        self.form_code = None
        self.logger = logging.getLogger("websubmission")

    @classmethod
    def build(cls, manager, extension, default_parser=None, form_code=None):
        channels = dict({".xls": Channel.XLS, ".csv": Channel.CSV})
        try:
            channel = channels[extension]
        except KeyError:
            raise InvalidFileFormatException()
        if default_parser is not None:
            parser = default_parser()
        elif extension == '.csv':
            parser = CsvParser()
        elif extension == '.xls':
            parser = XlsParser()
        else:
            raise InvalidFileFormatException()
        player = FilePlayer(manager, parser, channel, location_tree=LocationBridge(get_location_tree(),
                                                                                   get_loc_hierarchy=get_location_hierarchy))
        player.form_code = form_code
        return player

    def _process(self, form_model, values):
        if form_model.is_entity_registration_form():
            values = RegistrationWorkFlow(self.dbm, form_model, self.location_tree).process(values)
        if form_model.is_entity_type_reporter():
            reporter_entity = entity.get_by_short_code(self.dbm, values.get(form_model.entity_question.code.lower()),
                                                       form_model.entity_type)
            values = ActivityReportWorkFlow(form_model, reporter_entity).process(values)
        return values

    def _appendFailedResponse(self, message, values=None):
        response = Response(reporters=[], survey_response_id=None)
        response.success = False
        response.errors = dict(error=ugettext(message), row=values)
        return response

    def _create_user(self, email, organization, response):
        user = User.objects.create_user(email, email, 'password')
        group = Group.objects.filter(name="Data Senders")[0]
        user.groups.add(group)
        user.first_name = case_insensitive_lookup(response.processed_data, NAME_FIELD_CODE)
        user.save()
        profile = NGOUserProfile(user=user, org_id=organization.org_id, title="Mr",
                                 reporter_id=case_insensitive_lookup(response.processed_data, SHORT_CODE))
        profile.save()
        return user

    def _import_data_sender(self, form_model, organization, registered_emails, registered_phone_numbers, submission,
                           values):
        email = case_insensitive_lookup(values, "email")
        if email:
            if not email_re.match(email):
                raise InvalidEmailException(message="Invalid email address.")

            if email in registered_emails:
                raise DataObjectAlreadyExists(_("User"), _("email address"), email)

            response = self.submit(form_model, values, submission, [])

            if response.success:
                user = self._create_user(email, organization, response)
                send_email_to_data_sender(user, _("en"))
        else:
            response = self.submit(form_model, values, submission, [])
        return response

    def _append_country_for_location_field(self, form_model, values, organization):
        location_field_code = get_location_field_code(form_model)
        if location_field_code is None:
            return values
        if location_field_code in values and values[location_field_code]:
            values[location_field_code] = get_country_appended_location(values[location_field_code], organization.country_name())
        return values

    def _import_submission(self, form_code, organization, registered_emails, registered_phone_numbers, values, form_model=None):
        self._append_country_for_location_field(form_model, values, organization)
        transport_info = TransportInfo(transport=self.channel_name, source=self.channel_name, destination="")
        submission = self._create_submission(transport_info, form_code, copy(values))
        try:
            values = self._process(form_model, values)
            log_entry = "message: " + str(values) + "|source: web|"
            if case_insensitive_lookup(values, ENTITY_TYPE_FIELD_CODE) == REPORTER:
                response = self._import_data_sender(form_model, organization, registered_emails,
                                                   registered_phone_numbers, submission, values)
            else:
                response = self.submit(form_model, values, submission, [])

            if not response.success:
                response.errors = dict(error=response.errors, row=values)
                log_entry += "Status: False"
            else:
                log_entry += "Status: True"
            self.logger.info(log_entry)
            return response
        except DataObjectAlreadyExists as e:
            if self.logger is not None:
                log_entry += "Status: False"
                self.logger.info(log_entry)
            return self._appendFailedResponse("%s with %s = %s already exists." % (e.data[2], e.data[0], e.data[1]),
                                                values=values)
        except (InvalidEmailException, MangroveException, NameNotFoundException) as e:
            return self._appendFailedResponse(e.message, values=values)

    def _get_registered_emails(self):
        if type(self.parser) == XlsDatasenderParser:
            registered_emails = User.objects.values_list('email', flat=True)
        else:
            registered_emails = []
        return registered_emails

    def _get_form_model(self, rows):
        form_model = None
        if len(rows) > 0:
            (form_code, values) = rows[0]
            form_model = get_form_model_by_code(self.dbm, form_code)
            if self.form_code is not None and form_code != self.form_code:
                form_model = get_form_model_by_code(self.dbm, self.form_code)
                raise FormCodeDoesNotMatchException(
                    ugettext('The file you are uploading is not a list of [%s]. Please check and upload again.') %
                    form_model.entity_type[0], form_code=form_code)
        return form_model

    def _get_phone_numbers(self, organization):
        return get_all_registered_phone_numbers_on_trial_account() \
            if organization.in_trial_mode else get_datasenders_mobile(self.dbm)

    def accept(self, file_contents):
        from datawinners.utils import get_organization_from_manager

        organization = get_organization_from_manager(self.dbm)
        registered_phone_numbers = self._get_phone_numbers(organization)
        rows = self.parser.parse(file_contents)
        form_model = self._get_form_model(rows)
        responses = []
        registered_emails = self._get_registered_emails()
        for (form_code, values) in rows:
            responses.append(
                self._import_submission(form_code, organization, registered_emails, registered_phone_numbers,values, form_model))
        return responses

#TODO This is a hack. To be fixed after release. Introduce handlers and get error objects from mangrove
def translate_errors(items, question_dict={}, question_answer_dict={}):
    errors = []
    for key, value in items:

        answer, question_label = _get_answer_and_question_label(question_answer_dict, question_dict, key)

        # todo the ds & subject import errors will now start showing question_label than quotes. Do we need to have that?

        if 'is required' in value:
            errors.append(_('Answer for question %s is required.') % (question_label, ))

        elif 'Expected date in mm.yyyy format' in value:
            errors.append(_('Answer %s for question %s is invalid. Expected date in %s format') % (answer, question_label, ' mm.yyyy'))

        elif 'Expected date in dd.mm.yyyy format' in value:
            errors.append(_('Answer %s for question %s is invalid. Expected date in %s format') % (answer, question_label, 'dd.mm.yyyy'))

        elif 'Expected date in mm.dd.yyyy format' in value:
            errors.append(_('Answer %s for question %s is invalid. Expected date in %s format') % (answer, question_label, 'mm.dd.yyyy'))

        elif 'smaller than allowed' in value:
            errors.append(_('Answer %s for question %s is smaller than allowed.') % (answer, question_label))

        elif 'greater than allowed' in value:
            errors.append(_('Answer %s for question %s is greater than allowed.') % (answer, question_label))

        elif 'is of the wrong type' in value:
            errors.append(_('Answer %s for question %s is of the wrong type.') % (answer, question_label))

        elif 'contains more than one value' in value:
            errors.append(_('Answer %s for question %s contains more than one value.') % (answer, question_label))

        elif 'not present in the allowed options' in value:
            errors.append(_('Answer %s for question %s is not present in the allowed options.') % (answer, question_label))

        elif 'xx.xxxx yy.yyyy' in value:
            errors.append(_(
                'Incorrect GPS format. The GPS coordinates must be in the following format: xx.xxxx,yy.yyyy. Example -18.8665,47.5315.'))

        elif 'longer' in value:
            errors.append(_("Answer %s for question %s is longer than allowed") % (answer, question_label))

        elif 'Subject does not matched' in value:
            errors.append(_("The unique ID %s of the Subject does not match with any existing Subject ID. Please correct and import again.") % (answer))

        elif 'Data Sender ID not matched' in value:
            errors.append(_("The unique ID %s of the Data Sender does not match with any existing Data Sender ID. Please correct and import again.") % (answer))

        elif 'shorter' in value:
            errors.append(_("Answer %s for question %s is shorter than allowed.") % (answer, question_label))

        elif 'must be between' in value:
            # todo check the usage and remove the split
            text = value.split(' ')[2]
            low = value.split(' ')[6]
            high = value.split(' ')[8]
            errors.append(_("The answer %s must be between %s and %s.") % (text, low, high))
        else:
            errors.append(_(value))
    return errors

def _get_answer_and_question_label(question_answer_dict, question_dict, question_code):
    return question_answer_dict.get(question_code), question_dict.get(question_code, question_code)


def _get_form_model_questions(manager, row):
    return {'n':'&#39;Name&#39;', 'm':'&#39;Mobile Number&#39;'} if 'reporter' in row[1].entity_type else\
        get_form_model_by_code(manager, row[1].form_code).get_field_code_label_dict()

def tabulate_failures(rows,manager):
    tabulated_data = []
    form_model = None
    questions_dict = {}

    for row in rows:
        if form_model is None and row[1].form_code:
            questions_dict = _get_form_model_questions(manager,row)
        row[1].errors['row_num'] = row[0] + 2

        if isinstance(row[1].errors['error'], dict):

            errors = translate_errors(items=row[1].errors['error'].items(),question_dict=questions_dict, question_answer_dict=row[1].errors['row'])
        else:
            errors = [_(row[1].errors['error'])]

        row[1].errors['error'] = "<br>".join(errors)
        row[1].errors.pop('row')
        tabulated_data.append(row[1].errors)
    return tabulated_data

def tabulate_success(success_responses):
    tabulated_data = []
    for success_response in success_responses:
        tabulated_data.append(success_response.processed_data)
    return tabulated_data


def _get_entity_type_from_row(row):
    type = row['doc']['aggregation_paths']['_type']
    return type


def load_entity_registration_data(manager,
                                  type=REPORTER, tabulate_function=tabulate_data):
    entity_type = entity_type_as_sequence('registration' if type == REPORTER else type)
    form_model = get_form_model_by_entity_type(manager, entity_type)

    fields, labels, codes = get_entity_type_fields(manager, form_model.form_code)
    entities = get_all_entities(dbm=manager, entity_type=entity_type_as_sequence(type))
    data = []
    for entity in entities:
        data.append(tabulate_function(entity, form_model, codes))
    return data, fields, labels


def get_entity_types(manager):
    entity_types = get_all_entity_types(manager)
    return [entity_type[0] for entity_type in entity_types if entity_type[0] != 'reporter']


def get_field_infos(fields):
    fields_names, labels, codes = [], [], []
    for field in fields:
        if field.name != 'entity_type':
            fields_names.append(field.name)
            labels.append(field.label)
            codes.append(field.code)
    return fields_names, labels, codes


def get_entity_type_info(entity_type, manager=None):
    if entity_type == 'reporter':
        form_code = 'reg'
        form_model = manager.load_all_rows_in_view("questionnaire", key=form_code)[0]
        names, labels, codes = get_json_field_infos(form_model.value['json_fields'])
    else:
        form_model = get_form_model_by_entity_type(manager, entity_type_as_sequence(entity_type))
        form_code = form_model.form_code
        names, labels, codes = get_field_infos(form_model.fields)

    return dict(entity=entity_type, code=form_code, names=names, labels=labels, codes=codes, data=[])


def _from_row_to_subject(dbm, row):
    return Entity.new_from_doc(dbm=dbm, doc=Entity.__document_class__.wrap(row.get('value')))


def _get_subject_type_infos(subject_types, form_models_grouped_by_subject_type):
    subject_types_dict = {}
    default_form_model = form_models_grouped_by_subject_type.get('registration')

    for subject_type in subject_types:
        form_model = form_models_grouped_by_subject_type.get(subject_type, default_form_model)
        names, labels, codes = zip(*[(field.name, field.label, field.code) for field in form_model.fields])
        subject_types_dict[subject_type] = dict(entity=subject_type,
                                                code=form_model.form_code,
                                                names=names,
                                                labels=labels,
                                                codes=codes,
                                                data=[], )
    return subject_types_dict


@timebox
def get_subject_form_models(manager):
    form_models = {}
    form_model_values = manager.load_all_rows_in_view('questionnaire')
    for each in form_model_values:
        form_model = FormModel.new_from_doc(manager, FormModelDocument.wrap(each['value']))
        if form_model.is_entity_registration_form() and not form_model.is_entity_type_reporter():
            form_models[form_model.entity_type[0]] = form_model
    return form_models


@timebox
def get_all_subjects(manager):
    rows = manager.view.all_subjects()
    return [_from_row_to_subject(manager, row) for row in rows]


def _get_all_subject_data(form_models, subject_types, subjects):
    subject_type_infos_dict = _get_subject_type_infos(subject_types, form_models)
    for subject in subjects:
        subject_type = subject.type_string
        if subject_type in subject_type_infos_dict.keys():
            form_model = form_models[subject_type]
            data = tabulate_data(subject, form_model, subject_type_infos_dict[subject_type]['codes'])
            subject_type_infos_dict[subject_type]['data'].append(data)

    return [subject_type_infos_dict[subject_type] for subject_type in subject_types]


def load_all_entities_of_type(manager, type=REPORTER):
    return load_entity_registration_data(manager, type)


def _handle_uploaded_file(file_name, file, manager, default_parser=None, form_code=None):
    base_name, extension = os.path.splitext(file_name)
    player = FilePlayer.build(manager, extension, default_parser=default_parser, form_code=form_code)
    responses = player.accept(file)
    return responses


def _get_imported_entities(responses):
    short_codes = dict()
    datarecords_id = []
    form_code = []
    for response in responses:
        if response.success:
            short_codes.update({response.short_code: response.entity_type[0]})
            datarecords_id.append(response.datarecord_id)
            if response.form_code not in form_code:
                form_code.append(response.form_code)
    return {"short_codes": short_codes, "datarecords_id": datarecords_id, "form_code": form_code}


def _get_failed_responses(responses):
    return [i for i in enumerate(responses) if not i[1].success]

def _get_successful_responses(responses):
    return [response for response in responses if response.success]


@timebox
def _get_entity_types(manager):
    entity_types = get_all_entity_types(manager)
    entity_list = [entity_type[0] for entity_type in entity_types if entity_type[0] != 'reporter']
    return sorted(entity_list)


@timebox
def load_all_subjects(manager):
    subject_types = _get_entity_types(manager)
    form_models = get_subject_form_models(manager)
    subjects = get_all_subjects(manager)

    return _get_all_subject_data(form_models, subject_types, subjects)


def import_data(request, manager, default_parser=None, form_code=None):
    response_message = ''
    error_message = None
    failure_imports = None
    successful_imports = None
    imported_entities = {}
    try:
        #IE sends the file in request.FILES['qqfile'] whereas all other browsers in request.GET['qqfile']. The following flow handles that flow.
        file_name, file = get_filename_and_contents(request)
        responses = _handle_uploaded_file(file_name=file_name, file=file, manager=manager,
                                          default_parser=default_parser, form_code=form_code)
        imported_entities = _get_imported_entities(responses)
        form_code = imported_entities.get("form_code")[0] if len(imported_entities.get("form_code")) == 1 else None

        if form_code is not None and \
                len(imported_entities.get("datarecords_id")) and settings.CRS_ORG_ID == get_organization(
                request).org_id:
            from django.core.management import call_command

            datarecords_id = imported_entities.get("datarecords_id")
            call_command('crs_datamigration', form_code, *datarecords_id)

        imported_entities = imported_entities.get("short_codes")
        successful_import_count = len(imported_entities)
        total = len(responses)
        if total == 0:
            error_message = _("The imported file is empty.")
        failures = _get_failed_responses(responses)
        successes = _get_successful_responses(responses)
        failure_imports = tabulate_failures(failures,manager)
        successful_imports = tabulate_success(successes)
        response_message = ugettext_lazy('%s of %s records uploaded') % (successful_import_count, total)
    except CSVParserInvalidHeaderFormatException or XlsParserInvalidHeaderFormatException as e:
        error_message = e.message
    except InvalidFileFormatException:
        error_message = _(u"We could not import your data ! You are using a document format we canʼt import. Please use the excel (.xls) template file!")
    except FormCodeDoesNotMatchException as e:
        error_message = e.message
    except Exception:
        error_message = _(u"Some unexpected error happened. Please check the excel file and import again.")
        if settings.DEBUG:
            raise
    return error_message, failure_imports, response_message, imported_entities , successful_imports


def _file_and_name_for_ie(request):
    file_name = request.FILES.get('qqfile').name
    file = request.FILES.get('qqfile').read()
    return file_name, file


def _file_and_name(request):
    file_name = request.GET.get('qqfile')
    file = request.raw_post_data
    return file_name, file


def get_datasenders_mobile(manager):
    all_data_senders, fields, labels = load_all_entities_of_type(manager)
    index = fields.index(MOBILE_NUMBER_FIELD)
    return [ds["cols"][index] for ds in all_data_senders]


def send_email_to_data_sender(user, language_code, request=None, type="activation",organization=None):
    site = get_current_site(request)
    ctx_dict = {
        'domain': site.domain,
        'uid': int_to_base36(user.id),
        'user': user,
        'token': default_token_generator.make_token(user),
        'protocol': 'http',
        'site': site,
    }
    types = dict({"activation":
                      dict({"subject": 'activatedatasenderemail/activation_email_subject_for_data_sender_account_',
                            "subject_param": False,
                            "template": 'activatedatasenderemail/activation_email_for_data_sender_account_'}),
                  "created_user":
                      dict({"subject": 'registration/created_user_email_subject_',
                            "subject_param": site.domain,
                            "template": 'registration/created_user_email_'})})
    if type not in types:
        return
    action = types.get(type)
    subject = render_to_string(action.get("subject") + str(language_code) + '.txt')
    subject = ''.join(subject.splitlines())
    if action.get("subject_param"):
        subject = subject % action.get("subject_param")

    if request is not None:
        ctx_dict.update({"creator_user": request.user.first_name})
        if organization:
            ctx_dict.update({"org_number":get_organization_telephone_number(request)})
    message = render_to_string(action.get("template") + language_code + '.html', ctx_dict)
    email = EmailMessage(subject, message, EMAIL_HOST_USER, [user.email], [HNI_SUPPORT_EMAIL_ID])
    email.content_subtype = "html"
    email.send()


def get_filename_and_contents(request):
    return _file_and_name(request) if 'qqfile' in request.GET else _file_and_name_for_ie(request)