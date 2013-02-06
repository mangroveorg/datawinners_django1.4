from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.template import RequestContext
from accountmanagement.views import is_not_expired, session_not_expired
from alldata.helper import get_visibility_settings_for
from main.utils import get_database_manager
from mangrove.form_model.form_model import  FormModel
from mangrove.transport.player.player import WebPlayer
from mangrove.transport.submissions import get_submission_by_id
from project.models import Project
from project.views import _get_form_context
from project.web_questionnaire_form_creator import WebQuestionnaireFormCreator, SubjectQuestionFieldCreator
from datawinners.utils import get_organization_country

@login_required(login_url='/login')
@session_not_expired
@is_not_expired
def edit_submission(request, project_id=None, questionnaire_code=None, submission_id=None):
    manager = get_database_manager(request.user)
    project = Project.load(manager.database, project_id)
    form_model = FormModel.get(manager, project.qid)
    is_data_sender = request.user.get_profile().reporter
    template = "project/web_questionnaire.html"

    QuestionnaireForm = WebQuestionnaireFormCreator(SubjectQuestionFieldCreator(manager, project),
        form_model=form_model).create()
    submission = get_submission_by_id(manager, submission_id)

    questionnaire_form = QuestionnaireForm()
    form_context = _make_form_context(questionnaire_form, project)
    if request.method == 'GET':
        _map_submission_and_questionnaire(submission[0], questionnaire_form)
        return render_to_response(template, form_context,
            context_instance=RequestContext(request))
    if request.method == 'POST':
        questionnaire_form = QuestionnaireForm(country=get_organization_country(request), data=request.POST)
        return edit_my_submission(request, submission[0], questionnaire_form, manager, project, form_model,form_context)


def edit_my_submission(request, submission, questionnaire_form, manager, project, form_model,form_context):
    webplayer = WebPlayer(manager).submit(form_model,request.POST,submission,[],True)
    form_code_for_project_links = form_model.form_code
    disable_link_class, hide_link_class = get_visibility_settings_for(request.user)
    template = "project/web_questionnaire.html"
#    temp = dict()
#    temp1 = request.POST
    if not questionnaire_form.is_valid():
        form_context = _get_form_context(form_code_for_project_links, project, questionnaire_form,
            manager, hide_link_class, disable_link_class)
        return render_to_response(template, form_context,context_instance=RequestContext(request))

#    submission.update()
#    for key,value in submission[0].values.iteritems():
#        temp.update({key: temp1.get(key.upper())})
#    submission[0].values.clear()
#    submission[0].values.update(temp)
#    submission1 = Submission(manager)
#    submission1 = submission[0]
#    submission.save()
    return render_to_response(template, form_context,
        context_instance=RequestContext(request))


def _make_form_context(questionnaire_form, project):
    return {'questionnaire_form': questionnaire_form,
            'project': project,
    }


def _map_submission_and_questionnaire(submission, questionnaire_form):
    for field_name, field in questionnaire_form.fields.iteritems():
        if not field.widget.is_hidden:
            field.initial = submission.values.get(field_name.lower())

