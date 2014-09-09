DW.init_delete_periodicity_question_warning = function(){
    var kwargs = {container: "#delete_periodicity_question_warning",
        title: gettext('Warning: Your Collected Data Will be Lost'),
        width: 700,
        continue_handler: function(){
            question = questionnaireViewModel.selectedQuestion();
            questionnaireViewModel.removeQuestion(question);
        }
    };
    DW.delete_periodicity_question_warning = new DW.warning_dialog(kwargs);
};

basic_project_info = function(){
        var name = questionnaireViewModel.projectName() || '';
        var language = questionnaireViewModel.language();
        return JSON.stringify({'name':name, 'language':language});
};

DW.post_project_data = function (callback) {
    var questionnaire_data = JSON.stringify(ko.toJS(questionnaireViewModel.questions()));
    var post_create_request = function(original_questionnaire){

    var post_data = {
                      'questionnaire-code':questionnaireViewModel.questionnaireCode(),
                      'question-set':questionnaire_data,
                      'profile_form':basic_project_info(),
                      'csrfmiddlewaretoken':$('#question_form input[name=csrfmiddlewaretoken]').val()
                    };
        if (typeof original_questionnaire != "undefined"){
            post_data["datasenders"] = JSON.stringify(original_questionnaire.datasenders);
            post_data["reminder_and_deadline"] = JSON.stringify(original_questionnaire.reminder_and_deadline);
            post_data["is_outgoing_sms_enabled"] = original_questionnaire.is_outgoing_sms_enabled;
        }

        $.post(post_url , post_data).done(function(response){
            var responseJson = $.parseJSON(response);
            if (responseJson.success) {
               return callback(responseJson);
            }
            else {
                $.unblockUI();
                if(!(responseJson.code_has_errors || responseJson.name_has_errors)) {
                    questionnaireViewModel.errorInResponse(true);
                }
                if(responseJson.code_has_errors) {
                    questionnaireViewModel.questionnaireCode.setError(responseJson.error_message['code']);
                }
                if(responseJson.name_has_errors) {
                    questionnaireViewModel.projectName.setError(responseJson.error_message['name']);
                }
            }
        });
    };
    original_questionnaire_id = questionnaireCreationOptionsViewModel.selectedQuestionnaireId();
    if(original_questionnaire_id){
    questionnaireDataFetcher.getQuestionnaire(questionnaireCreationOptionsViewModel.selectedQuestionnaireId()).done(function(original_questionnaire){
        post_create_request(original_questionnaire);
    });
    } else {
        post_create_request();
    }
};


DW.controllers = {
    "templateQuestionnaire":function () {
            questionnaireViewModel.clearQuestionnaire();
            templateFetcher.getTemplateData(this.params.template_id).done(function(templateData){
                questionnaireViewModel.projectName(templateData.project_name);
                questionnaireViewModel.language(templateData.project_language);
                questionnaireViewModel.questionnaireCode(templateData.questionnaire_code);
                DW.existing_questions = templateData.existing_questions;
                $(templateData.existing_questions).each(function (index, question) {
                    questionnaireViewModel.loadQuestion(new DW.question(question));
                });
                questionnaireViewModel.showQuestionnaireForm(true);
                questionnaireCreationOptionsViewModel.showQuestionnaireCreationOptions(false);
                DW.trackEvent('questionnaire-creation-method', 'copy-from-template');
            });
    },
    "copyQuestionnaire": function(){
        questionnaireViewModel.clearQuestionnaire();
        var questionnaireData = questionnaireDataFetcher.getQuestionnaireData(this.params.questionnaire_id);
        questionnaireViewModel.language(questionnaireData.language);
        var question_list = questionnaireData.questions;
        for (var index in question_list) {
            var questions = new DW.question(question_list[index]);
            questionnaireViewModel.loadQuestion(questions);
        };
        questionnaireCreationOptionsViewModel.showQuestionnaireCreationOptions(false);
        questionnaireViewModel.showQuestionnaireForm(true);
        questionnaireViewModel.enableQuestionnaireTitleFocus(true);
        questionnaireViewModel.questionnaireCode(questionnaire_code);
        DW.trackEvent('questionnaire-creation-method', 'copy-questionnaire');
    },
    "blankQuestionnaire": function () {
            questionnaireViewModel.clearQuestionnaire();
            questionnaireViewModel.showQuestionnaireForm(true);
            questionnaireCreationOptionsViewModel.showQuestionnaireCreationOptions(false);
            questionnaireViewModel.questionnaireCode(questionnaire_code);
            questionnaireViewModel.enableQuestionnaireTitleFocus(true);
            DW.trackEvent('questionnaire-creation-method', 'blank-questionnaire');
    },
    "uploadQuestionnaire": function(){
        questionnaireViewModel.clearQuestionnaire();
        questionnaireCreationOptionsViewModel.showQuestionnaireCreationOptions(false);
        questionnaireViewModel.questionnaireCode(questionnaire_code);
        questionnaireViewModel.enableQuestionnaireTitleFocus(true);
        questionnaireViewModel.isXLSUploadQuestionnaire(true);
        DW.trackEvent('questionnaire-creation-method', 'advanced-questionnaire');
    },
    "questionnaireCreationOptions": function () {
            questionnaireCreationOptionsViewModel.resetCreationOption();
            questionnaireDataFetcher.clearCache();
            questionnaireViewModel.showQuestionnaireForm(false);
            questionnaireViewModel.isXLSUploadQuestionnaire(false);
            questionnaireCreationOptionsViewModel.showQuestionnaireCreationOptions(true);
    }
};


