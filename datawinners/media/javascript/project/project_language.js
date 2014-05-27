function ProjectLanguageViewModel(){
  var self = this;

  self.available_languages = [];
  self.enable_sms_replies = ko.observable(true);
  self.selected_language = ko.observable();
  self.is_modified = false;

    self.selected_language.subscribe(function(){
      self.is_modified = true;
  });

    self.enable_sms_replies.subscribe(function(){
      self.is_modified = true;
  });

  self.save = function(){
      var data = {
        'enable_sms_replies': self.enable_sms_replies(),
        'selected_language': self.selected_language(),
        'csrfmiddlewaretoken':$('input[name=csrfmiddlewaretoken]').val()
      };
      $.ajax({
          type: "POST",
          url: post_url,
          data: data,
          success: function(response){
              if(response.success){
                self.is_modified = false;
                flash_message("#flash-message-section", "Changes saved successfully", true);
              }
              else{
                flash_message("#flash-message-section", "Save Failed!", false);
              }
          },
          dataType: 'json'
      });
  };

}

$(function(){
    var viewModel = new ProjectLanguageViewModel();
    window.viewModel = viewModel; //for debugging
    viewModel.available_languages = languages_list;
    viewModel.selected_language(current_project_language);
    var options = {
        successCallBack:function(callback){
            viewModel.save();
            callback();
        },
        isQuestionnaireModified : function(){return viewModel.is_modified;},
        cancelDialogDiv : "#cancel_language_changes_warning",
        validate: function(){
            return true;
        }
    };
    new DW.CancelWarningDialog(options).init().initializeLinkBindings();
    ko.applyBindings(viewModel, $("#project_language_section")[0]);
});