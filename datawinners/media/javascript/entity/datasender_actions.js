//this file is being used as delete handler in datasenders/index.js and registered datasender
$(document).ready(function () {
    $("#delete_entity_block").dialog({
            title: gettext("Warning !!"),
            modal: true,
            autoOpen: false,
            width: 500,
            closeText: 'hide'
        }
    );

    $("#delete_entity_block .cancel_link").bind("click", function() {
        $("#delete_entity_block").dialog("close");
        $('#delete_entity_block').data("action_element").value = "";
        return false;
    });


    $("#ok_button").bind("click", function() {
        $("#delete_entity_block").dialog("close");
        var allIds = $('#delete_entity_block').data("allIds");
        var entity_type = $('#delete_entity_block').data("entity_type");
        var path = $(this).attr("href");
        post_data = {'all_ids':allIds.join(';'), 'entity_type':entity_type}
        if ($("#project_name").length)
            post_data.project = $("#project_name").val();
        if($('#select_all_link').attr('class') == 'selected')
            post_data.all_selected = true;
        $.post("/entity/delete/", post_data,
            function (json_response) {
                var response = $.parseJSON(json_response);
                if (response.success) {
                    if ($("#project_name").length) {
                        window.location.reload(true);
                    } else {
                        window.location.href = path;
                    }
                }
            }
        );
        return false;
    });

});

function warnThenDeleteDialogBox(allIds, entity_type, action_element) {
    $("#delete_entity_block").data("allIds", allIds);
    $("#delete_entity_block").data("entity_type", entity_type);
    $("#delete_entity_block").data("action_element", action_element);

    $("#delete_entity_block").dialog("open");
}


DW.DataSenderActionHandler = function(){
  this.delete = function(table, selected_ids, all_selected){
        handle_datasender_delete(table, selected_ids);
  };
  this.edit = function(table, selected_ids){
    location.href = '/entity/datasender/edit' + '/' + selected_ids[0] + '/';
  };
  this.makewebuser = function(table, selected_ids, all_selected){
    populate_dialog_box_for_web_users(table);
  };
  this.associate = function(table, selected_ids, all_selected){
    add_remove_from_project('associate');
  };
  this.disassociate = function(table, selected_ids, all_selected){
    add_remove_from_project('disassociate');
  };
};

function add_remove_from_project(action) {
    $("#all_project_block").dialog({
        autoOpen: false,
        modal: true,
        title: gettext('Select Projects'),
        zIndex: 1100,
        beforeClose: function () {
            $('#action').at;
        }
    });

    $("#all_project_block .cancel_link").bind("click", function () {
        $("#all_project_block").dialog("close");
    });

    $("#all_project_block .button").bind("click", function () {
        $('#error').remove();
        var allIds = $.map($('#datasender_table .row_checkbox:checked'), function(e){return $(e).val();});
        var projects = [];
        $('#all_project_block :checked').each(function () {
            projects.push($(this).val());
        });
        if (projects.length == 0) {
            $('<div class="message-box" id="error">' + gettext("Please select atleast 1 Project")
                + '</div>').insertBefore($("#all_projects"));
        } else {
            var url = '/entity/' + action + '/';
            $.blockUI({ message: '<h1><img src="/media/images/ajax-loader.gif"/><span class="loading">'
                + gettext("Just a moment") + '...</span></h1>', css: { width: '275px', zIndex: 1000000}});
            $.ajax({
                        url: url,
                        type: "POST",
                        headers: {
                            "X-CSRFToken": $.cookie('csrftoken')
                        },
                        data: {
                            'ids': allIds.join(';'),
                            'project_id': projects.join(';')
                        }
                    }
            ).done(function (data) {
                    window.location.href = data;
                });
        }
    });

    $("#all_project_block").dialog("open");
}

get_users_from_selected_datasenders = function (table, selected_ids) {
    var users = {};
    users["ids"] = [];
    users["names"] = [];
    $(table).find('input.row_checkbox:checked').each(function () {
        var datasender_id = $(this).val();
        if ($.inArray(datasender_id ,users_list) >= 0) {
            users["ids"].push(datasender_id);
            users["names"].push($(this).parent().next().html());
        }
    });

    return users;
}

function delete_all_ds_are_users_show_warning(users) {


    var kwargs = {container: "#delete_all_ds_are_users_warning_dialog",
        cancel_handler: function () {
            $('#action').removeAttr("data-selected-action");
            $("input.is_user").attr("checked", false);
        },
        height: 150,
        width: 550
    }

    var delete_all_ds_are_users = new DW.warning_dialog(kwargs);
    $(delete_all_ds_are_users.container + " .users_list").html(users);
    delete_all_ds_are_users.show_warning();
}

function uncheck_users(table, user_ids){
    $.each(user_ids, function(id){
        $(table).find(":checked").filter("[value=rep25]").attr('checked',false);
    });
    return $.map($(table).find(":checked"), function(e){return $(e).val();});
}