DW.projectRouter = Sammy(function () {
        this.get('#questionnaire/new', DW.controllers.blankQuestionnaire);
        this.get('#questionnaire/load/:template_id', DW.controllers.templateQuestionnaire);
        this.get('#questionnaire/copy/:questionnaire_id', DW.controllers.copyQuestionnaire);
        this.get('#questionnaire/xlsupload/$', DW.controllers.uploadQuestionnaire);
        this.get('project/wizard/create/$', DW.controllers.questionnaireCreationOptions);
});

function _initializeViewModel() {
    ko.setTemplateEngine(new ko.nativeTemplateEngine());
    window.questionnaireViewModel = new ProjectQuestionnaireViewModel();
    ko.applyBindings(questionnaireViewModel, $('#create_questionnaire')[0]);
    ko.applyBindings(questionnaireCreationOptionsViewModel, $('#project_profile')[0]);
}

function _save_questionnaire(callback) {
    if(!DW.check_empty_questionnaire() || !questionnaireViewModel.validateForSubmission())
        return false;

    $.blockUI({ message: '<h1><img src="/media/images/ajax-loader.gif"/><span class="loading">' + gettext("Just a moment") + '...</span></h1>', css: { width: '275px'}});
    DW.post_project_data(callback);
}
$(document).ready(function () {
    _initializeViewModel();
    DW.option_warning_dialog.init();
    new DW.UniqueIdHelpSection().init();
    DW.init_delete_periodicity_question_warning();
    DW.init_empty_questionnaire_warning();
    new DW.XLSHelpSection();
    DW.XLSSampleSectionTracker();


    var options = {
                    successCallBack: _save_questionnaire,
                    isQuestionnaireModified: function(){
                                                return questionnaireViewModel.showQuestionnaireForm() &&
                                                    (DW.questionnaire_was_changed || questionnaireViewModel.questions().length > 0);
                                            },
                    validate:function(){
                       return questionnaireViewModel.validateSelectedQuestion() && questionnaireViewModel.validateQuestionnaireDetails()
                    }
                  };
    new DW.CancelWarningDialog(options).init().initializeLinkBindings();

    $("#save_and_create").on("click", function () {
            _save_questionnaire(function (response) {
                var redirect_url = '/project/overview/' + response.project_id;
                DW.trackEvent('questionnaire-creation-method', 'simple-qns-success');
                window.location.replace(redirect_url);
                return true;
            });
    });

    new DW.UploadQuestionnaire({
        buttonText: "Upload XLSForm and Create Questionnaire",
        postUrl: function(){
           return '/xlsform/upload/';
        },
        params : function(){return {'pname':questionnaireViewModel.projectName(),'form_code':questionnaireViewModel.questionnaireCode()};},
        preUploadValidation: function(){
            var questionnaireName = questionnaireViewModel.projectName;
            DW.ko.mandatoryValidator(questionnaireName);
            return questionnaireName.valid();
        },
        postSuccessSave: function(responseJSON){
            DW.trackEvent('questionnaire-creation-method', 'advanced-qns-success');
            window.location.replace('/project/overview/' + responseJSON.project_id +'/');
        },
        postErrorHandler: function(responseJSON){
            DW.trackEvent('questionnaire-creation-method', 'advanced-qns-errored');
            if(responseJSON.duplicate_project_name){
                questionnaireViewModel.projectName.setError(responseJSON.error_msg[0]);
            }
            else{
                DW.showError(responseJSON.error_msg,responseJSON.message_prefix, responseJSON.message_suffix);
            }
        }
    });

    DW.projectRouter.run();

});


