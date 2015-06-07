import ast
from datetime import datetime
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from datawinners.sent_message.models import PollInfo
from mangrove.form_model.project import Project, is_active_form_model
from django.template.context import RequestContext
from django.core.urlresolvers import reverse
from datawinners.accountmanagement.decorators import is_not_expired, is_datasender
from datawinners.common.lang.utils import get_available_project_languages
from datawinners.main.database import get_database_manager
from datawinners.project.helper import is_project_exist
from datawinners.project.views.views import get_project_link


def _is_active(questionnaire):
    is_active = False
    if questionnaire.active == "active":
        is_active = True
    return is_active


def _is_same_questionnaire(question_id_active, questionnaire):
    if questionnaire.id == question_id_active:
        is_active = True
    else:
        is_active = False
    return is_active


def _get_number_of_recipients_(project_id):
    num_of_recipients = 0
    poll_submissions = PollInfo.objects.filter(questionnaire_id=project_id)
    for poll_submission in poll_submissions:
        num_of_recipients += len(ast.literal_eval(poll_submission.recipients))
    return num_of_recipients


def _construct_poll_recipients(poll_submission):
    poll_recipient_map = {}
    poll_recipients = ast.literal_eval(poll_submission.recipients)
    for poll_recipient in poll_recipients:
        poll_recipient_name, poll_recipient_id = poll_recipient.split("(")
        poll_recipient_map.update({poll_recipient_name: poll_recipient_id.strip(")")})
    return poll_recipient_map


def _get_poll_sent_messages_info(project_id):
    messages = {}
    messages_poll_info_array = []
    poll_submissions = PollInfo.objects.filter(questionnaire_id=project_id)
    for poll_submission in poll_submissions:
        messages['sent_on'] = poll_submission.sent_on
        messages['message'] = poll_submission.message
        poll_recipient_map = _construct_poll_recipients(poll_submission)
        messages['poll_recipient_map'] = poll_recipient_map
        messages['sender'] = poll_submission.sender
        messages_poll_info_array.append(messages)
    return messages_poll_info_array


@login_required
@csrf_exempt
@is_not_expired
def get_poll_info(request, project_id):
    messages_poll_info_array = _get_poll_sent_messages_info(project_id)
    return HttpResponse(json.dumps({'success': True, 'poll_messages': messages_poll_info_array}))



@login_required
@csrf_exempt
@is_not_expired
@is_project_exist
@is_datasender
def poll(request, project_id):
    manager = get_database_manager(request.user)
    questionnaire = Project.get(manager, project_id)
    project_links = get_project_link(questionnaire)
    is_active = _is_active(questionnaire)
    questionnaire_active, question_id_active, question_name_active = is_active_form_model(manager)
    from_date = questionnaire.modified.date()
    to_date = questionnaire.end_date.date()
    languages_list = get_available_project_languages(manager)
    current_project_language = questionnaire.language
    num_of_recipients = _get_number_of_recipients_(project_id)
    messages_poll_info_array = _get_poll_sent_messages_info(project_id)
    return render_to_response('project/poll.html', RequestContext(request, {
        'project': questionnaire,
        'project_links': project_links,
        'is_active': is_active,
        'from_date': from_date,
        'to_date': to_date,
        'questionnaire_id': question_id_active,
        'questionnaire_name': question_name_active,
        'languages_list': json.dumps(languages_list),
        'languages_link': reverse('languages'),
        'current_project_language': current_project_language,
        'post_url': reverse("project-language", args=[questionnaire.id]),
        'get_poll_info': reverse("get_poll_info", args=[questionnaire.id]),
        'questionnaire_code': questionnaire.form_code,
        'num_of_recipients': num_of_recipients,
        'poll_messages': messages_poll_info_array
    }))


def _change_questionnaire_status(questionnaire, active_status):
    questionnaire.active = active_status
    questionnaire.save()


def _change_questionnaire_end_date(questionnaire, end_date):
    questionnaire.end_date = end_date
    questionnaire.save()


@login_required
@csrf_exempt
@is_not_expired
def deactivate_poll(request, project_id):
    if request.method == 'POST':
        manager = get_database_manager(request.user)
        questionnaire = Project.get(manager, project_id)
        if questionnaire:
            _change_questionnaire_status(questionnaire, "deactivated")
            return HttpResponse(json.dumps({'success': True}))
        return HttpResponse(json.dumps({'success': False}))


@login_required
@csrf_exempt
@is_not_expired
def activate_poll(request, project_id):
    if request.method == 'POST':
        manager = get_database_manager(request.user)
        questionnaire = Project.get(manager, project_id)
        if questionnaire:
            is_active, question_id_active, question_name_active = is_active_form_model(manager)
            is_current_active = _is_same_questionnaire(question_id_active, questionnaire)
            end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%dT%H:%M:%S')
            if not is_active and not is_current_active:
                _change_questionnaire_status(questionnaire, "active")
                _change_questionnaire_end_date(questionnaire, end_date)
                return HttpResponse(json.dumps({'success': True}))
            elif is_current_active:
                _change_questionnaire_end_date(questionnaire, end_date)
                return HttpResponse(json.dumps({'success': True}))
        return HttpResponse(json.dumps({'success': False, 'message': "No Such questionnaire"}))