function handle_datasender_delete(table, allIds){
    $("#note_for_delete_users").hide();
    var users = get_users_from_selected_datasenders(table, allIds);

    if (users["names"].length) {

        var users_list_for_html = "<li>" + users["names"].join("</li><li>") + "</li>";
        if (users["names"].length == allIds.length) { //Each DS selected is also User

            delete_all_ds_are_users_show_warning(users_list_for_html);
        } else { // A mix of Simple DS and DS having user credentials
            $("#note_for_delete_users .users_list").html(users_list_for_html);
            $("#note_for_delete_users").show();
            allIds = uncheck_users(table, users["ids"]);
            warnThenDeleteDialogBox(allIds, "reporter", this);
        }
    } else {
        warnThenDeleteDialogBox(allIds, "reporter", this);
    }
}


function populate_dialog_box_for_web_users(table) {
    var data_sender_details = [];
    $(table).find("input:checked").each(function () {
        var row = $(this).parent().parent();
        var data_sender = {};
        data_sender.short_name = $($(row).children()[2]).html();
        data_sender.name = $($(row).children()[1]).html();
        data_sender.location = $($(row).children()[4]).html();
        data_sender.contactInformation = $($(row).children()[8]).html();
        data_sender.email = $($(row).children()[6]).html();
        data_sender.input_field_disabled = "disabled";
        if (!$.trim(data_sender.email)) {
            data_sender.input_field_disabled = "";
            data_sender.email = "";
        }
        data_sender_details.push(data_sender);
    });
     var markup = "<tr><td>${short_name}</td><td>${name}</td><td style='width:150px;'>" +
        "${location}</td><td>${contactInformation}</td><td>" +
        "<input type='text' style='width:150px' class='ds-email' value='${email}' " +
        "${input_field_disabled}/></td></tr>";
    $.template("webUserTemplate", markup);
    $('#web_user_table_body').html($.tmpl('webUserTemplate', data_sender_details));
    $("#web_user_block").dialog({
        autoOpen: false,
        modal: true,
        title: gettext('Give Web Submission Access'),
        zIndex: 1100,
        width: 900,
        beforeClose: function () {
            $('#action').removeAttr("data-selected-action");
            $('#web_user_error').hide();
        }
    });
    $("#web_user_block .cancel_link").bind("click", function () {
        $("#web_user_block").dialog("close");
    });

    $('#web_user_button').click(function () {
        $('#web_user_error').hide();
        var post_data = [];
        var should_post = true;
        $('input:enabled.ds-email').each(function () {
            var email = $.trim($(this).val());
            var emailRegEx = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}$/i;
            if (email == "") {
                $('#web_user_error').html(gettext('Emails are mandatory'));
                $('#web_user_error').removeClass('none');
                $('#web_user_error').show();
                should_post = false;
                return false;
            }
            if ($.trim(email).search(emailRegEx) == -1) {
                $('#web_user_error').removeClass('none');
                $('#web_user_error').html(email + gettext(": is not a valid email"));
                $('#web_user_error').show();
                should_post = false;
                return false;
            }
            var reporter_id = $($(this).parent().parent().children()[0]).html();
            post_data.push({email: email, reporter_id: reporter_id});
        });
        if (!should_post || post_data.length == 0) {
            return;
        }
        $.blockUI({ message: '<h1><img src="/media/images/ajax-loader.gif"/><span class="loading">'
            + gettext("Just a moment") + '...</span></h1>', css: { width: '275px', zIndex: 1000000}});
        $.post('/entity/webuser/create', {post_data: JSON.stringify(post_data)},
            function (response) {
                $.unblockUI();
                var json_data = JSON.parse(response);
                if (json_data.success) {
                    $("#web_user_block").dialog("close");
                    var redirect_url = location.href;
                    if (redirect_url.indexOf('#') != -1) {
                        redirect_url = redirect_url.substr(0, redirect_url.indexOf('#'));
                    }
                    if (redirect_url.indexOf('?web=1') == -1) {
                        redirect_url = redirect_url + '?web=1';
                    }
                    window.location.href = redirect_url;
                } else {
                    var html = "";
                    var i = 0;
                    for (i; i < json_data.errors.length; i = i + 1) {
                        var email_in_error = json_data.errors[i].split(' ')[3];
                        var error_message = gettext('User with email ') + email_in_error + gettext(' already exists');
                        html += "<tr><td>" + error_message + "</td></tr>";
                    }
                    if (html != "") {
                        html = '<table cellpadding="0" cellspacing="0" border="0">' + html + '</table>';
                    }
                    $('#web_user_error').removeClass('none');
                    $('#web_user_error').html(html);
                    $('#web_user_error').show();
                }

            });
        return false;
    });


    $("#web_user_block").dialog("open")
}